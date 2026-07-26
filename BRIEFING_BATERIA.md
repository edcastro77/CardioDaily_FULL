# BRIEFING — Bateria de Buraco Zero (CardioDaily)

Você está no repositório `CardioDaily_FULL`. Sua missão é **uma só**: fazer a corrente de análise
passar em **100% dos artigos, sem UMA única falha**. Use o modelo Opus 5.

## Contexto (leia antes de agir)

O dono do projeto é o Dr. Eduardo, cardiologista. A regra absoluta do CardioDaily é **BURACO ZERO**:
qualquer erro, por menor que seja, é inadmissível. Um artigo que não analisou é um buraco.

No run de 25/07/2026, 66 pastas foram criadas e só 17 completaram — **74% de falha**. A causa raiz
era estrutural: a extração pedia JSON ao modelo em texto livre e torcia para vir bem formado.
Isso **já foi corrigido** (saída estruturada via tool use, em `src/llm_client.py::gerar_json` +
`src/analise.py::SCHEMA_FATOS`). Sua função é **provar que está resolvido** — e corrigir o que sobrar.

## O que já foi feito (não refaça)

- `src/llm_client.py` → `gerar_json()` com **tool use** (a API obriga JSON válido) + retry com backoff.
- `src/analise.py` → `SCHEMA_FATOS` cobrindo 100% dos campos que `notas_prototipo` lê; extração usa tool use.
- `src/infographics/visual_abstract_generator.py` → parsing tolerante no JSON do LLM.
- `src/analisador.py` → `_conferir_entregaveis()`: só marca `_OK` se TODOS os entregáveis da porta
  existirem e tiverem tamanho mínimo (testado, 10/10 casos).
- Portas: ≥6 canônico+ACRI+perícia+PDF · ≥7 +Visual Abstract · ≥8 +áudio · <6 só canônico.

## Sua tarefa

1. Ative o venv: `source .venv/bin/activate`
2. Rode a bateria (começe pequeno):
   ```
   python src/bateria.py ARTIGOS/CLASSIFICADOS 5
   ```
3. **Se REPROVADO**: leia `outputs/_BATERIA/bateria_relatorio.json`, identifique a **CAUSA** de cada
   falha, corrija a causa **na raiz** (não o caso isolado) e rode de novo. Repita até APROVADO.
4. Quando passar com 5, suba a régua: **10 → 25 → 50**. Só considere pronto com **50/50 sem falha**.

## Regras inegociáveis

- **Corrija a CLASSE, não o caso.** Se um artigo falhou por vírgula no JSON, a pergunta certa é
  "por que ainda existe parsing frágil aqui?" — não "como reparo esta vírgula".
- **Nunca relate progresso parcial como sucesso.** "40 passaram, 10 falharam" é REPROVADO.
- **Não invente dado clínico.** Se a extração não achou um número, o campo é null — nunca preencha.
- **Não altere as notas nem a LEI 0** (regra de pontuação em `CLAUDE.md`). O motor de rigor é sagrado.
- **Não publique no Supabase** durante a bateria. A bateria é isolada em `outputs/_BATERIA`.
- Se precisar de decisão de produto (mudar regra, porta, formato), **pare e pergunte ao Dr. Eduardo** —
  não decida sozinho.

## Critério de pronto

`python src/bateria.py ARTIGOS/CLASSIFICADOS 50` → **APROVADO · 50/50 sem uma única falha.**

Só então avise o Dr. Eduardo. Antes disso, continue trabalhando sem interrompê-lo.
