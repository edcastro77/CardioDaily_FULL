# CardioDaily — Contexto Complementar (.claude/CLAUDE.md)
> Reescrito em 01/Set/2026. **A FONTE DE VERDADE do projeto é o `CLAUDE.md` da RAIZ**
> (as 12 leis, pipeline, stack, modelos, prompts, portas). Este arquivo guarda APENAS
> o que não está lá: identificadores de infraestrutura e padrões de código.
> Se algo aqui contradisser o CLAUDE.md da raiz, **vale o da raiz** — e este arquivo
> deve ser corrigido na hora (LEI 9: duas fontes de verdade é a definição de buraco).
>
> A versão anterior deste arquivo dizia que a análise usava `ARTICLE_ANALYSIS_PROMPT_v2`
> (aposentado — hoje é o motor determinístico `src/notas_prototipo.py` + `analise_prompt.md`),
> que o TTS de artigos era `onyx` (hoje é `gpt-4o-mini-tts` voz `cedar`) e que a raiz era
> `/Users/edcastro77/` (é `/Users/eduardocastro/projetos/`). Tudo isso está correto na raiz.

## Estrutura
- Raiz: `/Users/eduardocastro/projetos/CardioDaily_FULL/`
- Caderno de execução: `docs/CADERNO_EXECUCAO.md`
- Mapa do src: `MAPA_DO_SRC.md`

## Infraestrutura (identificadores)
- Supabase projeto: `hzqtogcpwdzhjfroxtfz` — tabela `artigos` (escrita SÓ pelo
  `publicador.py`, LEI 5) · tabela `agenda_envio` (fila de envio; o `administrador.py`
  escreve nela, e isso é legítimo — não é a tabela de artigos)
- Telegram Bot ID: 8349019693 | Canal: @CardioDailyBot | Chat ID: 237863636
- Z-API Instance: 3F0C22040662826CFF327E97F8598275
- Buckets Storage: `visual_abstracts`, `podcasts`, `resumos_pdf`, `radar`

## Padrões de código
- Python com type hints
- Verificar `docs/CADERNO_EXECUCAO.md` antes de modificar fluxos críticos
- Mudanças no schema Supabase exigem migração explícita
- Modelos de LLM SEMPRE via `src/modelos.py` — nunca hardcoded
- Conteúdo em português brasileiro; marca sempre "CardioDaily · Os Fatos sem Fírulas"
