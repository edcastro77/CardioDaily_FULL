#!/usr/bin/env python3
"""
scripts/extrair_ganchos.py
==========================

Gera o campo `gancho_lista` (TEXT, máx 90 chars) para cada artigo do Supabase
a partir do `analysis.md` local — usando Gemini 2.0 Flash.

O gancho_lista é a frase curta usada nas listas WhatsApp do CardioDaily.
Formato canônico: [QUALIDADE/DESENHO] · [BOLA NA REDE PRÁTICA]

Exemplos de gancho válido:
  - "RCT bem-feito · muda conduta em obeso diabético com IC"
  - "Resultado neutro · pode parar de prescrever rotineiramente"
  - "Meta robusta · prescrição segura, sem surpresa"
  - "Direcional mas com surrogate · esperar desfecho duro"

Custo estimado: ~US$ 0,0001 por artigo. 2.155 artigos = ~US$ 0,22 total.

Uso:
    python3 scripts/extrair_ganchos.py --teste                    # 10 artigos, não salva
    python3 scripts/extrair_ganchos.py --nota-min 7 --apenas-vazios --workers 5
    python3 scripts/extrair_ganchos.py --nota-min 7 --dry-run     # preview

Regras (LEIS DE OPERAÇÃO):
  - Para Gemini: system_msg=None, prompt + conteúdo juntos em contents.
  - `--apenas-vazios` é o default: nunca sobrescreve campo já preenchido.
  - Logs vão para archive/logs_operacionais/ — nunca para a raiz.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

import httpx
from google import genai
from google.genai import types

# Carregar .env
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")
except ImportError:
    pass

# -----------------------------------------------------------------------------
# Config
# -----------------------------------------------------------------------------
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")

CORPUS_DIR = Path(__file__).parent.parent / "outputs" / "corpus"
LOG_DIR = Path(__file__).parent.parent / "archive" / "logs_operacionais"
LOG_DIR.mkdir(parents=True, exist_ok=True)

MODELO = "gemini-3.6-flash"
MAX_CHARS_GANCHO = 90

if not (SUPABASE_URL and SUPABASE_SERVICE_KEY and GOOGLE_API_KEY):
    print("ERRO: defina SUPABASE_URL, SUPABASE_SERVICE_KEY e GOOGLE_API_KEY no .env", file=sys.stderr)
    sys.exit(1)

# -----------------------------------------------------------------------------
# Prompt
# -----------------------------------------------------------------------------
PROMPT_GANCHO = """Tarefa: escrever UMA frase de gancho sobre este artigo médico.

FORMATO OBRIGATÓRIO (exatamente assim, numa linha só):
TIPO · IMPACTO PRÁTICO

Onde:
- TIPO = tipo do estudo: RCT bem-feito / RCT com surrogate / Meta robusta / Meta heterogênea / Observacional grande / Sub-análise / Resultado neutro / Direcional / Reposicionamento
- · = separador literal (ponto alto)
- IMPACTO PRÁTICO = o que o cardiologista precisa saber/fazer (telegráfico)

Exemplos CORRETOS:
RCT bem-feito · muda conduta em IC com FEVE reduzida
Meta robusta · confirma dose padrão de estatina pós-SCA
Resultado neutro · não usar rotineiramente em FA paroxística
Observacional grande · reforça indicação em idosos com DRC
Direcional · esperar desfecho duro antes de mudar prática

Regras:
- Máximo 90 caracteres TOTAL
- Sem ponto final, sem aspas, sem markdown, sem emoji
- Voz ativa, sem "interessante", "importante", "promissor"
- Não citar autores, nome da revista ou do estudo

Artigo:
---
{analysis_md}
---

Responda com UMA linha apenas, exatamente no formato: TIPO · IMPACTO PRÁTICO"""

# -----------------------------------------------------------------------------
# Supabase helpers
# -----------------------------------------------------------------------------
def supabase_headers():
    return {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }

def buscar_artigos(nota_min: int, apenas_vazios: bool, limite: int | None) -> list[dict]:
    url = f"{SUPABASE_URL}/rest/v1/artigos"
    params = {
        "select": "doc_id,titulo,revista,nota_aplicabilidade,gancho_lista",
        "nota_aplicabilidade": f"gte.{nota_min}",
        "order": "nota_aplicabilidade.desc,created_at.desc",
    }
    if apenas_vazios:
        params["gancho_lista"] = "is.null"
    if limite:
        params["limit"] = str(limite)

    r = httpx.get(url, headers=supabase_headers(), params=params, timeout=60)
    r.raise_for_status()
    return r.json()

def patch_gancho(doc_id: str, gancho: str) -> bool:
    url = f"{SUPABASE_URL}/rest/v1/artigos"
    params = {"doc_id": f"eq.{doc_id}"}
    r = httpx.patch(url, headers=supabase_headers(), params=params,
                    json={"gancho_lista": gancho}, timeout=30)
    return r.status_code in (200, 204)

# -----------------------------------------------------------------------------
# Analysis.md loader — usa corpus canônico do projeto
# -----------------------------------------------------------------------------
def ler_analysis_md(doc_id: str) -> str | None:
    candidatos = [
        CORPUS_DIR / doc_id / "analysis.md",
        CORPUS_DIR / doc_id / "analise.md",
    ]
    for p in candidatos:
        if p.exists():
            try:
                return p.read_text(encoding="utf-8", errors="ignore")[:8000]
            except Exception as e:
                print(f"  ⚠️  Erro lendo {p}: {e}", file=sys.stderr)
                return None
    return None

# -----------------------------------------------------------------------------
# Gemini
# -----------------------------------------------------------------------------
client = genai.Client(api_key=GOOGLE_API_KEY)

def gerar_gancho_via_gemini(analysis_md: str) -> str | None:
    prompt = PROMPT_GANCHO.format(analysis_md=analysis_md)
    try:
        resp = client.models.generate_content(
            model=MODELO,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.2,
                max_output_tokens=500,
            ),
        )
        texto = (resp.text or "").strip()
    except Exception as e:
        print(f"  ❌ Gemini erro: {e}", file=sys.stderr)
        return None

    texto = texto.split("\n")[0].strip()
    texto = texto.strip('"').strip("'").rstrip(".")
    texto = texto.replace("**", "")

    if not texto or "·" not in texto:
        return None
    if len(texto) > MAX_CHARS_GANCHO:
        antes, sep, depois = texto.partition("·")
        depois = depois.strip()
        sobra = MAX_CHARS_GANCHO - len(antes.strip()) - 3
        if sobra > 10:
            depois = depois[:sobra].rstrip(" ,;:.-")
            texto = f"{antes.strip()} · {depois}"
        else:
            return None

    return texto

# -----------------------------------------------------------------------------
# Worker
# -----------------------------------------------------------------------------
def processar_artigo(artigo: dict, dry_run: bool) -> tuple[str, str | None, str]:
    doc_id = artigo["doc_id"]
    md = ler_analysis_md(doc_id)
    if not md:
        return (doc_id, None, "sem_analysis_md")

    gancho = gerar_gancho_via_gemini(md)
    if not gancho:
        return (doc_id, None, "gancho_invalido")

    if dry_run:
        return (doc_id, gancho, "dry_run")

    ok = patch_gancho(doc_id, gancho)
    return (doc_id, gancho, "ok" if ok else "erro_patch")

# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------
def main():
    raise SystemExit(
        "\n⛔ extrair_ganchos APOSENTADO — escrevia gancho_lista no Supabase por fora do PORTÃO ÚNICO (LEI 5).\n"
        "   O gancho_lista já é gerado pelo portão (ficha_site). Pra (re)gerar: python src/rodar_em_blocos.py ARTIGOS/CLASSIFICADOS\n")

    ap = argparse.ArgumentParser()
    ap.add_argument("--nota-min", type=int, default=7)
    ap.add_argument("--apenas-vazios", action="store_true", default=True)
    ap.add_argument("--reprocessar-tudo", action="store_true")
    ap.add_argument("--teste", action="store_true", help="10 artigos, não salva")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--workers", type=int, default=5)
    ap.add_argument("--limite", type=int, default=5000, help="Limite de artigos (default 5000)")
    args = ap.parse_args()

    apenas_vazios = not args.reprocessar_tudo
    if args.teste:
        args.dry_run = True
        args.limite = 10

    print(f"\n🔎 Buscando artigos no Supabase (nota ≥ {args.nota_min}, apenas_vazios={apenas_vazios}, limite={args.limite})...")
    artigos = buscar_artigos(args.nota_min, apenas_vazios, args.limite)
    print(f"   {len(artigos)} artigos a processar.")

    if not artigos:
        print("Nada a fazer.")
        return

    if args.dry_run:
        print("⚠️  DRY-RUN: nada será salvo no Supabase.")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = LOG_DIR / f"ganchos_{ts}.jsonl"

    contadores = {"ok": 0, "dry_run": 0, "sem_analysis_md": 0,
                  "gancho_invalido": 0, "erro_patch": 0}
    inicio = time.time()

    with ThreadPoolExecutor(max_workers=args.workers) as ex, open(log_path, "w") as flog:
        futs = {ex.submit(processar_artigo, a, args.dry_run): a for a in artigos}
        for i, fut in enumerate(as_completed(futs), 1):
            doc_id, gancho, status = fut.result()
            contadores[status] = contadores.get(status, 0) + 1
            flog.write(json.dumps({"doc_id": doc_id, "gancho": gancho, "status": status}) + "\n")
            if i % 20 == 0 or args.teste or args.dry_run:
                preview = (gancho or "—")[:80]
                print(f"  [{i:>4}/{len(artigos)}] {status:<18} {doc_id[:30]:<30} {preview}")

    dur = time.time() - inicio
    print("\n" + "=" * 70)
    print(f"📊 Resultado em {dur:.1f}s")
    for k, v in contadores.items():
        if v:
            print(f"  {k:<20} {v}")
    print(f"  Log JSONL: {log_path}")
    print("=" * 70)

    if args.teste:
        print("\n🔬 Modo TESTE concluído. Se aprovado, rode em produção:")
        print(f"   python3 scripts/extrair_ganchos.py --nota-min {args.nota_min} --workers {args.workers}")


if __name__ == "__main__":
    main()
