"""
painel_curadoria.py — O PAINEL DE CURADORIA (decisão do Dr. Eduardo, 27/Jul/2026).

VIRADA DE MODELO: o sistema NÃO publica/envia artigo sozinho. Só o Radar continua automático.
Tudo o mais — site, redes, grupo — é ESCOLHIDO AQUI, um a um, pelo Dr. Eduardo.

O painel lê a tabela `artigos` do Supabase e deixa FILTRAR por nota, revista, data de publicação,
mcid e tema; e ESCOLHER o que sai a cada dia:
  • Publicar no site      → seta publicar_no_site = true (o site só mostra o que está true)
  • Tirar do site         → publicar_no_site = false
  • Enviar no grupo       → WhatsApp (Z-API) e/ou Telegram, na hora, só o que você mandar
  • Instagram             → gera a legenda pronta + aponta o visual abstract (você posta)
  • Agenda da semana      → planeja o que sai em cada dia (arquivo local, não dispara nada sozinho)

Rodar:  streamlit run src/painel_curadoria.py
"""
from __future__ import annotations
import os, json, datetime
import requests
import streamlit as st
from dotenv import load_dotenv

_HERE = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(_HERE, "..", ".env"))

URL = os.getenv("SUPABASE_URL", "").rstrip("/")
KEY = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY", "")
HDR = {"apikey": KEY, "Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}
AGENDA = os.path.join(_HERE, "..", "outputs", "agenda_curadoria.json")
DIAS = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]

st.set_page_config(page_title="CardioDaily · Curadoria", page_icon="🫀", layout="wide")


# ───────────────────────────── Supabase ─────────────────────────────
@st.cache_data(ttl=120)
def buscar_artigos() -> list[dict]:
    """Traz todos os artigos não descartados (a filtragem fina é local, pra ser instantânea)."""
    campos = ("doc_id,titulo,revista,nota_aplicabilidade,nota_trabalho_estatistico,doenca_principal,"
              "data_publicacao,created_at,mcid_avaliacao,gancho_lista,gancho_abertura,resumo_markdown,"
              "publicar_no_site,caminho_pdf,caminho_audio,caminho_visual_abstract,tipo_estudo,doi")
    out, passo = [], 1000
    for salto in range(0, 20000, passo):
        r = requests.get(f"{URL}/rest/v1/artigos", headers=HDR, params={
            "select": campos, "descartado": "eq.false",
            "order": "created_at.desc", "limit": str(passo), "offset": str(salto)}, timeout=40)
        if r.status_code != 200:
            st.error(f"Supabase {r.status_code}: {r.text[:200]}"); break
        lote = r.json()
        out += lote
        if len(lote) < passo:
            break
    return out


def patch_artigo(doc_id: str, campos: dict) -> tuple[bool, str]:
    r = requests.patch(f"{URL}/rest/v1/artigos", headers={**HDR, "Prefer": "return=minimal"},
                       params={"doc_id": f"eq.{doc_id}"}, json=campos, timeout=30)
    return (r.status_code in (200, 204)), (r.text[:200] if r.status_code not in (200, 204) else "ok")


# ───────────────────────────── Agenda local ─────────────────────────────
def carregar_agenda() -> dict:
    if os.path.exists(AGENDA):
        try: return json.load(open(AGENDA, encoding="utf-8"))
        except Exception: return {}
    return {}


def salvar_agenda(ag: dict):
    os.makedirs(os.path.dirname(AGENDA), exist_ok=True)
    json.dump(ag, open(AGENDA, "w", encoding="utf-8"), ensure_ascii=False, indent=2)


# ───────────────────────────── Envio (só quando VOCÊ manda) ─────────────────────────────
def enviar_telegram(artigo: dict) -> str:
    import distribuidor as D
    try:
        D.tg_send_text(D.montar_mensagem(artigo, html=True), html=True)
        va = artigo.get("caminho_visual_abstract")
        if va: D.tg_send_image(va, caption=(artigo.get("titulo") or "")[:200])
        au = artigo.get("caminho_audio")
        if au: D.tg_send_audio(au, title=(artigo.get("titulo") or "")[:60])
        return "✅ enviado no Telegram"
    except Exception as e:
        return f"⚠️ Telegram falhou: {type(e).__name__}: {e}"


def enviar_whatsapp(artigo: dict, phone: str) -> str:
    import distribuidor as D
    try:
        D.enviar_artigo(phone, artigo)
        return f"✅ enviado no WhatsApp ({phone})"
    except Exception as e:
        return f"⚠️ WhatsApp falhou: {type(e).__name__}: {e}"


def legenda_instagram(artigo: dict) -> str:
    rev = (artigo.get("revista") or "").replace("_", " ")
    tit = artigo.get("titulo") or ""
    gancho = artigo.get("gancho_abertura") or artigo.get("gancho_lista") or ""
    return (f"{gancho}\n\n{tit}\n\n📌 {rev} · CardioDaily — dados e fatos, sem firula.\n"
            f"#cardiologia #cardiodaily #medicina").strip()


# ───────────────────────────── UI ─────────────────────────────
st.title("🫀 CardioDaily · Painel de Curadoria")
st.caption("O sistema não publica nem envia nada sozinho (só o Radar). Aqui **você** filtra e escolhe o que sai.")

dados = buscar_artigos()
if not dados:
    st.stop()

# ---- filtros (sidebar) ----
sb = st.sidebar
sb.header("Filtros")
if sb.button("🔄 Recarregar do Supabase"):
    buscar_artigos.clear(); st.rerun()

nmin, nmax = sb.slider("Nota de aplicabilidade", 1, 10, (6, 10))
revistas = sorted({(a.get("revista") or "").replace("_", " ") for a in dados if a.get("revista")})
rev_sel = sb.multiselect("Revista", revistas, default=[])
temas = sorted({a.get("doenca_principal") for a in dados if a.get("doenca_principal")})
tema_sel = sb.multiselect("Tema", temas, default=[])
so_mcid = sb.checkbox("Só com MCID preenchido", value=False)
status = sb.radio("Status no site", ["Todos", "Só NÃO publicados", "Só publicados"], index=1)

anos = [a.get("data_publicacao", "") for a in dados if a.get("data_publicacao")]
ano_min = sb.text_input("Data publicação DE (AAAA-MM-DD, opcional)", "")
ano_max = sb.text_input("Data publicação ATÉ (AAAA-MM-DD, opcional)", "")


def _passa(a: dict) -> bool:
    n = a.get("nota_aplicabilidade") or 0
    if not (nmin <= n <= nmax): return False
    if rev_sel and (a.get("revista") or "").replace("_", " ") not in rev_sel: return False
    if tema_sel and a.get("doenca_principal") not in tema_sel: return False
    if so_mcid and not (a.get("mcid_avaliacao") or "").strip(): return False
    if status == "Só NÃO publicados" and a.get("publicar_no_site"): return False
    if status == "Só publicados" and not a.get("publicar_no_site"): return False
    dp = a.get("data_publicacao") or ""
    if ano_min and dp and dp < ano_min: return False
    if ano_max and dp and dp > ano_max: return False
    return True


filtrados = [a for a in dados if _passa(a)]
filtrados.sort(key=lambda a: (a.get("nota_aplicabilidade") or 0, a.get("created_at") or ""), reverse=True)

c1, c2, c3 = st.columns(3)
c1.metric("Artigos no filtro", len(filtrados))
c2.metric("Publicados no site", sum(1 for a in dados if a.get("publicar_no_site")))
c3.metric("Total na base", len(dados))

st.divider()
esq, dir = st.columns([0.55, 0.45])

# ---- lista (esquerda) ----
with esq:
    st.subheader(f"Artigos ({len(filtrados)})")
    for a in filtrados[:200]:
        pub = "🟢" if a.get("publicar_no_site") else "⚪"
        rev = (a.get("revista") or "").replace("_", " ")
        rot = f"{pub} [{a.get('nota_aplicabilidade')}] {rev} · {(a.get('titulo') or '')[:70]}"
        if st.button(rot, key="sel_" + a["doc_id"], use_container_width=True):
            st.session_state["ativo"] = a["doc_id"]
    if len(filtrados) > 200:
        st.caption(f"Mostrando 200 de {len(filtrados)} — refine os filtros.")

# ---- detalhe + ações (direita) ----
with dir:
    ativo = st.session_state.get("ativo")
    art = next((a for a in filtrados if a["doc_id"] == ativo), None) or \
          next((a for a in dados if a["doc_id"] == ativo), None)
    if not art:
        st.info("← Escolha um artigo na lista para ver detalhes e decidir o que fazer.")
    else:
        st.subheader((art.get("titulo") or "")[:120])
        rev = (art.get("revista") or "").replace("_", " ")
        st.write(f"**{rev}** · {art.get('data_publicacao') or '—'} · tema: {art.get('doenca_principal') or '—'}")
        st.write(f"Nota aplicabilidade **{art.get('nota_aplicabilidade')}** · "
                 f"rigor {art.get('nota_trabalho_estatistico')} · "
                 f"{'🟢 no site' if art.get('publicar_no_site') else '⚪ fora do site'}")
        if art.get("mcid_avaliacao"):
            st.caption("**MCID:** " + art["mcid_avaliacao"][:400])
        if art.get("caminho_visual_abstract"):
            st.image(art["caminho_visual_abstract"], use_column_width=True)
        cols = st.columns(2)
        if art.get("caminho_pdf"): cols[0].link_button("📄 PDF", art["caminho_pdf"])
        if art.get("caminho_audio"): cols[1].link_button("🔊 Áudio", art["caminho_audio"])
        with st.expander("Prévia da análise"):
            st.markdown((art.get("resumo_markdown") or "—")[:4000])

        st.divider()
        st.markdown("### Publicar / enviar — só o que você mandar")

        p1, p2 = st.columns(2)
        if not art.get("publicar_no_site"):
            if p1.button("🟢 Publicar no site", use_container_width=True):
                ok, msg = patch_artigo(art["doc_id"], {"publicar_no_site": True})
                (st.success if ok else st.error)("Publicado no site" if ok else msg)
                buscar_artigos.clear(); st.rerun()
        else:
            if p1.button("⚪ Tirar do site", use_container_width=True):
                ok, msg = patch_artigo(art["doc_id"], {"publicar_no_site": False})
                (st.success if ok else st.error)("Tirado do site" if ok else msg)
                buscar_artigos.clear(); st.rerun()

        if p2.button("📲 Enviar no Telegram", use_container_width=True):
            st.toast(enviar_telegram(art))

        w1, w2 = st.columns([0.6, 0.4])
        phone = w1.text_input("WhatsApp (número ou ID do grupo)", key="wpp_" + art["doc_id"])
        if w2.button("💬 Enviar no WhatsApp", use_container_width=True, disabled=not phone):
            st.toast(enviar_whatsapp(art, phone.strip()))

        with st.expander("📸 Instagram — legenda pronta (você posta)"):
            st.code(legenda_instagram(art), language=None)
            if art.get("caminho_visual_abstract"):
                st.caption("Use o visual abstract acima como imagem do post.")

        st.divider()
        ag = carregar_agenda()
        atual = next((d for d, ids in ag.items() if art["doc_id"] in ids), "—")
        dia = st.selectbox("Agendar para o dia", ["—"] + DIAS,
                           index=(["—"] + DIAS).index(atual) if atual in DIAS else 0)
        if st.button("🗓️ Salvar na agenda da semana"):
            for d in list(ag): ag[d] = [x for x in ag[d] if x != art["doc_id"]]
            if dia in DIAS:
                ag.setdefault(dia, []).append(art["doc_id"])
            salvar_agenda(ag); st.success(f"Agendado: {dia}")

# ---- agenda da semana (rodapé) ----
st.divider()
with st.expander("🗓️ Agenda da semana (planejamento — não dispara nada sozinho)"):
    ag = carregar_agenda()
    por_id = {a["doc_id"]: a for a in dados}
    for d in DIAS:
        ids = ag.get(d, [])
        st.markdown(f"**{d}** ({len(ids)})")
        for i in ids:
            a = por_id.get(i)
            if a: st.write(f"· [{a.get('nota_aplicabilidade')}] {(a.get('titulo') or '')[:80]}")
