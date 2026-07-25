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
table {{ width: 100%; border-collapse: collapse; margin: 8pt 0 12pt 0; font-size: 9pt; }}
th {{ background: #eef2fb; color: {CINZA}; text-align: left; padding: 4pt 6pt; border: 0.5pt solid #ccd; }}
td {{ padding: 4pt 6pt; border: 0.5pt solid #dde; vertical-align: top; }}
"""


def _md_para_html(md):
    import markdown
    return markdown.markdown(md, extensions=["tables", "sane_lists"])


def _campo(txt, chave):
    m = re.search(rf'{chave}:\s*"(.*?)"\s*$', txt, re.M)
    return m.group(1).strip() if m else ""


def _num(txt, chave):
    m = re.search(rf"{chave}:\s*(\d+)", txt)
    return m.group(1) if m else "?"


def parse_meta(canonico):
    """Extrai metadados do frontmatter do canônico p/ a capa e o veredito."""
    return {
        "titulo": _campo(canonico, "titulo"),
        "revista": _campo(canonico, "revista"),
        "ano": _campo(canonico, "ano"),
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
    meta = parse_meta(open(can[0], encoding="utf-8").read())
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
