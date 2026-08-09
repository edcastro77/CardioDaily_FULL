#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CardioDaily — Daily WhatsApp Sender
Seleciona e envia 2 artigos/dia + 1 podcast do Radar para cada usuário ativo.

USO:
    python3 src/whatsapp/daily_sender.py            # envia para todos
    python3 src/whatsapp/daily_sender.py --dry-run  # simula sem enviar
    python3 src/whatsapp/daily_sender.py --phone 5511999999999  # 1 usuário
"""

import argparse
import os
import voo as VOO          # plano de voo (09/Ago)
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_ROOT / "src"))

try:
    from dotenv import load_dotenv
    load_dotenv(_ROOT / ".env")
except ImportError:
    pass

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY", "")
BIBLIOTECA_URL = os.getenv("BIBLIOTECA_URL", "http://localhost:5100")

# URL pública do Supabase Storage (para imagens e podcasts)
STORAGE_URL = f"{SUPABASE_URL}/storage/v1/object/public"

_SB = lambda: {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}


# ─── Importações internas ──────────────────────────────────────────────────────

from whatsapp.user_manager import (
    TEMA_DOENCAS, TEMAS, TEMAS_RADAR_ROTATION,
    get_all_active, mark_artigo_enviado, update_user,
)
from whatsapp import zapi_client as zapi


# ─── Seleção de artigos ────────────────────────────────────────────────────────

NOTA_MINIMA     = 8
ARTIGOS_POR_DIA = 1

# Prioridade de tipo: menor número = maior prioridade (Original > Meta > Revisão)
_TIPO_PRIORIDADE = {
    "artigo_original":                  0,
    "original":                         0,
    "revisao_sistematica_meta_analise": 1,
    "metanalise":                       1,
    "revisao_geral":                    2,
    "revisao":                          2,
    "guideline":                        2,
}


def _artigos_para_usuario(user: dict, n: int = ARTIGOS_POR_DIA) -> list[dict]:
    """
    Retorna 1 artigo do tema do usuário que ele ainda não recebeu.
    Critérios: nota_aplicabilidade >= 8, tem visual_abstract, indexado nos últimos 15 dias.
    Prioridade de tipo: Original > Meta-análise > Revisão.
    Filtro por created_at (data de indexação, não de publicação na revista).
    """
    temas = user.get("temas") or []
    ja_enviados = user.get("artigos_enviados") or []

    doencas = []
    for slug in temas:
        doencas.extend(TEMA_DOENCAS.get(slug, []))

    if not doencas:
        doencas = None

    candidatos = _query_artigos(doencas, ja_enviados)
    return _selecionar(candidatos, n)


def _query_artigos(doencas: list | None, ja_enviados: list) -> list[dict]:
    """Query no Supabase — filtra por created_at (indexação) e nota >= 8."""
    # Filtra pelo created_at (data em que o Dr. Eduardo indexou) — não pela data da revista
    cutoff = (datetime.now() - timedelta(days=15)).strftime("%Y-%m-%d")

    params = [
        f"nota_aplicabilidade=gte.{NOTA_MINIMA}",
        "caminho_visual_abstract=not.is.null",
        f"created_at=gte.{cutoff}T00:00:00",
        "order=nota_aplicabilidade.desc,created_at.desc",
        "limit=30",
        "select=doc_id,titulo,revista,doenca_principal,tipo_estudo,nota_aplicabilidade,caminho_visual_abstract,caminho_audio,doi,data_publicacao,created_at",
    ]

    if doencas:
        filter_doencas = ",".join(f'"{d}"' for d in doencas)
        params.append(f"doenca_principal=in.({filter_doencas})")

    url = f"{SUPABASE_URL}/rest/v1/artigos?" + "&".join(params)
    r = requests.get(url, headers=_SB(), timeout=15)
    if not r.ok:
        print(f"  ⚠️  Erro Supabase: {r.status_code} — {r.text[:200]}")
        return []

    todos = r.json()
    return [a for a in todos if a["doc_id"] not in ja_enviados]


def _selecionar(candidatos: list, n: int) -> list[dict]:
    """Ordena por tipo (Original>Meta>Revisão) → nota DESC → created_at DESC e retorna n."""
    if not candidatos:
        return []

    def _prio(a):
        t = (a.get("tipo_estudo") or "").lower()
        return _TIPO_PRIORIDADE.get(t, 99)

    def _created(a):
        d = (a.get("created_at") or "0000-00-00").replace("-", "")[:8]
        try:
            return int(d)
        except ValueError:
            return 0

    candidatos.sort(key=lambda a: (
        _prio(a),
        -(a.get("nota_aplicabilidade") or 0),
        -_created(a),
    ))
    return candidatos[:n]


def _build_va_url(caminho: str) -> str:
    """Constrói URL pública do visual abstract no Supabase Storage."""
    if not caminho:
        return ""
    # caminho pode ser 'visual_abstracts/doc_id.png' ou URL completa
    if caminho.startswith("http"):
        return caminho
    return f"{STORAGE_URL}/{caminho}"


def _build_audio_url(caminho: str) -> str:
    """Constrói URL pública do podcast no Supabase Storage."""
    if not caminho:
        return ""
    if caminho.startswith("http"):
        return caminho
    return f"{STORAGE_URL}/{caminho}"


def _build_biblioteca_link(doc_id: str) -> str:
    """Link para a análise completa na biblioteca web."""
    return f"{BIBLIOTECA_URL}/artigo/{doc_id}"


# ─── Radar do dia ──────────────────────────────────────────────────────────────

def _radar_do_dia() -> dict | None:
    """
    Busca o radar mais recente gerado hoje.
    Retorna {'audio_url': ..., 'tema': ...} ou None.
    """
    radar_dir = _ROOT / "outputs" / "radar_audio"
    if not radar_dir.exists():
        return None

    hoje = datetime.now().strftime("%Y%m%d")
    mp3s = sorted(radar_dir.glob(f"*{hoje}*.mp3"), reverse=True)
    if not mp3s:
        return None

    # O áudio do radar é local — precisamos de uma URL pública
    # Por enquanto, tentamos o Supabase Storage bucket 'radar_audio'
    nome = mp3s[0].name
    audio_url = f"{STORAGE_URL}/radar_audio/{nome}"
    tema_idx = datetime.now().timetuple().tm_yday % len(TEMAS_RADAR_ROTATION)
    tema_slug = TEMAS_RADAR_ROTATION[tema_idx]
    tema_nome = next(
        (t["nome"] for t in TEMAS.values() if t["slug"] == tema_slug),
        tema_slug
    )
    return {"audio_url": audio_url, "tema": tema_nome, "arquivo": str(mp3s[0])}


# ─── Envio por usuário ─────────────────────────────────────────────────────────

def enviar_para_usuario(user: dict, dry_run: bool = False) -> dict:
    """
    Envia o pacote diário para 1 usuário.
    Retorna dict com resultados.
    """
    phone  = user["phone"]
    nome   = user.get("nome") or phone
    artigos = _artigos_para_usuario(user)

    result = {"phone": phone, "nome": nome, "artigos": 0, "radar": False, "errors": []}

    if not artigos:
        result["errors"].append("Nenhum artigo novo para os temas selecionados")
        return result

    print(f"\n  📱 {nome} ({phone}) — {len(artigos)} artigo(s)")

    for art in artigos:
        doc_id   = art["doc_id"]
        titulo   = art.get("titulo") or doc_id
        va_url   = _build_va_url(art.get("caminho_visual_abstract") or "")
        audio_url = _build_audio_url(art.get("caminho_audio") or "")
        link     = _build_biblioteca_link(doc_id)
        nota     = art.get("nota_aplicabilidade", 0)

        print(f"     📄 {titulo[:60]}... (NAC:{nota})")
        if dry_run:
            print(f"        [dry-run] VA: {va_url}")
            print(f"        [dry-run] Audio: {audio_url or 'N/A'}")
        else:
            ok = zapi.send_article_package(phone, {
                **art,
                "va_url":    va_url,
                "audio_url": audio_url,
                "link":      link,
            })
            if ok:
                result["artigos"] += 1
                mark_artigo_enviado(phone, doc_id, user.get("artigos_enviados") or [])
            else:
                result["errors"].append(f"Falha ao enviar {doc_id}")
        time.sleep(2)

    # Radar do dia
    radar = _radar_do_dia()
    if radar:
        tema_nome = radar["tema"]
        print(f"     🎙️ Radar: {tema_nome}")
        if dry_run:
            print(f"        [dry-run] Audio: {radar['audio_url']}")
        else:
            ok_text = zapi.send_text(phone, f"🎙️ *Radar CardioDaily — {tema_nome}*")
            ok_audio = zapi.send_audio(phone, radar["audio_url"])
            result["radar"] = ok_text and ok_audio
    else:
        print(f"     🎙️ Radar: nenhum áudio gerado hoje")

    return result


# ─── Runner principal ──────────────────────────────────────────────────────────

def run(phone_filter: str | None = None, dry_run: bool = False):
    print(f"\n{'='*55}")
    print(f"📲 CardioDaily — Envio Diário WhatsApp")
    print(f"   {datetime.now().strftime('%d/%m/%Y %H:%M')}  {'[DRY-RUN]' if dry_run else ''}")
    print(f"{'='*55}\n")

    if not zapi.ZAPI_INSTANCE_ID and not dry_run:
        print("❌ ZAPI_INSTANCE_ID não configurado no .env")
        return

    if phone_filter:
        user = None
        from whatsapp.user_manager import get_user
        user = get_user(phone_filter)
        if not user:
            print(f"⚠️  Usuário {phone_filter} não encontrado")
            return
        usuarios = [user]
    else:
        usuarios = get_all_active()

    # ═══ WAYPOINT E4 — "a lista de envio foi montada" (09/Ago) ═══
    # `get_all_active()` faz `return r.json() if r.ok else []`. Supabase fora do ar, chave
    # errada e "nenhum assinante" produzem EXATAMENTE o mesmo resultado: lista vazia. E o
    # placar do fim fecha com "✅ OK: 0", que parece um dia tranquilo. Um dia inteiro sem
    # entrega e sem ninguém saber.
    if not usuarios:
        VOO.marcar("E4_LISTA", ok=False, n_destinos=0,
                   erro="lista de assinantes VAZIA — pode ser banco fora, chave errada ou zero "
                        "assinantes; as três são indistinguíveis aqui")
        print("⚠️  NENHUM assinante retornado.")
        print("    Isto NÃO significa 'zero assinantes': o Supabase fora do ar devolve o mesmo.")
        print("    Confira a credencial antes de concluir que a base está vazia.")
    else:
        VOO.marcar("E4_LISTA", n_destinos=len(usuarios))
    print(f"👥 {len(usuarios)} usuário(s) ativo(s)\n")

    totais = {"ok": 0, "parcial": 0, "erro": 0}

    for user in usuarios:
        try:
            result = enviar_para_usuario(user, dry_run=dry_run)
            if result["artigos"] > 0:
                totais["ok"] += 1
            elif result["errors"]:
                totais["erro"] += 1
            else:
                totais["parcial"] += 1
        except Exception as e:
            print(f"  ❌ Erro fatal para {user['phone']}: {e}")
            totais["erro"] += 1

        if not dry_run:
            time.sleep(3)  # intervalo entre usuários

    # ═══ WAYPOINT E5 — "a mensagem saiu para os destinatários" ═══
    VOO.marcar("E5_ENVIOU", ok=(totais["ok"] > 0 and totais["erro"] == 0),
               n_ok=totais["ok"], n_parcial=totais["parcial"], n_falha=totais["erro"],
               n_destinos=len(usuarios),
               erro=None if totais["ok"] else "nenhuma entrega confirmada")
    print(f"\n{'='*55}")
    print(f"✅ OK: {totais['ok']}  ⚠️  Parcial: {totais['parcial']}  ❌ Erro: {totais['erro']}")
    if not totais["ok"]:
        print("⚠️  NINGUÉM recebeu nada nesta rodada.")
        print("    Zona de busca: Z-API sem crédito · BETA_PAUSADO=1 (envia só para o dono) ·")
        print("    temas do filtro que não existem no banco · lista de assinantes vazia.")
    print(f"{'='*55}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CardioDaily — Envio Diário WhatsApp")
    parser.add_argument("--dry-run", action="store_true", help="Simula sem enviar")
    parser.add_argument("--phone", help="Envia só para este número")
    args = parser.parse_args()
    run(phone_filter=args.phone, dry_run=args.dry_run)
