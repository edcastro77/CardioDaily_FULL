#!/usr/bin/env python3
"""
CardioDaily — Gerar podcasts para revisões/guidelines que foram analisadas sem áudio.

Busca no Supabase artigos do tipo revisão/guideline com:
  - nota_aplicabilidade >= 8
  - caminho_audio IS NULL ou vazio

Para cada um, gera o podcast e faz upload automático.

Uso:
  python3 scripts/reparar_podcasts_revisoes.py --dry-run   # só lista, não gera
  python3 scripts/reparar_podcasts_revisoes.py             # gera e sobe
  python3 scripts/reparar_podcasts_revisoes.py --nota 7    # nota mínima diferente
  python3 scripts/reparar_podcasts_revisoes.py --doc-id <id>  # só 1 artigo
"""

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

import requests

SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY", "")
CORPUS_DIR   = ROOT / "outputs" / "corpus"

TIPOS_REVISAO = (
    "revisao_geral",
    "revisao_sistematica_meta_analise",
    "guideline",
    "ponto_de_vista",
)


# ── Supabase helpers ──────────────────────────────────────────────────────────

def _sb_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }


def buscar_revisoes_sem_podcast(nota_min: int, doc_id_filtro: str | None) -> list[dict]:
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("❌ SUPABASE_URL / SUPABASE_KEY não configurados.")
        sys.exit(1)

    tipos_query = ",".join(f'"{t}"' for t in TIPOS_REVISAO)
    url = (
        f"{SUPABASE_URL}/rest/v1/artigos"
        f"?select=doc_id,titulo,tipo_estudo,nota_aplicabilidade,caminho_audio,doi"
        f"&tipo_estudo=in.({tipos_query})"
        f"&nota_aplicabilidade=gte.{nota_min}"
        f"&caminho_audio=is.null"
        f"&order=nota_aplicabilidade.desc"
    )
    if doc_id_filtro:
        url += f"&doc_id=eq.{doc_id_filtro}"

    r = requests.get(url, headers=_sb_headers(), timeout=30)
    if r.status_code != 200:
        print(f"❌ Erro ao consultar Supabase: {r.status_code} {r.text[:200]}")
        sys.exit(1)

    return r.json()


def upload_podcast(doc_id: str, mp3_path: str) -> str | None:
    bucket = "podcasts"
    objeto = f"{doc_id}.mp3"
    url_publica = f"{SUPABASE_URL}/storage/v1/object/public/{bucket}/{objeto}"

    try:
        with open(mp3_path, "rb") as f:
            dados = f.read()
        h = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "audio/mpeg",
            "x-upsert": "true",
        }
        r = requests.post(
            f"{SUPABASE_URL}/storage/v1/object/{bucket}/{objeto}",
            headers=h, data=dados, timeout=120,
        )
        if r.status_code not in (200, 201):
            print(f"   ⚠️  Storage upload falhou: {r.status_code} {r.text[:100]}")
            return None

        requests.patch(
            f"{SUPABASE_URL}/rest/v1/artigos?doc_id=eq.{doc_id}",
            headers=_sb_headers(),
            json={"caminho_audio": url_publica},
            timeout=15,
        )
        return url_publica

    except Exception as e:
        print(f"   ⚠️  Erro no upload: {e}")
        return None


# ── Podcast helpers ────────────────────────────────────────────────────────────

def _init_generators():
    try:
        from podcast_script_generator import PodcastScriptGenerator
        script_gen = PodcastScriptGenerator()
    except Exception as e:
        print(f"❌ PodcastScriptGenerator: {e}")
        sys.exit(1)

    audio_gen = None
    try:
        from audio_generator import UnifiedAudioGenerator
        audio_gen = UnifiedAudioGenerator()
        print("✅ UnifiedAudioGenerator inicializado")
    except Exception:
        try:
            from elevenlabs_audio_generator import ElevenLabsAudioGenerator
            audio_gen = ElevenLabsAudioGenerator()
            print("✅ ElevenLabsAudioGenerator inicializado")
        except Exception as e:
            print(f"❌ Gerador de áudio: {e}")
            sys.exit(1)

    return script_gen, audio_gen


def gerar_podcast_para_artigo(doc_id: str, artigo: dict, script_gen, audio_gen, dry_run: bool) -> bool:
    from article_analyzer import extract_podcast_article_title

    artigo_dir = CORPUS_DIR / doc_id
    analysis_file = artigo_dir / "analysis.md"

    if not analysis_file.exists():
        print(f"   ⚠️  analysis.md não encontrado em {artigo_dir}")
        return False

    analysis = analysis_file.read_text(encoding="utf-8")
    titulo = artigo.get("titulo") or ""
    doi = artigo.get("doi") or "N/A"
    nota = artigo.get("nota_aplicabilidade") or 0
    tipo = artigo.get("tipo_estudo") or ""

    podcast_title = extract_podcast_article_title(analysis, doc_id)

    print(f"\n📄 {doc_id}")
    print(f"   Tipo: {tipo} | Nota: {nota}/10")
    print(f"   Título podcast: {podcast_title[:80]}...")

    if dry_run:
        print("   [DRY-RUN] Nenhuma ação tomada.")
        return True

    # Gerar script
    print("   🎤 Gerando script (GPT-4o)...")
    script = script_gen.generate_podcast_script(
        analysis_text=analysis,
        article_title=podcast_title,
        doi=doi,
        score=nota,
    )
    if not script:
        print("   ❌ Script vazio, pulando.")
        return False

    # Salvar script
    audio_dir = ROOT / "outputs" / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    script_path = audio_dir / f"{doc_id}_podcast_script.txt"
    script_path.write_text(script, encoding="utf-8")

    # Gerar áudio
    print("   🎵 Gerando áudio (ElevenLabs)...")
    mp3_path = str(audio_dir / f"{doc_id}_podcast.mp3")
    ok = audio_gen.generate_audio(text=script, output_path=mp3_path)
    if not ok:
        print("   ❌ Falha no áudio.")
        return False

    # Upload
    print("   ☁️  Subindo para Supabase Storage...")
    pub_url = upload_podcast(doc_id, mp3_path)
    if pub_url:
        print(f"   ✅ Podcast publicado: {pub_url}")
        return True
    else:
        print("   ❌ Upload falhou.")
        return False


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Gerar podcasts para revisões sem áudio")
    parser.add_argument("--dry-run", action="store_true", help="Só lista, não gera nada")
    parser.add_argument("--nota", type=int, default=8, metavar="N", help="Nota mínima (padrão: 8)")
    parser.add_argument("--doc-id", type=str, default=None, help="Processar apenas este doc_id")
    args = parser.parse_args()

    print("=" * 60)
    print("CardioDaily — Reparar Podcasts de Revisões")
    print("=" * 60)

    artigos = buscar_revisoes_sem_podcast(args.nota, args.doc_id)

    if not artigos:
        print(f"\n✅ Nenhuma revisão com nota ≥ {args.nota} sem podcast encontrada.")
        return

    print(f"\n🔍 Encontrados: {len(artigos)} artigos para processar\n")
    for a in artigos:
        print(f"   • {a['doc_id']} | {a.get('tipo_estudo')} | nota {a.get('nota_aplicabilidade')} | {(a.get('titulo') or '')[:60]}")

    if args.dry_run:
        print("\n[DRY-RUN] Nenhuma geração realizada. Remova --dry-run para executar.")
        return

    script_gen, audio_gen = _init_generators()

    ok = 0
    fail = 0
    for artigo in artigos:
        doc_id = artigo["doc_id"]
        sucesso = gerar_podcast_para_artigo(doc_id, artigo, script_gen, audio_gen, dry_run=False)
        if sucesso:
            ok += 1
        else:
            fail += 1

    print("\n" + "=" * 60)
    print(f"✅ Sucesso: {ok} | ❌ Falha: {fail}")
    print("=" * 60)


if __name__ == "__main__":
    main()
