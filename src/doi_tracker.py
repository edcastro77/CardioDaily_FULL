"""
doi_tracker.py — CASCA reconstruída (06/Jul/2026, branch lab/religar-prompts).
Perdido com o Mac. A doc marcou este módulo como 'meio-termo' (casca + alma na dedup):
esta reconstrução é a casca FIEL ao uso; a dedup por DOI pode ter casos-limite a refinar
depois. Sob o Golden Gate, a revisão humana pega qualquer escape antes de subir.

Interface esperada por article_analyzer.py:
    DOITracker(database_path=..., html_path=...)
    .extract_doi_from_pdf(pdf_path) -> str | None
    .is_analyzed(doi) -> bool
    .get_article(doi) -> dict | None
    .add_article(doi=, filename=, article_type=, score=, summary_path=, audio_path=, image_path=, **extra)
    .get_statistics() -> {'total','high_score','with_audio','with_image','scores'}
    .html_path  (atributo)

O "banco" é um JSON simples (database_path), indexado por DOI. Sob CARDIODAILY_SKIP_DB_WRITE=1
o analisador nem chama add_article — então no laboratório nada é gravado no histórico.
"""
import os
import re
import json

import fitz  # PyMuPDF

# DOI: 10.<registrante>/<sufixo>. Para na primeira quebra de espaço.
_DOI_RE = re.compile(r"10\.\d{4,9}/[-._;()/:A-Za-z0-9]+")


class DOITracker:
    def __init__(self, database_path="data/analyzed_articles.json",
                 html_path="data/analyzed_articles.html"):
        self.database_path = database_path
        self.html_path = html_path
        self._db = self._load()

    # ---------- persistência ----------
    def _load(self) -> dict:
        try:
            with open(self.database_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}
        if isinstance(data, dict):
            return data
        if isinstance(data, list):  # tolera formato antigo (lista de registros)
            return {a.get("doi"): a for a in data if isinstance(a, dict) and a.get("doi")}
        return {}

    def _save(self) -> None:
        d = os.path.dirname(self.database_path)
        if d:
            os.makedirs(d, exist_ok=True)
        with open(self.database_path, "w", encoding="utf-8") as f:
            json.dump(self._db, f, ensure_ascii=False, indent=2)

    # ---------- DOI ----------
    def extract_doi_from_pdf(self, pdf_path: str):
        """Extrai o 1º DOI do texto das primeiras páginas. None se não achar."""
        try:
            texto = ""
            with fitz.open(pdf_path) as doc:
                for i, page in enumerate(doc):
                    texto += page.get_text()
                    if i >= 2:  # DOI costuma estar nas 1 as páginas
                        break
        except Exception:
            return None
        m = _DOI_RE.search(texto)
        if not m:
            return None
        return m.group(0).rstrip(".")

    # ---------- dedup ----------
    def is_analyzed(self, doi) -> bool:
        return bool(doi) and doi in self._db

    def get_article(self, doi):
        return self._db.get(doi)

    def add_article(self, doi=None, filename=None, article_type=None, score=None,
                    summary_path=None, audio_path=None, image_path=None, **extra):
        if not doi:
            return
        rec = {
            "doi": doi,
            "filename": filename,
            "article_type": article_type,
            "score": score,
            "summary_path": summary_path,
            "audio_path": audio_path,
            "image_path": image_path,
        }
        rec.update(extra)
        self._db[doi] = rec
        self._save()

    # ---------- estatísticas ----------
    def get_statistics(self) -> dict:
        arts = list(self._db.values())
        scores = [a.get("score") for a in arts if isinstance(a.get("score"), (int, float))]
        return {
            "total": len(arts),
            "high_score": sum(1 for s in scores if s >= 7),
            "with_audio": sum(1 for a in arts if a.get("audio_path")),
            "with_image": sum(1 for a in arts if a.get("image_path")),
            "scores": scores,
        }
