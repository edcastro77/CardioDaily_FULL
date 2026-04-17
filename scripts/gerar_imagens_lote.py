#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CardioDaily — Geração de Visual Abstracts em Lote
Busca artigos sem imagem, extrai estrutura clínica via GPT-4o,
renderiza HTML no estilo CardioDaily e salva PNG via Playwright.

Uso:
    python scripts/gerar_imagens_lote.py              # todos elegíveis
    python scripts/gerar_imagens_lote.py --dry-run    # só lista
    python scripts/gerar_imagens_lote.py --limite 5   # máximo 5
    python scripts/gerar_imagens_lote.py --doc-id doi_XXXXX
    python scripts/gerar_imagens_lote.py --forcar     # regenera mesmo com imagem
"""

import argparse
import json
import os
import sys
import time
import requests
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "src"))

try:
    from dotenv import load_dotenv
    load_dotenv(_ROOT / ".env")
except ImportError:
    pass

# ─── Config ───────────────────────────────────────────────────────────────────
SUPABASE_URL  = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY  = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY", "")
OPENAI_KEY    = os.getenv("OPENAI_API_KEY", "")
IMG_DIR       = _ROOT / "outputs" / "imagens_lote"
BUCKET        = "visual_abstracts"
NOTA_MIN      = 7
DATA_DESDE    = "2026-02-01"
TIPOS_VALIDOS = ("original", "metanalise", "revisao", "meta_analise", "revisao_geral")

# ─── Supabase ─────────────────────────────────────────────────────────────────

def _sb_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }


def buscar_elegiveis(desde: str, limite: int, forcar: bool = False) -> list[dict]:
    params = {
        "select": "doc_id,titulo,tipo_estudo,nota_aplicabilidade,data_publicacao,doenca_principal",
        "nota_aplicabilidade": f"gte.{NOTA_MIN}",
        "data_publicacao": f"gte.{desde}",
        "order": "data_publicacao.desc",
        "limit": str(limite),
    }
    if not forcar:
        params["caminho_visual_abstract"] = "is.null"
    r = requests.get(f"{SUPABASE_URL}/rest/v1/artigos",
                     headers=_sb_headers(), params=params, timeout=30)
    if r.status_code != 200:
        print(f"❌ Supabase: {r.status_code} — {r.text[:200]}")
        return []
    artigos = r.json()
    return [a for a in artigos if (a.get("tipo_estudo") or "").lower() in TIPOS_VALIDOS]


def buscar_por_doc_id(doc_id: str) -> list[dict]:
    r = requests.get(f"{SUPABASE_URL}/rest/v1/artigos",
                     headers=_sb_headers(),
                     params={"select": "doc_id,titulo,tipo_estudo,nota_aplicabilidade,data_publicacao,doenca_principal",
                             "doc_id": f"eq.{doc_id}"},
                     timeout=15)
    return r.json() if r.status_code == 200 else []


def atualizar_caminho_imagem(doc_id: str, url: str) -> bool:
    r = requests.patch(
        f"{SUPABASE_URL}/rest/v1/artigos?doc_id=eq.{doc_id}",
        headers={**_sb_headers(), "Prefer": "return=minimal"},
        json={"caminho_visual_abstract": url},
        timeout=15,
    )
    return r.status_code in (200, 204)


def upload_png(doc_id: str, png_path: Path) -> str | None:
    objeto = f"{doc_id}.png"
    url_upload  = f"{SUPABASE_URL}/storage/v1/object/{BUCKET}/{objeto}"
    url_publica = f"{SUPABASE_URL}/storage/v1/object/public/{BUCKET}/{objeto}"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "image/png",
        "x-upsert": "true",
    }
    with open(png_path, "rb") as f:
        r = requests.post(url_upload, headers=headers, data=f, timeout=120)
    if r.status_code in (200, 201):
        return url_publica
    print(f"   ⚠️  Upload falhou: {r.status_code} — {r.text[:200]}")
    return None

# ─── Conteúdo textual ─────────────────────────────────────────────────────────

def buscar_abstract_pubmed(doi: str) -> str:
    try:
        query = urllib.parse.quote(f"{doi}[DOI]")
        url_s = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&term={query}&retmax=1&retmode=json"
        with urllib.request.urlopen(url_s, timeout=15) as resp:
            data = json.loads(resp.read())
        ids = data.get("esearchresult", {}).get("idlist", [])
        if not ids:
            return ""
        url_f = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&id={ids[0]}&rettype=abstract&retmode=xml"
        with urllib.request.urlopen(url_f, timeout=15) as resp:
            xml_data = resp.read()
        root = ET.fromstring(xml_data)
        title   = root.findtext(".//ArticleTitle") or ""
        texts   = [t.text or "" for t in root.findall(".//AbstractText")]
        abstract = "\n\n".join(texts)
        journal  = root.findtext(".//Title") or root.findtext(".//ISOAbbreviation") or ""
        year     = root.findtext(".//PubDate/Year") or ""
        return f"Título: {title}\nRevista: {journal} ({year})\nDOI: {doi}\n\nResumo:\n{abstract}"
    except Exception as e:
        print(f"   ⚠️  PubMed: {e}")
        return ""


def buscar_conteudo(doc_id: str) -> tuple[str, str]:
    """Retorna (conteudo, doi). Prioridade: script TTS → analysis.md → Supabase → PubMed."""
    # 1. Script TTS local
    sp = _ROOT / "outputs" / "audio_lote" / f"{doc_id}_script.txt"
    if sp.exists():
        print(f"   📖 Script TTS local: {sp.stat().st_size // 1024} KB")
        return sp.read_text(encoding="utf-8"), ""

    # 2. analysis.md local
    ap = _ROOT / "outputs" / "corpus" / doc_id / "analysis.md"
    if ap.exists():
        print(f"   📖 analysis.md local")
        return ap.read_text(encoding="utf-8"), ""

    # 3. Supabase
    r = requests.get(f"{SUPABASE_URL}/rest/v1/artigos",
                     headers=_sb_headers(),
                     params={"select": "resumo_markdown,doi", "doc_id": f"eq.{doc_id}"},
                     timeout=15)
    doi = ""
    if r.status_code == 200 and r.json():
        db = r.json()[0]
        doi = db.get("doi") or ""
        resumo = db.get("resumo_markdown") or ""
        if resumo and len(resumo) > 200:
            print(f"   📖 resumo_markdown Supabase")
            return resumo, doi

    # 4. PubMed
    if doi:
        print(f"   🔍 Abstract PubMed (DOI: {doi})…")
        txt = buscar_abstract_pubmed(doi)
        if txt:
            print(f"   📖 Abstract: {len(txt):,} chars")
            return txt, doi

    return "", doi

# ─── Extração estruturada via GPT-4o ──────────────────────────────────────────

PROMPT_EXTRACAO = """Você é o Dr. Eduardo Castro, cardiologista sênior. Sua missão é extrair aptidões para aplicabilidade prática imediata.
A partir do texto abaixo, retorne SOMENTE um JSON válido. TODOS os valores em PORTUGUÊS BRASILEIRO.

FOCO ABSOLUTO: o médico vai olhar este infográfico por 30 segundos. Cada campo tem que responder "o que faço com isso amanhã?".

{
  "titulo": "Título direto e impactante (max 12 palavras, sem rodeios)",
  "tagline": "O achado principal em uma frase — com número se possível (max 18 palavras)",
  "especialidade": "Subespecialidade cardiológica",
  "revista_ano": "Ex: JACC 2026",
  "pergunta_clinica": ["O que o estudo quis responder na prática clínica"],
  "metodos": ["Tipo de estudo e N de pacientes", "Seguimento", "Intervenção vs controle", "Desfecho primário com resultado e p-valor"],
  "populacao": ["Perfil do paciente incluído — idade, FE, classificação", "Comorbidades-chave", "Critério que define quem se beneficia"],
  "resultados": ["Resultado primário: [número relativo] e [número absoluto ou NNT]", "Resultado secundário relevante", "Achado de segurança ou efeito colateral"],
  "vieses": ["Limitação que restringe a aplicabilidade", "Outro ponto de atenção"],
  "pontos_fortes": ["Por que dá para confiar no resultado", "Representatividade da amostra", "Relevância do desfecho"],
  "pontos_fracos": ["Por que pode não se aplicar ao seu paciente", "Limitação prática"],
  "discussao": ["O que muda na prática a partir de agora", "Em quem NÃO aplicar", "Próximos passos na pesquisa"],
  "conclusao": ["Uma frase: o que fazer diferente na próxima consulta", "Impacto esperado no desfecho do paciente"],
  "o_que_usar": "Medicamento/estratégia/intervenção específica com dose se relevante (ex: dapagliflozina 10mg/dia)",
  "em_quem": "Perfil exato do paciente — FE, classe NYHA, escore, comorbidade que define a indicação",
  "o_que_paciente_ganha": "Benefício concreto em linguagem clínica (ex: redução de 22% em hospitalização por IC)",
  "cuidados": "Contraindicação ou condição que modifica a conduta",
  "perola": "UMA frase de ouro que o médico vai usar no ambulatório amanhã (max 18 palavras, começa com verbo)"
}

REGRAS:
- Listas: 2-4 itens, max 15 palavras cada
- perola DEVE começar com verbo de ação (ex: "Prescreva", "Inclua", "Considere", "Evite")
- o_que_usar DEVE ser específico — nome do fármaco/procedimento, não categoria genérica
- Sem markdown, asteriscos ou emojis no JSON
- Retorne APENAS o JSON
"""


def extrair_estrutura(conteudo: str, titulo: str, nota: int) -> dict | None:
    from openai import OpenAI
    client = OpenAI(api_key=OPENAI_KEY)

    mensagem = f"TÍTULO DO ARTIGO: {titulo}\nNOTA: {nota}/10\n\n---\n{conteudo[:6000]}"

    try:
        resp = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": PROMPT_EXTRACAO},
                {"role": "user",   "content": mensagem},
            ],
            temperature=0.3,
            max_tokens=2000,
            response_format={"type": "json_object"},
        )
        raw = resp.choices[0].message.content
        return json.loads(raw)
    except Exception as e:
        print(f"   ❌ GPT-4o: {e}")
        return None

# ─── HTML Template ────────────────────────────────────────────────────────────

def _ensure_list(v) -> list:
    """Garante que o valor é uma lista, mesmo se vier como string."""
    if isinstance(v, list):
        return v
    if isinstance(v, str) and v.strip():
        return [v]
    return []


def _li(itens) -> str:
    return "".join(f"<li>{_esc(i)}</li>" for i in _ensure_list(itens))


def _esc(t: str) -> str:
    import html
    return html.escape(str(t))


def montar_html(d: dict, nota: int) -> str:
    titulo   = _esc(d.get("titulo", ""))
    tagline  = _esc(d.get("tagline", ""))
    espec    = _esc(d.get("especialidade", ""))
    rev_ano  = _esc(d.get("revista_ano", ""))
    perola   = _esc(d.get("perola", ""))
    o_usar   = _esc(d.get("o_que_usar", ""))
    em_quem  = _esc(d.get("em_quem", ""))
    paciente = _esc(d.get("o_que_paciente_ganha", ""))
    cuidados = _esc(d.get("cuidados", ""))

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 11.5px;
    color: #1a1a1a;
    background: #fff;
    width: 900px;
    padding: 0;
  }}

  /* HEADER */
  .header {{
    background: #fff;
    padding: 20px 24px 14px 24px;
    border-bottom: 3px solid #e8e8e8;
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
  }}
  .header-left {{ flex: 1; padding-right: 20px; }}
  .header h1 {{
    font-size: 19px;
    font-weight: 700;
    color: #111;
    line-height: 1.25;
    margin-bottom: 6px;
  }}
  .header .tagline {{
    font-size: 11px;
    color: #555;
    line-height: 1.4;
  }}
  .logo-box {{
    display: flex;
    flex-direction: column;
    align-items: center;
    min-width: 80px;
  }}
  .logo-circle {{
    width: 48px; height: 48px;
    background: #c0392b;
    border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    margin-bottom: 4px;
  }}
  .logo-circle svg {{ width: 28px; height: 28px; fill: white; }}
  .logo-text {{ font-size: 9px; font-weight: 700; color: #c0392b; text-align: center; letter-spacing: 0.5px; }}
  .logo-sub  {{ font-size: 7px; color: #888; text-align: center; letter-spacing: 0.3px; }}

  /* BLUE BAND */
  .band {{
    background: #2c3e50;
    color: #fff;
    padding: 7px 24px;
    font-size: 10.5px;
    font-weight: 600;
    display: flex;
    gap: 20px;
    align-items: center;
  }}
  .band .sep {{ opacity: 0.4; }}

  /* BODY */
  .body {{ padding: 0 24px 0 24px; }}

  /* SECTIONS */
  .section {{ margin: 11px 0; }}
  .section-header {{
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 6px;
  }}
  .num {{
    width: 20px; height: 20px;
    background: #f39c12;
    border-radius: 4px;
    display: flex; align-items: center; justify-content: center;
    font-size: 10px; font-weight: 700; color: #fff;
    flex-shrink: 0;
  }}
  .section-title {{
    font-size: 10px;
    font-weight: 700;
    color: #333;
    text-transform: uppercase;
    letter-spacing: 0.6px;
  }}
  ul {{
    list-style: none;
    padding: 0;
    margin: 0;
  }}
  ul li {{
    padding: 2px 0 2px 12px;
    position: relative;
    font-size: 11px;
    line-height: 1.4;
    color: #222;
  }}
  ul li::before {{
    content: "•";
    position: absolute;
    left: 0;
    color: #c0392b;
    font-weight: 700;
  }}

  /* 2-COL */
  .two-col {{ display: flex; gap: 12px; }}
  .col {{ flex: 1; }}
  .col-title {{
    font-size: 9.5px;
    font-weight: 700;
    color: #555;
    text-transform: uppercase;
    letter-spacing: 0.4px;
    margin-bottom: 4px;
    padding-bottom: 2px;
    border-bottom: 1.5px solid #e0e0e0;
  }}

  /* 3-COL LIMITATIONS */
  .three-col {{ display: flex; gap: 8px; }}
  .lim-col {{
    flex: 1;
    padding: 8px;
    border-radius: 4px;
    font-size: 10.5px;
  }}
  .lim-col.vieses   {{ background: #fdf3e3; }}
  .lim-col.fortes   {{ background: #eafaf1; }}
  .lim-col.fracos   {{ background: #fef9e7; }}
  .lim-col .lim-title {{
    font-size: 9px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.4px;
    margin-bottom: 5px;
  }}
  .vieses  .lim-title {{ color: #e67e22; }}
  .fortes  .lim-title {{ color: #27ae60; }}
  .fracos  .lim-title {{ color: #d4a017; }}

  /* DIVIDER */
  .divider {{ border: none; border-top: 1px solid #ececec; margin: 8px 0; }}

  /* PÉROLA BANNER */
  .perola-banner {{
    background: #f5a623;
    color: #1a1a1a;
    padding: 10px 24px;
    font-size: 12px;
    font-weight: 700;
    text-align: center;
    font-style: italic;
    margin-top: 4px;
  }}

  /* APLICABILIDADE */
  .aplic-box {{
    background: #fafafa;
    border: 1px solid #e0e0e0;
    border-radius: 5px;
    padding: 10px 12px;
  }}
  .aplic-grid {{ display: flex; gap: 16px; }}
  .aplic-col {{ flex: 1; }}
  .aplic-label {{
    font-size: 8.5px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: #888;
    margin-bottom: 3px;
  }}
  .aplic-val {{
    font-size: 10.5px;
    color: #1a1a1a;
    line-height: 1.4;
    margin-bottom: 8px;
  }}

  /* FOOTER */
  .footer {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 8px 24px;
    border-top: 1px solid #e0e0e0;
    font-size: 9px;
    color: #888;
    margin-top: 2px;
  }}
  .nac-badge {{
    background: #c0392b;
    color: white;
    padding: 3px 10px;
    border-radius: 12px;
    font-size: 10px;
    font-weight: 700;
  }}
</style>
</head>
<body>

<!-- HEADER -->
<div class="header">
  <div class="header-left">
    <h1>{titulo}</h1>
    <p class="tagline">{tagline}</p>
  </div>
  <div class="logo-box">
    <div class="logo-circle">
      <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
        <path d="M12 21.593c-5.63-5.539-11-10.297-11-14.402
                 0-3.791 3.068-5.191 5.281-5.191 1.312 0 4.151.501 5.719 4.457
                 1.59-3.968 4.464-4.447 5.726-4.447 2.54 0 5.274 1.621 5.274 5.181
                 0 4.069-5.136 8.625-11 14.402z"/>
      </svg>
    </div>
    <div class="logo-text">CardioDaily</div>
    <div class="logo-sub">VISUAL ABSTRACT</div>
  </div>
</div>

<!-- BLUE BAND -->
<div class="band">
  <span>{espec}</span>
  <span class="sep">|</span>
  <span>{rev_ano}</span>
</div>

<div class="body">

  <!-- 1. PERGUNTA CLÍNICA -->
  <div class="section">
    <div class="section-header">
      <div class="num">1</div>
      <span class="section-title">Pergunta Clínica</span>
    </div>
    <ul>{_li(d.get("pergunta_clinica", []))}</ul>
  </div>

  <hr class="divider">

  <!-- 2+3. MÉTODOS + POPULAÇÃO -->
  <div class="section">
    <div class="section-header">
      <div class="num">2</div>
      <span class="section-title">Métodos &amp; População</span>
    </div>
    <div class="two-col">
      <div class="col">
        <div class="col-title">Métodos</div>
        <ul>{_li(d.get("metodos", []))}</ul>
      </div>
      <div class="col">
        <div class="col-title">População</div>
        <ul>{_li(d.get("populacao", []))}</ul>
      </div>
    </div>
  </div>

  <hr class="divider">

  <!-- 3. RESULTADOS -->
  <div class="section">
    <div class="section-header">
      <div class="num">3</div>
      <span class="section-title">Principais Resultados</span>
    </div>
    <ul>{_li(d.get("resultados", []))}</ul>
  </div>

  <hr class="divider">

  <!-- 4. LIMITAÇÕES -->
  <div class="section">
    <div class="section-header">
      <div class="num">4</div>
      <span class="section-title">Limitações do Estudo</span>
    </div>
    <div class="three-col">
      <div class="lim-col vieses">
        <div class="lim-title">Vieses</div>
        <ul>{_li(d.get("vieses", []))}</ul>
      </div>
      <div class="lim-col fortes">
        <div class="lim-title">Pontos Fortes</div>
        <ul>{_li(d.get("pontos_fortes", []))}</ul>
      </div>
      <div class="lim-col fracos">
        <div class="lim-title">Pontos Fracos</div>
        <ul>{_li(d.get("pontos_fracos", []))}</ul>
      </div>
    </div>
  </div>

  <hr class="divider">

  <!-- 5. DISCUSSÃO -->
  <div class="section">
    <div class="section-header">
      <div class="num">5</div>
      <span class="section-title">Discussão</span>
    </div>
    <ul>{_li(d.get("discussao", []))}</ul>
  </div>

  <hr class="divider">

  <!-- 6. CONCLUSÃO -->
  <div class="section">
    <div class="section-header">
      <div class="num">6</div>
      <span class="section-title">Conclusão</span>
    </div>
    <ul>{_li(d.get("conclusao", []))}</ul>
  </div>

  <hr class="divider">

  <!-- 7. APLICABILIDADE CLÍNICA -->
  <div class="section">
    <div class="section-header">
      <div class="num" style="background:#c0392b;">7</div>
      <span class="section-title">Aplicabilidade Clínica — Pérolas pro Ambulatório</span>
    </div>
    <div class="aplic-box">
      <div class="aplic-grid">
        <div class="aplic-col">
          <div class="aplic-label">O que usar</div>
          <div class="aplic-val">{o_usar}</div>
          <div class="aplic-label">O que o paciente ganha</div>
          <div class="aplic-val">{paciente}</div>
        </div>
        <div class="aplic-col">
          <div class="aplic-label">Em quem</div>
          <div class="aplic-val">{em_quem}</div>
          <div class="aplic-label">Cuidados</div>
          <div class="aplic-val">{cuidados}</div>
        </div>
      </div>
    </div>
  </div>

</div><!-- /body -->

<!-- PÉROLA BANNER -->
<div class="perola-banner">{perola}</div>

<!-- FOOTER -->
<div class="footer">
  <span>{rev_ano} · CardioDaily — Dados a fatos, sem firulas.</span>
  <span class="nac-badge">NAC {nota}/10</span>
</div>

</body>
</html>"""

# ─── Screenshot via Playwright ────────────────────────────────────────────────

def gerar_png(html: str, png_path: Path) -> bool:
    from playwright.sync_api import sync_playwright

    html_tmp = png_path.with_suffix(".html")
    png_path.parent.mkdir(parents=True, exist_ok=True)
    html_tmp.write_text(html, encoding="utf-8")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 900, "height": 1400})
        try:
            page.goto(f"file:///{html_tmp.as_posix()}", wait_until="networkidle", timeout=15000)
            # Altura real do conteúdo (sem espaço em branco)
            altura = page.evaluate("document.body.scrollHeight")
            page.set_viewport_size({"width": 900, "height": altura})
            page.screenshot(
                path=str(png_path),
                full_page=False,
                type="png",
            )
            html_tmp.unlink(missing_ok=True)
            size_kb = png_path.stat().st_size // 1024
            print(f"   ✅ PNG: {png_path.name} ({size_kb} KB)")
            return True
        except Exception as e:
            html_tmp.unlink(missing_ok=True)
            print(f"   ❌ Playwright: {e}")
            return False
        finally:
            browser.close()

# ─── Processador ──────────────────────────────────────────────────────────────

def processar_artigo(artigo: dict, dry_run: bool, forcar: bool = False) -> str:
    doc_id = artigo["doc_id"]
    titulo = artigo.get("titulo") or doc_id
    nota   = artigo.get("nota_aplicabilidade", 0)
    tipo   = artigo.get("tipo_estudo", "")
    data   = artigo.get("data_publicacao", "")

    print(f"\n{'─'*55}")
    print(f"📄 {doc_id}")
    print(f"   {titulo[:70]}{'...' if len(titulo) > 70 else ''}")
    print(f"   {tipo} | {nota}/10 | {data}")

    if dry_run:
        print("   [dry-run] — pulando")
        return "dry_run"

    png_path = IMG_DIR / f"{doc_id}.png"

    if forcar and png_path.exists():
        png_path.unlink()
        print("   🗑️  PNG removido (--forcar)")

    if not png_path.exists():
        # 1. Buscar conteúdo
        conteudo, _ = buscar_conteudo(doc_id)
        if not conteudo:
            print("   ⚠️  Sem conteúdo — pulando")
            return "sem_conteudo"

        # 2. Extrair estrutura via GPT-4o
        print("   🤖 Extraindo estrutura clínica (GPT-4o)…")
        estrutura = extrair_estrutura(conteudo, titulo, nota)
        if not estrutura:
            return "erro_gpt"

        # Garantir nota no dict
        estrutura["nota"] = nota

        # Salvar JSON para debug
        json_path = IMG_DIR / f"{doc_id}_estrutura.json"
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(estrutura, ensure_ascii=False, indent=2), encoding="utf-8")

        # 3. Montar HTML e gerar PNG
        print("   🖼️  Renderizando visual abstract…")
        html = montar_html(estrutura, nota)
        if not gerar_png(html, png_path):
            return "erro_png"
    else:
        print("   ♻️  PNG já existe — fazendo upload direto")

    # 4. Upload
    print(f"   ☁️  Upload para bucket '{BUCKET}'…")
    url = upload_png(doc_id, png_path)
    if not url:
        return "erro_upload"
    print(f"   ✅ {url}")

    # 5. Atualizar Supabase
    ok = atualizar_caminho_imagem(doc_id, url)
    print(f"   🗄️  caminho_visual_abstract {'atualizado' if ok else '⚠️  falhou'}")

    return "ok"

# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="CardioDaily — Visual Abstracts em Lote")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limite",  type=int, default=500)
    parser.add_argument("--desde",   type=str, default=DATA_DESDE)
    parser.add_argument("--doc-id",  type=str, default=None)
    parser.add_argument("--forcar",  action="store_true",
                        help="Regenera mesmo artigos que já têm imagem")
    args = parser.parse_args()

    if not SUPABASE_URL or not SUPABASE_KEY:
        print("❌ SUPABASE_URL / SUPABASE_SERVICE_KEY não configurados")
        sys.exit(1)
    if not OPENAI_KEY:
        print("❌ OPENAI_API_KEY não configurada")
        sys.exit(1)

    print(f"\n{'='*55}")
    print(f"🖼️  CardioDaily — Visual Abstracts em Lote")
    print(f"   📅 {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    if args.doc_id:
        print(f"   🎯 Artigo: {args.doc_id}")
    else:
        print(f"   📆 Desde: {args.desde} | Nota ≥ {NOTA_MIN} | Limite: {args.limite}")
    print(f"   {'[DRY-RUN]' if args.dry_run else 'MODO REAL — gerando PNGs'}")
    if args.forcar:
        print(f"   ⚠️  --forcar ativo")
    print(f"{'='*55}\n")

    if args.doc_id:
        artigos = buscar_por_doc_id(args.doc_id)
        if not artigos:
            print(f"❌ doc_id '{args.doc_id}' não encontrado")
            sys.exit(1)
    else:
        print("🔍 Buscando elegíveis no Supabase…")
        artigos = buscar_elegiveis(args.desde, args.limite, forcar=args.forcar)
        print(f"   {len(artigos)} artigos encontrados\n")

    if not artigos:
        print("✅ Nenhum artigo elegível sem imagem. Tudo em dia!")
        return

    print(f"{'#':>3}  {'doc_id':<30} {'tipo':<14} {'nota':>4}  data")
    print("─" * 65)
    for i, a in enumerate(artigos, 1):
        print(f"{i:>3}  {a['doc_id']:<30} {(a.get('tipo_estudo') or ''):<14} "
              f"{(a.get('nota_aplicabilidade') or 0):>4}  {a.get('data_publicacao','')}")

    if args.dry_run:
        print(f"\n✅ Dry-run: {len(artigos)} artigos seriam processados.")
        return

    print(f"\n{'='*55}")
    print(f"🚀 Gerando {len(artigos)} visual abstract(s)…")
    print(f"{'='*55}")

    stats = {"ok": 0, "sem_conteudo": 0, "erro_gpt": 0, "erro_png": 0, "erro_upload": 0}

    for i, artigo in enumerate(artigos, 1):
        print(f"\n[{i}/{len(artigos)}]")
        status = processar_artigo(artigo, dry_run=False, forcar=args.forcar)
        stats[status] = stats.get(status, 0) + 1
        if i < len(artigos):
            time.sleep(1)

    print(f"\n\n{'='*55}")
    print(f"✅ LOTE CONCLUÍDO")
    print(f"   ✅ Gerados com sucesso:  {stats['ok']}")
    print(f"   ⚠️  Sem conteúdo:        {stats.get('sem_conteudo', 0)}")
    print(f"   ❌ Erro GPT-4o:          {stats.get('erro_gpt', 0)}")
    print(f"   ❌ Erro PNG:             {stats.get('erro_png', 0)}")
    print(f"   ❌ Erro upload:          {stats.get('erro_upload', 0)}")
    print(f"{'='*55}\n")


if __name__ == "__main__":
    main()
