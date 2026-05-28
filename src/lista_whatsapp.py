"""
src/lista_whatsapp.py
=====================

Geração das mensagens WhatsApp do CardioDaily — lista navegável com pontuação.

Dois formatos:
  • FORMATO A (visual, com emoji de cor) — para WhatsApp do dia-a-dia
  • FORMATO B (sóbrio, com tag) — para a lista semanal de segunda

Ambos seguem a estrutura definida no CADERNO_EXECUCAO.md v22.0:
  - Header curto identificando o lote
  - Itens compactos: nota + revista + título + gancho de 1 linha + link
  - Rodapé com CTA de assinatura

Uso:
    from lista_whatsapp import (
        gerar_lista_diaria, gerar_lista_semanal_por_revista,
        FORMATO_A, FORMATO_B,
    )

    msg = gerar_lista_diaria(formato=FORMATO_A, dias=7, n=5,
                             temas=["coronaria", "arritmia"])
    print(msg)

Dependências: httpx (Supabase REST).
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")
except ImportError:
    pass

# -----------------------------------------------------------------------------
# Config
# -----------------------------------------------------------------------------
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")
SITE_BASE = os.getenv("CARDIODAILY_SITE_URL", "https://cardiodaily.com.br").rstrip("/")

FORMATO_A = "A"  # visual, emoji
FORMATO_B = "B"  # sóbrio, tag

# Mapeamento tema → doenca_principal (cópia fiel do distribuidor.py)
TEMA_PARA_DOENCA = {
    "coronaria": ["Coronariopatia Aguda", "Coronariopatia Crônica", "Intervenção Vascular"],
    "cardiometabolico": ["Dislipidemias", "Cardiometabólica", "Manifestações CV"],
    "miocardiopatias": ["Miocardiopatias", "IC", "Cardio-Onco", "Cardio-Obstet", "Congênitas", "Aortopatias"],
    "prevencao": ["HAS", "Pré-Op", "Prevenção CV", "Farmacologia", "Outros"],
    "valvulopatias": ["Valvulopatias"],
    "arritmia": ["Arritmias", "Marcapasso", "Stroke"],
    "uti": ["Emergências/UTI"],
    "imagem": ["Imagem Cardiovascular"],
}

AGENDA_SEMANAL_REVISTAS = {
    0: ("Segunda", ["Circulation"]),
    1: ("Terça", ["JACC"]),
    3: ("Quinta", ["NEJM", "JAMA"]),
    4: ("Sexta", ["European Heart Journal", "EHJ"]),
    5: ("Sábado", ["Revisões — AHJ, AHA Journals, Clinics"]),
    6: ("Domingo", ["Revisões — AHJ, AHA Journals, Clinics"]),
}

DIAS_PT = {
    0: "Segunda", 1: "Terça", 2: "Quarta", 3: "Quinta",
    4: "Sexta", 5: "Sábado", 6: "Domingo",
}

# -----------------------------------------------------------------------------
# Helpers de formato
# -----------------------------------------------------------------------------
def emoji_por_nota(nac: int | float | None) -> str:
    if nac is None:
        return "🟠"
    n = int(round(nac))
    if n >= 10:
        return "💎"
    if n >= 8:
        return "🟢"
    if n == 7:
        return "🟡"
    return "🟠"

def tag_por_nota(nac: int | float | None) -> str:
    n = int(round(nac)) if nac is not None else 0
    return f"[NAC {n}]"

def truncar_titulo(t: str | None, max_chars: int = 75) -> str:
    if not t:
        return "(sem título)"
    t = t.strip().replace("\n", " ")
    if len(t) <= max_chars:
        return t
    return t[:max_chars - 1].rsplit(" ", 1)[0] + "…"

def revista_curta(r: str | None) -> str:
    if not r:
        return "?"
    aliases = {
        "New England Journal of Medicine": "NEJM",
        "Journal of the American Medical Association": "JAMA",
        "Journal of the American College of Cardiology": "JACC",
        "European Heart Journal": "EHJ",
        "American Heart Journal": "AHJ",
        "Arquivos Brasileiros de Cardiologia": "Arq Bras Cardiol",
        "Circulation": "Circulation",
        "JAMA Cardiology": "JAMA Cardio",
    }
    return aliases.get(r.strip(), r.strip())

def url_artigo(doc_id: str, slug: str | None = None) -> str:
    s = (slug or doc_id).strip().replace(" ", "-").lower()
    return f"{SITE_BASE}/a/{s}"

# -----------------------------------------------------------------------------
# Supabase fetch
# -----------------------------------------------------------------------------
def _sb_headers() -> dict:
    return {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
    }

def _buscar_artigos(
    nota_min: int,
    dias: int,
    doencas: list[str] | None = None,
    revistas: list[str] | None = None,
    limite: int = 7,
) -> list[dict]:
    desde = (datetime.now(timezone.utc) - timedelta(days=dias)).isoformat()
    url = f"{SUPABASE_URL}/rest/v1/artigos"
    params = {
        "select": "doc_id,titulo,revista,nota_aplicabilidade,gancho_lista,doenca_principal,created_at",
        "nota_aplicabilidade": f"gte.{nota_min}",
        "created_at": f"gte.{desde}",
        "gancho_lista": "not.is.null",
        "order": "nota_aplicabilidade.desc,created_at.desc",
        "limit": str(limite),
    }
    if doencas:
        valores = ",".join(f'"{d}"' for d in doencas)
        params["doenca_principal"] = f"in.({valores})"

    r = httpx.get(url, headers=_sb_headers(), params=params, timeout=30)
    r.raise_for_status()
    artigos = r.json()

    if revistas:
        revistas_lower = [x.lower() for x in revistas]
        artigos = [a for a in artigos
                   if any(rv in (a.get("revista") or "").lower() for rv in revistas_lower)]

    return artigos[:limite]

# -----------------------------------------------------------------------------
# Renderização
# -----------------------------------------------------------------------------
def _render_item(artigo: dict, formato: str) -> str:
    nota = artigo.get("nota_aplicabilidade")
    revista = revista_curta(artigo.get("revista"))
    titulo = truncar_titulo(artigo.get("titulo"))
    gancho = (artigo.get("gancho_lista") or "").strip()
    url = url_artigo(artigo["doc_id"])

    if formato == FORMATO_A:
        linha1 = f"{emoji_por_nota(nota)} *{int(round(nota))}* · *{revista}* · {titulo}"
        linha2 = gancho if gancho else "—"
        linha3 = f"👉 {url}"
        return f"{linha1}\n{linha2}\n{linha3}"

    linha1 = f"{tag_por_nota(nota)} {revista} · {titulo}"
    linha2 = (gancho + ".") if gancho and not gancho.endswith(".") else (gancho or "—")
    linha3 = f"→ {url}"
    return f"{linha1}\n{linha2}\n{linha3}"

def _render_header_diaria(formato: str, dia: datetime, doencas_legenda: str, total: int) -> str:
    data_str = dia.strftime("%d/%m")
    dia_pt = DIAS_PT[dia.weekday()]
    if formato == FORMATO_A:
        return f"📋 *CardioDaily — {dia_pt} {data_str}*\n{doencas_legenda} · {total} novos nota ≥ 7"
    return f"*CardioDaily — {dia_pt} {data_str}*\n{doencas_legenda} · {total} novos nota ≥ 7"

def _render_header_semanal(formato: str, dia: datetime, revistas: list[str], total: int) -> str:
    data_str = dia.strftime("%d/%m")
    dia_pt = DIAS_PT[dia.weekday()]
    rev_str = " + ".join(revistas)
    if formato == FORMATO_A:
        return f"📋 *CardioDaily — {dia_pt} {data_str}*\n{rev_str} · {total} novos nota ≥ 7"
    return f"*CardioDaily — {dia_pt} {data_str}*\n{rev_str} · {total} novos nota ≥ 7"

def _render_footer(formato: str) -> str:
    if formato == FORMATO_A:
        return f"_Para acessar tudo: {SITE_BASE}/assinar_"
    return f"Para acessar tudo: {SITE_BASE}/assinar"

# -----------------------------------------------------------------------------
# API pública
# -----------------------------------------------------------------------------
def gerar_lista_diaria(
    formato: str = FORMATO_A,
    dias: int = 7,
    n: int = 5,
    temas: list[str] | None = None,
    nota_min: int = 7,
    dia_referencia: datetime | None = None,
) -> str:
    dia = dia_referencia or datetime.now()
    doencas = None
    if temas:
        doencas = []
        for t in temas:
            doencas.extend(TEMA_PARA_DOENCA.get(t.lower(), []))
        doencas = list(set(doencas))

    artigos = _buscar_artigos(nota_min=nota_min, dias=dias, doencas=doencas, limite=n)

    if not artigos:
        if formato == FORMATO_A:
            return f"📋 *CardioDaily — {DIAS_PT[dia.weekday()]} {dia.strftime('%d/%m')}*\n\nSem novidades relevantes nos seus temas nos últimos {dias} dias."
        return f"*CardioDaily — {DIAS_PT[dia.weekday()]} {dia.strftime('%d/%m')}*\n\nSem novidades relevantes nos seus temas nos últimos {dias} dias."

    doencas_legenda = ", ".join(temas) if temas else "Todos os temas"
    header = _render_header_diaria(formato, dia, doencas_legenda, len(artigos))
    itens = "\n\n".join(_render_item(a, formato) for a in artigos)
    footer = _render_footer(formato)
    return f"{header}\n\n{itens}\n\n{footer}"

def gerar_lista_semanal_por_revista(
    formato: str = FORMATO_B,
    revistas: list[str] | None = None,
    dias: int = 7,
    n: int = 7,
    nota_min: int = 7,
    dia_referencia: datetime | None = None,
) -> str:
    dia = dia_referencia or datetime.now()
    if revistas is None:
        revistas = AGENDA_SEMANAL_REVISTAS.get(dia.weekday(), ("?", []))[1]
        if not revistas:
            revistas = ["NEJM", "JAMA", "Circulation", "JACC", "EHJ"]

    artigos = _buscar_artigos(nota_min=nota_min, dias=dias, revistas=revistas, limite=n)

    if not artigos:
        rev_str = " + ".join(revistas)
        if formato == FORMATO_A:
            return f"📋 *CardioDaily — {DIAS_PT[dia.weekday()]} {dia.strftime('%d/%m')}*\n\n{rev_str} sem novidades nos últimos {dias} dias."
        return f"*CardioDaily — {DIAS_PT[dia.weekday()]} {dia.strftime('%d/%m')}*\n\n{rev_str} sem novidades nos últimos {dias} dias."

    header = _render_header_semanal(formato, dia, revistas, len(artigos))
    itens = "\n\n".join(_render_item(a, formato) for a in artigos)
    footer = _render_footer(formato)
    return f"{header}\n\n{itens}\n\n{footer}"
