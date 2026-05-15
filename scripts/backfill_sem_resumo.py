#!/usr/bin/env python3
"""
CardioDaily — Backfill de artigos sem resumo_markdown

Busca no Supabase todos os artigos sem resumo_markdown que tenham
source.pdf local, copia para pasta temp e chama article_analyzer.py.

USO:
    python3 scripts/backfill_sem_resumo.py --dry-run     # só conta
    python3 scripts/backfill_sem_resumo.py --limit 10   # teste com 10
    python3 scripts/backfill_sem_resumo.py               # todos
    python3 scripts/backfill_sem_resumo.py --revisoes    # inclui revisões
    python3 scripts/backfill_sem_resumo.py --ano 2025    # só 2025
"""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

import requests

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")
except ImportError:
    pass

PROJECT_ROOT = Path(__file__).parent.parent
CORPUS_DIR   = PROJECT_ROOT / "outputs" / "corpus"
TEMP_DIR     = PROJECT_ROOT / "tmp_backfill_sem_resumo"

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_KEY", "")

TIPOS_GEMINI = {"original", "metanalise", "meta_analise", "revisao_sistematica_meta_analise"}
TIPOS_CLAUDE = {"revisao", "revisao_geral", "guideline", "ponto_de_vista"}
ORDEM_TIPO   = {"original": 0, "metanalise": 1, "meta_analise": 1,
                "revisao": 2, "revisao_geral": 2, "guideline": 2}


def _headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }


def buscar_sem_resumo(incluir_revisoes: bool, ano: str | None, limit: int) -> list[dict]:
    todos = []
    page_size = 1000
    offset = 0
    while len(todos) < limit:
        params = {
            "select": "doc_id,tipo_estudo,nota_aplicabilidade,data_publicacao,caminho_pasta",
            "resumo_markdown": "is.null",
            "order": "nota_aplicabilidade.desc.nullslast",
            "limit": str(min(page_size, limit - len(todos))),
            "offset": str(offset),
        }
        if ano:
            params["data_publicacao"] = f"gte.{ano}-01-01"
            params["data_publicacao_lte"] = f"lte.{ano}-12-31"
        r = requests.get(f"{SUPABASE_URL}/rest/v1/artigos",
                         headers=_headers(), params=params, timeout=30)
        if r.status_code != 200 or not isinstance(r.json(), list):
            print(f"❌ Supabase {r.status_code}: {r.text[:200]}")
            break
        batch = r.json()
        if not batch:
            break
        todos.extend(batch)
        offset += len(batch)
        if len(batch) < page_size:
            break

    tipos_validos = TIPOS_GEMINI | (TIPOS_CLAUDE if incluir_revisoes else set())
    filtrados = [a for a in todos
                 if (a.get("tipo_estudo") or "original") in tipos_validos]
    filtrados.sort(key=lambda a: (
        ORDEM_TIPO.get(a.get("tipo_estudo") or "original", 9),
        -(a.get("nota_aplicabilidade") or 0),
    ))
    return filtrados


def _doc_id_from_row(row: dict) -> str:
    pasta = row.get("caminho_pasta") or ""
    if pasta:
        return pasta.rstrip("/").split("/")[-1]
    return row.get("doc_id") or ""


def tem_pdf_local(doc_id: str) -> bool:
    return (CORPUS_DIR / doc_id / "source.pdf").exists()


def main():
    parser = argparse.ArgumentParser(description="Backfill artigos sem resumo_markdown")
    parser.add_argument("--dry-run",   action="store_true", help="Só conta, não processa")
    parser.add_argument("--limit",     type=int, default=9999, help="Máx artigos (default: todos)")
    parser.add_argument("--revisoes",  action="store_true", help="Incluir revisões/guidelines")
    parser.add_argument("--ano",       type=str, default=None, help="Filtrar por ano (ex: 2025)")
    parser.add_argument("--keep-temp", action="store_true", help="Não apagar pasta temp ao final")
    args = parser.parse_args()

    if not SUPABASE_URL or not SUPABASE_KEY:
        print("❌ SUPABASE_URL / SUPABASE_SERVICE_KEY não configurados")
        sys.exit(1)

    print(f"\n{'='*65}")
    print("CardioDaily — Backfill artigos sem resumo_markdown")
    if args.dry_run:
        print("⚠️  MODO DRY-RUN")
    filtro_str = f"ano={args.ano}" if args.ano else "todos os anos"
    tipos_str  = "originais + meta + revisões" if args.revisoes else "originais + meta"
    print(f"   Tipos: {tipos_str}  |  Filtro: {filtro_str}  |  Limite: {args.limit}")
    print(f"{'='*65}\n")

    print("📋 Buscando artigos sem resumo no Supabase...")
    rows = buscar_sem_resumo(args.revisoes, args.ano, args.limit)
    print(f"   → {len(rows)} artigos elegíveis")

    # Enriquecer doc_id via caminho_pasta
    for row in rows:
        if not row.get("doc_id"):
            row["doc_id"] = _doc_id_from_row(row)

    com_pdf = [r for r in rows if tem_pdf_local(r["doc_id"])]
    sem_pdf = [r for r in rows if not tem_pdf_local(r["doc_id"])]

    print(f"   → {len(com_pdf)} com source.pdf local (serão processados)")
    print(f"   → {len(sem_pdf)} sem source.pdf (pulados)")

    if args.dry_run:
        print("\n--- Primeiros 20 a processar ---")
        for r in com_pdf[:20]:
            nota = r.get("nota_aplicabilidade") or "?"
            tipo = (r.get("tipo_estudo") or "?")[:12]
            ano  = (r.get("data_publicacao") or "")[:4]
            print(f"  {r['doc_id']} | {tipo:<12} | nota={nota} | {ano}")
        if len(com_pdf) > 20:
            print(f"  ... e mais {len(com_pdf)-20} artigos")
        print("\nDry-run — nada alterado.")
        return

    if not com_pdf:
        print("\n✅ Nenhum artigo com PDF local para processar.")
        return

    # Preparar pasta temp
    if TEMP_DIR.exists():
        shutil.rmtree(str(TEMP_DIR))
    TEMP_DIR.mkdir(parents=True)

    print(f"\n📂 Copiando {len(com_pdf)} PDFs para {TEMP_DIR.name}...")
    for i, row in enumerate(com_pdf, 1):
        doc_id = row["doc_id"]
        src = CORPUS_DIR / doc_id / "source.pdf"
        dst = TEMP_DIR / f"{doc_id}.pdf"
        shutil.copy2(str(src), str(dst))
        if i % 100 == 0:
            print(f"   {i}/{len(com_pdf)} copiados...")

    print(f"   ✅ {len(com_pdf)} PDFs prontos\n")

    # Apagar analysis.md e analysis.json para forçar reanálise
    print("🗑️  Removendo análises antigas...")
    removidos = 0
    for row in com_pdf:
        doc_id = row["doc_id"]
        article_dir = CORPUS_DIR / doc_id
        for nome in ("analysis.md", "analysis.json"):
            f = article_dir / nome
            if f.exists():
                f.unlink()
                removidos += 1
    print(f"   → {removidos} arquivos removidos\n")

    # Chamar article_analyzer.py
    cmd = [sys.executable, str(PROJECT_ROOT / "src" / "article_analyzer.py"),
           "--local-dir", str(TEMP_DIR)]
    env = os.environ.copy()
    env["CARDIODAILY_SKIP_BRIEFING"] = "1"

    print(f"🚀 Iniciando article_analyzer.py com {len(com_pdf)} artigos...")
    print(f"   (pode demorar — ~{len(com_pdf)*4//60} minutos estimados)\n")
    result = subprocess.run(cmd, env=env, cwd=str(PROJECT_ROOT))

    if not args.keep_temp:
        print(f"\n🗑️  Limpando {TEMP_DIR.name}...")
        shutil.rmtree(str(TEMP_DIR))

    print(f"\n{'='*65}")
    print(f"✅ Concluído — exit code: {result.returncode}")
    print(f"{'='*65}\n")


if __name__ == "__main__":
    main()
