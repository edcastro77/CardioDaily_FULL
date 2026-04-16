"""
CARDIODAILY — Distribuidor Diário v3
=====================================
Distribuição via Z-API (WhatsApp) + Telegram Bot.
Roda via cron ou Agendador de Tarefas do Windows.

Uso:
  python3 distribuidor.py artigos   → distribuição diária (07:00)
  python3 distribuidor.py radar     → podcast do radar (08:00)
  python3 distribuidor.py teste     → simula sem enviar
"""

import sys
import os
import random
import httpx
import logging
from datetime import datetime, timezone
from supabase import create_client

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# =============================================================================
# CONFIGURAÇÃO — lida de variáveis de ambiente (GitHub Secrets / .env local)
# =============================================================================
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ["SUPABASE_KEY"]

# Z-API WhatsApp
ZAPI_BASE         = os.environ["ZAPI_BASE"]
ZAPI_CLIENT_TOKEN = os.environ["ZAPI_CLIENT_TOKEN"]
ZAPI_HEADERS      = {"Client-Token": ZAPI_CLIENT_TOKEN}

# Telegram
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID", "237863636")

# Distribuição
ARTIGOS_POR_DIA = 2
DATA_INICIO = "2026-02-01"   # janela fixa — inclui revistas mensais/bimestrais
NOTA_MINIMA = 7
PRE_SELECAO = 8

# Logging
os.makedirs("logs", exist_ok=True)
_stream_handler = logging.StreamHandler()
if hasattr(_stream_handler.stream, "reconfigure"):
    _stream_handler.stream.reconfigure(encoding="utf-8", errors="replace")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("logs/distribuidor.log", encoding="utf-8"),
        _stream_handler,
    ]
)
log = logging.getLogger("CardioDaily")

# =============================================================================
# MAPEAMENTO DE TEMAS
# =============================================================================
TEMA_PARA_DOENCAS = {
    "coronaria": [
        "Coronariopatia Aguda", "Coronariopatia Crônica",
        "Intervenção Vascular", "Coronariopatia",
        "Prevenção Cardiovascular",
    ],
    "cardiometabolico": [
        "Dislipidemias", "Cardiometabólica",
        "Manifestações Cardiovasculares de Doenças Sistêmicas",
        "Hipertensão Arterial Sistêmica", "Farmacologia",
    ],
    "miocardiopatias": [
        "Miocardiopatias", "Insuficiencia Cardiaca",
        "Aortopatias", "Pericardiopatias",
    ],
    "valvulopatias": [
        "Valvulopatias",
    ],
    "arritmia": [
        "Arritmias", "Marcapasso", "Stroke",
    ],
    "uti": [
        "Emergências/UTI", "Choque", "Parada Cardiorespiratória",
        "Pré-Operatório",
    ],
    "imagem": [
        "Imagem Cardiovascular",
    ],
    "genomica": [
        "Genética", "Cardiopatia Congênita",
    ],
    "obstetrica": [
        "Cardio-Obstetricia",
    ],
    "oncologia": [
        "Cardio-Oncologia",
    ],
}


# =============================================================================
# SUPABASE
# =============================================================================

def conectar_supabase():
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def buscar_assinantes_ativos(sb):
    result = sb.table("whatsapp_users").select("*").eq("ativo", True).execute()
    assinantes = [u for u in result.data if u.get("temas") and len(u["temas"]) > 0]
    log.info(f"Assinantes ativos com temas: {len(assinantes)}")
    return assinantes


def resolver_doencas(temas):
    doencas = set()
    for tema in temas:
        t = tema.lower().strip()
        if t in TEMA_PARA_DOENCAS:
            doencas.update(TEMA_PARA_DOENCAS[t])
    return list(doencas)


def buscar_candidatos(sb, doencas, ja_enviados):
    result = sb.table("artigos").select(
        "doc_id, titulo, revista, doenca_principal, tipo_estudo, "
        "nota_aplicabilidade, caminho_visual_abstract, caminho_audio, caminho_pdf"
    ).gte("data_publicacao", DATA_INICIO
    ).gte("nota_aplicabilidade", NOTA_MINIMA
    ).in_("doenca_principal", doencas
    ).order("nota_aplicabilidade", desc=True
    ).limit(50).execute()

    if not result.data:
        return []
    return [a for a in result.data if a["doc_id"] not in (ja_enviados or [])]


def selecionar_artigos(candidatos):
    if not candidatos:
        return []
    top = candidatos[:PRE_SELECAO]
    qtd = min(ARTIGOS_POR_DIA, len(top))
    return random.sample(top, qtd)


def montar_mensagem(artigo, html=False):
    """Monta mensagem do artigo. html=True para Telegram (evita 400 com parse_mode HTML)."""
    if html:
        titulo = artigo['titulo'].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        msg = f"📚 <b>{titulo}</b>\n\n"
        if artigo.get("revista"):
            msg += f"📖 {artigo['revista']}\n"
        if artigo.get("doenca_principal"):
            msg += f"🏥 {artigo['doenca_principal']}\n"
        if artigo.get("tipo_estudo"):
            msg += f"🔬 {artigo['tipo_estudo']}\n"
        if artigo.get("nota_aplicabilidade"):
            estrelas = "⭐" * int(artigo["nota_aplicabilidade"])
            msg += f"NAC: {artigo['nota_aplicabilidade']}/10 {estrelas}\n"
        if artigo.get("caminho_pdf") and artigo["caminho_pdf"].startswith("http"):
            msg += f"\n📄 Análise completa: {artigo['caminho_pdf']}"
        if artigo.get("caminho_audio"):
            msg += f"\n🎙️ Resumo em áudio: {artigo['caminho_audio']}"
    else:
        msg = f"📚 {artigo['titulo']}\n\n"
        if artigo.get("revista"):
            msg += f"📖 {artigo['revista']}\n"
        if artigo.get("doenca_principal"):
            msg += f"🏥 {artigo['doenca_principal']}\n"
        if artigo.get("tipo_estudo"):
            msg += f"🔬 {artigo['tipo_estudo']}\n"
        if artigo.get("nota_aplicabilidade"):
            estrelas = "⭐" * int(artigo["nota_aplicabilidade"])
            msg += f"NAC: {artigo['nota_aplicabilidade']}/10 {estrelas}\n"
        if artigo.get("caminho_pdf") and artigo["caminho_pdf"].startswith("http"):
            msg += f"\n📄 Análise completa: {artigo['caminho_pdf']}"
        if artigo.get("caminho_audio"):
            msg += f"\n🎙️ Resumo em áudio: {artigo['caminho_audio']}"
    return msg


def registrar_envio(sb, assinante_id, doc_ids, ja_enviados):
    atualizados = list(ja_enviados or []) + doc_ids
    try:
        sb.table("whatsapp_users").update({
            "artigos_enviados": atualizados,
            "last_sent_at": datetime.now(timezone.utc).isoformat()
        }).eq("id", assinante_id).execute()
        log.info(f"  Registrados {len(doc_ids)} artigos como enviados")
    except Exception as e:
        log.error(f"  Erro ao registrar envio: {e}")


# =============================================================================
# Z-API — WHATSAPP (todas as funções com Client-Token)
# =============================================================================

def zapi_send_text(phone, text):
    try:
        resp = httpx.post(f"{ZAPI_BASE}/send-text",
            json={"phone": phone, "message": text},
            headers=ZAPI_HEADERS, timeout=30)
        resp.raise_for_status()
        log.info(f"  WhatsApp texto → {phone}")
        return True
    except Exception as e:
        log.error(f"  Erro WhatsApp texto: {e}")
        return False


def zapi_send_image(phone, image_url, caption=""):
    try:
        resp = httpx.post(f"{ZAPI_BASE}/send-image",
            json={"phone": phone, "image": image_url, "caption": caption},
            headers=ZAPI_HEADERS, timeout=30)
        resp.raise_for_status()
        log.info(f"  WhatsApp imagem → {phone}")
        return True
    except Exception as e:
        log.error(f"  Erro WhatsApp imagem: {e}")
        return False


def zapi_send_audio(phone, audio_url):
    try:
        resp = httpx.post(f"{ZAPI_BASE}/send-audio",
            json={"phone": phone, "audio": audio_url},
            headers=ZAPI_HEADERS, timeout=30)
        resp.raise_for_status()
        log.info(f"  WhatsApp áudio → {phone}")
        return True
    except Exception as e:
        log.error(f"  Erro WhatsApp áudio: {e}")
        return False


def zapi_send_document(phone, doc_url, filename=""):
    try:
        resp = httpx.post(f"{ZAPI_BASE}/send-document/pdf",
            json={"phone": phone, "document": doc_url, "fileName": filename or "CardioDaily.pdf"},
            headers=ZAPI_HEADERS, timeout=30)
        resp.raise_for_status()
        log.info(f"  WhatsApp PDF → {phone}")
        return True
    except Exception as e:
        log.error(f"  Erro WhatsApp PDF: {e}")
        return False


# =============================================================================
# TELEGRAM
# =============================================================================

def tg_send_text(text, html=False):
    try:
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text}
        if html:
            payload["parse_mode"] = "HTML"
        resp = httpx.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json=payload,
            timeout=30)
        resp.raise_for_status()
        log.info(f"  Telegram texto → {TELEGRAM_CHAT_ID}")
        return True
    except Exception as e:
        log.error(f"  Erro Telegram texto: {e}")
        return False


def tg_send_image(image_url, caption=""):
    try:
        resp = httpx.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto",
            json={"chat_id": TELEGRAM_CHAT_ID, "photo": image_url, "caption": caption[:1024]},
            timeout=30)
        resp.raise_for_status()
        log.info(f"  Telegram imagem → {TELEGRAM_CHAT_ID}")
        return True
    except Exception as e:
        log.error(f"  Erro Telegram imagem: {e}")
        return False


def tg_send_audio(audio_url, title=""):
    try:
        resp = httpx.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendAudio",
            json={"chat_id": TELEGRAM_CHAT_ID, "audio": audio_url, "title": title},
            timeout=30)
        resp.raise_for_status()
        log.info(f"  Telegram áudio → {TELEGRAM_CHAT_ID}")
        return True
    except Exception as e:
        log.error(f"  Erro Telegram áudio: {e}")
        return False


# =============================================================================
# ENVIAR ARTIGO COMPLETO (pacote: imagem + texto + áudio)
# =============================================================================

def enviar_artigo(phone, artigo):
    titulo = artigo.get("titulo", "Sem título")
    log.info(f"  Enviando: {titulo[:60]}...")

    caption = f"📚 {titulo}\n📖 {artigo.get('revista', '')}\n⭐ NAC: {artigo.get('nota_aplicabilidade', '?')}/10"

    # 1. Visual abstract
    if artigo.get("caminho_visual_abstract"):
        zapi_send_image(phone, artigo["caminho_visual_abstract"], caption)
        tg_send_image(artigo["caminho_visual_abstract"], caption)

    # 2. Texto com links (WhatsApp: plain text; Telegram: HTML para evitar 400)
    texto_wa = montar_mensagem(artigo, html=False)
    texto_tg = montar_mensagem(artigo, html=True)
    zapi_send_text(phone, texto_wa)
    tg_send_text(texto_tg, html=True)

    # 3. Áudio
    if artigo.get("caminho_audio"):
        zapi_send_audio(phone, artigo["caminho_audio"])
        tg_send_audio(artigo["caminho_audio"], f"CardioDaily - {titulo[:50]}")

    # 4. PDF
    if artigo.get("caminho_pdf") and artigo["caminho_pdf"].startswith("http"):
        zapi_send_document(phone, artigo["caminho_pdf"], f"CardioDaily_{artigo['doc_id']}.pdf")


# =============================================================================
# DISTRIBUIÇÃO DE ARTIGOS (07:00)
# =============================================================================

def distribuir_artigos():
    log.info("=" * 60)
    log.info("DISTRIBUIÇÃO DIÁRIA — 07:00")
    log.info(f"Data: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    log.info("=" * 60)

    sb = conectar_supabase()
    assinantes = buscar_assinantes_ativos(sb)
    total = 0

    for assinante in assinantes:
        nome = assinante.get("nome", "?")
        phone = assinante.get("phone", "")
        temas = assinante.get("temas", [])
        ja_enviados = assinante.get("artigos_enviados", [])

        log.info(f"\n{'─' * 40}")
        log.info(f"Assinante: {nome} ({phone})")

        doencas = resolver_doencas(temas)
        if not doencas:
            log.warning("  Sem doenças mapeadas. Pulando.")
            continue

        candidatos = buscar_candidatos(sb, doencas, ja_enviados)
        log.info(f"  Candidatos: {len(candidatos)}")

        if not candidatos:
            log.warning("  Sem artigos novos.")
            continue

        selecionados = selecionar_artigos(candidatos)
        log.info(f"  Selecionados: {len(selecionados)}")

        doc_ids = []
        for artigo in selecionados:
            enviar_artigo(phone, artigo)
            doc_ids.append(artigo["doc_id"])
            total += 1

        if doc_ids:
            registrar_envio(sb, assinante["id"], doc_ids, ja_enviados)

    log.info(f"\n{'=' * 60}")
    log.info(f"CONCLUÍDO — {total} artigos enviados")
    log.info("=" * 60)


# =============================================================================
# DISTRIBUIÇÃO DO RADAR (08:00)
# =============================================================================

def distribuir_radar():
    log.info("=" * 60)
    log.info("RADAR CARDIODAILY — 08:00")
    log.info("=" * 60)

    sb = conectar_supabase()
    hoje = datetime.now().strftime("%Y-%m-%d")  # horário local (Brasil)
    result = sb.table("radar").select("*").eq("data_varredura", hoje).limit(1).execute()

    if not result.data:
        log.warning("Nenhum radar para hoje.")
        return

    radar = result.data[0]
    tema = radar.get("tema", "")
    podcast_url = radar.get("caminho_podcast", "")

    # Mapeia a chave do banco para o nome legível
    TEMAS_PT = {
        "doenca_coronariana":       "Coronária/DAC",
        "cardio_metabolica":        "Cardiometabólica",
        "arritmias":                "Arritmias",
        "insuficiencia_cardiaca":   "Insuficiência Cardíaca",
        "valvulopatias":            "Valvulopatias",
        "miocardiopatias":          "Miocardiopatias",
        "intervencao_hemodinamica": "Intervenção/Hemodinâmica",
        "cardio_oncologia":         "Cardio-Oncologia",
        "cardiobstetrica":          "Cardio-Obstétrica",
        "cardio_genomica":          "Cardio-Genômica",
        "uti_cardiologica":         "UTI Cardiológica",
        "aorta_congenitas":         "Aorta e Congênitas",
        "imagem_cardiovascular":    "Imagem Cardiovascular",
    }
    tema_nome = TEMAS_PT.get(tema, tema)
    tema_safe = tema_nome.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    pergunta = radar.get("pergunta_socratica", "")
    n_artigos = radar.get("artigos_analisados", "?")
    data_hoje = datetime.now().strftime("%d/%m/%Y")

    # WhatsApp (plain text)
    msg_wa = f"🔬 *Radar CardioDaily* — {data_hoje}\n"
    msg_wa += f"📡 {tema_nome}\n\n"
    if pergunta:
        msg_wa += f"💭 _{pergunta}_\n\n"
    msg_wa += f"🎙️ Ouça o podcast de hoje — {n_artigos} estudos analisados."

    # Telegram (HTML)
    pergunta_safe = pergunta.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    msg_tg = f"🔬 <b>Radar CardioDaily</b> — {data_hoje}\n"
    msg_tg += f"📡 {tema_safe}\n\n"
    if pergunta_safe:
        msg_tg += f"💭 <i>{pergunta_safe}</i>\n\n"
    msg_tg += f"🎙️ Ouça o podcast de hoje — {n_artigos} estudos analisados."

    assinantes = buscar_assinantes_ativos(sb)
    for assinante in assinantes:
        phone = assinante.get("phone", "")
        zapi_send_text(phone, msg_wa)
        tg_send_text(msg_tg, html=True)
        if podcast_url:
            zapi_send_audio(phone, podcast_url)
            tg_send_audio(podcast_url, f"Radar - {tema}")

    log.info("RADAR CONCLUÍDO")


# =============================================================================
# MODO TESTE
# =============================================================================

def modo_teste():
    log.info("=" * 60)
    log.info("MODO TESTE — nenhuma mensagem será enviada")
    log.info("=" * 60)

    sb = conectar_supabase()
    assinantes = buscar_assinantes_ativos(sb)

    for a in assinantes:
        nome = a.get("nome", "?")
        temas = a.get("temas", [])
        doencas = resolver_doencas(temas)
        candidatos = buscar_candidatos(sb, doencas, a.get("artigos_enviados", []))
        selecionados = selecionar_artigos(candidatos)

        log.info(f"\n{nome}:")
        log.info(f"  Temas: {temas}")
        log.info(f"  Doenças mapeadas: {len(doencas)}")
        log.info(f"  Candidatos: {len(candidatos)}")
        log.info(f"  Selecionados:")
        for s in selecionados:
            va = "✅" if s.get("caminho_visual_abstract") else "❌"
            audio = "✅" if s.get("caminho_audio") else "❌"
            pdf = "✅" if s.get("caminho_pdf") and s["caminho_pdf"].startswith("http") else "❌"
            log.info(f"    [{s['nota_aplicabilidade']}] {s['titulo'][:55]}...")
            log.info(f"         VA:{va}  Audio:{audio}  PDF:{pdf}")


# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python3 distribuidor.py [artigos|radar|teste]")
        sys.exit(1)

    modo = sys.argv[1].lower()

    if modo == "artigos":
        distribuir_artigos()
    elif modo == "radar":
        distribuir_radar()
    elif modo == "teste":
        modo_teste()
    else:
        print(f"Modo desconhecido: {modo}")
        sys.exit(1)
