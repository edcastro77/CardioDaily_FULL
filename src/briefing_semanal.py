"""
briefing_semanal.py — Briefing de curadoria CardioDaily (Eduardo Cri-Cri).

Roda automaticamente ao final de cada lote de análise do article_analyzer.py.
Gera script ácido/irreverente + áudio via Cartesia Isabella PT-BR.

Uso direto:
    python3 src/briefing_semanal.py                    # artigos das últimas 24h
    python3 src/briefing_semanal.py --horas 48         # últimas 48h
    python3 src/briefing_semanal.py --doc-ids id1 id2  # IDs específicos
    python3 src/briefing_semanal.py --dry-run          # só gera script, sem áudio
"""

import argparse
import json
import os
import re
import sys
import struct
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

# ── Cartesia — Isabella PT-BR ────────────────────────────────────────────────
CARTESIA_VOICE_LUANA = "700d1ee3-a641-4018-ba6e-899dcadc9e2b"
CARTESIA_MODEL           = "sonic-3.5"
CARTESIA_SPEED           = 1.05   # ligeiramente mais rápida que Bruno — mais ágil
CARTESIA_MAX_CHUNK       = 9000

# ── Prompt ───────────────────────────────────────────────────────────────────
SYSTEM_BRIEFING = """Você é o alter-ego crítico do Dr. Eduardo Castro — o "Eduardo Cri-Cri".
Cardiologista sênior, leitor compulsivo, pouca paciência para mediocridade científica e humor ácido afiado.

VOZ E TOM:
- Fala como quem está comentando os artigos para si mesmo, sozinho, café na mão
- Direto, franco, irreverente — mas sempre pautado em dados
- Humor ácido quando o artigo merece: "fizeram um RCT de 47 pacientes para concluir que precisam de mais estudos. Obrigado, capitão óbvio."
- Entusiasmado de verdade quando algo é bom: "esse aqui é o tipo de dado que você vai citar por 5 anos"
- Sem filtro institucional — é uma conversa interna, não um podcast público
- Pode usar ironia, sarcasmo, comparações inusitadas — mas nunca perde o rigor clínico
- Pode fazer referências ao contexto brasileiro: "isso aqui não existe no Brasil ainda, mas..." ou "esse resultado é do mundo real, não de centro de excelência gringo"

ESTRUTURA DO SCRIPT (sem anunciar as seções — texto corrido para TTS):

ABERTURA (2-3 frases provocadoras):
Não diga "olá" nem se apresente. Comece com um comentário sobre o lote.
Ex: "Trinta artigos. Oito valem alguma coisa. O resto é a academia fazendo o que a academia faz melhor: produzir volume."
Ou: "Semana boa. Raro isso. Vamos ao que interessa."

PARA CADA ARTIGO (tempo proporcional à nota):
- Nota 9-10: 2-3 minutos — análise rica, implicação clínica, posicionamento crítico
- Nota 7-8: 1-1.5 minutos — resultado principal + take-home + comentário
- Nota 5-6: 30-45 segundos — 1 frase de resultado + 1 frase de comentário ácido
- Nota ≤4: menção rápida, eventualmente irônica (10-15 segundos)

PARA CADA ARTIGO inclua obrigatoriamente:
1. O que o estudo se propôs a fazer — em linguagem humana
2. O resultado principal — tamanho do efeito, não HR/IC bruto
3. O que você faz com isso — ação clínica concreta OU por que não muda nada ainda
4. Um comentário pessoal — entusiasmo, ceticismo, ironia conforme o caso

ENCERRAMENTO (2-3 frases):
Balanço do lote. Quais artigos merecem atenção esta semana. Tom pessoal.
Ex: "Desses trinta, eu ficaria de olho no de hipertrofia pós-TAVI e no de anticoagulação em obesos. O resto pode esperar."

REGRAS ABSOLUTAS:
- NUNCA cite PMID, DOI, número de registro
- NUNCA use HR/OR/RR/IC 95%/p-valor — traduza para linguagem humana
- NUNCA use marcadores, títulos, numeração no texto — apenas texto corrido para TTS
- NUNCA ultrapasse 1000 palavras por artigo nota 9-10
- Português brasileiro coloquial técnico — não é apresentação em congresso
"""


def _buscar_artigos_supabase(horas: int = 24, doc_ids: list[str] | None = None) -> list[dict]:
    """Busca artigos recentes no Supabase."""
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_KEY", "")
    if not url or not key:
        print("⚠️  SUPABASE_URL/SUPABASE_SERVICE_KEY não configurados")
        return []

    hdrs = {"apikey": key, "Authorization": f"Bearer {key}"}
    params = {
        "select": "doc_id,titulo,tipo_estudo,nota_aplicabilidade,doenca_principal,"
                  "revista,data_publicacao,resumo_markdown,created_at",
        "order": "nota_aplicabilidade.desc,created_at.desc",
        "limit": "200",
    }

    if doc_ids:
        params["doc_id"] = f"in.({','.join(doc_ids)})"
    else:
        since = (datetime.now(timezone.utc) - timedelta(hours=horas)).isoformat()
        params["created_at"] = f"gte.{since}"

    r = requests.get(f"{url}/rest/v1/artigos", headers=hdrs, params=params, timeout=30)
    if r.status_code != 200:
        print(f"⚠️  Supabase erro {r.status_code}: {r.text[:200]}")
        return []
    return r.json()


def _enriquecer_com_disco(artigos: list[dict]) -> list[dict]:
    """Adiciona análise do disco (analysis.json/md) quando disponível."""
    corpus = ROOT / "outputs" / "corpus"
    enriquecidos = []
    for a in artigos:
        doc_id = a.get("doc_id", "")
        pasta = corpus / doc_id
        extra = {}

        # Tentar pegar análise completa do analysis.md (mais rico que resumo_markdown)
        md_path = pasta / "analysis.md"
        if md_path.exists():
            md = md_path.read_text(encoding="utf-8", errors="ignore")
            # Pegar os primeiros 3000 chars do body (após o frontmatter)
            body = re.sub(r'^---.*?---\s*', '', md, flags=re.DOTALL).strip()
            extra["analise_completa"] = body[:4000]

        # Pegar nota estatística do analysis.json
        aj_path = pasta / "analysis.json"
        if aj_path.exists():
            try:
                aj = json.loads(aj_path.read_text(encoding="utf-8", errors="ignore"))
                ana = aj.get("analysis", {})
                extra["nota_estatistica"] = ana.get("nota_trabalho_estatistico")
                extra["keywords"] = ana.get("keywords", [])
                src = aj.get("source", {})
                extra["titulo_real"] = src.get("titulo", "")
            except Exception:
                pass

        enriquecidos.append({**a, **extra})
    return enriquecidos


def _montar_contexto_artigo(a: dict) -> str:
    """Monta bloco de contexto de um artigo para o prompt."""
    nota = a.get("nota_aplicabilidade") or 0
    titulo = a.get("titulo_real") or a.get("titulo") or a.get("doc_id", "")
    tipo = a.get("tipo_estudo", "")
    revista = a.get("revista", "")
    doenca = a.get("doenca_principal", "")
    nota_estat = a.get("nota_estatistica", "")

    linhas = [
        f"ARTIGO: {titulo}",
        f"Tipo: {tipo} | Revista: {revista} | Doença: {doenca}",
        f"Nota aplicabilidade: {nota}/10" + (f" | Nota estatística: {nota_estat}/10" if nota_estat else ""),
    ]

    # Análise completa se disponível, senão resumo_markdown
    conteudo = a.get("analise_completa") or a.get("resumo_markdown") or ""
    if conteudo:
        linhas.append(f"\nAnálise:\n{conteudo[:3000]}")

    return "\n".join(linhas)


def gerar_script(artigos: list[dict], client) -> str:
    """Gera script do briefing via Claude Sonnet 4.6."""
    n = len(artigos)
    notas = [a.get("nota_aplicabilidade") or 0 for a in artigos]
    n_altos = sum(1 for x in notas if x >= 8)
    n_medios = sum(1 for x in notas if 6 <= x < 8)
    n_baixos = sum(1 for x in notas if x < 6)

    contexto_artigos = "\n\n" + "="*60 + "\n\n".join(
        _montar_contexto_artigo(a) for a in artigos
    )

    user_prompt = f"""BRIEFING DE CURADORIA — LOTE DE HOJE

Estatísticas do lote:
- Total: {n} artigos
- Nota alta (≥8): {n_altos}
- Nota média (6-7): {n_medios}
- Nota baixa (<6): {n_baixos}
- Data: {datetime.now().strftime('%d/%m/%Y %H:%M')}

Aqui estão os artigos do lote, ordenados por nota (maior primeiro):

{contexto_artigos}

Gere o briefing completo em texto corrido, pronto para TTS.
Lembre: tempo proporcional à qualidade. Seja generoso com os bons, impiedoso com os fracos.
"""

    from anthropic import Anthropic
    if not isinstance(client, Anthropic):
        client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))

    raw_parts = []
    with client.messages.stream(
        model="claude-sonnet-5",   # 26/Jul: sonnet-4-6 velho → sonnet-5; thinking on ⇒ sem temperature (rejeitado)
        system=SYSTEM_BRIEFING,
        messages=[{"role": "user", "content": user_prompt}],
        max_tokens=24000,          # folga p/ thinking + briefing longo (antes 16000, sem thinking)
    ) as stream:
        for text in stream.text_stream:
            raw_parts.append(text)

    return "".join(raw_parts).strip()


def _limpar_para_audio(texto: str) -> str:
    """Remove markdown e formatação para TTS limpo."""
    texto = re.sub(r'\*\*(.+?)\*\*', r'\1', texto)
    texto = re.sub(r'\*(.+?)\*', r'\1', texto)
    texto = re.sub(r'#+\s+', '', texto)
    texto = re.sub(r'\[(.+?)\]\(.+?\)', r'\1', texto)
    texto = re.sub(r'`+', '', texto)
    texto = re.sub(r'\n{3,}', '\n\n', texto)
    return texto.strip()


def _find_data_chunk(wav: bytes) -> tuple[int, int]:
    """Retorna (offset_inicio_pcm, tamanho_pcm) localizando o chunk 'data' dinamicamente."""
    i = 12  # pula RIFF + tamanho + WAVE
    while i < len(wav) - 8:
        tag = wav[i:i+4]
        size = struct.unpack_from('<I', wav, i+4)[0]
        if tag == b'data':
            return i + 8, size
        i += 8 + size + (size % 2)  # chunks WAV são alinhados em 2 bytes
    raise ValueError("Chunk 'data' não encontrado no WAV")


def _concat_wavs(parts: list[bytes]) -> bytes:
    """Concatena múltiplos WAV PCM localizando o chunk data dinamicamente."""
    if len(parts) == 1:
        return parts[0]

    # Extrair PCM de cada parte
    pcm_blocks = []
    for part in parts:
        offset, _ = _find_data_chunk(part)
        pcm_blocks.append(part[offset:])

    pcm_data = b"".join(pcm_blocks)
    total_data = len(pcm_data)

    # Montar header WAV mínimo (44 bytes): RIFF/WAVE/fmt /data
    header = bytearray(44)
    header[0:4]   = b'RIFF'
    struct.pack_into('<I', header, 4, 36 + total_data)
    header[8:12]  = b'WAVE'
    header[12:16] = b'fmt '
    struct.pack_into('<I', header, 16, 16)       # tamanho do fmt chunk
    struct.pack_into('<H', header, 20, 1)        # PCM
    struct.pack_into('<H', header, 22, 1)        # mono
    struct.pack_into('<I', header, 24, 44100)    # sample rate
    struct.pack_into('<I', header, 28, 88200)    # byte rate = 44100 * 2
    struct.pack_into('<H', header, 32, 2)        # block align
    struct.pack_into('<H', header, 34, 16)       # bits per sample
    header[36:40] = b'data'
    struct.pack_into('<I', header, 40, total_data)

    return bytes(header) + pcm_data


def gerar_audio_cartesia(texto: str, output_path: str, cartesia_key: str) -> bool:
    """Gera WAV via Cartesia Isabella PT-BR."""
    texto = _limpar_para_audio(texto)
    if not texto:
        return False

    # Chunking por parágrafo
    chunks: list[str] = []
    current = ""
    for para in texto.split("\n\n"):
        para = para.strip()
        if not para:
            continue
        if len(current) + len(para) + 2 <= CARTESIA_MAX_CHUNK:
            current = (current + "\n\n" + para).strip()
        else:
            if current:
                chunks.append(current)
            current = para[:CARTESIA_MAX_CHUNK]
    if current:
        chunks.append(current)

    audio_parts: list[bytes] = []
    for i, chunk in enumerate(chunks, 1):
        if len(chunks) > 1:
            print(f"   🎙️  Cartesia chunk {i}/{len(chunks)} ({len(chunk)} chars)…")
        resp = requests.post(
            "https://api.cartesia.ai/tts/bytes",
            headers={
                "Cartesia-Version": "2026-03-01",
                "X-API-Key": cartesia_key,
                "Content-Type": "application/json",
            },
            json={
                "model_id": CARTESIA_MODEL,
                "transcript": chunk,
                "voice": {"mode": "id", "id": CARTESIA_VOICE_LUANA},
                "output_format": {
                    "container": "wav",
                    "encoding": "pcm_s16le",
                    "sample_rate": 44100,
                },
                "language": "pt",
                "generation_config": {
                    "speed": CARTESIA_SPEED,
                    "volume": 1.1,
                },
            },
            timeout=120,
        )
        if resp.status_code != 200:
            raise RuntimeError(f"Cartesia TTS HTTP {resp.status_code}: {resp.text[:300]}")
        audio_parts.append(resp.content)

    if not audio_parts:
        return False

    out_bytes = _concat_wavs(audio_parts)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    # Salvar WAV temporário e converter para MP3 via ffmpeg
    wav_tmp = Path(output_path).with_suffix(".tmp.wav")
    wav_tmp.write_bytes(out_bytes)

    import subprocess
    result = subprocess.run(
        ["ffmpeg", "-y", "-i", str(wav_tmp), "-codec:a", "libmp3lame", "-q:a", "4", output_path],
        capture_output=True,
    )
    wav_tmp.unlink(missing_ok=True)

    if result.returncode != 0:
        # ffmpeg falhou — salvar WAV direto como fallback
        Path(output_path).write_bytes(out_bytes)
        kb = Path(output_path).stat().st_size // 1024
        print(f"   ✅ WAV gerado via Cartesia Isabella ({kb} KB) [ffmpeg indisponível]")
    else:
        kb = Path(output_path).stat().st_size // 1024
        print(f"   ✅ MP3 gerado via Cartesia Luana ({kb} KB)")

    return True


def rodar_briefing(
    horas: int = 24,
    doc_ids: list[str] | None = None,
    dry_run: bool = False,
    anthropic_client=None,
) -> Path | None:
    """
    Ponto de entrada principal. Retorna caminho do WAV gerado (ou None).
    Chamado automaticamente pelo article_analyzer.py ao final de cada lote.
    """
    print(f"\n{'='*55}")
    print(f"🎙️  CardioDaily — Briefing de Curadoria (Eduardo Cri-Cri)")
    print(f"   📅 {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    if doc_ids:
        print(f"   🗂️  {len(doc_ids)} artigos específicos")
    else:
        print(f"   ⏰ Últimas {horas}h")
    print(f"{'='*55}\n")

    # 1. Buscar artigos
    print("📥 Buscando artigos no Supabase…")
    artigos = _buscar_artigos_supabase(horas=horas, doc_ids=doc_ids)
    if not artigos:
        print("ℹ️  Nenhum artigo encontrado para o período — briefing ignorado.")
        return None
    print(f"   {len(artigos)} artigos encontrados")

    # 2. Enriquecer com dados do disco
    print("📂 Enriquecendo com análises do disco…")
    artigos = _enriquecer_com_disco(artigos)

    # 3. Gerar script
    print(f"\n✍️  Gerando script (Claude Sonnet 4.6)…")
    script = gerar_script(artigos, anthropic_client)
    print(f"   Script: {len(script)} chars / ~{len(script.split()) // 130} min estimados")

    # 4. Salvar script
    saida_dir = ROOT / "outputs" / "briefing"
    saida_dir.mkdir(parents=True, exist_ok=True)
    data_str = datetime.now().strftime("%Y%m%d_%H%M")
    script_path = saida_dir / f"briefing_{data_str}.txt"
    script_path.write_text(script, encoding="utf-8")
    print(f"   💾 Script: {script_path.name}")

    if dry_run:
        print("\n[dry-run] Script gerado. Áudio não gerado.")
        return script_path

    # 5. Gerar áudio
    cartesia_key = os.environ.get("CARTESIA_API_KEY", "")
    if not cartesia_key:
        print("⚠️  CARTESIA_API_KEY não configurada — áudio não gerado.")
        return script_path

    print(f"\n🔊 Gerando áudio (Cartesia Luana PT-BR)…")
    mp3_path = saida_dir / f"briefing_{data_str}.mp3"
    try:
        ok = gerar_audio_cartesia(script, str(mp3_path), cartesia_key)
        if ok:
            print(f"   🎧 Áudio: {mp3_path.name}")
            wav_path = mp3_path  # alias para o restante do código

            # 6. Upload Supabase Storage para URL pública (WhatsApp precisa de URL)
            audio_url = _upload_supabase(mp3_path, data_str)

            # 7. Enviar WhatsApp (Dr. Eduardo — número pessoal)
            _enviar_whatsapp(audio_url, wav_path, len(artigos), data_str)

            # 8. Enviar Telegram
            _enviar_telegram(script_path, wav_path, len(artigos))

            return wav_path
    except Exception as e:
        print(f"   ❌ Áudio falhou: {e}")

    return script_path


def _upload_supabase(wav_path: Path, data_str: str) -> str | None:
    """Faz upload do WAV para Supabase Storage bucket 'briefing_audio'. Retorna URL pública."""
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_KEY", "")
    if not url or not key:
        return None
    try:
        audio_size = wav_path.stat().st_size
        if audio_size < 50_000:
            print(f"   ⚠️  Áudio inválido ({audio_size} bytes < 50KB) — upload cancelado")
            return None

        filename = f"briefing_{data_str}.wav"
        upload_url = f"{url}/storage/v1/object/briefing_audio/{filename}"
        hdrs = {
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "audio/wav",
            "x-upsert": "true",
        }
        r = requests.post(upload_url, headers=hdrs, data=wav_path.read_bytes(), timeout=120)
        if r.status_code in (200, 201):
            pub_url = f"{url}/storage/v1/object/public/briefing_audio/{filename}"
            print(f"   ☁️  Upload OK: {pub_url}")
            return pub_url
        else:
            print(f"   ⚠️  Upload Supabase falhou: {r.status_code} — {r.text[:100]}")
            return None
    except Exception as e:
        print(f"   ⚠️  Upload exceção: {e}")
        return None


def _enviar_whatsapp(audio_url: str | None, wav_path: Path | None,
                     n_artigos: int, data_str: str):
    """Envia briefing para o WhatsApp do Dr. Eduardo via Z-API."""
    import importlib.util as _ilu, sys as _sys

    zapi_instance = os.environ.get("ZAPI_INSTANCE_ID", "")
    zapi_token    = os.environ.get("ZAPI_TOKEN", "")
    zapi_client_t = os.environ.get("ZAPI_CLIENT_TOKEN", "")
    phone         = os.environ.get("EDUARDO_PHONE", "5511999999999")  # número do Dr. Eduardo

    if not zapi_instance or not zapi_token:
        print("   ⚠️  Z-API não configurado — WhatsApp ignorado.")
        return

    # Carregar zapi_client evitando conflito com pacote elevenlabs
    def _load(name, path):
        if name in _sys.modules:
            return _sys.modules[name]
        spec = _ilu.spec_from_file_location(name, path)
        mod = _ilu.module_from_spec(spec)
        _sys.modules[name] = mod
        spec.loader.exec_module(mod)
        return mod

    try:
        _wh_dir = ROOT / "src" / "whatsapp"
        _load("whatsapp", _wh_dir / "__init__.py")
        zapi = _load("whatsapp.zapi_client", _wh_dir / "zapi_client.py")
    except Exception as e:
        print(f"   ⚠️  Z-API client não carregado: {e}")
        return

    data_fmt = datetime.now().strftime("%d/%m/%Y")
    msg = (
        f"🎙️ *Briefing de Curadoria — {data_fmt}*\n"
        f"📊 {n_artigos} artigos analisados\n\n"
        f"_Eduardo Cri-Cri passou o pente-fino. Ouça antes de selecionar o conteúdo da semana._"
    )

    print(f"   📲 Enviando WhatsApp para {phone}…", end=" ")
    try:
        zapi.send_text(phone, msg)
        import time; time.sleep(1)
        if audio_url:
            zapi.send_audio(phone, audio_url)
            print("✅ (texto + áudio)")
        else:
            print("✅ (só texto — upload falhou)")
    except Exception as e:
        print(f"⚠️  {e}")


def _enviar_telegram(script_path: Path, wav_path: Path | None, n_artigos: int):
    """Envia script (e opcionalmente o áudio) ao Telegram do Dr. Eduardo."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat  = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat:
        return

    data_str = datetime.now().strftime("%d/%m/%Y %H:%M")
    caption = (
        f"🎙️ *Briefing de Curadoria — Eduardo Cri-Cri*\n"
        f"📅 {data_str} | {n_artigos} artigos analisados\n"
        f"_Seu pente-fino de hoje_"
    )

    try:
        # Enviar script como documento
        requests.post(
            f"https://api.telegram.org/bot{token}/sendDocument",
            data={"chat_id": chat, "caption": caption, "parse_mode": "Markdown"},
            files={"document": (script_path.name, script_path.read_bytes(), "text/plain")},
            timeout=30,
        )
        print(f"   📨 Script enviado ao Telegram")

        # Enviar áudio se existir e for pequeno o suficiente (<50MB)
        if wav_path and wav_path.exists():
            size_mb = wav_path.stat().st_size / (1024 * 1024)
            if size_mb < 48:
                requests.post(
                    f"https://api.telegram.org/bot{token}/sendAudio",
                    data={"chat_id": chat, "title": f"Briefing {datetime.now().strftime('%d/%m')}",
                          "parse_mode": "Markdown"},
                    files={"audio": (wav_path.name, wav_path.read_bytes(), "audio/wav")},
                    timeout=120,
                )
                print(f"   🎧 Áudio enviado ao Telegram ({size_mb:.1f} MB)")
            else:
                print(f"   ⚠️  Áudio grande ({size_mb:.1f} MB) — não enviado ao Telegram")
    except Exception as e:
        print(f"   ⚠️  Telegram falhou: {e}")


def main():
    parser = argparse.ArgumentParser(description="CardioDaily — Briefing de Curadoria")
    parser.add_argument("--horas", type=int, default=24, help="Janela de tempo em horas (default: 24)")
    parser.add_argument("--doc-ids", nargs="+", help="IDs específicos de artigos")
    parser.add_argument("--dry-run", action="store_true", help="Gera script sem áudio")
    args = parser.parse_args()

    try:
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env")
    except ImportError:
        pass

    rodar_briefing(
        horas=args.horas,
        doc_ids=args.doc_ids,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
