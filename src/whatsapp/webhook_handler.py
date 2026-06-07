#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CardioDaily — WhatsApp Webhook Handler

Processa mensagens inbound do Z-API:
- PDF recebido  → analisa com pipeline completo → devolve VA + texto + PDF + áudio
- Texto "buscar X" → consulta Supabase → lista artigos
- Onboarding de temas (novo usuário)
- Comandos: temas, parar, retomar, status
"""

import os
import sys
import logging
import tempfile
import threading
import requests
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "src"))

from whatsapp.user_manager import (
    TEMAS, get_user, create_user, set_temas, parse_tema_input,
    menu_temas_text, update_user,
)
from whatsapp import zapi_client as zapi

log = logging.getLogger("webhook")

# ─── Mensagens ────────────────────────────────────────────────────────────────

MSG_BOAS_VINDAS = """\
👋 Bem-vindo ao *CardioDaily*!

Sou seu assistente de literatura cardiológica com IA.

📅 Todo dia você receberá:
• 1 artigo selecionado (NAC ≥ 8) com visual abstract
• Podcast do Radar PubMed

Para começar, preciso saber seus temas de interesse 👇"""

MSG_CONFIRMACAO = """\
✅ Preferências salvas!

A partir de amanhã às 7h você receberá os artigos do dia.

💡 *Comandos disponíveis:*
• Envie um *PDF* → análise completa em ~5 minutos
• *buscar [tema]* → últimos artigos sobre o tema
• *temas* — alterar preferências
• *parar* — pausar envios
• *retomar* — reativar envios
• *status* — ver seu perfil"""

MSG_PAUSA = "⏸️ Envios pausados. Digite *retomar* quando quiser voltar."
MSG_RETOMADA = "▶️ Envios reativados! Você voltará a receber artigos amanhã."
MSG_AJUDA = """\
📚 *CardioDaily — Comandos*

📎 Envie um *PDF* de artigo → análise completa com visual abstract, podcast e resumo

🔍 *buscar [tema]* — busca na base de 3.700 artigos
   Ex: _buscar insuficiência cardíaca_
   Ex: _buscar stress CMR_

⚙️ *temas* — alterar preferências de tema
⚙️ *parar* — pausar envios diários
⚙️ *retomar* — reativar envios
⚙️ *status* — ver seu perfil"""

MSG_STATUS_TEMPLATE = """\
📊 *Seu perfil CardioDaily*

📱 Número: {phone}
🏷️ Temas: {temas}
📬 Status: {status}
📄 Artigos recebidos: {total}"""

MSG_PDF_RECEBIDO = """\
📄 *PDF recebido!* ✅

📝 _{titulo}_
🔬 Passando pelo filtro CardioDaily...
Em ~5 minutos você recebe:
• Visual Abstract
• Podcast do artigo
• PDF resumo com análise clínica"""

MSG_PDF_ERRO = "❌ Não consegui processar o PDF. Verifique se o arquivo é um artigo médico completo e tente novamente."
MSG_BUSCA_VAZIA = "🔍 Nenhum artigo encontrado para *{q}*. Tente um termo diferente (ex: _buscar coronária_, _buscar fibrilação atrial_)."


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _temas_formatados(slugs: list) -> str:
    if not slugs:
        return "nenhum"
    nomes = []
    for slug in slugs:
        for t in TEMAS.values():
            if t["slug"] == slug:
                nomes.append(f"{t['emoji']} {t['nome']}")
                break
    return ", ".join(nomes)


def _baixar_pdf(url: str, dest: Path) -> bool:
    """Baixa PDF da URL do Z-API para arquivo local."""
    try:
        r = requests.get(url, timeout=60, stream=True)
        if r.status_code != 200:
            return False
        dest.write_bytes(r.content)
        return dest.stat().st_size > 1000
    except Exception as e:
        log.error(f"Erro ao baixar PDF: {e}")
        return False


def _buscar_supabase(q: str, limite: int = 10) -> list[dict]:
    """Busca artigos no Supabase por termo livre — direto via REST API."""
    try:
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env")
        sb_url = os.getenv("SUPABASE_URL", "").rstrip("/")
        sb_key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY", "")
        if not sb_url or not sb_key:
            log.error("SUPABASE_URL ou SUPABASE_KEY não configurados")
            return []

        hdrs = {"apikey": sb_key, "Authorization": f"Bearer {sb_key}"}

        # Expandir termos PT→EN
        sys.path.insert(0, str(ROOT / "src"))
        try:
            from web_biblioteca import _expand
            termos = _expand(q.lower().strip())
        except Exception:
            termos = [q.lower().strip()]

        # Construir filtro OR: título, doenca_principal, gancho_lista
        filtros = []
        for t in termos[:6]:
            s = t.replace("'", "''")
            filtros.append(f"titulo.ilike.%{s}%")
            filtros.append(f"doenca_principal.ilike.%{s}%")
            filtros.append(f"gancho_lista.ilike.%{s}%")

        params = {
            "select": "doc_id,titulo,revista,nota_aplicabilidade,doenca_principal,data_publicacao",
            "or": f"({','.join(filtros)})",
            "nota_aplicabilidade": "gte.5",
            "order": "nota_aplicabilidade.desc,created_at.desc",
            "limit": str(limite),
        }

        r = requests.get(f"{sb_url}/rest/v1/artigos", headers=hdrs, params=params, timeout=15)
        log.info(f"buscar_supabase status={r.status_code} q={q!r} termos={termos}")

        if r.status_code != 200:
            log.error(f"Supabase erro {r.status_code}: {r.text[:200]}")
            return []

        return r.json() if isinstance(r.json(), list) else []

    except Exception as e:
        log.error(f"_buscar_supabase erro: {e}")
        return []


def _analisar_pdf_async(phone: str, pdf_path: Path, filename: str):
    """Roda análise completa em thread separada e envia resultado ao usuário."""
    try:
        sys.path.insert(0, str(ROOT / "src"))
        from article_analyzer import ArticleAnalyzer
        import os as _os

        # Diretório temporário para este artigo
        tmp_dir = pdf_path.parent

        analyzer = ArticleAnalyzer(input_local_dir=str(tmp_dir))
        file_info = {
            "name": filename,
            "path": str(pdf_path),
            "local": True,
            "id": None,
        }

        log.info(f"[{phone}] Iniciando análise: {filename}")
        resultado = analyzer.process_article(file_info)

        if not resultado:
            zapi.send_text(phone, MSG_PDF_ERRO)
            return

        # Buscar artigo recém-indexado no Supabase pelo doc_id
        doc_id = resultado if isinstance(resultado, str) else None

        # Tentar obter URLs do Supabase
        sb_url = _os.getenv("SUPABASE_URL", "").rstrip("/")
        sb_key = _os.getenv("SUPABASE_SERVICE_KEY") or _os.getenv("SUPABASE_KEY", "")
        artigo = {}

        if doc_id and sb_url and sb_key:
            r = requests.get(
                f"{sb_url}/rest/v1/artigos",
                params={"select": "doc_id,titulo,revista,doenca_principal,nota_aplicabilidade,"
                                   "caminho_visual_abstract,caminho_audio,caminho_pdf",
                        "doc_id": f"eq.{doc_id}"},
                headers={"apikey": sb_key, "Authorization": f"Bearer {sb_key}"},
                timeout=15,
            )
            rows = r.json() if r.status_code == 200 else []
            if rows:
                artigo = rows[0]

        # Fallback: tentar achar assets na pasta local
        if not artigo.get("caminho_visual_abstract"):
            va_local = tmp_dir / doc_id / "assets" / "visual_abstract.png" if doc_id else None
            if va_local and va_local.exists():
                artigo["_va_local"] = str(va_local)

        _enviar_resultado(phone, artigo, doc_id)

    except Exception as e:
        log.exception(f"[{phone}] Erro na análise: {e}")
        zapi.send_text(phone, MSG_PDF_ERRO)
    finally:
        # Limpar arquivo temporário
        try:
            pdf_path.unlink(missing_ok=True)
        except Exception:
            pass


def _enviar_resultado(phone: str, artigo: dict, doc_id: str | None):
    """Envia pacote completo após análise."""
    titulo = artigo.get("titulo") or "Artigo analisado"
    revista = artigo.get("revista") or ""
    doenca = artigo.get("doenca_principal") or ""
    nota = artigo.get("nota_aplicabilidade") or 0
    va_url = artigo.get("caminho_visual_abstract") or ""
    audio_url = artigo.get("caminho_audio") or ""
    pdf_url = artigo.get("caminho_pdf") or ""

    import time

    # 1. Visual abstract
    if va_url:
        zapi.send_image(phone, va_url, caption="")
        time.sleep(1)

    # 2. Texto resumo
    estrelas = "⭐" * min(int(nota or 0), 10)
    linhas = [
        "🧬 *Análise CardioDaily concluída*\n",
        f"📌 *{titulo}*",
        f"📔 _{revista}_ | 🏷️ {doenca}",
        f"⭐ NAC {nota}/10  {estrelas}",
    ]
    if pdf_url:
        linhas.append("\n📄 PDF resumo disponível abaixo.")
    if audio_url:
        linhas.append("🎙️ Podcast do artigo disponível abaixo.")
    linhas.append("\n_CardioDaily — Dados a fatos, sem firulas._")
    zapi.send_text(phone, "\n".join(linhas))
    time.sleep(1)

    # 3. PDF resumo
    if pdf_url:
        nome_pdf = f"CardioDaily_{(titulo or 'artigo')[:40].replace(' ','_')}.pdf"
        zapi.send_document(phone, pdf_url, nome_pdf, caption="")
        time.sleep(1)

    # 4. Podcast
    if audio_url:
        zapi.send_audio(phone, audio_url)

    if not any([va_url, pdf_url, audio_url]):
        zapi.send_text(phone, "✅ Análise concluída! O artigo foi indexado na base CardioDaily.")

    log.info(f"[{phone}] Pacote enviado — doc_id={doc_id}")


def _handle_busca(phone: str, query: str):
    """Processa pedido de busca e responde com lista de artigos."""
    q = query.strip()
    if not q:
        zapi.send_text(phone, MSG_AJUDA)
        return

    zapi.send_text(phone, f"🔍 Buscando artigos sobre *{q}*...")
    artigos = _buscar_supabase(q, limite=10)

    if not artigos:
        zapi.send_text(phone, MSG_BUSCA_VAZIA.format(q=q))
        return

    linhas = [f"📚 *{len(artigos)} artigos encontrados* — _{q}_\n"]
    for i, a in enumerate(artigos, 1):
        titulo = (a.get("titulo_display") or a.get("titulo") or "Sem título")[:65]
        nota = a.get("nota_aplicabilidade") or 0
        revista = (a.get("revista") or "")[:25].replace("_", " ")
        ano = (a.get("data_publicacao") or "")[:4]
        linhas.append(f"{i}. *[{nota}]* {titulo}\n   _{revista}_ {ano}")

    linhas.append("\n_Para análise completa de um artigo, envie o PDF._")
    zapi.send_text(phone, "\n".join(linhas))


# ─── Handler principal ────────────────────────────────────────────────────────

def handle_webhook(payload: dict) -> dict:
    """
    Processa evento recebido do Z-API.
    Retorna {"handled": bool, "action": str}.
    """
    # Ignorar mensagens de grupo
    if payload.get("isGroupMsg"):
        return {"handled": False, "action": "group_ignored"}

    # Ignorar callbacks de envio
    if payload.get("type") not in ("ReceivedCallback", "received"):
        return {"handled": False, "action": "not_received"}

    phone = payload.get("phone", "").strip()
    body  = (payload.get("body") or "").strip()
    nome  = payload.get("senderName") or ""

    if not phone:
        return {"handled": False, "action": "empty_phone"}

    # ── PDF recebido ───────────────────────────────────────────────────────────
    msg_type = (payload.get("messageType") or payload.get("type", "")).lower()
    is_pdf = (
        msg_type in ("document", "documentmessage")
        or (payload.get("mimetype") or "").lower() == "application/pdf"
        or (body or "").lower().endswith(".pdf")
    )

    if is_pdf:
        pdf_url = (
            payload.get("documentUrl")
            or payload.get("mediaUrl")
            or payload.get("url")
            or ""
        )
        filename = payload.get("fileName") or payload.get("caption") or "artigo.pdf"
        if not filename.lower().endswith(".pdf"):
            filename += ".pdf"

        # Confirmação imediata
        titulo_display = filename.replace(".pdf", "").replace("_", " ")[:60]
        zapi.send_text(phone, MSG_PDF_RECEBIDO.format(titulo=titulo_display))

        if pdf_url:
            # Baixar e analisar em background
            tmp_dir = Path(tempfile.mkdtemp(prefix="cardiodaily_"))
            pdf_path = tmp_dir / filename
            if _baixar_pdf(pdf_url, pdf_path):
                t = threading.Thread(
                    target=_analisar_pdf_async,
                    args=(phone, pdf_path, filename),
                    daemon=True,
                )
                t.start()
                return {"handled": True, "action": "pdf_analysis_started"}
            else:
                zapi.send_text(phone, MSG_PDF_ERRO)
                return {"handled": True, "action": "pdf_download_failed"}
        else:
            zapi.send_text(phone, "⚠️ Não consegui acessar o arquivo PDF. Tente reenviar.")
            return {"handled": True, "action": "pdf_no_url"}

    # ── Mensagens de texto ─────────────────────────────────────────────────────
    body_lower = body.lower()

    if not body_lower:
        return {"handled": False, "action": "empty_body"}

    user = get_user(phone)

    # Novo usuário
    if not user:
        user = create_user(phone, nome)
        zapi.send_text(phone, MSG_BOAS_VINDAS)
        zapi.send_text(phone, menu_temas_text())
        return {"handled": True, "action": "onboarding_start"}

    step = user.get("onboarding_step", 0)

    # Aguardando escolha de temas
    if step == 1:
        slugs = parse_tema_input(body_lower)
        if slugs:
            set_temas(phone, slugs)
            temas_str = _temas_formatados(slugs)
            zapi.send_text(phone, f"✅ Temas: {temas_str}\n\n{MSG_CONFIRMACAO}")
            return {"handled": True, "action": "temas_saved"}
        else:
            zapi.send_text(phone, "⚠️ Não entendi. " + menu_temas_text())
            return {"handled": True, "action": "invalid_tema_input"}

    # Comandos
    if body_lower in ("temas", "tema", "preferência", "preferencias"):
        update_user(phone, onboarding_step=1)
        zapi.send_text(phone, menu_temas_text())
        return {"handled": True, "action": "temas_reset"}

    if body_lower in ("parar", "stop", "pausar", "pause"):
        update_user(phone, ativo=False)
        zapi.send_text(phone, MSG_PAUSA)
        return {"handled": True, "action": "paused"}

    if body_lower in ("retomar", "resumir", "ativar", "start"):
        update_user(phone, ativo=True)
        zapi.send_text(phone, MSG_RETOMADA)
        return {"handled": True, "action": "resumed"}

    if body_lower == "status":
        temas_str = _temas_formatados(user.get("temas") or [])
        status_str = "✅ Ativo" if user.get("ativo") else "⏸️ Pausado"
        total = len(user.get("artigos_enviados") or [])
        zapi.send_text(phone, MSG_STATUS_TEMPLATE.format(
            phone=phone, temas=temas_str, status=status_str, total=total))
        return {"handled": True, "action": "status_sent"}

    # Busca de artigos
    if body_lower.startswith(("buscar ", "busca ", "artigos sobre ", "me manda ", "me mostre ")):
        for prefix in ("buscar ", "busca ", "artigos sobre ", "me manda ", "me mostre "):
            if body_lower.startswith(prefix):
                query = body[len(prefix):].strip()
                break
        t = threading.Thread(target=_handle_busca, args=(phone, query), daemon=True)
        t.start()
        return {"handled": True, "action": "search_started"}

    # Fallback
    zapi.send_text(phone, MSG_AJUDA)
    return {"handled": True, "action": "help_sent"}
