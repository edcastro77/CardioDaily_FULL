#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CardioDaily — Radar Diário Automático
Roda 1 tema por dia, ciclando os 13 temas a cada 13 dias.
Busca no PubMed: últimos 14 dias, máximo 50 artigos.
Gera script Gemini + MP3 TTS, faz upload ao bucket 'radar_podcasts',
insere registro na tabela 'radar' do Supabase e envia via WhatsApp.

Uso:
    python3 scripts/run_radar_diario.py             # roda tema do dia
    python3 scripts/run_radar_diario.py --dry-run   # mostra qual tema sem executar
    python3 scripts/run_radar_diario.py --categoria insuficiencia_cardiaca  # força tema
    python3 scripts/run_radar_diario.py --lista     # lista todos os temas
"""

import argparse
import os
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "src"))

try:
    from dotenv import load_dotenv
    load_dotenv(_ROOT / ".env")
except ImportError:
    pass

# ─── 13 temas oficiais (dia 0 → dia 12, repete) ───────────────────────────────
ROTACAO_DIARIA = [
    "doenca_coronariana",       # 1. Coronária/DAC
    "cardio_metabolica",        # 2. Cardiometabólica
    "arritmias",                # 3. Arritmias
    "insuficiencia_cardiaca",   # 4. Insuficiência Cardíaca
    "valvulopatias",            # 5. Valvulopatias
    "miocardiopatias",          # 6. Miocardiopatias
    "intervencao_hemodinamica", # 7. Intervenção/Hemodinâmica
    "cardio_oncologia",         # 8. Cardio-Oncologia
    "cardiobstetrica",          # 9. Cardio-Obstétrica
    "cardio_genomica",          # 10. Cardio-Genômica
    "uti_cardiologica",         # 11. UTI Cardiológica
    "aorta_congenitas",         # 12. Aorta/Congênitas
    "imagem_cardiovascular",    # 13. Imagem Cardiovascular
]

DIAS_CICLO   = len(ROTACAO_DIARIA)  # 13
DIAS_JANELA  = 14   # últimos N dias no PubMed
MAX_ARTIGOS  = 50   # máximo de artigos por busca


def categoria_do_dia(dia_ref: date | None = None) -> str:
    """Retorna a categoria para hoje baseado no dia do ano % 12."""
    d = dia_ref or date.today()
    idx = d.timetuple().tm_yday % DIAS_CICLO
    return ROTACAO_DIARIA[idx]


def _upload_radar_storage(mp3_path: Path, filename: str) -> str | None:
    """Faz upload do MP3 para o Supabase Storage bucket 'radar_podcasts'."""
    import requests
    supabase_url = os.getenv("SUPABASE_URL", "")
    supabase_key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY", "")
    if not supabase_url or not supabase_key:
        print("   ⚠️  SUPABASE_URL / SUPABASE_SERVICE_KEY não configurados — upload ignorado.")
        return None
    try:
        url = f"{supabase_url}/storage/v1/object/radar_podcasts/{filename}"
        headers = {
            "apikey": supabase_key,
            "Authorization": f"Bearer {supabase_key}",
            "Content-Type": "audio/mpeg",
            "x-upsert": "true",
        }
        with open(mp3_path, "rb") as f:
            r = requests.post(url, headers=headers, data=f, timeout=120)
        if r.status_code in (200, 201):
            pub_url = f"{supabase_url}/storage/v1/object/public/radar_podcasts/{filename}"
            print(f"   ☁️  Upload OK: {pub_url}")
            return pub_url
        else:
            print(f"   ⚠️  Upload falhou: HTTP {r.status_code} — {r.text[:200]}")
            return None
    except Exception as e:
        print(f"   ⚠️  Upload exceção: {e}")
        return None


def _inserir_radar_supabase(
    tema: str,
    tema_nome: str,
    data_varredura: str,
    periodo_inicio: str,
    periodo_fim: str,
    resumo_texto: str,
    caminho_podcast: str,
    artigos_analisados: int,
) -> bool:
    """Insere (ou atualiza via upsert) registro na tabela 'radar' do Supabase."""
    import requests
    supabase_url = os.getenv("SUPABASE_URL", "")
    supabase_key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY", "")
    if not supabase_url or not supabase_key:
        print("   ⚠️  SUPABASE_URL / SUPABASE_SERVICE_KEY não configurados — inserção ignorada.")
        return False
    try:
        payload = {
            "tema": tema,
            "data_varredura": data_varredura,
            "periodo_inicio": periodo_inicio,
            "periodo_fim": periodo_fim,
            "resumo_texto": resumo_texto,
            "caminho_podcast": caminho_podcast,
            "artigos_analisados": artigos_analisados,
        }
        url = f"{supabase_url}/rest/v1/radar"
        headers = {
            "apikey": supabase_key,
            "Authorization": f"Bearer {supabase_key}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates",  # upsert via índice único (tema, data_varredura)
        }
        r = requests.post(url, headers=headers, json=payload, timeout=30)
        if r.status_code in (200, 201):
            print(f"   🗄️  Supabase radar OK: {tema} / {data_varredura}")
            return True
        else:
            print(f"   ⚠️  Supabase radar falhou: HTTP {r.status_code} — {r.text[:300]}")
            return False
    except Exception as e:
        print(f"   ⚠️  Supabase radar exceção: {e}")
        return False


def _extrair_resumo_triagem(triagem: str, max_chars: int = 600) -> str:
    """Extrai as últimas linhas da triagem (resumo de tendências) como resumo_texto."""
    # O prompt PROMPT_TRIAGEM termina com "Resuma tendências da semana"
    # Procura por esse bloco no final da triagem
    for marcador in ["tendências", "tendencias", "Tendências", "Resumo", "resumo"]:
        idx = triagem.rfind(marcador)
        if idx != -1:
            trecho = triagem[idx:idx + max_chars].strip()
            if trecho:
                return trecho
    # Fallback: últimos max_chars chars
    return triagem[-max_chars:].strip()


def _enviar_whatsapp(audio_url: str, tema_nome: str, dry_run: bool = False) -> int:
    """Envia o radar para todos os usuários ativos. Retorna nº de envios."""
    try:
        from whatsapp.user_manager import get_all_active
        from whatsapp import zapi_client as zapi
    except ImportError as e:
        print(f"   ⚠️  WhatsApp não disponível: {e}")
        return 0

    usuarios = get_all_active()
    if not usuarios:
        print("   ℹ️  Nenhum usuário ativo cadastrado.")
        return 0

    msg = (
        f"🎙️ *Radar CardioDaily — {tema_nome}*\n"
        f"📅 {datetime.now().strftime('%d/%m/%Y')}\n\n"
        f"Ouça as principais novidades de *{tema_nome}* publicadas nos últimos 14 dias."
    )

    enviados = 0
    for user in usuarios:
        phone = user["phone"]
        nome  = user.get("nome") or phone
        print(f"   📱 {nome} ({phone})", end=" ")
        if dry_run:
            print("[dry-run]")
            continue
        ok_txt   = zapi.send_text(phone, msg)
        time.sleep(1)
        ok_audio = zapi.send_audio(phone, audio_url)
        if ok_txt and ok_audio:
            print("✅")
            enviados += 1
        else:
            print(f"⚠️  txt={ok_txt} audio={ok_audio}")
        time.sleep(2)

    return enviados


def run(categoria: str | None = None, dry_run: bool = False):
    from radar.radar_pubmed import RadarPubMed, CATEGORIAS_PT

    cat_key  = categoria or categoria_do_dia()
    cat_nome = CATEGORIAS_PT.get(cat_key, cat_key)
    hoje     = date.today()
    data_str = hoje.strftime("%Y-%m-%d")         # para Supabase (ISO)
    data_file = hoje.strftime("%Y%m%d")          # para nome de arquivo
    periodo_fim   = hoje.strftime("%Y-%m-%d")
    periodo_inicio = (hoje - timedelta(days=DIAS_JANELA)).strftime("%Y-%m-%d")
    mp3_filename  = f"{cat_key}_{data_file}.mp3"  # padrão: {tema}_{data}.mp3

    print(f"\n{'='*55}")
    print(f"📡 Radar CardioDaily — Diário Automático")
    print(f"   📅 {hoje.strftime('%d/%m/%Y')}  {'[DRY-RUN]' if dry_run else ''}")
    print(f"   🏷️  Tema: {cat_nome} ({cat_key})")
    print(f"   🔍 Janela: {periodo_inicio} → {periodo_fim} | Máx: {MAX_ARTIGOS} artigos")
    print(f"{'='*55}\n")

    if dry_run:
        print("✅ Dry-run: nada será executado.")
        return

    # ── 1. Inicializar radar ───────────────────────────────────────────────
    radar = RadarPubMed()
    radar.configure(
        gemini_key=os.getenv("GEMINI_API_KEY", ""),
        openai_key=os.getenv("OPENAI_API_KEY", ""),
        email=os.getenv("ENTREZ_EMAIL", "cardiodaily@cardiodaily.com.br"),
    )

    # ── 2. Buscar PubMed ──────────────────────────────────────────────────
    print(f"🔎 Buscando PubMed: {cat_nome}…")
    artigos = radar.buscar_por_categoria(cat_key, dias=DIAS_JANELA, max_results=MAX_ARTIGOS)
    print(f"   {len(artigos)} artigos encontrados")
    if not artigos:
        print("❌ Nenhum artigo encontrado — abortando.")
        return

    # ── 3. Triagem Gemini ─────────────────────────────────────────────────
    print(f"\n🤖 Triagem Gemini ({len(artigos)} artigos)…")
    triagem = radar.analisar_triagem(artigos, cat_nome)
    print(f"   Triagem concluída ({len(triagem)} chars)")

    # ── 4. Gerar script ───────────────────────────────────────────────────
    print(f"\n✍️  Gerando script de podcast…")
    script = radar.gerar_script_pubmed(artigos, triagem, cat_nome)
    print(f"   Script: {len(script)} chars")

    # ── 5. Salvar script local ────────────────────────────────────────────
    script_dir = _ROOT / "outputs" / "radar_audio"
    script_dir.mkdir(parents=True, exist_ok=True)
    script_path = script_dir / f"{cat_key}_{data_file}.txt"
    script_path.write_text(script, encoding="utf-8")
    print(f"   💾 Script salvo: {script_path.name}")

    # ── 6. Gerar MP3 ──────────────────────────────────────────────────────
    print(f"\n🔊 Gerando MP3 (OpenAI TTS)…")
    mp3_path = script_dir / mp3_filename
    ok = radar.gerar_audio(script, str(mp3_path))
    if not ok or not mp3_path.exists():
        print("❌ Falha na geração do MP3 — abortando envio.")
        return
    print(f"   ✅ MP3: {mp3_path.name} ({mp3_path.stat().st_size // 1024} KB)")

    # ── 7. Upload bucket 'radar_podcasts' ─────────────────────────────────
    print(f"\n☁️  Upload para Supabase Storage (radar_podcasts)…")
    audio_url = _upload_radar_storage(mp3_path, mp3_filename)
    if not audio_url:
        print("⚠️  Upload falhou — Supabase não receberá o registro.")
        audio_url = ""

    # ── 8. Inserir na tabela 'radar' ──────────────────────────────────────
    print(f"\n🗄️  Registrando na tabela radar…")
    resumo_texto = _extrair_resumo_triagem(triagem)
    _inserir_radar_supabase(
        tema=cat_key,
        tema_nome=cat_nome,
        data_varredura=data_str,
        periodo_inicio=periodo_inicio,
        periodo_fim=periodo_fim,
        resumo_texto=resumo_texto,
        caminho_podcast=audio_url,
        artigos_analisados=len(artigos),
    )

    # ── 9. Enviar WhatsApp ────────────────────────────────────────────────
    print(f"\n📲 Enviando para usuários ativos…")
    n = _enviar_whatsapp(audio_url, cat_nome, dry_run=dry_run)
    print(f"   {n} usuário(s) notificado(s)")

    print(f"\n{'='*55}")
    print(f"✅ Radar {cat_nome} concluído!")
    print(f"   MP3: {mp3_filename}")
    print(f"   URL: {audio_url}")
    print(f"{'='*55}\n")


def main():
    parser = argparse.ArgumentParser(description="CardioDaily — Radar Diário")
    parser.add_argument("--dry-run", action="store_true", help="Mostra categoria do dia sem executar")
    parser.add_argument("--categoria", type=str, default=None, help="Força uma categoria específica")
    parser.add_argument("--lista", action="store_true", help="Lista todas as categorias e a ordem de rotação")
    args = parser.parse_args()

    if args.lista:
        from radar.radar_pubmed import CATEGORIAS_PT
        print(f"\n📡 Rotação diária do Radar CardioDaily ({DIAS_CICLO} temas, ciclo de {DIAS_CICLO} dias)\n")
        hoje = date.today()
        cat_hoje = categoria_do_dia(hoje)
        for i, cat in enumerate(ROTACAO_DIARIA):
            nome = CATEGORIAS_PT.get(cat, cat)
            marcador = " ← HOJE" if cat == cat_hoje else ""
            print(f"  Dia {i+1:>2}: {nome}{marcador}")
        print(f"\n  Janela PubMed: {DIAS_JANELA} dias | Máx: {MAX_ARTIGOS} artigos\n")
        return

    run(categoria=args.categoria, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
