"""
administrador.py — ADMINISTRADOR.app (chave 3). CABINE DE CURADORIA.
Lê o Supabase (tabela `artigos`), mostra o top numa TABELA enxuta (revista · data · nome · NAC · MCID + links),
você VÊ o PDF/infográfico, OUVE o áudio, e APROVA marcando uma DATA DE ENVIO.
A aprovação grava a fila na tabela `agenda_envio` do Supabase (14/Ago/2026), lida pelo cron das 07:00
na nuvem — o envio NÃO depende deste Mac estar ligado, igual ao Radar.

Roda no seu notebook:  streamlit run administrador.py
"""
# 11/Ago — o `re as _re` estava importado na linha 256, e o filtro de data o usa na 173.
# Compila perfeitamente; quebra com NameError na hora que o painel abre — o MESMO formato
# do `_VOO` que custou 10 artigos pagos em 10/Ago. Import de módulo mora no topo, ponto.
import os, csv, re as _re, datetime as dt
import requests
from supabase_chaves import cabecalhos
import streamlit as st

AZUL = "#0B3D91"
_HERE = os.path.dirname(os.path.abspath(__file__))

# ─────────────────────────────────────────────────────────────────────────────────────
# LÁPIDE — 14/Ago/2026 · a agenda em ARQUIVO acabou
#
# Aqui vivia `AGENDA = <raiz>/saidas/agenda_envio.csv`, e acima dela um comentário longo
# sobre o `..` a mais que fazia a aprovação cair FORA do projeto (11/Ago). Aquele defeito
# era real e o conserto foi certo — mas o problema de fundo era outro: **agenda em arquivo
# no Mac dele**. Enquanto ela morasse no disco, a nuvem não podia enviar, e o envio dependia
# de ele clicar.
#
# Agora a agenda é a tabela `agenda_envio` no Supabase. Não há caminho de arquivo para
# errar, não há `..` para contar, e o cron das 07:00 lê de qualquer lugar do mundo.
#
# O arquivo `saidas/agenda_envio.csv` continua no disco como histórico do que foi curado
# até 14/Ago. NINGUÉM MAIS O LÊ.
# ─────────────────────────────────────────────────────────────────────────────────────
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
                                           "caminho_pdf,caminho_audio,caminho_visual_abstract,publicar_no_site,"
                                           # 20/Ago — as 4 do tema. Sem elas o painel não tinha como
                                           # filtrar pelo vocabulário de verdade (ver o comentário
                                           # do filtro "Tema", logo abaixo).
                                           "tema,tema_secundario,tema_origem,keywords,mesh_terms",
                                 "order": "nota_aplicabilidade.desc"},
                         headers=cabecalhos(key), timeout=40)
        r.raise_for_status()
        return r.json(), None
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"


# ═══════════════════════════════════════════════════════════════════════════════════
# 14/Ago/2026 — A AGENDA MUDOU DE CASA: DO DISCO PARA O SUPABASE
#
# Pergunta do Dr. Eduardo: *"por que o sistema não usa o mesmo do radar, que envia todos
# os dias independente de como meu computador estiver ligado ou não?"*
#
# Porque o Radar não depende de nada no Mac dele. O envio de artigos era igual — mesma
# Z-API, mesmo distribuidor — mas a lista do que enviar morava num CSV no disco, e a nuvem
# não enxerga o disco dele. Era só isso: um arquivo.
#
# Agora a Chave 3 grava na tabela `agenda_envio`, e o cron das 07:00 lê de lá. O Mac deixa
# de importar — ele pode estar de plantão com o notebook fechado.
#
# `enviado_em` mora na MESMA linha: NULL = ainda não saiu. A pergunta "está agendado?" e a
# pergunta "já foi enviado?" passam a ter uma fonte só.
#
# ⚠️ O CSV continua no disco como histórico do que foi curado até hoje, mas NINGUÉM MAIS O
#    LÊ. Se voltar a ser lido, são duas agendas — e agenda em dois lugares é o defeito que
#    custou os dias 09, 10 e 11.
# ═══════════════════════════════════════════════════════════════════════════════════
def ler_agenda():
    """A fila inteira, do Supabase. Devolve [] com aviso na tela se a leitura falhar."""
    url, key = _url(), _key()
    try:
        r = requests.get(f"{url}/rest/v1/agenda_envio",
                         params={"select": "data_envio,doc_id,titulo,revista,enviado_em",
                                 "order": "data_envio.asc"},
                         headers=cabecalhos(key), timeout=30)
        r.raise_for_status()
        # mantém os nomes que o resto do painel já usa (`nome` era o título no CSV)
        return [{"data_envio": l["data_envio"], "nome": l.get("titulo") or "",
                 "revista": l.get("revista") or "", "doc_id": l["doc_id"],
                 "enviado_em": l.get("enviado_em")} for l in (r.json() or [])]
    except Exception as e:
        st.error(f"Não consegui ler a agenda no Supabase: {type(e).__name__}: {e}")
        return []


def agendar(artigo, data_envio):
    """Põe UM artigo na fila para uma data. Devolve (ok, mensagem).

    Um upsert por (data_envio, doc_id): clicar duas vezes no mesmo artigo e na mesma data
    não cria linha dupla — a tabela tem UNIQUE, e sem isso ele receberia em dobro.
    """
    url, key = _url(), _key()
    try:
        r = requests.post(
            f"{url}/rest/v1/agenda_envio",
            params={"on_conflict": "data_envio,doc_id"},
            headers=cabecalhos(key, {"Content-Type": "application/json",
                                     "Prefer": "resolution=merge-duplicates,return=representation"}),
            json={"data_envio": str(data_envio), "doc_id": artigo.get("doc_id"),
                  "titulo": (artigo.get("titulo") or "")[:400],
                  "revista": artigo.get("revista") or ""},
            timeout=30)
        r.raise_for_status()
        return True, ""
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def desagendar(doc_id, data_envio):
    """Tira da fila. Só remove o que AINDA NÃO SAIU — o que já foi é histórico e fica."""
    url, key = _url(), _key()
    try:
        r = requests.delete(
            f"{url}/rest/v1/agenda_envio",
            params={"doc_id": f"eq.{doc_id}", "data_envio": f"eq.{data_envio}",
                    "enviado_em": "is.null"},
            headers=cabecalhos(key), timeout=30)
        r.raise_for_status()
        return True, ""
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


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

# ═══ 20/Ago/2026 — O FILTRO "TEMA" LIA O VOCABULÁRIO ERRADO ═══
#
# Ele digitou "OBSTETRIC" na busca e voltou ZERO de 520: *"o administrador é inútil como ele
# está funcionando hoje — ele não programa nada, não acha nada. A lista de temas está podre."*
#
# A causa, medida: este filtro lia `doenca_principal`, que é OUTRA lista — 8 rótulos criados
# por regex de palavra-chave lá no `ficha_site._tema()`:
#     Insuficiência Cardíaca 213 · Cardiologia Preventiva 149 · Coronária/DAC 106 ·
#     Valvopatias 54 · Arritmias 50 · Outros 29 · Imagem Cardíaca 9 · Hipertensão 6
# Não existe Cardio-Obstetrícia ali. Nem Miocardiopatias, nem Cardio-Oncologia, nem UTI.
# **Duas listas de temas no mesmo sistema** — a LEI 9 na forma mais cara: a máquina de temas
# de 17/Ago (13 temas, MeSH, tripé) nunca chegou à tela onde ele decide o que enviar.
#
# `doenca_principal` continua existindo porque o SITE usa (cardiodaily.ts → TEMAS) e mudá-lo
# quebraria a vitrine. Mas quem manda na curadoria agora é `tema`.
temas = sorted({t for a in artigos for t in (a.get("tema"), a.get("tema_secundario"))
                if t and t != "Não se aplica"})
f_tipo = sb.multiselect("Tipo", tipos)
f_rev = sb.multiselect("Revista", revistas)
f_tema = sb.multiselect("Tema", temas,
                        help="Casa com o tema PRINCIPAL ou o SECUNDÁRIO — um artigo pertence "
                             "legitimamente a dois, e o assinante de qualquer um dos dois recebe.")
busca = sb.text_input("Busca (título · tema · palavras-chave · MeSH)",
                      help="Procura em tudo, não só no título. É o que faz 'obstetric' e "
                           "'amiloidose' acharem o que o título não diz.")

# ── a fila do que ficou SEM TEMA: visível, não silenciosa (LEI 11) ──
_sem = [a for a in artigos if not a.get("tema") or a.get("tema") == "Sem tema"]
if _sem:
    sb.divider()
    sb.caption(f"⚠️ {len(_sem)} artigo(s) sem tema")
    _SO_SEM_TEMA = sb.checkbox("Ver só os SEM TEMA", key="so_sem_tema")

# ═══ 11/Ago/2026 — FILTRO DE DATA DE PUBLICAÇÃO ═══
#
#   *"fica aparecendo artigos de 1999 na curadoria atual"* · *"preciso de filtro de data —
#    data de inicio das buscas e final"*
#
# DUAS DATAS EXISTEM, e elas respondem perguntas diferentes. Medido antes de escolher:
#     data_publicacao   1951-01-01 → 2026-10-01   "o que saiu na literatura nesta janela"
#     created_at        2026-08-05 → 2026-08-11   "o que entrou na minha fila" — 6 dias só,
#                                                 porque o banco foi refeito
# Decisão dele: **data de publicação**. É a que produz o artigo de 1999 que o incomodou.
# Dos 449 artigos, 418 são de 2026 e 20 são anteriores a 2024 (os clássicos: RALES,
# MERIT-HF, PLATO, FAME).
#
# Decisão dele sobre o PADRÃO: **vazio, mostra tudo**. Nada é escondido sem ele mandar.
# Um filtro que já vem ligado é uma armadilha de memória: um dia ele procura um artigo,
# não acha, e a causa é uma régua que ele não lembra que existe. É o mesmo princípio das
# duas fontes de verdade que nos custou o dia de hoje, na versão interface.
def _dia(a):
    """A data de publicação como texto AAAA-MM-DD, ou '' se não der para ler."""
    return str(a.get("data_publicacao") or "")[:10]


_dias = sorted(d for d in {_dia(a) for a in artigos} if len(d) == 10)
sb.markdown("---")
sb.markdown("**Data de publicação**")
if _dias:
    _d_ini = sb.text_input("De (AAAA-MM-DD)", value="", placeholder=_dias[0],
                           help="Deixe vazio para não limitar. O mais antigo no banco é "
                                f"{_dias[0]}.")
    _d_fim = sb.text_input("Até (AAAA-MM-DD)", value="", placeholder=_dias[-1],
                           help="Deixe vazio para não limitar. O mais recente no banco é "
                                f"{_dias[-1]}.")
    # Atalhos, porque digitar data à mão em painel é fricção — mas nenhum vem marcado.
    _atalho = sb.radio("atalhos", ["—", "90 dias", "12 meses", "só 2026"],
                       horizontal=True, label_visibility="collapsed")
    if _atalho != "—":
        _hoje = dt.date.today()
        _de = {"90 dias": _hoje - dt.timedelta(days=90),
               "12 meses": _hoje - dt.timedelta(days=365),
               "só 2026": dt.date(2026, 1, 1)}[_atalho]
        _d_ini, _d_fim = _de.isoformat(), ""
        sb.caption(f"atalho ativo: de {_d_ini} em diante")
else:
    _d_ini = _d_fim = ""

# As datas digitadas erradas não podem filtrar em silêncio: um "2026/08" que não casa com
# nada esvaziaria a tela sem dizer por quê — o defeito do dia inteiro, de novo.
_ruins = [r for r in ((_d_ini, "De"), (_d_fim, "Até"))
          if r[0] and not _re.fullmatch(r"\d{4}-\d{2}-\d{2}", r[0])]
for _v, _q in _ruins:
    sb.error(f"«{_q}»: `{_v}` não é uma data AAAA-MM-DD — este campo está sendo IGNORADO.")
if [r for r in _ruins if r[1] == "De"]:
    _d_ini = ""
if [r for r in _ruins if r[1] == "Até"]:
    _d_fim = ""

# Janela invertida (fim antes do início) não devolve NADA, e a tela vazia não explica por quê.
# Medido na bancada: com "de 2026-08-01 até 2026-07-01" sobrava 1 artigo de 7 — o único sem
# data no metadado. Ele olharia para uma lista de um item e não teria como saber a causa.
if _d_ini and _d_fim and _d_fim < _d_ini:
    sb.error(f"A data final (`{_d_fim}`) é ANTERIOR à inicial (`{_d_ini}`) — "
             f"nenhuma publicação cabe nessa janela.")


def passa(a, so_sem_tema=False):
    n = a.get("nota_aplicabilidade") or 0
    if not (nmin <= n <= nmax):
        return False
    if f_tipo and a.get("tipo_estudo") not in f_tipo:
        return False
    if f_rev and a.get("revista") not in f_rev:
        return False
    # ── TEMA: casa com o PRINCIPAL ou o SECUNDÁRIO ──
    # Um artigo pertence legitimamente a dois temas, e o assinante de QUALQUER um dos dois
    # recebe. Foi ele quem apontou isso, olhando o septo/QRS na amiloidose: *"mas no caso 40
    # cabe as duas coisas — isso não é um erro."* Filtrar só pelo principal esconderia do
    # curador metade do que o assinante vai receber.
    if f_tema and not ({a.get("tema"), a.get("tema_secundario")} & set(f_tema)):
        return False
    # ⚠️ 21/Ago — aqui eu tinha escrito `st.session_state.get("_so_sem_tema")`, e isso QUEBROU a
    # bateria: a trava `teste_o_filtro_de_data...` extrai esta função e a roda ISOLADA, sem o
    # Streamlit. `NameError: name 'st' is not defined`, e a bateria inteira parou.
    # A lição é de desenho, não de sintaxe: **a regra de filtro não pode depender do estado da
    # TELA.** Se ela depende, deixa de ser testável fora dela — e trava que não roda é trava que
    # dá aprovado por ausência (o defeito de 06/Ago). A preferência vira PARÂMETRO, com padrão.
    if so_sem_tema and a.get("tema") not in (None, "", "Sem tema"):
        return False

    # ── BUSCA: em TUDO, não só no título ──
    # Ele digitou "OBSTETRIC" e voltou zero de 520. O título quase nunca diz o assunto pelo
    # nome que se procura — "Experiences of Racism and Risk of Preeclampsia" é cardio-obstetrícia
    # e não tem a palavra. Quem sabe são as keywords, os descritores MeSH e o tema.
    if busca:
        _b = busca.lower()
        _onde = " ".join(str(x) for x in (
            a.get("titulo") or "", a.get("tema") or "", a.get("tema_secundario") or "",
            a.get("revista") or "",
            " ".join(a.get("keywords") or []), " ".join(a.get("mesh_terms") or []))).lower()
        if _b not in _onde:
            return False
    # Data: comparação de texto AAAA-MM-DD, que ordena igual à data. Artigo SEM data legível
    # nunca é escondido por este filtro — sumir por falta de dado seria punir o artigo pelo
    # defeito do metadado.
    d = _dia(a)
    if len(d) == 10:
        if _d_ini and d < _d_ini:
            return False
        if _d_fim and d > _d_fim:
            return False
    return True


lista = [a for a in artigos if passa(a, _SO_SEM_TEMA)]

# O painel DIZ quando está escondendo coisa, e por quê. Um contador que só mostra o total
# filtrado deixa a pergunta "cadê o artigo?" sem resposta na própria tela.
_ativos = []
if (nmin, nmax) != (1, 10):
    _ativos.append(f"nota {nmin}–{nmax}")
if f_tipo:
    _ativos.append(f"tipo: {', '.join(f_tipo)}")
if f_rev:
    _ativos.append(f"revista: {len(f_rev)} selecionada(s)")
if f_tema:
    _ativos.append(f"tema: {', '.join(f_tema)}")
if busca:
    _ativos.append(f"nome contém «{busca}»")
if _d_ini or _d_fim:
    _ativos.append(f"publicado de {_d_ini or '—'} até {_d_fim or '—'}")

st.caption(f"**{len(lista)}** artigo(s) na tela · {len(artigos)} no banco"
           + (f" · {len(artigos) - len(lista)} escondidos pelos filtros" if _ativos else ""))
if _ativos:
    st.caption("filtros ativos: " + " · ".join(_ativos))
if not lista and _ativos:
    st.warning("Nenhum artigo passa nos filtros atuais — não é que o banco esteja vazio. "
               "Limpe um filtro na barra lateral.")

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
import glob as _glob, os as _os

_OUT     = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))), "outputs")
_STAGING = _os.path.join(_OUT, "STAGING")
_ARQUIVO = _os.path.join(_OUT, "ARQUIVO")          # AAAA-MM/<pacote>/

# ═══ 11/Ago/2026 — O ACRI SUMIU PORQUE O ARQUIVADOR MUDOU O PACOTE DE LUGAR ═══
#
# O Dr. Eduardo: *"concerta o acri que nao esta mais aparecendo no administrador"*.
#
# MEDIDO, não suposto. Dos 37 artigos nota 9 que o painel lista por padrão, **26 não achavam
# pacote nenhum**. Os pacotes não sumiram — mudaram de endereço:
#
#     outputs/STAGING/   196 pacotes · 147 ACRI     ← o índice olhava SÓ aqui
#     outputs/ARQUIVO/   864 pacotes · 571 ACRI     ← invisível para o painel
#
# A Chave 4 (Arquivador) move o pacote concluído para `outputs/ARQUIVO/AAAA-MM/` — é o
# trabalho dela, e ela faz certo. Só que o painel continuou lendo o endereço antigo. O artigo
# segue no Supabase (449 linhas), aparece na lista, ele clica — e o bloco do ACRI simplesmente
# não desenha. Nada quebra, nada avisa. Quanto mais o sistema é usado, mais artigos perdem o
# ACRI: cada rodada do Arquivador esvazia mais um pedaço do painel.
#
# É a MESMA família do resto da semana — duas pontas, uma escreve num lugar novo e a outra
# continua lendo o velho, sem nada quebrando no meio:
#     09/Ago  o `agenda_envio.csv` era gravado e ninguém lia
#     11/Ago  gravar e ler o MESMO nome em pastas diferentes (dois `..`)
#     11/Ago  DOIS telefones do dono, e a trava comparando com o velho
#     11/Ago  o pacote muda de pasta e o painel fica olhando a antiga
#
# Agora o índice varre AS DUAS ÁRVORES. O STAGING é varrido POR ÚLTIMO de propósito: se o
# mesmo DOI existir nos dois lugares (reanálise ainda não arquivada), quem vale é o recente.
_RAIZES = (_ARQUIVO, _STAGING)                      # ordem importa: STAGING sobrescreve


# O ttl era 300s (5 min). Com o ARQUIVO junto são 1.015 pacotes: 1,2s de varredura + 5,6s de
# `montar()` = ~7s. Uma vez está ok; a cada 5 minutos, no meio da curadoria, é castigo. O disco
# não muda enquanto ele curadora — só quando ele roda a Chave 2 ou a 4, e aí ele reabre o painel.
@st.cache_data(ttl=3600, show_spinner="Lendo os pacotes no disco (STAGING + ARQUIVO)…")
def indice_do_disco():
    """{doi_minusculo: {'pasta','card','acri'}} — a ponte entre a linha do banco e o pacote.

    Varre STAGING (trabalho do dia) E ARQUIVO (tudo que a Chave 4 já guardou).
    """
    ix = {}
    canonicos = []
    for raiz in _RAIZES:
        # STAGING é `<raiz>/<pacote>/`; ARQUIVO é `<raiz>/AAAA-MM/<pacote>/`. Os dois padrões.
        canonicos += sorted(_glob.glob(_os.path.join(raiz, "*", "*_CANONICO.md")))
        canonicos += sorted(_glob.glob(_os.path.join(raiz, "*", "*", "*_CANONICO.md")))
    for can in canonicos:
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
            # 10/Ago — o administrador LÊ, não publica: `montar()` é código de produção e marca
            # o waypoint P1_FICHA. Sem silenciar, cada abertura do painel escrevia uma marca de
            # produção por pacote no plano de voo — e a Chave 18 passava a relatar artigos
            # "parados no P1_FICHA" que na verdade tinham chegado ao fim horas antes.
            # Mesmo motivo do `ensaio_seco.py`; achado na mesma varredura.
            import voo as _VOO
            _VOO.silenciar(True)
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
            st.warning(f"⚠️ Não achei o pacote deste artigo no disco (procurei em STAGING e "
                       f"ARQUIVO).\n\ndoi=`{a.get('doi') or '—'}` · doc_id=`{a.get('doc_id') or '—'}`")
        elif not _pk.get("acri"):
            # 11/Ago — o silêncio aqui era metade do problema. Sem ACRI e sem mensagem, a tela
            # fica idêntica à de "o índice não funciona", e não há como distinguir uma da outra.
            # São coisas MUITO diferentes: uma é defeito, a outra é a LEI 10 fazendo o trabalho.
            st.info(f"Este artigo não tem ACRI no pacote — o card só é gerado com nota ≥ 6.\n\n"
                    f"Pasta: `{_os.path.basename(_pk['pasta'])}`")
        else:
            try:
                _txt = open(_pk["acri"], encoding="utf-8").read()
            except Exception as _e:
                _txt = ""
                st.error(f"O ACRI existe mas não consegui ler: {type(_e).__name__}")
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
            # 14/Ago — grava no Supabase, e SÓ diz "agendado" se o banco confirmar.
            # A versão anterior escrevia no CSV e imprimia "Agendado para <data>" sem
            # conferir nada. Foi assim que ele aprovou para os dias 12 e 13, leu a mensagem
            # de sucesso, e nada chegou. Mensagem de sucesso tem que custar uma confirmação.
            ok, erro = agendar(a, data)
            if ok:
                st.success(f"✅ Agendado para {data} — sai às 07:00, sem você precisar clicar.")
                st.rerun()
            else:
                st.error(f"🔴 NÃO agendei — o Supabase recusou: {erro}\n\n"
                         f"O artigo NÃO vai sair. Tente de novo.")

# ---------- a FILA ----------
st.markdown("### Fila de envio — tabela `agenda_envio` no Supabase")
st.caption("Sai automaticamente às 07:00, pela nuvem. Não depende do seu Mac estar ligado.")
ag = ler_agenda()
if ag:
    _hoje = dt.date.today().isoformat()
    _pend = [l for l in ag if not l.get("enviado_em")]
    _fut = [l for l in _pend if l["data_envio"] >= _hoje]
    _atrasados = [l for l in _pend if l["data_envio"] < _hoje]

    if _atrasados:
        # 14/Ago — os dias 12 e 13 passaram em branco e NADA avisou. O silêncio era idêntico
        # a "está tudo funcionando". Agora a fila atrasada aparece em vermelho, no topo.
        st.error(f"⚠️ {len(_atrasados)} artigo(s) com data JÁ PASSADA e ainda não enviados. "
                 f"Eles não saem sozinhos — a data precisa ser refeita para hoje ou depois.")
        st.dataframe([{"Era para sair em": l["data_envio"], "Nome": l["nome"][:80],
                       "Revista": l.get("revista", "")} for l in _atrasados],
                     use_container_width=True, hide_index=True)

    st.markdown(f"**Programado ({len(_fut)})**")
    if _fut:
        st.dataframe([{"Sai em": l["data_envio"], "Nome": l["nome"][:80],
                       "Revista": l.get("revista", "")} for l in _fut],
                     use_container_width=True, hide_index=True)
    else:
        st.caption("nada programado para hoje em diante.")

    _enviados = [l for l in ag if l.get("enviado_em")]
    with st.expander(f"✅ já enviados ({len(_enviados)})"):
        st.dataframe([{"Enviado em": (l.get("enviado_em") or "")[:16].replace("T", " "),
                       "Data marcada": l["data_envio"], "Nome": l["nome"][:80]}
                      for l in reversed(_enviados)],
                     use_container_width=True, hide_index=True)
else:
    st.caption("fila vazia — aprove artigos acima para agendar.")
