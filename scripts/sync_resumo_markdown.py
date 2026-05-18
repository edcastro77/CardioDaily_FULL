#!/usr/bin/env python3
"""
CardioDaily — Sync resumo_markdown do analysis.md para o Supabase

Extrai o conteúdo relevante do analysis.md local (take-home, bullets práticos,
reflexão final) e faz PATCH no Supabase para artigos com resumo_markdown vazio.

ZERO tokens gastos — só lê arquivos locais e atualiza o banco.

USO:
    python3 scripts/sync_resumo_markdown.py --dry-run
    python3 scripts/sync_resumo_markdown.py
    python3 scripts/sync_resumo_markdown.py --limit 50
"""

import argparse
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


def _hdrs():
    return {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json"}


def _extrair_resumo(doc_id: str) -> str | None:
    """Extrai resumo do analysis.md — prioriza take-home, depois reflexão final."""
    md = CORPUS_DIR / doc_id / "analysis.md"
    if not md.exists():
        return None

    try:
        content = md.read_text(errors="ignore")

        # 1. Seção TAKE-HOME MESSAGE
        m = re.search(
            r'#{1,4}[^\n]*TAKE.HOME[^\n]*\n(.*?)(?=\n#{1,4}|\Z)',
            content, re.IGNORECASE | re.DOTALL
        )
        if m:
            texto = m.group(1).strip()
            if len(texto) > 50:
                return _limpar(texto)

        # 2. Seção APLICAÇÃO PRÁTICA / bullets práticos
        m = re.search(
            r'#{1,4}[^\n]*(?:APLICA[ÇC][AÃ]O PRÁTICA|BULLETS|PRÁTICO|REFLEXÃO FINAL)[^\n]*\n(.*?)(?=\n#{1,4}|\Z)',
            content, re.IGNORECASE | re.DOTALL
        )
        if m:
            texto = m.group(1).strip()
            if len(texto) > 50:
                return _limpar(texto)

        # 3. Fallback: pegar os últimos 1500 chars do MD (geralmente a conclusão)
        # Mas só se o MD tiver análise real (não stub de duplicata)
        if "já foi analisado anteriormente" not in content and len(content) > 2000:
            # Pegar seção final após último ##
            partes = re.split(r'\n## ', content)
            if len(partes) > 1:
                ultima = partes[-1].strip()
                if len(ultima) > 100:
                    return _limpar(ultima[:1500])

    except Exception:
        pass

    return None


def _limpar(texto: str) -> str:
    """Remove apenas ruído estrutural, preserva tabelas markdown e bullets."""
    # Remover linhas com só hifens/iguais (separadores — nunca remover | pois são tabelas)
    texto = re.sub(r'^[-=]{3,}\s*$', '', texto, flags=re.MULTILINE)
    # Normalizar espaços em excesso
    texto = re.sub(r'\n{3,}', '\n\n', texto)
    texto = texto.strip()
    # Limitar a 3000 chars
    if len(texto) > 3000:
        texto = texto[:3000].rsplit('\n', 1)[0]
    return texto


def _buscar_sem_resumo(limit: int) -> list[dict]:
    """Busca artigos sem resumo_markdown no Supabase."""
    todos = []
    page_size = 1000
    offset = 0
    while len(todos) < limit:
        r = requests.get(f"{SUPABASE_URL}/rest/v1/artigos", headers=_hdrs(),
            params={"select": "doc_id",
                    "resumo_markdown": "is.null",
                    "order": "nota_aplicabilidade.desc.nullslast",
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


def _patch_supabase(doc_id: str, resumo: str) -> bool:
    r = requests.patch(f"{SUPABASE_URL}/rest/v1/artigos",
        headers={**_hdrs(), "Prefer": "return=minimal"},
        params={"doc_id": f"eq.{doc_id}"},
        json={"resumo_markdown": resumo},
        timeout=20)
    return r.status_code in (200, 204)


def _processar(doc_id: str):
    resumo = _extrair_resumo(doc_id)
    if not resumo:
        return "skip", "sem conteúdo no analysis.md"
    if _patch_supabase(doc_id, resumo):
        return "ok", len(resumo)
    return "erro", "falha no PATCH"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=9999)
    args = parser.parse_args()

    if not SUPABASE_URL or not SUPABASE_KEY:
        print("❌ SUPABASE_URL/SUPABASE_SERVICE_KEY não configurados")
        sys.exit(1)

    print(f"\n{'='*60}")
    print("CardioDaily — Sync resumo_markdown (analysis.md → Supabase)")
    print("💡 Zero tokens — só leitura de arquivos locais")
    if args.dry_run:
        print("⚠️  DRY-RUN")
    print(f"{'='*60}\n")

    print("📋 Buscando artigos sem resumo_markdown no Supabase...")
    artigos = _buscar_sem_resumo(args.limit)
    print(f"   → {len(artigos)} artigos sem resumo\n")

    if args.dry_run:
        extraiveis = 0
        for a in artigos[:50]:
            resumo = _extrair_resumo(a["doc_id"])
            if resumo:
                extraiveis += 1
        print(f"   Extraíveis (amostra 50): {extraiveis}/50")
        # Mostrar exemplo
        for a in artigos[:3]:
            resumo = _extrair_resumo(a["doc_id"])
            if resumo:
                print(f"\n   {a['doc_id']}:")
                print(f"   {resumo[:200]}...")
                break
        print("\nDry-run — nada alterado.")
        return

    ok = sem_md = erros = 0
    lock = threading.Lock()
    done = [0]
    t0 = time.time()

    with ThreadPoolExecutor(max_workers=10) as ex:
        futures = {ex.submit(_processar, a["doc_id"]): a["doc_id"] for a in artigos}
        for fut in as_completed(futures):
            status, payload = fut.result()
            with lock:
                done[0] += 1
                n = done[0]
            if status == "ok":
                with lock: ok += 1
                if n % 100 == 0:
                    elapsed = time.time() - t0
                    print(f"  [{n}/{len(artigos)}] {ok} atualizados — {elapsed/60:.1f}min")
            elif status == "skip":
                with lock: sem_md += 1
            else:
                with lock: erros += 1

    elapsed = time.time() - t0
    print(f"\n{'='*60}")
    print(f"✅ {ok} resumos sincronizados | {sem_md} sem analysis.md | {erros} erros")
    print(f"   Tempo: {elapsed:.0f}s")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
