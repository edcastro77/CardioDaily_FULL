"""
CARDIODAILY — Distribuidor Diário v4
=====================================
Distribuição via Z-API (WhatsApp) + Telegram Bot.
Roda via cron ou Agendador de Tarefas do Windows.

Uso:
  python3 distribuidor.py artigos          → distribuição diária (07:00) — 1 artigo destaque
  python3 distribuidor.py lista_diaria     → lista A navegável (07:00) — 5 artigos com gancho
  python3 distribuidor.py lista_semanal    → lista B por revista (segundas 07:30)
  python3 distribuidor.py radar            → podcast do radar (08:00)
  python3 distribuidor.py semana           → lista semanal legado (sem gancho)
  python3 distribuidor.py semana --dry-run → preview sem enviar
  python3 distribuidor.py teste            → simula sem enviar
"""

import sys
import os
import httpx
import logging
from datetime import datetime, timezone, timedelta
from supabase import create_client

# Lista navegável com ganchos
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
try:
    from lista_whatsapp import (
        gerar_lista_diaria,
        gerar_lista_semanal_por_revista,
        FORMATO_A, FORMATO_B,
    )
    _LISTA_OK = True
except ImportError:
    _LISTA_OK = False

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# =============================================================================
# CONFIGURAÇÃO — lida de variáveis de ambiente (GitHub Secrets / .env local)
# =============================================================================
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_KEY", "")

# Z-API WhatsApp
ZAPI_BASE         = os.environ.get("ZAPI_BASE", "")
ZAPI_CLIENT_TOKEN = os.environ.get("ZAPI_CLIENT_TOKEN", "")
ZAPI_HEADERS      = {"Client-Token": ZAPI_CLIENT_TOKEN}

# Telegram
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID", "237863636")

# Validação antecipada de credenciais críticas
_missing = [k for k, v in {
    "SUPABASE_URL": SUPABASE_URL,
    "SUPABASE_SERVICE_KEY": SUPABASE_KEY,
    "ZAPI_BASE": ZAPI_BASE,
    "ZAPI_CLIENT_TOKEN": ZAPI_CLIENT_TOKEN,
}.items() if not v]
if _missing:
    print(f"❌ ERRO: secrets não configurados: {', '.join(_missing)}")
    print("   Configure em: GitHub → Settings → Secrets and variables → Actions")
    sys.exit(1)

# Modo beta: quando BETA_PAUSADO=1, envia apenas para Dr. Eduardo
BETA_PAUSADO = os.environ.get("BETA_PAUSADO", "1") == "1"

# Distribuição
ARTIGOS_POR_DIA = 1
JANELA_DIAS    = 15          # busca nos últimos 15 dias
NOTA_MINIMA    = 8
PRE_SELECAO    = 5           # top-N por tema antes de sortear

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
    for tentativa in range(3):
        try:
            result = sb.table("whatsapp_users").select("*").eq("ativo", True).execute()
            assinantes = [u for u in result.data if u.get("temas") and len(u["temas"]) > 0]
            log.info(f"Assinantes ativos com temas: {len(assinantes)}")
            return assinantes
        except Exception as e:
            log.warning(f"  Tentativa {tentativa+1}/3 buscar_assinantes_ativos falhou: {e}")
            if tentativa < 2:
                import time; time.sleep(3)
    log.error("  buscar_assinantes_ativos: todas as tentativas falharam — usando lista mínima")
    # Fallback: Dr. Eduardo direto do env para não travar o envio do radar
    import os
    phone = os.getenv("EDUARDO_PHONE", "")
    if phone:
        return [{"phone": phone, "nome": "Dr. Eduardo", "temas": ["coronaria","arritmia","miocardiopatias","prevencao","valvulopatias","uti","imagem","cardiometabolico"], "ativo": True}]
    return []


def resolver_doencas(temas):
    doencas = set()
    for tema in temas:
        t = tema.lower().strip()
        if t in TEMA_PARA_DOENCAS:
            doencas.update(TEMA_PARA_DOENCAS[t])
    return list(doencas)


JANELAS_FALLBACK = [90, 180, 365]  # dias de data_publicacao — tenta cada janela em ordem
DATA_PUBLICACAO_PISO = "2024-01-01"  # nunca enviar artigos mais velhos que isso


def _data_publicacao_inicio(dias):
    return (datetime.now() - timedelta(days=dias)).strftime("%Y-%m-%d")


def _buscar_tema(sb, tema, doencas, ja_set, ja_dois, dias):
    """Busca artigos de um tema numa janela de data_publicacao."""
    data_inicio = max(_data_publicacao_inicio(dias), DATA_PUBLICACAO_PISO)
    result = sb.table("artigos").select(
        "doc_id, doi, titulo, revista, doenca_principal, tipo_estudo, "
        "nota_aplicabilidade, gancho_abertura, caminho_visual_abstract, caminho_audio, caminho_pdf"
    ).gte("data_publicacao", data_inicio
    ).gte("nota_aplicabilidade", NOTA_MINIMA
    ).in_("doenca_principal", doencas
    ).order("nota_aplicabilidade", desc=True
    ).order("data_publicacao", desc=True
    ).limit(PRE_SELECAO * 3).execute()  # busca mais para compensar filtro de DOI

    filtrados = []
    for a in (result.data or []):
        if a["doc_id"] in ja_set:
            continue
        doi = (a.get("doi") or "").strip().lower()
        if doi and doi in ja_dois:
            continue
        # Só artigos com VA e áudio — sem eles o envio é incompleto
        if not a.get("caminho_visual_abstract"):
            continue
        if not a.get("caminho_audio"):
            continue
        filtrados.append(a)
    return filtrados[:PRE_SELECAO]


def _extrair_dois_enviados(sb, doc_ids):
    """Busca os DOIs dos artigos já enviados para deduplicar por conteúdo."""
    if not doc_ids:
        return set()
    result = sb.table("artigos").select("doi").in_("doc_id", list(doc_ids)).execute()
    return {
        (r.get("doi") or "").strip().lower()
        for r in (result.data or [])
        if r.get("doi")
    }


def buscar_candidatos_por_tema(sb, temas, ja_enviados):
    """
    Para cada tema subscrito busca os melhores artigos com fallback:
    tenta 15 dias → 30 dias → 60 dias até encontrar artigos.
    Deduplica por doc_id E por DOI (evita mesmo estudo indexado 2x).
    Retorna dict {tema: [artigos]}.
    """
    ja_set = set(ja_enviados or [])
    ja_dois = _extrair_dois_enviados(sb, ja_set)
    por_tema = {}

    for tema in temas:
        doencas = TEMA_PARA_DOENCAS.get(tema.lower().strip(), [])
        if not doencas:
            continue
        for dias in JANELAS_FALLBACK:
            candidatos = _buscar_tema(sb, tema, doencas, ja_set, ja_dois, dias)
            if candidatos:
                por_tema[tema] = candidatos
                if dias > JANELAS_FALLBACK[0]:
                    log.info(f"  [{tema}] sem artigos em {JANELAS_FALLBACK[0]}d de publicação → usando janela {dias}d")
                break

    return por_tema


def selecionar_artigos_por_tema(por_tema):
    """
    Seleciona 1 artigo por dia.

    Regras:
    1. Junta todos os candidatos num pool único (deduplica por doc_id e DOI).
    2. Ordena por prioridade de tipo: Original > Meta-análise > Revisão.
    3. Dentro do mesmo tipo: nota_aplicabilidade DESC → data_publicacao DESC.
    4. Retorna o melhor artigo do pool ordenado.
    """
    if not por_tema:
        return []

    # Prioridade de tipo: menor número = maior prioridade
    TIPO_PRIORIDADE = {
        "artigo_original":                    0,
        "original":                           0,
        "revisao_sistematica_meta_analise":   1,
        "metanalise":                         1,
        "revisao_geral":                      2,
        "revisao":                            2,
        "guideline":                          2,
    }

    def _tipo_prio(a):
        t = (a.get("tipo_estudo") or "").lower()
        return TIPO_PRIORIDADE.get(t, 99)

    def _date_int(a):
        d = (a.get("data_publicacao") or "0000-00-00").replace("-", "")
        try:
            return int(d)
        except ValueError:
            return 0

    # Montar pool único — deduplica por doc_id e DOI
    pool = []
    vistos_ids: set = set()
    vistos_dois: set = set()
    for tema, candidatos in por_tema.items():
        for artigo in candidatos:
            if artigo["doc_id"] in vistos_ids:
                continue
            doi = (artigo.get("doi") or "").strip().lower()
            if doi and doi in vistos_dois:
                continue
            artigo["_tema"] = tema
            pool.append(artigo)
            vistos_ids.add(artigo["doc_id"])
            if doi:
                vistos_dois.add(doi)

    if not pool:
        return []

    # Ordenar: tipo ASC (Original=0 primeiro) → nota DESC → data DESC
    pool.sort(key=lambda a: (
        _tipo_prio(a),
        -(a.get("nota_aplicabilidade") or 0),
        -_date_int(a),
    ))

    return [pool[0]]


def montar_mensagem(artigo, html=False):
    """Monta mensagem do artigo. html=True para Telegram (evita 400 com parse_mode HTML)."""
    if html:
        titulo = artigo['titulo'].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        msg = f"📚 <b>{titulo}</b>\n\n"
        if artigo.get("impacto_pratica"):
            impacto = artigo['impacto_pratica'].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            msg += f"<b>{impacto}</b>\n\n"
        if artigo.get("revista"):
            msg += f"📖 {artigo['revista']}\n"
        if artigo.get("doenca_principal"):
            msg += f"🏥 {artigo['doenca_principal']}\n"
        if artigo.get("tipo_estudo"):
            msg += f"🔬 {artigo['tipo_estudo']}\n"
        if artigo.get("nota_aplicabilidade"):
            estrelas = "⭐" * int(artigo["nota_aplicabilidade"])
            msg += f"NAC: {artigo['nota_aplicabilidade']}/10 {estrelas}\n"
        if artigo.get("caminho_audio"):
            msg += f"\n🎙️ Resumo em áudio: {artigo['caminho_audio']}"
    else:
        msg = f"📚 {artigo['titulo']}\n\n"
        if artigo.get("impacto_pratica"):
            msg += f"{artigo['impacto_pratica']}\n\n"
        if artigo.get("revista"):
            msg += f"📖 {artigo['revista']}\n"
        if artigo.get("doenca_principal"):
            msg += f"🏥 {artigo['doenca_principal']}\n"
        if artigo.get("tipo_estudo"):
            msg += f"🔬 {artigo['tipo_estudo']}\n"
        if artigo.get("nota_aplicabilidade"):
            estrelas = "⭐" * int(artigo["nota_aplicabilidade"])
            msg += f"NAC: {artigo['nota_aplicabilidade']}/10 {estrelas}\n"
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

def zapi_check_connected() -> bool:
    """
    Verifica se a instância Z-API está conectada ao WhatsApp.
    Retorna True se conectada, False caso contrário.
    Em caso de desconexão, envia alerta imediato via Telegram para Dr. Eduardo.
    """
    try:
        resp = httpx.get(f"{ZAPI_BASE}/status", headers=ZAPI_HEADERS, timeout=10)
        data = resp.json()
        connected = data.get("connected", False)
        if not connected:
            motivo = data.get("error", "Sem detalhes")
            msg = (
                f"🚨 *CardioDaily — Z-API DESCONECTADA*\n\n"
                f"O WhatsApp está desconectado e os envios de hoje *não serão entregues*.\n\n"
                f"*Motivo:* {motivo}\n\n"
                f"*Ação necessária:*\n"
                f"1. Acesse app.z-api.io\n"
                f"2. Instância `3F0C22040662826CFF327E97F8598275`\n"
                f"3. Clique em Conectar → escaneie o QR code\n"
                f"4. Dispare manualmente: `gh workflow run artigos-diarios.yml`"
            )
            log.error(f"Z-API desconectada: {motivo}")
            # Alerta Telegram (mesmo sem WhatsApp, Telegram funciona)
            if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
                try:
                    httpx.post(
                        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                        json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"},
                        timeout=15
                    )
                    log.info("  🔔 Alerta de desconexão enviado via Telegram")
                except Exception as te:
                    log.error(f"  Falha ao enviar alerta Telegram: {te}")
        return connected
    except Exception as e:
        log.error(f"  Erro ao verificar status Z-API: {e}")
        return False


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
    """
    Sequência de entrega:
      1. Gancho socrático (texto)  — desperta curiosidade
      2. Áudio MP3                 — análise completa, ouve no carro
      3. Visual abstract (imagem)  — anzol visual
      4. Link PDF + crédito        — destino final para quem quer a prova
    """
    titulo = artigo.get("titulo", "Sem título")
    revista = artigo.get("revista", "")
    nac = artigo.get("nota_aplicabilidade", "?")
    log.info(f"  Enviando: {titulo[:60]}...")

    # 1. Gancho socrático
    gancho = artigo.get("gancho_abertura") or ""
    if gancho:
        msg_gancho = f"{gancho}\n\n📖 {revista} · NAC {nac}/10"
    else:
        # Fallback: título + revista
        msg_gancho = f"📚 {titulo}\n\n📖 {revista} · NAC {nac}/10"
    zapi_send_text(phone, msg_gancho)
    tg_send_text(msg_gancho.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))

    # 2. Áudio
    if artigo.get("caminho_audio"):
        zapi_send_audio(phone, artigo["caminho_audio"])
        tg_send_audio(artigo["caminho_audio"], f"CardioDaily — {titulo[:50]}")

    # 3. Visual abstract
    if artigo.get("caminho_visual_abstract"):
        caption = f"🔬 {titulo[:80]}"
        zapi_send_image(phone, artigo["caminho_visual_abstract"], caption)
        tg_send_image(artigo["caminho_visual_abstract"], caption)

    # 4. Link PDF
    if artigo.get("caminho_pdf"):
        msg_pdf = f"📄 Análise completa (PDF):\n{artigo['caminho_pdf']}\n\n_CardioDaily — dados e fatos, sem firulas._"
        zapi_send_text(phone, msg_pdf)
        tg_send_text(msg_pdf.replace("_", "").replace("&", "&amp;"))


# =============================================================================
# DISTRIBUIÇÃO DE ARTIGOS (07:00)
# =============================================================================

def distribuir_artigos():
    log.info("=" * 60)
    log.info("DISTRIBUIÇÃO DIÁRIA — 07:00")
    log.info(f"Data: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    log.info(f"Janela: data_publicacao >= {_data_publicacao_inicio(JANELAS_FALLBACK[0])} ({JANELAS_FALLBACK[0]}d), piso {DATA_PUBLICACAO_PISO}")
    log.info("=" * 60)

    # Verificar conexão Z-API antes de qualquer envio
    if not zapi_check_connected():
        log.error("❌ Z-API desconectada — distribuição abortada. Reconecte e dispare manualmente.")
        sys.exit(1)
    log.info("✅ Z-API conectada")

    sb = conectar_supabase()
    assinantes = buscar_assinantes_ativos(sb)
    total = 0

    for assinante in assinantes:
        nome = assinante.get("nome", "?")
        phone = assinante.get("phone", "")
        temas = assinante.get("temas", [])
        ja_enviados = assinante.get("artigos_enviados", [])

        if BETA_PAUSADO and phone != DR_EDUARDO_PHONE:
            log.info(f"  ⏸️  Beta pausado — pulando {nome} ({phone})")
            continue

        log.info(f"\n{'─' * 40}")
        log.info(f"Assinante: {nome} ({phone}) | temas: {temas}")

        por_tema = buscar_candidatos_por_tema(sb, temas, ja_enviados)
        temas_com_artigos = list(por_tema.keys())
        total_candidatos = sum(len(v) for v in por_tema.values())
        log.info(f"  Temas com artigos novos: {temas_com_artigos}")
        log.info(f"  Total candidatos: {total_candidatos}")

        if not por_tema:
            log.warning("  Sem artigos novos nos últimos 15 dias.")
            continue

        selecionados = selecionar_artigos_por_tema(por_tema)
        log.info(f"  Selecionados: {len(selecionados)}")

        doc_ids = []
        for artigo in selecionados:
            tema_tag = artigo.pop("_tema", "")
            log.info(f"  → [{tema_tag}] {artigo.get('titulo','')[:55]}...")
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

    # Verificar conexão Z-API antes de qualquer envio
    if not zapi_check_connected():
        log.error("❌ Z-API desconectada — radar abortado. Reconecte e dispare manualmente.")
        sys.exit(1)
    log.info("✅ Z-API conectada")

    sb = conectar_supabase()
    hoje = datetime.now().strftime("%Y-%m-%d")  # horário local (Brasil)

    radar = None
    for tentativa in range(3):
        try:
            result = sb.table("radar").select("*").eq("data_varredura", hoje).limit(1).execute()
            if result.data:
                radar = result.data[0]
            break
        except Exception as e:
            log.warning(f"  Tentativa {tentativa+1}/3 buscar radar falhou: {e}")
            if tentativa < 2:
                import time; time.sleep(3)

    if not radar:
        log.warning("Nenhum radar para hoje.")
        return
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
    pergunta = radar.get("pergunta_socratica") or ""
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

    if BETA_PAUSADO:
        log.info(f"  ⏸️  Beta pausado — enviando radar apenas para Dr. Eduardo ({DR_EDUARDO_PHONE})")

    assinantes = buscar_assinantes_ativos(sb)
    for assinante in assinantes:
        phone = assinante.get("phone", "")
        if BETA_PAUSADO and phone != DR_EDUARDO_PHONE:
            log.info(f"  ⏸️  Pulando {assinante.get('nome','?')} ({phone})")
            continue
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
    log.info(f"Janela: data_publicacao >= {_data_publicacao_inicio(JANELAS_FALLBACK[0])} ({JANELAS_FALLBACK[0]}d), piso {DATA_PUBLICACAO_PISO}")
    log.info("=" * 60)

    sb = conectar_supabase()
    assinantes = buscar_assinantes_ativos(sb)

    for a in assinantes:
        nome = a.get("nome", "?")
        temas = a.get("temas", [])
        por_tema = buscar_candidatos_por_tema(sb, temas, a.get("artigos_enviados", []))
        selecionados = selecionar_artigos_por_tema(por_tema)

        log.info(f"\n{nome}:")
        log.info(f"  Temas: {temas}")
        log.info(f"  Temas com artigos: {list(por_tema.keys())}")
        log.info(f"  Selecionados:")
        for s in selecionados:
            tema_tag = s.pop("_tema", "")
            va    = "✅" if s.get("caminho_visual_abstract") else "❌"
            audio = "✅" if s.get("caminho_audio") else "❌"
            pdf   = "✅" if s.get("caminho_pdf") and s["caminho_pdf"].startswith("http") else "❌"
            log.info(f"    [{tema_tag}] [{s['nota_aplicabilidade']}] {s['titulo'][:55]}...")
            log.info(f"         VA:{va}  Audio:{audio}  PDF:{pdf}")


# =============================================================================
# DISTRIBUIÇÃO PESSOAL — Dr. Eduardo (revisão de conteúdo)
# Envia 1 original + 1 revisão/meta diretamente para o número do Dr. Eduardo.
# Sem filtro de assinante, sem registro de enviados — para revisão de qualidade.
# =============================================================================

DR_EDUARDO_PHONE = "5527996089248"

def distribuir_eduardo():
    """Busca 1 original (nota ≥ 8) + 1 revisão/meta (nota ≥ 7) recentes e envia ao Dr. Eduardo."""
    log.info("=" * 60)
    log.info("DISTRIBUIÇÃO DR. EDUARDO — revisão de conteúdo")
    log.info(f"Data: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    log.info("=" * 60)

    sb = conectar_supabase()
    data_inicio = _data_publicacao_inicio(30)  # últimos 30 dias

    TIPOS_ORIGINAL = ["artigo_original", "original"]
    TIPOS_REVISAO  = ["revisao_sistematica_meta_analise", "metanalise", "revisao_geral",
                      "revisao", "guideline", "meta_analise", "ponto_de_vista"]

    def _buscar(tipos, nota_min, limite=10):
        r = sb.table("artigos").select(
            "doc_id, doi, titulo, revista, doenca_principal, tipo_estudo, "
            "nota_aplicabilidade, gancho_abertura, caminho_visual_abstract, caminho_audio, caminho_pdf"
        ).gte("created_at", (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%dT00:00:00")
        ).gte("nota_aplicabilidade", nota_min
        ).in_("tipo_estudo", tipos
        ).not_.is_("caminho_audio", "null"
        ).order("nota_aplicabilidade", desc=True
        ).order("created_at", desc=True
        ).limit(limite).execute()
        return r.data or []

    originais = _buscar(TIPOS_ORIGINAL, nota_min=8)
    revisoes  = _buscar(TIPOS_REVISAO,  nota_min=7)

    if not originais:
        log.warning("Nenhum original com nota ≥ 8 e áudio nos últimos 30 dias.")
    if not revisoes:
        log.warning("Nenhuma revisão/meta com nota ≥ 7 e áudio nos últimos 30 dias.")

    selecionados = []
    if originais:
        selecionados.append(originais[0])
    if revisoes:
        # garantir que não é o mesmo artigo
        for r in revisoes:
            if not selecionados or r["doc_id"] != selecionados[0]["doc_id"]:
                selecionados.append(r)
                break

    if not selecionados:
        log.error("Nada para enviar.")
        return

    for artigo in selecionados:
        tipo = artigo.get("tipo_estudo", "")
        log.info(f"\n→ [{tipo}] {artigo.get('titulo','')[:70]}...")
        log.info(f"  Nota: {artigo.get('nota_aplicabilidade')} | VA: {'✅' if artigo.get('caminho_visual_abstract') else '❌'} | Áudio: {'✅' if artigo.get('caminho_audio') else '❌'}")
        enviar_artigo(DR_EDUARDO_PHONE, artigo)

    log.info(f"\n{'=' * 60}")
    log.info(f"CONCLUÍDO — {len(selecionados)} artigos enviados para Dr. Eduardo")
    log.info("=" * 60)


# =============================================================================
# LISTA SEMANAL POR REVISTA
# =============================================================================

# Mapeamento de abreviações do banco para nomes legíveis
REVISTA_NOMES = {
    "NEJM":              "New England Journal of Medicine",
    "Lancet":            "The Lancet",
    "JAMA":              "JAMA",
    "JAMA_Cardiology":   "JAMA Cardiology",
    "EHJ":               "European Heart Journal",
    "EHJO":              "EHJ Open",
    "EHF":               "European Heart Journal — Failure",
    "EJPC":              "European Journal of Preventive Cardiology",
    "JACC":              "JACC",
    "JACC:_Advances":    "JACC: Advances",
    "CCI":               "Circulation: Cardiovascular Imaging",
    "CAE":               "Circulation: Arrhythmia and Electrophysiology",
    "JHF":               "JACC: Heart Failure",
    "Circulation":       "Circulation",
    "Heart":             "Heart",
    "Hypertension":      "Hypertension",
    "Atherosclerosis":   "Atherosclerosis",
    "Stroke":            "Stroke",
    "JAHA":              "Journal of the American Heart Association",
}

# Revistas top-tier que aparecem primeiro na lista
REVISTAS_TOP = {"NEJM", "Lancet", "JAMA", "JAMA_Cardiology", "EHJ", "JACC", "Circulation"}

TIPO_SIGLA = {
    "artigo_original":                   "original",
    "original":                          "original",
    "revisao_sistematica_meta_analise":   "meta",
    "metanalise":                         "meta",
    "revisao_geral":                     "revisão",
    "revisao":                           "revisão",
    "guideline":                         "guideline",
}


def buscar_artigos_semana(sb, dias: int = 7):
    """Busca artigos nota >= 8 indexados nos últimos `dias` dias."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=dias)).isoformat()
    result = (
        sb.table("artigos")
        .select("id,titulo,revista,nota_aplicabilidade,tipo_estudo,doenca_principal,created_at")
        .gte("nota_aplicabilidade", 8)
        .gte("created_at", cutoff)
        .order("revista", desc=False)
        .order("nota_aplicabilidade", desc=True)
        .limit(200)
        .execute()
    )
    return result.data or []


def montar_lista_semanal(artigos: list) -> str:
    """Formata a lista semanal agrupada por revista para WhatsApp."""
    if not artigos:
        return "📭 Nenhum artigo com nota ≥ 8 indexado esta semana."

    # Agrupar por revista
    por_revista: dict[str, list] = {}
    for a in artigos:
        rev = a.get("revista") or "Sem revista"
        por_revista.setdefault(rev, []).append(a)

    # Ordenar: top-tier primeiro, depois alfabético
    def _rev_sort(rev):
        return (0 if rev in REVISTAS_TOP else 1, rev.lower())

    data_ref = datetime.now().strftime("%d/%m/%Y")
    linhas = [f"📋 *Destaques da semana — CardioDaily*", f"📅 {data_ref}\n"]

    total = 0
    for rev in sorted(por_revista.keys(), key=_rev_sort):
        nome_rev = REVISTA_NOMES.get(rev, rev)
        lista = por_revista[rev]
        linhas.append(f"📖 *{nome_rev}*")
        for a in lista:
            titulo = a.get("titulo", "Sem título")
            # Trunca título longo para caber no WhatsApp
            if len(titulo) > 90:
                titulo = titulo[:87] + "…"
            nota = a.get("nota_aplicabilidade", "?")
            tipo = TIPO_SIGLA.get(a.get("tipo_estudo", ""), a.get("tipo_estudo", "") or "")
            tag = f"[{tipo}] " if tipo else ""
            linhas.append(f"  • {tag}NAC {nota} — {titulo}")
            total += 1
        linhas.append("")  # linha em branco entre revistas

    linhas.append(f"_Total: {total} artigos indexados esta semana (nota ≥ 8)_")
    return "\n".join(linhas)


def lista_semanal(dry_run: bool = False):
    """Envia a lista semanal de artigos por revista para todos os assinantes."""
    log.info("=" * 60)
    log.info("LISTA SEMANAL — artigos por revista")
    log.info("=" * 60)

    sb = conectar_supabase()
    artigos = buscar_artigos_semana(sb, dias=7)
    log.info(f"  {len(artigos)} artigos nota ≥ 8 nos últimos 7 dias")

    mensagem = montar_lista_semanal(artigos)
    log.info(f"  Mensagem: {len(mensagem)} chars")

    if dry_run:
        log.info("--- PREVIEW ---")
        log.info(mensagem)
        log.info("--- FIM PREVIEW (dry-run, nada enviado) ---")
        return

    assinantes = buscar_assinantes_ativos(sb)
    enviados = 0
    for assinante in assinantes:
        phone = assinante.get("phone", "")
        nome = assinante.get("nome", phone)
        ok = zapi_send_text(phone, mensagem)
        tg_send_text(mensagem)
        status = "✅" if ok else "⚠️"
        log.info(f"  {status} {nome} ({phone})")
        if ok:
            enviados += 1

    log.info(f"Lista semanal enviada para {enviados}/{len(assinantes)} assinantes.")


# =============================================================================
# LISTA DIÁRIA NAVEGÁVEL — FORMATO A (07:00)
# =============================================================================

def distribuir_lista_diaria(dry_run: bool = False):
    """
    Envia lista A (5 artigos com gancho) personalizada por temas de cada assinante.
    Substitui distribuir_artigos() como envio padrão das 07:00.
    """
    log.info("=" * 60)
    log.info("LISTA DIÁRIA NAVEGÁVEL — 07:00")
    log.info(f"Data: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    log.info("=" * 60)

    if not _LISTA_OK:
        log.error("❌ src/lista_whatsapp.py não encontrado — abortando.")
        sys.exit(1)

    if not dry_run and not zapi_check_connected():
        log.error("❌ Z-API desconectada — lista diária abortada.")
        sys.exit(1)
    if not dry_run:
        log.info("✅ Z-API conectada")

    sb = conectar_supabase()
    assinantes = buscar_assinantes_ativos(sb)
    enviados = 0

    for assinante in assinantes:
        nome  = assinante.get("nome", "?")
        phone = assinante.get("phone", "")
        temas = assinante.get("temas", [])

        if BETA_PAUSADO and phone != DR_EDUARDO_PHONE:
            log.info(f"  ⏸️  Beta pausado — pulando {nome}")
            continue

        msg = gerar_lista_diaria(
            formato=FORMATO_A,
            dias=10,
            n=5,
            temas=temas if temas else None,
            nota_min=7,
        )

        if "Sem novidades" in msg:
            log.info(f"  {nome}: sem novidades nos temas")
            continue

        log.info(f"  {nome} ({phone}) — {len(msg)} chars")

        if dry_run:
            log.info(f"  [DRY-RUN]\n{msg}\n")
            continue

        zapi_send_text(phone, msg)
        tg_send_text(msg)
        enviados += 1

    log.info(f"\n{'=' * 60}")
    log.info(f"LISTA DIÁRIA CONCLUÍDA — {enviados} enviados")
    log.info("=" * 60)


# =============================================================================
# LISTA SEMANAL POR REVISTA — FORMATO B (segunda 07:30)
# =============================================================================

def distribuir_lista_semanal(dry_run: bool = False):
    """
    Envia lista B (até 7 artigos por revista) para todos os assinantes.
    Roda às segundas 07:30 — usa revistas do dia (Circulation nas segundas).
    """
    log.info("=" * 60)
    log.info("LISTA SEMANAL POR REVISTA — FORMATO B")
    log.info(f"Data: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    log.info("=" * 60)

    if not _LISTA_OK:
        log.error("❌ src/lista_whatsapp.py não encontrado — abortando.")
        sys.exit(1)

    if not dry_run and not zapi_check_connected():
        log.error("❌ Z-API desconectada — lista semanal abortada.")
        sys.exit(1)
    if not dry_run:
        log.info("✅ Z-API conectada")

    msg = gerar_lista_semanal_por_revista(
        formato=FORMATO_B,
        dias=7,
        n=7,
        nota_min=7,
    )

    if "sem novidades" in msg.lower():
        log.info("Sem novidades para a lista semanal.")
        return

    log.info(f"  Mensagem: {len(msg)} chars")

    if dry_run:
        log.info(f"  [DRY-RUN]\n{msg}\n")
        return

    sb = conectar_supabase()
    assinantes = buscar_assinantes_ativos(sb)
    enviados = 0

    for assinante in assinantes:
        phone = assinante.get("phone", "")
        nome  = assinante.get("nome", phone)

        if BETA_PAUSADO and phone != DR_EDUARDO_PHONE:
            log.info(f"  ⏸️  Beta pausado — pulando {nome}")
            continue

        ok = zapi_send_text(phone, msg)
        tg_send_text(msg)
        log.info(f"  {'✅' if ok else '⚠️'} {nome} ({phone})")
        if ok:
            enviados += 1

    log.info(f"\n{'=' * 60}")
    log.info(f"LISTA SEMANAL CONCLUÍDA — {enviados} enviados")
    log.info("=" * 60)


# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python3 distribuidor.py [artigos|radar|semana|teste]")
        sys.exit(1)

    modo = sys.argv[1].lower()

    dry = "--dry-run" in sys.argv

    if modo == "lista_diaria":
        distribuir_lista_diaria(dry_run=dry)
    elif modo == "lista_semanal":
        distribuir_lista_semanal(dry_run=dry)
    elif modo == "artigos":
        distribuir_artigos()
    elif modo == "radar":
        distribuir_radar()
    elif modo == "semana":
        lista_semanal(dry_run=dry)
    elif modo == "teste":
        modo_teste()
    elif modo == "eduardo":
        distribuir_eduardo()
    else:
        print(f"Modo desconhecido: {modo}.")
        print("Use: lista_diaria | lista_semanal | artigos | radar | semana | teste | eduardo")
        sys.exit(1)
