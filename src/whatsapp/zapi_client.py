#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CardioDaily — Z-API Client
Wrapper para a API do Z-API (WhatsApp Business).

Documentação: https://developer.z-api.io
"""

import os
import time
from pathlib import Path

import requests

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")
except ImportError:
    pass

ZAPI_INSTANCE_ID   = os.getenv("ZAPI_INSTANCE_ID", "")
ZAPI_TOKEN         = os.getenv("ZAPI_TOKEN", "")
ZAPI_CLIENT_TOKEN  = os.getenv("ZAPI_CLIENT_TOKEN", "")

_BASE = "https://api.z-api.io/instances/{instance}/token/{token}"


def _base_url() -> str:
    return _BASE.format(instance=ZAPI_INSTANCE_ID, token=ZAPI_TOKEN)


def _headers() -> dict:
    h = {"Content-Type": "application/json"}
    if ZAPI_CLIENT_TOKEN:
        h["Client-Token"] = ZAPI_CLIENT_TOKEN
    return h


def _normalize_phone(phone: str) -> str:
    """Garante formato 55XXXXXXXXXXX (sem + ou espaços)."""
    phone = phone.strip().replace("+", "").replace(" ", "").replace("-", "")
    if not phone.startswith("55"):
        phone = "55" + phone
    return phone


def send_text(phone: str, message: str) -> bool:
    """Envia mensagem de texto."""
    phone = _normalize_phone(phone)
    r = requests.post(
        f"{_base_url()}/send-text",
        json={"phone": phone, "message": message},
        headers=_headers(),
        timeout=15,
    )
    if not r.ok:
        print(f"  Z-API send_text erro {r.status_code}: {r.text[:200]}")
    return r.ok


def send_image(phone: str, image_url: str, caption: str = "") -> bool:
    """Envia imagem com legenda opcional."""
    phone = _normalize_phone(phone)
    r = requests.post(
        f"{_base_url()}/send-image",
        json={"phone": phone, "image": image_url, "caption": caption},
        headers=_headers(),
        timeout=20,
    )
    if not r.ok:
        print(f"  Z-API send_image erro {r.status_code}: {r.text[:200]}")
    return r.ok


def send_audio(phone: str, audio_url: str) -> bool:
    """Envia MP3 como documento (mais compatível que send-audio PTT)."""
    phone = _normalize_phone(phone)
    r = requests.post(
        f"{_base_url()}/send-document/mp3",
        json={"phone": phone, "document": audio_url, "fileName": "podcast_cardiodaily.mp3"},
        headers=_headers(),
        timeout=30,
    )
    if not r.ok:
        print(f"  Z-API send_audio erro {r.status_code}: {r.text[:200]}")
    return r.ok


def send_document(phone: str, doc_url: str, filename: str, caption: str = "") -> bool:
    """Envia documento (PDF)."""
    phone = _normalize_phone(phone)
    r = requests.post(
        f"{_base_url()}/send-document/pdf",
        json={"phone": phone, "document": doc_url, "fileName": filename, "caption": caption},
        headers=_headers(),
        timeout=20,
    )
    if not r.ok:
        print(f"  Z-API send_document erro {r.status_code}: {r.text[:200]}")
    return r.ok


def is_connected() -> bool:
    """Verifica se a instância está conectada ao WhatsApp."""
    if not ZAPI_INSTANCE_ID or not ZAPI_TOKEN:
        return False
    try:
        r = requests.get(
            f"{_base_url()}/status",
            headers=_headers(),
            timeout=10,
        )
        return r.ok and r.json().get("connected", False)
    except Exception:
        return False


def send_article_package(phone: str, artigo: dict, biblioteca_url: str = "") -> bool:
    """
    Envia pacote completo de 1 artigo:
    1. Visual abstract (imagem)
    2. Texto com resumo + link
    3. Podcast (se disponível)
    """
    doc_id   = artigo.get("doc_id", "")
    titulo   = artigo.get("titulo", "Artigo CardioDaily")
    revista  = artigo.get("revista", "")
    nota     = artigo.get("nota_aplicabilidade") or artigo.get("nota_geral", 0)
    doenca   = artigo.get("doenca_principal", "")
    va_url   = artigo.get("va_url", "")       # URL pública do visual_abstract.png
    audio_url = artigo.get("audio_url", "")  # URL pública do podcast.mp3
    link     = artigo.get("link", "")        # Link da análise na biblioteca

    ok_img = True
    ok_audio = True

    # 1. Visual abstract
    if va_url:
        ok_img = send_image(phone, va_url, caption="")
        time.sleep(1)

    # 2. Texto
    estrelas = "⭐" * min(int(nota), 10)
    linhas = [
        f"📄 *{titulo}*",
        f"📔 _{revista}_ | 🏷️ {doenca}",
        f"🎯 NAC: {nota}/10  {estrelas}",
    ]
    if link:
        linhas.append(f"📖 Análise completa: {link}")
    # ═══ 09/Ago — O TEXTO ERA A ÚNICA PEÇA OBRIGATÓRIA, E ERA A ÚNICA NÃO CONFERIDA ═══
    # `send_text(...)` sem guardar o retorno, e `ok_img`/`ok_audio` começando em True (linhas
    # acima). Um artigo sem imagem e sem áudio — o caso comum — devolvia True SEMPRE, mesmo com
    # a Z-API fora do ar. E quem chama usa esse True para MARCAR O ARTIGO COMO ENVIADO, o que
    # significa que ele nunca mais é tentado. A mensagem some e o placar diz "OK".
    ok_texto = send_text(phone, "\n".join(linhas))
    time.sleep(1)

    # 3. Podcast
    if audio_url:
        ok_audio = send_audio(phone, audio_url)

    # o TEXTO é o mínimo: sem ele não houve entrega, com ou sem mídia.
    return bool(ok_texto) and ok_img and ok_audio
