#!/usr/bin/env python3
"""
CardioDaily — Backfill de Keywords

Gera keywords para todos os artigos do Supabase que não as têm.
Usa Gemini Flash (rápido e barato) com título + resumo_markdown como entrada.
Atualiza a coluna `keywords` no Supabase.

Uso:
    python3 scripts/backfill_keywords.py --dry-run     # só conta, não processa
    python3 scripts/backfill_keywords.py --limit 100   # processa 100 artigos
    python3 scripts/backfill_keywords.py               # processa todos
    python3 scripts/backfill_keywords.py --ano 2026    # só artigos de 2026
"""

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

import requests

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "src"))

try:
    from dotenv import load_dotenv
    load_dotenv(_ROOT / ".env")
except ImportError:
    pass

SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY", "")
GEMINI_KEY   = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY", "")
CORPUS_DIR   = _ROOT / "outputs" / "corpus"

HDRS_SB = lambda: {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}

PROMPT_KW = """Você é um indexador de literatura médica cardiovascular.

Dado o título e o resumo de um artigo científico, gere de 5 a 10 keywords em inglês, específicas e clinicamente relevantes para indexação.

Retorne APENAS um array JSON. Nenhum texto antes ou depois. Exemplo:
["heart failure", "SGLT2 inhibitors", "ejection fraction", "hospitalization", "mortality"]

Título: {titulo}

Resumo: {resumo}
"""


def _gerar_keywords_gemini(titulo: str, resumo: str) -> list[str]:
    """Chama Gemini Flash para gerar keywords."""
    prompt = PROMPT_KW.replace("{titulo}", titulo[:300]).replace("{resumo}", resumo[:2000])
    resp = requests.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_KEY}",
        json={"contents": [{"parts": [{"text": prompt}]}],
              "generationConfig": {"temperature": 0.1, "maxOutputTokens": 1024}},
        timeout=30,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Gemini {resp.status_code}: {resp.text[:200]}")

    raw = resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
    # Limpar markdown e thinking tags
    raw = re.sub(r'<think>.*?</think>', '', raw, flags=re.DOTALL).strip()
    raw = re.sub(r'```json\s*', '', raw)
    raw = re.sub(r'```\s*', '', raw).strip()
    # Extrair o array JSON
    m = re.search(r'\[.*\]', raw, re.DOTALL)
    if m:
        raw = m.group(0)
    return json.loads(raw)


def _gerar_keywords_do_disco(doc_id: str) -> list[str] | None:
    """Tenta extrair keywords do analysis.json local antes de chamar a API."""
    aj = CORPUS_DIR / doc_id / "analysis.json"
    if not aj.exists():
        return None
    try:
        data = json.loads(aj.read_text(encoding="utf-8", errors="ignore"))
        ana = data.get("analysis", {})
        kw = ana.get("keywords")
        if kw and isinstance(kw, list) and len(kw) >= 3:
            return [str(k) for k in kw if k]
    except Exception:
        pass
    return None


def _atualizar_supabase(doc_id: str, keywords: list[str]) -> bool:
    r = requests.patch(
        f"{SUPABASE_URL}/rest/v1/artigos",
        headers={**HDRS_SB(), "Prefer": "return=minimal"},
        params={"doc_id": f"eq.{doc_id}"},
        json={"keywords": keywords},
        timeout=20,
    )
    return r.status_code in (200, 204)


def _buscar_sem_keywords(ano: str | None, limit: int) -> list[dict]:
    params = {
        "select": "doc_id,titulo,resumo_markdown,tipo_estudo,data_publicacao",
        "keywords": "is.null",
        "resumo_markdown": "not.is.null",  # precisa ter resumo para gerar
        "order": "nota_aplicabilidade.desc.nullslast",
        "limit": str(limit),
    }
    if ano:
        params["data_publicacao"] = f"gte.{ano}-01-01"
    r = requests.get(f"{SUPABASE_URL}/rest/v1/artigos", headers=HDRS_SB(), params=params, timeout=30)
    return r.json() if r.status_code == 200 and isinstance(r.json(), list) else []


def main():
    parser = argparse.ArgumentParser(description="Backfill keywords Supabase")
    parser.add_argument("--dry-run", action="store_true", help="Só conta, não processa")
    parser.add_argument("--limit",   type=int, default=9999, help="Máx artigos a processar")
    parser.add_argument("--ano",     type=str, default=None, help="Filtrar por ano (ex: 2026)")
    args = parser.parse_args()

    if not SUPABASE_URL or not SUPABASE_KEY:
        print("❌ SUPABASE_URL/SUPABASE_SERVICE_KEY não configurados")
        sys.exit(1)

    if not GEMINI_KEY:
        print("❌ GEMINI_API_KEY não configurada")
        sys.exit(1)

    # Contar total sem keywords
    count_params = {"select": "doc_id", "keywords": "is.null"}
    if args.ano:
        count_params["data_publicacao"] = f"gte.{args.ano}-01-01"
    r_count = requests.get(f"{SUPABASE_URL}/rest/v1/artigos",
        headers={**HDRS_SB(), "Prefer": "count=exact", "Range": "0-0"},
        params=count_params, timeout=20)
    total_sem = int(r_count.headers.get("Content-Range", "0/0").split("/")[1])

    print(f"\n{'='*55}")
    print(f"CardioDaily — Backfill Keywords")
    filtro = f"ano={args.ano}" if args.ano else "todos os anos"
    print(f"   Sem keywords ({filtro}): {total_sem:,}")
    print(f"   Limite: {args.limit:,}")
    print(f"   Modo: {'DRY-RUN' if args.dry_run else 'PRODUÇÃO'}")
    print(f"{'='*55}\n")

    if args.dry_run:
        print("Dry-run — nada será alterado.")
        return

    artigos = _buscar_sem_keywords(args.ano, args.limit)
    print(f"📥 {len(artigos)} artigos para processar\n")

    ok = 0
    disco = 0
    api = 0
    erros = 0

    for i, a in enumerate(artigos, 1):
        doc_id  = a["doc_id"]
        titulo  = a.get("titulo") or ""
        resumo  = a.get("resumo_markdown") or ""
        tipo    = a.get("tipo_estudo", "?")
        nota    = a.get("nota_aplicabilidade", "?")

        print(f"[{i:>4}/{len(artigos)}] {doc_id} | {tipo:<12} | nota={nota}", end=" ")

        # 1. Tentar do disco primeiro (grátis)
        kw = _gerar_keywords_do_disco(doc_id)
        fonte = "disco"

        # 2. Fallback: Gemini Flash
        if not kw:
            if not titulo and not resumo:
                print("⏭️  sem título/resumo")
                continue
            try:
                kw = _gerar_keywords_gemini(titulo, resumo)
                fonte = "gemini"
                time.sleep(0.3)  # rate limit gentil
            except Exception as e:
                print(f"❌ {e}")
                erros += 1
                continue

        if not kw:
            print("⏭️  sem resultado")
            continue

        # 3. Salvar no Supabase
        if _atualizar_supabase(doc_id, kw):
            print(f"✅ {fonte} → {kw[:3]}{'...' if len(kw) > 3 else ''}")
            ok += 1
            if fonte == "disco":
                disco += 1
            else:
                api += 1
        else:
            print("❌ falha no update")
            erros += 1

    print(f"\n{'='*55}")
    print(f"✅ Concluído: {ok} atualizados ({disco} do disco + {api} via Gemini) | {erros} erros")
    print(f"{'='*55}\n")


if __name__ == "__main__":
    main()
