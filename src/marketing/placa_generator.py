"""
Gerador de placas CardioDaily — stories (1080×1920) e posts feed (1080×1080).
Renderiza HTML→PNG via Playwright com identidade visual CardioDaily.
"""
from __future__ import annotations

import base64
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from jinja2 import Environment, FileSystemLoader
from playwright.sync_api import sync_playwright

# ── Paths ────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parents[2]
TEMPLATES_DIR = Path(__file__).parent / "templates"
LOGO_PATH = Path("/Users/edcastro77/Desktop/RECURSOS/LOGOs/logo_cardiodaily.png")
OUTPUT_BASE = ROOT / "outputs" / "marketing"

# ── Identidade visual ─────────────────────────────────────────────────────────
BRAND = {
    "cor_fundo": "#F0F2F0",
    "cor_borda": "#3BAF9E",
    "cor_destaque": "#3BAF9E",
    "cor_titulo": "#111111",
    "cor_corpo": "#222222",
    "cor_rodape_bg": "#FFFFFF",
    "tag_topo": "CARDIOLOGIA · EVIDÊNCIA CIENTÍFICA",
    "slogan": "Os Fatos sem Fírulas",
    "carimbo": "Dr. Eduardo Castro · CRM-ES 8062 · RQE Cardiologia 6788 · RQE Medicina Interna 6787",
}


def _logo_b64() -> str:
    if LOGO_PATH.exists():
        data = LOGO_PATH.read_bytes()
        return f"data:image/png;base64,{base64.b64encode(data).decode()}"
    return ""


@dataclass
class StoryData:
    """Dados para geração de um story (1080×1920)."""
    tipo: str                        # "iconica" | "ancora" | "pontos"
    titulo: str
    corpo: str
    ancora_valor: str = ""           # só para tipo "ancora"
    bullets: list[str] = field(default_factory=list)  # só para tipo "pontos"
    fonte: str = ""


@dataclass
class PostFeedData:
    """Dados para geração do post feed (1080×1080)."""
    titulo: str
    ancora_valor: str
    bullets: list[str]
    corpo: str
    fonte: str


def _fontes_story(s: "StoryData") -> dict:
    """Calcula tamanhos de fonte para story baseado no volume de texto."""
    # Caracteres totais do conteúdo principal
    titulo_chars = len(s.titulo)
    corpo_chars  = len(s.corpo)
    bullets_chars = max((len(b) for b in s.bullets), default=0) if s.bullets else 0
    ancora_chars = len(s.ancora_valor) if s.ancora_valor else 0

    # Título: reduz se muitas linhas ou chars
    titulo_linhas = s.titulo.count("\n") + 1
    if titulo_chars > 40 or titulo_linhas > 3:
        fs_titulo = 72
    elif titulo_chars > 28 or titulo_linhas > 2:
        fs_titulo = 86
    else:
        fs_titulo = 98

    # Âncora: reduz se texto longo
    if ancora_chars > 60:
        fs_ancora = 58
    elif ancora_chars > 40:
        fs_ancora = 72
    else:
        fs_ancora = 86

    # Corpo
    if corpo_chars > 200:
        fs_corpo = 36
    elif corpo_chars > 140:
        fs_corpo = 40
    else:
        fs_corpo = 44

    # Bullets
    if bullets_chars > 120:
        fs_bullet = 32
        gap = 18
    elif bullets_chars > 80:
        fs_bullet = 36
        gap = 22
    else:
        fs_bullet = 40
        gap = 28

    return {
        "titulo": fs_titulo,
        "ancora": fs_ancora,
        "corpo":  fs_corpo,
        "bullet": fs_bullet,
        "gap":    gap,
    }


def _fontes_post(p: "PostFeedData") -> dict:
    """Calcula tamanhos de fonte para post feed baseado no volume de texto."""
    ancora_chars = len(p.ancora_valor)
    bullets_chars = max((len(b) for b in p.bullets), default=0) if p.bullets else 0
    n_bullets = len(p.bullets)

    # Âncora
    if ancora_chars > 60:
        fs_ancora = 42
    elif ancora_chars > 40:
        fs_ancora = 52
    else:
        fs_ancora = 62

    # Bullets — reduz se texto longo ou muitos bullets
    if bullets_chars > 100 or n_bullets > 3:
        fs_bullet = 24
        gap = 10
    elif bullets_chars > 70:
        fs_bullet = 28
        gap = 12
    else:
        fs_bullet = 32
        gap = 14

    return {
        "ancora": fs_ancora,
        "bullet": fs_bullet,
        "corpo":  26,
        "fonte":  20,
        "gap":    gap,
    }


class PlacaGenerator:
    def __init__(self):
        self._jinja = Environment(
            loader=FileSystemLoader(str(TEMPLATES_DIR)),
            autoescape=True,
        )
        self._logo_b64 = _logo_b64()

    # ── Renderização base ─────────────────────────────────────────────────────

    def _render_html(self, template_name: str, ctx: dict) -> str:
        tpl = self._jinja.get_template(template_name)
        return tpl.render(**ctx, brand=BRAND, logo_b64=self._logo_b64)

    def _html_to_png(self, html: str, out_path: Path, width: int, height: int) -> Path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            page = browser.new_page(viewport={"width": width, "height": height})
            page.set_content(html, wait_until="networkidle")
            page.wait_for_function("document.readyState === 'complete'")
            page.screenshot(path=str(out_path), full_page=False, clip={
                "x": 0, "y": 0, "width": width, "height": height
            })
            browser.close()
        return out_path

    # ── API pública ───────────────────────────────────────────────────────────

    def gerar_story(self, data: StoryData, out_path: Path) -> Path:
        fs = _fontes_story(data)
        ctx = {"s": data, "fs": fs}
        html = self._render_html("story.html", ctx)
        return self._html_to_png(html, out_path, 1080, 1920)

    def gerar_post_feed(self, data: PostFeedData, out_path: Path) -> Path:
        fs = _fontes_post(data)
        ctx = {"p": data, "fs": fs}
        html = self._render_html("post_feed.html", ctx)
        return self._html_to_png(html, out_path, 1080, 1080)

    def gerar_kit_completo(
        self,
        doc_id: str,
        story1: StoryData,
        story2: StoryData,
        story3: StoryData,
        post: PostFeedData,
        prefixo: str = "",
    ) -> dict[str, Path]:
        """Gera os 4 arquivos do kit e retorna dict com os caminhos."""
        out_dir = OUTPUT_BASE / doc_id
        out_dir.mkdir(parents=True, exist_ok=True)
        pref = f"{prefixo}_" if prefixo else ""

        resultados = {}
        print("  [1/4] Gerando story 1 — frase icônica...")
        resultados["story1"] = self.gerar_story(story1, out_dir / f"{pref}story1_iconica.png")

        print("  [2/4] Gerando story 2 — dado âncora...")
        resultados["story2"] = self.gerar_story(story2, out_dir / f"{pref}story2_ancora.png")

        print("  [3/4] Gerando story 3 — pontos-chave...")
        resultados["story3"] = self.gerar_story(story3, out_dir / f"{pref}story3_pontos.png")

        print("  [4/4] Gerando post feed...")
        resultados["post"] = self.gerar_post_feed(post, out_dir / f"{pref}post_feed.png")

        # Salvar metadados do kit
        meta = {
            "doc_id": doc_id,
            "story1": str(resultados["story1"]),
            "story2": str(resultados["story2"]),
            "story3": str(resultados["story3"]),
            "post": str(resultados["post"]),
        }
        (out_dir / f"{pref}kit_meta.json").write_text(
            json.dumps(meta, indent=2, ensure_ascii=False)
        )
        return resultados
