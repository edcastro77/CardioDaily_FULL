# CardioDaily — Contexto do Projeto

## Estrutura
- Raiz: /Users/edcastro77/CardioDaily_FULL/
- Caderno de execução: /Users/edcastro77/CardioDaily_FULL/docs/CADERNO_EXECUCAO.md
- Stack: Python + Supabase (hzqtogcpwdzhjfroxtfz) + Telegram + Z-API + WeasyPrint

## Infraestrutura
- Telegram Bot ID: 8349019693 | Canal: @CardioDailyBot | Chat ID: 237863636
- Z-API Instance: 3F0C22040662826CFF327E97F8598275
- Buckets: visual_abstracts, podcasts, resumos_pdf, radar

## Pipeline editorial
- Classifier → AI analysis → JSON/Markdown → PDF → WhatsApp/Telegram
- Análise usa ARTICLE_ANALYSIS_PROMPT_v2 (6 eixos CardioDaily, escala 10 pontos)
- Conteúdo em português brasileiro; marca sempre "CardioDaily"
- TTS: OpenAI TTS-HD onyx (podcasts de artigos) | ElevenLabs (Radar) | Cartesia Luana PT-BR (Briefing)

## Filosofia editorial
- "Dados e fatos, sem firula"
- Ceticismo metodológico, especialmente estudos patrocinados pela indústria
- Sempre declarar incerteza; não inventar dados

## Padrões de código
- Python com type hints
- Sempre verificar CADERNO_EXECUCAO.md antes de modificar fluxos críticos
- Mudanças no schema Supabase exigem migração explícita
