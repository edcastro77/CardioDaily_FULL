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


# ═══════════ GEMINI FORA DAS CADEIAS — 04/Ago/2026 ═══════════
# Decisão do Dr. Eduardo: *"pode tirar o gemini da jogada — ele é bom mas sempre dá problema,
# limites doidos"*. Medido na mesma noite, na prova da extração: `429 RESOURCE_EXHAUSTED` nos DOIS
# caminhos (estruturado e texto), em dois artigos seguidos. Ele era o último degrau de 5 das 7
# cadeias — ou seja, a "LEI DA EQUIVALÊNCIA" tinha na prática DOIS degraus, e ninguém sabia, porque
# fallback só é exercitado quando o primário cai: no meio de um lote, de madrugada.
#
# CONSEQUÊNCIA ASSUMIDA: sobram duas casas (Anthropic e OpenAI). O 3º degrau passa a ser um modelo
# da MESMA casa de um dos dois primeiros. É menos proteção que três donos independentes — mas é
# proteção que RESPONDE, e um degrau que devolve 429 não é degrau nenhum.

# GROK (xAI) — o 3º degrau, no lugar do gemini (decisão do Dr. Eduardo, 04/Ago).
# ⚠️ O ID DO MODELO É UM PALPITE MEU e precisa ser PROVADO pela Chave 12 antes de valer.
# A xAI já mudou nomes ("grok-4", "grok-4-latest", "grok-4.5", "grok-4-5"...). Se a Chave 12
# devolver 404 neste nome, é só ajustar CD_M_GROK no .env — sem tocar em código.
GROK = _env("CD_M_GROK", "grok-4.5")

# ─────────── CADEIAS POR TAREFA (primário → fallback cross-provider, mesmo tier) ───────────

# Escrita com raciocínio pesado: Pesquisador (capítulo), pontos críticos
PROFUNDO = [_env("CD_M_PROFUNDO", "claude-opus-5"), "gpt-5.6-sol", "claude-sonnet-5"]

# 04/Ago — TERRA PASSA A SER O PRIMÁRIO. Decisão do Dr. Eduardo: *"o sonnet está gastando demais e
# entregando praticamente o mesmo"*. Medido: na perícia (01/Ago) o terra ganhou nos três eixos e
# custou 40% do sonnet; na prova da extração (04/Ago, 2 artigos) os dois chegaram à MESMA nota, e o
# terra custou US$ 0,05 contra US$ 0,13 — 2,5× mais barato pela mesma decisão.
# ⚠️ RESSALVA HONESTA: são 2 artigos, e naquela rodada o terra correu em MODO TEXTO (o function
# calling falhou). Antes de soltar 500 artigos com ele na frente da EXTRAÇÃO, a Chave 12 tem de
# mostrar `function_calling` funcionando — senão os 500 rodam sem schema imposto, que é o modo que
# derrubou 74% da rodada de 25/07.
# Escrita em geral: perícia/redator, análise de artigo, ACRI, roteiro de áudio (a MAIORIA)
ESCRITA = [_env("CD_M_ESCRITA", "gpt-5.6-terra"), "claude-sonnet-5", GROK]

# Extração com rigor (homem das cavernas — decide tipo, delatores): escrita, não filtragem
EXTRACAO = [_env("CD_M_EXTRACAO", "gpt-5.6-terra"), "claude-sonnet-5", GROK]

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
PERICIA = [_env("CD_M_PERICIA", "gpt-5.6-terra"), "claude-sonnet-5", GROK]

# Rápido/volume: triagem do Radar, classificação, filtragem (pouco raciocínio)
# Haiku primário (Anthropic, confiável, na conta que o Dr. Eduardo controla). Gemini só como último fallback.
RAPIDO = [_env("CD_M_RAPIDO", "claude-haiku-4-5-20251001"), "gpt-5.6-luna", GROK]

# CLASSIFICACAO — o tipo do documento (Chave 1). MEDIDO, não escolhido por gosto:
# em 31/07/2026, nos 111 artigos do gabarito do Dr. Eduardo, com o prompt v3:
#     gpt-5.6-luna 110/111 = 99,1 %   ·   sonnet-5 e haiku ficaram atrás E custam mais
# Luna é o MAIS BARATO da casa ($0,20/$1,20 por 1M) e o mais exato nesta tarefa — não é trade-off.
# Por que merece cadeia própria e não usa a RAPIDO: na RAPIDO o Luna é FALLBACK, e quem responderia
# seria o Haiku. A LEI 8 diz que o classificador não pode errar; aqui o primário tem de ser o medido.
CLASSIFICACAO = [_env("CD_M_CLASSIF", "gpt-5.6-luna"), "claude-haiku-4-5-20251001", "claude-sonnet-5"]

# Guidelines: contexto longo (200+ páginas). GPT-5.6 Sol tem ~1,05M de janela → aguenta como primário.
# Gemini 3.1 Pro (1M) fica de fallback (Claude não cabe, ~200k).
# ⚠️ PERDA REAL E DECLARADA: o gemini era a ÚNICA outra janela de ~1M. Sem ele, o 2º degrau é o
# terra (~400k) — cobre a grande maioria das diretrizes, mas uma de 200+ páginas que hoje passa
# inteira no sol NÃO passaria no fallback. Como esta cadeia não é chamada por ninguém ainda
# (verificado 03/Ago), a perda é teórica — mas fica escrita para não virar surpresa.
GUIDELINE_LONGO = [_env("CD_M_GUIDELINE", "gpt-5.6-sol"), "gpt-5.6-terra"]


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
    if m.startswith("grok"):
        return "xai"          # 04/Ago: entrou no lugar do gemini como 3º degrau
    return "desconhecido"
