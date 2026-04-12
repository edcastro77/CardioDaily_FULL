#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CardioDaily — Geração de PDFs em Lote
Usa Playwright para renderizar a página /analise/{doc_id} do Administrador
(resultado idêntico ao "Salvar PDF / Imprimir" manual) e faz upload ao Supabase.

Uso:
    python3 scripts/gerar_pdfs_lote.py              # todos os elegíveis
    python3 scripts/gerar_pdfs_lote.py --dry-run    # só lista
    python3 scripts/gerar_pdfs_lote.py --limite 10  # máximo 10 artigos
    python3 scripts/gerar_pdfs_lote.py --desde 2026-03-01
    python3 scripts/gerar_pdfs_lote.py --doc-id doi_XXXXX  # artigo específico
"""

import argparse
import os
import sys
import time
import subprocess
import requests
from pathlib import Path
from datetime import datetime

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
ADMIN_URL     = "http://localhost:5100"
BUCKET        = "resumos_pdf"
PDF_DIR       = _ROOT / "outputs" / "pdfs_lote"
NOTA_MIN      = 7   # envia para nota >= 7 (distribuidor já filtra >= 7)
DATA_DESDE    = "2026-02-01"
TIPOS_VALIDOS = ("original", "metanalise", "revisao", "meta_analise", "revisao_geral")
_ADMIN_PROC   = None  # processo do Administrador iniciado por este script

# ─── Supabase ─────────────────────────────────────────────────────────────────

def _sb_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }


def buscar_elegíveis(desde: str, limite: int, forcar: bool = False) -> list[dict]:
    params = {
        "select": "doc_id,titulo,tipo_estudo,nota_aplicabilidade,data_publicacao",
        "nota_aplicabilidade": f"gte.{NOTA_MIN}",
        "data_publicacao": f"gte.{desde}",
        "order": "data_publicacao.desc",
        "limit": str(limite),
    }
    if not forcar:
        params["caminho_pdf"] = "is.null"
    r = requests.get(f"{SUPABASE_URL}/rest/v1/artigos",
                     headers=_sb_headers(), params=params, timeout=30)
    if r.status_code != 200:
        print(f"❌ Erro Supabase: {r.status_code} — {r.text[:300]}")
        return []
    artigos = r.json()
    return [a for a in artigos if (a.get("tipo_estudo") or "").lower() in TIPOS_VALIDOS]


def buscar_por_doc_id(doc_id: str) -> list[dict]:
    r = requests.get(f"{SUPABASE_URL}/rest/v1/artigos",
                     headers=_sb_headers(),
                     params={"select": "doc_id,titulo,tipo_estudo,nota_aplicabilidade,data_publicacao",
                             "doc_id": f"eq.{doc_id}"},
                     timeout=15)
    return r.json() if r.status_code == 200 else []


def upload_pdf(doc_id: str, pdf_path: Path) -> str | None:
    objeto = f"{doc_id}.pdf"
    url_upload  = f"{SUPABASE_URL}/storage/v1/object/{BUCKET}/{objeto}"
    url_publica = f"{SUPABASE_URL}/storage/v1/object/public/{BUCKET}/{objeto}"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/pdf",
        "x-upsert": "true",
    }
    with open(pdf_path, "rb") as f:
        r = requests.post(url_upload, headers=headers, data=f, timeout=120)
    if r.status_code in (200, 201):
        return url_publica
    print(f"   ⚠️  Upload falhou: {r.status_code} — {r.text[:200]}")
    return None


def atualizar_caminho_pdf(doc_id: str, url: str) -> bool:
    r = requests.patch(
        f"{SUPABASE_URL}/rest/v1/artigos?doc_id=eq.{doc_id}",
        headers={**_sb_headers(), "Prefer": "return=minimal"},
        json={"caminho_pdf": url},
        timeout=15,
    )
    return r.status_code in (200, 204)

# ─── Administrador ────────────────────────────────────────────────────────────

def admin_esta_rodando() -> bool:
    try:
        r = requests.get(f"{ADMIN_URL}/", timeout=3)
        return r.status_code == 200
    except Exception:
        return False


def iniciar_admin() -> subprocess.Popen | None:
    """Inicia o Administrador em background se não estiver rodando."""
    if admin_esta_rodando():
        print("   ✅ Administrador já rodando em localhost:5100")
        return None
    print("   🚀 Iniciando Administrador em background…")
    venv_python = _ROOT / ".venv" / "bin" / "python3"
    python = str(venv_python) if venv_python.exists() else "python3"
    proc = subprocess.Popen(
        [python, str(_ROOT / "src" / "web_biblioteca.py")],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    # Aguardar subir (máximo 15s)
    for _ in range(15):
        time.sleep(1)
        if admin_esta_rodando():
            print("   ✅ Administrador online")
            return proc
    print("   ❌ Administrador não subiu em 15s")
    proc.terminate()
    return None

# ─── PDF via Playwright ───────────────────────────────────────────────────────

def gerar_pdf_playwright(doc_id: str, pdf_path: Path) -> bool:
    """
    Abre /analise/{doc_id} no Playwright e salva como PDF.
    Idêntico ao resultado de clicar "Salvar PDF / Imprimir" no browser.
    """
    from playwright.sync_api import sync_playwright

    url = f"{ADMIN_URL}/analise/{doc_id}"
    pdf_path.parent.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            page.goto(url, wait_until="networkidle", timeout=30000)
            # Aguardar marked.js renderizar o markdown
            page.wait_for_selector("#content p, #content h1, #content h2",
                                   timeout=10000)
            # Mesmo CSS que o browser usa para impressão
            page.pdf(
                path=str(pdf_path),
                format="A4",
                margin={"top": "15mm", "right": "18mm", "bottom": "15mm", "left": "18mm"},
                print_background=False,
            )
            size_kb = pdf_path.stat().st_size // 1024
            print(f"   ✅ PDF: {pdf_path.name} ({size_kb} KB)")
            return True
        except Exception as e:
            print(f"   ❌ Playwright erro: {e}")
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
    print(f"   {titulo[:75]}{'...' if len(titulo) > 75 else ''}")
    print(f"   {tipo} | {nota}/10 | {data}")

    if dry_run:
        print("   [dry-run] — pulando")
        return "dry_run"

    # Verificar que analysis.md existe
    if not (CORPUS_DIR := _ROOT / "outputs" / "corpus" / doc_id / "analysis.md").exists():
        print(f"   ⚠️  analysis.md não encontrado — pulando")
        return "sem_analise"

    pdf_path = PDF_DIR / f"{doc_id}.pdf"

    # --forcar: apagar PDF local para regenerar
    if forcar and pdf_path.exists():
        pdf_path.unlink()
        print(f"   🗑️  PDF local removido (--forcar)")

    # Se PDF já existe localmente, pular geração e ir direto ao upload
    if not pdf_path.exists():
        print(f"   🖨️  Gerando PDF via Playwright…")
        if not gerar_pdf_playwright(doc_id, pdf_path):
            return "erro_pdf"
    else:
        print(f"   ♻️  PDF já existe localmente — fazendo upload direto")

    # Upload Supabase
    print(f"   ☁️  Upload para bucket '{BUCKET}'…")
    url = upload_pdf(doc_id, pdf_path)
    if not url:
        return "erro_upload"
    print(f"   ✅ {url}")

    # Atualizar Supabase
    ok = atualizar_caminho_pdf(doc_id, url)
    print(f"   🗄️  caminho_pdf {'atualizado' if ok else '⚠️  falhou (URL salva mesmo assim)'}")

    return "ok"

# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    global _ADMIN_PROC
    parser = argparse.ArgumentParser(description="CardioDaily — PDFs em Lote")
    parser.add_argument("--dry-run",  action="store_true")
    parser.add_argument("--limite",   type=int, default=500)
    parser.add_argument("--desde",    type=str, default=DATA_DESDE)
    parser.add_argument("--doc-id",   type=str, default=None,
                        help="Processar um único artigo")
    parser.add_argument("--forcar",   action="store_true",
                        help="Reprocessar mesmo artigos que já têm caminho_pdf (sobrescreve)")
    args = parser.parse_args()

    if not SUPABASE_URL or not SUPABASE_KEY:
        print("❌ SUPABASE_URL / SUPABASE_SERVICE_KEY não configurados")
        sys.exit(1)

    print(f"\n{'='*55}")
    print(f"🖨️  CardioDaily — PDFs em Lote")
    print(f"   📅 {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    if args.doc_id:
        print(f"   🎯 Artigo específico: {args.doc_id}")
    else:
        print(f"   📆 Desde: {args.desde} | Nota ≥ {NOTA_MIN} | Limite: {args.limite}")
    print(f"   {'[DRY-RUN]' if args.dry_run else 'MODO REAL'}")
    if args.forcar:
        print(f"   ⚠️  --forcar: sobrescrevendo PDFs existentes")
    print(f"{'='*55}\n")

    # Buscar artigos
    if args.doc_id:
        artigos = buscar_por_doc_id(args.doc_id)
        if not artigos:
            print(f"❌ doc_id '{args.doc_id}' não encontrado no Supabase")
            sys.exit(1)
    else:
        print("🔍 Buscando elegíveis no Supabase…")
        artigos = buscar_elegíveis(args.desde, args.limite, forcar=args.forcar)
        print(f"   {len(artigos)} artigos encontrados\n")

    if not artigos:
        print("✅ Nenhum artigo elegível sem PDF. Tudo em dia!")
        return

    # Listar
    print(f"{'#':>3}  {'doc_id':<30} {'tipo':<14} {'nota':>4}  data")
    print("─" * 65)
    for i, a in enumerate(artigos, 1):
        print(f"{i:>3}  {a['doc_id']:<30} {(a.get('tipo_estudo') or ''):<14} "
              f"{(a.get('nota_aplicabilidade') or 0):>4}  {a.get('data_publicacao','')}")

    if args.dry_run:
        print(f"\n✅ Dry-run: {len(artigos)} artigos seriam processados.")
        return

    # Garantir Administrador rodando
    print(f"\n🔧 Verificando Administrador…")
    _ADMIN_PROC = iniciar_admin()
    if not admin_esta_rodando():
        print("❌ Administrador não está acessível. Inicie com './Administrador.command' e tente novamente.")
        sys.exit(1)

    # Processar
    print(f"\n{'='*55}")
    print(f"🚀 Gerando {len(artigos)} PDF(s)…")
    print(f"{'='*55}")

    stats = {"ok": 0, "sem_analise": 0, "erro_pdf": 0, "erro_upload": 0}

    for i, artigo in enumerate(artigos, 1):
        print(f"\n[{i}/{len(artigos)}]", end="")
        status = processar_artigo(artigo, dry_run=False, forcar=args.forcar)
        stats[status] = stats.get(status, 0) + 1
        if i < len(artigos):
            time.sleep(1)

    # Encerrar Administrador se foi iniciado por este script
    if _ADMIN_PROC:
        _ADMIN_PROC.terminate()
        print("\n   🛑 Administrador encerrado")

    print(f"\n\n{'='*55}")
    print(f"✅ LOTE CONCLUÍDO")
    print(f"   ✅ PDFs gerados e enviados: {stats['ok']}")
    print(f"   ⚠️  Sem analysis.md:        {stats.get('sem_analise', 0)}")
    print(f"   ❌ Erro PDF:                {stats.get('erro_pdf', 0)}")
    print(f"   ❌ Erro upload:             {stats.get('erro_upload', 0)}")
    print(f"{'='*55}\n")


if __name__ == "__main__":
    main()
