# CADERNO DE EXECUÇÃO — CARDIODAILY
## Versão 25.0 | 29/Maio/2026
### Este documento substitui todas as versões anteriores. É o único documento canônico do projeto.

---

## PARTE 1 — O QUE É O CARDIODAILY E POR QUE EXISTE

### O problema real

O cardiologista da linha de frente trabalha 60 horas por semana, opera, prescreve, atende. Ele não lê o NEJM, o Circulation, o EHJ — não porque não quer, mas porque é impossível. O volume de publicações relevantes em cardiologia é de centenas de artigos por mês. Nenhum humano consegue filtrar isso sozinho.

O resultado: médicos praticando condutas desatualizadas. Não por negligência. Por falta de tempo e de filtro.

### A solução

O CardioDaily é um serviço de inteligência clínica. Ele:
1. **Captura** artigos de cardiologia de alto impacto (NEJM, JACC, EHJ, Circulation, JAMA Cardiology e ~40 outras revistas)
2. **Analisa** cada artigo com IA — não resume, analisa. Avalia metodologia, identifica o que muda na prática, quantifica o benefício
3. **Filtra** pelo que realmente importa — usa um sistema de notas com regras invioláveis (LEI 0) que impede inflar a importância de estudos fracos
4. **Entrega** todo dia às 07:00, personalizado por especialidade, em 4 formatos: gancho socrático + áudio + visual abstract + PDF completo

### A prova de que funciona

O próprio Dr. Eduardo mudou sua prática em pelo menos 3 condutas nos últimos 6 meses por causa do sistema: propranolol na tempestade elétrica, IECA vs BRA no BioBank, clopidogrel crônico no PEGASUS. Nenhuma dessas mudanças teria ocorrido sem o sistema filtrando e entregando na hora certa.

---

## PARTE 2 — A LEI 0: A REGRA MAIS IMPORTANTE DO SISTEMA

### Por que existe

A inteligência artificial — Gemini, Claude, GPT — tem tendência a superestimar a importância de estudos. Um registro nacional com 10.000 pacientes impressiona, mas metodologicamente é muito mais fraco que um RCT com 500. Se o sistema não tiver uma regra inviolável sobre isso, ele vai entregar "nota 9" para estudos que valem, no máximo, nota 6. Isso corromperia a confiança do médico.

### A regra

**Passo 1 — Teto por desenho de estudo:**

| Nível | Desenho | NAC máximo |
|---|---|---|
| A | RCT + desfecho duro + adjudicação central | 10 |
| B | RCT com surrogate validado ou com limitações | 8 |
| C | Observacional COM grupo controle + propensity score ou multivariada robusta | 7 |
| D | Registro prospectivo SEM grupo controle | 6 |
| E | Série de casos, transversal, opinião de especialista | 5 |

**Passo 2 — Teto estatístico:**
Se `nota_trabalho_estatistico < 8` → NAC máximo é 7, independente do desenho.

**O que NÃO eleva o nível:**
"Multicêntrico", "prospectivo", "nacional", "N=10.000" — nenhum desses conta. O que define o nível é: (1) randomização, (2) grupo controle, (3) adjudicação central de desfechos.

### Onde está implementada

- **Em código:** função `aplicar_teto_nac()` em `src/article_analyzer.py` — aplicada antes de salvar no Supabase
- **No prompt:** `src/prompts/prompt_artigo_original_v2.md` — instrui o LLM a respeitar o teto
- **No auditor:** `scripts/auditoria_supabase.py` — detecta violações automaticamente e lista os infratores

---

## PARTE 3 — O FUNIL DE ENTREGA

Todo artigo aprovado percorre este caminho antes de chegar no celular do médico:

```
1. GANCHO SOCRÁTICO (texto, 1-2 linhas)
   Pergunta ou provocação clínica — faz o médico querer saber mais.
   Exemplo: "Você ainda usa metoprolol para miocardiopatia hipertrófica obstrutiva?"
   Gerado por: scripts/gerar_ganchos_abertura.py (Claude Sonnet 4.6)

2. ÁUDIO (MP3, 3-5 minutos)
   Análise técnica narrada — ouve no carro, no corredor, entre procedimentos.
   Tom: colega para colega. Sem introdução longa, sem lero-lero.
   Gerado por: src/podcast_script_generator.py (GPT-4o script) + OpenAI TTS-HD onyx (áudio)
   Publicado em: Supabase bucket "podcasts"

3. VISUAL ABSTRACT (imagem PNG 1920×1080)
   8 seções visuais — o médico decide em 10 segundos se merece atenção.
   Não é para ensinar. É anzol.
   Gerado por: src/infographics/visual_abstract_generator.py (Playwright + Jinja2)
   Publicado em: Supabase bucket "visual_abstracts"

4. PDF COMPLETO (4-6 páginas)
   Análise completa com todos os campos clínicos — destino final para quem quer todos os detalhes.
   Gerado por: src/pdf_generator.py (WeasyPrint)
   Publicado em: Supabase bucket "resumos_pdf"
```

**Regra absoluta:** os 4 elementos são obrigatórios. Artigo sem áudio, sem VA ou sem PDF **não é enviado**. O distribuidor verifica os 4 antes de qualquer envio.

---

## PARTE 4 — ARQUITETURA: COMO O SISTEMA FUNCIONA

### O cérebro: Supabase

O Supabase é o banco de dados central. Tabela principal: `artigos` — 3.592 registros (Mai/2026).

Cada artigo no Supabase é um registro com campos precisos:

| Campo | O que é | Por que importa |
|---|---|---|
| `doc_id` | Hash único do PDF original | Chave primária — evita duplicatas |
| `titulo` | Título real do artigo | O que o médico vê na lista |
| `revista` | Sigla da revista (NEJM, JACC, EHJ…) | Contexto de credibilidade |
| `data_publicacao` | Data de publicação na revista | Filtra o que é recente |
| `created_at` | Data em que Dr. Eduardo indexou | **Usado pelo distribuidor** — não data_publicacao |
| `tipo_estudo` | original / revisao / metanalise / guideline | Define qual LLM analisa e qual prompt |
| `doenca_principal` | Categoria clínica (73 opções) | Personalização por especialidade do assinante |
| `nota_aplicabilidade` | NAC 1-10 com teto LEI 0 | O filtro de qualidade central do sistema |
| `nota_trabalho_estatistico` | Nota metodológica (Passo 2 da LEI 0) | Impede NAC inflado por estudo fraco |
| `caminho_audio` | URL pública do MP3 | Funil — sem isso o artigo não é enviado |
| `caminho_visual_abstract` | URL pública do VA PNG | Funil — sem isso o artigo não é enviado |
| `caminho_pdf` | URL pública do PDF | Funil — sem isso o artigo não é enviado |
| `gancho_abertura` | Frase socrática (200 chars) | Primeiro contato do médico com o artigo |
| `gancho_lista` | Frase curta (90 chars) | Listas WhatsApp semanais |
| `contexto_tema` | Por que o tema importa clinicamente | Componente do PDF e do site |
| `aplicabilidade_pratica` | O que fazer na prática | Componente central da entrega |
| `bullets_praticos` | JSONB — condutas com dose e critério | O mais acionável do sistema |
| `tamanho_beneficio` | ARR/NNT ou MD/SMD com IC 95% | Quantifica o benefício real — nunca apenas RR/OR/HR |
| `mcid_avaliacao` | MCID + efeito + IC 95% + veredito clínico | Separa significância estatística de relevância clínica real |

**Por que `created_at` e não `data_publicacao`?**
Um artigo do NEJM de janeiro de 2025 que o Dr. Eduardo analisou em maio de 2026 é **novo** para o sistema. O que importa é quando entrou na base, não quando foi publicado. Esse bug existiu e foi corrigido em 19/abr/2026.

### O corpus local

Cada artigo tem uma pasta em `outputs/corpus/{doc_id}/`:
```
outputs/corpus/doi_XXXXX/
├── source.pdf              ← PDF original
├── analysis.md             ← Análise completa em markdown
├── analysis.json           ← Todos os campos estruturados
└── assets/
    ├── visual_abstract.png ← VA 8 seções (nota ≥ 7)
    ├── resumo.pdf          ← PDF resumo
    └── podcast.mp3         ← Áudio (nota ≥ 8)
```

O Supabase é a janela pública do corpus. O corpus local é a fonte da verdade.

---

## PARTE 5 — OS SCRIPTS: CADA UM, SUA FUNÇÃO, SUA RAZÃO DE EXISTIR

### NÚCLEO — Rodam no dia a dia

**`ARTIGOS/classificador_artigos.py`**
O porteiro. Recebe PDFs novos, renderiza a primeira página como imagem, manda para o Gemini 2.0 Flash Vision que identifica: é original? revisão? meta-análise? guideline? Renomeia o arquivo no formato `YYYY-MM-REVISTA-Titulo.pdf` e move para a pasta certa. Acurácia: 98%+. Sem ele, o pipeline não sabe como analisar o artigo.

**`src/article_analyzer.py`**
O cérebro. O script mais importante do sistema. Orquestra todo o pipeline de análise:
- Lê o PDF, extrai texto
- Detecta tipo (original → Gemini 2.5 Pro, revisão/guideline → Claude Sonnet 4.6)
- Envia para o LLM com o prompt correto
- Aplica LEI 0 (teto de nota inviolável)
- Gera podcast script + áudio
- Gera Visual Abstract
- Gera PDF resumo
- Faz upsert completo no Supabase com todos os campos

**`distribuidor.py`**
O carteiro. Todo dia às 07:00, busca no Supabase os artigos elegíveis para cada assinante (nota ≥ 8, tema compatível, não enviado antes, pacote completo), monta a mensagem e envia via Z-API (WhatsApp) + Telegram. Também distribui o Radar às 08:00. Versão atual: v4.1.

**`src/web_biblioteca.py`**
O administrador local. Servidor HTTP em `localhost:5100` — busca visual, preview do artigo, análise completa renderizada. Usado pelo Dr. Eduardo para revisar artigos antes de qualquer decisão editorial.

**`src/radar/radar_pubmed.py`**
Varre o PubMed diariamente em 1 de 13 temas (ciclo de 13 dias). Baixa os abstracts, analisa com Gemini, gera script de podcast e áudio via ElevenLabs. Publica no Supabase bucket `radar_podcasts`. **ElevenLabs exclusivamente** — sem fallback para OpenAI TTS.

**`src/briefing_semanal.py`**
O Eduardo Cri-Cri. Ao final de cada lote de análise, gera um briefing ácido e irreverente sobre os novos artigos. Voz: Cartesia Luana PT-BR. Serve para o Dr. Eduardo ter um panorama rápido do que entrou sem precisar abrir o Administrador.

**`src/pdf_generator.py`**
Gera o PDF de 4-6 páginas de cada artigo. Lê `analysis.json` (formato novo) ou `analysis.md` (legado). Motor: WeasyPrint. Estilo: clean, acadêmico, sem emojis ou tabelas desnecessárias.

**`src/podcast_script_generator.py`**
Transforma a análise estruturada em um script de podcast coloquial. Motor: GPT-4o. Tom: colega para colega, direto, sem introdução longa.

**`src/infographics/visual_abstract_generator.py`**
Gera o Visual Abstract de 8 seções (1920×1080px). Motor: Playwright renderizando HTML/CSS → PNG. **ÚNICO formato visual aprovado** — todos os outros estão em quarentena permanente.

**`src/lista_whatsapp.py`**
Gera as mensagens de lista navegável para WhatsApp — lista diária e lista semanal por revista. Dois formatos: FORMATO_A (com emoji de cor) e FORMATO_B (sóbrio, com tag).

**`scripts/auditoria_supabase.py`**
O inspetor. Verifica a integridade de toda a tabela: campos nulos, títulos genéricos, violações de LEI 0, artigos sem áudio, cobertura do Radar. Roda semanalmente. Envia relatório via Telegram. **O único script que tem visão completa da saúde do sistema.**

---

### BACKFILL — Rodam uma vez para corrigir o passado

Existem porque o sistema evoluiu. Campos que hoje são obrigatórios não existiam quando os primeiros artigos foram indexados. Esses scripts preenchem retroativamente sem precisar reanalisar o artigo:

| Script | O que preenche | Por que existe |
|---|---|---|
| `scripts/backfill_campos_clinicos.py` | `contexto_tema`, `aplicabilidade_pratica`, `impacto_conduta`, etc. | Campos do schema novo, artigos antigos não tinham |
| `scripts/backfill_keywords.py` | `keywords` | Campo criado depois da indexação inicial |
| `scripts/backfill_titulos.py` | `titulo` | Artigos com título vazio ou de template |
| `scripts/backfill_data_publicacao.py` | `data_publicacao` | Datas faltando — CrossRef como fonte |
| `scripts/backfill_datas_crossref.py` | `data_publicacao` via CrossRef | Versão mais precisa do anterior |
| `scripts/backfill_sem_resumo.py` | `resumo_markdown` | Artigos sem take-home textual |
| `scripts/extrair_ganchos.py` | `gancho_lista` em lote | Ganchos para a lista semanal |
| `scripts/gerar_ganchos_abertura.py` | `gancho_abertura` | Gancho socrático para envio diário |

---

### UPLOAD — Publicam no Supabase Storage

O corpus local tem os arquivos. Esses scripts sobem para o bucket público:

| Script | O que sobe | Bucket |
|---|---|---|
| `scripts/upload_pdfs_supabase.py` | PDFs resumo | `resumos_pdf` |
| `scripts/upload_podcasts_supabase.py` | MP3 dos artigos | `podcasts` |
| `scripts/upload_visual_abstracts_supabase.py` | VA PNG | `visual_abstracts` |

---

### REANÁLISE — Reprocessam artigos já analisados

Existem porque o sistema evolui e análises antigas ficam desatualizadas:

| Script | Quando usar |
|---|---|
| `scripts/reanalisar_2026.py` | Reanálise dos artigos de 2026 com novo prompt |
| `scripts/reanalisar_flagados.py` | Artigos marcados como problemáticos |
| `scripts/reanalyze_failed_packages.py` | Artigos com pacote incompleto |
| `scripts/reparar_scores_e_vas.py` | Corrige notas e VAs quebrados |
| `scripts/reparar_audio_paths.py` | Reconecta áudios desvinculados |

**ATENÇÃO:** Reanálise custa dinheiro (Gemini + Claude). Nunca reanalisar sem antes verificar se o backfill zero-custo resolve. Regra absoluta: **auditar antes de reanalisar**.

---

### INDEXAÇÃO — Constroem o banco a partir do corpus local

| Script | Função |
|---|---|
| `scripts/indexar_corpus_completo.py` | Varre o corpus inteiro e indexa tudo no Supabase |
| `scripts/extrai_campos_llm.py` | Extrai campos clínicos via LLM de artigos sem structured data |
| `scripts/corrigir_taxonomia.py` | Corrige `doenca_principal` com valores errados (Other, Outros) |

---

### SUPORTE — Raramente rodam

| Script | Função |
|---|---|
| `scripts/admin_temas.py` | Gestão dos temas do Radar |
| `scripts/compactar_diretriz.py` | Compacta guidelines longas para o manual |
| `scripts/rebuild_markdown_exports.py` | Reconstrói exports markdown do corpus |
| `scripts/repair_corpus_missing_analysis_md.py` | Recupera artigos sem analysis.md |
| `scripts/sync_resumo_markdown.py` | Sincroniza resumos entre corpus e Supabase |
| `scripts/preencher_nota_aplicabilidade.py` | Preenche notas faltando em lote |
| `scripts/fix_titulos_supabase.py` | Correções manuais de títulos em lote |

---

## PARTE 6 — DOIS SCHEMAS DE ANÁLISE (DECISÃO CRÍTICA DE MAI/2026)

O sistema tem dois tipos de artigo com análises completamente diferentes:

### Schema 1 — Artigos Originais e Meta-análises (Gemini 2.5 Pro)

```json
{
  "titulo": "...",
  "nota_aplicabilidade_clinica": 8,
  "nota_trabalho_estatistico": 7,
  "contexto_tema": "por que este tema importa clinicamente",
  "nucleo_comum": {
    "aplicabilidade_pratica": "o que fazer",
    "impacto_conduta": "como muda a prática",
    "tamanho_beneficio": "magnitude do efeito",
    "conclusao_geral": "síntese"
  },
  "analise_especifica": { ... },  // módulos por tipo: RCT, Diagnóstico, Prognóstico...
  "reflexao_final": {
    "bullets_praticos": ["conduta 1", "conduta 2"]
  }
}
```

### Schema 2 — Revisões, Guidelines e Meta-análises de rede (Claude Sonnet 4.6)

```json
{
  "por_que_importa": { ... },
  "principais_recomendacoes": [...],
  "algoritmo_principal": "...",
  "nota_relevancia_pratica": 9
}
```

**Como o sistema detecta qual schema usar:**
```python
is_guideline = bool(s.get('por_que_importa') or s.get('principais_recomendacoes'))
```

**Por que dois schemas?** Guidelines têm estrutura própria (recomendações por classe de evidência, algoritmos). Forçar o mesmo JSON de um RCT em um guideline produzia análises ruins. A separação melhorou radicalmente a qualidade.

---

## PARTE 7 — O QUE FOI TENTADO E DESCARTADO

### n8n — CANCELADO (05/Abr/2026)
Custo: $350/mês. Complexidade: enorme. Valor: zero além do que Python já fazia.
Substituído 100% por `distribuidor.py` + GitHub Actions. Economia imediata.

### DALL-E 3 — PROIBIDO PERMANENTEMENTE
Testado para gerar infográficos. Resultado: corações bonitos com setas e bolinhas. Zero conteúdo clínico. Não consegue renderizar números, tabelas ou dados com precisão. Custo: US$0,04/imagem para lixo visual. Arquivos movidos para `archive/legacy_images/`.

### Cards HTML→PNG para WhatsApp — PROIBIDO PERMANENTEMENTE
Layout 1080×1080px via Playwright. Problema: bullets curtos (como devem ser) ficam com fonte minúscula. Espaços vazios enormes. Resultado visual amador. Não serve para WhatsApp onde o conteúdo precisa ser lido em 2 segundos.

### InfographicPortrait (`portrait_visualmed`) — PROIBIDO PERMANENTEMENTE
Gerador de infográficos portrait. Descartado pelos mesmos motivos dos cards: layout não adaptativo, resultado ruim com dados reais.

### MindmapGenerator PNG — PROIBIDO PERMANENTEMENTE
Gerador de mapas mentais visuais. Descartado. O mapa mental em markdown (`mindmap.md`) ainda existe no corpus mas sem geração de PNG.

### `infographic_mpl.py` (matplotlib/seaborn) — PROIBIDO PERMANENTEMENTE
Gráficos de barras e charts. Descartado. Representação visual de dados clínicos via matplotlib produzia gráficos genéricos sem valor para o médico.

**O único formato visual aprovado:** Visual Abstract de 8 seções (`src/infographics/visual_abstract_generator.py`). Aprovado pelo Dr. Eduardo após testes. Qualidade: 9/10.

### Google Drive como fonte de PDFs — ABANDONADO
O pipeline original baixava PDFs do Google Drive. Criava dependência de API, autenticação e lentidão. Substituído por pasta local: Dr. Eduardo joga o PDF na pasta, o sistema analisa.

---

## PARTE 8 — ESTADO ATUAL DO SISTEMA (29/Mai/2026)

### Funil nota ≥ 8 (1.012 artigos elegíveis)

| Asset | Cobertura | Situação |
|---|---|---|
| Visual Abstract | 100% | ✅ |
| PDF | 99% | ✅ |
| Gancho abertura | 99% | ✅ |
| Áudio | 54% (541/1.012) | 🔴 471 nunca gerados |

**Os 471 sem áudio:** nunca foram gerados — existem antes do sistema de áudio estar consolidado. Gerar todos custa ElevenLabs/OpenAI TTS. Decisão do Dr. Eduardo sobre quando e quanto gastar.

### Completude da tabela `artigos`

| Campo | Preenchimento | Observação |
|---|---|---|
| `titulo` | 99.7% | 9 vazios — artigos com problema no PDF original |
| `revista` | 99.5% | 16 nulos — todos nota ≤ 6, fora do funil |
| `nota_aplicabilidade` | 99.9% | LEI 0 aplicada em 41 artigos em 28/Mai/2026 |
| `nota_trabalho_estatistico` | ~35% | Só artigos do schema novo (Mai/2026+) |
| `mcid_avaliacao` | ~2.5% (90 artigos) | Campo novo — só artigos de 29/Mai/2026 |
| `tamanho_beneficio` | ~35% | Campo novo — schema Mai/2026+ |
| `doenca_principal` | 95% | 161 nulos — todos nota ≤ 4, fora do funil |
| `caminho_audio` | 19% | 471 históricos pendentes |
| `caminho_visual_abstract` | 68% | Upload histórico pendente |
| `caminho_pdf` | 97.9% | 76 pendentes |
| `resumo_markdown` | 74% | Artigos do schema antigo sem take-home |
| `keywords` | 86% | Backfill parcial feito |
| `contexto_tema` / campos clínicos | 66% | Só schema novo (Mai/2026+) |

**Sobre os buracos históricos:** não são erros. São artigos indexados antes do schema atual existir. Eles têm `analysis.md` e `nota_aplicabilidade` corretos — funcionam no funil. Só não têm os campos novos.

### Componentes operacionais

| Componente | Status |
|---|---|
| Classificador v8.0 (Gemini Vision) | ✅ 98%+ acurácia |
| Pipeline de análise (Gemini 2.5 Pro + Claude 4.6) | ✅ Operacional |
| LEI 0 em código | ✅ Inviolável |
| LEI 0 no auditor | ✅ Implementado 28/Mai/2026 |
| Campo `mcid_avaliacao` (Supabase + prompts) | ✅ Implementado 29/Mai/2026 |
| Campo `tamanho_beneficio` (ARR/NNT/MD/SMD) | ✅ Implementado 29/Mai/2026 |
| Campo `bullets_praticos` em revisões/meta | ✅ Implementado 29/Mai/2026 |
| Visual Abstract 8 seções | ✅ Operacional |
| Podcast (GPT-4o + TTS onyx) | ✅ Operacional |
| Radar PubMed (ElevenLabs) | ✅ 13 temas, ciclo de 13 dias |
| Briefing Cri-Cri (Cartesia Luana) | ✅ Operacional |
| PDF resumo (WeasyPrint) | ✅ Operacional |
| Distribuidor (Z-API + Telegram) | ✅ v4.1 — filtra títulos genéricos |
| Administrador web (localhost:5100) | ✅ Operacional |
| Auditor de integridade | ✅ v2.2 — LEI 0 + títulos + funil |
| Telegram Bot (@CardioDailyBot) | ⏳ Pendente migração do n8n |
| Deploy VPS | ⏳ Pendente — hoje roda local no Mac |

---

## PARTE 9 — PENDÊNCIAS POR PRIORIDADE

### 🔴 Alta

| # | Item | Comando |
|---|---|---|
| 1 | 471 artigos nota≥8 sem áudio — bloqueiam funil | `python3 scripts/gerar_audios_lote.py --desde 2020-01-01` |
| 2 | 76 PDFs sem upload no Supabase | `python3 scripts/upload_pdfs_supabase.py --since 2020-01-01` |
| 3 | Revisão de notas com viés (~850 artigos) | Decisão editorial — reanálise em lotes |

### 🟡 Média

| # | Item |
|---|---|
| 4 | Criar bucket `briefing_audio` no Supabase Dashboard → Storage |
| 5 | Conectar `radar_pubmed.py` → tabela `radar` para upload automático |
| 6 | Migrar `telegram_bot.py` para `nota_aplicabilidade` e dropar `nota_geral` |

### ⚪ Baixa

| # | Item |
|---|---|
| 7 | Telegram Bot — migrar para `scripts/telegram_bot.py` |
| 8 | RLS Supabase — habilitar antes do lançamento público |
| 9 | Deploy VPS $5/mês — produção estável sem depender do Mac |
| 10 | Site próprio — acesso dos assinantes + publicações |

---

## PARTE 10 — COMO OPERAR O SISTEMA

### Processar novos artigos (sequência completa)

```bash
# 1. Classificar PDFs novos
# Abrir: Classificar Artigos.app → apontar para pasta com PDFs

# 2. Analisar tudo
# Abrir: Analisar Tudo.app
# (roda article_analyzer.py nas 4 pastas: ARTIGOS_ORIGINAIS, REVISOES, META_ANALISES, GUIDELINES)

# 3. Arquivar PDFs processados
# Abrir: Arquivar Artigos.app

# 4. Gerar ganchos de abertura para novos artigos nota≥8
python3 scripts/gerar_ganchos_abertura.py --nota-min 8 --apenas-vazios
```

### Distribuição diária (automática via GitHub Actions)

```bash
python3 distribuidor.py artigos       # 07:00 — 1 artigo por assinante
python3 distribuidor.py radar         # 08:00 — podcast do Radar
python3 distribuidor.py teste         # dry-run — sem enviar nada
python3 distribuidor.py eduardo       # envia só para Dr. Eduardo (revisão)
```

### Auditoria semanal

```bash
python3 scripts/auditoria_supabase.py           # relatório completo + Telegram
python3 scripts/auditoria_supabase.py --dry-run # só exibe, não envia
python3 scripts/auditoria_supabase.py --quick   # só contadores
```

### Administrador local

```bash
# Abrir: Administrador.app
# Ou:
python3 src/web_biblioteca.py
# Acesso: http://localhost:5100
```

---

## PARTE 11 — VARIÁVEIS DE AMBIENTE (.env)

```
SUPABASE_URL                  # URL do projeto Supabase
SUPABASE_SERVICE_KEY          # Chave de serviço (admin) — NUNCA expor publicamente
ZAPI_BASE                     # Base URL do Z-API
ZAPI_CLIENT_TOKEN             # Token de autenticação Z-API
TELEGRAM_BOT_TOKEN            # Token do @CardioDailyBot
TELEGRAM_CHAT_ID              # Chat ID do Dr. Eduardo
GOOGLE_API_KEY                # Gemini 2.5 Pro + 2.0 Flash
ANTHROPIC_API_KEY             # Claude Sonnet 4.6
OPENAI_API_KEY                # GPT-4o (podcast script) + TTS-HD (áudio artigos)
ELEVENLABS_API_KEY            # Radar podcast
ELEVENLABS_VOICE_ID           # Voz do Radar (eleven_multilingual_v2)
CARTESIA_API_KEY              # Briefing Cri-Cri (Luana PT-BR)
BETA_PAUSADO=1                # Quando 1: envia apenas para Dr. Eduardo
```

---

## PARTE 12 — DECISÕES TÉCNICAS PERMANENTES

| Decisão | Regra | Motivo |
|---|---|---|
| Único artefato visual | Visual Abstract 8 seções — todos outros PROIBIDOS | Único testado e aprovado pelo Dr. Eduardo |
| TTS do Radar | ElevenLabs exclusivamente — sem fallback | Qualidade superior, voz consistente |
| TTS do Briefing | Cartesia Luana PT-BR | Isabella rejeitada ("rapariga de Portugal") |
| TTS dos artigos | OpenAI TTS-HD onyx | Custo menor que ElevenLabs para volume alto |
| Gemini: um único `contents` | Prompt + artigo juntos, sem `system_instruction` | Separar degrada qualidade da análise |
| PDF: sem `page-break` manual | Paginação automática WeasyPrint | Breaks manuais quebravam o layout |
| Filtro de envio | `created_at` (data de indexação), não `data_publicacao` | Artigo antigo analisado hoje = artigo novo |
| DALL-E | PROIBIDO | Zero valor clínico, custo real |
| n8n | CANCELADO | $350/mês sem vantagem sobre Python puro |
| `mcid_avaliacao` | OBRIGATÓRIO em todos os artigos sem exceção | Separa p<0,05 de "importa para o paciente" |
| Placeholders em prompts | PROIBIDO — usar valores exemplo reais | `[texto entre colchetes]` → Gemini trata como opcional e omite |

---

---

## PARTE 13 — MCID: O CRITÉRIO DE RELEVÂNCIA CLÍNICA REAL

### O que é MCID

MCID (Minimum Clinically Important Difference) é a menor mudança em um desfecho que o paciente percebe como benéfica. É o que separa **significância estatística** de **relevância clínica real**.

Um estudo pode ter p<0,001 e ainda assim o efeito ser clinicamente irrelevante — se o benefício real for menor que a MCID, o paciente individual não percebe diferença.

### Regra do sistema

O campo `mcid_avaliacao` é **obrigatório em todos os artigos**, sem exceção, independente de nota ou tipo. Formato padrão:

```
MCID: X% ARR ou Y unidades (fonte: autores/literatura/estimativa clínica)
| Efeito: ARR Z%; HR A (IC95% B–C)
| Limite inferior IC supera MCID: SIM ✅ ou NÃO ⚠️ ou Não calculável
| Veredito: frase direta sobre relevância clínica real para o paciente individual
```

### Como interpretar o campo

| Situação | Interpretação |
|---|---|
| Limite inferior IC > MCID | ✅ Benefício clínico robusto — mesmo no pior cenário estatístico, o paciente percebe diferença |
| IC cruza a linha da MCID | ⚠️ Significância estatística sem garantia de relevância clínica |
| Limite inferior < 0 | ❌ Sem evidência de benefício clínico |
| Não aplicável (qualitativo, diagnóstico, etc.) | Declarar explicitamente o motivo |

### Bug identificado e corrigido (29/Mai/2026)

O prompt original usava `"mcid_avaliacao": "[placeholder em colchetes]"` → Gemini interpretava como campo opcional e deixava vazio. Corrigido: todos os prompts agora usam valores exemplo reais no formato final esperado, com aviso obrigatório `⚠️ NUNCA deixe este campo vazio`.

### Prompts atualizados

| Prompt | Arquivo | Status |
|---|---|---|
| Artigos originais | `src/prompts/prompt_artigo_original_v2.md` | ✅ mcid_avaliacao obrigatório |
| Revisões/guidelines | `src/prompts/prompt_revisao_geral_v2.md` | ✅ mcid_avaliacao obrigatório |
| Meta-análises | `src/prompts/prompt_meta_analise_v2.md` | ✅ mcid_avaliacao obrigatório |

---

*Documento atualizado em 29/Mai/2026. Próxima atualização: ao final de cada sessão de desenvolvimento.*
