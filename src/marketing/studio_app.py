"""
CardioDaily Marketing Studio — Interface Streamlit
Sessão semanal: busca artigos, gera placas, legenda, script e agenda.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import requests
import streamlit as st
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
load_dotenv(ROOT / ".env")

from marketing.placa_generator import PlacaGenerator, PostFeedData, StoryData
from marketing.extrator_ia import extrair_conteudo_marketing, montar_defaults

# ── Config ────────────────────────────────────────────────────────────────────
URL  = os.getenv("SUPABASE_URL", "").rstrip("/")
KEY  = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY", "")
HDR  = {"apikey": KEY, "Authorization": f"Bearer {KEY}"}
AGENDA_FILE = ROOT / "outputs" / "marketing" / "agenda_semanal.json"
LOGO_PATH   = Path("/Users/edcastro77/Desktop/RECURSOS/LOGOs/logo_cardiodaily.png")

st.set_page_config(
    page_title="CardioDaily Marketing Studio",
    page_icon="🫀",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
  [data-testid="stAppViewContainer"] { background:#F7F8F7; }
  [data-testid="stSidebar"]          { background:#111111; }
  [data-testid="stSidebar"] *        { color:#FFFFFF !important; }
  .card {
    background:white; border-radius:12px; border-left:4px solid #3BAF9E;
    padding:16px 20px; margin-bottom:10px; box-shadow:0 2px 8px rgba(0,0,0,.06);
  }
  .nota-badge {
    display:inline-block; background:#3BAF9E; color:white; font-weight:700;
    border-radius:6px; padding:2px 10px; font-size:.88rem; margin-right:8px;
  }
  .sec { font-size:1.05rem; font-weight:700; color:#3BAF9E;
         border-bottom:2px solid #3BAF9E; padding-bottom:5px; margin:22px 0 14px; }
  .alerta { background:#FFF8E1; border-left:4px solid #FFC107;
            padding:10px 16px; border-radius:8px; color:#7B5700; margin-bottom:14px; }
</style>
""", unsafe_allow_html=True)

# ── Helpers ───────────────────────────────────────────────────────────────────

@st.cache_data(ttl=300)
def buscar_artigos() -> list[dict]:
    r = requests.get(f"{URL}/rest/v1/artigos", headers=HDR, params={
        "select": "doc_id,titulo,revista,nota_aplicabilidade,doenca_principal,data_publicacao,created_at,gancho_lista",
        "nota_aplicabilidade": "gte.8",
        "created_at": f"gte.{(datetime.now()-timedelta(days=30)).strftime('%Y-%m-%d')}",
        "order": "nota_aplicabilidade.desc,created_at.desc",
        "limit": "30",
    })
    d = r.json()
    return d if isinstance(d, list) else []


def ler_analysis(doc_id: str) -> tuple[str, dict]:
    base = ROOT / "outputs" / "corpus" / doc_id
    md   = (base / "analysis.md").read_text(encoding="utf-8") if (base/"analysis.md").exists() else ""
    meta = json.loads((base/"analysis.json").read_text(encoding="utf-8")) if (base/"analysis.json").exists() else {}
    return md, meta


def tem_kit(doc_id: str) -> bool:
    d = ROOT / "outputs" / "marketing" / doc_id
    return d.exists() and bool(list(d.glob("*.png")))


def carregar_agenda() -> dict:
    return json.loads(AGENDA_FILE.read_text(encoding="utf-8")) if AGENDA_FILE.exists() else {}


def salvar_agenda(ag: dict):
    AGENDA_FILE.parent.mkdir(parents=True, exist_ok=True)
    AGENDA_FILE.write_text(json.dumps(ag, indent=2, ensure_ascii=False))


def extrair_do_analysis(md: str) -> dict:
    """Extrai dados reais do analysis.md para preencher o conteúdo de marketing."""
    import re

    def _secao(titulo_regex: str) -> str:
        """Extrai o texto de uma seção pelo título."""
        m = re.search(
            rf"###?\s*{titulo_regex}[^\n]*\n+(.*?)(?=\n###|\Z)",
            md, re.DOTALL | re.IGNORECASE
        )
        return m.group(1).strip() if m else ""

    def _bullets_praticos() -> list[str]:
        """Extrai bullets_praticos do bloco JSON ou da seção de aplicação."""
        # Tenta extrair do JSON embutido
        m = re.search(r'"bullets_praticos"\s*:\s*\[(.*?)\]', md, re.DOTALL)
        if m:
            items = re.findall(r'"([^"]+)"', m.group(1))
            if items:
                return items[:4]
        # Fallback: bullets da seção aplicação prática
        secao = _secao(r"(?:APLICA[ÇC][ÃA]O PR[ÁA]TICA|APLICA[ÇC][ÃA]O|PR[ÁA]TICA)")
        bullets = re.findall(r'[*\-•]\s*\*?\*?([^\n]{20,120})', secao)
        return [b.strip("* ").strip() for b in bullets[:4]]

    def _dado_ancora() -> str:
        """Extrai o número/estatística mais impactante."""
        # Busca padrões tipo "X% redução", "OR X,XX", "NNT X", "ARR X%"
        padroes = [
            r'(?:reduz|redução|reduziu)[^.]*?(\d+[\.,]\d*\s*%)',
            r'NNT\s*(?:de\s*)?(\d+)',
            r'OR\s*([\d,\.]+)\s*\(IC',
            r'ARR[^.]*?(\d+[\.,]\d*\s*%)',
            r'(\d+[\.,]\d*\s*%)[^.]*(?:redução|menor|menos|reduz)',
            r'(?:aumenta|dobra|eleva)[^.]*?(\d+[\.,]\d*\s*%)',
        ]
        for p in padroes:
            m = re.search(p, md, re.IGNORECASE)
            if m:
                # Pega a frase completa ao redor
                start = max(0, m.start() - 60)
                end   = min(len(md), m.end() + 60)
                trecho = md[start:end].strip()
                # Limpa e encurta
                trecho = re.sub(r'\s+', ' ', trecho)
                if len(trecho) < 80:
                    return trecho.upper()
        return ""

    def _take_home() -> dict[str, str]:
        """Extrai as 6 dimensões do take-home."""
        resultado = {}
        dims = {
            "por_que": r"POR\s*QU[EÊ]",
            "como": r"COMO",
            "quando": r"QUANDO",
            "em_quem": r"EM\s*QUEM",
            "o_que": r"O\s*QUE\s*FAZER",
            "de_que": r"DE\s*QUE\s*MANEIRA",
        }
        for chave, regex in dims.items():
            m = re.search(rf"\*\*{regex}[:\*]*\*\*\s*(.+?)(?=\n\*\*|\Z)", md, re.DOTALL | re.IGNORECASE)
            if m:
                texto = m.group(1).strip().replace("\n", " ")
                resultado[chave] = re.sub(r'\s+', ' ', texto)
        return resultado

    def _muda_conduta() -> str:
        m = re.search(r'MUDA CONDUTA HOJE\?\s*([^\n]+)', md)
        return m.group(1).strip() if m else ""

    def _conclusao() -> str:
        m = re.search(r'"conclusao_geral"\s*:\s*"([^"]+)"', md)
        if m:
            return m.group(1)
        m = re.search(r'"impacto_conduta"\s*:\s*"([^"]+)"', md)
        return m.group(1) if m else ""

    def _titulo_real() -> str:
        m = re.search(r'TÍ?TULO\s*:\s*(.+)', md)
        return m.group(1).strip() if m else ""

    def _tipo_estudo() -> str:
        m = re.search(r'TIPO\s*:\s*(.+)', md)
        return m.group(1).strip() if m else ""

    return {
        "titulo_real": _titulo_real(),
        "tipo_estudo": _tipo_estudo(),
        "ancora": _dado_ancora(),
        "bullets": _bullets_praticos(),
        "take_home": _take_home(),
        "muda_conduta": _muda_conduta(),
        "conclusao": _conclusao(),
        "aplicacao": _secao(r"(?:APLICA[ÇC][ÃA]O PR[ÁA]TICA|4\.\s*APLICA[ÇC][ÃA]O)"),
        "problema": _secao(r"(?:PROBLEMA CL[ÍI]NICO|1\.\s*O PROBLEMA)"),
    }


def defaults_para(artigo: dict, md: str) -> dict:
    """Gera conteúdo de marketing pré-preenchido com dados reais do analysis.md."""
    titulo  = (artigo.get("titulo") or "")
    revista = (artigo.get("revista") or "").replace("_", " ")
    data    = (artigo.get("data_publicacao") or "")[:7]
    gancho  = (artigo.get("gancho_lista") or "")
    doenca  = (artigo.get("doenca_principal") or "doença cardiovascular")

    # Extrair dados reais do analysis.md
    dados = extrair_do_analysis(md) if md else {}

    titulo_real  = dados.get("titulo_real") or titulo
    tipo_estudo  = dados.get("tipo_estudo", "")
    ancora_real  = dados.get("ancora") or (gancho.split("·")[-1].strip() if "·" in gancho else "")
    bullets      = dados.get("bullets") or []
    take_home    = dados.get("take_home") or {}
    muda_conduta = dados.get("muda_conduta") or ""
    conclusao    = dados.get("conclusao") or ""
    aplicacao    = dados.get("aplicacao") or ""
    problema     = dados.get("problema") or ""

    # Montar frase icônica a partir do gancho e conduta
    gancho_partes = gancho.split("·")
    impacto = gancho_partes[-1].strip() if len(gancho_partes) > 1 else gancho
    tipo_label = gancho_partes[0].strip() if gancho_partes else tipo_estudo

    # Story 1 — frase icônica: baseada no impacto prático
    s1_titulo = impacto.upper()[:60] if impacto else "NOVO ESTUDO\nMUDA A PRÁTICA"
    # Quebrar em até 3 linhas de ~20 chars
    palavras = s1_titulo.split()
    linhas, linha_atual = [], []
    for p in palavras:
        linha_atual.append(p)
        if len(" ".join(linha_atual)) > 18:
            linhas.append(" ".join(linha_atual[:-1]))
            linha_atual = [p]
    if linha_atual:
        linhas.append(" ".join(linha_atual))
    s1_titulo = "\n".join(linhas[:4])

    s1_corpo = problema.split(".")[0] + "." if problema else \
               f"Publicado no {revista}, este estudo traz dados que impactam diretamente a conduta em {doenca}."

    # Story 2 — âncora
    s2_ancora = ancora_real.upper() if ancora_real else "VEJA OS DADOS\nNO CARDIODAILY"

    s2_corpo = conclusao if conclusao else \
               f"Os dados foram extraídos diretamente da análise publicada no {revista}."

    # Story 3 — bullets práticos
    b1 = bullets[0] if len(bullets) > 0 else take_home.get("o_que", "Aplicar conforme perfil do paciente")
    b2 = bullets[1] if len(bullets) > 1 else take_home.get("em_quem", "Avaliar critérios de inclusão do estudo")
    b3 = bullets[2] if len(bullets) > 2 else take_home.get("de_que", "Respeitar dose e contraindicações")

    s3_corpo = muda_conduta or take_home.get("por_que", "Os dados são sólidos. A decisão é sua, à beira do leito.")

    # Post feed
    p_b1 = bullets[0] if len(bullets) > 0 else gancho
    p_b2 = bullets[1] if len(bullets) > 1 else "Avaliar indicação conforme perfil do paciente"
    p_b3 = bullets[2] if len(bullets) > 2 else "Respeitar contraindicações e ajustes de dose"
    p_b4 = bullets[3] if len(bullets) > 3 else (muda_conduta[:80] if muda_conduta else "")

    # Legenda Instagram — baseada nos dados reais
    take_home_texto = ""
    if take_home:
        partes = []
        if take_home.get("o_que"):   partes.append(f"→ {take_home['o_que']}")
        if take_home.get("em_quem"): partes.append(f"→ {take_home['em_quem']}")
        if take_home.get("quando"):  partes.append(f"→ {take_home['quando']}")
        take_home_texto = "\n".join(partes)
    elif bullets:
        take_home_texto = "\n".join(f"→ {b}" for b in bullets[:3])

    limitacoes_lembrete = "(Declaro as limitações metodológicas conforme o estudo)"

    legenda = f"""{impacto.upper() if impacto else titulo_real.upper()}

{gancho}

{"Publicado no " + revista + " (" + data + "), " if revista else ""}{tipo_estudo + " que " if tipo_estudo else "Estudo que "}merece a atenção de quem trata {doenca}.

O que os dados mostram:
{take_home_texto if take_home_texto else "→ [revise os achados principais no analysis.md]"}

{"Muda a conduta? " + muda_conduta if muda_conduta else ""}

O que muda na prática:
{aplicacao.split(chr(10))[0] if aplicacao else conclusao if conclusao else "[revise a seção de aplicação prática no analysis.md]"}

{limitacoes_lembrete}

📌 Fonte: {titulo_real if titulo_real else titulo}. {revista}, {data}.

#CardioDaily #Cardiologia #MedicinaBaseadaEmEvidencias #OsFatosSemFirulas"""

    # Script de vídeo
    gancho_video  = problema.split(".")[0] + "." if problema else "[Abra com o dilema clínico que este estudo responde]"
    pratica_video = aplicacao.split("\n")[0] if aplicacao else (muda_conduta or "[conduta objetiva derivada do estudo]")

    script = f"""[GANCHO — 15s]
{gancho_video}

[CONTEXTO — 30s]
[Por que este tema é controverso ou mal resolvido na prática atual?
Use o problema clínico descrito na análise como ponto de partida.]

[O QUE O ESTUDO MOSTROU — 45s]
{tipo_estudo + " publicado no " + revista if tipo_estudo else "Publicado no " + revista}, este trabalho mostrou:
{chr(10).join("• " + b for b in bullets[:3]) if bullets else "• " + (ancora_real or "[dados principais do estudo]")}

[IMPLICAÇÃO PRÁTICA — 30s]
{pratica_video}

[CALL TO ACTION — 15s]
O artigo completo está analisado no CardioDaily — com os dados, as limitações e o fluxograma de decisão. Os fatos, sem fírulas. Link na bio."""

    return {
        "s1_titulo": s1_titulo,
        "s1_corpo":  s1_corpo,
        "s2_titulo": "O DADO\nQUE IMPORTA",
        "s2_ancora": s2_ancora,
        "s2_corpo":  s2_corpo,
        "s3_titulo": "O QUE MUDA\nNA PRÁTICA",
        "s3_b1": b1,
        "s3_b2": b2,
        "s3_b3": b3,
        "s3_corpo": s3_corpo,
        "p_titulo":  "",
        "p_ancora":  s2_ancora,
        "p_b1": p_b1,
        "p_b2": p_b2,
        "p_b3": p_b3,
        "p_b4": p_b4,
        "p_corpo":  f"{tipo_estudo} · {revista} · {data}" if tipo_estudo else f"{revista} · {data}",
        "p_fonte":  f"{titulo_real}. {revista}, {data}." if titulo_real else f"{revista}, {data}.",
        "legenda":  legenda,
        "script":   script,
    }


def _placeholder_para(artigo: dict, md: str) -> dict:
    """Fallback quando analysis.md não existe."""
    titulo  = (artigo.get("titulo") or "")
    revista = (artigo.get("revista") or "").replace("_", " ")
    data    = (artigo.get("data_publicacao") or "")[:7]
    gancho  = (artigo.get("gancho_lista") or "")
    doenca  = (artigo.get("doenca_principal") or "doença cardiovascular")
    ancora  = gancho.split("·")[-1].strip() if "·" in gancho else "VEJA OS DADOS NO CARDIODAILY"
    return {
        "s1_titulo": ancora.upper()[:60],
        "s1_corpo":  f"Publicado no {revista}, este estudo traz dados sobre {doenca}. {gancho}",
        "s2_titulo": "O DADO\nQUE IMPORTA",
        "s2_ancora": ancora.upper(),
        "s2_corpo":  f"Extraído da análise publicada no CardioDaily.",
        "s3_titulo": "O QUE MUDA\nNA PRÁTICA",
        "s3_b1": gancho[:100],
        "s3_b2": "Avaliar indicação conforme perfil do paciente",
        "s3_b3": "Respeitar contraindicações e ajustes de dose",
        "s3_corpo": "A decisão é sua, à beira do leito.",
        "p_titulo": "", "p_ancora": ancora.upper(),
        "p_b1": gancho[:100], "p_b2": "Avaliar indicação", "p_b3": "Respeitar contraindicações", "p_b4": "",
        "p_corpo": f"{revista} · {data}", "p_fonte": f"{revista}, {data}.",
        "legenda": f"{titulo.upper()}\n\n{gancho}\n\nFonte: {revista}, {data}.\n\n#CardioDaily #Cardiologia",
        "script": f"[Abra com um dilema clínico sobre {doenca}]\n\nPublicado no {revista}...\n\nLink na bio.",
    }


# ── Session state — garante reatividade ao trocar de artigo ──────────────────

CAMPO_KEYS = [
    "s1_titulo", "s1_corpo",
    "s2_titulo", "s2_ancora", "s2_corpo",
    "s3_titulo", "s3_b1", "s3_b2", "s3_b3", "s3_corpo",
    "p_titulo", "p_ancora", "p_b1", "p_b2", "p_b3", "p_b4", "p_corpo", "p_fonte",
    "legenda", "script",
]
# Keys internas do Streamlit (prefixo _) — precisam ser deletadas para o widget recarregar
WIDGET_KEYS = [f"_{k.replace('_', '', 1)}" if k.startswith("s") else f"_{k[1:]}"
               for k in CAMPO_KEYS]
WIDGET_KEYS = ["_s1t","_s1c","_s2t","_s2a","_s2c","_s3t","_s3b1","_s3b2","_s3b3","_s3c",
               "_pt","_pa","_pb1","_pb2","_pb3","_pb4","_pc","_pf","_leg","_scr"]


def inicializar_estado(artigo: dict, md: str):
    """Carrega defaults no session_state quando o artigo muda."""
    doc_id = artigo.get("doc_id", "")
    if st.session_state.get("_artigo_ativo") == doc_id:
        return  # mesmo artigo, não recarrega

    # Deletar keys dos widgets para forçar Streamlit a usar novos valores
    for k in WIDGET_KEYS:
        st.session_state.pop(k, None)

    d = defaults_para(artigo, md) if md else _placeholder_para(artigo, md)
    for k, v in d.items():
        st.session_state[k] = v
    st.session_state["_artigo_ativo"] = doc_id


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    if LOGO_PATH.exists():
        st.image(str(LOGO_PATH), width=130)
    st.markdown("## Marketing Studio")
    st.markdown("*Os Fatos sem Fírulas*")
    st.markdown("---")
    pagina = st.radio("", [
        "🏠  Sessão Semanal",
        "📅  Agenda da Semana",
        "📁  Kits Gerados",
    ], label_visibility="collapsed")
    st.markdown("---")
    st.caption("Dr. Eduardo Castro\nCRM-ES 8062\nRQE Cardio 6788 · MI 6787")


# ══════════════════════════════════════════════════════════════════════════════
# PÁGINA 1 — SESSÃO SEMANAL
# ══════════════════════════════════════════════════════════════════════════════
if pagina == "🏠  Sessão Semanal":

    st.title("🫀 CardioDaily Marketing Studio")
    st.caption(f"Sessão de {datetime.now().strftime('%A, %d/%m/%Y')}")

    with st.spinner("Buscando artigos nota ≥ 8 dos últimos 30 dias..."):
        artigos = buscar_artigos()

    if not artigos:
        st.error("Nenhum artigo encontrado. Verifique a conexão com o Supabase.")
        st.stop()

    sem_kit = [a for a in artigos if not tem_kit(a.get("doc_id",""))]
    if sem_kit:
        st.markdown(f'<div class="alerta">⚡ <strong>{len(sem_kit)} artigos</strong> aguardando kit de marketing esta semana</div>',
                    unsafe_allow_html=True)

    # ── Seletor de artigo ─────────────────────────────────────────────────────
    st.markdown('<div class="sec">Selecione o artigo</div>', unsafe_allow_html=True)

    opcoes_label = []
    opcoes_map   = {}
    for a in artigos:
        nota  = a.get("nota_aplicabilidade","?")
        kit   = "✅" if tem_kit(a.get("doc_id","")) else "🔲"
        titulo = (a.get("titulo") or "Sem título")[:75]
        revista = (a.get("revista") or "")[:25]
        data = (a.get("data_publicacao") or "")[:10]
        lbl = f"{kit} [{nota}]  {titulo}  ·  {revista}  ·  {data}"
        opcoes_label.append(lbl)
        opcoes_map[lbl] = a

    def _carregar_artigo(artigo_novo: dict, md_novo: str):
        """Carrega defaults nas widget keys — usa Claude se analysis.md disponível."""
        doc_id_novo = artigo_novo["doc_id"]
        # Deletar widget keys para forçar reset
        for k in WIDGET_KEYS:
            st.session_state.pop(k, None)

        if md_novo:
            # Tenta extração via Claude
            dados_ia = extrair_conteudo_marketing(md_novo, artigo_novo)
            d = montar_defaults(dados_ia, artigo_novo) if dados_ia else defaults_para(artigo_novo, md_novo)
        else:
            d = _placeholder_para(artigo_novo, "")

        st.session_state["_s1t"]  = d["s1_titulo"]
        st.session_state["_s1c"]  = d["s1_corpo"]
        st.session_state["_s2t"]  = d["s2_titulo"]
        st.session_state["_s2a"]  = d["s2_ancora"]
        st.session_state["_s2c"]  = d["s2_corpo"]
        st.session_state["_s3t"]  = d["s3_titulo"]
        st.session_state["_s3b1"] = d["s3_b1"]
        st.session_state["_s3b2"] = d["s3_b2"]
        st.session_state["_s3b3"] = d["s3_b3"]
        st.session_state["_s3c"]  = d["s3_corpo"]
        st.session_state["_pa"]   = d["p_ancora"]
        st.session_state["_pb1"]  = d["p_b1"]
        st.session_state["_pb2"]  = d["p_b2"]
        st.session_state["_pb3"]  = d["p_b3"]
        st.session_state["_pb4"]  = d["p_b4"]
        st.session_state["_pc"]   = d["p_corpo"]
        st.session_state["_pf"]   = d["p_fonte"]
        st.session_state["_leg"]  = d["legenda"]
        st.session_state["_scr"]  = d["script"]
        st.session_state["_artigo_ativo"] = doc_id_novo

    def _on_artigo_change():
        """Callback do selectbox — recarrega com extração IA."""
        lbl = st.session_state["_sel_artigo"]
        artigo_novo = opcoes_map[lbl]
        md_novo, _ = ler_analysis(artigo_novo["doc_id"])
        _carregar_artigo(artigo_novo, md_novo)

    # Inicializar seletor se necessário
    if "_sel_artigo" not in st.session_state:
        st.session_state["_sel_artigo"] = opcoes_label[0]

    st.selectbox("Artigo", opcoes_label,
                 key="_sel_artigo",
                 on_change=_on_artigo_change,
                 label_visibility="collapsed")

    artigo  = opcoes_map[st.session_state["_sel_artigo"]]
    doc_id  = artigo["doc_id"]
    md, meta = ler_analysis(doc_id)

    # Inicializar na primeira carga OU quando artigo mudou
    col_recarregar, col_info = st.columns([1, 4])
    with col_recarregar:
        recarregar = st.button("🤖 Analisar com IA", type="primary", use_container_width=True)
    with col_info:
        if st.session_state.get("_artigo_ativo") == doc_id:
            st.caption(f"Conteúdo carregado para: **{artigo.get('titulo','')[:60]}**")
        else:
            st.caption("Clique em **Analisar com IA** para carregar o conteúdo deste artigo.")

    if recarregar or st.session_state.get("_artigo_ativo") != doc_id:
        with st.spinner("Analisando artigo com IA — aguarde ~10 segundos..."):
            _carregar_artigo(artigo, md)
        st.rerun()

    # Card resumo
    st.markdown(f"""<div class="card">
        <span class="nota-badge">{artigo.get('nota_aplicabilidade')}</span>
        <strong>{artigo.get('titulo','')[:90]}</strong>
        <div style="color:#888;font-size:.82rem;margin-top:4px">
            {artigo.get('revista','')} · {(artigo.get('data_publicacao') or '')[:10]} · {artigo.get('doenca_principal','')}
        </div>
        <div style="color:#3BAF9E;font-size:.85rem;margin-top:6px;font-style:italic">
            {artigo.get('gancho_lista','')}
        </div>
    </div>""", unsafe_allow_html=True)

    st.markdown("---")

    # ── Tabs ──────────────────────────────────────────────────────────────────
    tab_s, tab_p, tab_l, tab_v = st.tabs([
        "📱 Stories (sem legenda)",
        "🖼 Post Feed + Legenda",
        "✍ Legenda Completa",
        "🎬 Script de Vídeo",
    ])

    # ── STORIES ───────────────────────────────────────────────────────────────
    with tab_s:
        st.info("Stories ficam 24h no ar e somem — apenas imagem, sem legenda.")
        st.markdown('<div class="sec">Story 1 — Frase Icônica</div>', unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1:
            st.text_area("Título (\\n = quebra de linha)", key="_s1t",
                         value=st.session_state.get("s1_titulo",""), height=110)
            st.text_area("Corpo", key="_s1c",
                         value=st.session_state.get("s1_corpo",""), height=90)

        st.markdown('<div class="sec">Story 2 — Dado Âncora</div>', unsafe_allow_html=True)
        c3, c4 = st.columns(2)
        with c3:
            st.text_area("Título", key="_s2t",
                         value=st.session_state.get("s2_titulo",""), height=80)
            st.text_area("Estatística (em verde grande)", key="_s2a",
                         value=st.session_state.get("s2_ancora",""), height=90)
            st.text_area("Corpo", key="_s2c",
                         value=st.session_state.get("s2_corpo",""), height=90)

        st.markdown('<div class="sec">Story 3 — Pontos-chave</div>', unsafe_allow_html=True)
        c5, c6 = st.columns(2)
        with c5:
            st.text_area("Título", key="_s3t",
                         value=st.session_state.get("s3_titulo",""), height=80)
            st.text_input("Bullet 1", key="_s3b1",
                          value=st.session_state.get("s3_b1",""))
            st.text_input("Bullet 2", key="_s3b2",
                          value=st.session_state.get("s3_b2",""))
            st.text_input("Bullet 3", key="_s3b3",
                          value=st.session_state.get("s3_b3",""))
            st.text_area("Corpo", key="_s3c",
                         value=st.session_state.get("s3_corpo",""), height=80)

    # ── POST FEED ─────────────────────────────────────────────────────────────
    with tab_p:
        st.info("Post persiste no feed — acompanha legenda densa (editada na aba ✍).")
        st.markdown('<div class="sec">Post Feed 1080×1080</div>', unsafe_allow_html=True)
        cp1, cp2 = st.columns(2)
        with cp1:
            st.text_input("Âncora", key="_pa",
                          value=st.session_state.get("p_ancora",""))
            st.text_input("Bullet 1", key="_pb1",
                          value=st.session_state.get("p_b1",""))
            st.text_input("Bullet 2", key="_pb2",
                          value=st.session_state.get("p_b2",""))
            st.text_input("Bullet 3", key="_pb3",
                          value=st.session_state.get("p_b3",""))
            st.text_input("Bullet 4", key="_pb4",
                          value=st.session_state.get("p_b4",""))
            st.text_input("Linha de contexto", key="_pc",
                          value=st.session_state.get("p_corpo",""))
            st.text_input("Fonte", key="_pf",
                          value=st.session_state.get("p_fonte",""))

    # ── LEGENDA ───────────────────────────────────────────────────────────────
    with tab_l:
        st.info("Esta legenda acompanha o post feed. Stories não levam legenda.")
        st.text_area("Legenda Instagram", key="_leg",
                     value=st.session_state.get("legenda",""), height=500)
        if st.button("📋 Preparar para copiar"):
            st.code(st.session_state.get("_leg",""), language=None)

    # ── SCRIPT DE VÍDEO ───────────────────────────────────────────────────────
    with tab_v:
        tom = st.selectbox("Tom do vídeo:", [
            "Tecnico - fala com cardiologistas",
            "Provocativo - questiona a pratica atual",
            "Sarcastico - expoe contradicoes com ironia leve",
            "Incitador - urgencia clinica, chama para acao",
            "Informativo - fala com publico leigo",
        ])
        st.text_area("Script", key="_scr",
                     value=st.session_state.get("script",""), height=520)
        st.caption("⏱ Estrutura: Gancho 15s · Contexto 30s · Estudo 45s · Prática 30s · CTA 15s = ~2'15\"")

    # ── GERAR PLACAS ──────────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown('<div class="sec">Gerar e Agendar</div>', unsafe_allow_html=True)

    # Agendamento simplificado — apenas o dia
    dias = ["Selecione o dia", "Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]
    col_ag1, col_ag2, col_ag3 = st.columns([2, 1, 1])
    with col_ag1:
        dia_pub = st.selectbox("📅 Dia de publicação (todo o kit vai no mesmo dia)", dias)
    with col_ag2:
        hora_stories = st.time_input("Stories (horário)", value=None, help="Horário de postagem dos stories")
    with col_ag3:
        hora_post = st.time_input("Post feed (horário)", value=None, help="Horário de postagem do post")

    col_b1, col_b2 = st.columns([3, 1])
    with col_b1:
        gerar = st.button("🎨 Gerar Kit Completo", type="primary", use_container_width=True)
    with col_b2:
        if st.button("📂 Abrir pasta", use_container_width=True):
            out_dir = ROOT / "outputs" / "marketing" / doc_id
            out_dir.mkdir(parents=True, exist_ok=True)
            os.system(f'open "{out_dir}"')

    if gerar:
        s1 = StoryData(tipo="iconica",
                       titulo=st.session_state.get("_s1t",""),
                       corpo=st.session_state.get("_s1c",""))
        s2 = StoryData(tipo="ancora",
                       titulo=st.session_state.get("_s2t",""),
                       ancora_valor=st.session_state.get("_s2a",""),
                       corpo=st.session_state.get("_s2c",""))
        s3 = StoryData(tipo="pontos",
                       titulo=st.session_state.get("_s3t",""),
                       bullets=[st.session_state.get("_s3b1",""),
                                 st.session_state.get("_s3b2",""),
                                 st.session_state.get("_s3b3","")],
                       corpo=st.session_state.get("_s3c",""))
        post = PostFeedData(
            titulo="",
            ancora_valor=st.session_state.get("_pa",""),
            bullets=[b for b in [st.session_state.get("_pb1",""), st.session_state.get("_pb2",""),
                                  st.session_state.get("_pb3",""), st.session_state.get("_pb4","")] if b],
            corpo=st.session_state.get("_pc",""),
            fonte=st.session_state.get("_pf",""),
        )

        with st.spinner("Renderizando placas..."):
            try:
                gen = PlacaGenerator()
                resultados = gen.gerar_kit_completo(doc_id, s1, s2, s3, post, prefixo="studio")

                # Salvar conteúdo
                out_dir = ROOT / "outputs" / "marketing" / doc_id
                (out_dir / "conteudo_studio.md").write_text(
                    f"# {artigo.get('titulo','')[:80]}\n\n"
                    f"**{artigo.get('revista','')} · {(artigo.get('data_publicacao') or '')[:10]}**\n\n"
                    f"---\n\n## LEGENDA INSTAGRAM\n\n{st.session_state.get('_leg','')}\n\n"
                    f"---\n\n## SCRIPT DE VÍDEO ({tom})\n\n{st.session_state.get('_scr','')}\n",
                    encoding="utf-8"
                )

                # Salvar na agenda
                if dia_pub != "Selecione o dia":
                    agenda = carregar_agenda()
                    agenda[doc_id] = {
                        "titulo": artigo.get("titulo","")[:60],
                        "dia": dia_pub,
                        "hora_stories": str(hora_stories) if hora_stories else "07:00",
                        "hora_post": str(hora_post) if hora_post else "12:00",
                        "arquivos": {k: str(v) for k, v in resultados.items() if str(v).endswith(".png")},
                    }
                    salvar_agenda(agenda)
                    st.success(f"✅ Kit gerado e agendado para {dia_pub}!")
                else:
                    st.success("✅ Kit gerado!")

                # Exibir resultados
                st.markdown('<div class="sec">Placas geradas</div>', unsafe_allow_html=True)
                c_s1, c_s2, c_s3 = st.columns(3)
                with c_s1:
                    st.image(str(resultados["story1"]), caption="Story 1 — Frase Icônica")
                with c_s2:
                    st.image(str(resultados["story2"]), caption="Story 2 — Dado Âncora")
                with c_s3:
                    st.image(str(resultados["story3"]), caption="Story 3 — Pontos-chave")

                st.image(str(resultados["post"]), caption="Post Feed 1080×1080", width=500)

            except Exception as e:
                st.error(f"Erro ao gerar: {e}")
                st.exception(e)


# ══════════════════════════════════════════════════════════════════════════════
# PÁGINA 2 — AGENDA
# ══════════════════════════════════════════════════════════════════════════════
elif pagina == "📅  Agenda da Semana":
    st.title("📅 Agenda da Semana")
    agenda = carregar_agenda()

    if not agenda:
        st.info("Nenhuma publicação agendada. Gere um kit na sessão semanal e escolha o dia.")
        st.stop()

    dias_ordem = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]
    por_dia: dict[str, list] = {d: [] for d in dias_ordem}

    for doc_id_ag, info in agenda.items():
        dia = info.get("dia", "")
        if dia in por_dia:
            por_dia[dia].append(info | {"doc_id": doc_id_ag})

    cols = st.columns(7)
    for col, dia in zip(cols, dias_ordem):
        with col:
            st.markdown(f"**{dia}**")
            for item in por_dia[dia]:
                arquivos = item.get("arquivos", {})
                n_imgs = len([v for v in arquivos.values() if v.endswith(".png")])
                st.markdown(f"""<div class="card" style="font-size:.78rem">
                    <strong>{item.get('titulo','')[:40]}</strong><br>
                    🖼 {n_imgs} placas<br>
                    📱 Stories: {item.get('hora_stories','—')}<br>
                    🖼 Post: {item.get('hora_post','—')}
                </div>""", unsafe_allow_html=True)
            if not por_dia[dia]:
                st.caption("—")

    st.markdown("---")
    if st.button("🗑 Limpar agenda completa"):
        salvar_agenda({})
        st.success("Agenda limpa.")
        st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# PÁGINA 3 — KITS GERADOS
# ══════════════════════════════════════════════════════════════════════════════
elif pagina == "📁  Kits Gerados":
    st.title("📁 Kits Gerados")

    marketing_dir = ROOT / "outputs" / "marketing"
    kits = sorted(
        [d for d in marketing_dir.iterdir() if d.is_dir() and list(d.glob("*.png"))],
        key=lambda d: d.stat().st_mtime, reverse=True
    ) if marketing_dir.exists() else []

    if not kits:
        st.info("Nenhum kit gerado ainda.")
        st.stop()

    for kit_dir in kits:
        pngs = sorted(kit_dir.glob("*.png"))
        mds  = list(kit_dir.glob("*.md"))
        data_mod = datetime.fromtimestamp(kit_dir.stat().st_mtime).strftime("%d/%m/%Y %H:%M")

        with st.expander(f"📦 {kit_dir.name}  ·  {len(pngs)} imagens  ·  {data_mod}"):
            cols = st.columns(min(len(pngs), 4))
            for col, png in zip(cols, pngs):
                with col:
                    st.image(str(png), caption=png.stem, use_container_width=True)
            if mds:
                conteudo = mds[0].read_text(encoding="utf-8")
                st.download_button(
                    "⬇ Baixar conteúdo (.md)",
                    conteudo,
                    file_name=mds[0].name,
                    mime="text/markdown",
                    key=f"dl_{kit_dir.name}",
                )
