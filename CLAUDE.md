# CLAUDE.md - Instrucoes do Projeto CardioDaily
## Versão 3.0 | 30/Jul/2026
### Auditado linha a linha contra o disco em 30/Jul/2026 — todo caminho citado aqui foi verificado.

## LEIS INVIOLAVEIS DO PROJETO

Estas regras sao ABSOLUTAS e nao podem ser quebradas em nenhuma circunstancia:

### LEI 0: REGRA DE PONTUACAO DE ARTIGOS ORIGINAIS (PEDRA ANGULAR DO CARDIODAILY)

Esta e a regra mais importante do sistema de analise. Qualquer sugestao de nota que viole estas
regras deve ser imediatamente corrigida, independente do que o LLM retornou.

**PASSO 1 — TETO POR DESENHO (aplicar antes de qualquer outra avaliacao):**

| Nivel | Desenho | Teto NAC |
|-------|---------|----------|
| A | RCT com desfecho DURO + adjudicacao central + randomizacao adequada | 10 |
| B | RCT com desfecho surrogate validado, ou RCT com limitacoes (sem cegamento, perdas >10%) | 8 |
| C | Observacional COM grupo controle + propensity score ou multivariada robusta | 7 |
| D | Registro prospectivo SEM grupo controle, coorte sem adjudicacao central | 6 |
| E | Serie de casos, relato de caso, estudo transversal, opiniao de especialista | 5 |

**ATENCAO:** "multicentrico", "prospectivo" e "nacional" NAO elevam o nivel. O que define o nivel
e a presenca de: (1) randomizacao, (2) grupo controle, (3) adjudicacao central de desfechos.

**PASSO 2 — TETO ESTATISTICO (aplicar apos passo 1):**
- Se nota_trabalho_estatistico < 8 → nota_aplicabilidade_clinica NAO PODE ultrapassar 7
- O teto final e o MENOR entre o teto do desenho e o teto estatistico

**EXEMPLOS CORRETOS:**
- Registro prospectivo nacional N=190, sem randomizacao, sem controle, sem adjudicacao → Nivel D → NAC maximo 6
- RCT com desfecho FEVE como primario → Nivel B → NAC maximo 8
- Coorte com propensity score bem conduzida → Nivel C → NAC maximo 7
- RCT MORTALIDADE bem conduzido → Nivel A → NAC pode ser 10

**EXEMPLOS PROIBIDOS:**
- Registro sem controle recebendo NAC 9 → ERRADO (teto e 6)
- Observacional sem propensity score recebendo NAC 8 → ERRADO (teto e 6 ou 7)
- Estudo observacional recebendo NAC 9 → ERRADO (estudos observacionais estao excluidos de NAC >= 9)

**CRITERIOS DEFINITIVOS DE NOTA (detalhamento completo):**

| Nota | Classificacao | Definicao resumida | Tipos tipicos |
|------|--------------|-------------------|---------------|
| 10 | Disruptivo/Landmark | Muda pratica amanha; novo padrao de cuidado | Grande RCT multicentrico, desfecho duro |
| 9 | Fortemente Modificador | Altera conduta padrao; prática deve mudar | RCT alta qualidade; meta-analise rede de RCTs. Observacionais EXCLUIDOS |
| 8 | Potencialmente Modificador | Influencia mudanca de pratica, sem mandato | RCT com limitacoes, grandes prospectivos, meta-analises robustas |
| 7 | Altamente Relevante | TETO retrospectivos; confirma e quantifica | Grandes registros com propensity score |
| 6 | Relevante/Contextual | Util, pouca forca para mudar conduta | Coortes retrospectivas, registros de centro unico |
| 5 | Gerador de Hipoteses | Bem conduzido, mas nao clinicamente acionavel | Transversais, pequenas series, post-hoc |
| ≤4 | Academico/Falho | Falhas metodologicas graves ou pre-clinico | Relato de caso, estudos pre-clinicos |

**ONDE A LEI 0 VIVE HOJE (atualizado 30/Jul/2026):** em **`src/notas_prototipo.py`** — o MOTOR DE RIGOR.
A nota é **determinística**: recebe os FATOS extraídos e aplica `min(teto_desenho, teto_externa, nota_estatistica)`.
Não é um prompt, não depende do humor do modelo, e o LLM **não pode** contrariá-la.

- `teto_desenho()` = REGRA 0 (teto por tipo de pergunta/desenho) · `teto_externa()` = teto 7 se não-extrapolável
- Os FATOS vêm de `src/analise.py` (saída estruturada / tool use) usando `src/analise_prompt.md`

⚠️ **`src/prompts/prompt_artigo_original_v2.md` NÃO é mais usado pela corrente.** Aqueles arquivos pertencem
ao `prompts_config_v2.py`, que só o **analisador ANTIGO** (`article_analyzer.py`) lê — e lá o oficial já é o v3.
A corrente nova usa 5 prompts, todos na raiz de `src/`: `analise_prompt.md` (fatos), `redator_prompt.md`
(perícia), `acri_prompt.md` (card), `script_audio_prompt.md` (áudio), `gancho_abertura_prompt.md`.

---

### LEI 8: O CLASSIFICADOR É A DECISÃO — NÃO É UMA ETIQUETA (02/Ago/2026)

**Palavras do Dr. Eduardo:** *"por este motivo que o classificador não pode errar — se ele colocar um
trabalho na caixa errada, vamos usar o motor errado, o prompt errado, análise e notas erradas...
estas ações não têm como ficar para o analisador decidir."*

Até 02/Ago o tipo do documento parecia um detalhe de organização de pasta. **Não é.** Desde que cada
tipo ganhou prompt próprio (01/Ago) e motor de notas próprio (02/Ago), a decisão do classificador
**determina toda a cadeia**:

| Se o classificador erra a caixa | então |
|---|---|
| pasta errada | **PROMPT errado** — cobra randomização de uma diretriz, ou PRISMA de um RCT |
| tipo errado | **MOTOR errado** — pondera 6 domínios de meta num artigo original |
| motor errado | **NOTAS erradas** — as duas, aplicabilidade e rigor |
| notas erradas | **PERÍCIA errada** — o redator recebe o veredito e escreve em cima dele |
| tudo errado | **publica** — e nenhuma trava a jusante pega, porque cada peça está "coerente" |

**Consequências que passam a valer:**

1. **O tipo é decidido UMA vez, no classificador, e todo o resto OBEDECE.** É proibido cada etapa
   decidir o tipo por conta própria — foi assim que nasceu a incoerência de 02/Ago, em que a escolha
   do prompt olhava a PASTA e a escolha do motor olhava o campo `desenho` dos FATOS. Duas fontes de
   verdade para a mesma pergunta é a definição de buraco.
2. **Erro de classificação não é erro pequeno.** Não existe "o analisador conserta depois". Não existe
   "o modelo percebe". A jusante ninguém percebe: tudo fica internamente coerente e errado.
3. **O classificador tem que provar acerto ANTES de qualquer lote.** Padrão-ouro conferido a mão,
   medição, e nada sobe sem bater. Medido em 31/Jul: produção 91,9 % · corrigido 99,1 %.
4. **Na dúvida, REVISÃO HUMANA.** Classificar errado custa mais caro que não classificar. O
   `nao_classificavel` e a pasta `REVISAO_HUMANA` existem para isso e devem ser usados sem vergonha.

### LEI 9: UMA REGRA MORA EM VÁRIOS BLOCOS — VARRA TODOS ANTES DE MUDAR (02/Ago/2026)

**Palavras do Dr. Eduardo:** *"o que eu pedi para você fazer parece que é um lixo... cagou e andou
para um pedido expresso meu! 'pode', 'não sei', 'pode talvez'... mas NÃO PODE. Resolvi e não fez nada.
Você pode incluir em suas regras que **antes de tomar uma decisão que afeta todo o sistema, você
deveria checar TODOS OS PONTOS que podem afetar esta decisão — são blocos distintos**. Aumenta o
trabalho mas não é tão complexo assim."*

**A REGRA:** quando o Dr. Eduardo decide algo que é uma REGRA DE NEGÓCIO (não um conserto local), essa
regra quase nunca vive num arquivo só. Antes de mexer, o Claude **VARRE TODOS OS BLOCOS** onde ela pode
estar escrita, **CONSERTA EM TODOS**, e **MOSTRA A VARREDURA** — arquivo por arquivo, inclusive os que
estavam certos. Consertar onde se achou e seguir em frente é o mesmo que não consertar: o bloco que
sobrou continua rodando, e roda **em silêncio**.

**OS BLOCOS DO CARDIODAILY** (a lista que tem de ser varrida — cada um decide sozinho):

| # | bloco | onde |
|---|---|---|
| 1 | **Classificador — cascata** | `classificador_ouro.py`: mapa de revista → rótulo do topo → descarte → título → **mapa de pubtype do PubMed** → rótulo original → LLM. **Cada camada decide sozinha e as de cima calam as de baixo.** |
| 2 | **Classificador — mapa do PubMed** | `classificador_pubmed.py` · `_PUBTYPE_PRIORITY` |
| 3 | **Classificador — prompt** | `classificador_prompt.py` (v3) |
| 4 | **Extração** | `analise_prompt.md` · `analise_diretriz_prompt.md` · `analise_revisao_prompt.md` + os SCHEMAS em `analise.py` |
| 5 | **Motor de notas** | `notas_prototipo.py` (4 motores: ORIGINAL · META · DIRETRIZ · REVISAO) |
| 6 | **Escolha do prompt / do tipo** | `analisador.py`: `tipo_do_documento`, `escolher_prompt`, cache de fatos |
| 7 | **Redator e derivados** | `redator_*_prompt.md` (4) · `acri_prompt.md` · `script_audio_prompt.md` · `gancho_abertura_prompt.md` |
| 8 | **Portão do Supabase** | `contrato.py` · `publicador.py` · `ficha_site.py` |
| 9 | **Prova** | `teste_motor.py` · `prova_classificador.py` · `placar.py` |
| 10 | **Documentação** | `CLAUDE.md` · `docs/CADERNO_EXECUCAO.md` |

**COMO SE PROVA QUE FOI FEITO** (sem isto, não foi feito):
1. Antes de codar, o Claude **escreve a lista dos blocos** onde a regra PODE estar.
2. Faz a varredura de verdade (grep/leitura) e **mostra o resultado de CADA bloco** — inclusive
   "bloco 7: não tem essa regra, ok". O que não aparece na lista, não foi olhado.
3. Onde a regra puder ser expressa em código, cria uma **trava de função pura** no `teste_motor.py`,
   para o portão da Chave 8 recusar o retorno dela.

**O CASO QUE ORIGINOU A LEI (02/Ago/2026) — medido, não suposto.**
Em 31/Jul o Dr. Eduardo decidiu a **D-01: "revisão sistemática É meta-análise, mesma trilha"**.
Essa regra vivia em **TRÊS blocos**:

| bloco | o que dizia | quando foi corrigido |
|---|---|---|
| prompt da prova (3) | v3, correto | 31/Jul |
| prompt de produção (1) | *"se parecer meta/revisão sistemática, escolha revisao_geral"* | **02/Ago** |
| **mapa do PubMed (2)** | `("revisao_geral", {"Review", "Systematic Review"})` | **02/Ago, tarde — só depois do estrago** |

O Claude achou a contradição no PROMPT, consertou ali, **declarou o classificador resolvido**, mediu
99,1 % — e o número era verdadeiro, mas media o LLM sozinho. O bloco 2 decide **antes** do LLM. Na
produção, o LLM sequer era chamado para esses artigos. Resultado: o Dr. Eduardo rodou 112 artigos e
os erros voltaram idênticos — revisões sistemáticas em REVISOES, três Scientific Statements em REVISOES.

**Agravante que a lei também proíbe:** o Claude escreveu, com todas as letras, que "a cascata + LLM
nunca rodaram juntos" e **mesmo assim disse "pode soltar"**. Enunciar o risco não é o mesmo que tratá-lo.
Se o Claude sabe nomear o que não foi medido, ele **para** — não mede pela metade e libera.

### LEI 10: O CARDIODAILY PUBLICA MENOS E REPROVA MAIS — E ISSO É A REGRA (04/Ago/2026)

**Palavras do Dr. Eduardo, quando eu avisei que a régua nova derrubaria metade da fila:**
*"CardioDaily publica muito menos e reprova muito mais — ESTA É A REGRA!"*

O CardioDaily NÃO é um serviço de resumo. É um serviço de **filtro**. O valor que ele vende é
dizer *"olhei 24 e 12 não prestam"* — e ter razão. Um sistema que aprova quase tudo não vale
assinatura nenhuma: o cardiologista já tem excesso de artigo, o que falta é quem separe.

**A ESCADA DE AVALIAÇÃO CRÍTICA DE META-ANÁLISES** (especificação dele, para ele e para os
residentes do Hospital Rio Doce). Vale para TODAS as metas, inclusive **rede** e **IPD**:

| Degrau | O que olha | Efeito |
|---|---|---|
| 1 · registro | PROSPERO, PRISMA, PICO(TS) | desconto no domínio `busca` |
| 2 · qualidade de entrada | **misturou ECR com observacional no primário?** | **FATAL — teto 5** |
| 3 · heterogeneidade | I²>50% sem sensibilidade/subgrupo/meta-regressão | teto 6 ("em cima do muro") |
| 4 · viés de publicação | **perdeu significância no Trim-and-Fill?** | **FATAL — teto 5** |
| 5 · utilidade clínica | desfecho SUBSTITUTO (Lp(a), GLS, FEVE) | teto 8 |

**A ESCALA DE APLICABILIDADE** — os 4 crivos do algoritmo de beira do leito GRADUAM a nota
(não apenas capam). Números ditados por ele, um a um:

| crivos cumpridos | nota máxima |
|---|---|
| 4/4 | **9 ou 10** (LOE A · muda conduta · TSA cruzada autoriza o 10) |
| 3/4 | 8 |
| 2/4 | 6 |
| 1/4 | 5 |
| 0/4 | 4 |

Os crivos: (1) só ECR de baixo risco de viés · (2) I²<25% ou alto porém isolado e explicado ·
(3) robusto ao Trim-and-Fill · (4) desfecho DURO. **O NNT<25 VALORIZA, mas NÃO é régua.**
Repare no salto 2→3 (6 para 8) e na ausência do 7: é de propósito.

**A REGRA MAIS IMPORTANTE DE TODAS — BICONDICIONAL:**
*"Toda nota 9 e 10 muda conduta! Se muda a conduta é 9 ou 10, e se é 9 ou 10 é porque muda
conduta."* Nota e `muda_conduta` são o MESMO fato dito de dois jeitos. É proibido calculá-los
por caminhos separados — em 04/Ago existiam TRÊS caminhos que discordavam, e três meta-análises
subiram ao Supabase com nota 9 e "muda_conduta: NÃO".

**O CASO QUE ORIGINOU A LEI — TOCILIZUMABE NA COVID-19.** Em 2021 as meta-análises diziam que a
droga não valia o investimento; a nota técnica do Ministério da Saúde (CCATES, abril/2021)
concluiu, com "certeza moderada", que reduzia ventilação mecânica mas **não** reduzia mortalidade
— apoiada num conjunto que **misturava ECRs com observacionais**. O RECOVERY, **um único** ensaio
com N adequado, encerrou a discussão sozinho: reduzia mortalidade.

Nas palavras dele: *"uma meta-análise só é tão boa quanto os estudos que a compõem. Somar estudos
pequenos, retrospectivos, heterogêneos e enviesados propaga e amplifica esses erros numa
estimativa matematicamente bonita, mas clinicamente enganosa."* **GIGO.**

**MEDIDO em 04/Ago, nas 24 metas do lote:** só ECR de baixo risco = 5/24 · Trim-and-Fill feito =
**1/24** · TSA feita = **2/24**. Média das notas: 5,92. Publicáveis: **12 de 24**. E das 24, **4
reprovaram no Degrau 2 — todas por misturar ECR com observacional**, com a ferramenta dupla
(RoB 2 + ROBINS-I) escrita no próprio artigo. O erro do tocilizumabe, quatro vezes em 24.

**Corolário:** quando o Claude achar que a régua está "severa demais" e for propor afrouxá-la,
ele mostra os números e QUEM DECIDE É O DONO. Afrouxar régua para caber mais artigo é trocar o
produto por volume — e o produto é justamente o filtro.

**O DESCONTO DE INDÚSTRIA NÃO CRUZA A FRONTEIRA DO 9 (06/Ago/2026)**

Na primeira rodada real dos artigos originais, os três primeiros RCTs de peso saíram assim:

| estudo | nota | muda_conduta |
|---|---|---|
| TRITON-TIMI 38 (Prasugrel, 2007) | 8 | **NÃO** |
| PLATO (Ticagrelor, 2009) | 8 | **NÃO** |
| DAPA-HF (Dapagliflozina, 2019) | 8 | **NÃO** |

Os três com `teto_desenho: 10`, `nota_trabalho_estatistico: 9`, ARR/ano acima do limiar da casa,
e o MESMO delator: `independência editorial −1.0 (indústria envolvida)`. O motor reconheceu tudo;
o desconto derrubou 9 → 8; e a **bicondicional** leu o 8 e escreveu que o ticagrelor não muda conduta.

**Por que era estrutural.** Quase todo ensaio de fase 3 em cardiologia é patrocinado — PLATO e
DAPA-HF são AstraZeneca, TRITON é Daiichi Sankyo/Lilly; SPRINT e ISCHEMIA são a exceção. Desconto
integral + bicondicional, juntos, tornavam quase impossível um artigo original chegar a 9, e o
produto perdia a frase mais valiosa que vende: *"isto muda sua prática"*. Nenhuma das duas regras
estava errada sozinha — elas se atropelavam porque o desconto entrava DEPOIS, no mesmo lugar onde
a bicondicional lê.

**A regra (opção A, decisão do Dr. Eduardo):** se a nota ANTES do desconto já era ≥9, o desconto
desce no máximo até **9**, e o delator DIZ quanto teria sido descontado. Financiamento é **ressalva
declarada, não rebaixamento de categoria** — o leitor vê que o ensaio é bom E quem pagou por ele.
Abaixo de 9 o desconto vale INTEIRO, como ele definiu em 05/Ago.
Trava: `teste_independencia_nao_cruza_o_nove` (`PISO_INDEPENDENCIA = 9`).

**⚠️ REVOGADO EM 22/Ago/2026 — O QUE PROTEGE É O RIGOR, NÃO A ALTURA DA NOTA**

A frase *"abaixo de 9 o desconto vale INTEIRO"* (linha acima) **não vale mais**. Quem a
derrubou foi o EXCEL.

Ele, lendo a nota: *"não tem como o EXCEL — estudo que muda a cardiologia — não estar com nota
9... ou eu tô muito doido"*. E logo depois: *"como um estudo que avalia uma galera que racha o
peito e no outro braço coloca stent poderia ser cego?"*

**Eu propus a coisa errada primeiro.** Peguei a razão dele sobre o cegamento e propus tirar o
teto 8 do open-label — sem ter olhado que o **gabarito dele de 11/Ago já dizia EXCEL 8, NOBLE 7,
ISAR-REACT 5 = 7**, todos open-label. A calibração dos ensaios abertos foi feita por ele sabendo
que ninguém cega esternotomia contra punção femoral. Teto 8 não é castigo por não cegar — é
quanta certeza o desenho entrega quando o composto inclui IAM julgado, que é exatamente a
controvérsia que fez a EACTS sair da diretriz da ESC em 2019. **Ele concordou com a minha
proposta**, e ela teria quebrado três gabaritos dele. Só não quebrou porque fui abrir o arquivo
antes de codar.

O que faltava era outra coisa: o EXCEL fecha em 8 pelo desenho, e o desconto de indústria
(Abbott) descia inteiro, levando a 7.

**A REGRA NOVA:** o desconto de independência **não rebaixa quem tem `nota_trabalho_estatistico`
≥ 9** — vira ressalva declarada, em qualquer altura da escala. É a MESMA frase de 06/Ago
(*"ressalva declarada, não rebaixamento de categoria"*), que nunca foi limitada ao 9; fui eu que
a implementei só ali. **Rigor <9 continua levando o desconto INTEIRO** — patrocinado e mal feito
paga.

**Por que não afrouxa a LEI 10:** quase todo ensaio de fase 3 em cardiologia é patrocinado
(EXCEL/Abbott, NOBLE/Biosensors, PLATO/AstraZeneca). Um desconto que quase todos levam não
separa ninguém — só empurra o acervo inteiro um degrau para baixo. O que separa é o rigor.

**MEDIDO ANTES DE VALER** — mesmo `fatos`, motor de ontem contra o de hoje, 1011 artigos únicos:
**22 mudam, TODOS de 7 → 8, nenhum desce.** Nenhum cruza a porta de publicação (já publicavam
com 7); o que muda é a CATEGORIA editorial. Gabarito: 7/7 continuam batendo.

Travas: `teste_o_desconto_de_industria_nao_rebaixa_quem_provou_o_metodo` — que carrega **o
gabarito dele inteiro dentro**, para nenhuma regra nova poder revogá-lo em silêncio — mais
`teste_independencia_nao_cruza_o_nove` e `..._o_portao_da_publicacao`, reescritas com a
revogação declarada no corpo.


**A TELA DA CHAVE 2 MOSTRAVA DUAS ORDENS DIFERENTES (06/Ago)**

A contagem do topo listava `ARTIGOS_ORIGINAIS · META · GUIDELINES · REVISOES`; o menu logo abaixo
numerava `1)META 2)GUIDELINES 3)REVISOES 4)ARTIGOS_ORIGINAIS`. O Dr. Eduardo leu a contagem, contou
até revisões, digitou **4** — e o 4 era artigos originais: 255 artigos, US$ 76,50. É a versão de
interface do "duas fontes de verdade" da LEI 9, e a culpa é de quem desenhou a tela, não de quem
digitou. Agora existe **UMA lista, com UM número por pasta** — o mesmo que se digita — e o custo
de cada linha aparece antes da escolha.

**A LISTA FIXA DE TESTES DAVA APROVADO POR AUSÊNCIA (06/Ago)**

`teste_independencia_nao_cruza_o_nove` foi escrita, a bateria rodou, saiu APROVADO — e a trava não
tinha rodado uma única vez: não estava na lista chumbada do runner. É o mesmo defeito do
`teste_schema_do_google` (que omitia o `SCHEMA_FATOS_META`), e é o pior tipo de defeito de prova:
**aprova por não ter olhado.** O runner agora VARRE o módulo e recolhe toda função `teste_*`; a
lista sobrevive só para fixar a ordem de leitura do relatório.

**`muda_conduta` SÓ EXISTE ONDE A PERGUNTA CABE (06/Ago/2026)**

A bicondicional de 04/Ago foi aplicada nos QUATRO motores. Nos dois em que a pergunta não cabia,
ela produziu afirmação clínica falsa — medido no lote real de 06/Ago:

| tipo | o que saiu | por quê estava errado |
|---|---|---|
| **revisão narrativa** | 8 revisões com nota 9 e `muda_conduta: SIM` | revisão não testa intervenção; não há conduta a mudar |
| **diretriz** | statement ESC de cardio-oncologia: `6/10 · MUDA CONDUTA: NÃO` — impresso, acima de cinco ordens diretas ao leitor | diretriz muda conduta POR DEFINIÇÃO |

**REVISÃO** — palavras dele: *"este termo muda conduta se aplica a um RCT. As revisões irão me
ajudar a ORGANIZAR O CONHECIMENTO. E a pontuação reflete a qualidade do material utilizado e a
quantidade de informações aplicáveis que ele de fato entrega."*
A NOTA não mudou: continua podendo chegar a 10 (decisão dele de 02/Ago, que revogou a minha
proposta de teto 6). O que saiu foi o CAMPO → `N/A (revisão organiza conhecimento, não testa
intervenção)`. Nota 10 significa "organiza excepcionalmente bem", não "prescreva".

**DIRETRIZ** — palavras dele: *"a diretriz muda várias coisas, pela atualização. Ninguém escreve
uma diretriz que não muda nada. Então o que muda é o GRAU COM QUE PODEMOS ACREDITAR NELA, baseado
na nota que o motor calcula. Podemos ajustar o nome e recomendar ou não recomendar."*
A nota AGREE passa a responder **"confie quanto?"**, em 4 faixas (`RECOMENDACAO_DIRETRIZ`):

| nota | veredito | o porquê que acompanha |
|---|---|---|
| ≥8 | **RECOMENDADA** | base sólida; pode seguir |
| 6–7 | **RECOMENDADA COM RESSALVAS** | parte relevante é opinião — leia com olho crítico |
| 4–5 | **REFERÊNCIA, NÃO AUTORIDADE** | é o documento que existe; não é prova, é consenso |
| ≤3 | **NÃO RECOMENDADA** | método frágil demais para sustentar o que recomenda |

⚠️ **A recomendação AVISA, não RETÉM.** A LEI 10 continua: a diretriz sobe em QUALQUER nota,
inclusive NÃO RECOMENDADA. Trava: `teste_diretriz_recomenda_em_vez_de_mudar_conduta` reprova se a
recomendação virar porta.

**A bicondicional NÃO foi enfraquecida** — ela continua inteira na intervenção (RCT e meta), e as
travas reprovam nos dois sentidos. A coluna `muda_conduta` foi REUSADA (decisão dele: sem ALTER
TABLE) e guarda quatro vocabulários diferentes conforme o tipo.

**O QUE EU ERREI, E É A LEI 9 DE NOVO:** implementei a bicondicional em 04/Ago nos quatro motores
sem varrer o que ela significaria em cada um. A lei que ele escreveu depois de eu cometer este
erro, cometido outra vez.

**O VISUAL ABSTRACT ERA O ÚLTIMO PONTO OLHANDO O `desenho` (06/Ago)**

`📋 Tipo detectado: artigo original` em **48 de 48 revisões**. O gerador escolhia o molde pelo campo
`desenho` dos FATOS — e o extrator da revisão não preenche `desenho` (`None` → `""` → cai no else →
"original"). 48 cards de revisão desenhados com o molde de RCT: MÉTODOS, POPULAÇÃO, PRINCIPAIS
RESULTADOS, "NNT não calculável" — numa peça que não tem população nem desfecho.

É o defeito que o próprio CLAUDE.md nomeia na LEI 8 (*"a escolha do prompt olhava a PASTA e a
escolha do motor olhava o campo `desenho` dos FATOS"*). Em 03/Ago consertamos o prompt e o motor;
o Visual Abstract ficou com a fonte velha, e ninguém notou porque **ele não quebra: escolhe o molde
errado e desenha bonito.** Segundo defeito empilhado: o analisador dizia `revisao_narrativa` e o
gerador só reconhecia `revisao` — mesmo com o tipo certo, cairia no adivinhador.
Fonte agora: `fatos["tipo_documento"]`, a MESMA que o motor usa.

**TAXA DE INCIDÊNCIA ≠ RISCO CUMULATIVO — DOIS CAMPOS (06/Ago/2026, opção A)**

O artigo reporta a diferença de risco de duas formas, com DENOMINADORES diferentes:

| forma | exemplo | denominador | o campo |
|---|---|---|---|
| incidência ACUMULADA | "16,3% vs 21,2% em 18,2 meses" | pessoas | `arr_pct` + `seguimento_anos` (o motor DIVIDE) |
| densidade de incidência | "141 vs 330 por 100.000 **pessoas-ano**" | pessoas-TEMPO | `arr_ano_pct` (o motor **NÃO** divide) |

Existia UM campo e o motor SEMPRE dividia. O número `2,0` é `2,0` — nada nele diz qual é, e o motor
não tinha como perceber. O erro andava nos DOIS sentidos: uma ARR de 2,0 %/ano num estudo de 5 anos
virava 0,4 %/ano e **reprovava um ensaio que muda conduta**; risco cumulativo lido como taxa
**aprovava o que devia reprovar**.

**Medido antes de consertar:** 129 pacotes · `arr_pct` preenchido em 8 · dupla divisão em ZERO. O
defeito ainda não tinha mordido — mas o mecanismo apareceu nos primeiros 20 originais, com as
palavras do extrator no JAMA Coffee: *"NNT não calculável, pois não foram fornecidos riscos
cumulativos"*, tendo "189 por 100.000 pessoas-ano" na primeira linha do resultado. Ele desistiu
porque o campo pedia o que o artigo não dava. Coorte longa em cardiologia quase sempre reporta em
pessoas-ano (Framingham, NHS, HPFS, UK Biobank), e faltavam 235 artigos originais na fila.

Trava: `teste_arr_por_ano_nao_e_dividida_de_novo` — e ela cobre os TRÊS blocos (motor · schema ·
prompt), porque motor certo + schema certo + **prompt calado** = campo null para sempre. Foi assim
que as palavras-chave da meta nasceram sem instrução em 05/Ago.

**A CONTA IMPRESSA PARA O REDATOR NÃO FECHAVA (06/Ago)**

O `veredito_completo` imprime `APLICABILIDADE = o MENOR entre: desenho · externa · falha fatal ·
MCID · rigor`. O campo `teto_mcid` vinha só do teto POR RÓTULO (01/Ago) e ignorava a CONTA conferida
(05/Ago). Com o JAMA Coffee saía:

```
APLICABILIDADE = o MENOR entre: desenho 10 · externa 10 · falha fatal 10 · MCID 10 · rigor 9
Nota 6/10
   • MCID conferido → teto 6: ARR 0,19 %/ano < 1,0 %/ano
```

**Nenhum número da conta produz 6**, e o delator contradiz a linha de cima. O VEREDITO ABERTO existe
para o redator explicar a nota a partir dos domínios (medido em 02/Ago: com o número nu, 86% dos
parágrafos mudavam) — e ele recebia domínios que não somam a nota. Ou inventa, ou desiste.
Agora `tm = min(tm, _t_mcid)`, e a trava confere que `min(domínios) == nota`.

**A ÚNICA EXCEÇÃO — A DIRETRIZ NÃO TEM PORTA (05/Ago/2026)**

*"As diretrizes — precisamos manter esta classificação mas não teremos nenhum impedimento para
subir. Mesmo com as limitações, é o que tem para hoje."* — Dr. Eduardo

**POR QUE NÃO É BRECHA:** a LEI 10 funciona porque, para uma meta ruim, existe outra melhor —
reter não custa nada ao leitor. Com diretriz é o contrário: não existe "outra diretriz de
fibrilação atrial", existe **A** diretriz. Se ela é fraca, o médico precisa saber que é fraca
**e mesmo assim precisa dela**, porque é o documento pelo qual ele será cobrado. Reter não
protege ninguém: esconde o que rege a prática.

| | diretriz | meta · revisão · artigo original |
|---|---|---|
| porta de publicação | **nenhuma** — sobe em qualquer nota | nota ≥ 6 |
| ACRI + perícia | sempre | nota ≥ 6 |
| Visual Abstract | sempre | nota ≥ 7 |
| áudio | sempre, com **roteiro próprio** (6–8 min, 900–1.200 palavras) | nota ≥ 8 |
| a nota | aparece **com justificativa** (6 domínios AGREE + % nível C + % Classe I em C) | idem |

O roteiro `script_audio_diretriz_prompt.md` tem uma obrigação que os outros não têm: **dizer a
nota EM VOZ ALTA e explicar em uma frase o que a puxou para baixo**, traduzido do jargão AGREE
("ninguém de fora leu antes de publicar", "a maior parte é opinião de especialista"). E, se a
nota for baixa, fechar com a razão de estar no ar assim mesmo.

Medido em 04/Ago: **13 de 31 diretrizes ficavam retidas com nota 4 e 5** — ESC, AHA, ESPEN, NICE.

⚠️ **A exceção é SÓ da diretriz.** Palavras dele: *"ESTA REGRA SÓ VALE PARA DIRETRIZ."*
Trava: `teste_diretriz_nao_tem_porta` reprova se a porta voltar OU se a exceção vazar para os
outros três tipos.

**AS PALAVRAS-CHAVE SÃO PORTUGUÊS — os prompts pediam INGLÊS (05/Ago)**

O focused update de dislipidemia do ESC subiu com `dyslipidaemia`, `LDL cholesterol`,
`bempedoic acid`. O cardiologista brasileiro digita `dislipidemia`, `colesterol LDL`, `ácido
bempedoico` — e não achava nada. A diretriz é o documento mais buscado do acervo e era o pior
indexado. Não era o modelo errando: **três prompts pediam "EM INGLÊS", com todas as letras.**
Achado em um, corrigido em três (LEI 9). Regra: 8–12 termos em português, cobrindo doença ·
intervenção/droga · população · desfecho, específicos (nada de "cardiologia" ou "manejo").

### LEI 1: NUNCA PROPOR ABANDONAR PARTE DO PROJETO
- O Claude NUNCA deve sugerir abandonar, descontinuar, remover ou desistir de qualquer funcionalidade planejada ou em desenvolvimento do CardioDaily.
- Se uma abordagem tecnica nao funciona, o Claude deve propor ALTERNATIVAS, nunca eliminacao.
- "Abandonar a ideia" NAO e uma opcao. Sempre existe uma solucao — encontre-a.
- O dono do projeto (Dr. Eduardo) decide o que entra e o que sai. O Claude executa e resolve.

### LEI 2: RESOLVER, NAO DESISTIR

Diante de dificuldades técnicas, o Claude deve, **nesta ordem**:

1. **Rever o objetivo central e o objetivo do MÓDULO.** Se o objetivo não está sendo alcançado, definir
   se é **erro de sintaxe/implementação** ou se **a ferramenta não atende à expectativa** — são problemas
   diferentes e exigem soluções diferentes.
2. **Identificar o problema real** (a causa, não o sintoma).
3. **Propor 2–3 alternativas viáveis**, sempre na ordem de prioridade do CardioDaily:
   **CONFIABILIDADE > CUSTO > VELOCIDADE.**
4. **Recomendar a melhor opção** — com o porquê.
5. **Se implementar: registrar IMEDIATAMENTE no `docs/CADERNO_EXECUCAO.md`**, com **data e hora**, na
   seção **do módulo alterado** (não no fim do documento, não num changelog genérico). Quem ler o módulo
   amanhã tem que ver o que mudou, quando e por quê.
6. **NUNCA listar "abandonar" como uma das opções.**

### LEI 3: RESPEITAR A VISAO DO PRODUCT OWNER
- O Dr. Eduardo define o que o CardioDaily deve fazer e como deve parecer.
- O Claude implementa a visao do dono, nao substitui por sua propria opiniao.
- Se o Claude discorda tecnicamente, apresenta a ressalva MAS executa o que foi pedido.

### LEI 4: UMA PASTA SÓ — O FULL É A ÚNICA VERDADE

**Existe UM projeto: `CardioDaily_FULL`. É PROIBIDO criar pasta paralela, cópia de trabalho, "lab",
"v2", "novo" ou qualquer variante do projeto.**

- O `CardioDaily_LAB` existiu e **foi DELETADO pelo Dr. Eduardo em 25/07/2026**. Motivo, nas palavras dele:
  *"esta estratégia não funcionou porque você se confundiu e não transicionava os arquivos finalizados"* —
  o que era aprovado virava órfão no LAB enquanto a produção seguia com o código velho.
  **Duas pastas = duas verdades = buraco.** (Conteúdo preservado em `archive/lab_snapshot_2026-07-25/`,
  só para consulta histórica.)
- Trabalho novo é feito **no FULL**, em branch de trabalho, e vai pro `main` quando aprovado.
- Se algo precisa ser testado sem sujar produção, o isolamento é por **branch do git** ou por **pasta de
  saída** (`outputs/_BATERIA`, `outputs/STAGING`) — **NUNCA** por cópia do projeto.
- O Claude **nunca** propõe "vamos fazer isso numa pasta separada". Se propuser, é para ser recusado.
- Corolário que sobrevive da lei antiga: **o que é aprovado é commitado no `main` sem esperar ser mandado.**
  Nada de "está pronto, mas só na minha branch".

### LEI 5: PORTÃO ÚNICO PARA O SUPABASE (A REGRA-MÃE DOS BURACOS)

**Só UM programa pode ESCREVER linha de artigo no Supabase: o `publicador.py`** (via `contrato` +
`preflight` + upsert idempotente). Ele é o ÚNICO portão de entrada da tabela `artigos`.

- É **PROIBIDO** qualquer outro programa dar INSERT/UPSERT/DELETE em `artigos`. Dois portões alimentando
  o mesmo Supabase foi a **causa raiz dos buracos** que quase mataram o CardioDaily (análise divergente,
  registro em branco, nota 5 publicada, DOI duplicado).
- Quem precisar publicar/atualizar artigo **chama o portão** (`rodar_em_blocos` → `publicador`), nunca
  REST cru pra `/rest/v1/artigos`.
- **Portões/portas já FECHADOS (aposentados com guarda que recusa):**
  - Portões completos: `article_analyzer.py` (analisador antigo), `scripts/ingerir_artigos.py` (pipeline
    GPT-4o paralelo), `scripts/indexar_corpus_completo.py` (indexador que inseria/apagava).
  - Portas laterais de mídia: `scripts/gerar_audios_lote.py`, `gerar_pdfs_lote.py`, `gerar_ganchos_abertura.py`,
    `extrair_ganchos.py`, `reparar_podcasts_revisoes.py` — o portão já faz áudio (≥8)/PDF (≥6)/gancho_lista;
    e o **gancho_abertura foi ABSORVIDO no portão** (análise nota≥8 gera `gancho_abertura_prompt.md` → ficha_site).
- Pra (re)gerar mídia/gancho de um artigo, **rode o portão** (`rodar_em_blocos`), nunca escreva por fora.
- Regra de produto pendente: áudio de REVISÃO/GUIDELINE com nota<8 (o portão só faz áudio ≥8). Se for pra ter,
  muda a PORTA do áudio no analisador — não se escreve por fora.
- **Só leem (ok):** `src/web_biblioteca.py`, `src/lista_whatsapp.py`, `src/whatsapp/daily_sender.py`.
- ✔ Verificado em 30/Jul: os três portões aposentados têm guarda que recusa no próprio arquivo.
- Antes de aprovar QUALQUER programa novo que fale com o Supabase: ele escreve em `artigos`? Se sim e não é
  o publicador → **é um buraco, recusar.**

### LEI 6: O QUE É DECISÃO DO DONO, COMO É DECISÃO DO CLAUDE

**O QUE entra no produto é decisão do Dr. Eduardo. COMO implementar é do Claude.**

- Sempre que o Claude construir algo que envolva ESCOLHA — qual campo preencher, qual limiar, qual porta,
  qual formato, o que entra e o que fica de fora — ele **LISTA as escolhas explicitamente ANTES de codar**.
  Uma lista curta: "vou preencher estes campos, deixar estes de fora, por este motivo". O Dr. Eduardo decide.
- **Se o Claude não listou, ele não decidiu: ele PEGOU uma decisão que era do dono.**
- É PROIBIDO embrulhar decisão de produto dentro de código e chamar de "detalhe de implementação".
- Vale também para o inverso: o Claude **não** deve trazer escolha técnica pura (nome de função, estrutura de
  pasta, biblioteca) — isso é dele, e perguntar só rouba o tempo do dono.

**O caso que originou a lei (28/07/2026):** o Claude montou a `ficha_site` com 25 das 39 colunas da tabela
`artigos` e chamou as outras 14 de "órfãs" — sem nunca perguntar. Resultado: `populacao`, `intervencao`,
`tamanho_beneficio`, `conclusao_geral`, `por_que_importa`, `principais_recomendacoes` e `nota_metodologica`
ficaram VAZIAS em toda a base, e o portão **não via isso como buraco** porque só validava os campos que o
próprio Claude escolheu. Buraco zero virou "zero buraco nas colunas que eu escolhi olhar".

**Corolário — BURACO ZERO tem definição de dono:** a linha sobe COMPLETA. Não é "não sobe linha quebrada";
é "toda coluna com significado editorial está preenchida". Quem define quais colunas têm significado é o
Dr. Eduardo, não o Claude.

### LEI 7: NÃO PODE HAVER "RESOLVIDO" E NÃO ESTAR

O CardioDaily existe para ser **consistente e sólido**. Isso é impossível se o Dr. Eduardo não puder
confiar no que o Claude relata. Portanto:

**"Não sei" é resposta válida. "Não consigo verificar daqui" é resposta válida. "Não dá" é resposta
válida. "Resolvido" sem estar resolvido NÃO É.**

**VOCABULÁRIO OBRIGATÓRIO DE CERTEZA** — o Claude usa a palavra exata, nunca uma acima:

| Palavra | Significa EXATAMENTE |
|---|---|
| **"Escrevi"** | existe no arquivo; nada rodou |
| **"Compila"** | sintaxe ok; lógica não testada |
| **"Testei aqui"** | rodou com dado de MENTIRA, sem API/banco — prova a lógica, não o mundo real |
| **"Rodou na sua máquina"** | o Dr. Eduardo executou e a saída está na tela |
| **"RESOLVIDO"** | **só isto:** rodou no ambiente dele, com dado real, com evidência visível |

**Limite físico que o Claude declara toda vez, sem esperar ser perguntado:** ele NÃO consegue chamar a API
dos modelos nem o Supabase do próprio ambiente. Logo, tudo que envolve LLM ou banco só chega a "testei
aqui" — a palavra "resolvido" **depende do Dr. Eduardo rodar**, e o Claude diz isso explicitamente.

**Proibido também:**
- Relatar sucesso de UM componente como se fosse sucesso do TODO ("70/70" quando o critério era parcial).
- Dar diagnóstico sobre o que não foi olhado ("o gargalo é X" sem ter visto X).
- Prometer trabalho fora do turno: **o Claude não roda sozinho em segundo plano.** Se o trabalho precisa
  acontecer sem o Dr. Eduardo presente, quem faz é o Claude Code da pasta (agentico) — e isso é dito na hora.
- Comemorar progresso parcial diante de falha ("analisamos 20, falharam 8, mas evoluímos"). Falha é falha.

**O caso que originou a lei (28/07/2026):** o Claude afirmou "buraco zero atingido" (o portão só olhava as
colunas que ele mesmo escolheu), disse "a camada de entrega é o gargalo" sem nunca ter visto o site — que já
estava pronto, com empresa, podcast e páginas legais — e disse "vou trabalhar agora" durante um plantão,
sabendo que não roda em segundo plano. Três horas depois, nada havia sido feito.

---

## DECISOES TECNICAS PERMANENTES

### CARDS HTML→PNG (Playwright) PARA WHATSAPP — PROIBIDO
O modelo de card 1080×1080px via HTML/CSS + Playwright foi testado para WhatsApp Top e DESCARTADO. Motivos:
1. **Texto minusculo**: Bullets curtos (como devem ser) ficam com fonte pequena que nao preenche o espaco
2. **Espacos vazios grandes**: Layout com flex expande os boxes mas o conteudo nao ocupa — resultado visual amador
3. **Nao serve para WhatsApp**: Card de redes sociais precisa ser lido em 2 segundos; esse modelo exige leitura cuidadosa

**Regra**: NAO gerar cards HTML→PNG para WhatsApp em nenhuma circunstancia enquanto nao existir um layout adaptativo que garanta densidade visual real.

**Alternativas validas para visual WhatsApp:**
- Imagem central do artigo original (figura da revista)
- Post "slogan" simples (titulo + 1 linha de descricao)
- Apenas texto formatado (sem imagem)

**Nota (verificado 30/Jul/2026):** o arquivo `whatsapp_card.html` **não existe mais** — foi removido do
projeto. O único template em `src/infographics/templates/` é o `visual_abstract_template.html`.

---

### ARTEFATOS VISUAIS PERMITIDOS — LEI ABSOLUTA

São permitidos DOIS artefatos visuais, e SÓ estes dois:

**1. Visual Abstract de 8 seções** (artigos originais, meta, revisão — a maioria):
- Arquivo: `src/infographics/visual_abstract_generator.py`
- Template: `src/infographics/templates/visual_abstract_template.html`
- Output: o gerador grava em `<pasta_do_artigo>/assets/visual_abstract.png` e o **analisador copia**
  para `<pasta_do_artigo>/{nome}_visual.png` — que é onde `ficha_site` e `contrato` procuram (`*_visual*`).
  Mínimo aceito pelo portão: 50 KB (abaixo disso = truncado, artigo volta pra fila).

**2. Fluxograma de conduta em Mermaid** (EXCLUSIVO da trilha MINIRREVISÃO / opinião de especialista) —
   aprovado pelo Dr. Eduardo em 25/07/2026:
- Motor: **Mermaid**, tematizado CardioDaily (azul #0B3D91 / vermelho #C00000, Helvetica), renderizado
  offline (mmdc / mermaid-cli).
- Por que Mermaid e NÃO HTML/CSS: o layout é do motor → consistência garantida, nunca "quebra feio".
  Foi a variabilidade do HTML/CSS feito à mão (caixa vazia, texto de tamanho variável) que reprovou os
  cards — o mesmo princípio do buraco zero. É o ÚNICO uso permitido de fluxograma.
- Escopo: só a trilha minirevisão. NÃO usar fluxograma em artigo original/meta.

**TODOS os outros geradores de imagem/gráfico estão em QUARENTENA PERMANENTE:**
- `InfographicPortrait` (portrait_visualmed) — PROIBIDO · *(verificado 30/Jul: o arquivo próprio não existe
  mais; o nome só sobrevive dentro de `src/article_analyzer.py`, que é o analisador ANTIGO)*
- `MindmapGenerator` visual PNG — PROIBIDO · *(idem: só resta menção dentro do `article_analyzer.py`)*
- `infographic_mpl.py` (matplotlib) — PROIBIDO · *(verificado 30/Jul: **não existe** em lugar nenhum)*
- Qualquer gerador de gráficos de barras, charts, ou artifícios visuais — PROIBIDO
- DALL-E 3 — PROIBIDO (já existia)
- Cards HTML→PNG para WhatsApp — PROIBIDO (já existia)

**Regra**: Nunca adicionar, reativar ou sugerir qualquer outro gerador visual sem aprovação explícita do Dr. Eduardo.

---

### DALL-E 3 — PROIBIDO NO PROJETO
O DALL-E 3 (OpenAI) foi testado e REMOVIDO do CardioDaily. Motivos:
1. **Imagens genericas e inuteis**: Gera coracoes bonitos com setas e bolinhas, mas ZERO conteudo clinico real. Nenhum dado, nenhum numero, nenhuma informacao util aparece nas imagens.
2. **Custo sem retorno**: ~US$ 0.04/imagem para gerar lixo visual sem valor cientifico.
3. **Impossibilidade tecnica**: O DALL-E 3 NAO consegue renderizar texto, numeros, tabelas ou dados clinicos com precisao. Ele e um gerador de arte, nao de infograficos.
4. **Arquivos removidos**: `src/dalle_image_generator.py` e `src/image_prompt_generator.py` não existem mais
   no projeto (verificado 30/Jul/2026 — foram apagados, não arquivados; a pasta `archive/legacy_images/`
   citada em versões antigas deste documento **não existe**).

**Regra**: Nenhum codigo do CardioDaily deve usar DALL-E para geracao de infograficos. Se precisar de geracao de imagem, usar alternativas que consigam renderizar dados reais (Gemini Imagen com prompts estruturados, SVGs programaticos, HTML/CSS renderizado).

---

## META DO PROJETO (atualizado 30/Jul/2026)

A meta agora é **VENDER**. O motor de análise está provado (70 artigos, zero falha, 25/Jul).
O que falta é a última milha: abrir a porta (amostra pública + assinatura) e fechar a qualidade
editorial (perícia com tabelas, conferidor de números).

- **Caderno de execucao completo:** `docs/CADERNO_EXECUCAO.md` (v30.0)
- **Mapa dos arquivos de `src/`:** `MAPA_DO_SRC.md` (o que é a corrente, o que roda sozinho, o que é legado)

## ESTRUTURA DO PROJETO

- `/chaves/` - **os 4 botões** (.command) — é assim que o Dr. Eduardo roda o sistema
- `/src/` - Codigo fonte: **31 arquivos .py, mas só 21 são a CORRENTE** (o resto é legado do
  `article_analyzer` ou roda sozinho pelo Actions). Ver `MAPA_DO_SRC.md`.
- `/src/infographics/` - Gerador do Visual Abstract (Playwright + Jinja2)
- `/scripts/` - Scripts de lote (maioria manual; só `run_radar_diario.py` e `auditoria_supabase.py` no Actions)
- `/docs/` - Documentacao (CADERNO_EXECUCAO.md v30.0)
- `/outputs/STAGING/` - **pacote por artigo** (o GOLDEN GATE, antes de publicar)
- `/ARTIGOS/` - entrada dos PDFs + CLASSIFICADOS/ por tipo
- `/archive/` - Codigo descontinuado (inclui `lab_snapshot_2026-07-25/`)

## STACK TECNICA (modelos: SEMPRE via `src/modelos.py` — nunca hardcoded)

- Python 3 · Supabase (tabela `artigos`) · Playwright + Jinja2 (Visual Abstract) · WeasyPrint (PDF)
- **Cadeias de modelo** (primário → fallback CROSS-PROVIDER, LEI DA EQUIVALÊNCIA):
  - `PROFUNDO` (Pesquisador, pontos críticos): **claude-opus-5** → gpt-5.6-sol → gemini-3.1-pro-preview
  - `ESCRITA` (perícia, ACRI, áudio, análise): **claude-sonnet-5** → gpt-5.6-terra → gemini-3.1-pro-preview
  - `EXTRACAO` (fatos, classificação): **claude-sonnet-5** → gpt-5.6-terra → gemini-3.1-pro-preview
  - `RAPIDO` (triagem, volume): **claude-haiku-4-5** → gpt-5.6-luna → gemini-3.6-flash
  - `GUIDELINE_LONGO` (contexto 1M): **gpt-5.6-sol** → gemini-3.1-pro-preview
- **Gemini NUNCA é primário — só fallback** (trava demais / 429).
- **TTS:** OpenAI `gpt-4o-mini-tts` voz **cedar** (artigos) · ElevenLabs (Radar) · Cartesia (Briefing)
- Extração usa **saída estruturada (tool use)**: JSON inválido é impossível.

## ESTADO ATUAL DO SISTEMA (30/Jul/2026)

| Componente | Status |
|---|---|
| Classificador (PubMed autoritativo + Sonnet 5) | ✅ Operacional |
| Analisador modular (fatos → LEI 0 → perícia/ACRI/áudio) | ✅ Operacional |
| Visual Abstract 8 seções (Sonnet 5 + Playwright) | ✅ Operacional |
| Publicador (contrato + preflight → Supabase rascunho) | ✅ Operacional |
| Administrador (curadoria) · Arquivador | ✅ Operacional |
| Bateria de prova (`bateria.py`) | ✅ 70/70 sem falha (25/Jul) |
| **Perícia com TABELAS** (hoje é prosa ilegível) | **🔴 PENDENTE** |
| **Conferidor de números** (nenhum dado fora da fonte) | **🔴 PENDENTE** |
| **Colunas vazias da tabela `artigos`** | **🔴 PENDENTE (decisão do dono)** |
| **Editorial/Comment entra na fila e vira perícia** | **🔴 BUG — queima dinheiro** |
| **Dois analisadores vivos** (`article_analyzer` no Actions) | **🔴 RISCO** |
| Amostra pública + assinatura no site | ⏳ Não implementado |

## COMO SE RODA O SISTEMA — OS 4 BOTÕES (`/chaves/`)

Não há CLI. O Dr. Eduardo roda por **dois cliques** em `~/projetos/CardioDaily_FULL/chaves/`:

| Botão | O que faz |
|---|---|
| **1_Classificador** | lê os PDFs de `ARTIGOS/`, identifica o tipo (PubMed) e move p/ `CLASSIFICADOS/<tipo>/` |
| **2_Analisador** | analisa **e publica em BLOCOS DE 20** (`rodar_em_blocos.py`) — se a net cair, só o bloco refaz. Depois roda `minirevisao.py` na pasta MINIRREVISOES (condutas + fluxograma Mermaid, **não** sobe no Supabase) |
| **3_Administrador** | painel Streamlit de curadoria: ver · ouvir · aprovar com data de envio |
| **4_Arquivador** | move o staging concluído p/ `ARQUIVO/AAAA-MM` (nunca deleta) |

## PACOTE POR ARTIGO (o que existe no STAGING)

```
outputs/STAGING/{nome_do_artigo}/
├── {nome}_fatos.json        # FATOS extraídos (saída estruturada) — a base de tudo
├── {nome}_CANONICO.md       # registro canônico (YAML + análise) — SEMPRE, mesmo retido
├── {nome}_ACRI.txt          # o card: Análise · Confiança · Resposta · Impacto   [nota ≥6]
├── {nome}_analise.md        # a PERÍCIA completa                                  [nota ≥6]
├── {nome}_analise.pdf       # a perícia em PDF (peça central do site)              [nota ≥6]
├── {nome}_visual.png        # VISUAL ABSTRACT de 8 seções                          [nota ≥7]
├── {nome}_audio.mp3         # áudio-anzol (~3 min)                                 [nota ≥8]
├── {nome}_roteiro_audio.txt # roteiro do áudio                                     [nota ≥8]
└── _OK                      # marcador: só existe se TUDO da porta foi conferido
```

**NÃO existe mais:** mapa mental (`mindmap.*`), `outputs/corpus/`, CLI `./cardiodaily`, "infográfico rico
estilo NotebookLM". O único artefato visual é o **Visual Abstract de 8 seções**.

### LEI 12: NADA DESTRUTIVO SEM CONFERIR ANTES — E O TRABALHO DELE NÃO É MEU PARA APAGAR (20/Ago/2026)

**Palavras do Dr. Eduardo:** *"já não pedi para você revisar antes de fazer as coisas? RÁPIDO
SIGNIFICA ERRADO!"*

**O que aconteceu.** Ele marcou 40 linhas do gabarito cego de tema — trabalho manual, dele, que
só ele pode fazer. Mandou o arquivo. O upload chegou com **0 bytes** (ainda não tinha terminado
de subir). Eu copiei esse arquivo por cima do original em `saidas/` **sem olhar o tamanho**, num
`cp` de uma linha. As marcações se perderam. `saidas/` não está no git.

Dois erros, e o segundo é pior:
1. **Agi rápido em cima de um arquivo sem conferir se ele tinha conteúdo.** É a mesma família
   que este documento inteiro persegue — ausência lida como dado — só que desta vez a ausência
   não mentiu num número: **destruiu.**
2. **Declarei o estrago antes de investigar.** Disse "apaguei seu trabalho" e mandei ele
   procurar em Downloads. Só DEPOIS descobri que o upload tinha terminado e que o Excel estava
   com o arquivo aberto (havia um `~$` no disco). Diagnóstico apressado em cima de dano
   apressado. A LEI 7 já proíbe a segunda metade; a primeira faltava.

**A REGRA — antes de QUALQUER operação que sobrescreve, move ou apaga:**

| # | confere | por quê |
|---|---|---|
| 1 | **o arquivo de origem tem tamanho plausível?** | 0 byte, ou muito menor que o esperado, é upload incompleto — não é dado |
| 2 | **o destino existe e é diferente da origem?** | sobrescrever com cópia do próprio destino é perda pura |
| 3 | **o que vai ser perdido é reconstruível por MIM?** | se só o Dr. Eduardo consegue refazer (marcação a mão, curadoria, decisão), **NÃO ENCOSTA** — pede |
| 4 | **existe backup?** | `saidas/`, `outputs/` e `ARTIGOS/` **não estão no git**. Ali não há desfazer |

**Corolário duro:** trabalho MANUAL dele — gabarito marcado, curadoria da Chave 3, PDF que ele
organizou na mão — vale mais que qualquer arquivo que o sistema gera, porque o sistema regera e
ele não. Sobre esses arquivos o Claude **só lê**. Quem grava é ele.

**E a pressa não é desculpa: é a causa.** Não existe motivo para um `cp` ser feito antes de um
`ls -la`. O segundo custa zero.
