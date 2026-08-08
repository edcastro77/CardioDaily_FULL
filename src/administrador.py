"""
administrador.py — ADMINISTRADOR.app (chave 3). CABINE DE CURADORIA.
Lê o Supabase (tabela `artigos`), mostra o top numa TABELA enxuta (revista · data · nome · NAC · MCID + links),
você VÊ o PDF/infográfico, OUVE o áudio, e APROVA marcando uma DATA DE ENVIO.
A aprovação grava a fila em `saidas/agenda_envio.csv` (nome + data) — versionável no git, lida pelo enviador diário.

Roda no seu notebook:  streamlit run administrador.py
"""
import os, csv, datetime as dt
import requests
import streamlit as st

AZUL = "#0B3D91"
_HERE = os.path.dirname(os.path.abspath(__file__))
AGENDA = os.path.abspath(os.path.join(_HERE, "..", "..", "saidas", "agenda_envio.csv"))


def _carregar_env():
    from dotenv import load_dotenv
    d = _HERE
    for _ in range(8):
        c = os.path.join(d, "CardioDaily_FULL", ".env")
        if os.path.exists(c):
            load_dotenv(c, override=True); return
        d = os.path.dirname(d)
    load_dotenv(override=True)


_carregar_env()


def _url():
    return (os.getenv("SUPABASE_URL") or "").rstrip("/")


def _key():
    for k in ("SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_SERVICE_KEY", "SUPABASE_KEY", "SUPABASE_ANON_KEY"):
        v = os.getenv(k)
        if v:
            return v
    return ""


def _verdade(x):
    return str(x).strip().lower() in ("true", "1", "t", "yes")


@st.cache_data(ttl=120)
def buscar():
    url, key = _url(), _key()
    if not url or not key:
        return None, "SUPABASE_URL / chave ausentes no .env"
    try:
        r = requests.get(f"{url}/rest/v1/artigos",
                         params={"select": "doc_id,doi,titulo,revista,data_publicacao,tipo_estudo,doenca_principal,"
                                           "nota_aplicabilidade,nota_trabalho_estatistico,mcid_avaliacao,"
                                           "caminho_pdf,caminho_audio,caminho_visual_abstract,publicar_no_site",
                                 "order": "nota_aplicabilidade.desc"},
                         headers={"apikey": key, "Authorization": f"Bearer {key}"}, timeout=40)
        r.raise_for_status()
        return r.json(), None
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"


def ler_agenda():
    if not os.path.exists(AGENDA):
        return []
    return list(csv.DictReader(open(AGENDA, encoding="utf-8")))


def gravar_agenda(linhas):
    os.makedirs(os.path.dirname(AGENDA), exist_ok=True)
    with open(AGENDA, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["data_envio", "nome", "revista", "doc_id"])
        w.writeheader()
        for l in sorted(linhas, key=lambda x: x.get("data_envio", "")):
            w.writerow(l)


st.set_page_config(page_title="CardioDaily — Administrador", page_icon="🫀", layout="wide")
st.markdown(f"<h1 style='color:{AZUL};margin-bottom:0'>CardioDaily — Curadoria</h1>"
            "<p style='color:#666;margin-top:2px'>ver · ouvir · aprovar — dados e fatos, sem firulas</p>",
            unsafe_allow_html=True)

artigos, erro = buscar()
if erro:
    st.error(f"Não consegui ler o Supabase: {erro}"); st.stop()
if not artigos:
    st.info("Nenhum artigo publicado ainda."); st.stop()

# ---------- filtros ----------
sb = st.sidebar
sb.header("Filtros")
nmin, nmax = sb.slider("NAC (nota)", 1, 10, (8, 10))          # padrão: os que você pede (>8)
tipos = sorted({a.get("tipo_estudo", "") for a in artigos if a.get("tipo_estudo")})
revistas = sorted({a.get("revista", "") for a in artigos if a.get("revista")})
temas = sorted({a.get("doenca_principal", "") for a in artigos if a.get("doenca_principal")})
f_tipo = sb.multiselect("Tipo", tipos)
f_rev = sb.multiselect("Revista", revistas)
f_tema = sb.multiselect("Tema", temas)
busca = sb.text_input("Busca no nome")


def passa(a):
    n = a.get("nota_aplicabilidade") or 0
    if not (nmin <= n <= nmax):
        return False
    if f_tipo and a.get("tipo_estudo") not in f_tipo:
        return False
    if f_rev and a.get("revista") not in f_rev:
        return False
    if f_tema and a.get("doenca_principal") not in f_tema:
        return False
    if busca and busca.lower() not in (a.get("titulo") or "").lower():
        return False
    return True


lista = [a for a in artigos if passa(a)]
st.caption(f"{len(lista)} artigo(s) no filtro · {len(artigos)} no banco")

# ---------- a TABELA de revisão ----------
st.markdown("### Tabela de revisão")
st.dataframe(
    [{"Revista": a.get("revista", ""), "Data": (a.get("data_publicacao") or "")[:10],
      "Nome": a.get("titulo", ""), "NAC": a.get("nota_aplicabilidade"),
      "Rigor": a.get("nota_trabalho_estatistico"), "MCID": (a.get("mcid_avaliacao") or "")[:60]} for a in lista],
    use_container_width=True, hide_index=True)

# ---------- ver · ouvir · aprovar (um por vez) ----------
# ═══════════════════════════════════════════════════════════════════════════════════
# 07/Ago — O CARD E O ACRI VÊM PARA CÁ (pedido do Dr. Eduardo)
#
#   *"o administrador poderia colocar o acri direto lá — desta forma eu não precisaria
#     ficar procurando na pasta staging."*
#
# Este painel lê o SUPABASE; o card ACRI e o texto do ACRI vivem no DISCO, dentro do
# pacote do artigo. A ponte entre os dois é o DOI, que existe nos dois lados. O índice é
# construído UMA vez por sessão (`cache_data`) varrendo os canônicos — 433 arquivos de
# texto, dezenas de milissegundos, sem rede.
#
# Por que não subir o card para o Storage e ler pela URL: seria coluna nova + ALTER TABLE,
# e o card é peça de trabalho dele — não vai para o site nem para o assinante. Fica no
# disco, aparece aqui, ele baixa e posta.
# ═══════════════════════════════════════════════════════════════════════════════════
import glob as _glob, os as _os, re as _re

_STAGING = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))),
                         "outputs", "STAGING")


@st.cache_data(ttl=300)
def indice_do_disco():
    """{doi_minusculo: {'pasta','card','acri'}} — a ponte entre a linha do banco e o pacote."""
    ix = {}
    for can in _glob.glob(_os.path.join(_STAGING, "*", "*_CANONICO.md")):
        try:
            txt = open(can, encoding="utf-8").read(4000)
        except Exception:
            continue
        m = _re.search(r'doi:\s*"([^"]+)"', txt)
        if not m:
            continue
        pasta = _os.path.dirname(can)
        base = _os.path.basename(pasta)
        card = _os.path.join(pasta, f"{base}_card.png")
        acri = _glob.glob(_os.path.join(pasta, "*_ACRI.txt"))
        reg = {"pasta": pasta,
               "card": card if _os.path.exists(card) else "",
               "acri": acri[0] if acri else ""}
        ix[m.group(1).strip().lower()] = reg
        # 07/Ago — DUAS CHAVES, porque uma só falhou em silêncio.
        # A primeira versão casava SÓ por DOI, e o SELECT do Supabase (linha 55) nem pedia a
        # coluna `doi` — então `_do_disco` recebia string vazia em TODO artigo e o bloco do
        # ACRI era pulado sem uma mensagem sequer. O Dr. Eduardo abriu o painel e não achou nada.
        # O `doc_id` é a chave que o portão usa e existe em toda linha; indexar pelos dois torna
        # a ponte imune a um dos lados faltar.
        try:
            import ficha_site as _F
            _d = (_F.montar(pasta) or {}).get("doc_id")
            if _d:
                ix[str(_d).strip().lower()] = reg
        except Exception:
            pass
    return ix


def _do_disco(artigo):
    """O pacote deste artigo no disco. Tenta DOI e, se falhar, doc_id."""
    ix = indice_do_disco()
    for chave in ((artigo.get("doi") or ""), (artigo.get("doc_id") or "")):
        k = str(chave).strip().lower()
        if k and k in ix:
            return ix[k]
    return {}


st.markdown("### Ver · ouvir · aprovar")
if lista:
    rotulo = {f"[{a.get('nota_aplicabilidade')}] {a.get('titulo','')[:80]} · {a.get('revista','')}": a for a in lista}
    escolha = st.selectbox("Escolha o artigo", list(rotulo.keys()))
    a = rotulo[escolha]
    c1, c2 = st.columns([2, 1])
    with c1:
        st.markdown(f"**{a.get('titulo','')}**")
        st.caption(f"{a.get('revista','')} · {(a.get('data_publicacao') or '')[:10]} · tema: {a.get('doenca_principal','')}")
        st.markdown(f"**NAC {a.get('nota_aplicabilidade')}/10** · Rigor {a.get('nota_trabalho_estatistico')}/10")
        if a.get("mcid_avaliacao"):
            st.markdown(f"**MCID:** {a['mcid_avaliacao']}")
        links = []
        if a.get("caminho_pdf"):
            links.append(f"[📄 PDF]({a['caminho_pdf']})")
        if a.get("caminho_visual_abstract"):
            links.append(f"[🖼️ Infográfico]({a['caminho_visual_abstract']})")
        if links:
            st.markdown(" · ".join(links))
        if a.get("caminho_audio"):
            st.audio(a["caminho_audio"])          # OUVIR aqui mesmo

        # ── O PACOTE NO DISCO: card para postar, ACRI para copiar ──
        _pk = _do_disco(a)
        if not _pk:
            st.caption(f"⚠️ pacote não encontrado no STAGING "
                       f"(doi={a.get('doi') or '—'} · doc_id={a.get('doc_id') or '—'})")
        if _pk.get("acri"):
            try:
                _txt = open(_pk["acri"], encoding="utf-8").read()
            except Exception:
                _txt = ""
            if _txt:
                with st.expander("📋 ACRI — copiar para o WhatsApp", expanded=True):
                    # `st.code` porque ele traz o botão de copiar no canto, e é isso que
                    # ele faz com o ACRI: copia e cola no grupo.
                    st.code(_txt, language=None)
        # O CARD não é mostrado — decisão dele em 07/Ago: *"não precisa ser o card, pode ser
        # só o txt"*. Uma imagem de 1080×1350 em cada artigo empurra a tela toda para baixo e
        # ele já viu o card quando gerou. Fica só o botão, para quando for postar.
        if _pk.get("card"):
            try:
                with open(_pk["card"], "rb") as _f:
                    st.download_button("⬇️ Baixar o card (1080×1350)", _f.read(),
                                       file_name=_os.path.basename(_pk["card"]),
                                       mime="image/png")
            except Exception:
                pass
    with c2:
        data = st.date_input("Enviar em", dt.date.today())
        if st.button("✅ Aprovar e agendar", use_container_width=True):
            ag = [l for l in ler_agenda() if l.get("doc_id") != a.get("doc_id")]
            ag.append({"data_envio": str(data), "nome": a.get("titulo", ""),
                       "revista": a.get("revista", ""), "doc_id": a.get("doc_id", "")})
            gravar_agenda(ag)
            st.success(f"Agendado para {data}.")

# ---------- a FILA (nome + data) ----------
st.markdown("### Fila de envio (nome · data) — `saidas/agenda_envio.csv`")
ag = ler_agenda()
if ag:
    st.dataframe([{"Enviar em": l["data_envio"], "Nome": l["nome"], "Revista": l.get("revista", "")} for l in ag],
                 use_container_width=True, hide_index=True)
else:
    st.caption("fila vazia — aprove artigos acima para agendar.")
