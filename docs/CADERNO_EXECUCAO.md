# CADERNO DE EXECUÇÃO — CARDIODAILY
## Versão 16.2 | 30/Abril/2026
### Histórico: v13.2 (20/Fev) → v15.0 (05/Abr) → v16.0 (29/Abr) → v16.1 (29/Abr) → v16.2 (30/Abr)

---

## DECISÕES DE PRODUTO (29/Abril/2026)

### Radar — ElevenLabs exclusivamente
- Radar usa ElevenLabs em todos os pontos de entrada — decisão permanente, sem fallback para OpenAI TTS

### Distribuição de artigos — 1 artigo/dia ✅ Implementado
- **Regra:** 1 artigo por dia (era 2), nota ≥ 8 (era 7)
- **Prioridade de tipo:** Original > Meta-análise > Revisão (dentro do tipo: nota DESC → data DESC)
- **Implementado em `distribuidor.py`:** `ARTIGOS_POR_DIA=1`, `NOTA_MINIMA=8`, `selecionar_artigos_por_tema()` reescrita

### Lista semanal por revista ✅ Implementado
- **Quando:** toda segunda-feira às 07:30 BRT (cron + GitHub Actions `lista-semanal.yml`)
- **Conteúdo:** artigos nota ≥ 8 indexados nos últimos 7 dias, agrupados por revista
- **Formato:** mensagem WhatsApp (plain text) — top-tier primeiro (NEJM, JAMA, EHJ, JACC, Circulation), depois alfabético
- **Campos:** tipo (original/meta/revisão), NAC, título truncado a 90 chars
- **Comando:** `python3 distribuidor.py semana` (dry-run: `--dry-run`)

### Roadmap médio prazo
- **Site próprio** — plataforma web do CardioDaily
- **Gestor de redes sociais** — automação de posts Instagram/Twitter

---

## MUDANÇAS v16.0 (29/Abril/2026)

### Radar: OpenAI TTS → ElevenLabs TTS (PT-BR)
- **Motivo:** bug de alternância de idioma no áudio do Radar; voz antiga (OpenAI) substituída
- **Provider:** ElevenLabs `eleven_multilingual_v2` com `language_code: pt-BR` (travado em PT-BR)
- **Voz:** `ELEVENLABS_VOICE_ID=iKcBfmBSyO9Mrvg8MRRd` (configurado no `.env`)
- **Arquivos alterados:**
  - `src/radar/radar_pubmed.py` — `configure()` recebe `elevenlabs_key`; `gerar_audio()` chama ElevenLabs (sem chunking manual)
  - `scripts/run_radar_diario.py` — `configure(elevenlabs_key=os.getenv("ELEVENLABS_API_KEY"))`
  - `src/radar/journal_issue_fetcher.py` — `generate_audio()` usa `ElevenLabsAudioGenerator`
  - `src/web_biblioteca.py` — `_configure_radar()` lê `ELEVENLABS_API_KEY`
- **Lição aprendida:** sempre fazer grep completo em `src/`, `scripts/` e raiz antes de alterar qualquer chamada de API — ontem a mudança foi incompleta porque `run_radar_diario.py` ficou com `openai_key`

### Organização da pasta raiz
- 51 arquivos temporários movidos para `archive/logs_operacionais/`

### Caderno de execução — fonte única
- `docs/CADERNO_EXECUCAO.md` é o **único registro canônico** a partir de agora
- `/Users/edcastro77/files/CADERNO_EXECUCAO_v15.md` era cópia externa — descontinuado
- **Regra:** Claude atualiza este arquivo ao final de cada sessão com mudanças relevantes

---

## MUDANÇAS v15.0 (05/Abril/2026)

### Arquitetura: n8n cancelado → Python + cron
- n8n ($350/mês) substituído por `distribuidor.py` + cron em VPS ($5-10/mês)
- Economia anual: ~$4.000
- Motivos: n8n corrompia configurações, arquitetura de "agenda semanal" contradizia o princípio "cardiologia de hoje", custo desproporcional

### Bug crítico distribuidor (19/Abr/2026)
- Distribuidor usava `data_publicacao` (data da revista) para filtrar artigos novos
- Corrigido para `created_at` (data de indexação pelo Dr. Eduardo)
- Impacto: artigo de 2023 analisado hoje = artigo novo para o distribuidor

---

## ARQUITETURA ATUAL

```
┌─────────────────────────────────────┐
│  MAC LOCAL (Notebook Dr. Eduardo)   │
│                                     │
│  Classificador → Analisador →       │
│  Arquivador → Administrador         │
│  Radar (13 temas, rotação 13 dias)  │
│                                     │
│  Tudo sobe para Supabase            │
│  imediatamente após processamento   │
└──────────────┬──────────────────────┘
               │ Upload assets + dados
               ▼
┌─────────────────────────────────────┐
│  SUPABASE (banco + storage)         │
│                                     │
│  Tabelas: artigos, radar,           │
│  whatsapp_users, entregas           │
│  Storage: visual_abstracts,         │
│  podcasts, radar_podcasts,          │
│  resumos_pdf                        │
└──────────────┬──────────────────────┘
               │ Query + URLs
               ▼
┌─────────────────────────────────────┐
│  VPS ($5/mês) ou MAC LOCAL          │
│                                     │
│  distribuidor.py (cron)             │
│  07:00 → 2 artigos personalizados   │
│  08:00 → 1 podcast do Radar         │
│                                     │
│  telegram_bot.py (serviço)          │
│  Chatbot: /top /artigos /podcast    │
│  /status /semana                    │
└──────────────┬──────────────────────┘
               │ API WhatsApp + Telegram
               ▼
┌─────────────────────────────────────┐
│  ASSINANTES (200+ médicos)          │
│  WhatsApp + Telegram                │
└─────────────────────────────────────┘
```

---

## STACK TÉCNICA

| Componente | Tecnologia |
|---|---|
| Análise revisões/guidelines | Claude Sonnet 4 |
| Análise originais/meta-análises | Gemini 2.5 Pro |
| Classificação visual | Gemini 2.0 Flash |
| Script de podcast (artigos) | GPT-4o |
| Áudio artigos | OpenAI TTS-HD voz onyx |
| **Áudio Radar** | **ElevenLabs `eleven_multilingual_v2` PT-BR** |
| Infográfico visual | Visual Abstract 8 seções (Playwright + Jinja2) |
| Banco de dados | Supabase (3.100+ artigos, 73 categorias EN) |
| WhatsApp | Z-API (instance `3F0C22040662826CFF327E97F8598275`) |
| Radar PubMed | Gemini 2.5 Pro + ElevenLabs |

---

## DISTRIBUIÇÃO DIÁRIA (distribuidor.py)

### 07:00 — Artigos personalizados
1. Consulta temas do assinante (`temas` em `whatsapp_users`)
2. Mapeia temas → `doenca_principal`
3. Busca artigos dos últimos 10 dias, nota ≥ 7 — **filtro por `created_at`**
4. Filtra já enviados (`artigos_enviados`)
5. Pré-seleciona 8 melhores, sorteia 2
6. Envia: visual abstract + texto + áudio
7. Marca como enviado

### 08:00 — Radar
1. Consulta tabela `radar` para hoje
2. Se existe: envia podcast + resumo para todos
3. Se não existe: não envia

### 8 Temas do assinante
| Tema | doenca_principal incluídas |
|---|---|
| coronaria | Coronariopatia Aguda, Crônica, Intervenção Vascular |
| cardiometabolico | Dislipidemias, Cardiometabólica, Manifestações CV |
| miocardiopatias | Miocardiopatias, IC, Cardio-Onco, Cardio-Obstet, Congênitas, Aortopatias |
| prevencao | HAS, Pré-Op, Prevenção CV, Farmacologia, Outros |
| valvulopatias | Valvulopatias |
| arritmia | Arritmias, Marcapasso, Stroke |
| uti | Emergências/UTI |
| imagem | Imagem Cardiovascular |

---

## RADAR PUBMED — 13 TEMAS (rotação diária)

| Dia (% 13) | Tema | Nome PT |
|---|---|---|
| 0 | doenca_coronariana | Coronária/DAC |
| 1 | cardio_metabolica | Cardiometabólica |
| 2 | arritmias | Arritmias |
| 3 | insuficiencia_cardiaca | Insuficiência Cardíaca |
| 4 | valvulopatias | Valvulopatias |
| 5 | miocardiopatias | Miocardiopatias |
| 6 | intervencao_hemodinamica | Intervenção/Hemodinâmica |
| 7 | cardio_oncologia | Cardio-Oncologia |
| 8 | cardiobstetrica | Cardio-Obstétrica |
| 9 | cardio_genomica | Cardio-Genômica |
| 10 | uti_cardiologica | UTI Cardiológica |
| 11 | aorta_congenitas | Aorta/Congênitas |
| 12 | imagem_cardiovascular | Imagem Cardiovascular |

**Pipeline:** `run_radar_diario.py` → PubMed (14 dias, 50 artigos) → triagem Gemini → script Gemini → MP3 ElevenLabs → Supabase Storage → tabela `radar` → WhatsApp

---

## CHATBOT TELEGRAM (telegram_bot.py)

Serviço separado, roda contínuo (systemd ou screen).
- `/top` — Top artigos nota ≥ 8
- `/artigos <termo>` — Busca por tema/título
- `/podcast <doc_id>` — Podcast de artigo específico
- `/semana` — Agenda da semana
- `/status` — Estatísticas do sistema
- `/ajuda` — Lista de comandos

---

## DEPLOY

### Opção A — VPS (produção)
```bash
git clone <repo> CardioDaily_FULL
cd CardioDaily_FULL
python3 -m venv venv && source venv/bin/activate
pip install supabase httpx python-telegram-bot

# Cron (10/11 UTC = 07/08 BRT)
0 10 * * * cd /opt/CardioDaily_FULL && venv/bin/python3 distribuidor.py artigos
0 11 * * * cd /opt/CardioDaily_FULL && venv/bin/python3 distribuidor.py radar
```

### Opção B — Mac local (beta)
```bash
0 7 * * * cd /Users/edcastro77/CardioDaily_FULL && venv/bin/python3 distribuidor.py artigos
0 8 * * * cd /Users/edcastro77/CardioDaily_FULL && venv/bin/python3 distribuidor.py radar
```

---

## CHECKLIST BETA (atualizado 29/Abril/2026)

### Concluído
- [x] Diagnóstico completo do Supabase (3.100+ artigos)
- [x] Reclassificação completa — artigos corrigidos, categoria `Não Cardiológico` criada
- [x] n8n cancelado, `distribuidor.py` criado e funcional
- [x] Tabela `radar` criada no Supabase
- [x] Bug `created_at` corrigido no distribuidor (19/Abr)
- [x] Radar: OpenAI TTS → ElevenLabs PT-BR (29/Abr)
- [x] Distribuidor: 1 artigo/dia, nota ≥ 8, prioridade Original > Meta > Revisão (29/Abr)
- [x] Cron corrigido: `/opt/homebrew/bin/python3` → `venv/bin/python3` (30/Abr — era a causa raiz: distribuidor.py nunca executava)
- [x] `daily_sender.py` corrigido: nota ≥ 8, 1 artigo, filtro `created_at`, prioridade de tipo (30/Abr)
- [x] GitHub Actions identificado como distribuidor real (30/Abr — roda `ubuntu-latest` independente do Mac)
- [x] Bug crítico de áudio: `UNIFIED_AUDIO_AVAILABLE` ausente em `audio_generator.py` — pipeline nunca gerou áudio desde fevereiro (975 artigos sem áudio). Corrigido + provider trocado para ElevenLabs (30/Abr)

### Pendente imediato
- [ ] Backfill de áudio: ~975 artigos com VA mas sem áudio — Dr. Eduardo vai gravar os scripts manualmente (voz própria, sem custo de API). Precisamos de interface para listar e acessar os scripts facilmente.
- [ ] Lista semanal de artigos por revista — formato e frequência a definir
- [x] Radar: gerado e enviado (30/Abr) — tema Insuficiência Cardíaca
- [x] Bug ElevenLabs `language_code` removido (eleven_multilingual_v2 não suporta)
- [x] Bug curadoria do Radar: Gemini incluía artigos de outras doenças. Prompt agora injeta o tema e proíbe artigos tangenciais explicitamente (30/Abr)
- [x] Caderno unificado em `docs/CADERNO_EXECUCAO.md`
- [x] Pasta raiz limpa (51 arquivos → `archive/logs_operacionais/`)
- [x] Lista semanal por revista implementada em `distribuidor.py lista_semanal()` + cron segunda 07:30 BRT + GitHub Actions `lista-semanal.yml` (30/Abr)

### Pendente — Prioridade ALTA
- [ ] Preencher credenciais no distribuidor.py (SUPABASE_SERVICE_KEY, ZAPI_TOKEN, TELEGRAM_BOT_TOKEN)
- [ ] Testar: `python3 distribuidor.py teste`
- [ ] Conectar Radar ao Supabase (upload automático → bucket `radar_podcasts`)
- [ ] Gerar PDFs no Administrador e subir ao Storage

### Pendente — Prioridade MÉDIA
- [ ] Migrar telegram_bot.py (chatbot)
- [ ] Deploy VPS para produção
- [ ] Gerar áudios em lote (meta-análises + revisões nota ≥ 8)

### Pendente — Limpeza técnica
- [ ] Dropar coluna `nota_geral` do Supabase
- [ ] Dropar coluna `resumo_json` do Supabase
- [ ] Ativar RLS no Supabase
- [ ] Limpar usuário duplicado em `whatsapp_users`
- [ ] Cancelar plano n8n

---

## LEIS DE OPERAÇÃO (Claude)

1. **Busca sistemática antes de qualquer mudança de API/provider:** grep em `src/`, `scripts/` e raiz — listar TODOS os pontos afetados antes de tocar código
2. **Atualizar `docs/CADERNO_EXECUCAO.md` ao final de cada sessão** com mudanças relevantes
3. **Nunca criar arquivos temporários na pasta raiz** — usar `archive/logs_operacionais/` ou `outputs/`
4. **Arquivo canônico único:** `docs/CADERNO_EXECUCAO.md` — não criar versões paralelas

---

## PRINCÍPIOS INVIOLÁVEIS DO PROJETO

1. Rigor metodológico acima de tudo
2. Crítica ao estudo, nunca ao autor
3. Incerteza declarada é virtude
4. Bola na rede — toda análise termina com conduta prática
5. Nunca abandonar uma funcionalidade — sempre existe uma alternativa
6. Independência editorial absoluta
7. Controle total — sem dependência de plataformas visuais de terceiros

---

*Versão 16.2 — 30/Abril/2026 — atualizado por Claude ao final da sessão*
