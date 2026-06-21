# Backfills Aposentados

**Data de aposentadoria:** 20/06/2026

## O que são

Scripts de reparo retroativo que escreviam campos críticos diretamente na
tabela `artigos` do Supabase sem passar pelo portão de validação:

| Script | Campo(s) que gravava |
|--------|---------------------|
| `backfill_titulos.py` | `titulo` (disco + CrossRef) |
| `backfill_campos_clinicos.py` | `keywords`, `titulo`, `revista`, `doenca_principal`, campos clínicos |
| `backfill_keywords.py` | `keywords` (disco + Gemini Flash) |
| `extrai_campos_llm.py` | `contexto_tema`, `aplicabilidade_pratica`, `bullets_praticos`, etc. (Gemini) |
| `sync_resumo_markdown.py` | `resumo_markdown` (extração do analysis.md) |

## Por que foram aposentados

Com o portão de validação ativo (`src/article_validator.py`, commit `121025a`),
artigos com campos críticos ausentes ou inválidos são barrados na ingestão e
gravados em `artigos_rejeitados`. Buracos novos não nascem mais na tabela
`artigos`.

Esses scripts nasceram para reparar o passado (quando não havia portão). Com o
portão em produção, rodar esses scripts representaria um risco: escreveriam
campos sem validação, podendo introduzir títulos filename-like, resumos curtos
ou mcid vazio direto no banco.

## Lógica preservada

Toda a lógica interna está intacta. Se for necessário um reparo do passado em
lote (ex: backfill de `resumo_markdown` para artigos antigos), o procedimento
correto é:

1. Copiar o script relevante para fora desta pasta
2. Adaptar para gravar em tabela paralela controlada (ex: `artigos_backfill`),
   não diretamente em `artigos`
3. Revisar e importar via portão de validação após auditoria manual

## Referência histórica

- Commit de aposentadoria: `a61ca20`
- Portão de validação: `src/article_validator.py` (commit `121025a`)
- Tabela de rejeitos: `artigos_rejeitados` (Supabase)
