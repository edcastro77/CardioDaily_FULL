#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CLASSIFICADOR DE ARTIGOS CIENTIFICOS - CardioDaily v8.0
========================================================
Classifica, renomeia e organiza PDFs de artigos cientificos.

ESTRATEGIA: GEMINI VISION como motor UNICO de classificacao.
  1. Renderiza primeira pagina do PDF como imagem (PyMuPDF)
  2. Envia imagem para Gemini 2.0 Flash Vision
  3. Gemini analisa headers, layout, badges visuais
  4. Extrai DOI + metadata (CrossRef) APENAS para renomear
  5. Renomeia: YYYY-MM-Revista-Titulo_Abreviado.pdf
  6. Move para pasta por tipo

POR QUE VISAO?
  - Todo artigo cientifico tem um HEADER VISUAL na primeira pagina:
    "ORIGINAL ARTICLE", "REVIEW", "EDITORIAL", "GUIDELINES", etc.
  - Isso e 10x mais confiavel que CrossRef (que retorna "journal-article" para tudo)
  - Gemini Flash le a imagem em ~1s com >95% de acerto

TIPOS DE ARTIGO (5 categorias):
    1. artigo_original      -> ARTIGOS_ORIGINAIS/
    2. revisao_sistematica_meta_analise -> META_ANALISES/
    3. revisao_geral        -> REVISOES/
    4. guideline            -> GUIDELINES/
    5. ponto_de_vista       -> EDITORIAIS/

USO:
    python3 classificador_artigos.py /caminho/para/pdfs
    python3 classificador_artigos.py /caminho/para/pdfs --dry-run
    python3 classificador_artigos.py /caminho/para/pdfs --dest-root /destino

Autor: Dr. Eduardo Castro - CardioDaily
Data: Fevereiro 2026
"""

import os
import sys
import re
import csv
import json
import shutil
import hashlib
import logging
import argparse
import unicodedata
import base64
import time
from datetime import datetime
from dataclasses import dataclass
from typing import Optional, Tuple
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

# Carregar variaveis de ambiente
from dotenv import load_dotenv
dotenv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '.env')
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path=dotenv_path, override=True)

# PyMuPDF para renderizar PDF como imagem
try:
    import fitz
    FITZ_AVAILABLE = True
except ImportError:
    FITZ_AVAILABLE = False
    print("ERRO FATAL: PyMuPDF nao encontrado. pip install PyMuPDF")
    sys.exit(1)

# Google GenAI para Gemini Vision
GENAI_AVAILABLE = False
try:
    from google import genai
    from google.genai import types
    GENAI_AVAILABLE = True
except ImportError:
    try:
        import google.generativeai as genai_old
        GENAI_AVAILABLE = True
    except ImportError:
        print("ERRO FATAL: Google GenAI nao encontrado. pip install google-genai")
        sys.exit(1)

VERSION = "8.0.0"
MAX_TITLE_WORDS = 8

# ============================================================================
# PROMPT DE CLASSIFICACAO VISUAL (core do sistema)
# ============================================================================

VISION_PROMPT = """You are an expert medical librarian. Look at this FIRST PAGE of a scientific PDF and extract BOTH the article type AND its bibliographic metadata.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STEP 1 — CLASSIFY THE ARTICLE TYPE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Choose ONE of 5 categories based on the header/badge/label visible on the page:

**ARTIGO_ORIGINAL** — Original research with Methods/Results/Discussion:
- Headers: "ORIGINAL RESEARCH", "ORIGINAL ARTICLE", "ORIGINAL INVESTIGATION", "CLINICAL TRIAL", "BRIEF REPORT", "RESEARCH ARTICLE", "CLINICAL RESEARCH"
- Words: "randomized", "cohort", "enrolled", "patients", "we studied"

**META_ANALISE** — Systematic review or meta-analysis:
- Headers: "META-ANALYSIS", "SYSTEMATIC REVIEW", "SYSTEMATIC REVIEW AND META-ANALYSIS", "POOLED ANALYSIS"
- PRISMA flow diagram, forest plots, "pooled estimate"

**REVISAO** — Narrative/general review (no systematic search):
- Headers: "REVIEW", "REVIEW ARTICLE", "STATE-OF-THE-ART REVIEW", "STATE OF THE ART", "NARRATIVE REVIEW", "CONTEMPORARY REVIEW", "COMPREHENSIVE REVIEW", "IN FOCUS", "COMPENDIUM", "UPDATE", "ADVANCES IN"

**GUIDELINE** — Clinical guidelines or consensus documents:
- Headers: "GUIDELINE", "GUIDELINES", "CONSENSUS", "SCIENTIFIC STATEMENT", "POSITION STATEMENT", "EXPERT CONSENSUS"
- Recommendation classes (I, IIa, IIb, III), from AHA/ACC/ESC/SBC

**EDITORIAL** — Short opinion pieces, editorials, letters, commentaries:
- Headers: "EDITORIAL", "COMMENTARY", "PERSPECTIVE", "VIEWPOINT", "LETTER", "CORRESPONDENCE", "OPINION"
- Short documents (1-4 pages), no original data

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STEP 2 — EXTRACT BIBLIOGRAPHIC METADATA
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Read the first page carefully and extract:

- **title**: The FULL article title exactly as printed (not the journal name). If the title spans multiple lines, join them. Max 200 chars.
- **journal**: Journal abbreviation or short name (e.g., "NEJM", "JAMA", "Lancet", "EHJ", "JACC", "Circulation"). Look for the journal header/logo at the top.
- **year**: Publication year (4 digits, e.g., "2026"). Look in the header, footer, or citation line.
- **month**: Publication month as 2-digit string (e.g., "03" for March). Look for date in header, "Published online", "Received/Accepted" dates, or volume/issue info. If truly not visible, use "".
- **doi**: DOI if visible on the page (e.g., "10.1056/NEJMoa2600123"). Otherwise "".

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RESPOND with ONLY a JSON object (no markdown, no backticks, no extra text):
{
  "type": "ARTIGO_ORIGINAL|META_ANALISE|REVISAO|GUIDELINE|EDITORIAL",
  "confidence": "HIGH|MEDIUM|LOW",
  "reason": "brief explanation of what header/badge you saw",
  "title": "Full article title as printed on first page",
  "journal": "Journal short name",
  "year": "2026",
  "month": "03",
  "doi": "10.xxxx/xxxxx or empty string"
}
"""

# ============================================================================
# MAPEAMENTOS
# ============================================================================

TYPE_MAP = {
    "ARTIGO_ORIGINAL": "artigo_original",
    "META_ANALISE": "revisao_sistematica_meta_analise",
    "REVISAO": "revisao_geral",
    "GUIDELINE": "guideline",
    "EDITORIAL": "ponto_de_vista",
}

CONFIDENCE_MAP = {
    "HIGH": 0.95,
    "MEDIUM": 0.80,
    "LOW": 0.60,
}

FOLDERS = {
    "artigo_original": "ARTIGOS_ORIGINAIS",
    "revisao_sistematica_meta_analise": "META_ANALISES",
    "revisao_geral": "REVISOES",
    "guideline": "GUIDELINES",
    "ponto_de_vista": "EDITORIAIS",
    "DUPLICADO": "DUPLICADOS",
    "UNK": "NAO_CLASSIFICADOS",
}

# ============================================================================
# DOI -> JOURNAL (fallback quando CrossRef nao retorna revista)
# ============================================================================

DOI_JOURNAL_HINTS = [
    (re.compile(r'^10\.1016/j\.jacc\.', re.I), 'JACC'),
    (re.compile(r'^10\.1016/j\.jchf\.', re.I), 'JHF'),
    (re.compile(r'^10\.1016/j\.jcmg\.', re.I), 'JACC_Cardiovasc_Imag'),
    (re.compile(r'^10\.1016/j\.jcin\.', re.I), 'JCI'),
    (re.compile(r'^10\.1016/j\.jacbts\.', re.I), 'JACC_BTS'),
    (re.compile(r'^10\.1016/j\.jacep\.', re.I), 'JACC_EP'),
    (re.compile(r'^10\.1016/j\.jaccas\.', re.I), 'JACC:_Asia'),
    (re.compile(r'^10\.1161/CIRCHEARTFAILURE\.', re.I), 'CircHF'),
    (re.compile(r'^10\.1161/CIRCIMAGING\.', re.I), 'CircImaging'),
    (re.compile(r'^10\.1161/CIRCINTERVENTIONS\.', re.I), 'CircInterv'),
    (re.compile(r'^10\.1161/CIRCEP\.', re.I), 'CircAE'),
    (re.compile(r'^10\.1161/CIRCGEN\.', re.I), 'CircGenomics'),
    (re.compile(r'^10\.1161/CIRCULATIONAHA\.', re.I), 'Circulation'),
    (re.compile(r'^10\.1161/CIRCULATION\.', re.I), 'Circulation'),
    (re.compile(r'^10\.1161/JAHA\.', re.I), 'JAHA'),
    (re.compile(r'^10\.1161/STROKEAHA\.', re.I), 'Stroke'),
    (re.compile(r'^10\.1161/HYPERTENSIONAHA\.', re.I), 'Hypertension'),
    (re.compile(r'^10\.1161/ATVBAHA\.', re.I), 'ATVB'),
    (re.compile(r'^10\.1161/CIR\.', re.I), 'Circulation'),
    (re.compile(r'^10\.1056/NEJM', re.I), 'NEJM'),
    (re.compile(r'^10\.1093/eurheartj/', re.I), 'EHJ'),
    (re.compile(r'^10\.1093/ehjci/', re.I), 'EHJ_CI'),
    (re.compile(r'^10\.1001/jamacardio', re.I), 'JAMA_Cardiology'),
    (re.compile(r'^10\.1001/jamaneurol', re.I), 'JAMA_Neurology'),
    (re.compile(r'^10\.1001/jama\.', re.I), 'JAMA'),
    (re.compile(r'^10\.1136/heartjnl', re.I), 'Heart'),
    (re.compile(r'^10\.1136/bmj', re.I), 'BMJ'),
    (re.compile(r'^10\.1161/CIRCRESAHA\.', re.I), 'Circulation_Research'),
    (re.compile(r'^10\.1016/j\.ahj\.', re.I), 'AHJ'),
    (re.compile(r'^10\.1002/ehf2\.', re.I), 'ESC_HF'),
    (re.compile(r'^10\.1093/cvr/', re.I), 'CVR'),
    (re.compile(r'^10\.1161/CIRCOUTCOMES\.', re.I), 'CPHO'),
]

# ============================================================================
# DATACLASS RESULTADO
# ============================================================================

@dataclass
class ClassificationResult:
    arquivo_original: str
    arquivo_novo: str
    tipo: str
    confianca: float
    doi: Optional[str]
    titulo: str
    revista: str
    ano: str
    mes: str
    pasta_destino: str
    motivo: str
    duplicado: bool = False
    motivo_duplicado: str = ""
    fonte_metadados: str = ""
    renomeado: bool = True

# ============================================================================
# FUNCOES UTILITARIAS
# ============================================================================

_SEEN_DOIS = {}
_SEEN_HASHES = {}

DOI_REGEX = [
    re.compile(r'(?:doi[:\s]*|DOI[:\s]*|https?://(?:dx\.)?doi\.org/)\s*(10\.\d{4,9}/[^\s"<>\]\)\n]+)', re.I),
    re.compile(r'doi\.org/(10\.\d{4,9}/[^\s"<>\]\)\n]+)', re.I),
    re.compile(r'\b(10\.\d{4,9}/[^\s"<>\]\)\n]{5,})', re.I),
]


def setup_logging(verbose: bool = False):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(levelname)s | %(message)s")


def compute_file_hash(filepath: str) -> str:
    h = hashlib.sha256()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            h.update(chunk)
    return h.hexdigest()[:16]


def extract_text(pdf_path: str, pages: int = 3) -> str:
    """Extrai texto do PDF (apenas para DOI, nao para classificacao)."""
    try:
        doc = fitz.open(pdf_path)
        text_parts = []
        for i, page in enumerate(doc):
            if i >= pages:
                break
            text_parts.append(page.get_text())
        doc.close()
        return "\n".join(text_parts)
    except Exception as e:
        logging.warning(f"PyMuPDF texto falhou: {e}")
        return ""


def pdf_page_to_png(pdf_path: str, page_num: int = 0, dpi: int = 200) -> Optional[bytes]:
    """Renderiza uma pagina do PDF como imagem PNG."""
    try:
        doc = fitz.open(pdf_path)
        if page_num >= len(doc):
            doc.close()
            return None
        page = doc[page_num]
        zoom = dpi / 72.0
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)
        img_bytes = pix.tobytes("png")
        doc.close()
        return img_bytes
    except Exception as e:
        logging.warning(f"Render PDF falhou: {e}")
        return None


def find_doi(text: str) -> Optional[str]:
    """Encontra DOI no texto."""
    for pattern in DOI_REGEX:
        m = pattern.search(text)
        if m:
            doi = m.group(1).rstrip('.,;:)')
            doi = re.sub(r'[\x00-\x1f\x7f]', '', doi)
            if len(doi) > 10:
                return doi
    return None


def infer_journal_from_doi(doi: str) -> str:
    """Infere revista a partir do DOI."""
    for pattern, journal in DOI_JOURNAL_HINTS:
        if pattern.search(doi):
            return journal
    return ""


def crossref_get(doi: str) -> Optional[dict]:
    """Consulta CrossRef API para metadata (titulo, revista, data)."""
    try:
        url = f"https://api.crossref.org/works/{doi}"
        req = Request(url, headers={"User-Agent": "CardioDaily/8.0 (mailto:edcastro77@gmail.com)"})
        with urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            return data.get("message", {})
    except Exception:
        return None


def get_metadata_from_crossref(meta: dict) -> dict:
    """Extrai titulo, revista, ano, mes do CrossRef."""
    title = ""
    titles = meta.get("title", [])
    if titles:
        title = titles[0]

    journal = ""
    container = meta.get("container-title", [])
    if container:
        journal = container[0]
    elif meta.get("short-container-title"):
        journal = meta["short-container-title"][0]

    year, month = "", ""
    for key in ["published-print", "published-online", "created"]:
        date_parts = meta.get(key, {}).get("date-parts", [[]])
        if date_parts and date_parts[0]:
            parts = date_parts[0]
            year = str(parts[0]) if len(parts) > 0 else ""
            month = f"{parts[1]:02d}" if len(parts) > 1 else "01"
            break

    return {"title": title, "journal": journal, "year": year, "month": month}


def sanitize_filename(s: str) -> str:
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode('ascii')
    s = re.sub(r'[^\w\s\-]', '', s)
    s = re.sub(r'\s+', '_', s.strip())
    return s[:80]


def abbreviate_journal(name: str) -> str:
    if not name:
        return "Unknown"
    remove = {'the', 'of', 'and', 'in', 'for', 'a', 'an', 'on'}
    words = [w for w in name.split() if w.lower() not in remove]
    if len(words) <= 2:
        return "_".join(words)
    return "".join(w[0].upper() for w in words[:5])


def abbreviate_title(title: str, max_words: int = MAX_TITLE_WORDS) -> str:
    if not title:
        return "Untitled"
    words = re.findall(r'\b[A-Za-z0-9]+\b', title)
    return "_".join(w.capitalize() for w in words[:max_words])


def compose_filename(year: str, month: str, journal: str, title: str) -> str:
    y = year or str(datetime.now().year)
    m = month or "01"
    j = abbreviate_journal(journal)
    t = abbreviate_title(title)
    return f"{y}-{m}-{j}-{t}.pdf"


def check_duplicate(doi: str, file_hash: str) -> Tuple[bool, str]:
    if doi and doi in _SEEN_DOIS:
        return True, f"DOI duplicado: {doi}"
    if file_hash in _SEEN_HASHES:
        return True, f"Hash duplicado: {file_hash}"
    return False, ""


def register_article(doi: str, file_hash: str):
    if doi:
        _SEEN_DOIS[doi] = True
    _SEEN_HASHES[file_hash] = True


def ensure_dirs(root: str):
    for folder in FOLDERS.values():
        os.makedirs(os.path.join(root, folder), exist_ok=True)


def unique_path(path: str) -> str:
    if not os.path.exists(path):
        return path
    base, ext = os.path.splitext(path)
    for i in range(1, 100):
        candidate = f"{base}({i}){ext}"
        if not os.path.exists(candidate):
            return candidate
    return path


# ============================================================================
# GEMINI VISION — MOTOR DE CLASSIFICACAO
# ============================================================================

class GeminiVisionClassifier:
    """Classifica artigos enviando imagem da primeira pagina ao Gemini."""

    def __init__(self, api_key: str = None, model: str = "gemini-2.0-flash",
                 verbose: bool = False, call_interval: float = 4.0):
        self.api_key = api_key or os.environ.get('GOOGLE_API_KEY') or os.environ.get('GEMINI_API_KEY')
        self.model = model
        self.verbose = verbose
        self.call_interval = call_interval  # segundos entre chamadas
        self._use_new_api = False

        if not self.api_key:
            raise ValueError("GOOGLE_API_KEY nao encontrada no .env")

        # Detectar qual API usar
        try:
            from google.genai import types as _t
            self._use_new_api = True
        except ImportError:
            pass

        # Inicializar cliente (nova API)
        if self._use_new_api:
            self._client = genai.Client(api_key=self.api_key)
        else:
            genai_old.configure(api_key=self.api_key)

        self._call_count = 0

    def classify(self, pdf_path: str) -> Tuple[str, float, str, dict]:
        """
        Classifica um PDF pela primeira pagina e extrai metadata bibliografica.

        Returns:
            (tipo, confianca, motivo, meta_visao)
            tipo: artigo_original | revisao_sistematica_meta_analise | revisao_geral | guideline | ponto_de_vista
            meta_visao: {"title": str, "journal": str, "year": str, "month": str, "doi": str}
        """
        empty_meta = {"title": "", "journal": "", "year": "", "month": "", "doi": ""}

        # 1. Renderizar pagina 1 como PNG
        img_bytes = pdf_page_to_png(pdf_path, page_num=0, dpi=200)
        if not img_bytes:
            logging.warning(f"Falha ao renderizar: {os.path.basename(pdf_path)}")
            return ("artigo_original", 0.30, "ERRO: falha ao renderizar PDF", empty_meta)

        if self.verbose:
            logging.debug(f"  Imagem: {len(img_bytes)/1024:.0f} KB")

        # 2. Rate limit simples
        self._call_count += 1
        if self._call_count > 1:
            time.sleep(self.call_interval)

        # 3. Chamar Gemini Vision com backoff exponencial
        esperas = [30, 60, 120]
        last_err = None
        for tentativa, espera in enumerate([0] + esperas):
            if espera:
                logging.info(f"  Aguardando {espera}s (rate limit, tentativa {tentativa+1}/4)...")
                time.sleep(espera)
            try:
                if self._use_new_api:
                    result = self._call_new_api(img_bytes)
                else:
                    result = self._call_old_api(img_bytes)
                return result
            except Exception as e:
                err_msg = str(e)
                last_err = err_msg
                if "429" in err_msg or "quota" in err_msg.lower() or "RESOURCE_EXHAUSTED" in err_msg:
                    logging.warning(f"  Rate limit: {err_msg[:80]}")
                    continue
                # Erro não relacionado a rate limit — falhar imediatamente
                logging.error(f"  Gemini Vision erro: {err_msg}")
                return ("artigo_original", 0.30, f"ERRO Gemini: {err_msg}", empty_meta)

        logging.error(f"  Todas as tentativas falharam: {last_err[:80]}")
        return ("artigo_original", 0.30, f"ERRO após retries: {last_err[:60]}", empty_meta)

    def _call_new_api(self, img_bytes: bytes) -> Tuple[str, float, str, dict]:
        """Chama Gemini via nova API (google-genai)."""
        from google.genai import types

        contents = [
            types.Content(
                role="user",
                parts=[
                    types.Part.from_bytes(data=img_bytes, mime_type="image/png"),
                    types.Part.from_text(text=VISION_PROMPT),
                ]
            )
        ]

        response = self._client.models.generate_content(
            model=self.model,
            contents=contents,
            config=types.GenerateContentConfig(
                temperature=0.1,
                max_output_tokens=500,
            )
        )

        return self._parse_response(response.text)

    def _call_old_api(self, img_bytes: bytes) -> Tuple[str, float, str, dict]:
        """Chama Gemini via API antiga (google-generativeai)."""
        from PIL import Image
        import io

        model = genai_old.GenerativeModel(self.model)
        img = Image.open(io.BytesIO(img_bytes))

        response = model.generate_content(
            [VISION_PROMPT, img],
            generation_config=genai_old.types.GenerationConfig(
                temperature=0.1,
                max_output_tokens=500,
            )
        )

        return self._parse_response(response.text)

    def _parse_response(self, text: str) -> Tuple[str, float, str, dict]:
        """Parseia resposta JSON do Gemini. Retorna (tipo, conf, reason, meta_visao)."""
        text = text.strip()
        text = re.sub(r'^```(?:json)?\s*', '', text)
        text = re.sub(r'\s*```$', '', text)

        empty_meta = {"title": "", "journal": "", "year": "", "month": "", "doi": ""}

        try:
            data = json.loads(text)
            raw_type = data.get("type", "").upper().strip()
            raw_conf = data.get("confidence", "MEDIUM").upper().strip()
            reason = data.get("reason", "classificacao visual")

            tipo = TYPE_MAP.get(raw_type, None)
            if tipo is None:
                for key, val in TYPE_MAP.items():
                    if key in raw_type:
                        tipo = val
                        break
                if tipo is None:
                    logging.warning(f"  Tipo desconhecido: {raw_type}")
                    tipo = "artigo_original"
                    raw_conf = "LOW"

            conf = CONFIDENCE_MAP.get(raw_conf, 0.70)

            # Extrair metadata da visao
            meta_visao = {
                "title": (data.get("title") or "").strip(),
                "journal": (data.get("journal") or "").strip(),
                "year": (data.get("year") or "").strip(),
                "month": (data.get("month") or "").strip().zfill(2) if data.get("month") else "",
                "doi": (data.get("doi") or "").strip(),
            }
            return (tipo, conf, reason, meta_visao)

        except json.JSONDecodeError:
            text_upper = text.upper()
            for key, val in TYPE_MAP.items():
                if key in text_upper:
                    return (val, 0.70, f"Extraido de: {text[:100]}", empty_meta)

            logging.warning(f"  Parse falhou: {text[:150]}")
            return ("artigo_original", 0.30, f"PARSE FALHOU: {text[:80]}", empty_meta)


# ============================================================================
# PROCESSAMENTO PRINCIPAL
# ============================================================================

def process_pdf(
    root: str,
    filename: str,
    vision: GeminiVisionClassifier,
    dry_run: bool = False,
    no_rename: bool = False,
    dest_root: Optional[str] = None,
) -> ClassificationResult:
    """Processa um PDF: classifica (visao), extrai metadata, move."""

    pdf_path = os.path.join(root, filename)
    out_root = dest_root or root
    logging.info(f"Processando: {filename}")

    file_hash = compute_file_hash(pdf_path)

    # --- Extrair texto APENAS para DOI (nao para classificacao) ---
    text = extract_text(pdf_path, pages=3)

    # --- Extrair metadata via DOI/CrossRef ---
    year, month, journal, title = "", "", "", ""
    doi = find_doi(text)
    fonte = "nenhuma"
    renomeado = False

    if doi:
        meta = crossref_get(doi)
        if meta:
            md = get_metadata_from_crossref(meta)
            if md["title"] and len(md["title"]) > 10:
                title = md["title"]
                journal = md["journal"]
                year = md["year"]
                month = md["month"]
                fonte = "crossref"
                renomeado = True

        if not journal:
            journal = infer_journal_from_doi(doi)
            if journal and fonte == "nenhuma":
                fonte = "doi_inferido"

    if not title:
        title = re.sub(r'\.pdf$', '', filename, flags=re.I)
        renomeado = False

    if not year:
        year = str(datetime.now().year)
    if not month:
        month = "01"

    # --- CLASSIFICAR via Gemini Vision (também extrai metadata) ---
    # Fazemos isso ANTES da verificação de duplicata para ter meta_visao disponível
    article_type, confidence, motivo, meta_visao = vision.classify(pdf_path)

    # --- Usar metadata da visão como fallback quando CrossRef falhou ---
    if meta_visao.get("title") and len(meta_visao["title"].split()) >= 3:
        # Se CrossRef não trouxe título OU trouxe o nome da revista como título
        titulo_crossref_e_revista = journal and title.lower().strip() == journal.lower().strip()
        titulo_parece_filename = not renomeado and (
            re.search(r'\d{10,}', title) or  # hash numérico no nome
            title.lower() == re.sub(r'\.pdf$', '', filename, flags=re.I).lower()
        )
        if not title or len(title.split()) < 3 or titulo_crossref_e_revista or titulo_parece_filename:
            logging.info(f"  Título via Gemini Vision: {meta_visao['title'][:70]}")
            title = meta_visao["title"]
            renomeado = True
            if not journal and meta_visao.get("journal"):
                journal = meta_visao["journal"]
                fonte = "visao_gemini"
            if meta_visao.get("year") and (not year or year == str(datetime.now().year)):
                year = meta_visao["year"]
            if meta_visao.get("month") and month == "01":
                month = meta_visao["month"]
            if not doi and meta_visao.get("doi"):
                doi = meta_visao["doi"]
    elif meta_visao.get("journal") and not journal:
        journal = meta_visao["journal"]
    if meta_visao.get("year") and month == "01" and meta_visao.get("month"):
        month = meta_visao["month"]

    # --- Verificar duplicata ---
    is_dup, dup_reason = check_duplicate(doi, file_hash)
    if is_dup:
        logging.warning(f"  DUPLICATA: {dup_reason}")
        result = ClassificationResult(
            arquivo_original=filename, arquivo_novo=filename,
            tipo="DUPLICADO", confianca=1.0, doi=doi,
            titulo=title[:80], revista=journal, ano=year, mes=month,
            pasta_destino=FOLDERS["DUPLICADO"], motivo=dup_reason,
            duplicado=True, motivo_duplicado=dup_reason,
            fonte_metadados=fonte, renomeado=False,
        )
        if not dry_run:
            target = os.path.join(out_root, FOLDERS["DUPLICADO"], filename)
            if os.path.abspath(target) != os.path.abspath(pdf_path):
                dest = unique_path(target)
                shutil.move(pdf_path, dest)
                result.arquivo_novo = os.path.basename(dest)
        return result

    register_article(doi, file_hash)

    # Nome do arquivo (article_type/confidence/motivo já extraídos acima com meta_visao)
    if no_rename or not renomeado:
        new_filename = filename
        renomeado = False
    else:
        new_filename = compose_filename(year, month, journal, title)

    dest_folder = FOLDERS.get(article_type, FOLDERS["UNK"])

    result = ClassificationResult(
        arquivo_original=filename, arquivo_novo=new_filename,
        tipo=article_type, confianca=confidence, doi=doi,
        titulo=title[:80], revista=journal, ano=year, mes=month,
        pasta_destino=dest_folder, motivo=motivo,
        fonte_metadados=fonte, renomeado=renomeado,
    )

    icon = "V" if renomeado else "o"
    logging.info(f"  [{article_type}] {icon} ({confidence:.0%}) -> {new_filename[:60]}")

    if not dry_run:
        target = os.path.join(out_root, dest_folder, new_filename)
        if os.path.abspath(target) != os.path.abspath(pdf_path):
            dest = unique_path(target)
            shutil.move(pdf_path, dest)
            result.arquivo_novo = os.path.basename(dest)

    return result


# ============================================================================
# RELATORIO
# ============================================================================

def generate_report(results: list, root: str):
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = os.path.join(root, f"classificacao_{ts}.csv")

    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(["original", "novo", "tipo", "confianca", "doi",
                         "titulo", "revista", "motivo"])
        for r in results:
            writer.writerow([
                r.arquivo_original, r.arquivo_novo, r.tipo,
                f"{r.confianca:.0%}", r.doi or "",
                r.titulo, r.revista, r.motivo[:100],
            ])

    print(f"\n📋 CSV: {csv_path}")
    return csv_path


# ============================================================================
# MAIN
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description=f"CardioDaily Classificador v{VERSION} (Gemini Vision)")
    parser.add_argument("entrada", nargs="*", default=["."], help="Pasta(s) com PDFs")
    parser.add_argument("--dry-run", action="store_true", help="Apenas simular")
    parser.add_argument("--no-rename", action="store_true", help="Nao renomear arquivos")
    parser.add_argument("--dest-root", help="Pasta de destino")
    parser.add_argument("--model", default="gemini-2.0-flash", help="Modelo Gemini (default: gemini-2.0-flash)")
    parser.add_argument("--intervalo", type=float, default=4.0, metavar="S",
                        help="Segundos entre chamadas Gemini (default: 4 — limite free tier 15 RPM)")
    parser.add_argument("--lote", type=int, default=0, metavar="N",
                        help="Processar N PDFs por vez com pausa de 60s entre lotes (0 = sem lotes)")
    parser.add_argument("--max", type=int, default=0, metavar="N",
                        help="Parar após N PDFs classificados (0 = sem limite). Use 200 no free tier para não esgotar quota.")
    parser.add_argument("-v", "--verbose", action="store_true", help="Log detalhado")
    args = parser.parse_args()

    setup_logging(args.verbose)

    print(f"\n{'='*60}")
    print(f"  CARDIODAILY CLASSIFICADOR v{VERSION}")
    print(f"  Motor: GEMINI VISION (primeira pagina)")
    print(f"  Modelo: {args.model}")
    print(f"{'='*60}\n")

    # Inicializar classificador visual
    vision = GeminiVisionClassifier(
        model=args.model,
        verbose=args.verbose,
        call_interval=args.intervalo,
    )
    print(f"  Gemini Vision OK ({args.model})\n")

    entradas = [os.path.abspath(p) for p in args.entrada]
    out_root = os.path.abspath(args.dest_root) if args.dest_root else None

    if args.dry_run:
        print("*** MODO DRY-RUN (simulacao) ***\n")

    results = []

    for path in entradas:
        if not os.path.exists(path):
            logging.error(f"Nao encontrado: {path}")
            continue

        if os.path.isdir(path):
            pdfs = sorted(f for f in os.listdir(path) if f.lower().endswith('.pdf') and not f.startswith('._'))
            print(f"📁 Pasta: {path}")
            print(f"📄 PDFs encontrados: {len(pdfs)}")

            if not pdfs:
                continue

            # ── PREFLIGHT CHECK ───────────────────────────────────────────
            LIMITE_DIARIO_FREE = 200   # estimativa segura para free tier
            total_rodar = min(len(pdfs), args.max) if args.max > 0 else len(pdfs)
            tempo_min = total_rodar * args.intervalo / 60
            print(f"⏱️  PDFs na fila: {len(pdfs)}  |  Serão processados: {total_rodar}  |  Tempo: ~{tempo_min:.0f} min")
            if args.max == 0 and len(pdfs) > LIMITE_DIARIO_FREE:
                print(f"\n⚠️  AVISO: {len(pdfs)} PDFs pode esgotar a quota diária do Gemini free tier.")
                print(f"   Recomendado: use --max 200 para processar 200/dia em segurança.")
                if args.lote == 0:
                    print(f"   Sugestão adicional: --lote 40 para pausas entre grupos.")
            elif args.max > 0:
                print(f"   Modo quota-safe: para após {args.max} PDFs.")
            print()
            # ─────────────────────────────────────────────────────────────

            effective_root = out_root or path
            if not args.dry_run:
                ensure_dirs(effective_root)

            lote_tamanho = args.lote if args.lote > 0 else len(pdfs)
            classificados_hoje = 0
            for i, f in enumerate(pdfs, 1):
                # Limite diário --max
                if args.max > 0 and classificados_hoje >= args.max:
                    restantes = len(pdfs) - i + 1
                    print(f"\n\n🛑 Limite diário de {args.max} PDFs atingido. {restantes} PDFs aguardam amanhã.")
                    print(f"   Execute novamente após 04h00 (reset da quota Gemini free tier).")
                    break

                print(f"\n[{i}/{len(pdfs)}] ", end="", flush=True)
                try:
                    r = process_pdf(path, f, vision, args.dry_run, args.no_rename, out_root)
                    results.append(r)
                    classificados_hoje += 1
                except Exception as e:
                    logging.error(f"Erro em {f}: {e}")

                # Pausa entre lotes
                if args.lote > 0 and i % lote_tamanho == 0 and i < len(pdfs):
                    print(f"\n\n⏸️  Lote {i // lote_tamanho} concluído. Pausando 60s para respeitar quota Gemini...")
                    time.sleep(60)
                    print("▶️  Retomando...\n")
        else:
            root_dir = os.path.dirname(path) or "."
            effective_root = out_root or root_dir
            if not args.dry_run:
                ensure_dirs(effective_root)
            try:
                r = process_pdf(root_dir, os.path.basename(path), vision, args.dry_run, args.no_rename, out_root)
                results.append(r)
            except Exception as e:
                logging.error(f"Erro: {e}")

    # Sumario
    if results:
        print(f"\n{'='*60}")
        print(f"  RESULTADO (Gemini Vision v{VERSION})")
        print(f"{'='*60}")

        counts = {}
        for r in results:
            counts[r.tipo] = counts.get(r.tipo, 0) + 1

        total = len(results)
        for tipo, count in sorted(counts.items(), key=lambda x: -x[1]):
            folder = FOLDERS.get(tipo, "?")
            pct = count / total * 100
            print(f"  {folder:<25} {count:>3} ({pct:.0f}%)")

        print(f"  {'─'*40}")
        print(f"  {'TOTAL':<25} {total:>3}")

        if not args.dry_run:
            generate_report(results, out_root or os.path.dirname(entradas[0]))

    if args.dry_run and results:
        print(f"\n{'='*60}")
        print(f"  PREVIA (dry-run)")
        print(f"{'='*60}")
        for r in results:
            icon = "👁️" if r.confianca >= 0.80 else "⚠️"
            print(f"  {icon} [{r.tipo:40}] {r.arquivo_original[:50]}")
            if r.motivo:
                print(f"      Motivo: {r.motivo[:80]}")


if __name__ == "__main__":
    main()
