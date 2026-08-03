# CADERNO DE EXECUÇÃO — CARDIODAILY
## Versão 30.0 | 25/Jul/2026
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

## PARTE 5-A — CODEBOOK: QUAL MÓDULO USA QUAL PROGRAMA, PARA FAZER O QUÊ
*Criado 30/Jul/2026 · auditado arquivo por arquivo contra o disco.*
*Regra: toda alteração num módulo é registrada AQUI, na seção do módulo, com data e hora (LEI 2, item 5).*

> **Como ler:** cada MÓDULO é um botão em `/chaves/`. Cada módulo usa N programas de `src/`.
> "Modelo" = a cadeia de `src/modelos.py` (nunca hardcoded). "Lê / Escreve" = entrada e saída reais.

---

### MÓDULO 1 · CLASSIFICADOR  (botão `1_Classificador.command`)
**Objetivo:** decidir o TIPO de cada PDF sem chutar, renomear e mover para a pasta certa.

| Programa | Faz o quê | Modelo | Lê | Escreve |
|---|---|---|---|---|
| `classificador_ouro.py` | **entrada do módulo.** Camada A: mapa de revista por prefixo de DOI (determinístico, sem LLM). Camada B/C: quando o mapa não decide, chama o LLM lendo só a 1ª página | `EXTRACAO` (Sonnet 5) | `ARTIGOS/*.pdf` | `ARTIGOS/CLASSIFICADOS/<TIPO>/` |
| `classificador_pubmed.py` | **a autoridade.** Extrai o DOI (tolera quebra de linha e parêntese de citação) e consulta PubMed/EuropePMC para pegar o `publicationType` OFICIAL. É quem evita o chute | `RAPIDO` (Haiku) | PDF + API PubMed/EuropePMC | devolve tipo ao `classificador_ouro` |
| `pdf_extractor.py` | extrai o texto do PDF | — | PDF | texto |
| `reprocessar_fila.py` | **drena a FILA_ESPERA.** Artigo *ahead-of-print* ainda não indexado no PubMed espera aqui em vez de ser chutado; este programa re-consulta todo dia e classifica quando o PubMed cataloga | `RAPIDO` | `FILA_ESPERA/` | move p/ `CLASSIFICADOS/` ou `DESCARTADOS/` |

**Pastas de saída:** `ARTIGOS_ORIGINAIS` · `META_ANALISES` · `REVISOES` · `GUIDELINES` · `EDITORIAIS` ·
`MINIRREVISOES` · `DESCARTADOS` (relato de caso, carta) · `FILA_ESPERA` (aguarda PubMed) · `REVISAO_HUMANA`.

**🔴 BUG ABERTO (28/Jul/2026):** `Editorial`/`Comment` são mapeados para `ponto_de_vista` → pasta
`EDITORIAIS` → **entram na fila de análise**. Resultado no run de 27/Jul: 136 editoriais viraram perícia
completa (~7.400 tokens cada), saíram fora de contexto e foram recusados no portão. **Queima dinheiro.**
Decisão pendente do Dr. Eduardo: descartar na porta ou dar trilha própria.

---

### MÓDULO 2 · ANALISADOR  (botão `2_Analisador.command`) — o coração
**Objetivo:** transformar o PDF em FATOS → NOTA determinística → entregáveis, e publicar pelo portão.

| Programa | Faz o quê | Modelo | Lê | Escreve |
|---|---|---|---|---|
| `rodar_em_blocos.py` | **entrada do módulo.** Roda em BLOCOS DE 20: analisa o bloco → publica o bloco → só então o próximo. Se a net cair, só o bloco em andamento refaz | — | `CLASSIFICADOS/` | orquestra |
| `analisador.py` | orquestra UM artigo: fatos → nota → entregáveis por porta → **confere** → `_OK` | `ESCRITA` (Sonnet 5) | 1 PDF | pasta no `outputs/STAGING/` |
| `analise.py` | **extrai os FATOS** por SAÍDA ESTRUTURADA (tool use): a API obriga o modelo a devolver o `SCHEMA_FATOS`. JSON inválido é impossível | `EXTRACAO` | PDF + `analise_prompt.md` | `{nome}_fatos.json` |
| `notas_prototipo.py` | **MOTOR DE RIGOR — a LEI 0.** Determinístico, sem LLM: `min(teto_desenho, teto_externa, nota_estatistica, teto_falha_fatal)`. *Sagrado: não se mexe sem ordem do dono* | **nenhum** | os FATOS | as 2 notas + rota + falhas fatais + delatores |
| `teste_motor.py` | **a PROVA do motor.** Função pura → testável de graça, em 1 segundo, sem LLM/rede/banco. 11 baterias: pré-clínico fora da escala · o desenho importa em TODAS as perguntas · exemplos da LEI 0 um a um · teto estatístico em 3.000 combinações aleatórias · F1–F8 com os limiares numéricos · gabarito dos 6 artigos · contrato de saída | **nenhum** | `notas_prototipo` | APROVADO / REPROVADO |
| `pipeline.py` | monta o REGISTRO CANÔNICO (YAML + análise) — a "linha do banco", forjada uma vez | — | fatos + notas | `{nome}_CANONICO.md` |
| `pdf_analise.py` | perícia markdown + metadados → HTML → **PDF WeasyPrint** (a peça central do site) | — | `{nome}_analise.md` | `{nome}_analise.pdf` |
| `voz_utils.py` | roteiro → **MP3** (TTS OpenAI `gpt-4o-mini-tts`, voz **cedar**). Fatia por frase se passar de 4.000 chars; retry em queda de conexão. Tem também o lint anti-inglês (o TTS trocava de idioma) | TTS | roteiro | `{nome}_audio.mp3` |
| `infographics/visual_abstract_generator.py` | **VISUAL ABSTRACT de 8 seções** — o único artefato visual permitido. Extrai dados da perícia → Jinja2 → Playwright → PNG | Sonnet 5 | `analysis.md` | `assets/visual_abstract.png` → copiado p/ `{nome}_visual.png` |
| `minirevisao.py` | **trilha separada:** minirevisão / opinião de especialista → condutas + **fluxograma Mermaid**. NÃO sobe no Supabase | `ESCRITA` + `RAPIDO` | `CLASSIFICADOS/MINIRREVISOES/` | condutas + fluxograma |

**Prompts (todos na raiz de `src/`):** `analise_prompt.md` (fatos) · `redator_prompt.md` (perícia) ·
`acri_prompt.md` (card) · `script_audio_prompt.md` (áudio) · `gancho_abertura_prompt.md`.

### MUDANÇAS NESTE MÓDULO — 01/Ago/2026, 14h (motor de rigor)

**O que se mediu antes de mexer** (o motor nunca tinha sido testado; é função pura, custo zero):

1. **Fora de `intervencao`, o desenho era IGNORADO.** Etiologia, prognóstico e diagnóstico devolviam
   **8/8 para os 11 desenhos** — coorte, transversal, série de casos e pré-clínico, todos 8. Esta era
   a causa REAL do "padrão de nota 8" que o Dr. Eduardo apontou nas análises de 27/Jul. Não era o LLM.
2. **O camundongo foi reproduzido:** `pre_clinico` + `etiologia` + coleta boa → **NAC 8**.
3. **As duas notas coincidem em 80 %** de 4.000 combinações — e é **por construção**:
   `aplic = min(tetos, estatística)`. Quando nenhum teto morde, a segunda nota *é* a primeira.
   Não são duas medidas independentes. **Isto não é bug — é o desenho da régua.** (Item #18 do kanban
   pode ser fechado como "explicado", não como "consertado".)
4. **O motor ignorava 5 campos que a extração JÁ paga para produzir:** `qualidade_nhlbi` (48 critérios),
   `falhas_fatais`, `fracao_ejecao`, `relevancia_clinica` (o MCID inteiro) e `pre_clinico`.

**O que mudou (decisões do Dr. Eduardo em 01/Ago, LEI 6 — listadas antes de codar):**

- **Pré-clínico SAI da escala clínica** (`rota = FORA_DA_ESCALA_CLINICA`, `aplic = 0`, sem nota de
  rigor). Nenhum dos 6 instrumentos do NHLBI cobre animal/in vitro: dar aplicabilidade clínica a
  camundongo é erro de categoria. `nao_classificavel` → `REVISAO_HUMANA`: **o motor não chuta.**
- **Matriz de teto por desenho para etiologia/prognóstico/diagnóstico** (`_TETO_NAO_INTERVENCAO`):
  coorte prospectiva impecável 8 · retrospectiva 7 · caso-controle 7 · registro 7 · transversal 6 ·
  antes-depois 5 · série de casos 5.
- **Matriz explícita também para intervenção** (`_TETO_INTERVENCAO`), fechando o `else: 6` que dava
  6 para série de casos e transversal.
- **Falhas fatais F1–F8 → teto 4**, lidas de DUAS fontes: a lista que o extrator devolve **e** os
  limiares numéricos do bloco NHLBI (dropout diferencial ≥15 pp, perda >20 %, participação <50 %).
  Limiar medido não depende do humor do modelo. `null` = "não reporta" **não** acusa falha.
- **TETO DO RIGOR PELO DESENHO** (`_TETO_RIGOR_DESENHO`, aprovado 01/Ago, 15h). A `nota_estatistica`
  partia de **9 fixo** para tudo que não fosse RCT duplo-cego — uma SÉRIE DE CASOS recebia
  "Rigor 9/10". Não vazava para o assinante (o teto de aplicabilidade segura em 5), **mas o
  `analisador.py` injeta essa linha no contexto do redator com a instrução literal "use estes
  números, não invente outros"** — numa coorte (NAC 6) o "Rigor 9" ia parar DENTRO da perícia.
  Agora o rigor parte do desenho: RCT 10 · meta 9 · **coorte 8** · observacional ajustado / caso-controle 7 ·
  registro / transversal 6 · antes-depois / série de casos 5. O teto é aplicado **ANTES** dos
  delatores, para que eles continuem descendo a partir de um ponto de partida honesto.
  Efeito medido (fatos bons): série de casos **9 → 5** · transversal **9 → 6** · registro **9 → 6** ·
  antes-depois **9 → 5** · observacional ajustado **9 → 7**.
  ⚠️ **`coorte` é 8 e não 7 de propósito:** pus 7 na 1ª tentativa e o `teste_motor.py` REPROVOU,
  acusando o **Framingham** (gabarito do dono = 8). O piso 8 é da coorte PROSPECTIVA impecável;
  quem derruba a coorte fraca é o garbage-in (→5) e o teto retrospectivo (→7).
- **MCID — RELEVÂNCIA CLÍNICA VIRA TETO** (`teto_mcid`, aprovado 01/Ago, 15h30). O bloco
  `relevancia_clinica` era extraído — **pago em TODO artigo** — e jogado fora pelo motor.
  Agora capa: `significativo_mas_abaixo_do_mcid` → **6** · `nao_relevante` → **6** ·
  `incerto` → **7** · `robusto`/`provavel`/`nao_avaliavel` → não capa.
  *Significância estatística não é relevância clínica: p<0,001 num efeito abaixo da diferença mínima
  clinicamente importante não muda a conduta de ninguém.*
  ⚠️ **ESCOLHAS MINHAS, para o dono desfazer:** só o teto 6 do `abaixo_do_mcid` foi aprovado
  explicitamente. Pus `nao_relevante` no mesmo 6 (deixar sem teto seria incoerente — é pelo menos
  tão ruim) e `incerto` em 7 (efeito de relevância duvidosa não deveria "mudar a prática amanhã").
- **NHLBI CONTÁVEL — o rigor vira auditável** (`contagem_nhlbi`, aprovado 01/Ago, 15h30).
  Passa a ser possível MOSTRAR: *"cumpriu 6 dos 12 critérios do NHLBI para ensaio controlado;
  falhou em alocação sigilosa, cegamento do avaliador, ITT"*. É o que dá autoridade e o que o
  concorrente não tem. Faixas (proporção de critérios cumpridos entre os RESPONDIDOS →
  teto de rigor): ≥80 % → 10 · 60–79 % → 8 · 40–59 % → 6 · <40 % → 5.
  ⚠️ **DUAS ESCOLHAS MINHAS, explícitas:**
  (a) **a contagem só BAIXA, nunca SOBE.** Falhar critério prova fragilidade; cumprir critério de
      relato não prova que o estudo é bom. Assim a contagem não infla nota nenhuma nem quebra o gabarito.
  (b) **abaixo de 5 critérios respondidos a contagem NÃO capa** (`MIN_CRITERIOS_RESPONDIDOS`), senão
      todo artigo cujo extrator falou pouco seria punido por silêncio do modelo, não por má qualidade.

### 🔴 ONDE PARAMOS — 02/Ago/2026, fim do dia (LEIA ISTO PRIMEIRO NA PRÓXIMA SESSÃO)

**Decisão do Dr. Eduardo, depois de um plantão de 24h:** parar de reprocessar o acervo, **limpar o
Supabase e o corpus**, e voltar na semana seguinte com **50 a 100 artigos NOVOS**. Está certo, e a
medição do dia sustenta: acervo já processado não serve de prova (ver LEI 10 abaixo).

**O QUE FICOU PRONTO E COMMITADO** (`7a5040f`, no GitHub):

| | |
|---|---|
| 4 motores por tipo | ORIGINAL · META · DIRETRIZ (AGREE) · REVISÃO (rigor × utilidade) |
| 2 extratores novos | `analise_diretriz_prompt.md` · `analise_revisao_prompt.md` |
| Veredito ABERTO | o redator recebe os domínios medidos, não o número nu |
| Classificador | prompt v4 único (prova + produção), páginas 1-3, gpt-5.6-luna |
| Travas novas | DOI emprestado · BRIEF REPORT (F-02) · D-01 no mapa do PubMed · SEMINAR |
| Diário da rodada | CSV com camada, modelo, confiança e trecho citado |
| Provas | `teste_motor.py`, 30 baterias, função pura |
| Leis | LEI 8 (o classificador é a decisão) · LEI 9 (varrer todos os blocos) |

**O QUE FICOU ABERTO:**
1. **Limpar o Supabase** — `docs/LIMPEZA_02AGO.sql` (o Dr. Eduardo executa; o Claude nunca apaga).
2. **Limpar/arquivar o corpus** de `ARTIGOS/` — recomeçar com PDFs novos.
3. **Medir o prompt v4** — os 99,1 % eram do v3. O v4 mudou o texto e **não foi medido**.
4. **Tarefa #34** — fonte única do tipo para original/meta (hoje o prompt olha a pasta, o motor olha
   os fatos). Só depois que o classificador estiver provado.

**A PRIMEIRA COISA A FAZER NA VOLTA:** com os artigos novos, rodar a Chave 1 **em `--dry-run`**, ler
o diário, e só então deixar mover. Nunca soltar um lote sem olhar o CSV antes.

### LEI 10 (candidata) — REPROCESSAR O ACERVO NÃO É PROVA (02/Ago/2026)

**Palavras do Dr. Eduardo:** *"quando rodamos novamente um artigo que já tinha sido analisado de forma
errada e nomeado de forma errada, vai arrastar este erro porque o sistema inocente acredita no título
de uma análise errada anterior — por isso refazer o trabalho nunca é uma prova de fato do que tem
pela frente."*

**Verificado no código, e o mecanismo é mais preciso do que "acredita no título":**

1. **O erro não é arrastado — é REGENERADO.** A classificação NÃO lê o nome do arquivo (`_META_TITULO`
   olha o título do PubMed ou o texto do PDF). Mas o DOI emprestado continua **dentro do PDF**: mesma
   entrada → mesma resposta do PubMed → mesma pasta. Rodar de novo é a mesma conta dando o mesmo
   resultado, não um teste. "Errou de novo" NÃO distingue *o conserto falhou* de *o conserto não toca
   essa camada*.
2. **O corpus já foi mutado.** Os PDFs de hoje são a SAÍDA do sistema velho — renomeados, já triados.
   Medir a cascata contra eles mede as rodadas anteriores. (Prova: no diário de 02/Ago o `mapa de
   revista` acertou 49 de 49 — porque os artigos de revista mista já tinham saído em rodadas passadas.)
3. **O nome errado contamina o que vem DEPOIS.** `analisador.py`: `base = basename(pdf)` — e esse nome
   vira `{base}_fatos.json`, `_analise.md`, `_visual.png` e a ficha do site. A classificação não lê o
   nome; **todo o resto lê**.

**A CONSEQUÊNCIA:** prova é contra o **GABARITO**, com o **diário da cascata**, em PDFs **como chegam
da revista**. Nunca "rodar o acervo de novo e ver se melhorou".

**A MEDIÇÃO DA CASCATA INTEIRA (a 1ª que existiu — e que expôs o buraco):**

| camada | julgou | errou | acerto |
|---|---|---|---|
| A · mapa de revista | 49 | 0 | 100 % |
| B · rótulo do topo | 3 | 0 | 100 % |
| D · título = meta | 6 | 0 | 100 % |
| E · PubMed | 9 | 1 | 88,9 % |
| G · LLM | 38 | 5 | 86,8 % |

⚠️ **Este número NÃO vale como prova** — é justamente o caso da LEI 10. Mas ele revelou o que importa:
**o LLM decide só 31 % dos artigos** (114 de 369). Os 99,1 % medidos em 31/Jul cobriam UM TERÇO do
classificador; os outros 69 % (mapa, rótulo, título, PubMed) **nunca tinham sido medidos**.

### O VEREDITO ABERTO — 02/Ago/2026: a nota não é rótulo, é VOLANTE (medido)

**O experimento do Dr. Eduardo.** Ele rodou a MESMA revisão narrativa (Nature Rev Endocrinol,
"Causes and consequences of discontinuation of GLP1RAs or tirzepatide") duas vezes no comparativo,
com o MESMO modelo (claude-sonnet-5), mudando **só o número do veredito** colado no painel: 6/10 e 9/10.

**O que foi medido nas duas perícias:**

| | 6/10 | 9/10 |
|---|---|---|
| tamanho | 25.578 chars | **29.245** (+14%) |
| parágrafos | 38 | 48 |
| parágrafos **idênticos** entre as duas | **6** de 48 (86% mudou) | |
| números citados | 72 | 86 — **os 72 aparecem nos 86, zero contradição** |

O MESMO fato sustentou as duas notas opostas:
> **6/10:** *"os autores declaram um método de busca (PubMed…) — isso é positivo… mas não configura
> busca sistemática. A nota 6/10 reflete exatamente isso."*
> **9/10:** *"Dito isso, este texto faz melhor do que a média do gênero: os autores declaram método
> de busca (PubMed…)"*

**Três conclusões:**
1. A nota **não é um rótulo colado no fim** — é o volante. 86% da perícia gira em torno dela.
2. A **LEI DO NÚMERO aguentou**: nenhum número foi inventado nem contradito. O ancoramento mudou
   tom, estrutura e profundidade — não os fatos.
3. **A nota baixa fez o modelo trabalhar MENOS.** 14 números a mais na versão 9/10. O assinante de
   um artigo 6/10 receberia uma perícia mais pobre, não apenas um veredito mais duro.

Isto é a MEDIÇÃO da LEI 8: *"tudo fica internamente coerente e errado"*. **86%.**

**O CONSERTO (aprovado por ele em 02/Ago):** o redator deixa de receber o **número nu** e passa a
receber os **domínios medidos** que produziram o número:

```
Nota 7/10 | Rigor 7/10 | Muda conduta NÃO        ← contrato de MÁQUINA (não mexer no formato)

COMO O MOTOR CHEGOU NESTAS NOTAS (motor REVISAO) — a sua explicação das notas tem de
sair DESTES domínios medidos, não do número:
  RIGOR — dá para confiar? — média ponderada = 7/10
      viés de seleção                     5/10   × peso 0.30
      abrangência / escopo               10/10   × peso 0.20
      ...
```

- **Onde vive:** `notas_prototipo.veredito_completo(r)` — UM lugar só. O `analisador.py` (que monta o
  contexto do redator) e a Chave 9 leem daqui. Se cada um montasse a sua linha, seria mais uma fonte
  de verdade — o erro que a LEI 8 proíbe.
- ⚠️ **A PRIMEIRA LINHA É CONTRATO DE MÁQUINA:** `Nota N/10 | Rigor N/10 | Muda conduta X`, exatamente
  assim. É o que `conferir_veredito` lê por regex antes de gastar token. Rótulo bonito
  ("Rigor de desenvolvimento (AGREE)") vai nas linhas de baixo — nunca na primeira. Testado.
- **Prova:** `teste_veredito_aberto` — confere, nos 4 motores, que a regex do analisador pega a NOTA
  e não um domínio, que cada motor mostra os SEUS domínios com peso, e que pré-clínico continua
  saindo como "SEM NOTA" sem um `Nota N/10` que enganaria a trava.

### MOTOR DA DIRETRIZ (AGREE) — 02/Ago/2026, construído COM o Dr. Eduardo

**O buraco:** até hoje uma diretriz caía no motor do ARTIGO ORIGINAL, que lhe cobra randomização,
cegamento, I² e dropout. Nenhuma dessas coisas existe num consenso. Não havia o que recuperar: o
`src/prompts/prompt_guideline_v2.md` que sobreviveu do CardioDaily antigo está **intitulado** "Análise
de Revisões e Meta-Análises", não menciona AGREE e não tem bloco de notas. A diretriz nunca teve motor.

**As duas notas, numa diretriz:**
- **RIGOR** = como o documento foi **construído** (AGREE II). Não mede estatística; não há.
- **APLICABILIDADE** = quanto dá para **obedecer** — dominada pela base de evidência e pelo Brasil.

**RIGOR — 6 domínios ponderados** (pesos aprovados pelo Dr. Eduardo em 02/Ago). A forma espelha a
lógica que ele mesmo escreveu para a meta-análise: lá o maior peso era CONCLUSÕES (0,25) — *"foram
além do que a evidência permite?"*. Numa diretriz a pergunta idêntica é o vínculo recomendação↔evidência.

| domínio | peso | AGREE II |
|---|---|---|
| Vínculo recomendação ↔ evidência | **0,25** | 9, 12 |
| Busca e seleção da evidência | 0,20 | 7, 8 |
| Independência editorial | 0,20 | 22, 23 |
| Método de formular a recomendação (votação, quórum, risco×benefício) | 0,15 | 10, 11 |
| Revisão externa | 0,10 | 13 |
| Plano de atualização | 0,10 | 14 |

Os domínios AGREE 4 (clareza) e 5 (implementação) ficam **fora do rigor** de propósito: clareza de
escrita não é rigor de método; implementação entra na aplicabilidade (teto Brasil).

**APLICABILIDADE — os tetos** (`aplic = min` de todos):

| teto | régua |
|---|---|
| **tipo do documento** | diretriz com metodologia declarada 10 · sem metodologia 7 · statement/position paper 7 · sem classe nem nível 6 — **derivado dos fatos**, não perguntado ao modelo |
| **% nível C** | <30% → 10 · 30–49% → 8 · 50–69% → 7 · ≥70% → 6 |
| **Classe I em nível C** | ≥50% das Classe I apoiadas em nível C → **7** |
| **Brasil** | recomendações centrais sem ANVISA/CONITEC/exame disponível → 7 |

O teto do **% nível C** é a pergunta-assinatura do CardioDaily: *quanto disto é evidência e quanto é
opinião de especialista com cara de evidência?* O teto da **Classe I em nível C** é falha DIFERENTE, e
por isso ganhou teto próprio: o % geral diz "o campo não tem evidência"; este diz "a sociedade mandou
fazer assim mesmo". É onde mora o risco ao paciente.

**FALHA FATAL — só UMA.** O Dr. Eduardo aprovou G1 e **recusou explicitamente** G2, G3 e G4:

| | |
|---|---|
| **G1** (aprovada) | documento NORMATIVO sem classe nem nível — não é auditável → teto 4 |
| G2 · G3 · G4 (recusadas) | conflito não declarado · indústria sem política · sem busca e sem revisão externa |

As recusadas **não somem**: continuam derrubando o RIGOR pelos domínios `independencia` e
`revisao_externa`. Deixaram de reprovar; não deixaram de pesar. (Testado: `teste_diretriz_recusadas_ainda_pesam`.)

**ESCOLHAS MINHAS, registradas para o dono desfazer:**
1. **Classe I em nível C não desconta no rigor**, só capa a aplicabilidade. Se descontasse nos dois, o
   rigor cairia a 5 e — como `aplic = min(..., rigor)` — o teto 7 que ele aprovou viraria letra morta.
   Punir duas vezes o mesmo defeito revoga a decisão dele por via oblíqua.
2. **AGREE com menos de 3 itens extraídos → rigor 5 e o documento RETÉM** (a porta publica a partir de 6).
   LEI 8: na dúvida, revisão humana. Diretriz cujo método não deu para ler não vai ao assinante.
3. **Idade é FATO, nunca teto.** Ele não aprovou teto por idade — e o motor só pode usar o que está
   DENTRO do PDF ("já foi substituída pela versão nova" é fato de fora).
4. **`muda_conduta` = SIM se aplic ≥ 8.** Numa diretriz o documento inteiro é conduta; o gatilho é a nota.

**Onde vive:** `src/notas_prototipo.py` (`score_diretriz`, `dominios_diretriz`, `nota_diretriz`,
`teto_tipo_documento`, `teto_nivel_c`, `teto_classe_i_em_c`, `teto_brasil`, `FALHAS_FATAIS_DIRETRIZ`).
**Extrator próprio:** `src/analise_diretriz_prompt.md` + `SCHEMA_FATOS_DIRETRIZ` em `src/analise.py`
(21 itens AGREE + 12 campos de contagem de classe/nível). Perguntar randomização a um consenso é o
mesmo superficializar, uma camada antes da perícia.
**Prova:** `src/teste_motor.py` — 9 baterias novas; 20 no total, todas verdes, sem LLM e sem custo.

⚠️ **Estado (LEI 7):** "testei aqui" — o motor é função pura e roda de verdade. O **extrator** ainda não
rodou contra uma diretriz real, porque eu não alcanço a API. "RESOLVIDO" depende do Dr. Eduardo rodar
a Chave 9 numa diretriz da pasta GUIDELINES.

### MOTOR DA REVISÃO NARRATIVA — 02/Ago/2026, construído COM o Dr. Eduardo

**A semente veio dele:** `src/prompts/prompt_revisao_geral_v2.md`, Seção 4 — escopo · atualidade ·
viés de seleção · conflitos · lacunas reconhecidas. Cinco critérios, escritos por ele.

**⚠️ A CORREÇÃO QUE MUDOU O DESENHO INTEIRO.** Eu ia dar **teto 6** a toda revisão narrativa, com o
argumento "não é fonte de evidência primária". Ele recusou, e a frase dele virou a especificação:

> *"PODE CHEGAR A 10 — a revisão não tem graduação estatística. Ela se baseia em quanto ela me ajuda
> na prática, quanta informação aplicável ela entrega. Se fala por cima, ela tem nota baixa. Se ela
> explica que os silenciadores genéticos são extremamente eficientes — mas custam 750 mil reais no
> Brasil, e que isso dificulta sua implementação apesar das facilidades de uso e ter baixíssimos
> efeitos adversos — então ela tem uma nota muito alta."*

Num documento que **não é estudo**, "aplicabilidade clínica" quer dizer aplicabilidade MESMO —
utilidade prática entregue — e **não** posição na hierarquia de evidência. **Não existe teto por
categoria.** As 5 dimensões da utilidade saíram desse exemplo.

**AS DUAS NOTAS, com escalas diferentes e 5 domínios cada:**

| RIGOR — dá para confiar? | peso | UTILIDADE — entrega o quê? | peso |
|---|---|---|---|
| Viés de seleção | **0,30** | Conduta acionável (CONTAGEM) | **0,30** |
| Abrangência / escopo | 0,20 | Magnitude quantificada | 0,20 |
| Atualidade | 0,20 | **Custo e acesso no Brasil** | 0,20 |
| Conflitos de interesse | 0,15 | Segurança / efeitos adversos | 0,15 |
| Lacunas reconhecidas | 0,15 | Em quem NÃO usar | 0,15 |

Viés de seleção no topo pelas palavras dele no rascunho do redator: *"numa revisão narrativa, o
principal viés é a SELEÇÃO INVISÍVEL"*.

**`aplic = min(utilidade, rigor, teto_atualidade)`** — o rigor continua capando, o que preserva a
decisão dele de 01/Ago de não afrouxar a régua. Uma revisão riquíssima porém promocional e paga pela
indústria **não** chega a 10.

**A REGRA DURA DO INVISÍVEL:** o motor só pontua o que está **dentro do texto**. É PROIBIDO ao extrator
listar "ensaios que faltaram" — isso exige conhecimento de fora, e ele inventaria. Palavras dele no
rascunho: *"Não invente ausências."* O viés de seleção é medido por três coisas verificáveis:
afirmações centrais têm citação? · a revisão apresenta a evidência que a contraria? · ela distingue
RCT de observacional?

**TETO DA ATUALIDADE** (aprovado como teto próprio): referência mais recente com ≥5 anos → 6; ≥8 anos → 5.
*"Uma revisão de IC escrita antes dos ensaios de SGLT2 não é só fraca — ela ensina errado."*
⚠️ **REGISTRADO:** a atualidade pesa DUAS vezes (domínio 0,20 do rigor **e** teto próprio). Foi assim
que ele aprovou — as duas perguntas foram feitas em separado e ele disse sim às duas. Se ficar duro
demais, tirar o teto é apagar `_FAIXA_TETO_ATUALIDADE`.

**FALHAS FATAIS: NENHUMA.** Ele recusou R1 (promocional sem declarar conflito) e R2 (afirmações sem
citação). As duas continuam vivas dentro do rigor: `tom_promocional` derruba viés de seleção **e**
conflitos; `afirmacoes_sem_citacao="frequentes"` leva o viés de seleção a 3.

**Comportamento medido (motor puro, sem LLM):**

| cenário | nota | rigor | útil |
|---|---|---|---|
| silenciadores genéticos (o exemplo dele) | **10** | 10 | 10 |
| a mesma revisão, sem o custo no Brasil | 8 | 10 | 8 |
| a mesma revisão, "falando por cima" | 3 | 10 | 3 |
| riquíssima, mas promocional e paga pela indústria | 8 | 8 | 10 |
| riquíssima, mas de 2018 (antes dos SGLT2) | 5 | 8 | 10 |
| sem conflito declarado e afirmações sem fonte | 7 | 7 | 10 |

Repare na linha 3: **rigor 10 e utilidade 3.** São eixos independentes de propósito — uma revisão pode
ser impecavelmente honesta e ainda assim não entregar nada aplicável.

**Onde vive:** `src/notas_prototipo.py` (`score_revisao`, `dominios_revisao_rigor`,
`dominios_revisao_util`, `teto_atualidade`). **Extrator próprio:** `src/analise_revisao_prompt.md` +
`SCHEMA_FATOS_REVISAO` (19 fatos). **Prova:** 7 baterias novas no `teste_motor.py` — 27 no total.

⚠️ **Estado (LEI 7):** "testei aqui". O extrator nunca viu uma revisão real — depende do Dr. Eduardo
rodar a Chave 9 numa revisão da pasta REVISOES.

### AS DUAS NOTAS — 02/Ago/2026: EXPLICADO, NÃO CONSERTADO (decisão do dono)

**A pergunta:** por que aplicabilidade e rigor saem tão parecidos?

**A resposta é a própria régua.** O rigor está DENTRO do mínimo:
`aplic = min(rigor, teto_desenho, teto_externa, teto_falha_fatal, teto_MCID)`.
Logo (a) a aplicabilidade **nunca** excede o rigor, e (b) **coincide** com ele sempre que o rigor
for o gargalo. Não são duas medidas paralelas — o rigor é um dos candidatos a elo mais fraco.

**Medido em 6.000 artigos com mistura realista do acervo:**

| | |
|---|---|
| notas iguais | **55 %** (era **80 %** antes dos tetos de MCID e falha fatal) |
| notas diferentes | 44 %, distância média 1,8 ponto |

Quem decide a aplicabilidade: **rigor 55 % · desenho 27 % · falha fatal 7 % · MCID 7 % · externa 2 %**.
⚠️ Os tetos aprovados em 01/Ago **reduziram** a redundância de 80 % para 55 %. A trajetória é a certa.

**DECISÃO DO DR. EDUARDO (02/Ago):** MANTER como está.
Ele cogitou tornar o rigor independente, achando que isso deixaria a aplicabilidade **mais** exigente.
É o contrário: tirar o rigor do mínimo **revoga o PASSO 2 da LEI 0** (`CLAUDE.md`: "se
nota_trabalho_estatistico < 8 → aplicabilidade NÃO PODE ultrapassar 7") e **AFROUXA** a nota.
Medido: um RCT duplo-cego com **ITT falso + poucos eventos** passaria de **NAC 6 → NAC 10**.
Palavras dele: *"Não quero que afrouxe."* Item #18 fecha como **explicado**, não como consertado.

**Fica em aberto, se um dia ele quiser a aplicabilidade MAIS dura:** separar os delatores em duas
famílias (execução → rigor; desenho/relevância/extrapolação → aplicabilidade). Isso torna as notas
independentes na FONTE sem revogar o teto — mas não foi pedido e não foi feito.

**Validação por MUTAÇÃO — 16 sabotagens, 16 detecções.** Leva 3 (MCID/NHLBI): desligar o teto do
MCID · fazer `abaixo_do_mcid` parar de capar · desligar a contagem NHLBI · deixar o NHLBI SUBIR nota ·
capar mesmo sem dado suficiente · afrouxar as faixas. **O teste pegou as 6.**

**Validação por MUTAÇÃO (o que faz este teste valer):** sabotei o motor de **10 maneiras** —
6 na 1ª leva (voltar o bug do camundongo, voltar o 8 universal, desligar as falhas fatais, afrouxar
o limiar de dropout, igualar série de casos a coorte, tirar o teto estatístico da régua) e 4 na 2ª
(voltar o rigor 9 fixo, série de casos com rigor de coorte, derrubar o Framingham, aplicar o teto
DEPOIS dos delatores em vez de antes). **O teste pegou as 10.**

**Como se provou:** `python src/teste_motor.py` → APROVADO. E o teste foi validado por **mutação**:
sabotei o código de 6 maneiras (voltar o bug do camundongo, voltar o 8 universal, desligar as falhas
fatais, afrouxar o limiar de dropout, igualar série de casos a coorte, tirar o teto estatístico da
régua) e **o teste pegou as 6**. Teste que não falha quando o código quebra não é teste.

**Efeito na corrente:** nenhum. `aplic` continua `int` (0 na rota fora da escala), então as portas
`>= 6/7/8` do analisador seguem funcionando sem tratamento especial. O `analisador.py` passou a
escrever `SEM NOTA — <rota> | <motivo>` no canônico em vez de `Rigor None/10`.

**AS PORTAS (o que cada nota libera):**

| Nota | Entregáveis |
|---|---|
| ≤5 | **FICA retido** — só o canônico. Não publica. |
| ≥6 | canônico + ACRI + perícia (`.md`) + PDF |
| ≥7 | + **Visual Abstract** (mín. 50 KB) |
| ≥8 | + **áudio-anzol** (~3 min) + roteiro |

`_OK` só é escrito se **TODOS** os entregáveis da porta existirem e tiverem tamanho mínimo
(`_conferir_entregaveis`). Faltou um → erro → o artigo volta pra fila. É o buraco zero no nível do artigo.

---

### MÓDULO 3 · PUBLICADOR  (roda dentro do botão 2) — **o portão único do Supabase**
**Objetivo:** ser a ÚNICA porta de escrita na tabela `artigos` (LEI 5), e não deixar buraco passar.

| Programa | Faz o quê | Lê | Escreve |
|---|---|---|---|
| `publicador.py` | monta a ficha → **contrato** → **preflight de schema** → sobe mídia p/ Storage → upsert idempotente por `doc_id`. Default é **dry-run** (LEI DO CLONE): só sobe com `--publicar` | `outputs/STAGING/` | Supabase `artigos` + buckets |
| `contrato.py` | **o portão anti-buraco.** Recusa: campo narrativo vazio/raso, PDF ausente, nota ≥7 sem visual, nota ≥8 sem áudio, **nota <6 (fica retido)** | a ficha | `_REVISAR_publicacao.txt` se recusar |
| `ficha_site.py` | monta a ficha a partir do `_CANONICO.md` (frontmatter) + `_ACRI.txt` + arquivos da pasta. Determinístico, sem LLM | pasta do staging | dict com as colunas |

**Buckets do Storage:** `visual_abstracts` (PNG) · `podcasts` (MP3) · `resumos_pdf` (PDF).
Sobe sempre como **rascunho** (`publicar_no_site=false`) — quem libera é o Dr. Eduardo na Chave 3.

**🔴 PENDENTE (28/Jul/2026):** a ficha preenche 25 das 39 colunas. As outras 14 ficaram vazias porque o
Claude escolheu sozinho quais preencher (violação que originou a LEI 6). Aguarda decisão do dono.

---

### MÓDULO 4 · ADMINISTRADOR  (botão `3_Administrador.command`)
**Objetivo:** o Dr. Eduardo cura o que sai. Painel Streamlit.

| Programa | Faz o quê | Lê | Escreve |
|---|---|---|---|
| `administrador.py` | tabela enxuta (revista · data · nome · NAC · rigor · MCID) + links do PDF/áudio/visual para **ver · ouvir · aprovar com data de envio** | Supabase `artigos` | agenda de envio |

---

### MÓDULO 5 · ARQUIVADOR  (botão `4_Arquivador.command`)
**Objetivo:** arquivar, e ponto.

| Programa | Faz o quê | Lê | Escreve |
|---|---|---|---|
| `arquivador.py` | move as pastas do staging para `ARQUIVO/AAAA-MM`. **Nunca deleta.** Default dry-run; só move com `--arquivar` | `outputs/STAGING/` | `ARQUIVO/AAAA-MM/` |

---

### INFRAESTRUTURA (usada por todos os módulos)

| Programa | Faz o quê |
|---|---|
| `modelos.py` | **CONFIG CENTRAL DE MODELOS.** Trocar de modelo = mudar UMA linha aqui. Cadeias: `PROFUNDO` · `ESCRITA` · `EXTRACAO` · `RAPIDO` · `GUIDELINE_LONGO`. **É PROIBIDO hardcodar modelo em qualquer programa.** |
| `llm_client.py` | **CLIENTE UNIFICADO.** Executa a cadeia cross-provider (LEI DA EQUIVALÊNCIA), faz `gerar_json` com tool use, prompt caching, retry com backoff, e remove `temperature` onde o modelo de raciocínio rejeita |

### PROVA

| Programa | Faz o quê |
|---|---|
| `bateria.py` | **régua binária.** Roda N artigos pelo caminho REAL (inclusive o portão em dry-run) e responde só **APROVADO** (zero falha) ou **REPROVADO** com as causas agrupadas. Nunca reporta "progresso". `--continuar` reaproveita staging pronto |

---

### REGISTRO DE ALTERAÇÕES POR MÓDULO (LEI 2, item 5)
*Toda mudança em módulo entra aqui, com data e hora, na seção do módulo.*

**30/Jul/2026 14:50 · MÓDULO 1 (Classificador)** — `classificador_pubmed.extrair_doi`: adicionada trava de
parêntese DESBALANCEADO. Causa: `(doi:10.1056/NEJMoa0904327)` gravava o `)` dentro do `doc_id`, que é a
CHAVE do upsert — dois artigos entraram duplicados no Supabase. Preserva parêntese legítimo
(`10.1016/S0140-6736(01)05627-6`) por contagem de balanceamento. Testado aqui: 8/8 casos.

**30/Jul/2026 14:50 · MÓDULO 2 (Analisador)** — `pipeline.py`: ELIMINADA a extração de DOI duplicada
(regex crua que nunca recebeu as travas). Agora importa a função única do `classificador_pubmed`.
Uma fonte de DOI no sistema inteiro.

**30/Jul/2026 15:10 · MÓDULO 2 (Analisador)** — `redator_prompt.md`: (a) criada a **LEI DO NÚMERO** — todo
número tem que estar no texto do artigo; citar estudo-marco pelo NOME é permitido, citar NÚMERO de memória
é proibido (era a origem dos números inventados: o prompt mandava contextualizar "pelo seu conhecimento");
(b) trocada a ordem "escreva em PROSA densa" por **números em TABELA, crítica em prosa, limitações em lista**.
Status: **escrito, não rodado** — falta gerar um artigo e conferir.

**30/Jul/2026 15:10 · MÓDULO 3 (Publicador)** — `contrato.py`: passa a RECUSAR nota <6 (a porta existia na
regra mas não no código; um artigo nota 5 foi publicado em 25/Jul).

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

## PARTE 14 — BURACO ZERO: A CORRENTE MODULAR E A BATERIA DE PROVA (25/Jul/2026)

### O que aconteceu

Em 25/Jul/2026 a corrente nova (Classificador → Analisador → Publicador → Administrador → Arquivador)
rodou pela primeira vez ponta a ponta contra o Supabase real. O primeiro run expôs **74% de falha**
(66 pastas criadas, 17 completas). A causa não era um bug: era **método**. O sistema pedia JSON ao
modelo em texto livre e torcia para vir bem formado; cada malformação nova (vírgula sobrando,
caractere de controle, comentário) derrubava o artigo inteiro, e cada correção tapava um caso.

**Decisão do Dr. Eduardo (inegociável):** *"qualquer erro, por menor que seja, é inadmissível"* —
esta é a tradução operacional do BURACO ZERO. 40% de falha não é progresso: é sistema quebrado.

### A virada: corrigir a CLASSE, nunca o caso

| Antes (remendo) | Depois (estrutural) |
|---|---|
| Pedir JSON em texto e reparar o que vier quebrado | **Saída estruturada (tool use)**: a API OBRIGA o modelo a devolver o schema. JSON inválido deixa de ser POSSÍVEL |
| Teto de tokens dimensionado ignorando o *thinking* | Tetos com folga (perícia 16k, ACRI/roteiro 8k) + **piso de tamanho**: saída truncada é rejeitada, não publicada |
| Falha de rede matava o artigo | **Retry com backoff** em toda chamada LLM e no TTS |
| `_OK` escrito mesmo faltando entregável | `_conferir_entregaveis()`: só é "pronto" se TUDO da porta existir e tiver tamanho |
| Extração de DOI duplicada (uma endurecida, uma crua) | **Fonte única** `classificador_pubmed.extrair_doi` + trava de parêntese desbalanceado |

### A régua: `src/bateria.py`

Roda N artigos e responde **APROVADO** (zero falha) ou **REPROVADO** — nunca "progresso".
Roda o **portão real** (`publicador.processar_pasta` em dry-run = contrato + preflight de schema),
sem subir nada. Assim "APROVADO" significa **publicável**, não apenas "arquivo existe no staging".
Retomável com `--continuar`.

```
python src/bateria.py ARTIGOS/CLASSIFICADOS 50
```

### Resultado — BURACO ZERO ATINGIDO (25/Jul/2026)

| Prova | Resultado |
|---|---|
| 50 artigos originais | ✅ APROVADO 50/50 |
| Meta-análises | ✅ APROVADO 5/5 |
| Guidelines | ✅ APROVADO 5/5 |
| Revisões | ✅ APROVADO 5/5 |
| Editoriais | ✅ APROVADO 5/5 |
| LEI 0 (motor de rigor) | ✅ 7/7 fixtures — intacto, não tocado |

**70 artigos, zero falha.**

### Correções de raiz encontradas pela bateria

1. **`bateria.py`** — passou a rodar o Publicador em dry-run; antes dava APROVADO em artigo que o
   Publicador recusaria (o buraco que jogava artigo em `_RECUSADOS`).
2. **`ficha_site._frases`** — descartava frase densa >240 chars, zerando os bullets de artigo bem
   escrito → contrato recusava. Agora segmenta em cláusulas, nunca descarta.
3. **`voz_utils`** — TTS sem retry: queda de conexão no streaming derrubava qualquer artigo ≥8.
   Agora com retry/backoff. (Também: roteiro >4000 chars era truncado; agora é fatiado por frase.)
4. **`pipeline.py` + `analisador.py`** — eliminada a extração dupla no canônico: **uma extração,
   uma nota**. O canônico nunca diverge da porta.

### Riscos ABERTOS (registrados, fora do escopo da bateria)

- ⚠️ **Dois analisadores vivos**: `article_analyzer.py` (antigo) ainda roda todo dia às 07:00 via
  `distribuidor.py` no GitHub Actions, enquanto a corrente nova roda pela Chave 2. Ambos publicam no
  MESMO Supabase → risco de análise duplicada/divergente. **Decisão pendente do Dr. Eduardo:**
  aposentar o caminho antigo (distribuidor só distribui) ou mantê-los convivendo.
- ⚠️ **As duas notas vêm sempre idênticas** — nas 10 linhas reais do Supabase,
  `nota_aplicabilidade == nota_trabalho_estatistico` em 10/10 (7/7, 9/9, 5/5). Pela LEI 0 elas se
  relacionam, mas nunca divergirem sugere colapso das duas numa só. É o coração do produto: investigar.
- ⚠️ **Dados a limpar no banco**: 2 `doc_id` gravados com `)` (causa já corrigida) e 1 artigo nota 5
  publicado violando a porta (contrato agora barra <6).
- ⚠️ **`reprocessar_fila.py` órfão** — drena a FILA_ESPERA (ahead-of-print aguardando indexação no
  PubMed). Foi feito para rodar todo dia, mas não está ligado a botão nem ao Actions.

### Mapa dos arquivos

`MAPA_DO_SRC.md` (raiz do projeto) — quais dos 29 arquivos de `src/` formam a corrente (19),
quais rodam sozinhos pelo Actions, e quais são legado do caminho antigo.

---

## PARTE 15 — HISTÓRICO DE VERSÕES

| Versão | Data | Mudanças |
|---|---|---|
| 31.0 | 27/Jul/2026 | **Virada para CURADORIA MANUAL (ver PARTE 16).** O sistema não publica/envia artigo sozinho — só o Radar. Novo **Painel de Curadoria** (`src/painel_curadoria.py`, Chave 5): filtra por nota/revista/data/MCID/tema e escolhe o que sai no site, no grupo (WhatsApp/Telegram) e no Instagram. Actions `artigos-diarios` e `lista-semanal` desligadas do cron (só manual). **LEI 0:** motor determinístico agora vive em `notas_prototipo.py` (o `article_analyzer.py` foi aposentado — Lei 4); novo teto: retrospectivo observacional = 7. **Trava de inversão de fração de ejeção** no portão (`contrato.py`): HFpEF rotulado "ICFER" é recusado. Modelos convergidos para o cliente unificado (`llm_client.py`, Claude 5). |
| 30.0 | 25/Jul/2026 | **BURACO ZERO atingido (70 artigos, zero falha).** Corrente modular migrada do LAB para o FULL. Saída estruturada (tool use) na extração — JSON inválido virou impossível. Retry/backoff em todo LLM e no TTS. Piso de tamanho e conferência de entregáveis por porta. Preflight de schema no Publicador (mata o 400 mudo do Supabase). Fonte única de extração de DOI. Convergência de TODOS os modelos para `modelos.py` (grep limpo: zero modelo morto). `bateria.py` como régua binária. 4 botões (chaves) movidos do LAB para `CardioDaily_FULL/chaves/`; LAB arquivado em `archive/lab_snapshot_2026-07-25/`. |
| 29.0 | 04/Jun/2026 | Causa raiz dos 43 linhas: timeout Anthropic SDK (~2min padrão) — revisões grandes levam 5-6min. Corrigido para 1800s. Validação por chars (-2DP por tipo). Guidelines migrados para Gemini 3.1 Pro Preview (janela 1M, aguenta 882k chars em 66s). Reanálise 21 revisões corrompidas. |
| 28.0 | 03/Jun/2026 | Correção sistêmica de análises corrompidas; validação de qualidade no pipeline; detecção de corrupção no auditor; reanálise de 14 artigos nota≥7 com Gemini 3.5 Flash; podcast script migrado para Gemini 3.5 Flash (quota OpenAI zerada); 4 colunas criadas no Supabase (`muda_conduta text`, `por_que_importa`, `principais_recomendacoes`, `nota_metodologica numeric`) |
| 27.0 | 02/Jun/2026 | Troca `gemini-2.5-pro` → `gemini-3.5-flash` em originais/meta; troca `gpt-4o` → `gpt-4.1` no podcast; Claude Code padrão: Sonnet 4.6 + alto esforço |
| 26.0 | 31/Mai/2026 | MCID framework completo; campos novos; estado Supabase 31/Mai |
| 25.0 | 29/Mai/2026 | Padronização completa dos prompts — MCID obrigatório, placeholders proibidos |

---

## PARTE 16 — CURADORIA MANUAL: O DR. EDUARDO ESCOLHE O QUE SAI (27/Jul/2026)

### A virada

Até aqui o sistema **publicava e enviava sozinho** (distribuidor às 07:00, nota≥8, pacote completo).
Decisão do Dr. Eduardo em 27/Jul/2026: **isso acaba.** O médico não tem tempo de checar um a um, mas
também não aceita que o sistema mande qualquer coisa sem ele ver. A solução não é automação cega nem
revisão exaustiva — é um **painel de curadoria** onde ele filtra rápido e escolhe.

**Regra nova:** o sistema **NÃO publica no site, NÃO envia no grupo, NÃO posta em rede social por conta
própria.** A única coisa que continua automática e diária é o **Radar** (`radar.yml`).

### O Painel de Curadoria — `src/painel_curadoria.py` (Chave 5)

Streamlit local (`streamlit run src/painel_curadoria.py`, ou o botão `chaves/5_Painel_Curadoria.command`).
Lê a tabela `artigos` do Supabase e deixa:

- **Filtrar** por nota de aplicabilidade, revista, data de publicação, MCID (preenchido) e tema.
- **Publicar no site**: seta `publicar_no_site = true` (o site só mostra o que está `true`; o padrão de
  quem entra pela análise é `false` — fica na biblioteca esperando a curadoria).
- **Tirar do site**: volta `publicar_no_site = false`.
- **Enviar no grupo agora**: WhatsApp (Z-API) e/ou Telegram — só o artigo que ele mandar, na hora.
- **Instagram**: gera a legenda pronta + aponta o visual abstract (não há API do Instagram — ele posta).
- **Agenda da semana**: planeja o que sai em cada dia (`outputs/agenda_curadoria.json`) — planejamento,
  não gatilho: nada dispara sozinho a partir da agenda.

### O que foi desligado

| Antes (automático) | Agora |
|---|---|
| `.github/workflows/artigos-diarios.yml` (cron 07:00, envia nota≥8) | **só `workflow_dispatch`** (manual) |
| `.github/workflows/lista-semanal.yml` (cron segunda 07:30) | **só `workflow_dispatch`** (manual) |
| `radar.yml` | **mantido automático e diário** |
| `auditoria-semanal.yml` | mantido (auditoria interna, não publica nada) |

O `publicar_no_site = false` que o Publicador grava deixou de ser "rascunho a aprovar às cegas" e virou
o **estado natural da biblioteca**: o artigo existe, completo, esperando o Dr. Eduardo escolher no painel.

### Correções de integridade do mesmo dia (LEI 0 e terminologia)

Um visual abstract enviado ao grupo expôs dois erros do pipeline VELHO que motivaram consertos estruturais:

1. **LEI 0 — retrospectivo não pega o piso 8.** O motor determinístico (`notas_prototipo.py`) ganhou o
   fato `retrospectivo`: estudo observacional retrospectivo é capado em **7** (Nível C), nunca 8. O piso 8
   é só de coorte PROSPECTIVA (tipo Framingham). Gabarito segue 7/7.
2. **Trava de inversão de fração de ejeção no portão** (`contrato.py`). Novo fato `fracao_ejecao`
   (preservada/levemente_reduzida/reduzida/nao_se_aplica). Se o fenótipo é preservada e o texto usa a
   sigla ICFER/HFrEF (que significam REDUZIDA), o portão **RECUSA** — e vice-versa. A sigla tem sentido
   fixo (ICFE**R**=Reduzida, ICFE**P**=Preservada); glossário reforçado no redator/visual/áudio. Lock
   determinístico, não súplica ao modelo — mesmo princípio do Mermaid > HTML.

**Onde a LEI 0 vive hoje:** `src/notas_prototipo.py` (determinístico, 7 fixtures de gabarito). O
`article_analyzer.py` citado na PARTE 2 foi **aposentado** (Lei 4 — corrente modular). Os modelos também
convergiram: um cliente unificado (`src/llm_client.py`, cadeia cross-provider, Claude 5 na frente).
