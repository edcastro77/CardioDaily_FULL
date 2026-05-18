# CADERNO DE EXECUÇÃO — CARDIODAILY
## Versão 20.0 | 18/Maio/2026
### Histórico: v13.2 (20/Fev) → v15.0 (05/Abr) → v16.0 (29/Abr) → v17.0 (02/Mai) → v18.0 (02/Mai) → v19.0 (15/Mai) → v20.0 (18/Mai)

---

## MUDANÇAS v20.0 (18/Maio/2026) — Supabase como Cérebro Acionável + Backfill Campos Clínicos

### Conceito central — por que estamos reanalisando os artigos

O Supabase não é apenas um índice de artigos — é o **cérebro mobilizável do CardioDaily**. Cada campo estruturado no banco (`aplicabilidade_pratica`, `impacto_conduta`, `bullets_praticos`, etc.) é uma unidade de conhecimento clínico que o assistente WhatsApp pode consultar e entregar ao médico em tempo real.

A reanálise não é manutenção técnica. É construção do ativo principal do produto.

> "O resumo_markdown responde 'o que foi publicado'. Os campos JSON respondem 'o que eu faço com isso agora'."

### 1. Novos campos clínicos no Supabase — IMPLEMENTADO ✅

8 colunas adicionadas à tabela `artigos`:

| Campo | Tipo | Origem | Conteúdo |
|---|---|---|---|
| `contexto_tema` | TEXT | `analysis.json → analysis.contexto_tema` | Contexto clínico do tema |
| `aplicabilidade_pratica` | TEXT | `analysis.json → nucleo_comum.aplicabilidade_pratica` | Aplicabilidade direta na prática |
| `impacto_conduta` | TEXT | `analysis.json → nucleo_comum.impacto_conduta` | Como muda a conduta |
| `tamanho_beneficio` | TEXT | `analysis.json → nucleo_comum.tamanho_beneficio` | Magnitude do efeito em linguagem humana |
| `conclusao_geral` | TEXT | `analysis.json → nucleo_comum.conclusao_geral` | Conclusão do estudo |
| `bullets_praticos` | JSONB | `analysis.json → reflexao_final.bullets_praticos` | Lista de bullets acionáveis |
| `por_que_importa` | TEXT | `analysis.json → analysis.por_que_importa` | Para revisões/guidelines: por que este estudo importa |
| `principais_recomendacoes` | TEXT | `analysis.json → analysis.principais_recomendacoes` | Para revisões/guidelines: recomendações principais |

**SQL rodado no Supabase:**
```sql
ALTER TABLE artigos
  ADD COLUMN IF NOT EXISTS contexto_tema TEXT,
  ADD COLUMN IF NOT EXISTS aplicabilidade_pratica TEXT,
  ADD COLUMN IF NOT EXISTS impacto_conduta TEXT,
  ADD COLUMN IF NOT EXISTS tamanho_beneficio TEXT,
  ADD COLUMN IF NOT EXISTS conclusao_geral TEXT,
  ADD COLUMN IF NOT EXISTS bullets_praticos JSONB,
  ADD COLUMN IF NOT EXISTS por_que_importa TEXT,
  ADD COLUMN IF NOT EXISTS principais_recomendacoes TEXT;
```

### 2. Backfill — 408 artigos populados, zero tokens ✅

**Script:** `scripts/backfill_campos_clinicos.py`

Lê `analysis.json` local de cada artigo, extrai os 8 campos e faz PATCH no Supabase. Zero tokens — só leitura de arquivo local.

```bash
python3 scripts/backfill_campos_clinicos.py --dry-run          # preview
python3 scripts/backfill_campos_clinicos.py                    # todos
python3 scripts/backfill_campos_clinicos.py --nota-min 8       # só nota≥8
```

**Resultado da primeira execução (18/Mai/2026):**
- 3191 pastas com `analysis.json` analisadas
- **408 artigos atualizados** (reanalisados com novo schema — notas 8, 9, 10 + parte 2026)
- 2783 artigos sem campos (schema antigo — serão preenchidos conforme reanálise da nota-7)
- Tempo: 21 segundos, 0 erros

### 3. indexar_corpus_completo.py — inclui campos clínicos no upsert ✅

`importar_supabase()` agora envia os 8 campos clínicos no payload. Toda nova indexação (ou re-indexação) popula automaticamente os campos a partir do `analysis.json`.

```python
# Campos clínicos ricos (knowledge base acionável)
for campo in ["contexto_tema", "aplicabilidade_pratica", "impacto_conduta",
              "tamanho_beneficio", "conclusao_geral",
              "por_que_importa", "principais_recomendacoes"]:
    if metadata.get(campo):
        data[campo] = metadata[campo]
if metadata.get("bullets_praticos"):
    data["bullets_praticos"] = metadata["bullets_praticos"]  # JSONB
```

### 4. sync_resumo_markdown.py — bug de tabelas corrigido ✅

`_limpar()` tinha linha `re.sub(r'\|.*\|', '', texto)` que destruía todo conteúdo do TAKE-HOME MESSAGE (formatado como tabela Markdown). Removida.

**Impacto:** o campo `resumo_markdown` agora preserva tabelas — conteúdo do take-home chega íntegro ao banco.

### 5. Plano de reanálise — nota-7 (568 artigos)

| Nota | Total | Status |
|---|---|---|
| 10 | 6 | ✅ Concluído |
| 9 | 110 | ✅ Concluído |
| 8 | 182 | ✅ Concluído |
| 7 | 568 | ⏳ 100/fim de semana (~6 fins de semana) |
| 6 | 253 | 🔴 Stubs — precisam reanálise real |
| 5 | 192 | 🔴 Stubs — precisam reanálise real |

**Protocolo por sessão:**
1. Claude prepara bloco de 100 PDFs em `tmp_nota7/`
2. Dr. Eduardo roda no Terminal: `caffeinate -dims python3 src/article_analyzer.py --local-dir tmp_nota7`
3. Ao terminar: `python3 scripts/backfill_campos_clinicos.py --nota-min 7`
4. Claude faz sync e prepara próximo bloco

**Regra:** nunca rodar o `article_analyzer.py` em background pelo Claude Code — trava. Sempre no Terminal interativo do Dr. Eduardo.

### 6. RLS no Supabase — status e plano

O Supabase alerta "RLS Disabled in Public" para todas as tabelas — é um aviso de segurança, não erro operacional. Scripts Python usam `SUPABASE_SERVICE_KEY` que bypass RLS por design.

**Plano antes do lançamento (tabelas prioritárias):**
```sql
-- Tabelas sensíveis: habilitar RLS + política service_role
ALTER TABLE public.whatsapp_users ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.conversas_whatsapp ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.whatsapp_sends ENABLE ROW LEVEL SECURITY;

-- Política: scripts (service_role) têm acesso total
CREATE POLICY "service_role_full_access" ON public.whatsapp_users
  USING (auth.role() = 'service_role')
  WITH CHECK (auth.role() = 'service_role');
-- (repetir para cada tabela)

-- Tabelas de conteúdo público (artigos, taxonomia): leitura livre, escrita restrita
ALTER TABLE public.artigos ENABLE ROW LEVEL SECURITY;
CREATE POLICY "read_public" ON public.artigos FOR SELECT USING (true);
CREATE POLICY "write_service_only" ON public.artigos FOR ALL
  USING (auth.role() = 'service_role');
```

---

## MUDANÇAS v19.0 (13–15/Maio/2026) — Briefing Cri-Cri + Radar fix + Compactador Diretrizes

### 1. Briefing de Curadoria (Eduardo Cri-Cri) — NOVO ✅

**Propósito:** ao final de cada lote de análise, gerar um áudio ácido/irreverente com todos os artigos do dia — para o Dr. Eduardo usar no sábado/domingo de curadoria para selecionar o conteúdo da semana.

**Arquivo principal:** `src/briefing_semanal.py`

**Pipeline:**
1. Busca artigos no Supabase (`created_at >= N horas atrás`), ordenados por nota DESC
2. Enriquece com `analysis.md` (primeiros 4000 chars) e `analysis.json` (nota estatística, keywords, título real)
3. Gera script via **Claude Sonnet 4.6** (temp=0.7, max_tokens=16000) com persona Eduardo Cri-Cri
4. Salva script em `outputs/briefing/briefing_YYYYMMDD_HHMM.txt`
5. Gera áudio via **Cartesia Luana PT-BR** (voz `700d1ee3-a641-4018-ba6e-899dcadc9e2b`, speed=1.05)
6. Converte WAV → MP3 via ffmpeg (121 MB → ~15 MB)
7. Upload para bucket Supabase `briefing_audio`
8. Envia texto + áudio ao WhatsApp do Dr. Eduardo via Z-API
9. Envia script (documento) + áudio ao Telegram

**Voz:** Cartesia Luana PT-BR — `700d1ee3-a641-4018-ba6e-899dcadc9e2b`
- Isabella foi testada e rejeitada ("rapariga de Portugal")
- Luana — "Public Speaker" — aprovada pelo Dr. Eduardo

**Fix crítico de WAV corrompido:**
- A Cartesia gera WAV RF64 (chunk `data` com `size=0xFFFFFFFF`)
- A concatenação antiga assumia PCM no offset 44 — errado (há chunk `LIST/INFO` variável entre `fmt` e `data`)
- Solução: `_find_data_chunk()` localiza o chunk `data` dinamicamente; `_concat_wavs()` monta header WAV limpo do zero; saída convertida para MP3 via ffmpeg
- Arquivos antigos `.wav` corrompidos podem ser recuperados extraindo PCM bruto a partir do offset 78

**Auto-trigger:** `article_analyzer.py` chama `rodar_briefing()` automaticamente ao final de cada lote com `processados > 0`. Desativar com env var `CARDIODAILY_SKIP_BRIEFING=1`.

**App macOS:** duplo clique em `Briefing Curadoria.app` ou `Briefing Curadoria.command`

**CLI:**
```bash
./cardiodaily briefing              # últimas 24h
./cardiodaily briefing --horas 48   # janela maior
./cardiodaily briefing --dry-run    # só script, sem áudio
```

**Env vars necessárias** (já configuradas no `.env`):
- `CARTESIA_API_KEY` — TTS
- `EDUARDO_PHONE=5527996089248` — WhatsApp do Dr. Eduardo
- `TELEGRAM_CHAT_ID=237863636` — Telegram
- `ZAPI_INSTANCE_ID`, `ZAPI_TOKEN`, `ZAPI_CLIENT_TOKEN` — Z-API
- `SUPABASE_URL`, `SUPABASE_SERVICE_KEY` — upload + busca artigos
- Bucket `briefing_audio` — criar no Supabase Dashboard (Storage → New bucket → público)

---

### 2. Radar — fixes de qualidade + arquitetura ✅

#### Prompt reescrito (radar_pubmed.py)
Problemas identificados no script de produção e corrigidos:
- **PMIDs no áudio** → regra absoluta: nunca citar PMID, DOI ou qualquer identificador
- **HR/IC 95%/p-valor** → traduzir sempre para linguagem humana ("reduziu o risco em um terço")
- **Abertura burocrática** ("A semana trouxe volume expressivo...") → substituída por gancho provocador por artigo
- **"Menções rápidas" e "artigos descartados"** → seções eliminadas — máx 3 artigos com tratamento completo
- **Filtro Brasil** → artigo sobre droga/dispositivo/procedimento indisponível no Brasil: ignorar silenciosamente
- **Duração** → alvo 5 min (600–800 palavras); nunca ultrapassar 7 min
- **Abertura fixa:** `"Olá! Eu sou o assistente virtual do Dr. Eduardo Castro e este é o Radar PubMed do CardioDaily. Fatos à mesa, sem firulas!"`
- **Encerramento fixo:** `"Este foi o seu Radar PubMed CardioDaily de hoje. Fatos à mesa para um bom aprendizado. Até a próxima!"`

#### TTS: Cartesia removido do radar
- Radar usa **ElevenLabs exclusivamente** (decisão de produto — sem fallback)
- `gerar_audio()` em `radar_pubmed.py`: apenas `_gerar_audio_elevenlabs()`, sem Cartesia
- Código do Cartesia mantido na classe mas não chamado pelo radar

#### Arquitetura: dois workflows → um único (radar.yml)
- **Antes:** `radar-gerar.yml` (07:30 BRT) gerava + enviava WhatsApp; `radar-enviar.yml` (08:00 BRT) enviava de novo → **duplicata diária**
- **Depois:** `radar.yml` — um único job em sequência:
  1. `python scripts/run_radar_diario.py` → gera MP3 + registra Supabase (zero WhatsApp)
  2. `python distribuidor.py radar` → único responsável pelo envio WhatsApp + Telegram
- `run_radar_diario.py`: função `_enviar_whatsapp` removida; `import time` removido
- **Guard anti-duplo-disparo** mantido: se registro `(tema, data)` já existe no Supabase, aborta imediatamente

---

### 3. Compactador de Diretrizes SBC-PI — NOVO ✅

**Propósito:** compactar diretrizes/guidelines/reviews em peças no formato CardioDaily SBC-PI para publicação.

**Módulo:** `src/compactador_diretrizes/`
- `compactador_diretriz.py` — lógica principal (Claude Sonnet 4.6, streaming, max_tokens=32000)
- `web_compactador.py` — interface Flask na porta 5002
- `prompts/system_compactador.md` — prompt do sistema
- `prompts/user_compactador.md` — template do usuário
- `schemas/schema_diretriz_cardiodaily.json` — schema JSON de validação
- `fewshots/fewshot_trc_jama2026.json` — exemplo few-shot

**CLI:** `./cardiodaily diretriz --input arquivo.pdf --autores "..." --titulo "..." --revista EHJ --ano 2024`
**Web:** `./cardiodaily diretriz-web` → `http://localhost:5002`

**Fix crítico de template:** `str.replace()` em vez de `str.format()` — o template contém `{}` literais do schema JSON que quebram o `format()`

**Tabela Supabase:** `diretrizes_compactas` — criar com SQL em `scripts/supabase/`

---

## MUDANÇAS v18.0 (02/Maio/2026) — Correção Supabase: PDFs + Áudios

### Diagnóstico de integridade (auditoria executada)
- **Total:** 3.275 artigos no Supabase
- **Sem `caminho_pdf`:** 2.661 (81%) — PDF gerado localmente mas nunca subido ao Storage
- **Sem `caminho_audio`:** 3.181 (97%) — apenas 94 artigos com URL de áudio
- **Nota ≥ 8 em 2026 sem áudio:** 60 artigos (24 originais, 26 revisões, 10 meta-análises)
- **Causa raiz dos PDFs:** `pdf_generator.py` gerava `assets/resumo.pdf` local mas nunca subia ao bucket `resumos_pdf` nem atualizava `caminho_pdf`

### Correções implementadas

#### 1. `article_analyzer.py` — PDF gerado + publicado após cada análise (step 7e)
- Adicionada função `_upload_pdf_supabase(doc_id, pdf_path)` — análoga ao `_upload_podcast_supabase()` já existente
- Adicionado step 7e no pipeline de análise: chama `ArticlePDFGenerator`, faz upload ao bucket `resumos_pdf`, atualiza `caminho_pdf` no Supabase
- **Resultado:** toda nova análise gera PDF + publica automaticamente — nunca mais ficará sem `caminho_pdf`

#### 2. `scripts/gerar_audios_lote.py` — migrado OpenAI TTS → ElevenLabs
- TTS: `eleven_multilingual_v2`, `language_code: pt-BR`, voz `ELEVENLABS_VOICE_ID`, `speed: 1.1`
- **Consistente com a decisão de 29/Abr:** ElevenLabs exclusivamente (sem OpenAI TTS em nenhum ponto)

#### 3. `scripts/auditoria_supabase.py` — script de monitoramento periódico (novo)
- Executa diagnóstico completo: total, sem PDF, sem áudio, nota≥8 sem áudio, corpus local vs. Supabase
- Exibe status com semáforo (✅/🟡/🔴) e comando exato de correção quando detecta problema
- **Uso:** `python3 scripts/auditoria_supabase.py`
- **Recomendação:** rodar semanalmente (pode adicionar ao cron)

### Scripts de backfill (já existiam, prontos para uso)
- `scripts/upload_pdfs_supabase.py` — backfill de PDFs (gera local + sobe ao Storage + atualiza DB)
  ```
  python3 scripts/upload_pdfs_supabase.py --dry-run --since 2020-01-01  # preview
  python3 scripts/upload_pdfs_supabase.py --since 2020-01-01             # executar
  ```
- `scripts/gerar_audios_lote.py` — backfill de áudios (GPT-4o script + ElevenLabs TTS + upload)
  ```
  python3 scripts/gerar_audios_lote.py --dry-run   # preview
  python3 scripts/gerar_audios_lote.py             # executar
  ```

### Prevenção de recorrência
| Ação | Onde | Status |
|------|------|--------|
| Upload PDF automático após análise | `article_analyzer.py` step 7e | ✅ Implementado |
| Upload áudio automático após análise | `article_analyzer.py` `_upload_podcast_supabase()` | ✅ Já existia |
| Script de auditoria periódica | `scripts/auditoria_supabase.py` | ✅ Implementado |
| Backfill PDFs histórico | `scripts/upload_pdfs_supabase.py --since 2020-01-01` | ⏳ Pendente execução |
| Backfill áudio 2026 | `scripts/gerar_audios_lote.py` | ⏳ Pendente execução |

---

## MUDANÇAS v17.0 (02/Maio/2026) — Novo formato de análise + PDF

### Prompt de análise de artigos originais — reescrito
- **Arquivo:** `src/prompts/prompt_artigo_original_v2.md`
- **O que mudou:** Prompt reescrito no estilo do Replete (sistema de referência aprovado pelo Dr. Eduardo). Estrutura idêntica ao `ARTICLE_ANALYSIS_PROMPT` do Replete, com 3 adições do CardioDaily:
  1. Regra de endpoint DURO/SURROGATE com teto de nota explícito
  2. Análise obrigatória de poder estatístico para RCTs (taxa assumida vs. real, classificação BEM POWERED / UNDERPOWERED)
  3. Instrução explícita: todos os campos de análise em **prosa fluida** — sem tabelas, checklists ou marcações Markdown dentro dos valores JSON
- **O que foi removido:** 15 seções com tabelas, emojis, checklists, análise de poder estatístico em tabela separada, seção PÉROLAS em tabela, CHECKLIST FINAL — tudo substituído por instrução narrativa
- **Output:** JSON com campos `titulo`, `revista`, `ano`, `autores_principais`, `nota_aplicabilidade_clinica`, `nota_trabalho_estatistico`, `justificativa_notas`, `contexto_tema`, `nucleo_comum` (10 subcampos), `analise_especifica`, `reflexao_final`, `mapa_mental`
- **Mapa mental:** mantido — campo `mapa_mental` como string Markdown dentro do JSON (não mais bloco ```markdown``` no texto bruto)

### Envio ao Gemini — correção crítica de qualidade
- **Problema:** prompt estava sendo enviado em `system_instruction` separado do artigo (`system_only` mode) com max 16.000 tokens — isso degradava significativamente a qualidade da análise
- **Solução:** para Gemini, prompt + artigo juntos num único `contents` (`system_msg=None`), max_output_tokens fixo em 32.000
- **Para Claude:** mantido `system_message` separado (comportamento correto para Claude)
- **Arquivo:** `src/article_analyzer.py` — bloco de preparação de mensagens (~linha 1170)
- **Regra permanente:** nunca separar prompt do artigo para Gemini. O Replete usa tudo junto — é o modelo de referência.

### article_analyzer.py — suporte ao novo formato JSON
- LLM retorna JSON estruturado → parser extrai e valida
- `analysis.json` agora inclui: `titulo`, `revista`, `ano`, `autores_principais`, `justificativa_notas`, `contexto_tema`, `nucleo_comum`, `analise_especifica`, `reflexao_final` (quando análise nova)
- `analysis.md` gerado a partir dos campos JSON estruturados (não mais dump bruto do LLM)
- Mapa mental extraído do campo `mapa_mental` do JSON (fallback: bloco ```markdown``` legado)
- Título real extraído do campo `titulo` do JSON (fallback: heurística sobre o texto)
- Backward compatible: artigos antigos com analysis.md legado continuam funcionando

### PDF Generator v2 — formato Replete aprovado ✅
- **Arquivo:** `src/pdf_generator.py` (reescrito)
- **Templates:** `src/templates/article_report.html` + `article_report.css` (reescritos)
- **Layout:** capa azul (página 1) + informações + notas + contexto (página 2) + núcleo comum (páginas 3-4) + análise específica + reflexão final (página 5)
- **Fix crítico de páginas em branco:** capa usa `@page cover` com margin zero; `report-body` usa `page-break-before: always`. Nunca usar `<div class="page-break">` manual entre seções do corpo — a paginação é automática pelo WeasyPrint
- **Markdown renderizado:** campos do nucleo_comum convertidos de Markdown → HTML via `python-markdown` antes de injetar no template (`| safe` no Jinja2). Sem `white-space: pre-wrap` — causava páginas em branco quando havia blocos grandes de texto
- **Backward compat:** lê `nucleo_comum` do `analysis.json` (novo); fallback extrai seções do `analysis.md` legado

### Outros fixes da sessão
- `import time` adicionado em `src/article_analyzer.py` (estava faltando)
- Gemini 503/UNAVAILABLE adicionado ao retry em `classificador_artigos.py`, `robust_classifier.py`, `article_analyzer.py`
- `indexar_corpus_completo.py`: bug `md_content` usado antes de ser lido — corrigido
- Mac crontab de distribuição desativado — GitHub Actions é o único dispatcher
- ElevenLabs `speed: 1.1` adicionado em `radar_pubmed.py`
- "firula" → "firulas" corrigido em todos os prompts e scripts

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
- [x] Novo prompt de análise (formato Replete) aprovado pelo Dr. Eduardo (02/Mai)
- [x] PDF Generator v2 — layout clean aprovado (02/Mai)
- [x] Gemini: prompt + artigo juntos, 32k tokens (02/Mai)
- [x] article_analyzer.py: suporte ao novo formato JSON estruturado (02/Mai)
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

### Concluído v20.0 (18/Mai/2026)
- [x] 8 novos campos clínicos criados no Supabase (`contexto_tema`, `aplicabilidade_pratica`, `impacto_conduta`, `tamanho_beneficio`, `conclusao_geral`, `bullets_praticos`, `por_que_importa`, `principais_recomendacoes`)
- [x] `indexar_corpus_completo.py` — upsert inclui campos clínicos ricos
- [x] `scripts/backfill_campos_clinicos.py` criado — 408 artigos populados, 0 erros, 21s
- [x] `sync_resumo_markdown.py` — bug de strip de tabelas Markdown corrigido

### Pendente imediato
- [ ] Reanálise nota-7: próxima sessão de fim de semana — `caffeinate -dims python3 src/article_analyzer.py --local-dir tmp_nota7` (100 artigos)
- [ ] Após cada lote nota-7: `python3 scripts/backfill_campos_clinicos.py --nota-min 7`
- [ ] Backfill de áudio: ~975 artigos com VA mas sem áudio — Dr. Eduardo vai gravar os scripts manualmente
- [ ] Ativar RLS no Supabase antes do lançamento (SQL em v20.0 acima)

### Pendente — Prioridade ALTA
- [ ] Preencher credenciais no distribuidor.py (SUPABASE_SERVICE_KEY, ZAPI_TOKEN, TELEGRAM_BOT_TOKEN)
- [ ] Testar: `python3 distribuidor.py teste`
- [ ] Conectar Radar ao Supabase (upload automático → bucket `radar_podcasts`)
- [ ] Backfill PDFs histórico: `python3 scripts/upload_pdfs_supabase.py --since 2020-01-01`

### Pendente — Prioridade MÉDIA
- [ ] Migrar telegram_bot.py (chatbot)
- [ ] Deploy VPS para produção
- [ ] Gerar áudios em lote (meta-análises + revisões nota ≥ 8)

### Pendente — Limpeza técnica
- [ ] Dropar coluna `nota_geral` do Supabase
- [ ] Dropar coluna `resumo_json` do Supabase
- [ ] Limpar usuário duplicado em `whatsapp_users`
- [ ] Cancelar plano n8n

---

## LEIS DE OPERAÇÃO (Claude)

1. **Busca sistemática antes de qualquer mudança de API/provider:** grep em `src/`, `scripts/` e raiz — listar TODOS os pontos afetados antes de tocar código
2. **Atualizar `docs/CADERNO_EXECUCAO.md` ao final de cada sessão** com mudanças relevantes
3. **Nunca criar arquivos temporários na pasta raiz** — usar `archive/logs_operacionais/` ou `outputs/`
4. **Arquivo canônico único:** `docs/CADERNO_EXECUCAO.md` — não criar versões paralelas
5. **Modelo de referência para prompts:** o Replete (`/Users/edcastro77/Downloads/cardiodaily_export/prompts.py`) é o padrão de qualidade aprovado. Antes de reescrever qualquer prompt, ler o equivalente no Replete e usar como base — nunca partir do zero
6. **Gemini: sempre prompt + artigo juntos.** Para Gemini, `system_msg=None` e todo o conteúdo (prompt + texto do artigo) em `contents`. Separar em `system_instruction` degrada a qualidade. Para Claude: `system_message` separado é correto
7. **PDF sem page-break manual:** nunca adicionar `<div class="page-break">` entre seções do corpo do relatório — causa páginas em branco. Paginação é automática pelo WeasyPrint. A capa usa `@page cover` isolada

---

## COMO FORNECER CONTEXTO AO CLAUDE EM SESSÕES FUTURAS

Para ajustar prompts, PDFs ou qualquer componente do CardioDaily com máxima eficiência, forneça:

### Para ajustar um prompt de análise
```
1. O arquivo de referência: /Users/edcastro77/Downloads/cardiodaily_export/prompts.py
   (ou cole o trecho relevante diretamente)
2. Um PDF ou screenshot do resultado atual (o que está ruim)
3. Um PDF ou screenshot do resultado desejado (o modelo a seguir)
4. O artigo PDF que usou para testar (ou o nome do arquivo em ARTIGOS/)
```

### Para ajustar o layout do PDF
```
1. Screenshot do PDF atual com anotações do que está errado
2. Screenshot ou descrição do layout desejado (ex: "igual ao PDF do Replete")
3. Dizer se o problema é visual (CSS/HTML) ou de conteúdo (o que o LLM gera)
```

### Para adicionar novo componente ao pipeline
```
1. O que entra (input: tipo de arquivo, formato, fonte)
2. O que sai (output: onde salva, formato, nome do arquivo)
3. Quando dispara (manual / cron / gatilho automático)
4. Qual modelo usar (Gemini / Claude / GPT-4o)
5. Exemplo do resultado esperado (PDF, texto, JSON)
```

### Para corrigir um bug
```
1. Comando exato que falhou
2. Mensagem de erro completa (copiar do terminal)
3. O que deveria ter acontecido
4. Quando o bug começou (antes/depois de qual mudança)
```

### Regra geral
> **Mostrar é melhor que descrever.** Um screenshot do problema + um screenshot do esperado vale mais do que um parágrafo de texto. Sempre que possível, arraste o PDF ou imagem direto na conversa.

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

*Versão 20.0 — 18/Maio/2026 — atualizado por Claude ao final da sessão*
