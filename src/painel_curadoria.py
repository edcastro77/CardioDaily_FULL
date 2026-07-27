"""
painel_curadoria.py — O PAINEL DE CURADORIA (decisão do Dr. Eduardo, 27/Jul/2026).

MODELO (nas palavras do Dr. Eduardo):
  "O painel é pra eu olhar os temas, filtrados por nota. Se eu gostar, abro o PDF, o visual abstract
   e o áudio pra confirmar que não tem loucura. Se for bom mesmo, agendo pro grupo de médicos — quantos
   trabalhos eu quiser em cada dia — sempre vendo a agenda dos próximos 7 dias."

Ou seja: o sistema NÃO envia nada sozinho (só o Radar). Aqui o Dr. Eduardo REVISA e AGENDA/ENVIA pro
grupo de WhatsApp. "Não publicado" = ainda não foi pro grupo.

Rodar:  streamlit run src/painel_curadoria.py   (ou a Chave 5)
"""
from __future__ import annotations
import os, json, datetime, re
import requests
import streamlit as st
from dotenv import load_dotenv

_HERE = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(_HERE, "..", ".env"))

URL = os.getenv("SUPABASE_URL", "").rstrip("/")
KEY = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY", "")
HDR = {"apikey": KEY, "Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}
AGENDA = os.path.join(_HERE, "..", "outputs", "agenda_curadoria.json")   # {data_iso: [doc_id,...]}
ENVIADOS = os.path.join(_HERE, "..", "outputs", "enviados_grupo.json")   # {doc_id: data_iso}
WD = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
# Grupo WhatsApp "CardioDaily" (Z-API). Sobrescreve com ZAPI_GRUPO_ID no .env se mudar.
GRUPO_WPP = os.getenv("ZAPI_GRUPO_ID", "120363402464114458-group")

st.set_page_config(page_title="CardioDaily · Curadoria", page_icon="🫀", layout="wide")

TIPOS = ["Original", "Meta-análise", "Revisão", "Guideline", "Outro"]
# Sinais FORTES no título — reclassificam mesmo que o banco diga "original" (o campo tipo_estudo erra).
# ALTA PRECISÃO: 'guideline' só conta como TIPO de documento, não em 'guideline-directed/recommended/based'
# (frase comum em estudo ORIGINAL). Idem consenso/position statement, que são o tipo do trabalho.
_TIT_GUIDE = re.compile(
    r"clinical practice guideline|practice guidelines?\b|\bguidelines?\b(?![-\s]*(direct|recommend|base|adher|concord|eligib))"
    r"|consensus (statement|document|conference)|expert consensus|scientific statement"
    r"|position (paper|statement)|\bdiretriz(es)?\b", re.I)
_TIT_META = re.compile(r"meta-?analys|meta-?anális|metanál|network meta", re.I)
_TIT_REV = re.compile(r"systematic review|narrative review|scoping review|umbrella review"
                      r"|revisão sistemática|:\s*a review\b|state[- ]of[- ]the[- ]art", re.I)


def tipo_norm(t: str | None, titulo: str | None = None) -> str:
    """Normaliza o tipo em 4 categorias. Primeiro confia no TÍTULO quando ele grita revisão/meta/guideline
    (o campo tipo_estudo do banco erra: rotula revisão como 'original'). Só depois cai no campo do banco.
    Ordem importa: guideline → meta → revisão → original."""
    tt = titulo or ""
    if _TIT_GUIDE.search(tt): return "Guideline"
    if _TIT_META.search(tt): return "Meta-análise"
    if _TIT_REV.search(tt): return "Revisão"
    t = (t or "").lower()
    if "guide" in t or "diretriz" in t: return "Guideline"
    if "meta" in t: return "Meta-análise"
    if "revis" in t: return "Revisão"
    if "original" in t: return "Original"
    return "Outro"


# ───────────────────────────── Supabase ─────────────────────────────
@st.cache_data(ttl=120)
def buscar_artigos() -> list[dict]:
    campos = ("doc_id,titulo,revista,nota_aplicabilidade,nota_trabalho_estatistico,doenca_principal,"
              "data_publicacao,created_at,mcid_avaliacao,gancho_lista,gancho_abertura,resumo_markdown,"
              "caminho_pdf,caminho_audio,caminho_visual_abstract,tipo_estudo,doi")
    out, passo = [], 1000
    for salto in range(0, 20000, passo):
        r = requests.get(f"{URL}/rest/v1/artigos", headers=HDR, params={
            "select": campos, "descartado": "eq.false",
            "order": "created_at.desc", "limit": str(passo), "offset": str(salto)}, timeout=40)
        if r.status_code != 200:
            st.error(f"Supabase {r.status_code}: {r.text[:200]}"); break
        lote = r.json(); out += lote
        if len(lote) < passo: break
    return out


# ───────────────────────────── Estado local (agenda + enviados) ─────────────────────────────
def _ler(p):
    if os.path.exists(p):
        try: return json.load(open(p, encoding="utf-8"))
        except Exception: return {}
    return {}


def _grava(p, d):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    json.dump(d, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)


def proximos_7_dias() -> list[tuple[str, str]]:
    hoje = datetime.date.today()
    out = []
    for i in range(7):
        d = hoje + datetime.timedelta(days=i)
        rot = ("Hoje" if i == 0 else "Amanhã" if i == 1 else WD[d.weekday()]) + d.strftime(" %d/%m")
        out.append((d.isoformat(), rot))
    return out


def agendar(doc_id: str, data_iso: str | None):
    ag = _ler(AGENDA)
    for dia in list(ag): ag[dia] = [x for x in ag[dia] if x != doc_id]   # tira de qualquer dia
    if data_iso: ag.setdefault(data_iso, []).append(doc_id)
    ag = {k: v for k, v in ag.items() if v}
    _grava(AGENDA, ag)


def marcar_enviado(doc_id: str):
    env = _ler(ENVIADOS); env[doc_id] = datetime.date.today().isoformat(); _grava(ENVIADOS, env)


# ───────────────────────────── Envio (só quando VOCÊ manda) ─────────────────────────────
def enviar_grupo(artigo: dict, wpp: bool, tg: bool, phone: str) -> list[str]:
    import distribuidor as D
    msgs = []
    if tg:
        try:
            D.tg_send_text(D.montar_mensagem(artigo, html=True), html=True)
            if artigo.get("caminho_visual_abstract"): D.tg_send_image(artigo["caminho_visual_abstract"], caption=(artigo.get("titulo") or "")[:200])
            if artigo.get("caminho_audio"): D.tg_send_audio(artigo["caminho_audio"], title=(artigo.get("titulo") or "")[:60])
            msgs.append("✅ Telegram")
        except Exception as e: msgs.append(f"⚠️ Telegram: {type(e).__name__}")
    if wpp:
        try:
            D.enviar_artigo(phone, artigo); msgs.append(f"✅ WhatsApp")
        except Exception as e: msgs.append(f"⚠️ WhatsApp: {type(e).__name__}")
    if any(m.startswith("✅") for m in msgs):
        marcar_enviado(artigo["doc_id"]); agendar(artigo["doc_id"], None)   # saiu da agenda, virou enviado
    return msgs


def legenda_instagram(artigo: dict) -> str:
    rev = (artigo.get("revista") or "").replace("_", " ")
    gancho = artigo.get("gancho_abertura") or artigo.get("gancho_lista") or ""
    return (f"{gancho}\n\n{artigo.get('titulo') or ''}\n\n📌 {rev} · CardioDaily — dados e fatos, sem firula.\n"
            f"#cardiologia #cardiodaily #medicina").strip()


# ───────────────────────────── UI ─────────────────────────────
st.title("🫀 CardioDaily · Painel de Curadoria")
st.caption("Nada vai pro grupo sozinho (só o Radar). Você revisa e agenda/envia o que quiser.")

dados = buscar_artigos()
if not dados: st.stop()
enviados = _ler(ENVIADOS)
por_id = {a["doc_id"]: a for a in dados}

sb = st.sidebar
sb.header("Filtros")
if sb.button("🔄 Recarregar do Supabase"):
    buscar_artigos.clear(); st.rerun()
nmin, nmax = sb.slider("Nota de aplicabilidade", 1, 10, (6, 10))
revistas = sorted({(a.get("revista") or "").replace("_", " ") for a in dados if a.get("revista")})
rev_sel = sb.multiselect("Revista", revistas)
temas = sorted({a.get("doenca_principal") for a in dados if a.get("doenca_principal")})
tema_sel = sb.multiselect("Tema", temas)
presentes = [t for t in TIPOS if any(tipo_norm(a.get("tipo_estudo"), a.get("titulo")) == t for a in dados)]
tipo_sel = sb.multiselect("Tipo de artigo", presentes)
so_mcid = sb.checkbox("Só com MCID preenchido")
status = sb.radio("No grupo de médicos", ["Todos", "Ainda não enviados", "Já enviados"], index=0)

usar_data = sb.checkbox("Filtrar por data")
campo_data = data_de = data_ate = None
if usar_data:
    campo_data = sb.radio("Filtrar pela data de", ["Publicação na revista", "Análise (entrou na base)"], index=0)
    _hoje = datetime.date.today()
    _mes_passado = (_hoje.replace(day=1) - datetime.timedelta(days=1)).replace(day=1)   # 1º dia do mês anterior
    data_de = sb.date_input("De", value=_mes_passado)     # padrão útil: ~2 meses recentes (não jan do ano)
    data_ate = sb.date_input("Até", value=_hoje)


def _parse_data(s):
    """AAAA-MM-DD → date; aceita também AAAA-MM e AAAA; não reconhecível → None."""
    s = (s or "").strip()
    for n, fmt in ((10, "%Y-%m-%d"), (7, "%Y-%m"), (4, "%Y")):
        try: return datetime.datetime.strptime(s[:n], fmt).date()
        except Exception: continue
    return None


def data_efetiva(a) -> tuple:
    """Regra do Dr. Eduardo: usar a data de PUBLICAÇÃO real. Só cai na data de ANÁLISE quando o trabalho
    é AHEAD-OF-PRINT RECENTE cujo mês se perdeu — sinal: data = AAAA-01-01 (só-ano) E do MESMO ANO da
    análise. NUNCA inventa data pra artigo antigo: RALES 1999-01-01 continua 1999 (ano ≠ ano da análise).
    Devolve (date, fonte) com fonte em {'publicação', 'análise'}."""
    d = _parse_data(a.get("data_publicacao"))
    da = _parse_data(a.get("created_at"))
    if d is None:                                    # sem data nenhuma → usa análise
        return (da, "análise") if da else (None, "publicação")
    so_ano = d.month == 1 and d.day == 1             # só-ano defaulta pra 01/01
    if so_ano and da and d.year == da.year:          # placeholder do ANO CORRENTE = ahead-of-print recente
        return da, "análise"
    return d, "publicação"                           # ano real (inclui 1999) → mantém a publicação


def _passa(a: dict) -> bool:
    n = a.get("nota_aplicabilidade") or 0
    if not (nmin <= n <= nmax): return False
    if rev_sel and (a.get("revista") or "").replace("_", " ") not in rev_sel: return False
    if tema_sel and a.get("doenca_principal") not in tema_sel: return False
    if tipo_sel and tipo_norm(a.get("tipo_estudo"), a.get("titulo")) not in tipo_sel: return False
    if so_mcid and not (a.get("mcid_avaliacao") or "").strip(): return False
    ja = a["doc_id"] in enviados
    if status == "Ainda não enviados" and ja: return False
    if status == "Já enviados" and not ja: return False
    if usar_data:
        if (campo_data or "").startswith("Análise"):
            d = _parse_data(a.get("created_at"))
        else:
            d, _ = data_efetiva(a)          # publicação real, com fallback p/ análise quando é só-ano
        if d is None or d < data_de or d > data_ate: return False
    return True


filtrados = [a for a in dados if _passa(a)]
filtrados.sort(key=lambda a: (a.get("nota_aplicabilidade") or 0, a.get("created_at") or ""), reverse=True)

c1, c2, c3 = st.columns(3)
c1.metric("No filtro", len(filtrados))
c2.metric("Já no grupo", len(enviados))
c3.metric("Total na base", len(dados))

st.divider()
esq, dirt = st.columns([0.52, 0.48])

with esq:
    st.subheader(f"Temas ({len(filtrados)}) — filtrados por nota")
    for a in filtrados[:200]:
        selo = "✅" if a["doc_id"] in enviados else "🔎"
        rev = (a.get("revista") or "").replace("_", " ")
        if st.button(f"{selo} [{a.get('nota_aplicabilidade')}] {rev} · {(a.get('titulo') or '')[:66]}",
                     key="sel_" + a["doc_id"], use_container_width=True):
            st.session_state["ativo"] = a["doc_id"]
    if len(filtrados) > 200: st.caption(f"Mostrando 200 de {len(filtrados)} — refine os filtros.")

with dirt:
    art = por_id.get(st.session_state.get("ativo"))
    if not art:
        st.info("← Escolha um tema pra revisar (PDF, visual abstract, áudio) e agendar pro grupo.")
    else:
        st.subheader((art.get("titulo") or "")[:120])
        rev = (art.get("revista") or "").replace("_", " ")
        _def, _fonte = data_efetiva(art)
        st.write(f"**{rev}** · {_fonte} {_def or '—'} · tema: {art.get('doenca_principal') or '—'}")
        st.write(f"Nota **{art.get('nota_aplicabilidade')}** · rigor {art.get('nota_trabalho_estatistico')} · "
                 + ("✅ já no grupo" if art['doc_id'] in enviados else "🔎 ainda não enviado"))
        if art.get("mcid_avaliacao"): st.caption("**MCID:** " + art["mcid_avaliacao"][:400])

        st.markdown("**Conferir antes de aprovar:**")
        r1, r2 = st.columns(2)
        if art.get("caminho_pdf"): r1.link_button("📄 Abrir PDF", art["caminho_pdf"], use_container_width=True)
        if art.get("caminho_audio"): r2.link_button("🔊 Ouvir áudio", art["caminho_audio"], use_container_width=True)
        if art.get("caminho_visual_abstract"):
            st.image(art["caminho_visual_abstract"], use_container_width=True)
        with st.expander("Prévia da análise (texto)"):
            st.markdown((art.get("resumo_markdown") or "—")[:4000])

        st.divider()
        st.markdown("### Agendar pro grupo de médicos")
        dias = proximos_7_dias()
        rot2iso = {r: i for i, r in dias}
        col = st.columns([0.6, 0.4])
        escolha = col[0].selectbox("Dia (próximos 7)", [r for _, r in dias], key="dia_" + art["doc_id"])
        if col[1].button("🗓️ Adicionar ao dia", use_container_width=True):
            agendar(art["doc_id"], rot2iso[escolha]); st.success(f"Agendado: {escolha}"); st.rerun()

        st.markdown("**Ou enviar agora:**")
        e1, e2, e3 = st.columns(3)
        go_wpp = e1.checkbox("WhatsApp", value=True, key="w_" + art["doc_id"])
        go_tg = e2.checkbox("Telegram", value=False, key="t_" + art["doc_id"])
        if e3.button("📤 Enviar agora", use_container_width=True):
            res = enviar_grupo(art, go_wpp, go_tg, GRUPO_WPP)
            st.toast(" · ".join(res) or "nada selecionado"); st.rerun()

        with st.expander("📸 Instagram — legenda pronta (você posta)"):
            st.code(legenda_instagram(art), language=None)

# ───────────────────────────── Agenda dos próximos 7 dias ─────────────────────────────
st.divider()
st.subheader("🗓️ Agenda dos próximos 7 dias")
ag = _ler(AGENDA)
cols = st.columns(7)
for (iso, rot), c in zip(proximos_7_dias(), cols):
    ids = ag.get(iso, [])
    c.markdown(f"**{rot}**\n\n{len(ids)} artigo(s)")
    for i in ids:
        a = por_id.get(i)
        if not a: continue
        c.caption(f"[{a.get('nota_aplicabilidade')}] {(a.get('titulo') or '')[:40]}")
        if c.button("↩︎ tirar", key=f"rm_{iso}_{i}"):
            agendar(i, None); st.rerun()
    if ids and c.button("📤 Enviar todos deste dia", key=f"send_{iso}", use_container_width=True):
        for i in list(ids):
            a = por_id.get(i)
            if a: enviar_grupo(a, True, False, GRUPO_WPP)
        st.toast(f"Enviado o dia {rot}"); st.rerun()
