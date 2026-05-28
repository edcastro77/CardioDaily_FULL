#!/usr/bin/env python3
"""
scripts/gerar_ganchos_abertura.py
==================================

Gera o campo `gancho_abertura` (TEXT, máx 200 chars) para artigos nota >= 8.

É a frase de abertura socrática/provocativa enviada no WhatsApp ANTES do áudio.
Deve despertar curiosidade imediata — não descrever o artigo, mas provocar.

Formato: pergunta ou afirmação de impacto + contexto de 1 linha.
Exemplos:
  "A prevenção secundária pós-cirurgia cardíaca vai mudar. Você já leu a nova diretriz?"
  "O que você prescrevia há 10 anos pode estar prejudicando seu paciente hoje."
  "DAPT por 12 meses no pós-operatório: evidência sólida ou mito bem vestido?"

Uso:
    python3 scripts/gerar_ganchos_abertura.py --teste
    python3 scripts/gerar_ganchos_abertura.py --nota-min 8 --apenas-vazios
    python3 scripts/gerar_ganchos_abertura.py --nota-min 8 --reprocessar-tudo
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

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")
except ImportError:
    pass

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")

CORPUS_DIR = Path(__file__).parent.parent / "outputs" / "corpus"
LOG_DIR = Path(__file__).parent.parent / "archive" / "logs_operacionais"
LOG_DIR.mkdir(parents=True, exist_ok=True)

MODELO = "gemini-2.5-flash"
MAX_CHARS = 200

if not (SUPABASE_URL and SUPABASE_SERVICE_KEY and GOOGLE_API_KEY):
    print("ERRO: defina SUPABASE_URL, SUPABASE_SERVICE_KEY e GOOGLE_API_KEY no .env", file=sys.stderr)
    sys.exit(1)

# -----------------------------------------------------------------------------
# Prompt
# -----------------------------------------------------------------------------
PROMPT = """Você é o CardioDaily, sistema de curadoria científica para cardiologistas brasileiros.

Tarefa: escrever UMA frase de abertura provocativa para enviar no WhatsApp antes do áudio deste artigo.

OBJETIVO: fazer o cardiologista querer ouvir o áudio imediatamente. Não é um resumo — é um gancho emocional e intelectual.

FORMATO: 1 a 2 frases. Pode ser:
- Pergunta socrática que desafia a prática atual
- Afirmação de ruptura ("O que você fazia até hoje pode estar errado")
- Revelação de contradição entre evidência e prática
- Provocação de identidade profissional

REGRAS:
- Máximo 200 caracteres TOTAL
- Sem emoji, sem markdown, sem aspas
- Sem citar autores, nome do estudo ou revista
- Voz direta, tom colega-para-colega (não didático, não comercial)
- Nunca dizer "importante", "interessante", "promissor"
- Pode terminar com ponto de interrogação ou de exclamação

EXEMPLOS CORRETOS:
A prevenção secundária pós-cirurgia vai mudar. Você vai participar dessa mudança ou não?
DAPT por 12 meses no pós-operatório: evidência sólida ou mito bem vestido?
O que prescrevemos há 10 anos pode estar prejudicando o paciente de hoje.
Essa diretriz inverte o que parecia óbvio. Vale ouvir antes de opinar.

EXEMPLOS ERRADOS (nunca fazer):
"Estudo importante sobre anticoagulação" — descritivo, sem impacto
"Novidade promissora na área de arritmias" — genérico, palavras proibidas
"Artigo do NEJM mostra que..." — cita fonte, não é gancho

Artigo:
---
{analysis_md}
---

Responda com UMA ou DUAS frases apenas, sem formatação."""

# -----------------------------------------------------------------------------
# Supabase helpers
# -----------------------------------------------------------------------------
def _headers():
    return {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }

def buscar_artigos(nota_min: int, apenas_vazios: bool, limite: int) -> list[dict]:
    params = {
        "select": "doc_id,titulo,nota_aplicabilidade,gancho_abertura",
        "nota_aplicabilidade": f"gte.{nota_min}",
        "order": "nota_aplicabilidade.desc,created_at.desc",
        "limit": str(limite),
    }
    if apenas_vazios:
        params["gancho_abertura"] = "is.null"

    r = httpx.get(f"{SUPABASE_URL}/rest/v1/artigos", headers=_headers(), params=params, timeout=60)
    r.raise_for_status()
    return r.json()

def patch_gancho(doc_id: str, gancho: str) -> bool:
    r = httpx.patch(
        f"{SUPABASE_URL}/rest/v1/artigos",
        headers=_headers(),
        params={"doc_id": f"eq.{doc_id}"},
        json={"gancho_abertura": gancho},
        timeout=30,
    )
    return r.status_code in (200, 204)

def ler_analysis_md(doc_id: str) -> str | None:
    for nome in ("analysis.md", "analise.md"):
        p = CORPUS_DIR / doc_id / nome
        if p.exists():
            try:
                return p.read_text(encoding="utf-8", errors="ignore")[:6000]
            except Exception:
                return None
    return None

# -----------------------------------------------------------------------------
# Gemini
# -----------------------------------------------------------------------------
client = genai.Client(api_key=GOOGLE_API_KEY)

def gerar_gancho(analysis_md: str) -> str | None:
    prompt = PROMPT.format(analysis_md=analysis_md)
    try:
        resp = client.models.generate_content(
            model=MODELO,
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0.4, max_output_tokens=500),
        )
        texto = (resp.text or "").strip()
    except Exception as e:
        print(f"  Gemini erro: {e}", file=sys.stderr)
        return None

    # Limpar markdown residual
    texto = texto.strip('"').strip("'").replace("**", "").replace("*", "")
    # Máx 2 frases
    frases = [f.strip() for f in texto.replace("\n", " ").split(".") if f.strip()]
    if len(frases) > 2:
        texto = ". ".join(frases[:2]) + "."

    if len(texto) > MAX_CHARS:
        texto = texto[:MAX_CHARS].rstrip(" ,;:.-") + "."

    if len(texto) < 20:
        return None

    return texto

# -----------------------------------------------------------------------------
# Worker
# -----------------------------------------------------------------------------
def processar(artigo: dict, dry_run: bool) -> tuple[str, str | None, str]:
    doc_id = artigo["doc_id"]
    md = ler_analysis_md(doc_id)
    if not md:
        return (doc_id, None, "sem_analysis_md")

    gancho = gerar_gancho(md)
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
    ap = argparse.ArgumentParser()
    ap.add_argument("--nota-min", type=int, default=8)
    ap.add_argument("--apenas-vazios", action="store_true", default=True)
    ap.add_argument("--reprocessar-tudo", action="store_true")
    ap.add_argument("--teste", action="store_true", help="5 artigos, não salva")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--limite", type=int, default=2000)
    args = ap.parse_args()

    apenas_vazios = not args.reprocessar_tudo
    if args.teste:
        args.dry_run = True
        args.limite = 5

    print(f"\nBuscando artigos (nota >= {args.nota_min}, apenas_vazios={apenas_vazios}, limite={args.limite})...")
    artigos = buscar_artigos(args.nota_min, apenas_vazios, args.limite)
    print(f"   {len(artigos)} artigos a processar.")

    if not artigos:
        print("Nada a fazer.")
        return

    if args.dry_run:
        print("DRY-RUN: nada será salvo.")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = LOG_DIR / f"ganchos_abertura_{ts}.jsonl"
    contadores: dict[str, int] = {}
    inicio = time.time()

    with ThreadPoolExecutor(max_workers=args.workers) as ex, open(log_path, "w") as flog:
        futs = {ex.submit(processar, a, args.dry_run): a for a in artigos}
        for i, fut in enumerate(as_completed(futs), 1):
            doc_id, gancho, status = fut.result()
            contadores[status] = contadores.get(status, 0) + 1
            flog.write(json.dumps({"doc_id": doc_id, "gancho": gancho, "status": status}) + "\n")
            if i % 10 == 0 or args.dry_run or i <= 5:
                preview = (gancho or "—")[:90]
                print(f"  [{i:>4}/{len(artigos)}] {status:<18} {preview}")

    dur = time.time() - inicio
    print(f"\nResultado em {dur:.1f}s")
    for k, v in contadores.items():
        if v:
            print(f"  {k:<20} {v}")
    print(f"  Log: {log_path}")

    if args.teste:
        print("\nModo TESTE concluído. Se aprovado:")
        print(f"   python3 scripts/gerar_ganchos_abertura.py --nota-min {args.nota_min} --workers {args.workers}")


if __name__ == "__main__":
    main()
