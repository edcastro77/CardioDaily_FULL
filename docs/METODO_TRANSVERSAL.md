# MÉTODO CARDIODAILY — LEITURA CRÍTICA DE ESTUDOS TRANSVERSAIS
## v1.0 · 02/Set/2026 · DITADO PELO DR. EDUARDO (não é proposta — é a régua dele)

> Origem: o caso REACT (NEJM, "Prevalence of Silent Atherosclerosis across Adult Life"),
> que o sistema avaliou com molde de RCT e NAC 6. O Dr. Eduardo leu o artigo, deu **nota
> mínima 8**, e ditou este método completo. Ele é a especificação do módulo transversal:
> prompt de extração, motor de nota e molde de perícia nascem DAQUI.

---

## A REGRA DO TOPO DA FOLHA

> *"Cross-sectional é extraordinário para responder 'O QUE ESTÁ ACONTECENDO?' e 'COM O QUE
> ISSO ESTÁ ASSOCIADO?'. É muito mais fraco para responder 'POR QUE ACONTECE?', 'O QUE
> ACONTECERÁ?' e, principalmente, 'O QUE EU DEVO FAZER PARA MUDAR O DESFECHO?'."*

A pergunta mais importante diante de qualquer transversal:
**o achado descreve uma realidade clínica relevante, ou está tentando provar algo que o
desenho não consegue provar?**

- Prevalência → pode mudar minha **percepção** do problema.
- Associação → pode levantar uma **hipótese** clínica.
- Causalidade → normalmente precisa de **evidência adicional** (coorte prospectiva, RCT).

E o fecho obrigatório de toda leitura — a FRASE-LIMITE:

> **"Este estudo permite que eu ____________, mas não permite que eu conclua ____________."**

---

## OS 4 NÍVEIS DE IMPACTO NA PRÁTICA (a espinha da nota)

| nível | o que o estudo entrega | exemplo | efeito na prática |
|---|---|---|---|
| 🟢 **1 — Muda a percepção clínica** | prevalência, carga de doença, under-diagnosis/under-treatment, guideline × prática | "só 22% dos que têm indicação recebem a terapia" | pode justificar auditar a própria prática AMANHÃ |
| 🟡 **2 — Gera vigilância clínica** | fenótipo com maior prevalência de um problema | deficiência de ferro em determinado fenótipo de IC | "procurar mais sistematicamente" — ainda não "tratar por causa disso" |
| 🟠 **3 — Gera hipótese, não conduta** | associação exposição↔desfecho | vitamina X ↔ menos FA | "hipótese interessante" — jamais prescrição |
| 🔴 **4 — Não deveria mudar tratamento** | o artigo conclui "X previne Y", "X reduz mortalidade", "devemos iniciar X" | — | pergunta de intervenção exige desenho longitudinal/RCT |

---

## O CHECKLIST DAS 10 PERGUNTAS

1. **A pergunta cabe no desenho?** "Quanto existe?" / "quem está associado a quê?" = ✅.
   "X causa Y" / "X aumenta o risco futuro de Y" com exposição e desfecho medidos
   simultaneamente = 🚩 (Oxford define o transversal pela simultaneidade).
2. **Quem entrou no estudo?** (STROBE: elegibilidade, fonte, seleção.) População geral ≠
   atenção primária ≠ ambulatório ≠ PS ≠ UTI ≠ centro de referência. "40% dos pacientes
   com IC têm deficiência de ferro" numa clínica terciária de IC avançada NÃO é o
   ambulatório. **A amostra é uma miniatura da população que eu trato?** (selection bias)
3. **Como foram selecionados?** Consecutiva / aleatória / conveniência / voluntários /
   banco administrativo / formulário online. Pesquisa online sobre sintomas → quem teve
   sintoma responde mais → prevalência aparente ≠ real.
4. **Exposição e desfecho medidos corretamente?** "Hipertensão" pode ser 6 definições
   diferentes. ICFEp ≠ dispneia + FEVE preservada. DAC ≠ qualquer placa. **Quanto mais
   importante o achado, mais rigorosa deve ser a definição do fenótipo.**
5. **Temporalidade?** O calcanhar de Aquiles. Sedentarismo↔IC: A) sed→IC, B) IC→sed,
   C) idade→ambos. **Pergunta de ouro: é biologicamente possível que o DESFECHO tenha
   provocado a EXPOSIÇÃO?** Se sim → muita cautela (reverse causality).
6. **Confundidores medidos e ajustados?** Não basta "adjusted analysis" — *adjusted for
   what?* 🚩 "Independentemente associado" ≠ fator causal independente. Modelo estatístico
   não transforma observacional em causal.
7. **Ajustaram DEMAIS?** Overadjustment (ajustar pela via causal: obesidade→PA→HVE,
   ajustou PA, apagou o efeito) e collider (introduz associação artificial). Muitas
   covariáveis ≠ modelo melhor; o que vale é a lógica causal a priori (idealmente DAG),
   não "entrou porque p<0,05".
8. **PR ou OR?** Com desfecho FREQUENTE, o OR exagera: prev. 40% vs 20% → PR 2,0, mas
   OR 2,67. Ler OR como "167% mais risco" é exagerar. **Em transversal, não usar a
   palavra "risco" automaticamente.**
9. **Precisão?** Nunca só o p. Estimativa + IC95%. PR 1,40 (1,02–1,92) ≠ PR 1,40
   (1,35–1,45). O intervalo contém efeitos clinicamente irrelevantes ou radicalmente
   diferentes?
10. **Significativo ou IMPORTANTE?** Com 100.000 indivíduos, PA 125,2 vs 124,3 dá
    p<0,001 — e talvez seja clinicamente irrelevante (CEBM: válido → importante →
    aplicável).

## AS 5 ARMADILHAS

11. **Neyman / survivor / prevalence-incidence bias** — o transversal vê quem está vivo
    e disponível; perde quem morreu rápido, sarou rápido, saiu.
12. **Missing data** — quem ficou sem dado? Missing não é aleatório (NT-proBNP dosado só
    nos graves → "NT-proBNP alto associa-se a pior condição" = viés de indicação).
13. **Multiplicidade** — 40 variáveis × 12 subgrupos × 5 desfechos → algo dá p<0,05 por
    acaso. Hipótese pré-especificada ou nascida olhando os dados? Exploratória é válida
    — só não pode ser vendida como confirmação.
14. **Análise de sensibilidade** — mudou a definição/premissa e o resultado sobrevive?
    Robusto sobrevive; frágil desaparece.
15. **Validade externa** — os pacientes do estudo se parecem com os meus? (idade, sexo,
    comorbidades, gravidade, cenário, geografia, tratamento contemporâneo, acesso.)

---

## A CASCATA DE AVALIAÇÃO

```
STROBE  → consigo entender o que fizeram?     (transparência de RELATO — bom STROBE ≠ bom estudo)
JBI     → consigo confiar no resultado?       (risco de viés / validade interna)
CEBM    → o efeito é importante?
Aplicabilidade → vale para os meus pacientes?
CONDUTA → muda / talvez mude / gera hipótese / não muda
```

## O TESTE DOS 60 SEGUNDOS

1. Qual foi a pergunta? 2. Quem foi estudado? 3. Como selecionados? 4. Como exposição e
desfecho foram definidos? 5. Exposição veio antes do desfecho? 6. Quais confundidores?
7. PR ou OR? 8. Efeito + IC95%? 9. Selection/missing/survivor bias? 10. Parecem com os
meus pacientes? 11. Associação, ou os autores insinuaram causalidade? 12. Qual exatamente
seria a mudança na minha prática? → e fechar com a FRASE-LIMITE.

---

## O CASO EXEMPLAR — REACT (a razão da nota ≥8, nas palavras dele)

O REACT é o transversal do NÍVEL 1 feito certo: pergunta de prevalência (não insinuou
causalidade), elegibilidade explícita (18–70 anos, sem doença aterosclerótica conhecida,
sem sintoma), avaliação sistemática multimodal (carótida + femoral + coronária por
angio-TC), estatística declarada (regressões com transformações apropriadas, ajuste por
país/idade/sexo, sem colinearidade) — *"desde que respeitem a metodologia para extração
do dado e declarem abertamente como o dado foi manipulado... têm informações extremamente
críticas e práticas para o meu dia a dia"*.

E o impacto no raciocínio — o uso BAYESIANO da prevalência contra o escore:

> *"Qual é a minha inferência de um baixo risco num paciente de 75 anos, onde 9 de cada
> 10 vão ter carga aterosclerótica alta? Se o score vem baixo risco, eu não vou confiar
> no score."* Prevalência alta + escore baixo → desconfie do escore. Prevalência baixa +
> escore concordante → chance de erro muito baixa.

Os números que mudam a percepção: placa coronariana em **~20% aos 30 anos, ~40% aos 45,
~90% aos 70** — em assintomáticos. Consequência prática: agressividade no controle de
fatores de risco acima dos 50–60 anos *"independente do que venha no teste de esteira"*,
porque o indivíduo de 60 anos tem 20 anos de horizonte para colher o benefício — um
impacto que nem os RCTs medem (o JUPITER tem 5 anos).

*"Não é todo estudo — é raro o transversal que traz essa qualidade. Mas quando acontece,
são significativos e não podem ser penalizados."* (Chagas numa tacada só; as necrópsias
do Braunwald; Framingham.)

---

## PRODUTO DERIVADO (pedido dele)

Transformar isto num **"Checklist CardioDaily de leitura crítica de Cross-Sectional — 1
página"** para os residentes: caixas SIM/NÃO/INCERTO, semáforo 🟢🟡🟠🔴 e campo final
obrigatório: *"Impacto na minha prática: muda conduta / muda rastreio / gera hipótese /
nenhum impacto"*.

## O QUE ISTO ESPECIFICA NO SISTEMA (implementação pendente de calibração)

| peça | o que muda |
|---|---|
| FATOS (extração) | campos novos do transversal: pergunta-cabe-no-desenho, fonte/método de amostragem, definição de fenótipo, risco de causalidade reversa, ajuste (e OVERajuste), PR vs OR com prevalência do desfecho, IC95%, multiplicidade, sensibilidade, missing, validade externa |
| MOTOR | nota = NÍVEL de impacto (1→alto … 4→baixo) × qualidade da execução (JBI); **sem teto categórico por ser transversal**; delatores próprios (OR vendido como risco; causalidade insinuada; amostra de conveniência; sem sensibilidade) |
| PERÍCIA | molde transversal = este checklist + semáforo + FRASE-LIMITE obrigatória — nunca mais o esqueleto de RCT com "não se aplica" |
| GABARITO | REACT = fixture nº 0, nota do dono ≥8 |
