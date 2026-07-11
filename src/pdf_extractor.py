"""
pdf_extractor.py — CASCA reconstruída (06/Jul/2026, branch lab/religar-prompts).
Perdido com o Mac; é casca pura. Interface esperada por article_analyzer.py:
    PDFExtractor().extract_text(pdf_path) -> str

Motor: PyMuPDF (fitz) — leve, rápido, não trava (decisão do elo 2 EXTRAIR:
o "interruptor de luz" que aguenta diretriz de 140 páginas em segundos).
"""
import fitz  # PyMuPDF


class PDFExtractor:
    def __init__(self, min_chars: int = 500):
        # min_chars: referência do mínimo esperado de texto útil (a doc citou >500)
        self.min_chars = min_chars

    def extract_text(self, pdf_path: str) -> str:
        """Extrai todo o texto do PDF. Retorna string (pode ser vazia se o PDF for imagem)."""
        partes = []
        with fitz.open(pdf_path) as doc:
            for page in doc:
                partes.append(page.get_text())
        return "\n".join(partes).strip()
