#!/usr/bin/env python3
"""
CardioDaily — Backfill de títulos no Supabase

Para cada artigo com título vazio:
  1. Tenta extrair do analysis.json local
  2. Tenta extrair do frontmatter do analysis.md
  3. Consulta CrossRef pelo DOI (grátis, sem chave)

USO:
    python3 scripts/backfill_titulos.py --dry-run
    python3 scripts/backfill_titulos.py
    python3 scripts/backfill_titulos.py --limit 100
"""

import argparse
import json
import os
import re
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
CROSSREF_UA  = "CardioDaily/1.0 (mailto:edcastro77@gmail.com)"


def _hdrs():
    return {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json"}


def _extrair_doi_local(doc_id: str) -> str | None:
    """Extrai DOI do analysis.md local."""
    md = CORPUS_DIR / doc_id / "analysis.md"
    if not md.exists():
        return None
    try:
        content = md.read_text(errors="ignore")
        m = re.search(r'^doi:\s*["\']?(.+?)["\']?\s*$', content, re.MULTILINE)
        if m:
            doi = m.group(1).strip().strip('"\'')
            if doi and doi != "null" and doi.startswith("10."):
                return doi
    except Exception:
        pass
    return None


def _titulo_do_crossref(doi: str) -> str | None:
    """Busca título no CrossRef pelo DOI."""
    try:
        r = requests.get(
            f"https://api.crossref.org/works/{doi}",
            headers={"User-Agent": CROSSREF_UA},
            timeout=15,
        )
        if r.status_code == 200:
            titles = r.json().get("message", {}).get("title", [])
            if titles and titles[0]:
                return titles[0].strip()
    except Exception:
        pass
    return None


def _titulo_do_disco(doc_id: str) -> str | None:
    """Tenta extrair título do analysis.json local."""
    aj = CORPUS_DIR / doc_id / "analysis.json"
    if not aj.exists():
        return None
    try:
        d = json.loads(aj.read_text(errors="ignore"))
        t = (d.get("analysis") or {}).get("titulo") or d.get("titulo")
        if t and len(t) > 5:
            return t.strip()
    except Exception:
        pass
    return None


def _buscar_sem_titulo(limit: int) -> list[dict]:
    todos = []
    page_size = 1000
    offset = 0
    while len(todos) < limit:
        r = requests.get(f"{SUPABASE_URL}/rest/v1/artigos", headers=_hdrs(),
            params={"select": "doc_id",
                    "titulo": "eq.",
                    "order": "created_at.desc",
                    "limit": str(min(page_size, limit - len(todos))),
                    "offset": str(offset)},
            timeout=30)
        if r.status_code != 200 or not isinstance(r.json(), list):
            break
        batch = r.json()
        if not batch:
            break
        todos.extend(batch)
        offset += len(batch)
        if len(batch) < page_size:
            break
    return todos


def _atualizar(doc_id: str, titulo: str) -> bool:
    r = requests.patch(f"{SUPABASE_URL}/rest/v1/artigos",
        headers={**_hdrs(), "Prefer": "return=minimal"},
        params={"doc_id": f"eq.{doc_id}"},
        json={"titulo": titulo},
        timeout=20)
    return r.status_code in (200, 204)


def _processar(doc_id: str):
    # 1. Disco
    titulo = _titulo_do_disco(doc_id)
    fonte = "disco"

    # 2. CrossRef via DOI local
    if not titulo:
        doi = _extrair_doi_local(doc_id)
        if doi:
            titulo = _titulo_do_crossref(doi)
            fonte = "crossref"
            time.sleep(0.1)  # gentil com CrossRef

    if not titulo:
        return "skip", "não encontrado"

    if _atualizar(doc_id, titulo):
        return "ok", (fonte, titulo)
    return "erro", "falha no update"


def main():
    import sys
    print("[APOSENTADO 20/06] Backfill desativado. Com o portao de validacao "
          "ativo, buracos novos nao nascem. Reparo do passado, se necessario, "
          "deve ser feito em tabela paralela controlada, nao aqui.")
    sys.exit(0)
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=9999)
    args = parser.parse_args()

    if not SUPABASE_URL or not SUPABASE_KEY:
        print("❌ SUPABASE_URL/SUPABASE_SERVICE_KEY não configurados")
        sys.exit(1)

    print(f"\n{'='*60}")
    print("CardioDaily — Backfill títulos (disco + CrossRef)")
    if args.dry_run:
        print("⚠️  DRY-RUN")
    print(f"{'='*60}\n")

    print("📋 Buscando artigos com título vazio no Supabase...")
    artigos = _buscar_sem_titulo(args.limit)
    print(f"   → {len(artigos)} artigos sem título\n")

    if not artigos:
        print("✅ Nenhum artigo sem título.")
        return

    if args.dry_run:
        # Testar amostra de 10
        print("Testando amostra de 10 artigos...")
        for a in artigos[:10]:
            doc_id = a["doc_id"]
            doi = _extrair_doi_local(doc_id)
            titulo = _titulo_do_disco(doc_id)
            if not titulo and doi:
                titulo = _titulo_do_crossref(doi)
                fonte = "crossref"
            else:
                fonte = "disco"
            status = "✅" if titulo else "❌"
            print(f"  {status} {doc_id} [{fonte}]: {(titulo or 'N/A')[:60]}")
        print("\nDry-run — nada alterado.")
        return

    ok = sem_titulo = erros = 0
    disco_count = crossref_count = 0
    lock = threading.Lock()
    done_count = [0]
    t0 = time.time()

    with ThreadPoolExecutor(max_workers=8) as ex:
        futures = {ex.submit(_processar, a["doc_id"]): a["doc_id"] for a in artigos}
        for fut in as_completed(futures):
            status, payload = fut.result()
            with lock:
                done_count[0] += 1
                n = done_count[0]
            if status == "ok":
                fonte, titulo = payload
                with lock:
                    ok += 1
                    if fonte == "disco":
                        disco_count += 1
                    else:
                        crossref_count += 1
                if n % 200 == 0:
                    elapsed = time.time() - t0
                    rate = n / elapsed * 60
                    print(f"  [{n}/{len(artigos)}] {ok} atualizados — {rate:.0f}/min")
            elif status == "skip":
                with lock:
                    sem_titulo += 1
            else:
                with lock:
                    erros += 1

    elapsed = time.time() - t0
    print(f"\n{'='*60}")
    print(f"✅ {ok} títulos atualizados ({disco_count} do disco + {crossref_count} via CrossRef)")
    print(f"   {sem_titulo} sem título disponível | {erros} erros | {elapsed/60:.1f}min")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    import sys
    print("[APOSENTADO 20/06] Backfill desativado. Com o portao de validacao "
          "ativo, buracos novos nao nascem. Reparo do passado, se necessario, "
          "deve ser feito em tabela paralela controlada, nao aqui.")
    sys.exit(0)
    main()
