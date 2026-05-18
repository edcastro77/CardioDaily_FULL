#!/usr/bin/env python3
"""
CardioDaily — Backfill campos clínicos ricos no Supabase

Lê analysis.json local de cada artigo e faz PATCH nos campos:
  contexto_tema, aplicabilidade_pratica, impacto_conduta,
  tamanho_beneficio, conclusao_geral, bullets_praticos,
  por_que_importa, principais_recomendacoes

ZERO tokens — só leitura de arquivos locais.

USO:
    python3 scripts/backfill_campos_clinicos.py --dry-run
    python3 scripts/backfill_campos_clinicos.py
    python3 scripts/backfill_campos_clinicos.py --nota-min 8
"""

import argparse
import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")
except ImportError:
    pass

SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY", "")
CORPUS_DIR   = Path(__file__).parent.parent / "outputs" / "corpus"

CAMPOS_TEXTO = [
    "contexto_tema",
    "aplicabilidade_pratica",
    "impacto_conduta",
    "tamanho_beneficio",
    "conclusao_geral",
    "por_que_importa",
    "principais_recomendacoes",
]


def _hdrs():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }


def _extrair_campos(doc_id: str) -> dict | None:
    json_path = CORPUS_DIR / doc_id / "analysis.json"
    if not json_path.exists():
        return None
    try:
        data = json.loads(json_path.read_text(errors="ignore"))
    except Exception:
        return None

    analise  = data.get("analysis", {})
    nucleo   = analise.get("nucleo_comum", {})
    reflexao = analise.get("reflexao_final", {})

    campos = {}

    # Campos texto (originais)
    for c in ["contexto_tema", "por_que_importa", "principais_recomendacoes"]:
        v = analise.get(c)
        if v and isinstance(v, str) and len(v.strip()) > 10:
            campos[c] = v.strip()

    for c in ["aplicabilidade_pratica", "impacto_conduta", "tamanho_beneficio", "conclusao_geral"]:
        v = nucleo.get(c)
        if v and isinstance(v, str) and len(v.strip()) > 10:
            campos[c] = v.strip()

    # bullets_praticos — JSONB (lista de strings)
    bp = reflexao.get("bullets_praticos")
    if isinstance(bp, list) and bp:
        campos["bullets_praticos"] = bp
    elif isinstance(bp, str) and bp.strip():
        # fallback: string → lista com 1 item
        campos["bullets_praticos"] = [bp.strip()]

    return campos if campos else None


def _patch_supabase(doc_id: str, campos: dict) -> bool:
    r = requests.patch(
        f"{SUPABASE_URL}/rest/v1/artigos",
        headers=_hdrs(),
        params={"doc_id": f"eq.{doc_id}"},
        json=campos,
        timeout=20,
    )
    return r.status_code in (200, 204)


def _buscar_doc_ids_por_nota(nota_min: int) -> list[str]:
    todos = []
    page_size = 1000
    offset = 0
    while True:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/artigos",
            headers=_hdrs(),
            params={
                "select": "doc_id",
                "nota_aplicabilidade": f"gte.{nota_min}",
                "order": "nota_aplicabilidade.desc",
                "limit": str(page_size),
                "offset": str(offset),
            },
            timeout=30,
        )
        if r.status_code != 200 or not isinstance(r.json(), list):
            break
        batch = r.json()
        if not batch:
            break
        todos.extend(a["doc_id"] for a in batch)
        offset += len(batch)
        if len(batch) < page_size:
            break
    return todos


def _todos_doc_ids_locais() -> list[str]:
    return [p.name for p in CORPUS_DIR.iterdir()
            if p.is_dir() and (p / "analysis.json").exists()]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--nota-min", type=int, default=0,
                        help="Backfill só artigos com nota >= N (0 = todos)")
    parser.add_argument("--workers", type=int, default=10)
    args = parser.parse_args()

    if not SUPABASE_URL or not SUPABASE_KEY:
        print("❌ SUPABASE_URL/SUPABASE_SERVICE_KEY não configurados")
        sys.exit(1)

    print(f"\n{'='*60}")
    print("CardioDaily — Backfill campos clínicos (analysis.json → Supabase)")
    print("💡 Zero tokens — só leitura de arquivos locais")
    if args.dry_run:
        print("⚠️  DRY-RUN — nada será alterado")
    print(f"{'='*60}\n")

    if args.nota_min > 0:
        print(f"🔍 Buscando artigos com nota ≥ {args.nota_min} no Supabase...")
        doc_ids = _buscar_doc_ids_por_nota(args.nota_min)
        print(f"   → {len(doc_ids)} artigos")
    else:
        print("📂 Lendo corpus local...")
        doc_ids = _todos_doc_ids_locais()
        print(f"   → {len(doc_ids)} pastas com analysis.json")

    # Amostrar no dry-run
    amostra = doc_ids[:20] if args.dry_run else doc_ids

    ok = sem_json = sem_campos = erros = 0
    lock = threading.Lock()
    done = [0]
    t0 = time.time()

    def processar(doc_id):
        campos = _extrair_campos(doc_id)
        if campos is None:
            return "sem_campos", doc_id
        if args.dry_run:
            return "dry", (doc_id, campos)
        if _patch_supabase(doc_id, campos):
            return "ok", len(campos)
        return "erro", doc_id

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futures = {ex.submit(processar, d): d for d in amostra}
        for fut in as_completed(futures):
            status, payload = fut.result()
            with lock:
                done[0] += 1
                n = done[0]

            if status == "ok":
                with lock: ok += 1
                if n % 200 == 0:
                    elapsed = time.time() - t0
                    print(f"  [{n}/{len(amostra)}] {ok} atualizados — {elapsed/60:.1f}min")
            elif status == "sem_campos":
                with lock: sem_campos += 1
            elif status == "erro":
                with lock: erros += 1
                print(f"  ❌ PATCH falhou: {payload}")
            elif status == "dry":
                doc_id, campos = payload
                with lock: ok += 1
                print(f"  {doc_id}: {list(campos.keys())}")

    elapsed = time.time() - t0
    print(f"\n{'='*60}")
    if args.dry_run:
        print(f"DRY-RUN: {ok} artigos com campos extraíveis (amostra de {len(amostra)})")
    else:
        print(f"✅ {ok} artigos atualizados | {sem_campos} sem campos | {erros} erros")
    print(f"   Tempo: {elapsed:.0f}s")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
