# CardioDaily — Contexto do Projeto

Plataforma de curadoria científica em cardiologia para médicos.
Desenvolvida por Dr. Eduardo Castro. Em fase de **beta fechado** (abril/maio 2026).

---

## Arquitetura geral

```
WhatsApp (Z-API) ←→ Supabase Edge Function (agente_whatsapp)
                          ↓
                   jobs_pendentes (Supabase)
                          ↓
                   processar_jobs.py  ← roda via Windows Task Scheduler local
                          ↓
              ingerir_artigos.py (GPT-4o + TTS + imagem + PDF)
                          ↓
              Supabase Storage (buckets: visual_abstracts, podcasts, resumos_pdf)
                          ↓
              Entrega WhatsApp + Telegram ao usuário
```

**Distribuição diária (GitHub Actions — cloud, independente do PC):**
- 07:00 BRT → `distribuidor.py artigos` (2 artigos por assinante)
- 07:30 BRT → `scripts/run_radar_diario.py` (gera podcast do radar PubMed)
- 08:00 BRT → `distribuidor.py radar` (envia o podcast gerado)

---

## Stack

| Componente | Tecnologia |
|---|---|
| Banco de dados | Supabase (PostgreSQL) |
| Armazenamento | Supabase Storage |
| Webhook / Agente IA | Supabase Edge Function `agente_whatsapp` |
| WhatsApp | Z-API |
| Telegram | Bot API direto |
| Análise de artigos | GPT-4o (texto + visão) |
| Podcast TTS | OpenAI TTS (voz onyx, modelo tts-1-hd) |
| Radar científico | PubMed (biopython Entrez) + Gemini (triagem) + OpenAI TTS |
| Cron em nuvem | GitHub Actions |
| Python | 3.11+ (venv local em Windows, ubuntu-latest no CI) |

---

## Arquivos principais

| Arquivo | Função |
|---|---|
| `distribuidor.py` | Distribui artigos (07h) e radar (08h) via WhatsApp + Telegram |
| `scripts/run_radar_diario.py` | Gera podcast diário do radar PubMed |
| `scripts/processar_jobs.py` | Processa PDFs enviados pelo usuário via WhatsApp |
| `scripts/ingerir_artigos.py` | Pipeline completo: PDF → GPT-4o → assets → Supabase |
| `scripts/gerar_imagens_lote.py` | Gera visual abstracts (HTML → PNG via Playwright) |
| `scripts/gerar_audios_lote.py` | Gera áudios em lote para artigos sem MP3 |
| `scripts/gerar_pdfs_lote.py` | Gera PDFs resumo em lote |
| `src/radar/radar_pubmed.py` | Backend do radar: busca PubMed, triagem Gemini, TTS |
| `.github/workflows/` | 3 workflows de cron em nuvem |

---

## Supabase — tabelas principais

| Tabela | Uso |
|---|---|
| `artigos` | 3100+ artigos analisados |
| `whatsapp_users` | Assinantes (phone, temas, artigos_enviados) |
| `radar` | Registros diários do podcast do radar |
| `jobs_pendentes` | Fila de PDFs enviados via WhatsApp para análise |
| `conversas_whatsapp` | Histórico de chat do agente IA |

**Buckets Storage:** `visual_abstracts`, `podcasts`, `resumos_pdf`, `radar_podcasts`, `pdf_uploads`

---

## Credenciais

**Nunca commitadas.** Existem em dois lugares:
1. `.env` na raiz — para rodar localmente no Windows/Mac
2. GitHub Secrets — para os workflows em nuvem

Variáveis necessárias: `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `ZAPI_BASE`, `ZAPI_CLIENT_TOKEN`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `OPENAI_API_KEY`, `GEMINI_API_KEY`, `ENTREZ_EMAIL`

O arquivo `.env.template` tem a estrutura sem os valores.

---

## Mudanças recentes (abril 2026)

### 18/04 — Prompts: conduta clínica prática
- **GPT-4o vision ativado**: primeiras 6 páginas do PDF renderizadas como imagem → captura fluxogramas e gráficos de diretrizes
- **Podcast reescrito (90s)**: estrutura Abertura → Paciente-alvo → Resultado-chave → Como usar → Pérola. Zero contexto histórico, zero metodologia antes do resultado
- **Branching revisão vs original**: diretrizes recebem fluxo diagnóstico-terapêutico; estudos originais recebem resultado com NNT e conduta específica
- **PROMPT_ANALISE reescrito**: exige números absolutos/relativos, NNT, fármaco com dose, pérola com verbo de ação
- **PROMPT_EXTRACAO reescrito**: infográfico orientado a aptidão prática

### 16/04 — GitHub Actions (cron em nuvem)
- Cron movido do Agendador de Tarefas do Windows → GitHub Actions
- `distribuidor.py` refatorado para ler credenciais de variáveis de ambiente
- `requirements.txt` criado
- `.env` adicionado ao `.gitignore`

### 15/04 — Bug crítico: entrega WhatsApp silenciosa
- `processar_jobs.py` não entregava artigos analisados: `ZAPI_BASE` ausente no `.env`
- Corrigido: `ZAPI_BASE` e `ZAPI_CLIENT_TOKEN` adicionados ao `.env`

### 15/04 — Edge Function `agente_whatsapp`
- Já existia e funciona: recebe webhook Z-API, baixa PDF, cria job em `jobs_pendentes`
- Agente IA (Claude) responde perguntas sobre cardiologia via WhatsApp
- Ferramentas: `buscar_artigos`, `atualizar_temas`, `minha_conta`

---

## Pendências ativas

- [ ] **Beta fechado**: finalizar lista de participantes e cadastrá-los em `whatsapp_users`
- [ ] **Análise via WhatsApp**: testar fluxo completo com PDF de revisão/diretriz após correção dos prompts
- [ ] **`processar_jobs.py`**: migrar para GitHub Actions (hoje roda só no Windows local)
- [ ] **Configurar GitHub Secrets** se ainda não feito: necessário para workflows funcionarem

---

## Como rodar localmente (Mac)

```bash
# Instalar dependências
pip install -r requirements.txt

# Configurar credenciais
cp .env.template .env
# editar .env com as chaves

# Testar distribuição (sem enviar)
python distribuidor.py teste

# Rodar radar manualmente
python scripts/run_radar_diario.py --dry-run

# Processar PDFs na fila
python scripts/processar_jobs.py
```

**Playwright** (para gerar imagens/PDFs) precisa de instalação extra:
```bash
pip install playwright
playwright install chromium
```
