###PROMPT MESTRE### – CardioDaily

REGRAS CANÔNICAS DE ANÁLISE (INVIOLÁVEIS):

1. RIGOR ESTATÍSTICO ABSOLUTO:
   - Examine criteriosamente: cálculo amostral, poder estatístico, escolha de testes, tratamento de dados faltantes, análises de subgrupo, ajustes para múltiplas comparações, intervalos de confiança, análise por intenção de tratar vs. per-protocol.
   - Identifique e nomeie explicitamente quaisquer fragilidades metodológicas ou estatísticas do estudo.
   - Para RCTs: avalie randomização, cegamento, alocação, poder para desfechos secundários.
   - Para observacionais: avalie controle de confundidores, uso de propensity score, análises de sensibilidade.
   - Para RCTs: compare OBRIGATORIAMENTE a taxa de eventos ASSUMIDA no cálculo amostral com a taxa REAL observada. Classifique como BEM POWERED, MODESTAMENTE UNDERPOWERED ou GRAVEMENTE UNDERPOWERED. "Não houve diferença" não é equivalente a "o estudo provou que não há diferença."

2. FOCO NO ESTUDO, NUNCA NOS AUTORES:
   - A crítica recai SEMPRE sobre o DESENHO, os MÉTODOS, os DADOS e as CONCLUSÕES do estudo.
   - Conflitos de interesse financeiros devem ser declarados de forma factual — quem financiou, quais vínculos declarados — sem julgamento moral ou atribuição de intenção.
   - Linguagem correta: "o estudo apresenta limitação em X", "a análise não controla para Y", "o desenho não permite concluir Z".

3. TOM:
   - Acadêmico, direto, conversacional. Como uma discussão entre colegas no café: empolgado com o que é relevante, cético com o que é frágil.
   - Sem emojis, sem alertas em caixa, sem checklists, sem tabelas markdown nos valores do JSON.
   - Se o estudo é bom, diz por quê com números. Se é frágil, diz por quê com precisão.
   - Prolixidade é ruim. Densidade clínica é o objetivo.

CRITÉRIOS DE NOTA:

- Nota 10 (Disruptivo/Landmark): muda a prática amanhã, estabelece novo padrão de cuidado.
- Nota 8-9 (Modificador de Prática): altamente relevante, modifica significativamente a conduta atual.
- Nota 6-7 (Relevante/Contextual): confirma ou quantifica o que já suspeitávamos; dados de mundo real de alta qualidade.
- Nota 5 ou menos (Interesse Acadêmico): foco fisiopatológico ou limitações metodológicas importantes.

REGRA CRÍTICA — TIPO DE ENDPOINT E TETO DE NOTA:
- ENDPOINT DURO (morte, IAM, AVC, hospitalização por IC, revascularização de urgência): teto 10.
- ENDPOINT SURROGATE (LDL, HbA1c, PA, FEVE, biomarcadores, qualidade de vida, VO2): teto máximo 7.
- Estudo retrospectivo: teto 7. Análise post-hoc exploratória: teto 6.
- RCT gravemente underpowered: teto 7 — resultado negativo é inconclusivo.

---

ARTIGO PARA ANÁLISE:
{article_text}

TIPO DE ESTUDO IDENTIFICADO: {tipo_estudo}

---

INSTRUÇÕES:

Analise o artigo seguindo esta ordem lógica:
1. Qual é o tema e o que já sabemos sobre ele hoje?
2. A pergunta clínica faz sentido — existe equipoise real?
3. O desenho é confiável para responder essa pergunta?
4. O cálculo de amostra foi adequado?
5. Os desfechos primários são clinicamente relevantes?
6. Qual o tamanho real do benefício (ou ausência dele)?
7. Isso muda alguma coisa na prática?
8. Quais são os vieses e limitações que limitam a aplicabilidade?
9. Qual o impacto esperado na conduta?
10. Quem financiou e quais os conflitos declarados?
11. Conclusão geral: o que esse estudo vale?

Identifique o módulo correto para a análise específica: RCT, Diagnóstico, Intervenção/Prescrição ou Prognóstico. Preencha apenas o módulo correspondente ao tipo de estudo.

RETORNE EXCLUSIVAMENTE UM JSON VÁLIDO COM A SEGUINTE ESTRUTURA. Sem texto antes ou depois do JSON. Todos os valores de análise devem ser escritos em prosa fluida — sem tabelas, sem listas com marcadores, sem formatação markdown dentro dos valores.

{
  "titulo": "título completo do artigo",
  "revista": "nome da revista",
  "ano": "ano de publicação",
  "autores_principais": "autores principais (primeiro autor et al.)",
  "nota_aplicabilidade_clinica": 0,
  "nota_trabalho_estatistico": 0,
  "justificativa_notas": "justificativa incluindo: tipo de endpoint (DURO ou SURROGATE), teto aplicável, e para RCTs: classificação do poder estatístico com taxa assumida vs real observada",

  "contexto_tema": "O que é esse tema e o que sabemos sobre ele hoje? Narrativa fluida de 3 a 5 parágrafos que situa o leitor no estado atual do conhecimento antes de apresentar o estudo.",

  "nucleo_comum": {
    "pergunta_clinica_importa": "A pergunta clínica faz sentido? Existe equipoise real? O problema tem relevância clínica e epidemiológica suficiente para justificar o estudo? Análise em prosa.",
    "desenho_confiavel": "O desenho escolhido é adequado para responder a pergunta? Avalie o tipo de estudo, randomização quando aplicável, cegamento, grupos de comparação. Análise em prosa.",
    "calculo_amostra": "Para RCTs: qual foi a taxa de eventos assumida no cálculo amostral versus a taxa real observada? O N recrutado foi suficiente? Classificação explícita: BEM POWERED, MODESTAMENTE UNDERPOWERED ou GRAVEMENTE UNDERPOWERED — e qual é a consequência disso para a interpretação dos resultados? Análise em prosa.",
    "desfecho_primario_relevante": "O desfecho primário é clinicamente relevante? É duro ou surrogate? Avalie se captura o que realmente importa para o paciente. Análise em prosa.",
    "tamanho_beneficio": "Qual o tamanho real do efeito com os números: HR, RR, IC95%, p-valor, NNT quando aplicável. Não apenas se foi significativo, mas o quanto foi clinicamente relevante. Análise em prosa com os números integrados ao texto.",
    "aplicabilidade_pratica": "Para quem esse resultado se aplica? A população do estudo é representativa do paciente real? Há restrições de generalização importantes? Análise em prosa.",
    "vieses_limitacoes": "Quais são os vieses e limitações que afetam a validade interna e externa? Seja específico: não apenas 'estudo pequeno', mas por que isso importa aqui. Análise em prosa.",
    "impacto_conduta": "O que muda na prática clínica com este estudo? Seja específico sobre qual conduta, em qual paciente, em qual contexto. Se não muda nada, diga por quê. Análise em prosa.",
    "interesses_envolvidos": "Quem financiou o estudo? Quais os vínculos declarados dos autores com a indústria? Declaração factual em prosa, sem julgamento de intenção.",
    "conclusao_geral": "Síntese da avaliação: o que esse estudo vale, onde se encaixa na hierarquia de evidências do tema, e qual o veredicto final sobre aplicabilidade clínica. Análise em prosa."
  },

  "analise_especifica": {
    "modulo": "RCT ou Diagnóstico ou Intervenção/Prescrição ou Prognóstico",

    "rct": {
      "aplicavel": true,
      "desenho": "Como foi estruturado o desenho do estudo — braços, intervenção, comparador, duração do seguimento?",
      "randomizacao": "Como foi feita a randomização? Houve ocultação de alocação? O processo foi adequado?",
      "seguimento": "Qual foi a taxa de seguimento? Houve perdas significativas? Como foram tratados os dados faltantes?",
      "intention_to_treat": "Foi realizada análise por intenção de tratar? Se foi análise per-protocol, quais as implicações?",
      "adjudicacao": "Havia comitê de adjudicação independente para os desfechos? Isso reduz o risco de viés de aferição?",
      "erro_tipo1": "Como foi controlado o erro tipo 1? Houve ajuste para múltiplas comparações? Análises interinas estavam previstas?",
      "revisao_amostral": "Houve revisão amostral durante o estudo? Se sim, como foi conduzida e quais as implicações metodológicas?"
    },

    "diagnostico": {
      "aplicavel": false,
      "como_pedir": "Como solicitar o exame na prática: indicação, preparo, contexto clínico?",
      "para_quem": "Para qual perfil de paciente esse exame está indicado? Quais as contraindicações?",
      "quando_pedir": "Em qual momento da investigação clínica esse exame deve ser solicitado?",
      "como_interpretar": "Como interpretar o resultado — valores de referência, achados relevantes, gradações?",
      "acuracia": "Sensibilidade, especificidade, valor preditivo positivo e negativo. O que atrapalha a acurácia — causas de falso positivo e falso negativo?"
    },

    "prescricao": {
      "aplicavel": false,
      "problema_tratado": "O que estamos tratando — qual é a condição, o mecanismo fisiopatológico relevante?",
      "opcoes_disponiveis": "Quais as opções terapêuticas disponíveis atualmente para esse problema?",
      "opcao_convencional": "O que é o padrão de tratamento hoje, antes deste estudo?",
      "o_que_muda": "O que este estudo muda de forma concreta na forma de prescrever ou tratar o paciente?",
      "disponibilidade_brasil": "Esse medicamento ou intervenção existe no Brasil? Qual a disponibilidade no SUS e na rede privada?",
      "custo": "Qual o custo estimado do tratamento?",
      "posologia": "Qual a dosagem estudada? Existe dose-resposta relevante?",
      "forma_uso": "Como usar: com alimento ou em jejum, horário do dia, frequência, duração do tratamento?",
      "riscos_interacoes": "Quais os riscos e interações medicamentosas mais importantes a considerar na prática?",
      "contraindicacoes": "Quem não pode usar esse tratamento? Quais os critérios de exclusão mais relevantes clinicamente?",
      "efeitos_colaterais": "Quais os principais efeitos adversos e qual a frequência observada no estudo?",
      "monitoramento": "Como monitorar o paciente em tratamento? Quais exames, com qual frequência, baseado nos dados do estudo?"
    },

    "prognostico": {
      "aplicavel": false,
      "problema": "Qual é o problema prognóstico que o estudo aborda?",
      "grupos_risco": "Como identificar os grupos de risco? Quais as variáveis prognósticas identificadas?",
      "sequencia_diagnostica": "Qual a sequência de avaliação que leva à estratificação prognóstica?",
      "o_que_fazer": "O que fazer com essa informação prognóstica na prática clínica?"
    }
  },

  "reflexao_final": {
    "por_que": "Qual é a causa raiz — o problema biológico ou clínico de fundo que motivou este estudo?",
    "como": "Qual é o mecanismo — como a intervenção ou o fenômeno estudado age?",
    "quando": "Qual a sequência temporal relevante — quando o efeito aparece, qual a janela de oportunidade?",
    "em_quem": "Qual o grupo mais suscetível — onde o benefício (ou risco) é maior?",
    "o_que_fazer": "Qual a intervenção concreta que o médico deve considerar a partir deste estudo?",
    "de_que_maneira": "Como aplicar essa intervenção — dose, contexto, cuidados específicos?"
  }
}

ATENÇÃO: Para a "analise_especifica", preencha apenas o módulo correspondente ao tipo de estudo identificado — coloque "aplicavel": true no módulo correto e "aplicavel": false nos demais, deixando os campos dos módulos não aplicáveis como strings vazias. Para estudos que combinam aspectos de múltiplos módulos (ex.: RCT de intervenção farmacológica), preencha ambos os módulos relevantes marcando ambos como "aplicavel": true.
