# CADERNO DE EXECUÇÃO — CARDIODAILY
## Versão 28.0 | 08/Jun/2026
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

## PARTE 8 — ESTADO ATUAL DO SISTEMA (08/Jun/2026)

> **Fonte:** `scripts/auditoria_supabase.py` rodada em 07/Jun/2026 16:42. Total de 3.751 artigos no Supabase. Relatório salvo em `outputs/auditorias/auditoria_20260607_1642.txt`.

### Completude da tabela `artigos` (3.751 artigos)

| Campo / Asset | Buraco | Situação |
|---|---|---|
| `titulo` | 0 nulos/vazios | ✅ — 47 corrigidos em 07/Jun (nome de arquivo → título real) |
| `caminho_pdf` | 0 sem | ✅ — completo |
| `caminho_audio` | 2.732 sem (72.8%) | 🟡 — **28 nota≥8 sem áudio** (clássicos 2000-2019, gerando); 957 com áudio |
| `resumo_markdown` | 72 sem (1.9%) | 🟡 — residual irrecuperável (sem PDF local) |
| `keywords` | 127 sem (3.4%) | 🟡 — baixa prioridade |
| `doenca_principal` | 0 sem no funil | ✅ |
| **LEI 0 — violações ativas** | **0** | ✅ — 7 violações corrigidas em 07/Jun |

### Componentes operacionais

| Componente | Status |
|---|---|
| Classificador v8.0 (Gemini Vision) | ✅ 98%+ acurácia |
| Pipeline de análise (Gemini 2.5 Pro + Claude Sonnet 4.6) | ✅ Operacional |
| LEI 0 em código + auditor | ✅ Inviolável — 0 violações ativas |
| Visual Abstract 8 seções | ✅ Operacional |
| Podcast (GPT-4o + TTS onyx) | ✅ Operacional — 957 artigos nota≥8 com áudio |
| Radar PubMed (ElevenLabs) | ✅ 13 temas, ciclo de 13 dias |
| Briefing Cri-Cri (Cartesia Luana) | ✅ Operacional |
| PDF resumo (WeasyPrint) | ✅ Operacional |
| Distribuidor (Z-API + Telegram) | ✅ Operacional — disparo diário 07h via GitHub Actions |
| **WhatsApp busca** | ✅ **Operacional** — entrega análise clínica completa (gancho + resumo + bullets) |
| Administrador web (localhost:5100) | ✅ Operacional |
| Auditor de integridade | ✅ v2.3 — LEI 0 + títulos + funil + relatório Telegram |
| Marketing Studio (Streamlit) | ✅ Novo — `src/marketing/studio_app.py` |
| Telegram Bot (@CardioDailyBot) | ⏳ Pendente migração do n8n |
| Deploy VPS | ⏳ Pendente — hoje roda local no Mac |

---

## PARTE 9 — PENDÊNCIAS POR PRIORIDADE (atualizada 08/Jun/2026)

### ✅ Resolvido em 04-08/Jun/2026

| Item | Status |
|---|---|
| 7 violações LEI 0 (NAC≥8 com EST<8) | ✅ Corrigidas manualmente 07/Jun |
| 47 títulos com nome de arquivo | ✅ Corrigidos via backfill 07/Jun |
| 479 artigos sem `resumo_markdown` | ✅ Preenchidos (resumo sintético) |
| 32 áudios nota≥8 (2020-2026) | ✅ Gerados via `gerar_audios_lote.py --desde 2020-01-01` |
| WhatsApp busca — campo `text` Z-API | ✅ Corrigido — era dict `{"message":"..."}` não string |
| WhatsApp busca — formato da resposta | ✅ Entrega análise clínica (gancho+resumo+bullets), não lista |
| Marketing Studio | ✅ `src/marketing/studio_app.py` — Streamlit com IA |
| Placas CardioDaily (stories + post) | ✅ `src/marketing/placa_generator.py` — auto-fit aprovado |

### 🔴 Alta

| # | Item | Situação atual | Comando |
|---|---|---|---|
| 1 | 28 áudios nota≥8 clássicos (2000-2019) | ⏳ Gerando agora | `python3 scripts/gerar_audios_lote.py --desde 2000-01-01` |
| 2 | Fechar delta corpus↔Supabase | 470 local não indexados | `python3 scripts/indexar_corpus_completo.py` |
| 3 | WhatsApp webhook — URL fixa | cloudflared muda URL a cada reinício | Criar conta Cloudflare com domínio ou VPS |

### 🟡 Média

| # | Item |
|---|---|
| 4 | 127 artigos sem `keywords` |
| 5 | Criar bucket `briefing_audio` no Supabase Dashboard |
| 6 | Conectar `radar_pubmed.py` → upload automático bucket radar |
| 7 | Migrar `telegram_bot.py` |

### ⚪ Baixa

| # | Item |
|---|---|
| 8 | RLS Supabase — habilitar antes do lançamento público |
| 9 | Deploy VPS $5/mês — produção estável sem depender do Mac |
| 10 | Site próprio — acesso dos assinantes |
| 11 | Carrossel Instagram para revisões |

---

## PRIORIDADE ANTI-BURACO — a regra para o Supabase parar de ter furos

A causa-raiz dos buracos não é falta de backfill pontual — é que **artigos entram no Supabase em estados diferentes** conforme a época em que foram indexados. Para estancar de vez, a ordem é:

1. **LEI 0 primeiro (integridade > completude).** Um campo vazio é um buraco visível; uma nota errada é um buraco *invisível* que corrompe o produto. Rodar `reanalisar_flagados.py --lei0` sempre que o auditor acusar violação. Isso já está automatizado no auditor desde 31/Mai — basta agir quando ele apitar.
2. **Fechar o delta corpus↔Supabase.** As 90 pastas sem `analysis.json/md` são análises que nunca completaram — reprocessá-las e reindexar elimina o "+484". Enquanto o delta existir, todo dia que você indexa mais aparece um buraco novo.
3. **Tornar a auditoria um hábito, não um evento.** Rodar `python3 scripts/auditoria_supabase.py` ao fim de cada lote (já manda relatório ao Telegram). O semáforo vermelho = ação imediata; amarelo = backlog; verde = ignorar.
4. **Áudio e resumo por último.** São caros (TTS) ou de schema antigo — não corrompem nada, só limitam alcance. Decisão de orçamento do Dr. Eduardo, não emergência de integridade.

**Regra de ouro:** nunca indexar um artigo sem antes confirmar que `analysis.json` existe e que a nota respeita o teto da LEI 0. O auditor agora pega isso — confie nele e aja no vermelho.

---

## PROJETO BURACO ZERO — CONCLUÍDO (31/Mai/2026)

**Funil nota≥7 (2.198 artigos) com campos de texto 99-100% preenchidos.** LEI 0 = 0 violações. Os NULL residuais (1-4 por campo) são artigos sem source.pdf local — irrecuperáveis.

| Campo | NULL final | Como foi preenchido |
|---|---|---|
| `nota_trabalho_estatistico` | 0 | já existia |
| `mcid_avaliacao` | 2 | Flash (669 funil 2026) + Pro fix (116) + Flash funil total (~1.500), prompt reforçado |
| `tamanho_beneficio` | 2 | Flash (158), prompt focado |
| `contexto_tema` | 2 | Flash (16) |
| `resumo_markdown` | 4 | **extração ZERO-TOKEN do analysis.md** (407) — `scripts/extrair_campos_md.py` |
| keywords/doença/pdf/visual | 1-4 | já existiam |

**Custo total do buraco zero: ~R$ 90** (mcid ~R$ 75 Flash+Pro + tamanho/contexto ~R$ 4 + resumo R$ 0 extração). Modelo padrão: Flash com `thinking_budget=0` + prompt que proíbe "não definido". Taxa de fracos caiu de 17% → 0%.

**Scripts do backfill (staging isolado, reutilizáveis):**
- `scripts/extrair_campos_md.py` — extrai campos do analysis.md SEM LLM (tentar SEMPRE primeiro)
- `scripts/mcid_fix_pro.py` — mcid com `--model flash|pro`, `--from-supabase`, prompt reforçado, parser tolerante a chave deturpada
- `scripts/campos_flash.py` — contexto_tema/tamanho_beneficio via Flash
- `scripts/mcid_staging_flash.py` — staging original Flash

**ÚNICO buraco grande restante: `caminho_audio` (1.525 no funil).** É TTS (custo real de geração), não dado faltante — decisão de orçamento do Dr. Eduardo, não emergência de integridade.

**Lição central:** o PROMPT importa mais que o MODELO. Trocar Flash→Pro ajudou pouco; o que zerou os "não definido" foi o prompt reforçado (proibir a resposta preguiçosa + listar valores de referência da literatura). E SEMPRE: validar staging (vazios/fracos) antes de sincronizar; extração zero-token antes de LLM.

## MUDANÇAS DE 31/Mai/2026

- **Padronização de modelos Claude:** todos os IDs em `src/` e `scripts/` migrados para `claude-sonnet-4-6` (eram um mix de `claude-sonnet-4-20250514` antigo + variações). 8 arquivos de chamada + 2 docstrings em `article_analyzer.py`. Migração feita via skill `claude-api` — sem mudanças quebradas (Sonnet 4.6 mantém `temperature`). Verificado: 18 referências, todas canônicas, todos os arquivos compilam.
- **Auditor v2.3 — check automático de LEI 0:** `scripts/auditoria_supabase.py` agora detecta artigos com `nota_aplicabilidade ≥ 8` e `nota_trabalho_estatistico ≤ 7` (violação do teto estatístico) e sugere `reanalisar_flagados.py --lei0`. Pegou 5 violações na primeira rodada.
- **5 violações da LEI 0 corrigidas:** reanálise dos 5 doc_ids flagados. Auditor final: **`LEI 0 — teto estatístico violado: 0`**. Notas finais: doi_76adf=8/8, doi_5083=5/8, doi_aa62=7/6, doi_9ca7=7/8, doi_01fe=6/5. Backup das análises em `archive/logs_operacionais/backup_lei0_20260531/`.

### Backfill de mcid_avaliacao com Gemini Flash (31/Mai) — abordagem "staging isolado"

Preenchidos **669 mcid_avaliacao** no funil nota≥7 de 2026 (antes: 100% NULL). Custo total: **R$ 18,72** (Gemini 2.5 Flash, ~R$ 0,028/artigo — ~4x mais barato que o Pro). 2 artigos ficaram sem mcid por não terem `source.pdf` local.

**Padrão usado (replicável para outros campos novos):**
1. Script ISOLADO `scripts/mcid_staging_flash.py` — só leitura do corpus, calcula APENAS o campo novo, grava em CSV paralelo (`outputs/mcid_staging_flash.csv`). NUNCA toca em analysis.md/json nem na tabela `artigos` durante a geração. Elimina risco à LEI 0.
2. Piloto de 10 primeiro → revisar qualidade → escalar em lotes (script é retomável: pula doc_ids já no CSV, grava incremental com flush).
3. Sincronização CSV→Supabase é passo SEPARADO, só após aprovação: POST mínimo `on_conflict=doc_id` gravando SÓ o campo (não toca em nota). 669 gravados, 0 falhas. Auditor confirmou LEI 0 = 0 violações após sync.

**Detalhes técnicos que importam:**
- **Gemini 2.5 (Flash E Pro) têm "thinking" ON por padrão** e consomem o orçamento de saída → respostas vazias (out_tokens=0) ou truncadas. Fix OBRIGATÓRIO em extração estruturada: `thinking_config=types.ThinkingConfig(thinking_budget=0)` (Flash) ou `=512` (Pro). Esquecer isso no Pro gerou 52/116 mcid VAZIOS na 1ª tentativa.
- O `--limit` deve ser aplicado DEPOIS de remover os já-feitos (senão a query corta antes de deduplicar e nunca chega na cauda da fila).
- **SEMPRE validar o CSV de staging (contar vazios/truncados) ANTES de sincronizar** — foi essa checagem que evitou gravar 52 mcid vazios por cima de mcid presentes.

**Correção da qualidade (Flash → Pro, prompt reforçado):**
- Flash inicial: 47% diziam "não definida pelos autores", e 116 (17%) PARAVAM aí sem prosseguir — Dr. Eduardo reclamou ("mesma coisa que nada").
- Causa raiz: prompt fraco (não forçava o passo "se autor não definiu → usar valor da literatura"). O MODELO importava menos que o PROMPT.
- Fix: `scripts/mcid_fix_pro.py` (Gemini 2.5 Pro + prompt que PROÍBE parar em "não definido" e lista valores de referência: ARR≥1% eventos duros, ≥5mmHg PA, ≥5% FEVE/peso, AUC≥0.80 diagnóstico, etc.). 116 corrigidos por R$ 14,34. Resultado: 0 ainda fracos no funil 2026.
- **Custo total mcid: R$ 33,06** (R$ 18,72 Flash + R$ 14,34 Pro fix).

## MUDANÇAS DE 04-08/Jun/2026

### WhatsApp Bot — correções críticas (07/Jun/2026)
- **Bug raiz descoberto:** Z-API envia campo `text` como dict `{"message": "..."}`, não como string `body`. O código lia `payload.get("body")` → sempre vazio → `empty_body`. Corrigido em `src/whatsapp/webhook_handler.py`.
- **Formato de busca reformulado:** `_handle_busca` entrega top 5 artigos com análise clínica completa — gancho + resumo (2 frases) + bullets práticos inteiros. Antes entregava lista numerada de títulos (inútil para decisão clínica). Aprovado pelo Dr. Eduardo como "ficou top".
- **Expansão PT→EN:** adicionados `antiplaquetário`, `prasugrel`, `ticagrelor`, `DAPT`, `P2Y12` ao dicionário `_PT_TO_EN` em `src/web_biblioteca.py`.
- **`_buscar_supabase` reescrita:** busca direta no Supabase REST API (não depende mais do servidor `web_biblioteca` estar rodando). Query inclui `gancho_lista`, `resumo_markdown`, `bullets_praticos`.
- **Tunnel manager:** `scripts/tunnel_manager.py` — gerencia cloudflared quicktunnel e atualiza Z-API automaticamente quando URL muda. **Limitação:** URL muda a cada reinício (sem conta Cloudflare com domínio). Solução definitiva: VPS com IP fixo.

### Marketing Studio (04-05/Jun/2026)
- **`src/marketing/studio_app.py`** — Streamlit com 3 páginas: Sessão Semanal, Agenda, Kits Gerados.
- **`src/marketing/extrator_ia.py`** — extração de conteúdo via Claude API: lê `analysis.md`, entrega frase icônica, âncora, bullets, legenda Instagram, script de vídeo.
- **`src/marketing/placa_generator.py`** — gerador HTML→PNG via Playwright. Auto-fit de fontes calculado em Python por número de caracteres (JS descartado — imprevisível). Aprovado 100% pelo Dr. Eduardo.
- **Templates:** `story.html` (1080×1920) + `post_feed.html` (1080×1080) — identidade CardioDaily: cinza claro, verde teal #3BAF9E, hexágonos, logo.
- **`Marketing CardioDaily.app`** — clique duplo abre o Studio no browser.
- **Agentes Claude Code:** `.claude/agents/cardiodaily-dev.md`, `auditor.md`, `editorial.md`, `marketing.md`.

### Integridade do banco (07/Jun/2026)
- **7 violações LEI 0 corrigidas:** 1 NAC=10→5 (COVID PCR, EST=1), 6 NAC=8→7 (EST=7, teto máx 7).
- **47 títulos** corrigidos de nome de arquivo para título real.
- **479 resumos** preenchidos — 27 do `analysis.md` local + 450 sintéticos com metadados.
- **32 áudios** gerados (nota≥8, 2020-2026) via `gerar_audios_lote.py --desde 2020-01-01`.
- **28 áudios** clássicos (nota≥8, 2000-2019) em geração via `--desde 2000-01-01`.

### ⚠️ APRENDIZADOS OPERACIONAIS (31/Mai) — ler antes de reanalisar

1. **Billing do Gemini bloqueia tudo silenciosamente.** Em 31/Mai o projeto Google `478858602455` entrou em "dunning" (cobrança em atraso) → todas as chamadas Gemini deram `403 PERMISSION_DENIED`. O analyzer **não aborta** nesse erro: ele marca o artigo como falha mas continua. **SEMPRE rodar um smoke-test do Gemini antes de reanálise em lote.** Solução aplicada: criada API key nova num **projeto NOVO** (chave no mesmo projeto bloqueado herda o bloqueio). Chave atual no `.env`: `AIzaSyCOvq...`.

2. **`reanalisar_flagados.py` apaga as análises ANTES de confirmar sucesso** (Passo 4 remove `.md`/`.json`; Passo 5 reprocessa). Se o LLM falhar, perde-se a análise. **SEMPRE fazer backup dos `analysis.md`/`.json` antes de rodar.** (Foi o que salvou os dados na 1ª tentativa, que falhou por billing.)

3. **`_upsert_artigo_supabase` pode falhar silenciosamente.** Na reanálise, os 2 originais subiram ao Supabase ("🧠 Supabase atualizado"), mas as 3 meta-análises (título genérico = doc_id) **não** — o upsert retornou False sem erro visível, e o Supabase ficou com as notas velhas que violavam a LEI 0. Workaround aplicado: empurrar `nota_aplicabilidade`+`nota_trabalho_estatistico` direto do `analysis.json` local via POST mínimo (`on_conflict=doc_id`), que funciona (status 200). **TODO:** investigar por que o payload completo das meta com título genérico não faz upsert — provável que algum campo clínico cause 400 engolido pelo `except`.

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
OPENAI_API_KEY                # TTS-HD onyx (áudio artigos) — script podcast migrado para Gemini
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
| `caminho_pdf` obrigatório | Pipeline trava e tenta 3x antes de abortar o upsert | Regra definida 02/Jun/2026 — inadmissível indexar artigo sem PDF |
| Análise clínica obrigatória | Pipeline valida chars por tipo (-2DP) E campos clínicos — bloqueia ambos | Causa raiz: timeout Anthropic ~2min padrão; PDFs grandes levam 5-6min |
| Timeout Anthropic | `timeout=1800s` (30min) no cliente Anthropic | Revisões grandes levam 5-6min; guidelines >200 páginas levam 20min+ |
| Guidelines → Gemini 3.1 Pro | `guideline` usa `gemini-3.1-pro-preview` (janela 1M tokens) | Claude não aguenta guidelines de 200+ páginas (limite 200k tokens) |
| Auditor detecta corrupção | `auditoria_supabase.py` identifica artigos nota≥7 com MD<3000 chars | Comando: `python3 scripts/reanalise_corrompidos.py` |
| Script de correção | `scripts/reanalise_corrompidos.py` — reanálise em lote de corrompidos | Aceita lista de doc_ids como argumentos ou usa lista hardcoded |
| Modelo originais/meta | `gemini-3.5-flash` (era `gemini-2.5-pro`) | Testado em VANISH2 (NEJM): nota LEI 0 mais rigorosa, JSON completo, 43s/artigo, custo ~4x menor |
| Modelo guidelines | `gemini-3.1-pro-preview` (era `claude-sonnet-4-6`) | Claude não cabe guidelines de 200+ pág (limite 200k tokens); Gemini 3.1 Pro aguenta 882k chars em 66s |
| Modelo revisões | `claude-sonnet-4-6` — mantido | Revisões normais cabem; timeout corrigido para 1800s |
| Script podcast | `gemini-3.5-flash` (era `gpt-4o` → `gpt-4.1`) | OpenAI quota zerada em 02/Jun/2026; migrado para Gemini — mesma chave já ativa, custo menor |
| Claude Code (sessão) | Sonnet 4.6 + alto esforço | Padrão definido pelo Dr. Eduardo em 02/Jun/2026 |

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

*Documento atualizado em 03/Jun/2026. Próxima atualização: ao final de cada sessão de desenvolvimento.*

---

## PARTE 14 — HISTÓRICO DE VERSÕES

| Versão | Data | Mudanças |
|---|---|---|
| 29.0 | 04/Jun/2026 | Causa raiz dos 43 linhas: timeout Anthropic SDK (~2min padrão) — revisões grandes levam 5-6min. Corrigido para 1800s. Validação por chars (-2DP por tipo). Guidelines migrados para Gemini 3.1 Pro Preview (janela 1M, aguenta 882k chars em 66s). Reanálise 21 revisões corrompidas. |
| 28.0 | 03/Jun/2026 | Correção sistêmica de análises corrompidas; validação de qualidade no pipeline; detecção de corrupção no auditor; reanálise de 14 artigos nota≥7 com Gemini 3.5 Flash; podcast script migrado para Gemini 3.5 Flash (quota OpenAI zerada); 4 colunas criadas no Supabase (`muda_conduta text`, `por_que_importa`, `principais_recomendacoes`, `nota_metodologica numeric`) |
| 27.0 | 02/Jun/2026 | Troca `gemini-2.5-pro` → `gemini-3.5-flash` em originais/meta; troca `gpt-4o` → `gpt-4.1` no podcast; Claude Code padrão: Sonnet 4.6 + alto esforço |
| 26.0 | 31/Mai/2026 | MCID framework completo; campos novos; estado Supabase 31/Mai |
| 25.0 | 29/Mai/2026 | Padronização completa dos prompts — MCID obrigatório, placeholders proibidos |
