# MÉTODO DE AVALIAÇÃO DE ESTUDOS CLÍNICOS — CardioDaily
## v1.0 · 30/Jul/2026 · síntese dos instrumentos formais enviados pelo Dr. Eduardo

> **O que este documento é:** a tradução dos instrumentos internacionais (NHLBI, CONSORT 2025,
> PRISMA 2020, STARD 2015, AGREE, SPIRIT 2025) para o que o CardioDaily precisa perguntar de cada
> artigo, por desenho, com **limiares numéricos** — não impressão.
>
> **O que ele NÃO é:** ainda não é decisão de produto. Como a nota é do Dr. Eduardo (LEI 6), as
> propostas de mapeamento nota↔critério estão marcadas **[PROPOSTA]** e aguardam aprovação.

---

## 1. A DESCOBERTA QUE MUDA A ARQUITETURA

Os instrumentos formais reconhecem **8 desenhos de estudo clínico**. Nenhum deles — nenhum —
cobre estudo **pré-clínico / animal / in vitro**.

Isso não é lacuna dos instrumentos: é a resposta. **Pré-clínico não é estudo clínico.** Não tem
aplicabilidade clínica para pontuar, porque não há paciente. Tentar dar nota de aplicabilidade a um
estudo em camundongo é um erro de categoria — foi exatamente o que produziu o **NAC 8/10** no artigo
RND3-ACAT1-PDHA1 (Circulation, 27/Jul/2026).

**Consequência para o sistema:** o pré-clínico não precisa de uma "nota melhor". Ele precisa de uma
**rota própria**, fora do motor de aplicabilidade clínica.

---

## 2. A TAXONOMIA: DESENHO → INSTRUMENTO

| Desenho | Qualidade (validade interna) | Relato (o que o artigo deve trazer) |
|---|---|---|
| **RCT / intervenção controlada** | NHLBI *Controlled Intervention* (14 critérios) | **CONSORT 2025** (26 itens) |
| **Revisão sistemática / meta-análise** | NHLBI *Systematic Reviews* (8 critérios) | **PRISMA 2020** |
| **Coorte / transversal** | NHLBI *Observational Cohort & Cross-Sectional* (14 critérios) | STROBE |
| **Caso-controle** | NHLBI *Case-Control* (12 critérios) | STROBE |
| **Antes-depois sem controle** | NHLBI *Before-After (Pre-Post)* (11 critérios) | — |
| **Série de casos** | NHLBI *Case Series* (9 critérios) | — |
| **Acurácia diagnóstica** | — | **STARD 2015** |
| **Diretriz / guideline** | — | **AGREE** |
| **Protocolo (ainda sem resultado)** | — | **SPIRIT 2025** |
| ⛔ **Pré-clínico / animal / in vitro** | **nenhum instrumento clínico se aplica** | ARRIVE (fora do escopo) |

---

## 3. OS CRITÉRIOS, POR DESENHO

### 3.1 RCT — NHLBI *Controlled Intervention* (14 critérios)

1. Descrito como randomizado?
2. **Método de randomização adequado** (sequência gerada ao acaso — não alternância, não data de admissão)?
3. **Alocação sigilosa** (envelope opaco numerado, central, computador não revelado)?
4. Participantes e provedores cegados?
5. **Avaliadores de desfecho cegados?**
6. Grupos similares no basal?
7. **Dropout total ≤ 20%?**
8. **Dropout DIFERENCIAL entre braços ≤ 15 pontos percentuais?**
9. Alta adesão ao protocolo?
10. Cointervenções evitadas ou similares?
11. Desfechos medidos com instrumento válido e do mesmo jeito nos dois braços?
12. **Poder ≥ 80% declarado para o desfecho primário?**
13. Desfechos e subgrupos **pré-especificados**?
14. **Análise por intenção de tratar (ITT)?**

**Limiares que o NHLBI trata como FALHA FATAL** (não é desconto — reprova):
- Dropout diferencial **≥ 15 pp** entre braços → *"serious potential for bias… fatal flaw, resulting in a poor quality rating"*.

### 3.2 Meta-análise / revisão sistemática — NHLBI (8 critérios)

1. Pergunta focada e bem formulada?
2. Critérios de elegibilidade **pré-definidos**?
3. Busca sistemática e abrangente?
4. Títulos/resumos/textos revisados em **duplicata independente**?
5. Qualidade de cada estudo incluído avaliada por **≥2 revisores** com método padrão?
6. Estudos incluídos listados com características e resultados?
7. **Viés de publicação avaliado?**
8. **Heterogeneidade avaliada?**

*(Os itens 7 e 8 são exatamente o que o `redator_prompt.md` atual NÃO pergunta — verificado em 30/Jul.)*

### 3.3 Coorte / transversal — NHLBI (14 critérios)

Destaques com limiar:
- **Taxa de participação dos elegíveis ≥ 50%?**
- **Perda de seguimento ≤ 20%?**
- Exposição medida **antes** do desfecho? *(o que separa coorte de transversal)*
- Exposição medida **mais de uma vez** ao longo do tempo?
- Avaliadores de desfecho cegados à exposição?
- **Confundidores medidos E ajustados?**
- Justificativa de tamanho amostral / poder?

### 3.4 Caso-controle — NHLBI (12 critérios)

- Controles da **mesma população** que originou os casos, **mesmo período**?
- Casos claramente definidos e diferenciados dos controles?
- Se <100% dos elegíveis, seleção **aleatória**?
- **Controles concorrentes?**
- Confirmado que a **exposição precedeu** a condição?
- Avaliadores de exposição **cegados** ao status caso/controle?
- Confundidores ajustados?

### 3.5 Antes-depois sem controle — NHLBI (11 critérios)

- Participantes representativos dos elegíveis?
- Todos os elegíveis foram incluídos?
- **Perda ≤ 20%?**
- Métodos estatísticos examinam a **mudança** pré→pós?
- **Série temporal interrompida** (múltiplas medidas antes e depois)?

### 3.6 Série de casos — NHLBI (9 critérios)

- **Casos consecutivos?** *(não consecutivo = viés de seleção)*
- Sujeitos comparáveis?
- Definição de caso explícita?
- Seguimento adequado?

### 3.7 Diretriz — AGREE
Escopo e finalidade · envolvimento das partes · **rigor do desenvolvimento** (busca sistemática,
critérios de evidência, revisão externa) · clareza · aplicabilidade · **independência editorial**.

### 3.8 Acurácia diagnóstica — STARD 2015
Padrão de referência · cegamento entre teste e padrão · **espectro de pacientes** ·
intervalo entre teste e referência · fluxo de participantes · **sensibilidade/especificidade com IC**.

---

## 4. AS FALHAS FATAIS (reprovam, não descontam)

Extraídas dos instrumentos, são as que os revisores tratam como desqualificantes:

| # | Falha | Onde |
|---|---|---|
| F1 | **Dropout diferencial ≥15 pp** entre braços | NHLBI RCT (explícito: *fatal flaw*) |
| F2 | Randomização **não é ao acaso** (alternância, data, prontuário) | NHLBI RCT Q2 |
| F3 | **Perda de seguimento >20%** sem análise de sensibilidade | NHLBI coorte/pré-pós |
| F4 | **Participação <50%** dos elegíveis | NHLBI coorte |
| F5 | Meta sem **heterogeneidade** nem **viés de publicação** avaliados | NHLBI meta Q7/Q8 |
| F6 | Caso-controle com controles de **população diferente** | NHLBI CC Q4 |
| F7 | Série de casos **não consecutiva** | NHLBI série Q3 |
| F8 | **Desfecho trocado** após o início (não pré-especificado) | NHLBI RCT Q13 · CONSORT 10 |

---

## 5. [PROPOSTA] COMO ISSO SE LIGA À NOTA DO CARDIODAILY

> **Precisa da sua aprovação — é decisão de produto (LEI 6).**

**5.1 — Pré-clínico sai do motor clínico.**
Ganha rota própria: sem NAC, sem perícia clínica, sem áudio. Se for publicado, é como
"ciência de fronteira", com rótulo explícito. Nunca compete com estudo clínico na mesma escala.

**5.2 — A nota de rigor passa a ser contável, não impressionista.**
Hoje `nota_estatistica` é uma escada de condições. Proposta: a nota de rigor deriva de
**quantos critérios do instrumento do desenho o artigo cumpre** — 14 para RCT, 8 para meta, etc.
Vira auditável: dá para mostrar ao assinante *quais* critérios falharam.

**5.3 — As falhas fatais viram teto duro.**
Qualquer F1–F8 presente → teto de rigor 4, independentemente do resto. É o "delator" do motor,
mas ancorado em instrumento internacional em vez de regra caseira.

**5.4 — O checklist do desenho entra na perícia.**
A seção de limitações deixa de ser prosa livre e passa a ser a **tabela do instrumento**:
critério · cumpre? · consequência. É o que dá autoridade — e é exatamente o que o concorrente
não tem.

---

## 6. O QUE ISSO CORRIGE, CONCRETAMENTE

| Problema observado | O que o método resolve |
|---|---|
| Pré-clínico com NAC 8 (Circulation, 27/Jul) | pré-clínico sai da escala clínica |
| Meta-análise periciada sem I² nem viés de publicação | NHLBI meta Q7/Q8 obrigatórios |
| Diretriz periciada sem classe de recomendação | AGREE entra na trilha de guideline |
| "Padrão de nota 8" em tudo | nota de rigor contável por critério |
| Schema com 7 desenhos que força o chute | taxonomia de 8 + rota pré-clínica + "não classificável" |

---

## 7. FONTES (arquivos enviados pelo Dr. Eduardo, 31/Jul/2026)

- **NHLBI Study Quality Assessment Tools** (NIH, 2013) — 6 ferramentas, 36 pág.
  *(enviado 6× com nomes diferentes: "COORTES OBSERVACIONAIS", "SERIE DE CASOS",
  "ESTUDOS CASO CONTROLE", "REVISAO SISTEMATICA", "ESTUDOS COM INVERSAO DE TT" — é o mesmo documento)*
- **CONSORT 2025** — checklist de 26 itens para RCT
- **SPIRIT 2025** — checklist para protocolos
- **PRISMA 2020** — checklist expandido para revisões sistemáticas
- **STARD 2015** — acurácia diagnóstica
- **AGREE Reporting Checklist** — diretrizes
