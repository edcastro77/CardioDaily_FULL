# MÉTODO CARDIODAILY — DADOS DE MUNDO REAL (RWD/RWE)
## v1.0 · 04/Set/2026 · DITADO PELO DR. EDUARDO (caso: sacubitril/valsartana ABC, gabarito nº 11, nota 3)

> Par do METODO_TRANSVERSAL.md. Origem: a leitura do observacional do ABC
> ("Sacubitril/Valsartan versus Enalapril or Losartan at Maximum Doses" — o sistema deu 7,
> o dono deu **3**). Acompanha o checklist formal em
> **docs/RWD_Critical_Appraisal_Checklist.docx** (FDA 2024 · ICH M14 2026 · EMA DQF 2026 ·
> ENCePP r11 · STaRT-RWE · RECORD-PE · target-trial emulation), fornecido por ele.

---

## O TRIPÉ DO MUNDO REAL (as três perguntas antes de qualquer resultado)

1. **Como foi PADRONIZADA a extração dos dados?**
2. **Como foi ARMAZENADA a informação?**
3. **Como foi feita a ANÁLISE?**

*"A não ser que ele descreva como foi coletada a história, como foi organizado,
padronizado, prospectivamente — não é confiável."*

**A realidade brasileira, nas palavras dele:** não existe código padrão uniforme (não é o
UK Biobank); o médico anota o que o paciente REFERE, sem inquérito padronizado ("quantos
tiveram inquérito detalhado de álcool? nunca vi"); metformina virou "diabetes" no
prontuário sem critério. **Banco de dados brasileiro sem coleta prospectiva padronizada
descrita = informação pouquíssimo confiável.** Ler RWD nacional com MUITA cautela.

## O PRINCÍPIO-NÚCLEO (do checklist, e ele subscreve)

> *"O tamanho do banco não compensa um desenho causal ruim. Sofisticação estatística não
> resgata um desenho estruturalmente enviesado."* N grande torna o viés mais PRECISO,
> não mais válido.

## AS RÉGUAS QUE O CASO ABC ENSINOU (por que 3, e não o 7 do sistema)

| defeito | a régua que nasce dele |
|---|---|
| **>50% dos dados retrospectivos de prontuário** (931 prospectivos + 1.383 retrospectivos) | mistura retro+prospectivo sem padronização descrita → o tripé cai na primeira pergunta |
| **N≈900 analisados para uma pergunta que o PARADIGM respondeu com milhares** | *"para chegar a conclusão com 900 pacientes é surreal"* — não-inferioridade exigiria ~8–12 mil; estudo underpowered não responde, e conclusão de estudo que não pode responder não vale nota de resposta |
| **Só entra quem TOLERA dose máxima** | seleção = quem tolera dose plena está MENOS grave (confusão por indicação); o benefício líquido do sacubitril se entrega ao paciente MAIS grave (diâmetros diastólicos maiores) — o desenho seleciona exatamente quem menos se beneficiaria |
| **Eco sem padronização declarada** | desfecho/fenótipo sem uniformidade de medida → checklist B ☠6 (misclassification) |
| **412 excluídos por "dose submáxima"** | exclusão pós-exposição relacionada a prognóstico → ☠8/☠7 |

*"Eu teria parado de ler o estudo aqui. A conclusão dele não me interessa, porque o estudo
é muito mal feito... eu não aceitaria nem para publicação."* — **o direito de PARAR é
parte do método**: estudo que reprova na estrutura não ganha leitura da conclusão.

## O INSTRUMENTO FORMAL (docs/RWD_Critical_Appraisal_Checklist.docx)

- **Checklist A — 20 marcas de credibilidade**: pergunta causal precisa e estimando;
  lógica de target trial (time zero correto!); dados fit-for-purpose; comparador ativo
  substituível; new-user design; confundidores por conhecimento causal (não p-valor);
  balanço E positividade DEMONSTRADOS; exposição e desfecho validados; missing
  caracterizado; censura/competing risks; efeitos ABSOLUTOS; sensibilidade robusta;
  controles negativos/E-value; protocolo e SAP pré-especificados; code lists
  transparentes; conclusão do tamanho do desenho.
- **Checklist B — 10 erros FATAIS** (qualquer um → F): time zero quebrado/immortal time ·
  confusão por indicação · comparador inválido ("não-usuários") · prevalent-user/survivor
  bias · falha de positividade · misclassification crítica · ajuste por pós-exposição/
  collider · missing informativo ignorado · análise dirigida pelo resultado ·
  overclaim causal sem sensibilidade.
- **Triagem de 60 segundos** + **graduação A–F**:

| grau | significado | mapeamento CardioDaily (a calibrar com o dono) |
|---|---|---|
| A | target-trial alinhado, dados fit-for-purpose, robusto | teto alto do momento |
| B | bom desenho, 1–2 limitações que sobrevivem à sensibilidade | um degrau abaixo |
| C | gera hipótese; confusão residual importante | nota de hipótese (≤5?) |
| D | um problema estrutural maior | baixa |
| F | erro fatal irreparável | *"não usar para inferência causal"* — o caso ABC |

## O QUE ISTO ESPECIFICA NO SISTEMA (pendente de calibração da matriz)

| peça | o que muda |
|---|---|
| FATOS (extração RWD) | campos novos: fonte dos dados (prospectivo/retro/misto + %), coleta padronizada descrita?, time zero alinhado?, comparador (ativo/não-usuário), new-user?, balanço/overlap demonstrados?, validação de exposição/desfecho, poder para a pergunta (N necessário vs N analisado), exclusões pós-exposição, protocolo pré-especificado? |
| MOTOR | os 10 fatais viram FALHAS FATAIS do sub-motor RWD (como o GIGO da meta); grau A–F ancora o teto; underpowered para a pergunta = não-resposta, não resposta fraca |
| PERÍCIA | molde RWD = tripé + target-trial + os fatais + a licença de PARAR ("estrutura reprovada — conclusão não lida") |
| GABARITO | ABC sacubitril = fixture: sistema 7 → dono **3** (a maior divergência medida até agora, no sentido que a LEI 10 protege) |
