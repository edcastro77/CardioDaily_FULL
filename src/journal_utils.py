"""
journal_utils.py — CASCA reconstruída (06/Jul/2026, branch lab/religar-prompts).
Reconstruído na HIERARQUIA AUTORITATIVA que o próprio sistema já usava (não no filename cru):
    1) CrossRef via DOI  → container-title  (fonte primária; a mesma que dá a data exata, ~99%)
    2) dica da análise    → campo 'revista' do JSON estruturado (extração do modelo)
    3) referência Vancouver no analysis.md → "Autores. Título. Revista. Ano;Vol..."
    4) nome do arquivo     → 3º segmento de YYYY-MM-Revista-Titulo (último recurso)
    5) NADA disso          → "DESCONHECIDA" (marca VISÍVEL p/ revisão humana — NUNCA "" calado)

Interface esperada por article_analyzer.py:
    extract_journal(pdf_filename=<nome>, doi=<doi>, revista_hint=<str>, md_text=<str>) -> str

NOTA de otimização (registrada, não agora): a consulta ao CrossRef aqui é uma chamada própria.
No futuro, buscar o CrossRef UMA vez por artigo (data + revista + título juntos) e reaproveitar,
para não repetir a chamada que a data já faz. Falha graciosa: se o CrossRef não responder, cai
para o próximo nível — nunca trava o pipeline (lei do interruptor de luz).
"""
import os
import re

import requests

JOURNAL_DESCONHECIDA = "DESCONHECIDA"  # sentinela VISÍVEL — nunca "" silencioso

# chave normalizada (minúscula, só letras/números) -> nome canônico da revista
JOURNAL_NORMALIZE = {
    "jacc": "JACC",
    "jacccardiooncology": "JACC: CardioOncology",
    "jacccardiovascularimaging": "JACC: Cardiovascular Imaging",
    "jacccardiovascularinterventions": "JACC: Cardiovascular Interventions",
    "jaccheartfailure": "JACC: Heart Failure",
    "circulation": "Circulation",
    "circ": "Circulation",
    "jama": "JAMA",
    "jamacardiology": "JAMA Cardiology",
    "nejm": "NEJM",
    "newenglandjournalofmedicine": "NEJM",
    "ehj": "European Heart Journal",
    "europeanheartjournal": "European Heart Journal",
    "eurheartj": "European Heart Journal",
    "lancet": "The Lancet",
    "thelancet": "The Lancet",
}


def _norm_key(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def _normalize(revista: str) -> str:
    revista = (revista or "").strip()
    if not revista:
        return ""
    return JOURNAL_NORMALIZE.get(_norm_key(revista), revista)


def journal_from_crossref(doi, timeout: int = 10):
    """Nome da revista pela fonte autoritativa (CrossRef via DOI). None se falhar/timeout."""
    if not doi:
        return None
    try:
        r = requests.get(
            f"https://api.crossref.org/works/{doi}",
            headers={"User-Agent": "CardioDaily/1.0 (mailto:edcastro77@gmail.com)"},
            timeout=timeout,
        )
        if r.status_code != 200:
            return None
        ct = (r.json().get("message", {}) or {}).get("container-title") or []
        return ct[0].strip() if ct else None
    except Exception:
        return None


def _journal_from_vancouver(md_text):
    """Extrai a revista da referência Vancouver do analysis.md. None se não achar."""
    if not md_text:
        return None
    m = re.search(r"\.\s+([A-Z][A-Za-z\s\(\)&/\-]+?)\.\s+(\d{4});\d+", md_text)
    return m.group(1).strip() if m else None


def _journal_from_filename(pdf_filename):
    """3º segmento de YYYY-MM-Revista-Titulo. None se o nome não seguir o padrão."""
    if not pdf_filename:
        return None
    partes = os.path.splitext(os.path.basename(pdf_filename))[0].split("-")
    if len(partes) < 3:
        return None
    revista = partes[2].strip()
    return revista or None


def extract_journal(pdf_filename=None, doi=None, revista_hint=None, md_text=None, **kwargs) -> str:
    """
    Revista pela hierarquia autoritativa. NUNCA devolve "" calado:
    se nada resolver, devolve 'DESCONHECIDA' (visível para a revisão humana / Golden Gate).
    """
    # 1) CrossRef via DOI (autoritativo)
    j = journal_from_crossref(doi)
    if j:
        return _normalize(j)
    # 2) dica da própria análise (campo 'revista' do JSON estruturado)
    if revista_hint:
        return _normalize(revista_hint)
    # 3) referência Vancouver no analysis.md
    j = _journal_from_vancouver(md_text)
    if j:
        return _normalize(j)
    # 4) nome do arquivo (último recurso)
    j = _journal_from_filename(pdf_filename)
    if j:
        return _normalize(j)
    # 5) nada resolveu → marca VISÍVEL, nunca "" calado
    return JOURNAL_DESCONHECIDA
