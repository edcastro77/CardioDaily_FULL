# CADERNO DE FALHAS — auditoria do sistema
## Aberto em 31/Jul/2026 · por ordem do Dr. Eduardo: "POR ENQUANTO SO ANOTA AS FALHAS - DEPOIS DISCUTIREMOS SOBRE ELAS"

## 🟢 RESULTADO DA PROVA — 31/Jul/2026, 22h30

| | Acurácia contra o gabarito (111 artigos) |
|---|---|
| Classificador em produção hoje | 102/111 = **91,9 %** |
| gpt-5.6-luna · prompt v1 | 102/111 = 91,9 % |
| claude-sonnet-5 · v1 | 100/111 = 90,1 % |
| claude-haiku-4-5 · v1 | 99/111 = 89,2 % |
| **gpt-5.6-luna · prompt v2** | **110/111 = 99,1 %** |
| gpt-5.6-luna · prompt v3 | *pendente — falta o Dr. Eduardo clicar* |

**O modelo mais barato do teste (US$ 0,20/M) é o mais preciso.** Custo em produção estimado:
**US$ 0,30/mês** para 400 artigos. Repetibilidade medida (3 rodadas): Haiku 99,1 % · Sonnet 98,2 % ·
Luna 96,4 %. **Custo total do experimento: US$ 6,20.**

**As duas mudanças que produziram o salto de 91,9 % → 99,1 %** (nenhuma delas é troca de modelo):
1. **Ler páginas 1–3 em vez da página 1.** No ESC o rótulo impresso sobe de 23 % → 92 %.
2. **Prompt com o vocabulário do CardioDaily**: case-based educacional = minirevisão; trava da
   revisão sistemática (só com PRISMA/bases/critérios declarados); rótulo impresso decide (v3).

**O que a prova DERRUBOU da minha proposta:** eu queria que o modelo virasse juiz e o mapa de
revista encolhesse. Errado. O mapa determinístico acerta 45/45 de graça no EHJ Supplements.
A arquitetura certa é: **mapa primeiro, modelo onde o mapa se cala.**

**Erros do placar que foram MEUS, não do sistema** (todos custaram tempo e um deles custou dinheiro):
- contei `ponto_de_vista` como erro quando o próprio `classificador_ouro.py` linha 234 já faz
  `ponto_de_vista → minirevisao`. Isso sozinho fez os modelos parecerem 8 pontos piores.
- zerei o CSV em vez de apagá-lo → o cabeçalho não foi escrito → placar quebrou.
- acrescentei uma coluna ao CAMPOS sem migrar o cabeçalho do arquivo em disco → as 111 linhas
  pagas ficaram deslocadas. **Regra que ficou: nunca anexar em CSV sem conferir o cabeçalho.**
- estimei US$ 1,50 para a rodada completa; custou US$ 6,11.

**Correção feita NO GABARITO** (o padrão-ouro também errou, e isso está registrado nele):
`Impact_of_Catheter_Ablation` e `Heart_Failure_with_Supranormal_EF` declaram PRISMA e bases
nomeadas → são `revisao_sistematica_meta_analise`, não `revisao_geral`. O modelo estava certo.

---

## 🔵 LINHA DE BASE MEDIDA — 31/Jul/2026, 111 artigos, gabarito do Dr. Eduardo

**O classificador de hoje acerta 104/111 = 93,7 %. São 7 erros (6,3 %).**
É o primeiro número real que o CardioDaily tem sobre o próprio classificador.
Fonte: `outputs/PROVA/gabarito.xlsx`, preenchido por conferência manual, artigo por artigo.

| O classificador pôs em | Era, segundo o Dr. Eduardo | Artigo |
|---|---|---|
| revisao_sistematica_meta_analise | **guideline** | AJKD "Incidence and Adverse Outcomes of AKD" |
| revisao_sistematica_meta_analise | revisao_geral | Thrombosis & Haemostasis — ABC Pathway |
| revisao_geral | artigo_original | ABC Cardiologia `e20250862` |
| revisao_geral | **guideline** | JACC — Antiplatelet Therapy in the Management… |
| revisao_geral | revisao_sistematica_meta_analise | Circulation — Cost-Effectiveness SGLT2i/ARNI |
| revisao_geral | **guideline** | JACC — Management of HF With Preserved EF |
| guideline | ponto_de_vista | JAMA — Dyslipidemia Evaluation and Management |

**Padrão:** 3 dos 7 são **guideline/statement rebaixado a revisão**. É a mesma falha medida em O-2:
o PubMed carimba *scientific statement* como `Review`, e o classificador obedece.

### O-9 · O ERRO DE NOME **CAUSA** O ERRO DE CLASSIFICAÇÃO (achado de 31/Jul)
O arquivo `2025-10-American_journal_of_kidn-Incidence_and_Adverse_Outcomes_of_Acute_Kidney_Disease…pdf`
**não é** esse artigo. Abrindo o PDF, a primeira página diz:

> `KDIGO 2026 CLINICAL PRACTICE GUIDELINE FOR ACUTE KIDNEY INJURY (AKI) AND ACUTE KIDNEY DISEASE (AKD) — PUBLIC REVIEW DRAFT`

É uma **diretriz KDIGO**, com o nome de uma meta-análise do AJKD. Classificado como META porque o
NOME dizia meta. **Um erro de nome virou um erro de classificação** — e o Dr. Eduardo contou os dois
separados (são 2 dos 11).

Verificado: o documento **não tem nenhum DOI** em nenhuma das suas páginas. Portanto o rename pelo
PubMed não poderia ter acontecido — e **eu não sei em que passo esse nome foi colado**, porque o
classificador não grava nada (ver O-1). Este arquivo é a prova viva de por que o registro de decisão
não é luxo.

---

> **Regra deste arquivo:** aqui só se ANOTA. Não se discute, não se propõe conserto, não se conserta.
> Cada falha entra com data/hora, o que o Dr. Eduardo disse (verbatim), e o que eu observei —
> sem diagnóstico. A discussão vem depois, quando ele mandar.

---

## F-01 · NOME ERRADO
- **Quando:** 31/Jul/2026
- **Verbatim do Dr. Eduardo:** "PRIMEIRA FALHA - NOME ERRADO"
- **Detalhe:** _pendente — a especificar na discussão_
- **Status:** ANOTADA

---

## F-02 a F-10 · ERROS DE CLASSIFICAÇÃO (lote de 31/Jul/2026)
- **Verbatim do Dr. Eduardo:**
  > "SEGUNDA FALHA - BRIEF REPORTING COMO ARTIGO ORIGINAL. TERCEIRO ERRO - EDITORIAL AVALIADO COMO
  > GUIDELINE, QUARTO ERRO - GUIDELINE CLASSIFICADO COMO META ANALISE, SEXTO ERRO - REVISAO
  > CLASSIFICADO COMO META ANALISE. SETIMO ERRO ART ORIGINAL CLASSIFICADO COMO REVISAO, OITAVO ERRO -
  > GUIDELINE CLASSIFICADO COMO REVISAO. NONO ERRO - ART ORIGINAL CLASSIFICADO COMO REVISAO. DECIMO
  > ERRO OUTRO GUIDELINNE CLASSSIFICADO COMO REVISAO."

| # | O QUE É (Dr. Eduardo) | ONDE O CLASSIFICADOR PÔS |
|---|---|---|
| F-02 | Brief Report | ARTIGOS_ORIGINAIS |
| F-03 | Editorial | GUIDELINES |
| F-04 | Guideline | META_ANALISES |
| F-05 | _(não informado — o Dr. Eduardo pulou o nº 5)_ | — |
| F-06 | Revisão | META_ANALISES |
| F-07 | Artigo original | REVISOES |
| F-08 | Guideline | REVISOES |
| F-09 | Artigo original | REVISOES |
| F-10 | Guideline | REVISOES |

**Arquivos que o Dr. Eduardo anexou como prova, e onde estão HOJE no disco** (só localização verificada,
sem atribuir qual arquivo é qual erro — isso se confirma na discussão):

| Arquivo | Pasta atual |
|---|---|
| `0066-782X-abc-123-6-e20250750.x98474.pdf` (ABC Cardiol) | ARTIGOS_ORIGINAIS |
| `2026-05-JAMA_cardiology-Coronary_Plaque_Progression_After_ADT…` | ARTIGOS_ORIGINAIS |
| `2026-07-JAMA-Dyslipidemia_Evaluation_and_Management.pdf` | GUIDELINES |
| `2025-10-AJKD-Incidence_and_Adverse_Outcomes_of_Acute_Kidney_Disease_SR_M…` | META_ANALISES |
| `2026-01-Thrombosis_and_haemostas-The_AF_Better_Care_Pathway…` | META_ANALISES |
| `0066-782X-abc-123-6-e20250862.x98474.pdf` (ABC Cardiol) | REVISOES |
| `2026-07-Circulation_Population_h-Cost_Effectiveness_of_SGLT2i_and_ARNI…` | REVISOES |

**Observação de fato colhida ao localizar os arquivos (não é diagnóstico, é o que está no disco):**
o arquivo `…Cost_Effectiveness_of_Sodium_Glucose…` existe em DUAS pastas ao mesmo tempo —
`CLASSIFICADOS/REVISOES/` **e** `CLASSIFICADOS/_PUBLICADOS/`. Ou seja: um artigo já publicado voltou
a aparecer na fila com outra classificação.

- **Status:** ANOTADAS
- **Nota de escopo:** os 7 PDFs anexados não cobrem os 9 erros listados (F-07 a F-10 exigem 4 arquivos
  em REVISOES; só 2 vieram). Faltam arquivos-prova para fechar o mapeamento.

---

## DENOMINADOR DA AUDITORIA — 31/Jul/2026

- **Verbatim do Dr. Eduardo:** "EM UMA ANALISE DE 62 ARTIGOS EU ENCONTREI 11 ERROS - 2 NOMES E
  9 CLASSIFICACOES ERRADAS."

| | |
|---|---|
| Artigos conferidos (por ele, um a um) | **62** |
| Erros totais | **11** → **17,7%** |
| — nome errado | **2** → 3,2% |
| — classificação errada | **9** → **14,5%** |

**Auditor:** Dr. Eduardo, conferência manual artigo por artigo. **Não** é medida do sistema —
a auditoria automática existente não apontou nenhum destes.

**Numeração:** ele numerou de 1 a 11. Descreveu explicitamente 1 (nome) e 2,3,4,6,7,8,9,10
(classificação). Ficaram sem descrição os nº **5** e **11** — e faltam justamente 1 erro de nome e
1 de classificação para fechar a conta. A atribuição de qual é qual fica para a discussão.

- **Status:** ANOTADO

---

## O QUE EU OLHEI NO CÓDIGO (31/Jul/2026) — fatos, não conserto

**Quem a Chave 1 chama:** `src/classificador_ouro.py` (não o `classificador_pubmed.py`, que só empresta
funções). Cascata real, na ordem em que decide:

`rede caiu → mapa de revista (DOI) → rótulo do topo → descarte → META pelo título → PubMed autoritativo
→ rótulo "original" → Sonnet lê a 1ª página → REVISAO_HUMANA`

### O-1 · O CLASSIFICADOR NÃO ESCREVE NADA
`classificar()` só faz `print`. Não grava CSV, não grava log, não grava por artigo o DOI, os pubtypes,
**qual camada decidiu** nem para onde foi. Fechou o terminal, a prova evaporou.
**Consequência direta:** dos 9 erros de classificação do Dr. Eduardo, **eu não consigo dizer qual camada
errou em cada um.** E é por isso que "a auditoria não fez nada" — não há o que auditar.

### O-2 · O PUBMED NÃO CLASSIFICA PARA O CARDIODAILY — CONSULTEI AGORA, DADO REAL
Puxei o PubMed ao vivo dos PDFs anexados:

| Artigo | O que o PubMed devolve | Para onde o código manda |
|---|---|---|
| Cost-Effectiveness SGLT2i/ARNI (Circulation) | `['Journal Article', 'Systematic Review']` | REVISOES |
| AHA Scientific Statement — Physical Activity/Obesity | `['Journal Article', 'Review']` | REVISOES |
| JACC CardioOnc — "…**Systematic Review and Meta-Analysis**" | `['Journal Article']` — **sem tipo** | cai pro Sonnet |
| ABC Cardiologia (`10.36660/abc…`), 2 arquivos | **não indexado** | cai pro Sonnet |
| DAPA-HF, PLATO, EXCEL, ISAR-REACT 5 | RCT/Multicenter — corretos | ARTIGOS_ORIGINAIS ✅ |

O classificador **obedeceu** ao PubMed. O PubMed cataloga para bibliotecário da NLM, não para curadoria
clínica: *scientific statement* da AHA é "Review"; estudo de custo-efetividade é "Systematic Review";
artigo fresco só tem "Journal Article".

### O-3 · DECISÃO EM CIMA DE FATIA DE TEXTO CRU DO PDF
- META é decidida por `_META_TITULO` procurando "meta-analys" no título do PubMed **ou nos primeiros
  250 caracteres do texto cru** — e isso roda **ANTES** do PubMed e do Sonnet. Qualquer artigo que
  mencione meta-análise na abertura vira META_ANALISES sem apelação.
- rótulo do topo = `texto[:600]`; Sonnet = `texto[:5000]`.
- A ordem do texto extraído de PDF em 2 colunas não é estável. Mesmo artigo, rodadas diferentes,
  fatia diferente → decisão diferente. Bate com o arquivo achado em DUAS pastas (F-02–F-10).

### O-4 · O RENAME DEPENDE DO PUBMED
`_novo_nome()` monta o nome com revista+título do PubMed. Sem registro no PubMed → **mantém o nome
troncho da editora** (ex.: `0066-782X-abc-123-6-e20250750.x98474.pdf`). No lote atual: 4 de 105
arquivos ficaram sem renome — 2 deles nas GUIDELINES.

### O-5 · IDADE DO CLASSIFICADOR
`classificador_ouro.py` nasceu em **09/Jul/2026**; o `classificador_pubmed.py` em **11/Jul/2026**.
Ou seja: **não é o programa que rodou um ano sem dar problema.** Este tem 3 semanas.

- **Status:** ANOTADO — sem conserto, sem proposta implementada.

---

## DECISÃO DO DONO · D-01 — REVISÃO SISTEMÁTICA = META-ANÁLISE
### 31/Jul/2026 · verbatim: "REVISAO SISTEMATICA é o mesmo que meta analise."

Revisão sistemática e meta-análise são **o mesmo tipo** para o CardioDaily: mesma trilha, mesma
pasta, mesmo prompt. Revisão **narrativa** continua sendo `revisao_geral`.

**Isto contradiz o que EU tinha escrito no código, sem nunca ter perguntado — violação da LEI 6.**
Está literalmente comentado em `classificador_pubmed.py`:

> `("revisao_sistematica_meta_analise", {"Meta-Analysis"}),  # só meta; revisão sistemática s/ meta = revisão`

**Onde essa decisão minha está enterrada hoje (5 lugares, nenhum consertado):**

| # | Arquivo | O que está escrito hoje |
|---|---|---|
| 1 | `classificador_pubmed.py` · `_PUBTYPE_PRIORITY` | `"Systematic Review"` está dentro de **`revisao_geral`** |
| 2 | `classificador_ouro.py` · `_META_TITULO` | regex só pega `meta[-\s]?analys` — não pega "systematic review" |
| 3 | `classificador_ouro.py` · `_PROMPT` (Sonnet) | "*Se o artigo parecer meta/revisão sistemática, escolha **revisao_geral***" |
| 4 | `classificador_ouro.py` · `_PROMPT` | "*revisao_geral: revisão narrativa, integrativa **OU sistemática***" |
| 5 | `classificador_pubmed.py` · `_LLM_PROMPT` | "*revisao_geral: revisão narrativa OU revisão sistemática SEM meta-análise*" |

**O que essa decisão sozinha já explica** (dado real puxado do PubMed em 31/Jul):
- `Biological, Radiological and Clinical Significance of Spotty Calcification` (JACC Imaging) —
  PubMed `['Systematic Review', 'Review']` → hoje foi pra REVISOES; pela decisão D-01 é META.

**O que ela NÃO resolve sozinha, e fica para discussão:**
- `Cost-Effectiveness of SGLT2i and ARNI` (Circulation) — PubMed carimba `Systematic Review`, mas o
  Dr. Eduardo classificou como **artigo original** (é um modelo de custo-efetividade). Aplicar D-01
  mandaria para META — continua errado. Aqui o rótulo do PubMed está errado para qualquer regra
  que confie nele.
- Nome da pasta `META_ANALISES` (o rótulo passa a cobrir os dois) — decisão pendente.

- **Status:** REGISTRADA · **NÃO IMPLEMENTADA**

---

## ESTADO REAL EM 31/Jul/2026, 
### Pergunta do Dr. Eduardo: "qual solução você implementou para parar de errar?"

**RESPOSTA: NENHUMA. Nada foi implementado. Zero linha alterada.**
Tudo neste documento é anotação e diagnóstico. O classificador de hoje é bit a bit o mesmo que
produziu os 11 erros. Se a Chave 1 for clicada agora, ela erra igual.

---

## O-6 · O PUBMED SERVE — MAS NÃO PARA SER JUIZ (dado real, 31/Jul)

Consultei o PubMed ao vivo em 20 PDFs. O padrão é nítido e **previsível**:

**ACERTOU (tipo específico e correto):**
DAPA-HF · PLATO · EXCEL · ISAR-REACT 5 · TRITON → `Randomized Controlled Trial` ✅ ·
JAMA Cardiology (ADT/placa) → `RCT + Multicenter` ✅ · JAMA Intern Med (aspirina/TEV) →
`Meta-Analysis + Systematic Review` ✅ · HF Supranormal EF (MDPI) → `Review` ✅ ·
Cardiology/HF/Interventional Clinics → `Review` ✅

**FALHOU — e sempre pelos MESMOS 4 motivos:**

| Motivo | Caso real | O que o PubMed disse |
|---|---|---|
| 1. Artigo recente ainda sem tipo | JACC CardioOnc "…Systematic Review and Meta-Analysis" | só `Journal Article` |
| 1. (idem) | NEJMoa2603649 — Rivaroxaban vs AAS (é RCT) | só `Journal Article` |
| 2. Revista não indexada | ABC Cardiologia `10.36660/abc…` ×2 | **inexistente no PubMed** |
| 3. Statement de sociedade | AHA Scientific Statement (Physical Activity) | `Review` (nunca `Guideline`) |
| 4. Estudo construído sobre literatura | Custo-efetividade SGLT2i/ARNI (é original) | `Systematic Review` |

**Conclusão de fato:** o PubMed é testemunha confiável para **"isto é ensaio/estudo com dados
primários?"**. É testemunha ruim para **"que tipo de não-ensaio é isto?"**.
No código de hoje ele é **JUIZ** — a linha `elif pubtypes and map_pubtype(pubtypes)` decide e
**nada depois dela pode contradizer**. Nem o Sonnet, que nem chega a ler o artigo.

## O-7 · O RÓTULO DO TOPO É CEGO EM PDF DE MDPI/Elsevier
No `…Supranormal_Ejection_Fraction` (J Clin Med), as 6 primeiras linhas que o `rotulo_topo()` lê são:
`Academic Editor: …` · `Received: …` · `Revised: …` · `Accepted: …` · `Published: …` · `Copyright: ©…`
Nenhuma palavra do artigo. E os 250 primeiros caracteres que a trava de META enxerga são a mesma
boilerplate de licença. **As travas determinísticas leem lixo editorial, não o artigo.**

## O-8 · TESTE PEDIDO PELO DR. EDUARDO: CIRCULATION E ESC (31/Jul, 158 PDFs reais do corpus)

Pergunta dele: o rótulo de seção ("ORIGINAL RESEARCH") é impresso como FIGURA, e por isso o
extrator não lê? Testado em **todo** o Circulation (82) e **todo** o ESC/EHJ (76) do corpus.

| | Circulation (82) | ESC / EHJ (76) |
|---|---|---|
| rótulo na **página 1** (como o sistema lê hoje) | **81 %** | **23 %** 🔴 |
| rótulo lendo **páginas 1–3** | 82 % | **92 %** ✅ |
| abstract/methods nas páginas 1–3 | **100 %** | 85 % |
| sem rótulo **E** sem abstract em 1–3 | **0** | **0** |

**Não é figura.** `img=0` em praticamente todos os ESC; no Circulation `img=1` é só o logo.
Os rótulos saem em texto puro: `ORIGINAL RESEARCH ARTICLE`, `AHA SCIENTIFIC STATEMENT`,
`CLINICAL PRACTICE GUIDELINE`, `STATE-OF-THE-ART`, `IN DEPTH`, `FRONTIERS`, `CLINICAL RESEARCH`,
`THE HEART OF THE MATTER`, `CONSENSUS`.

**A causa real do buraco do ESC:** o PDF do Oxford Academic tem **capa** na página 1 — título,
autores e "Downloaded from academic.oup.com". Só isso. Medido: os EHJ Supplements têm de
**177 a 470 caracteres** na página 1. O classificador lê essa capa e decide no escuro.
Nas MINIRREVISOES são **53 arquivos** nessa condição.

**Consequência para a memória do Gemini-visão:** naqueles ESC, um print da página 1 mostraria a
mesma capa. **Visão na página 1 não teria resolvido o ESC.** (Não tenho a evidência do sistema
antigo para explicar por que funcionava para o Dr. Eduardo — isso fica em aberto, não afirmo.)

**Conclusão medida:** ler **páginas 1–3** leva a leitura de rótulo de **54 % → 87 %** no conjunto,
e garante abstract/methods em 147 de 158. **Zero** arquivos ficam sem nada. Não é problema de
modelo nem de visão: é problema de **quanta página se lê**.

---
