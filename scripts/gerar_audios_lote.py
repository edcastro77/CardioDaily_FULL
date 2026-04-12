#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CardioDaily — Geração de Áudios em Lote
Busca no Supabase artigos elegíveis sem áudio e gera MP3 via OpenAI TTS.

Elegíveis: nota_aplicabilidade >= 8, data_publicacao >= 2026-02-01,
           tipo_estudo in (original, metanalise, revisao), caminho_audio IS NULL

Uso:
    python3 scripts/gerar_audios_lote.py              # roda todos os elegíveis
    python3 scripts/gerar_audios_lote.py --dry-run    # só lista, não gera
    python3 scripts/gerar_audios_lote.py --limite 10  # gera no máximo 10
    python3 scripts/gerar_audios_lote.py --desde 2026-03-01  # data customizada
"""

import argparse
import os
import sys
import time
import json
import requests
from datetime import datetime
from pathlib import Path

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
OPENAI_KEY    = os.getenv("OPENAI_API_KEY", "")
CORPUS_DIR    = _ROOT / "outputs" / "corpus"
AUDIO_DIR     = _ROOT / "outputs" / "audio_lote"
BUCKET        = "podcasts"
NOTA_MIN      = 8
DATA_DESDE    = "2026-02-01"
TIPOS_VALIDOS = ("original", "metanalise", "revisao", "meta_analise", "revisao_geral")

# ─── Supabase helpers ─────────────────────────────────────────────────────────

def _sb_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }


def buscar_elegíveis(desde: str, limite: int) -> list[dict]:
    """Busca artigos elegíveis sem áudio no Supabase."""
    params = {
        "select": "doc_id,titulo,tipo_estudo,nota_aplicabilidade,data_publicacao",
        "caminho_audio": "is.null",
        "nota_aplicabilidade": f"gte.{NOTA_MIN}",
        "data_publicacao": f"gte.{desde}",
        "order": "data_publicacao.desc",
        "limit": str(limite),
    }
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/artigos",
        headers=_sb_headers(),
        params=params,
        timeout=30,
    )
    if r.status_code != 200:
        print(f"❌ Erro Supabase: {r.status_code} — {r.text[:300]}")
        return []
    artigos = r.json()
    # Filtrar por tipo_estudo (Supabase não tem IN fácil via params simples)
    return [a for a in artigos if (a.get("tipo_estudo") or "").lower() in TIPOS_VALIDOS]


def atualizar_caminho_audio(doc_id: str, url: str) -> bool:
    """Atualiza caminho_audio no Supabase. Retry 3x com timeout aumentado."""
    for tentativa in range(1, 4):
        try:
            r = requests.patch(
                f"{SUPABASE_URL}/rest/v1/artigos?doc_id=eq.{doc_id}",
                headers={**_sb_headers(), "Prefer": "return=minimal"},
                json={"caminho_audio": url},
                timeout=60,
            )
            if r.status_code in (200, 204):
                return True
            print(f"   ⚠️  Supabase HTTP {r.status_code} — tentativa {tentativa}/3")
        except requests.exceptions.Timeout:
            print(f"   ⚠️  Timeout Supabase — tentativa {tentativa}/3")
        if tentativa < 3:
            time.sleep(5)
    return False


def upload_mp3(doc_id: str, mp3_path: Path) -> str | None:
    """Faz upload do MP3 ao bucket 'podcasts'. Retorna URL pública ou None."""
    objeto = f"{doc_id}.mp3"
    url_upload = f"{SUPABASE_URL}/storage/v1/object/{BUCKET}/{objeto}"
    url_publica = f"{SUPABASE_URL}/storage/v1/object/public/{BUCKET}/{objeto}"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "audio/mpeg",
        "x-upsert": "true",
    }
    with open(mp3_path, "rb") as f:
        r = requests.post(url_upload, headers=headers, data=f, timeout=120)
    if r.status_code in (200, 201):
        return url_publica
    print(f"   ⚠️  Upload falhou: {r.status_code} — {r.text[:200]}")
    return None

# ─── Script de podcast ────────────────────────────────────────────────────────

def gerar_script(analysis_text: str, titulo: str, doc_id: str, nota: int) -> str:
    """Gera script de podcast via GPT-4o a partir da análise."""
    from openai import OpenAI
    client = OpenAI(api_key=OPENAI_KEY)

    prompt = f"""Você é o Dr. CardioDaily. Crie um SCRIPT DE PODCAST objetivo e direto baseado na análise abaixo.

INFORMAÇÕES DO ARTIGO:
- Título: {titulo}
- Doc ID: {doc_id}
- Score de Aplicabilidade Clínica: {nota}/10

ANÁLISE COMPLETA:
{analysis_text}

---

INSTRUÇÕES PARA O SCRIPT DE PODCAST:

1. ABERTURA (15-20 segundos)
   - "Olá, aqui é o Dr. CardioDaily."
   - Diga em UMA frase o que o estudo investigou. Sem rodeios.

2. CORPO (5-7 minutos)
   - Identificação do artigo (título, revista, ano)
   - Contexto clínico em 2-3 frases
   - Pergunta do estudo: objetiva e clara
   - Desenho e amostra: tipo, N, seguimento, desfechos
   - Resultados principais: NÚMEROS CONCRETOS (HR, IC95%, NNT, p-valor)
   - Interpretação clínica: o que muda na prática?
   - Limitações reais que comprometem validade ou generalização
   - Conflitos de interesse relevantes (se houver)

3. FECHAMENTO (15-20 segundos)
   - UM takeaway acionável
   - "Até o próximo, aqui no CardioDaily."

TOM: objetivo e direto, como attending explicando para fellow durante visita.
PROIBIDO: "vamos mergulhar", hipérboles, sensacionalismo.
OBRIGATÓRIO: números concretos, tom crítico quando necessário.

FORMATO: texto de fala, frases curtas, 1.200-1.500 palavras.
NÃO inclua marcações de tempo ou indicações técnicas.
Escreva APENAS o texto que será falado.

Crie o script agora:"""

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=6000,
    )
    return response.choices[0].message.content

# ─── TTS ──────────────────────────────────────────────────────────────────────

def gerar_mp3(script: str, output_path: Path) -> bool:
    """Gera MP3 via OpenAI TTS-HD, com chunking se necessário."""
    import re as _re

    voice = os.getenv("OPENAI_TTS_VOICE", "onyx")
    model = os.getenv("OPENAI_TTS_MODEL", "tts-1-hd")
    speed = float(os.getenv("OPENAI_TTS_SPEED", "1.0"))

    # Limpar markdown para áudio
    texto = _re.sub(r'#{1,6}\s+.*$', '', script, flags=_re.MULTILINE)
    texto = _re.sub(r'\*\*([^*]+)\*\*', r'\1', texto)
    texto = _re.sub(r'\*([^*]+)\*', r'\1', texto)
    texto = _re.sub(r'\n{3,}', '\n\n', texto)
    texto = texto.strip()

    max_chars = 4096
    headers = {
        "Authorization": f"Bearer {OPENAI_KEY}",
        "Content-Type": "application/json",
    }

    if len(texto) <= max_chars:
        chunks = [texto]
    else:
        # Dividir por parágrafos
        paragrafos = texto.split('\n\n')
        chunks, atual = [], ''
        for p in paragrafos:
            p = p.strip()
            if not p:
                continue
            if len(atual) + len(p) + 2 <= max_chars:
                atual = (atual + '\n\n' + p).strip()
            else:
                if atual:
                    chunks.append(atual)
                atual = p
        if atual:
            chunks.append(atual)

    all_bytes = []
    for i, chunk in enumerate(chunks, 1):
        r = requests.post(
            "https://api.openai.com/v1/audio/speech",
            headers=headers,
            json={"model": model, "input": chunk, "voice": voice,
                  "response_format": "mp3", "speed": speed},
            timeout=300,
        )
        if r.status_code != 200:
            print(f"   ❌ TTS chunk {i}: HTTP {r.status_code} — {r.text[:200]}")
            return False
        all_bytes.append(r.content)
        if len(chunks) > 1:
            time.sleep(0.5)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as f:
        for b in all_bytes:
            f.write(b)
    return True

# ─── Processador de artigo ────────────────────────────────────────────────────

def processar_artigo(artigo: dict, dry_run: bool) -> str:
    """
    Processa um artigo: gera script → MP3 → upload → atualiza Supabase.
    Retorna status: 'ok' | 'sem_analise' | 'erro_script' | 'erro_tts' | 'erro_upload'
    """
    doc_id = artigo["doc_id"]
    titulo = artigo.get("titulo") or doc_id
    nota   = artigo.get("nota_aplicabilidade", 0)
    tipo   = artigo.get("tipo_estudo", "")
    data   = artigo.get("data_publicacao", "")

    print(f"\n{'─'*55}")
    print(f"📄 {doc_id}")
    print(f"   Título: {titulo[:80]}{'...' if len(titulo) > 80 else ''}")
    print(f"   Tipo: {tipo} | Nota: {nota}/10 | Data: {data}")

    if dry_run:
        print("   [dry-run] — pulando geração")
        return "dry_run"

    # ── 1. Ler analysis.md do corpus ──────────────────────────────────────
    corpus_path = CORPUS_DIR / doc_id / "analysis.md"
    if not corpus_path.exists():
        print(f"   ⚠️  analysis.md não encontrado — pulando")
        return "sem_analise"

    analysis_text = corpus_path.read_text(encoding="utf-8")
    print(f"   📖 analysis.md: {len(analysis_text):,} chars")

    # ── 2. Verificar se já tem MP3 local (evita regerar) ──────────────────
    mp3_path = AUDIO_DIR / f"{doc_id}.mp3"
    if mp3_path.exists():
        print(f"   ♻️  MP3 já existe localmente — pulando geração, fazendo upload direto")
    else:
        # ── 3. Gerar script GPT-4o ─────────────────────────────────────────
        print(f"   🤖 Gerando script (GPT-4o)…")
        try:
            script = gerar_script(analysis_text, titulo, doc_id, nota)
            print(f"   ✅ Script: {len(script):,} chars")
        except Exception as e:
            print(f"   ❌ Erro no script: {e}")
            return "erro_script"

        # Salvar script localmente
        script_path = AUDIO_DIR / f"{doc_id}_script.txt"
        script_path.parent.mkdir(parents=True, exist_ok=True)
        script_path.write_text(script, encoding="utf-8")

        # ── 4. Gerar MP3 ──────────────────────────────────────────────────
        print(f"   🔊 Gerando MP3 (TTS-HD)…")
        ok = gerar_mp3(script, mp3_path)
        if not ok or not mp3_path.exists():
            print(f"   ❌ Falha na geração do MP3")
            return "erro_tts"
        print(f"   ✅ MP3: {mp3_path.stat().st_size // 1024} KB")

    # ── 5. Upload Supabase Storage ────────────────────────────────────────
    print(f"   ☁️  Upload para bucket '{BUCKET}'…")
    url = upload_mp3(doc_id, mp3_path)
    if not url:
        return "erro_upload"
    print(f"   ✅ URL: {url}")

    # ── 6. Atualizar Supabase ─────────────────────────────────────────────
    ok = atualizar_caminho_audio(doc_id, url)
    if ok:
        print(f"   🗄️  caminho_audio atualizado no Supabase")
    else:
        print(f"   ⚠️  Falha ao atualizar Supabase (URL já salva: {url})")

    return "ok"

# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="CardioDaily — Áudios em Lote")
    parser.add_argument("--dry-run",  action="store_true", help="Lista elegíveis sem gerar")
    parser.add_argument("--limite",   type=int, default=200, help="Máx de artigos a processar (padrão: 200)")
    parser.add_argument("--desde",    type=str, default=DATA_DESDE, help=f"Data mínima ISO (padrão: {DATA_DESDE})")
    args = parser.parse_args()

    if not SUPABASE_URL or not SUPABASE_KEY:
        print("❌ SUPABASE_URL / SUPABASE_SERVICE_KEY não configurados no .env")
        sys.exit(1)
    if not OPENAI_KEY and not args.dry_run:
        print("❌ OPENAI_API_KEY não configurada no .env")
        sys.exit(1)

    print(f"\n{'='*55}")
    print(f"🎙️  CardioDaily — Geração de Áudios em Lote")
    print(f"   📅 {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    print(f"   📆 Desde: {args.desde} | Nota ≥ {NOTA_MIN} | Limite: {args.limite}")
    print(f"   {'[DRY-RUN]' if args.dry_run else 'MODO REAL — gerando MP3s'}")
    print(f"{'='*55}\n")

    # Buscar elegíveis
    print("🔍 Buscando artigos elegíveis no Supabase…")
    artigos = buscar_elegíveis(args.desde, args.limite)
    print(f"   {len(artigos)} artigos encontrados\n")

    if not artigos:
        print("✅ Nenhum artigo elegível sem áudio. Tudo em dia!")
        return

    # Listar elegíveis
    print(f"{'#':>3}  {'doc_id':<30} {'tipo':<15} {'nota':>4}  {'data'}")
    print("─" * 70)
    for i, a in enumerate(artigos, 1):
        print(f"{i:>3}  {a['doc_id']:<30} {(a.get('tipo_estudo') or ''):<15} "
              f"{(a.get('nota_aplicabilidade') or 0):>4}  {a.get('data_publicacao','')}")

    if args.dry_run:
        print(f"\n✅ Dry-run concluído. {len(artigos)} artigos seriam processados.")
        return

    # Processar
    print(f"\n{'='*55}")
    print(f"🚀 Iniciando geração de {len(artigos)} áudio(s)…")
    print(f"{'='*55}")

    stats = {"ok": 0, "sem_analise": 0, "erro_script": 0, "erro_tts": 0, "erro_upload": 0}

    for i, artigo in enumerate(artigos, 1):
        print(f"\n[{i}/{len(artigos)}]", end="")
        status = processar_artigo(artigo, dry_run=False)
        stats[status] = stats.get(status, 0) + 1
        if i < len(artigos):
            time.sleep(2)  # pausa entre artigos

    print(f"\n\n{'='*55}")
    print(f"✅ LOTE CONCLUÍDO")
    print(f"   ✅ Gerados com sucesso: {stats['ok']}")
    print(f"   ⚠️  Sem analysis.md:    {stats['sem_analise']}")
    print(f"   ❌ Erro script:         {stats['erro_script']}")
    print(f"   ❌ Erro TTS:            {stats['erro_tts']}")
    print(f"   ❌ Erro upload:         {stats['erro_upload']}")
    print(f"{'='*55}\n")


if __name__ == "__main__":
    main()
