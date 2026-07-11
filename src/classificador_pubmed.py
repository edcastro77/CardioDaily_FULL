"""
classificador_pubmed.py — CLASSIFICADOR ENXUTO em CAMADAS (06/Jul/2026, branch lab/religar-prompts).
Troca a VISÃO do Gemini (o calcanhar de Aquiles) por uma cascata determinística e barata:

  CAMADA 1  PubMed "Publication Type" via DOI  → catálogo HUMANO da NLM (grátis, ~99% quando indexado).
  CAMADA 1b Europe PMC via DOI                 → indexa MAIS RÁPIDO que o PubMed, inclui preprints (grátis).
  CAMADA 2  Claude HAIKU lendo o TEXTO         → só o que as duas fontes grátis não cobrem (centavos, sem visão).
  CAMADA 3  REVISAO_HUMANA/                     → o que ficou ambíguo até pro Haiku (você decide).
  DESCARTE  relato de caso / técnica            → DESCARTADOS/ (quarentena, fora da análise, não apagado).

Motivo (evidência do backlog real): você baixa os papers fresquíssimos; MAIS DA METADE ainda não
está no PubMed. A rede de texto crua misclassificava (inflava GUIDELINES). O Haiku-no-texto conserta.

Saída (dentro da pasta de entrada):
  <ARTIGOS>/CLASSIFICADOS/<TIPO>/   (o analisador lê SÓ aqui)
  <ARTIGOS>/DESCARTADOS/            (relatos de caso/técnica)
  <ARTIGOS>/REVISAO_HUMANA/         (ambíguos)

Uso:  python src/classificador_pubmed.py <PASTA_ARTIGOS> [--dry-run] [--max N] [--sem-llm]
"""
import os
import re
import time
import shutil
import argparse
import unicodedata

from dotenv import load_dotenv
import requests

from pdf_extractor import PDFExtractor

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(_ROOT, ".env"), override=True)

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
EPMC = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
NCBI_API_KEY = os.getenv("NCBI_API_KEY", "")
NCBI_EMAIL = os.getenv("PUBMED_EMAIL") or os.getenv("ENTREZ_EMAIL", "")
ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY", "")
_DELAY = 0.12 if NCBI_API_KEY else 0.4
_llm_erro_mostrado = False  # mostra o 1º erro do LLM (nunca engole em silêncio)

_DOI_RE = re.compile(r"10\.\d{4,9}/[-._;()/:A-Za-z0-9]+")

FOLDERS = {
    "artigo_original": "ARTIGOS_ORIGINAIS",
    "revisao_sistematica_meta_analise": "META_ANALISES",
    "revisao_geral": "REVISOES",
    "guideline": "GUIDELINES",
    "ponto_de_vista": "EDITORIAIS",
}
SUB_ANALISE, SUB_DESCARTE, SUB_REVISAO = "CLASSIFICADOS", "DESCARTADOS", "REVISAO_HUMANA"
SUB_FILA = "FILA_ESPERA"   # ahead-of-print: espera o PubMed catalogar (re-check diário)

_PUBTYPE_PRIORITY = [
    ("guideline",                        {"Practice Guideline", "Guideline"}),
    ("revisao_sistematica_meta_analise", {"Meta-Analysis"}),  # só meta; revisão sistemática s/ meta = revisão
    ("ponto_de_vista",                   {"Editorial", "Comment"}),  # "Letter" agora é descarte
    ("artigo_original",                  {"Randomized Controlled Trial", "Clinical Trial",
                                          "Controlled Clinical Trial", "Comparative Study",
                                          "Observational Study", "Multicenter Study",
                                          "Equivalence Trial", "Pragmatic Clinical Trial",
                                          "Validation Study", "Clinical Trial, Phase III",
                                          "Clinical Trial, Phase II"}),
    ("revisao_geral",                    {"Review", "Systematic Review"}),
]
_CASO_RE = re.compile(
    r"\b(case report|case series|a case of|technique for|technique with|first[- ]in[- ]human|"
    r"how (we|i) do it|step[- ]by[- ]step)\b", re.I)
# cabeçalho de research letter (formato carta breve) → descarte (decisão do Dr. Eduardo)
_LETTER_RE = re.compile(r"\bresearch letter\b|^\s*letters?\b", re.I)
_NAO_DESCARTAR = {"Meta-Analysis", "Systematic Review", "Practice Guideline", "Guideline",
                  "Randomized Controlled Trial"}

# rótulos válidos que o Haiku pode devolver
_LLM_LABELS = set(FOLDERS) | {"relato_de_caso", "incerto"}


_DOI_VALID = set("-._;()/:")


def extrair_doi(texto):
    """Extrai o DOI tolerando QUEBRA DE LINHA no meio (PDF quebra 'j.card'⏎'fail...').
    Junta a continuação só se ela for DOI-like (minúscula/dígito); prosa começa em maiúscula."""
    if not texto:
        return None
    m = re.search(r"10\.\d{4,9}/", texto)
    if not m:
        return None
    n = len(texto)
    k = m.start()
    out = []
    while k < n:
        c = texto[k]
        if c in "\r\n":
            k2 = k
            while k2 < n and texto[k2] in "\r\n":
                k2 += 1
            prev = out[-1] if out else ""
            # Junta a quebra SÓ quando o DOI quebrou no MEIO de uma palavra
            # (Elsevier parte '10.1016/j.'⏎'cardfail...'): última char = letra ou '.'
            # E a próxima linha começa com letra minúscula. Assim NÃO gruda a linha
            # do ISSN/página que vem depois de um DOI já completo ('...001'⏎'0733-8651').
            if k2 < n and (prev.isalpha() or prev == ".") and texto[k2].islower():
                k = k2
                continue
            break
        if c.isalnum() or c in _DOI_VALID:
            out.append(c)
            k += 1
        else:
            break
    doi = "".join(out).rstrip(".")
    doi = re.sub(r"/\d{6,}$", "", doi)  # apara id de manuscrito espúrio (ex: Oxford .../oeag107/8724699)
    return doi or None


def _params(extra):
    p = {"tool": "CardioDaily", "email": NCBI_EMAIL}
    if NCBI_API_KEY:
        p["api_key"] = NCBI_API_KEY
    p.update(extra)
    return p


class RedeIndisponivel(Exception):
    """A consulta FALHOU de rede (429/5xx/timeout) após esgotar as tentativas.
    NÃO é 'não encontrado' — é 'não deu pra perguntar'. O chamador deve mandar
    o artigo pra fila de RETENTAR, NUNCA rebaixar pra troncho silencioso."""


def _http_get(url, params, tentativas=4):
    """GET com retry/backoff em 429/5xx/timeout/conexão.
    - Sucesso (2xx/3xx/4xx≠429) → devolve a resposta.
    - Falha transitória → espera (backoff) e tenta de novo.
    - Esgotou → levanta RedeIndisponivel (falha VISÍVEL, não engolida)."""
    ultimo = None
    for i in range(tentativas):
        try:
            r = requests.get(url, params=params, timeout=20)
            if r.status_code == 429 or r.status_code >= 500:
                ultimo = f"HTTP {r.status_code}"
                time.sleep(_DELAY * (2 ** i) + 0.5)   # 0.9, 1.3, 2.1, 3.7s...
                continue
            return r
        except requests.RequestException as e:
            ultimo = type(e).__name__
            time.sleep(_DELAY * (2 ** i) + 0.5)
    raise RedeIndisponivel(f"{url.split('/')[2]} indisponível após {tentativas} tentativas ({ultimo})")


def pubmed_lookup(doi):
    """Devolve (pubtypes, meta). ([], {}) = DOI não indexado (ok).
    Levanta RedeIndisponivel se a REDE falhar (para não virar troncho silencioso)."""
    if not doi:
        return [], {}
    time.sleep(_DELAY)
    r = _http_get(f"{EUTILS}/esearch.fcgi",
                  _params({"db": "pubmed", "term": f"{doi}[DOI]", "retmode": "json"}))
    ids = r.json().get("esearchresult", {}).get("idlist", []) if r.ok else []
    if not ids:
        return [], {}
    pmid = ids[0]
    time.sleep(_DELAY)
    r = _http_get(f"{EUTILS}/esummary.fcgi",
                  _params({"db": "pubmed", "id": pmid, "retmode": "json"}))
    res = r.json().get("result", {}).get(pmid, {}) if r.ok else {}
    return (res.get("pubtype", []) or []), {
        "title": res.get("title") or "",
        "journal": res.get("fulljournalname") or res.get("source") or "",
        "pubdate": res.get("pubdate") or res.get("epubdate") or "",
    }


def europepmc_lookup(doi):
    """Igual: ([], {}) = não achado; RedeIndisponivel = rede caiu."""
    if not doi:
        return [], {}
    r = _http_get(EPMC, {"query": f"DOI:{doi}", "format": "json",
                         "resultType": "core", "pageSize": 1})
    results = r.json().get("resultList", {}).get("result", []) if r.ok else []
    if not results:
        return [], {}
    res = results[0]
    ptl = (res.get("pubTypeList", {}) or {}).get("pubType", [])
    if isinstance(ptl, str):
        ptl = [ptl]
    journal = res.get("journalTitle") or \
        (res.get("journalInfo", {}) or {}).get("journal", {}).get("title", "")
    return ptl, {"title": res.get("title") or "",
                 "journal": journal,
                 "pubdate": res.get("firstPublicationDate") or ""}


def map_pubtype(pubtypes):
    s = set(pubtypes or [])
    for canon, gatilhos in _PUBTYPE_PRIORITY:
        if s & gatilhos:
            return canon
    return None


def eh_descartavel(pubtypes, titulo, texto):
    """Relato de caso/técnica OU research letter → descarte (fora da análise, quarentena)."""
    s = set(pubtypes or [])
    if "Case Reports" in s or "Letter" in s:
        return True
    if s & _NAO_DESCARTAR:
        return False
    titulo_l = (titulo or "").lower()
    cabecalho = (texto or "")[:400]
    if _CASO_RE.search(titulo_l) or _CASO_RE.search(cabecalho):
        return True          # relato de caso / técnica
    if _LETTER_RE.search(cabecalho):
        return True          # research letter
    return False


_LLM_PROMPT = """Classifique este artigo científico em UMA categoria. Responda SOMENTE com a palavra exata:
artigo_original | revisao_geral | revisao_sistematica_meta_analise | guideline | ponto_de_vista | relato_de_caso | carta_de_pesquisa | incerto

Definições:
- artigo_original: estudo com dados primários (RCT, coorte, caso-controle, observacional, transversal).
- revisao_geral: revisão narrativa OU revisão sistemática SEM meta-análise.
- revisao_sistematica_meta_analise: meta-análise (síntese quantitativa/pooled dos dados).
- guideline: diretriz, consenso, scientific statement de sociedade.
- ponto_de_vista: editorial, viewpoint, perspectiva, comentário.
- relato_de_caso: relato de caso único ou descrição de uma técnica/procedimento em paciente(s).
- carta_de_pesquisa: "research letter" / carta ao editor (formato breve), mesmo que contenha estudo ou meta.
- incerto: se não der para decidir com segurança.

TEXTO (início do artigo):
{texto}
"""


def classify_llm(texto):
    """Claude Haiku lendo o TEXTO. Devolve rótulo canônico, 'relato_de_caso', 'incerto' ou None.
    (Flash foi trocado por Haiku: a conta do Gemini estava sem créditos; a Anthropic é a que
    move o sistema.) Nunca engole erro: mostra o 1º que acontecer."""
    global _llm_erro_mostrado
    if not ANTHROPIC_KEY or not texto:
        return None
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=20,
            messages=[{"role": "user", "content": _LLM_PROMPT.format(texto=texto[:4000])}],
        )
        out = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text").strip().lower()
        for cat in ("revisao_sistematica_meta_analise", "artigo_original", "revisao_geral",
                    "guideline", "ponto_de_vista", "carta_de_pesquisa", "relato_de_caso"):
            if cat in out:
                return cat
        return "incerto"
    except Exception as e:
        if not _llm_erro_mostrado:
            print(f"   ⚠️ LLM (Haiku) falhou: {type(e).__name__} - {e}")
            _llm_erro_mostrado = True
        return None


def _slug(s, maxlen=60):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode()
    s = re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_")
    return s[:maxlen] or "SEM_TITULO"


def _novo_nome(meta, original):
    pd = meta.get("pubdate", "")
    ym = re.search(r"(\d{4})[-\s]*(\w{2,3})?", pd)
    ano = ym.group(1) if ym else "0000"
    meses = {"jan": "01", "feb": "02", "mar": "03", "apr": "04", "may": "05", "jun": "06",
             "jul": "07", "aug": "08", "sep": "09", "oct": "10", "nov": "11", "dec": "12",
             "01": "01", "02": "02", "03": "03", "04": "04", "05": "05", "06": "06",
             "07": "07", "08": "08", "09": "09", "10": "10", "11": "11", "12": "12"}
    mes = meses.get((ym.group(2) or "").lower(), "01") if ym else "01"
    titulo = meta.get("title", "")
    rev, tit = _slug(meta.get("journal", ""), 24), _slug(titulo, 80)
    # Revisões em partes ("... - Part 1" / "Part Two"): o diferenciador costuma cair FORA do corte.
    # Preserva o "Part N" pra o título ficar verídico E distinto (Cardiology/HF/Interv. Clinics).
    mp = re.search(r"\bpart\s+(\d+|one|two|three|four|five|[ivx]+)\b", titulo, re.I)
    if mp:
        parte = "Part_" + mp.group(1).capitalize()
        if parte.lower() not in tit.lower():
            tit = f"{tit}_{parte}"
    if rev == "SEM_TITULO" and tit == "SEM_TITULO":
        return original
    return f"{ano}-{mes}-{rev}-{tit}.pdf"


def classificar_pasta(pasta, dry_run=True, max_n=0, esperar_indexacao=True):
    extractor = PDFExtractor()
    pdfs = sorted(f for f in os.listdir(pasta)
                  if f.lower().endswith(".pdf") and not f.startswith("._"))
    if max_n:
        pdfs = pdfs[:max_n]

    print(f"\n{'DRY-RUN (nada é movido)' if dry_run else 'EXECUTANDO (move arquivos)'} — {len(pdfs)} PDF(s)\n")
    contagem = {}
    for i, nome in enumerate(pdfs, 1):
        caminho = os.path.join(pasta, nome)
        try:
            texto = extractor.extract_text(caminho)
        except Exception:
            texto = ""
        doi = extrair_doi(texto)

        # camada 1 e 1b (fontes autoritativas grátis)
        pubtypes, meta = pubmed_lookup(doi) if doi else ([], {})
        fonte = "PubMed"
        if not pubtypes and doi:
            pubtypes, meta = europepmc_lookup(doi)
            fonte = "EuropePMC"
        titulo = meta.get("title", "")

        if eh_descartavel(pubtypes, titulo, texto):
            destino, via, marca = "DESCARTE", f"descarte: caso/carta ({fonte} {pubtypes})", "⛔"
        else:
            tipo = map_pubtype(pubtypes) if pubtypes else None
            if tipo:
                destino, via, marca = tipo, f"{fonte} {pubtypes}", "✅"
            elif esperar_indexacao:
                # ahead-of-print: NÃO adivinha. Espera o PubMed catalogar (re-check diário).
                destino, via, marca = "FILA", "aguarda indexação no PubMed", "⏳"
            else:
                llm = classify_llm(texto)  # modo opcional (--com-haiku): adivinha em vez de esperar
                if llm in ("relato_de_caso", "carta_de_pesquisa"):
                    destino, via, marca = "DESCARTE", f"Haiku: {llm}", "⛔"
                elif llm in FOLDERS:
                    destino, via, marca = llm, "Haiku (texto)", "🟡"
                else:
                    destino, via, marca = "REVISAO", f"ambíguo (Haiku={llm})", "🔴"

        if destino == "DESCARTE":
            dest_dir = os.path.join(pasta, SUB_DESCARTE)
        elif destino == "REVISAO":
            dest_dir = os.path.join(pasta, SUB_REVISAO)
        elif destino == "FILA":
            dest_dir = os.path.join(pasta, SUB_FILA)
        else:
            dest_dir = os.path.join(pasta, SUB_ANALISE, FOLDERS[destino])
        rel = os.path.relpath(dest_dir, pasta)
        contagem[rel] = contagem.get(rel, 0) + 1

        print(f"[{i}/{len(pdfs)}] {marca} {nome[:56]}")
        print(f"        DOI: {doi or '(não achado)'} | via: {via}")
        print(f"        → {rel}/" + (f"  ({_novo_nome(meta, nome)})" if meta else ""))

        if not dry_run:
            os.makedirs(dest_dir, exist_ok=True)
            novo = _novo_nome(meta, nome) if meta else nome
            shutil.move(caminho, os.path.join(dest_dir, novo))

    print("\nResumo:", ", ".join(f"{k}={v}" for k, v in sorted(contagem.items())))
    if dry_run:
        print("(dry-run — nada foi movido. Rode sem --dry-run para valer.)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Classificador enxuto (PubMed→EuropePMC→Haiku→humano)")
    ap.add_argument("pasta", help="Pasta com os PDFs")
    ap.add_argument("--dry-run", action="store_true", help="Só mostra o que faria (não move)")
    ap.add_argument("--max", type=int, default=0, help="Processar no máximo N PDFs")
    ap.add_argument("--com-haiku", action="store_true",
                    help="Em vez de esperar a indexação, adivinha com Haiku (não recomendado)")
    args = ap.parse_args()
    classificar_pasta(os.path.expanduser(args.pasta), dry_run=args.dry_run,
                      max_n=args.max, esperar_indexacao=not args.com_haiku)
