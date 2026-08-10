"""
precos.py — A TABELA DE PREÇOS. UMA SÓ.

═══════════════════════════════════════════════════════════════════════════════════════
POR QUE ESTE ARQUIVO EXISTE — LEI 9, DE NOVO
═══════════════════════════════════════════════════════════════════════════════════════

Em 09/Ago/2026, ao responder "quanto custa de verdade rodar a Chave 2", encontrei DUAS
tabelas de preço no projeto, e elas DISCORDAVAM:

    modelo             prova_extracao.py      prova_classificador.py
    gpt-5.6-terra        1,25 / 10,00            2,00 / 12,00
    gpt-5.6-sol          1,25 / 10,00            5,00 / 25,00
    claude-sonnet-5      3,00 / 15,00            2,00 / 10,00

A mesma pergunta ("quanto custou esta chamada?") tinha duas respostas, e a diferença entre
elas era de 22 % na conta do mês. É exatamente o defeito que a LEI 9 nomeia: uma regra que
mora em vários blocos, consertada em um só, rodando errado em silêncio no outro.

Agora mora AQUI, e os dois programas importam daqui.

═══════════════════════════════════════════════════════════════════════════════════════
⚠️  O QUE ESTE ARQUIVO **NÃO** É — LEIA ANTES DE CONFIAR NO NÚMERO
═══════════════════════════════════════════════════════════════════════════════════════

**Preço não é fato medido; token é.** O `uso.jsonl` grava TOKENS, que são verdade absoluta
vinda do provedor. O dinheiro é DERIVADO — sai desta tabela, que é a parte frágil.

Consequência prática, e ela é boa: **se esta tabela estiver errada, nada se perde.** É só
corrigir os números aqui e rodar a Chave 19 de novo — os meses inteiros se recalculam do
histórico, sem gastar um centavo e sem reanalisar um artigo.

⚠️  CONFERIDO CONTRA A FATURA? **NÃO.** Estes valores vieram do `prova_extracao.py`, que os
declara como *"aproximado e declarado como tal"*. Ninguém os comparou com uma fatura real da
OpenAI ou da Anthropic. Enquanto `CONFERIDO_EM` for None, todo número de dinheiro que sair
daqui é ESTIMATIVA — e quem imprime tem obrigação de dizer isso na tela.
"""

# Data em que a tabela foi conferida contra uma FATURA de verdade. None = nunca foi.
CONFERIDO_EM = None

# US$ por 1.000.000 de tokens — (entrada, saída)
PRECO = {
    "claude-opus-5":              (15.00, 75.00),
    "claude-sonnet-5":            (3.00, 15.00),
    "claude-haiku-4-5-20251001":  (1.00, 5.00),
    "gpt-5.6-sol":                (1.25, 10.00),
    "gpt-5.6-terra":              (1.25, 10.00),
    "gpt-5.6-luna":               (0.20, 1.20),
    "gemini-3.1-pro-preview":     (1.25, 10.00),
    "gemini-3.6-flash":           (0.10, 0.40),
    "grok-4.5":                   (3.00, 15.00),   # estimado — conferir na fatura da xAI
}

# Multiplicadores de cache. Valem para Anthropic e OpenAI; se um provedor mudar, muda AQUI.
CACHE_LEITURA = 0.10    # ler do cache custa 10 % do preço de entrada
CACHE_ESCRITA = 1.25    # gravar no cache custa 125 % (só a Anthropic cobra isto)
BATCH = 0.50            # Batch API: metade do preço. Acumula com o cache.


def custo(modelo, entrada=0, saida=0, cache_leitura=0, cache_escrita=0, batch=False):
    """US$ de UMA chamada. Devolve 0.0 se o modelo não estiver na tabela — nunca levanta
    exceção, porque isto é chamado de dentro de relatório e de log, e relatório que quebra
    é pior que relatório aproximado.

    `entrada` é o TOTAL de tokens de entrada reportado pelo provedor — os tokens de cache
    JÁ ESTÃO dentro dele. Por isso a conta desconta antes de recobrar ao preço certo; somar
    os três seria cobrar o mesmo token duas vezes.
    """
    p = PRECO.get(str(modelo))
    if not p:
        return 0.0
    ent = max((entrada or 0) - (cache_leitura or 0) - (cache_escrita or 0), 0)
    v = (ent * p[0]
         + (cache_leitura or 0) * p[0] * CACHE_LEITURA
         + (cache_escrita or 0) * p[0] * CACHE_ESCRITA
         + (saida or 0) * p[1]) / 1_000_000
    return v * BATCH if batch else v


def custo_da_linha(linha, batch=False):
    """Mesma conta, direto de uma linha do `outputs/uso.jsonl`."""
    return custo(linha.get("modelo"),
                 entrada=linha.get("input") or 0,
                 saida=linha.get("output") or 0,
                 cache_leitura=linha.get("cache_read") or 0,
                 cache_escrita=linha.get("cache_write") or 0,
                 batch=batch)


def aviso():
    """A frase que TODO relatório de custo tem de imprimir enquanto a tabela não for conferida."""
    if CONFERIDO_EM:
        return f"preços conferidos contra a fatura em {CONFERIDO_EM}"
    return ("⚠️  ESTIMATIVA — a tabela de preços (src/precos.py) nunca foi conferida contra uma "
            "fatura real. Os TOKENS são medidos; o dinheiro é derivado deles.")
