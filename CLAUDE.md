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
