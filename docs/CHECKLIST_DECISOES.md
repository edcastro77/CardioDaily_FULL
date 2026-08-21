# CHECKLIST DE DECISÕES — o que se responde ANTES de codar

## LEI 11 — A LISTA VEM ANTES DO CÓDIGO, E O VAZIO TEM DE TER NOME (20/Ago/2026)

**Palavras do Dr. Eduardo:** *"você precisa criar um checklist de pontos principais das decisões
antes de codar — nós havíamos decidido que nestes casos você vai colocar 'não se aplica', mas
buraco não pode existir."*

Duas regras, e a segunda é a que fecha o buraco de verdade:

### 1 · A LISTA VEM ANTES
Antes de escrever a primeira linha de código de qualquer coisa que envolva ESCOLHA, o Claude
preenche um checklist como o abaixo e MOSTRA. É a LEI 6 com um formato: lá dizia "liste as
escolhas"; aqui diz **como** listar, para que a lista não vire um parágrafo que se lê e esquece.
Cada linha tem: o campo · o que entra quando dá certo · **o que entra quando NÃO dá** · quem decide.

### 2 · NULL NÃO É RESPOSTA. "NÃO SE APLICA" É.
Nunca deixar coluna vazia porque "não deu para preencher". Vazio é indistinguível de esquecido,
de quebrado e de nunca-implementado — e é assim que todo buraco deste projeto começou:

| data | o vazio | o que ele foi lido como sendo |
|---|---|---|
| 11/Ago | `retrospectivo: null` | "não é retrospectivo" → Framingham com teto 8 |
| 14/Ago | livro de bordo ilegível | "não enviei nada, pode mandar tudo" |
| 18/Ago | `nao_avaliavel` sem teto | "relevância máxima" |
| 19/Ago | PDF com 257 chars de carimbo | "tem texto, pode analisar" |
| 20/Ago | `tema: NULL` em 117 linhas | "ninguém sabe se falhou ou se nunca rodou" |

O precedente já é dele, de 06/Ago: `muda_conduta` numa revisão virou
`N/A (revisão organiza conhecimento, não testa intervenção)` — **um texto que se lê e se
entende**, não um vazio. É esse padrão que passa a valer em toda coluna.

**Como se escreve o vazio, nesta ordem de preferência:**
1. `Não se aplica` + o porquê, quando a pergunta não cabe naquele objeto;
2. um valor explícito de "não sei" (`Sem tema`, `nao_avaliavel`), quando a pergunta cabe e a
   resposta não veio — e ele tem de aparecer na tela do Administrador, filtrável;
3. RETER a linha, quando o campo é essencial demais para subir sem ele.

Nunca `NULL`. Nunca `""`. Nunca a coluna ausente do payload.

---

# CHECKLIST · TEMA NO PORTÃO (20/Ago/2026)

**Medido antes de propor:** 616 linhas · 117 sem tema · 78 das 83 de 19/Ago.
**Causa:** o `marcar_temas.py` é um segundo portão (PATCH em `artigos`, violando a LEI 5) e o
`publicador.py` nunca soube que estas colunas existem.

## As colunas, e o que entra em cada caso

| # | coluna | quando DÁ certo | quando NÃO dá | decisão |
|---|---|---|---|---|
| 1 | `tema` | um dos 13 temas | **`Sem tema`** (nunca NULL) | ⬜ |
| 2 | `tema_secundario` | 2º tema acima do piso 0,40 | **`Não se aplica`** — a maioria dos artigos tem UM tema só, e isso é o normal, não uma falha | ⬜ |
| 3 | `tema_origem` | `mesh` · `llm` | **`nao_classificavel`** — exige migração: o CHECK hoje só aceita mesh/llm/manual | ⬜ |
| 4 | `mesh_terms` | os descritores do PubMed | **`{}`** (array vazio, não NULL) — significa "procurei e não achou", que é diferente de "não procurei" | ⬜ |

## As perguntas que mudam o comportamento

| # | pergunta | proposta | por quê |
|---|---|---|---|
| 5 | linha com `Sem tema` **sobe**? | **NÃO** — fica retida com o motivo, como qualquer buraco | você decidiu "sem tema não sobe" |
| 6 | e a **DIRETRIZ**? | **TAMBÉM NÃO** — e é o alarme mais alto | ver abaixo |
| 7 | quem **PREENCHE** | só o `publicador.py`, dentro do portão | LEI 5. Hoje são dois programas e foi isso que abriu o buraco |
| 8 | o `marcar_temas.py` | **aposentado** com guarda que recusa, como os outros 3 portões fechados | o PATCH dele é a violação da LEI 5 |
| 9 | os **117** já no banco | backfill: MeSH grátis primeiro, LLM no resto | ~US$0,12 medido no lote anterior (186 artigos) |
| 10 | o `nao_classificavel` | vai para uma fila visível no Administrador | senão vira o mesmo silêncio, só com outro nome |

### ⚠️ #6 — EU TINHA MISTURADO DUAS COISAS (corrigido por ele, 20/Ago)

Eu propus que a diretriz subisse sem tema, invocando a LEI 10. **Estava errado.**

A exceção de 05/Ago é sobre a **NOTA**: *"não existe 'outra diretriz de fibrilação atrial',
existe A diretriz — se ela é fraca, o médico precisa saber que é fraca e mesmo assim precisa
dela"*. Reter por nota baixa esconderia o documento pelo qual ele será cobrado.

**Tema não é nota.** Palavras dele: *"não tem cabimento uma diretriz subir sem tema."* E ele
está certo pelo mesmo raciocínio que criou a exceção: uma diretriz é, por definição, **sobre um
assunto** — "Diretriz de Dislipidemia", "Diretriz de FA". Não existe diretriz sem tema no mundo.
Se o sistema não achou o tema de uma diretriz, isso não é "o objeto não tem essa propriedade";
é o classificador falhando **no caso mais fácil que existe**.

Ou seja: diretriz sem tema não é exceção, é **defeito** — e defeito não passa. Ela é retida como
qualquer outra, e com prioridade na fila de revisão humana, porque é o sinal mais forte de que
algo quebrou a montante.

**A regra fica UMA, para os quatro tipos.** Menos exceção, menos chance de a exceção vazar —
que foi o que aconteceu em 06/Ago quando a bicondicional foi aplicada nos quatro motores sem eu
varrer o que ela significava em cada um.

## O que eu NÃO vou decidir sozinho
- **#3** exige `ALTER TABLE` (o CHECK de `tema_origem`). Você já disse em 06/Ago que prefere
  **reusar coluna a fazer ALTER TABLE**. Se preferir evitar a migração, a alternativa é gravar
  `manual` com um texto no motivo — mas aí `manual` passa a significar duas coisas, que é
  exatamente o defeito que a LEI 9 persegue. **Minha recomendação: fazer a migração.**
- **#5 vs #1** têm uma tensão real: se nada sobe sem tema, o valor `Sem tema` quase nunca chega
  ao banco — ele existe para o caso da diretriz e para o backfill. É de propósito.

## Depois de aprovado — os blocos a varrer (LEI 9)

| # | bloco | o que muda |
|---|---|---|
| 1 | `ficha_site.py` | preenche as 4 colunas · nunca NULL |
| 2 | `contrato.py` | exige tema · exceção da diretriz |
| 3 | `publicador.py` | as 4 colunas no mapa de tipos |
| 4 | `scripts/marcar_temas.py` | guarda que recusa (aposentado) |
| 5 | `administrador.py` | filtro por tema + fila dos `Sem tema` |
| 6 | `teste_motor.py` | travas: sem tema não sobe · diretriz sobe · ninguém mais escreve |
| 7 | `CLAUDE.md` · `CADERNO_EXECUCAO.md` | a LEI 11 e a LEI 5 violada por mim |

---

# CHECKLIST · AS REGRAS DE TEMA (20/Ago/2026)

## MEDIDO PRIMEIRO — gabarito cego de 40 artigos, marcados a mão pelo Dr. Eduardo

| régua | MeSH | LLM | TOTAL |
|---|---|---|---|
| 1º tema idêntico | 50 % | 75 % | 62 % |
| par idêntico (1º+2º, sem ordem) | 20 % | 25 % | 22 % |
| **★ o tema DELE está no par gravado** | **65 %** | **85 %** | **75 %** |

### ⚠️ QUAL DESSES NÚMEROS VALE — ele decidiu, e eu tinha escolhido o errado

Eu apresentei **62 %** e chamei de "acerto estrito". Ele olhou o caso 40 (septo/QRS para
amiloidose, que o sistema pôs em Miocardiopatias e ele em Arritmias) e disse:

> *"mas no caso 40 cabe as duas coisas — isso não é um erro."*

Tem razão, e isso troca a métrica inteira. **Um artigo carrega DOIS temas.** Se o tema que ele
daria está em qualquer uma das duas posições, o assinante daquela categoria **recebe o artigo** —
a ordem só decide o que aparece primeiro no card. Medir por "1º idêntico" pune o sistema por
uma diferença que o assinante nunca vê.

**A régua honesta é a ★: 75 % chegam ao leitor certo.** E o que sobra são **10 artigos em que o
assinante NÃO receberia** — 7 do MeSH, 3 do LLM. Esse é o defeito real, e é ele que se conserta.

### As 10 que não chegariam — e são TRÊS causas, não dez

**(a) `Miocardiopatias` é um buraco no mapa — 4 das 10.**
HP portopulmonar · a diretriz de hemodinâmica em HP · doença reumatológica · COVID/miocardite.
O sistema só chega em Miocardiopatias quando o título diz "cardiomyopathy". **Toda a lista do
ambulatório dele — Chagas, amiloidose, sarcoidose, Kawasaki, Danon, PKP2, pericárdio,
miocardite, VD — está FORA do mapa.**

**(b) `Cardiometabólica` está sendo destino, não origem — 2 das 10.**
Anti-PF4 e poluição/saúde cerebral. O sistema manda para Arritmias e Imagem; ele manda para
Cardiometabólica porque é o **mecanismo** que gera a aterosclerose (regra A).

**(c) Os três temas de MÉTODO não existem como conceito — 3 das 10.**
Eco na progressão da estenose · PA pós-trombectomia · ECG no amiloide. É a regra "quem lê".

**Nenhuma das dez é caso isolado.** Cada uma cai numa das regras que ele ditou — consertar as
regras conserta as dez de uma vez, e é isso que a remedição vai provar ou desmentir.

⚠️ **Em 17/Ago eu mostrei "499 de 520 com tema" e chamei de resultado.** Cobertura não é
acerto: cobertura diz quantos foram marcados, não quantos foram marcados CERTO. É a confusão
que a LEI 7 proíbe — relatar o sucesso de um componente como se fosse o do todo. A precisão só
foi medida hoje, três dias depois, e ela é **50 % no MeSH**.

## ~~A REGRA-MÃE — o tema é a DOENÇA, não o MÉTODO~~ ❌ SUPERADA

⚠️ **Esta seção está ERRADA e fica aqui só como registro.** Eu a escrevi com os 40 casos ainda
sem comentário e apoiada num exemplo que eu tinha lido invertido (o do amiloide — ver abaixo).
Quando ele comentou 24 casos um a um, a regra certa apareceu, e é outra:
**O TEMA É QUEM LÊ** — a seção no fim deste arquivo.

Fica registrada porque "doença antes de método" ainda vale como *heurística de desempate*, mas
não como regra: ela quebra em pelo menos seis dos casos que ele explicou (11, 16, 25, 39, 40 e
o par 13/20).

| caso real | o sistema leu | ele lê |
|---|---|---|
| Portopulmonary Hypertension | avaliação hemodinâmica → Intervenção | é HP → **Miocardiopatias** |
| ~~Septal thickness / QRS voltage p/ amiloide~~ | **EU INVERTI:** o sistema deu Miocardiopatias | ele deu **Arritmias** — o ECG é a ferramenta de quem lê |
| Reserva de fluxo subendocárdica | "flow reserve" → Imagem | invasivo → **Intervenção** |
| IVUS na braquiterapia | "imaging" → Imagem | hemodinâmica → **Intervenção** |
| Anti–Platelet Factor 4 | "anticoagulação" → Arritmias | cascata → **Cardiometabólica** |

É também por isso que o LLM ganha do MeSH: ele lê o título inteiro e enxerga o assunto; o mapa
soma descritores e não distingue objeto de instrumento.

## AS CINCO REGRAS, nas palavras dele

**R1 · ATEROSCLEROSE É UM CONTÍNUO.**
*"leve em consideração que a aterosclerose de coronária e de outros leitos arteriais é um
contínuo de aterosclerose clínica"*
Leito cerebral, carotídeo, periférico ou coronário é a mesma doença. Fator de risco e mecanismo
metabólico → `Cardiometabólica`; placa, doença estabelecida e tratamento → `Coronária/DAC`.
*(Corrige: "Air Pollution and Brain Health", que estava em Imagem Cardiovascular.)*

**R2 · "IMAGEM CARDIOVASCULAR" É MÉTODO NÃO INVASIVO.**
*"o termo que usamos imagem cardiovascular se refere principalmente a imagem por métodos não
invasivos — isto poderia ser feito pelo radiologista?"*
O teste dele é bom e é operacional: **um radiologista poderia fazer?** Se sim, é Imagem. IVUS,
OCT, FFR, reserva de fluxo invasiva e qualquer coisa feita dentro da sala de hemodinâmica →
`Intervenção/Hemodinâmica`.

**R3 · TODA hipertensão pulmonar → `Miocardiopatias`.**
*"toda e qualquer HP vira miocardiopatia pela repercussão no VD e tudo que a falência de VD pode
repercutir."*
Sem exceção por grupo (1 · tromboembólica · do VE · portopulmonar) e independentemente de a
avaliação ser hemodinâmica invasiva. **O que define é o órgão que adoece: o ventrículo direito.**
Perguntei se valia só quando havia miocardiopatia associada; a resposta foi que a HP É a
miocardiopatia, porque a via final é sempre a falência do VD e tudo que ela repercute. Uma linha
no mapa não bastava: o descritor `Hypertension, Pulmonary` inteiro muda de dono.

**R4 · `Arritmias/Anticoagulantes` é FA e anticoagulação CLÍNICA.**
*"não tem nada de arritmia, mas diz respeito a coagulação primariamente, assim como os
mecanismos de ativação desta cascata."*
Biologia da hemostasia, ativação plaquetária e cascata → `Cardiometabólica`.

**R5 · DOENÇA ANTES DE MÉTODO** — a regra que unifica R2, R3 e o caso do amiloide.

## O QUE A MEDIÇÃO EXIGE DECIDIR

| # | decisão | proposta | ⬜ |
|---|---|---|---|
| 1 | **a ordem** — hoje MeSH tenta primeiro e o LLM só entra na ausência de descritor | **inverter**: LLM decide, MeSH confirma/desempata. 75 % vs 50 % medidos | ⬜ |
| 2 | as 5 regras entram **onde** | no prompt do `tema_llm.py` (R1–R5) **e** no mapa `mesh_para_tema.json` (R1–R4), porque as duas pontas decidem | ⬜ |
| 3 | o desempate 1º/2º | 9 das 15 divergências são ordem, não tema. Rever o peso IDF com as regras aplicadas | ⬜ |
| 4 | remedir depois | os MESMOS 40, mesmo gabarito. Sem remedir, "consertei" é opinião | ⬜ |

---

# A REGRA-MÃE, CORRIGIDA — **O TEMA É QUEM LÊ** (20/Ago/2026)

Ele comentou 24 dos 40 casos, um a um. Eu tinha proposto *"o tema é a DOENÇA, não o método"* —
e essa regra **quebra** em pelo menos seis dos casos que ele explicou. A regra verdadeira ele
enunciou três vezes sem nomear:

> *"interessa diretamente ao **hemodinamicista**"* · caso 11
> *"interessa diretamente o médico de plantão na **UTI**"* · caso 26
> *"o cara que é clínico, que trata hipertensão, diabetes, que faz teste ergométrico, **não vai
> ler isso**; interessa para o cara que faz UTI"* · caso 37

**O tema é o LEITOR.** Não a doença, não o método, não a revista. É a única régua que explica os
24 casos ao mesmo tempo — e é exatamente o que o produto vende: o artigo certo para o assinante
certo. Nas palavras dele em 17/Ago, quando mandou parar tudo por causa disto: *"o tema diz
respeito à minha capacidade de disponibilizar o material correto para quem quer receber."*

⚠️ **E EU TINHA INVERTIDO UM DOS EXEMPLOS.** No resumo anterior escrevi que o sistema leu
"QRS → Arritmias" e que ele corrigiu para Miocardiopatias. Foi ao contrário: o sistema deu
**Miocardiopatias** e ele deu **Arritmias/Anticoagulantes**, porque quem lê um artigo sobre
"septal thickness / QRS voltage" é o eletrofisiologista usando o ECG como ferramenta de triagem.
Eu construí a regra "doença antes de método" apoiado num exemplo que dizia o contrário.

## OS TRÊS TEMAS QUE SÃO DE MÉTODO, E UM QUE É DE CENÁRIO

Isto não estava escrito em lugar nenhum, e é o que fazia o mapa MeSH errar:

| tema | é o tema quando… | leitor |
|---|---|---|
| `Imagem Cardiovascular` | o objeto é a **aquisição/interpretação NÃO invasiva** | imagenologista |
| `Intervenção/Hemodinâmica` | a medida ou o gesto acontece **dentro da sala de hemodinâmica** | hemodinamicista |
| `Arritmias/Anticoagulantes` | a ferramenta é o **ECG/eletrofisiologia**, ou o assunto é **uso clínico de anticoagulante** | eletrofisiologista |
| `UTI Cardiológica` | o cuidado é **à beira do leito crítico** | intensivista |

**O teste operacional que ele deu para Imagem** (caso 3): *"isto poderia ser feito pelo
radiologista?"* Se sim → Imagem. IVUS, OCT, FFR e reserva de fluxo invasiva → Intervenção.

## MÉTODO OU DOENÇA? A DISTINÇÃO QUE ELE FEZ, E QUE EU NÃO TINHA

Ele separou dois casos quase idênticos, e a diferença é o **objeto do artigo**:

| caso | tema 1º | por quê (palavras dele) |
|---|---|---|
| 20 · avaliação do paciente **para** TAVI | `Valvulopatias` | *"não diz respeito ao procedimento em si — está avaliando o paciente que VAI fazer o procedimento"* |
| 11 · reserva de fluxo subendocárdica | `Intervenção` | a medida É o objeto, e é feita no laboratório |
| 16 · eco na progressão da estenose | `Imagem` | o objeto é a avaliação por imagem |
| 13 · miocárdio em risco no TAVI | `Valvulopatias` | o objeto é a doença valvar |
| 25 · como adquirir RM cardíaca fetal | `Imagem` | *"diz respeito primariamente a um método de aquisição"* |
| 39 · imagem intravascular guiando PCI | `Intervenção` | *"não à doença em si, mas a como eu avalio com a imagem invasiva"* |

**Regra:** avaliar o PACIENTE → tema da doença. Avaliar ou executar o MÉTODO → tema do método.

## AS REGRAS DE CONTEÚDO (ditadas, caso a caso)

**A · ATEROSCLEROSE É UM CONTÍNUO, e `Coronária/DAC` significa "aterosclerose clínica".**
*"coronária e DAC é um reflexo da aterosclerose clínica, e a gente vai sempre considerar a
possibilidade de implicar qualquer outro leito arterial"*. Qualquer leito — cerebral, carotídeo,
periférico.
**A ordem importa:** carga/fator metabólico que LEVA à placa → `Cardiometabólica` 1º e
`Coronária/DAC` 2º (casos 1, 27, 32). Placa/doença estabelecida → `Coronária/DAC` 1º (33, 38).
Sobre o caso 27: *"não é primariamente a aterosclerose por si só, mas tudo que acontece numa
combinação de fatores amplos para gerar a aterosclerose. Primeiro o cardiometabólico, depois a
aterosclerose."*

**B · TODA hipertensão pulmonar → `Miocardiopatias` (1º E 2º).**
*"todas as repercussões que a miocardiopatia pode gerar por disfunção do ventrículo direito, por
congestão hepática, congestão pulmonar, hipertensão venocapilar, congestão venosa renal, infarto
venoso."* Sem exceção de grupo. *"Eu odeio o ventrículo direito."*

**C · O AMBULATÓRIO DE MIOCARDIOPATIAS — a lista dele, do INCOR:**
pericardiopatia · derrame pericárdico · miocardiopatia restritiva · **Chagas** · **amiloidose** ·
**sarcoidose** · **doença de Danon** · **PKP2** · **doença de Kawasaki** · miocardite.
*"Todos esses entram dentro de miocardiopatias."*
E mais: **cardio-oncologia é vista pelo grupo de miocardiopatias** (*"Dr. Fábio Fernandes, do
INCOR, é o titular da miocardiopatia e é quem mais fala no Brasil sobre cardio-oncologia,
sarcoidose, amiloidose"*) → por isso `Cardio-Oncologia` costuma ter `Miocardiopatias` como 2º
(casos 7, 30).
E ainda: **doença congênita do adulto cursa com miocardiopatia**, via VD e hipertensão pulmonar
(caso 23). E **doença reumatológica** → pericardite/miocardite + vasculite acelerando
aterosclerose (caso 21).

**D · ANTICOAGULANTE: mecanismo ≠ uso clínico.**
Biologia da hemostasia, ativação plaquetária, parede vascular → `Cardiometabólica` (caso 32).
**USO CLÍNICO de anticoagulante** → `Arritmias/Anticoagulantes`, **mesmo sem arritmia nenhuma**
(caso 36: *"não tem nada a ver com arritmia, mas tem a ver com os anticoagulantes"*).

**E · CONTEXTO CLÍNICO GANHA DE ÓRGÃO.**
Gravidez → `Cardio-Obstetrícia` 1º, doença como 2º (caso 17).
Pediátrico → `Aorta/Congênitas/Genética` como 2º (casos 25, 29).
AVC agudo e parada → `UTI Cardiológica` 1º, e *"a hipertensão aqui é secundária: é pressão de
perfusão, estou falando de manter cérebro viável"* (caso 34).
⚠️ **Exceção que me surpreendeu (caso 15):** cuidado antenatal para risco CV de longo prazo →
`Aorta/Congênitas/Genética`, **não** Cardio-Obstetrícia. *"Se é uma avaliação de risco antenatal,
é avaliação genética ou congênita."*

**F · SOBREVIVENTE DE CÂNCER É CARDIO-ONCOLOGIA, mesmo anos depois.**
*"doxorrubicina, antineoplásicos e quimioterapia induzem perda de complacência arterial e
envelhecimento precoce do vaso; os eventos podem começar entre 5 e 10 anos após o término do
tratamento"* (caso 24).

---

# ⬜ AS QUATRO DECISÕES — falta o martelo do dono

Tudo acima é medição e regra dele. Estas quatro mudam arquitetura, e são LEI 6: eu não decido.

### D1 · A ORDEM — quem decide o tema?
Hoje o **MeSH decide** e o LLM só entra quando não há descritor. Medido: MeSH chega ao leitor
certo em 65 %, LLM em 85 %. **A arquitetura está invertida em relação ao que os números mostram.**

| opção | como fica | custo |
|---|---|---|
| **A (recomendada)** | LLM decide · MeSH entra como 2º tema e desempate | ~US$0,0006/artigo (medido: US$0,12 em 186) |
| B | MeSH decide, e o LLM confere quando discordam | dobra a chamada nos discordantes |
| C | fica como está e conserta só o mapa | grátis, mas o teto continua sendo 65 % |

⚠️ **Contra-argumento honesto:** o MeSH é determinístico e humano (atribuído pela NLM); o LLM
varia entre rodadas. Trocar um pelo outro troca precisão por reprodutibilidade. A opção A mitiga
isso mantendo o MeSH como 2º tema — que é justamente onde ele é bom.

### D2 · ONDE AS REGRAS ENTRAM
Proposta: **nas duas pontas** — prompt do `tema_llm.py` (a regra "quem lê" + A–F) e o
`mesh_para_tema.json` (a lista do ambulatório de miocardiopatias, os 3 temas de método, HP → Mio).
Só numa ponta = a outra continua decidindo sozinha = LEI 9.

### D3 · `tema_origem` quando ninguém classifica
Precisa de `ALTER TABLE` (o CHECK só aceita mesh/llm/manual). **Recomendo migrar** para aceitar
`nao_classificavel`. Reusar `manual` faria a palavra significar duas coisas.

### D4 · REMEDIR NOS MESMOS 40
Sem remedir, "consertei" é opinião minha. O gabarito dele já está salvo; o `placar_tema.py` roda
de novo em segundos e de graça. **Meta declarada ANTES de mexer: ★ ≥ 90 %** — e se não chegar,
é para dizer que não chegou, não para mexer na régua até fechar.

---

# ✅ DECIDIDO E MEDIDO — o tripé entra (20/Ago/2026)

| decisão | resposta dele |
|---|---|
| D1 · ordem | **LLM decide, MeSH vira 2º tema e desempate** |
| D2 · onde as regras entram | **nas duas pontas** (prompt + mapa) |
| D3 · `nao_classificavel` | **não existe.** *"Inadmissível não ter tema — então não é cardiologia e medicina, estamos falando do cosmo."* → o TRIPÉ decide, e quando ele não fecha é `fora_do_escopo` |
| D4 · remedir | feito, nos mesmos 40, com a meta declarada ANTES |

## O RESULTADO — medido, não estimado

| régua | MeSH (antes) | TRIPÉ (agora) |
|---|---|---|
| 1º tema idêntico | 70 % | 77 % |
| **★ chega ao leitor certo** | **80 %** | **92 %** (37/40) |
| `fora_do_escopo` indevido | — | **0** |

Meta declarada antes de mexer: **90 %**. Bateu.
Custo: **US$ 0,0008/artigo** — menos de US$ 0,50 no acervo inteiro.

⚠️ **A ressalva estatística fica junto do número, sempre:** 37/40 tem IC95% de ~79 % a 98 %.
É "37 de 40 nesta amostra", não "o sistema acerta 92 %". Quem disser a segunda coisa está
repetindo o erro de 17/Ago, quando eu chamei cobertura de acerto.

## AS 3 CORREÇÕES DE GABARITO — e por que não são maquiagem

Estão em `outputs/_PROVA_TEMA/correcoes_gabarito.json`, **cada uma com o motivo escrito**:

| caso | por quê |
|---|---|
| PET (11) | fato do artigo: o método é Rb-82, não cateterismo. Ele marcou pelo título |
| Antenatal (15) | ele confundiu com o caso 25 (RM fetal) ao marcar; viu os dois lado a lado |
| **COVID (36)** | **ele retirou o PRÓPRIO gabarito** ao ver os MeSH |

### 🔴 A REGRA QUE NASCEU DO CASO 36 — o gabarito tem de ser alcançável pelo artigo

Ele tinha marcado `Miocardiopatias` para o artigo de anticoagulação na COVID, por uma cadeia
real: anticoagulação → previne TEP → TEP → hipertensão pulmonar → falência de VD. Ao abrir o
PubMed e ver os descritores (`Anticoagulants/administration`, `COVID-19 Drug Treatment`,
`Hospitalization`, `SARS-CoV-2` — **nenhum** de miocárdio, pericárdio ou HP), ele mesmo desfez:

> *"estou usando um conhecimento muito amplo que adquiri durante a pandemia para decidir —
> para mim é quase medular... mas não vejo indícios fáceis de definir como miocardiopatia."*

E anexou o Ackermann (NEJM 2020, endotelite vascular pulmonar na COVID) — **outro artigo**, que
é onde aquele raciocínio de fato mora.

**A regra:** se para chegar ao tema é preciso conhecimento que o TEXTO não carrega, o sistema
não pode chegar lá e não deve. Senão o gabarito mede a distância entre o modelo e a cabeça do
Dr. Eduardo, não entre o modelo e o artigo — e o classificador seria ajustado para perseguir
uma coisa que ele não tem como ver.

## AS 3 QUE RESTAM (e duas nem são erro)
- anti-PF4 e ECG do amiloide → ele mesmo disse *"cabem as duas coisas"*
- doença reumatológica → ele diz Miocardiopatias (pericardite/miocardite); o sistema diz
  Coronária+Cardiometabólica, e tem argumento: o artigo é sobre ativação plaquetária e risco
  cardiovascular, não sobre pericárdio. **Fica em aberto para a revisão dos 800.**

---

# 📌 PONTO DE REVISÃO — AOS 800 ARTIGOS NO SUPABASE

**Decisão dele, 20/Ago:** *"a título de ajuste — assim que bater 800 artigos no Supabase,
faremos uma revisão buscando melhorias."*

Hoje: **616**. Faltam **184**.

O que se mede naquele dia (e não antes, para não virar ajuste sobre ruído):

| # | o que olhar | por quê |
|---|---|---|
| 1 | novo gabarito cego, amostra maior | 40 dá IC de ~20 pontos. 100 fecha para ~±8 |
| 2 | distribuição por tema | Cardiometabólica levava 33 % das diretrizes — ver se ainda atrai |
| 3 | as 3 em aberto | reumatológica · anti-PF4 · ECG do amiloide |
| 4 | quantos `fora_do_escopo` de verdade | se aparecer muito, o classificador de TIPO está deixando entrar lixo |
| 5 | MeSH como 2º tema — está ajudando? | medir se o par melhora com ele ou se ele só polui |
| 6 | os 3 eixos do tripé | quais combinações aparecem, e se alguma nunca é usada |
