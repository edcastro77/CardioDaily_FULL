# CLAUDE.md - Instrucoes do Projeto CardioDaily

## LEIS INVIOLAVEIS DO PROJETO

Estas regras sao ABSOLUTAS e nao podem ser quebradas em nenhuma circunstancia:

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

### ÚNICO ARTEFATO VISUAL PERMITIDO: VISUAL ABSTRACT 8 SEÇÕES — LEI ABSOLUTA

**ÚNICO formato visual de artigo permitido no CardioDaily é o Visual Abstract de 8 seções:**
- Arquivo: `src/infographics/visual_abstract_generator.py`
- Template: `src/infographics/templates/visual_abstract_template.html`
- Output: `assets/visual_abstract.png`

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
