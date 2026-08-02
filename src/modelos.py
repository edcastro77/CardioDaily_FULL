"""
modelos.py — CONFIG CENTRAL DE MODELOS do CardioDaily. UM lugar só (mata a máquina de sangrar).

Decisão do Dr. Eduardo (24/07/2026):
  • Escrita com raciocínio pesado (Pesquisador, pontos críticos) → OPUS 5.
  • Escrita em geral (perícia, redator, análise de artigo — a maioria) → SONNET 5.
  • Simples (filtragem, triagem, volume sem raciocínio) → HAIKU / GEMINI FLASH.

LEI DA EQUIVALÊNCIA (inviolável): o fallback é sempre de OUTRO provedor + tier EQUIVALENTE.
  Nunca do mesmo dono (se faltou crédito na Anthropic, Opus/Sonnet/Haiku caem juntos).
  Nunca inferior (um flash barato não escreve a perícia).

REGRA DO GEMINI (24/07/2026): Gemini NUNCA é primário — só fallback. Tem qualidade e custo ótimos,
  mas TRAVA demais (429/cota). Confiabilidade acima de custo — foi o Gemini que derrubou o Radar.

ARMADILHAS 07/2026 (das docs oficiais — não ignorar):
  • Sonnet 5 / Opus 5: thinking ligado por padrão → NÃO passar temperature/top_p (é rejeitado). budget_tokens removido.
  • IDs sem data desde a 4.6: `claude-sonnet-5` já é o snapshot.
  • GPT-4o APOSENTADO (02/2026). Gemini 2.0 Flash/Lite DESLIGADOS (06/2026 → 404). Não usar.
  • Cache hit = 10% do input · Batch = -50% (acumulam). São o maior ganho — mais que o modelo.

Cada programa importa daqui. Trocar de modelo = UMA linha (ou uma variável no .env). Nunca mais 30 lugares.
"""
import os


def _env(chave, padrao):
    v = os.getenv(chave)
    return v if v else padrao


# ─────────── CADEIAS POR TAREFA (primário → fallback cross-provider, mesmo tier) ───────────

# Escrita com raciocínio pesado: Pesquisador (capítulo), pontos críticos
PROFUNDO = [_env("CD_M_PROFUNDO", "claude-opus-5"), "gpt-5.6-sol", "gemini-3.1-pro-preview"]

# Escrita em geral: perícia/redator, análise de artigo, ACRI, roteiro de áudio (a MAIORIA)
ESCRITA = [_env("CD_M_ESCRITA", "claude-sonnet-5"), "gpt-5.6-terra", "gemini-3.1-pro-preview"]

# Extração com rigor (homem das cavernas — decide tipo, delatores): escrita, não filtragem
EXTRACAO = [_env("CD_M_EXTRACAO", "claude-sonnet-5"), "gpt-5.6-terra", "gemini-3.1-pro-preview"]

# PERÍCIA (a análise crítica que vai ao site) — cadeia PRÓPRIA, decidida por MEDIÇÃO em 01/Ago/2026.
# Comparativo real em 5 documentos (original, diretriz, revisão, meta, diretriz SBC de 130 páginas),
# 3–4 modelos cada, com os prompts por tipo. O gpt-5.6-terra ganhou nos três eixos que importam:
#   • TABELAS: 108 na diretriz de 130 pág (Sonnet: 43) · 176 na meta (Sonnet: 51)
#   • LACUNAS ADMITIDAS ("não reportado" em vez de inventar): 25 (Sonnet: 6)
#   • TEMPO e CUSTO: 70 s / US$ 0,42 contra 253 s / US$ 0,72 do Sonnet no mesmo documento
# O Sonnet 5 gastou 3× em TODOS os testes ~15.000 tokens de raciocínio para entregar ~7.500 de texto
# (cobrados como saída). Fica como 1º fallback: ele é o melhor a ANCORAR afirmação em número.
# Por que cadeia separada e não trocar a ESCRITA: ACRI e roteiro de áudio NÃO foram testados assim —
# mexer neles sem medir seria repetir o erro que passamos o dia consertando.
PERICIA = [_env("CD_M_PERICIA", "gpt-5.6-terra"), "claude-sonnet-5", "gemini-3.1-pro-preview"]

# Rápido/volume: triagem do Radar, classificação, filtragem (pouco raciocínio)
# Haiku primário (Anthropic, confiável, na conta que o Dr. Eduardo controla). Gemini só como último fallback.
RAPIDO = [_env("CD_M_RAPIDO", "claude-haiku-4-5-20251001"), "gpt-5.6-luna", "gemini-3.6-flash"]

# Guidelines: contexto longo (200+ páginas). GPT-5.6 Sol tem ~1,05M de janela → aguenta como primário.
# Gemini 3.1 Pro (1M) fica de fallback (Claude não cabe, ~200k).
GUIDELINE_LONGO = [_env("CD_M_GUIDELINE", "gpt-5.6-sol"), "gemini-3.1-pro-preview"]


# ─────────── temperature: modelos de raciocínio (thinking on) REJEITAM sampling custom ───────────
# Gemini aceita temperature normalmente; a restrição é dos Claude 5 e dos GPT-5 (reasoning).
_SEM_TEMPERATURE = ("claude-opus-5", "claude-sonnet-5", "claude-opus-4-7", "claude-opus-4-8", "gpt-5")


def aceita_temperature(model_id):
    """False p/ modelos de raciocínio (thinking on) que rejeitam temperature/top_p."""
    return not any(str(model_id).startswith(p) for p in _SEM_TEMPERATURE)


def temp_kwargs(model_id, temperatura):
    """Devolve {'temperature': t} só se o modelo aceitar; senão {} (não quebra Sonnet 5/Opus 5)."""
    return {"temperature": temperatura} if aceita_temperature(model_id) else {}


def provedor(model_id):
    m = str(model_id)
    if m.startswith("claude"):
        return "anthropic"
    if m.startswith("gpt"):
        return "openai"
    if m.startswith("gemini"):
        return "google"
    return "desconhecido"
