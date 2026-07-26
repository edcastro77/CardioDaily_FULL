# CLAUDE.md - Instrucoes do Projeto CardioDaily
## Versão 2.0 | 22/Mai/2026

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

**Arquivo do prompt:** `src/prompts/prompt_artigo_original_v2.md` — regra 0 e 0b

---

### LEI 1: NUNCA PROPOR ABANDONAR PARTE DO PROJETO
- O Claude NUNCA deve sugerir abandonar, descontinuar, remover ou desistir de qualquer funcionalidade planejada ou em desenvolvimento do CardioDaily.
- Se uma abordagem tecnica nao funciona, o Claude deve propor ALTERNATIVAS, nunca eliminacao.
- "Abandonar a ideia" NAO e uma opcao. Sempre existe uma solucao — encontre-a.
- O dono do projeto (Dr. Eduardo) decide o que entra e o que sai. O Claude executa e resolve.

### LEI 2: RESOLVER, NAO DESISTIR
- Diante de dificuldades tecnicas, o Claude deve:
  1. Identificar o problema real
  2. Propor 2-3 alternativas viaveis
  3. Recomendar a melhor opcao
  4. NUNCA listar "abandonar" como uma das opcoes

### LEI 3: RESPEITAR A VISAO DO PRODUCT OWNER
- O Dr. Eduardo define o que o CardioDaily deve fazer e como deve parecer.
- O Claude implementa a visao do dono, nao substitui por sua propria opiniao.
- Se o Claude discorda tecnicamente, apresenta a ressalva MAS executa o que foi pedido.

### LEI 4: O QUE PASSA ADIANTE VIVE NO FULL (LAB → FULL É OBRIGATÓRIO, NÃO OPCIONAL)

- O **CardioDaily_LAB** é a oficina: construir, testar, discutir, e refazer se o Dr. Eduardo não gostar.
- Mas **uma vez que uma mudança "passa adiante" (é aprovada), ela OBRIGATORIAMENTE tem que estar no
  CardioDaily_FULL** — no repositório, commitada, no `main`. O FULL é a fonte da verdade da produção.
- É **PROIBIDO** deixar aprovado no LAB como órfão. Nada de "está pronto, mas só na pasta do LAB". Se está
  pronto, está no FULL. Fim.
- Por isso o Claude **NUNCA pergunta** "quer que eu migre pro FULL?". Migrar o que foi aprovado é dever,
  não pergunta. O Claude migra, testa que não quebra produção, e avisa que subiu.
- A única coisa que fica no LAB é o que **ainda está em construção ou não foi aprovado**. No instante em
  que o Dr. Eduardo aprova, o destino é o FULL.
- Ordem de trabalho: construir/testar no LAB → Dr. Eduardo aprova → **Claude migra pro FULL (commit no
  main) sem esperar ser mandado** → confirma. Aposentar o caminho antigo faz parte da migração.

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

**Arquivo de referencia historica**: `src/infographics/templates/whatsapp_card.html` — NAO usar em producao.

---

### ARTEFATOS VISUAIS PERMITIDOS — LEI ABSOLUTA

São permitidos DOIS artefatos visuais, e SÓ estes dois:

**1. Visual Abstract de 8 seções** (artigos originais, meta, revisão — a maioria):
- Arquivo: `src/infographics/visual_abstract_generator.py`
- Template: `src/infographics/templates/visual_abstract_template.html`
- Output: `assets/visual_abstract.png`

**2. Fluxograma de conduta em Mermaid** (EXCLUSIVO da trilha MINIRREVISÃO / opinião de especialista) —
   aprovado pelo Dr. Eduardo em 25/07/2026:
- Motor: **Mermaid**, tematizado CardioDaily (azul #0B3D91 / vermelho #C00000, Helvetica), renderizado
  offline (mmdc / mermaid-cli).
- Por que Mermaid e NÃO HTML/CSS: o layout é do motor → consistência garantida, nunca "quebra feio".
  Foi a variabilidade do HTML/CSS feito à mão (caixa vazia, texto de tamanho variável) que reprovou os
  cards — o mesmo princípio do buraco zero. É o ÚNICO uso permitido de fluxograma.
- Escopo: só a trilha minirevisão. NÃO usar fluxograma em artigo original/meta.

**TODOS os outros geradores de imagem/gráfico estão em QUARENTENA PERMANENTE:**
- `InfographicPortrait` (portrait_visualmed) — PROIBIDO
- `MindmapGenerator` visual PNG — PROIBIDO
- `infographic_mpl.py` (matplotlib) — PROIBIDO
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
4. **Arquivos removidos**: `src/dalle_image_generator.py` e `src/image_prompt_generator.py` foram movidos para `archive/legacy_images/`.

**Regra**: Nenhum codigo do CardioDaily deve usar DALL-E para geracao de infograficos. Se precisar de geracao de imagem, usar alternativas que consigam renderizar dados reais (Gemini Imagen com prompts estruturados, SVGs programaticos, HTML/CSS renderizado).

---

## META DO PROJETO

- **TESTE BETA:** Abril 2026 — sistema funcional para 10 medicos avaliarem (Eduardo Lapa/CardioPapers + convidados)
- **LANCAMENTO:** Maio 2026 — inicio das vendas
- **Caderno de execucao completo:** `docs/CADERNO_EXECUCAO.md` (v12.0)

## ESTRUTURA DO PROJETO

- `/src/` - Codigo fonte principal
- `/src/infographics/` - Geradores de infograficos e mapas mentais (Playwright + Jinja2)
- `/scripts/` - Scripts de execucao em lote
- `/docs/` - Documentacao (inclui CADERNO_EXECUCAO.md v12.0)
- `/outputs/corpus/` - Artigos analisados (doi_XXXXX/)
- `/ARTIGOS/` - Classificador e PDFs novos
- `/archive/` - Codigo descontinuado

## STACK TECNICA

- Python 3
- Claude Sonnet 4 (analise de revisoes/guidelines + extracao JSON para mapas mentais)
- Gemini 2.5 Pro (analise de originais/meta-analises)
- Gemini 2.0 Flash (classificacao visual)
- OpenAI GPT-4o (script de podcast)
- OpenAI TTS-HD voz onyx (audio de podcast)
- Playwright + Jinja2 (infograficos e mapas mentais visuais — HTML/CSS → PNG 1920x1080)
- Supabase (banco de dados — 2.700+ artigos, taxonomia 73 categorias EN)

## ESTADO ATUAL DO SISTEMA (Fev/2026)

| Componente | Status |
|---|---|
| Classificador v8.0 (Gemini Vision) | ✅ 98%+ acuracia |
| Analise Claude Sonnet 4 (revisoes) | ✅ Operacional |
| Analise Gemini 2.5 Pro (originais) | ✅ Operacional |
| Mapa mental visual v3 (Claude + Playwright) | ✅ Nota 9/10 |
| Podcast (GPT-4o script + TTS-HD audio) | ✅ 240 gerados |
| Indexacao Supabase | ✅ 2.700+ artigos |
| **Infografico rico (estilo NotebookLM)** | **🔴 PENDENTE CRITICO** |
| **Administrador/Bibliotecario** | **🔴 PENDENTE CRITICO** |
| Telegram Bot | ⏳ Nao implementado |
| Templates Instagram (Reel/post) | ⏳ Nao implementado |

## 4 BLOCOS DE TRABALHO (cronograma no CADERNO_EXECUCAO.md)

1. **BLOCO 1: CONTEUDO** — Pipeline de analise (✅ quase completo, falta infografico rico)
2. **BLOCO 2: ADMINISTRADOR** — Bibliotecario inteligente + automacao redes sociais
3. **BLOCO 3: DISTRIBUICAO** — Telegram Bot, Instagram, WhatsApp
4. **BLOCO 4: FEEDBACK BETA** — 10 testers, formulario, metricas

## CLI

```bash
./cardiodaily [comando]
# classify, analyze, originals, reviews, meta, archive, pdf, infographic, audit, report, radar
```

## PACOTE CANONICO

```
outputs/corpus/{doc_id}/
├── source.pdf              # PDF original
├── analysis.md             # Analise completa
├── analysis.json           # Metadados estruturados
├── mindmap.md              # Mapa mental Markdown
└── assets/
    ├── mindmap.png         # Mapa mental visual (Claude Sonnet 4 + Playwright)
    ├── mindmap_data.json   # Cache JSON do Claude
    ├── infografico.png     # 🔴 PENDENTE (rico, estilo NotebookLM)
    └── podcast.mp3         # Podcast (score >= 8)
```
