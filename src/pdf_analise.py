"""
pdf_analise.py — o PDF da ANÁLISE CRÍTICA (a peça central do site, o caminho_pdf).
Redator (voz Lapa, markdown) + metadados do canônico → HTML (identidade CardioDaily) → PDF (WeasyPrint).
Reusa o padrão do Guideline Assistant (Jinja/WeasyPrint), mas com molde próprio pra prosa do redator.

Uso:
  from pdf_analise import gerar_pdf_de_pasta
  gerar_pdf_de_pasta("<pasta_do_staging>")   # lê *_analise.md + *_CANONICO.md → escreve *_analise.pdf
"""
import os, re, glob, html as _html

AZUL = "#0B3D91"      # azul cardiológico (marca do site)
VERM = "#C00000"      # acento vermelho (linha)
CINZA = "#1F2937"

CSS = f"""
@page {{
  size: A4; margin: 2.2cm 2cm 2.8cm 2cm;
  @top-left {{ content: "{{TITULO_CURTO}} — ANÁLISE CRÍTICA CardioDaily | {{REVISTA}} {{ANO}}";
    font-family: Helvetica, Arial, sans-serif; font-size: 8pt; color: #666;
    padding-bottom: 4pt; border-bottom: 0.5pt solid {VERM}; width: 100%; }}
  @bottom-left {{ content: "CardioDaily — dados e fatos, sem firulas. Material educativo; não substitui o julgamento clínico.";
    font-family: Helvetica, Arial, sans-serif; font-size: 7.5pt; color: #666;
    padding-top: 6pt; border-top: 0.5pt solid #ccc; width: 100%; text-align: left; }}
  @bottom-right {{ content: "Página " counter(page); font-family: Helvetica, Arial, sans-serif;
    font-size: 7.5pt; color: #666; padding-top: 6pt; }}
}}
body {{ font-family: Helvetica, Arial, sans-serif; font-size: 10.5pt; color: {CINZA}; line-height: 1.5; margin: 0; }}
.capa-titulo {{ font-size: 21pt; font-weight: 700; color: {AZUL}; margin: 0 0 4pt 0; line-height: 1.2; }}
.capa-sub {{ font-size: 11pt; color: #444; margin: 0 0 2pt 0; }}
.capa-tag {{ font-size: 9pt; font-style: italic; color: #666; margin: 2pt 0 14pt 0;
  padding-bottom: 8pt; border-bottom: 1.5pt solid {VERM}; }}
.veredito {{ background: #eef2fb; border-left: 3pt solid {AZUL}; padding: 10pt 14pt; margin: 0 0 16pt 0; page-break-inside: avoid; }}
.veredito .linha {{ font-size: 11pt; font-weight: 700; color: {AZUL}; margin: 0 0 4pt 0; }}
.veredito .nsid {{ font-size: 9.5pt; color: #333; margin: 2pt 0 0 0; }}
.veredito .badge {{ display: inline-block; background: {AZUL}; color: #fff; font-size: 9pt; font-weight: 700;
  padding: 1pt 8pt; border-radius: 8pt; margin-left: 4pt; }}
h1 {{ font-size: 15pt; color: {AZUL}; margin: 16pt 0 6pt 0; page-break-after: avoid; }}
h2 {{ font-size: 13pt; font-weight: 700; color: {CINZA}; margin: 15pt 0 5pt 0; page-break-after: avoid;
  border-bottom: 0.5pt solid #ddd; padding-bottom: 2pt; }}
h3 {{ font-size: 11pt; font-weight: 700; color: #444; margin: 10pt 0 4pt 0; page-break-after: avoid; }}
p {{ margin: 5pt 0 7pt 0; text-align: justify; }}
ul, ol {{ margin: 5pt 0 9pt 0; padding-left: 18pt; }}
li {{ margin-bottom: 3pt; line-height: 1.45; }}
strong {{ color: {CINZA}; }}
em {{ color: #333; }}
/* ═══════ TABELAS — ESTILO DE REVISTA · 04/Ago/2026 ═══════════════════════════
   Duas rodadas de conserto no mesmo dia. Vale registrar as duas.

   RODADA 1 (06h) — A TABELA CORTADA. O CSS só dizia `width: 100%`. Sem `table-layout`, isso é
   um PEDIDO, não uma ordem: o motor mede a largura mínima de cada coluna pelo conteúdo, soma, e
   se passar da página TRANSBORDA. Medido no JACC: 192,2 mm numa página de 170 mm úteis — a
   coluna "Peso na agregação" saía cortada na margem. `table-layout: fixed` torna o transbordo
   matematicamente impossível.

   RODADA 2 (08h) — O DR. EDUARDO OLHOU E REPROVOU: "esteticamente não é muito interessante, e
   está sem título". Duas coisas, e as duas eram minhas:
     · o título ("Estudos Incluídos") ficava FORA da tabela; a página deitada que eu tinha
       criado forçava quebra e deixava o título órfão numa página quase em branco.
     · a grade cheia de linhas verticais, com colunas inteiras dizendo só "Não reportado".

   DECISÃO DELE (LEI 6 — o QUE é do dono):
     · ESTILO DE REVISTA: zero linha vertical. Três traços horizontais — topo, sob o cabeçalho e
       base — como NEJM e Lancet. Zebra levíssima. É o que "parece publicação séria".
     · EM PÉ, COLUNAS ENXUTAS: nada de página deitada. Coluna que não foi reportada em NENHUM
       estudo é PODADA — e a poda é DECLARADA em nota sob a tabela. Dado não some calado.
     · o título vira LEGENDA da tabela (elemento caption) — parte dela, nunca mais órfão.
   ══════════════════════════════════════════════════════════════════════════ */
table {{ width: 100%; table-layout: fixed; border-collapse: collapse; margin: 4pt 0 4pt 0;
  font-size: 8.5pt; word-wrap: break-word; overflow-wrap: break-word; hyphens: auto;
  border-top: 1.2pt solid {CINZA}; border-bottom: 1.2pt solid {CINZA}; }}
/* 04/Ago 08h45, o Dr. Eduardo: "este destaque em azul não precisa ser tão assim — poderia ser
   só o título em azul". Fora a CAIXA ALTA e o espaçamento de letra: sobra o título, em azul,
   como ele pediu. Azul é destaque; MAIÚSCULA AZUL ESPAÇADA é grito. */
caption {{ caption-side: top; text-align: left; font-size: 10.5pt; font-weight: 700;
  color: {AZUL}; padding: 12pt 0 5pt 0; }}
th {{ background: none; color: {CINZA}; text-align: left; font-weight: 700; font-size: 8pt;
  padding: 4pt 7pt 4pt 0; border: none; border-bottom: 0.8pt solid {CINZA}; vertical-align: bottom; }}
td {{ padding: 4pt 7pt 4pt 0; border: none; vertical-align: top; }}
tbody tr:nth-child(even) {{ background: #f7f8fa; }}
tr {{ page-break-inside: avoid; }}
thead {{ display: table-header-group; }}
table, caption {{ page-break-after: avoid; }}
.tab-nota {{ font-size: 7.5pt; color: #777; font-style: italic; margin: 2pt 0 14pt 0; }}
th {{ background: #eef2fb; color: {CINZA}; text-align: left; padding: 4pt 6pt; border: 0.5pt solid #ccd; }}
td {{ padding: 4pt 6pt; border: 0.5pt solid #dde; vertical-align: top; }}
"""


# valores que significam "esta célula não diz nada" — para decidir se a COLUNA inteira é vazia
_NADA = {"", "-", "–", "—", "n/a", "na", "nd", "nr", "?",
         "não reportado", "nao reportado", "não reportada", "nao reportada",
         "não reportados", "nao reportados", "não relatado", "nao relatado",
         "não informado", "nao informado", "não disponível", "nao disponivel",
         "não se aplica", "nao se aplica", "not reported", "not available", "none"}

_CEL = re.compile(r"<t([hd])\b[^>]*>(.*?)</t\1>", re.S)
_LINHA = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S)


def _texto_puro(html_celula):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", html_celula)).strip()


def _podar_colunas_vazias(tabela_html):
    """Remove as colunas em que NENHUM estudo reportou nada — e devolve os nomes removidos.

    04/Ago, escolha do Dr. Eduardo. A tabela do Arquivos Brasileiros tinha 9 colunas, e duas
    ("Peso na agregação", "Desfecho contribuído") diziam "Não reportado" em TODAS as linhas.
    Coluna que não informa nada em estudo nenhum não é dado: é largura roubada das que informam.

    O que NÃO se faz aqui: apagar em silêncio. Quem chama escreve uma nota sob a tabela dizendo
    exatamente o que saiu. O leitor tem de saber que a informação foi PEDIDA e NÃO EXISTIA —
    isso é um achado sobre a revisão, não um detalhe de diagramação.
    """
    linhas = _LINHA.findall(tabela_html)
    if len(linhas) < 2:
        return tabela_html, []
    grade = [_CEL.findall(l) for l in linhas]
    n_col = max(len(l) for l in grade)
    cabec = [_texto_puro(c) for _, c in grade[0]]
    corpo = grade[1:]

    manter, removidas = [], []
    for j in range(n_col):
        vals = [_texto_puro(l[j][1]).lower() for l in corpo if j < len(l)]
        # a 1ª coluna é a identidade da linha: nunca se poda, nem vazia
        if j == 0 or not vals or any(v not in _NADA for v in vals):
            manter.append(j)
        else:
            removidas.append(cabec[j] if j < len(cabec) else "coluna %d" % (j + 1))
    if not removidas:
        return tabela_html, []

    def _monta(linha):
        return "<tr>" + "".join("<t%s>%s</t%s>" % (t, c, t)
                                for j, (t, c) in enumerate(linha) if j in manter) + "</tr>"

    nova = ("<table><thead>" + _monta(grade[0]) + "</thead><tbody>"
            + "".join(_monta(l) for l in corpo) + "</tbody></table>")
    return nova, removidas


def _titulo_vira_caption(html):
    """Puxa o título que vem logo antes da tabela para DENTRO dela, como <caption>.

    04/Ago: "está sem título". O título era um cabeçalho IRMÃO da tabela — bastava uma quebra de
    página entre os dois para o título ficar numa página e a tabela na outra. Como <caption>,
    ele é PARTE do elemento tabela: não existe quebra capaz de separar os dois.
    """
    def _t(m):
        return "<table><caption>%s</caption>" % _texto_puro(m.group(2))

    # ⚠️ 04/Ago 08h45 — O `.*?` PREGUIÇOSO NÃO É PREGUIÇOSO O BASTANTE.
    # A 1ª versão era `<h([23])[^>]*>(.*?)</h\1>\s*<table>`. Parece certo e está errado:
    # o motor acha o `<h2>`, tenta o fechamento mais próximo, o `<table>` NÃO vem em seguida —
    # e então ele VOLTA ATRÁS e estica o `.*?` até um `</h2>` LÁ NA FRENTE que tenha tabela
    # depois. Tudo que estava no meio (parágrafos inteiros da perícia) virou legenda.
    # O Dr. Eduardo viu na tela: um parágrafo de 8 linhas em MAIÚSCULA AZUL.
    # O conserto é o "ponto temperado" `(?:(?!</h\1>).)*?` — um curinga que se recusa a
    # atravessar o fechamento. Sem esse freio, não existe quantificador preguiçoso que segure.
    return re.sub(r"<h([23])[^>]*>((?:(?!</h\1>).)*?)</h\1>\s*<table>", _t, html, flags=re.S)


def _arrumar_tabelas(html):
    def _troca(m):
        nova, fora = _podar_colunas_vazias(m.group(0))
        if not fora:
            return nova
        lista = ", ".join("<em>%s</em>" % x for x in fora)
        return nova + ('<p class="tab-nota">Colunas omitidas por não terem sido reportadas em '
                       'nenhum dos estudos: %s.</p>' % lista)
    return _titulo_vira_caption(re.sub(r"<table>.*?</table>", _troca, html, flags=re.S))


def _md_para_html(md):
    import markdown
    return _arrumar_tabelas(markdown.markdown(md, extensions=["tables", "sane_lists"]))


def _campo(txt, chave):
    m = re.search(rf'{chave}:\s*"(.*?)"\s*$', txt, re.M)
    return m.group(1).strip() if m else ""


def _num(txt, chave):
    m = re.search(rf"{chave}:\s*(\d+)", txt)
    return m.group(1) if m else "?"


def _do_nome_do_arquivo(pasta):
    """Título, revista e ano a partir do NOME da pasta — `AAAA-MM-Revista-Titulo`.

    Quem montou esse nome foi o CLASSIFICADOR, com metadado do PubMed. É CATÁLOGO, não é o
    modelo relendo o PDF: como fonte de identificação, é melhor que a extração.
    """
    m = re.match(r"^(\d{4})-(\d{2})-([^-]+)-(.+)$", os.path.basename(str(pasta).rstrip("/")))
    if not m:
        return {}
    ano, _mes, rev, tit = m.groups()
    return {"ano": ano, "revista": rev.replace("_", " ").strip(),
            "titulo": tit.replace("_", " ").strip()}


def parse_meta(canonico, pasta=""):
    """Extrai metadados do frontmatter do canônico p/ a capa e o veredito.

    ═══ 04/Ago 08h35 — A LEI 9, COMETIDA POR MIM, HORAS DEPOIS DE INVOCÁ-LA ═══
    O `SCHEMA_FATOS_META` não pedia titulo/revista/ano, então o canônico das meta-análises sai
    com os três VAZIOS. Às 06h eu consertei isso — mas só no `ficha_site.py`, que monta a linha
    do Supabase. NÃO varri o `pdf_analise.py`, que lê exatamente os mesmos campos para a CAPA e
    para o CABEÇALHO de toda página.

    Resultado: o Dr. Eduardo abriu o PDF às 08h35 e o cabeçalho dizia
    "Análise — ANÁLISE CRÍTICA CardioDaily |" — sem título, sem revista, sem ano.

    É a definição da LEI 9: uma regra mora em vários blocos; consertar onde se achou e seguir em
    frente é o mesmo que não consertar, porque o bloco que sobrou continua rodando EM SILÊNCIO.
    Blocos onde a identificação vive: (1) analise.py/SCHEMA · (2) analise_meta_prompt.md ·
    (3) ficha_site.py · (4) pdf_analise.py ← este, esquecido na primeira passada.
    """
    n = _do_nome_do_arquivo(pasta) if pasta else {}
    return {
        "titulo": _campo(canonico, "titulo") or n.get("titulo", ""),
        "revista": _campo(canonico, "revista") or n.get("revista", ""),
        "ano": _campo(canonico, "ano") or n.get("ano", ""),
        "doi": _campo(canonico, "doi"),
        "nac": _num(canonico, "nota_aplicabilidade_clinica"),
        "rigor": _num(canonico, "nota_trabalho_estatistico"),
        "muda": _campo(canonico, "muda_conduta"),
        "nsid_classe": _campo(canonico, "classificacao"),
        "nsid_frase": _campo(canonico, "frase_chave"),
    }


def montar_html(meta, corpo_md):
    # tira só um H1 de topo, se houver (evita título gigante duplicado). NUNCA corta o miolo.
    corpo_md = re.sub(r"^\s*#\s+.*\n", "", corpo_md, count=1)
    corpo = _md_para_html(corpo_md)
    titulo_curto = _html.escape((meta["titulo"] or "Análise")[:52])
    css = (CSS.replace("{TITULO_CURTO}", titulo_curto)
              .replace("{REVISTA}", _html.escape(meta["revista"]))
              .replace("{ANO}", _html.escape(meta["ano"])))
    nsid = ""
    if meta["nsid_classe"] and meta["nsid_classe"] != "n/a":
        nsid = (f'<div class="nsid"><strong>Relevância clínica (N-SID):</strong> '
                f'<span class="badge">{_html.escape(meta["nsid_classe"])}</span> — {_html.escape(meta["nsid_frase"])}</div>')
    return f"""<!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8">
<title>{titulo_curto} — Análise CardioDaily</title><style>{css}</style></head><body>
<div class="capa-titulo">{_html.escape(meta["titulo"])}</div>
<div class="capa-sub">{_html.escape(meta["revista"])} · {_html.escape(meta["ano"])}{(' · DOI ' + _html.escape(meta["doi"])) if meta["doi"] and meta["doi"]!='n/a' else ''}</div>
<div class="capa-tag">Análise crítica CardioDaily — dados e fatos, sem firulas.</div>
<div class="veredito">
  <div class="linha">Aplicabilidade clínica (NAC): {meta["nac"]}/10 · Rigor estatístico: {meta["rigor"]}/10 · Muda conduta: {_html.escape(meta["muda"])}</div>
  {nsid}
</div>
{corpo}
</body></html>"""


def gerar_pdf_de_pasta(pasta, so_html=False):
    """Lê *_analise.md + *_CANONICO.md da pasta → escreve *_analise.html e *_analise.pdf."""
    an = glob.glob(os.path.join(pasta, "*_analise.md"))
    can = glob.glob(os.path.join(pasta, "*_CANONICO.md"))
    if not an or not can:
        raise FileNotFoundError("faltam *_analise.md ou *_CANONICO.md na pasta")
    base = os.path.basename(an[0]).replace("_analise.md", "")
    meta = parse_meta(open(can[0], encoding="utf-8").read(), pasta)
    corpo = open(an[0], encoding="utf-8").read()
    html_str = montar_html(meta, corpo)
    html_path = os.path.join(pasta, base + "_analise.html")
    open(html_path, "w", encoding="utf-8").write(html_str)
    if so_html:
        return html_path
    from weasyprint import HTML
    pdf_path = os.path.join(pasta, base + "_analise.pdf")
    HTML(string=html_str).write_pdf(pdf_path)
    return pdf_path


if __name__ == "__main__":
    import sys
    print("gerado:", gerar_pdf_de_pasta(sys.argv[1]))
