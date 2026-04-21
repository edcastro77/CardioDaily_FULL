#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CardioDaily — WhatsApp User Manager
CRUD de usuários no Supabase (tabela whatsapp_users).
"""

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import requests

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")
except ImportError:
    pass

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY", "")

_HEADERS = lambda: {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}

# ─── 7 temas do CardioDaily ────────────────────────────────────────────────────

TEMAS = {
    "1":  {"slug": "coronaria",        "nome": "Coronária / DAC",         "emoji": "🫀"},
    "2":  {"slug": "cardiometabolico", "nome": "Cardiometabólico",        "emoji": "⚗️"},
    "3":  {"slug": "miocardiopatias",  "nome": "Miocardiopatias / IC",    "emoji": "💔"},
    "4":  {"slug": "valvulopatias",    "nome": "Valvulopatias",           "emoji": "🔬"},
    "5":  {"slug": "arritmia",         "nome": "Arritmia / FA",           "emoji": "⚡"},
    "6":  {"slug": "uti",              "nome": "UTI Cardiológica",        "emoji": "🏥"},
    "7":  {"slug": "imagem",           "nome": "Imagem CV",               "emoji": "🖼️"},
    "8":  {"slug": "prevencao",        "nome": "Prevenção CV",            "emoji": "🛡️"},
    "9":  {"slug": "genomica",         "nome": "Cardio-Genômica",         "emoji": "🧬"},
    "10": {"slug": "obstetrica",       "nome": "Cardio-Obstétrica",       "emoji": "🤰"},
    "11": {"slug": "oncologia",        "nome": "Cardio-Oncologia",        "emoji": "🎗️"},
}

# Mapeamento slug → doenca_principal no Supabase
TEMA_DOENCAS = {
    "coronaria":        ["Coronariopatia Aguda", "Imagem Cardiovascular", "Valvulopatias"],
    "cardiometabolico": ["Dislipidemias", "Hipertensão Arterial Sistêmica", "Farmacologia",
                         "Manifestações Cardiovasculares de Doenças Sistêmicas"],
    "genomica":         ["Miocardiopatias", "Cardiopatia Congênita"],
    "obstetrica":       ["Cardio-Obstetricia"],
    "oncologia":        ["Cardio-Oncologia"],
    "uti":              ["Insuficiencia Cardiaca"],
    "arritmia":         ["Arritmias"],
}

# Rotação diária de temas para o Radar (7 temas, 1 por dia)
# Rotação usada pelo daily_sender (temas de usuário — slugs da tabela whatsapp_users)
TEMAS_RADAR_ROTATION = [
    "coronaria", "cardiometabolico", "arritmia", "uti",
    "genomica", "obstetrica", "oncologia",
]

# Rotação usada pelo run_radar_diario.py (categorias PubMed — 12 temas, ciclo 12 dias)
# Mantida aqui para referência; a lista canônica está em scripts/run_radar_diario.py
RADAR_CATEGORIAS_ROTATION = [
    "doenca_coronariana", "insuficiencia_cardiaca", "arritmias", "prevencao_cv",
    "cardio_metabolica", "miocardiopatias", "valvulopatias", "cardiogeriatria",
    "hipertensao_pulmonar", "cirurgia_cardiaca", "cardiobstetrica", "cardio_oncologia",
]


def _url(table: str) -> str:
    return f"{SUPABASE_URL}/rest/v1/{table}"


def get_user(phone: str) -> Optional[dict]:
    """Retorna usuário pelo número ou None se não existir."""
    phone = _normalize_phone(phone)
    r = requests.get(
        f"{_url('whatsapp_users')}?phone=eq.{phone}&limit=1",
        headers=_HEADERS(),
        timeout=10,
    )
    data = r.json() if r.ok else []
    return data[0] if data else None


def create_user(phone: str, nome: str = "") -> dict:
    """Cria novo usuário com onboarding_step=1 (aguardando tema)."""
    phone = _normalize_phone(phone)
    payload = {
        "phone": phone,
        "nome": nome,
        "temas": [],
        "ativo": True,
        "beta_tester": True,
        "onboarding_step": 1,
        "artigos_enviados": [],
        "radar_tema_idx": 0,
    }
    r = requests.post(
        _url("whatsapp_users"),
        json=payload,
        headers=_HEADERS(),
        timeout=10,
    )
    return r.json()[0] if r.ok else payload


def update_user(phone: str, **fields) -> bool:
    """Atualiza campos do usuário."""
    phone = _normalize_phone(phone)
    r = requests.patch(
        f"{_url('whatsapp_users')}?phone=eq.{phone}",
        json=fields,
        headers=_HEADERS(),
        timeout=10,
    )
    return r.ok


def set_temas(phone: str, slugs: list[str]) -> bool:
    """Define preferências de tema e finaliza onboarding."""
    return update_user(phone, temas=slugs, onboarding_step=2)


def mark_artigo_enviado(phone: str, doc_id: str, current_list: list) -> bool:
    """Adiciona doc_id à lista de artigos já enviados."""
    nova_lista = list(set(current_list + [doc_id]))
    return update_user(phone, artigos_enviados=nova_lista, last_sent_at=_now())


def get_all_active() -> list[dict]:
    """Retorna todos os usuários ativos com onboarding completo."""
    r = requests.get(
        f"{_url('whatsapp_users')}?ativo=eq.true&onboarding_step=eq.2&order=created_at.asc",
        headers=_HEADERS(),
        timeout=10,
    )
    return r.json() if r.ok else []


def get_all_users() -> list[dict]:
    """Retorna todos os usuários (para admin)."""
    r = requests.get(
        f"{_url('whatsapp_users')}?order=created_at.desc",
        headers=_HEADERS(),
        timeout=10,
    )
    return r.json() if r.ok else []


def parse_tema_input(text: str) -> list[str]:
    """
    Converte input do usuário em lista de slugs.
    Ex: "1 3 10" → ["coronaria", "miocardiopatias", "obstetrica"]
    Ex: "1, 2, 11" → ["coronaria", "cardiometabolico", "oncologia"]
    """
    import re
    nums = re.findall(r'\d+', text)
    slugs = []
    seen = set()
    for n in nums:
        if n in TEMAS and n not in seen:
            slugs.append(TEMAS[n]["slug"])
            seen.add(n)
    return slugs


def menu_temas_text() -> str:
    """Retorna o texto do menu de temas para enviar ao usuário."""
    linhas = ["*Escolha seus temas de interesse:*\n"]
    for num, t in TEMAS.items():
        linhas.append(f"{t['emoji']} {num}. {t['nome']}")
    linhas.append("\n_Responda com os números separados por espaço_")
    linhas.append("_Exemplo: 1 3 7 (pode escolher mais de um)_")
    return "\n".join(linhas)


def _normalize_phone(phone: str) -> str:
    phone = phone.strip().replace("+", "").replace(" ", "").replace("-", "")
    if not phone.startswith("55"):
        phone = "55" + phone
    return phone


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
