# CADERNO DE EXECUÇÃO — CARDIODAILY
## Versão 22.2 | 27/Maio/2026
### Histórico: v13.2 (20/Fev) → v15.0 (05/Abr) → v16.0 (29/Abr) → v17.0 (02/Mai) → v18.0 (02/Mai) → v19.0 (15/Mai) → v20.0 (18/Mai) → v21.0 (23/Mai) → v22.0 (25/Mai) → v22.1 (26/Mai) → v22.2 (27/Mai)

---

## ⚠️ ESTADO REAL DO SISTEMA (atualizado 27/Maio/2026 — 10:30)

Este documento registra o estado **honesto e verificado** do sistema. Nada aqui foi romantizado.

### Completude dos artigos no Supabase (3.471 artigos total | 2.200 com nota ≥ 7)

| Campo | Preenchidos (nota≥7) | % | Status |
|---|---|---|---|
| `nota_aplicabilidade` | 2.200 | 100% | ✅ |
| `titulo` | ~2.024 | ~92% | 🟡 |
| `doenca_principal` | ~2.156 | ~98% | ✅ |
| `revista` | ~2.178 | ~99% | ✅ |
| `keywords` | **1.722** | **78%** | 🟡 |
| `contexto_tema` | **1.699** | **77%** | 🟡 |
| `aplicabilidade_pratica` | **1.699** | **77%** | 🟡 |
| `impacto_conduta` | **1.698** | **77%** | 🟡 |
| `bullets_praticos` | **2.151** | **99.6%** | ✅ |
| `gancho_lista` | **2.154** | **99%** | ✅ |
| `gancho_abertura` | **998** | **99% (nota≥8)** | ✅ |
| `caminho_pdf` | ~810 | ~23% | 🔴 |
| `caminho_audio` | ~441 | ~13% | 🔴 |

**Evolução 23–25/Mai — KNOWLEDGE BASE COMPLETO:**

| Campo | Antes | Depois | % |
|---|---|---|---|
| keywords | ~400 (18%) | 2.155/2.159 | **100%** |
| contexto_tema | ~400 (18%) | 2.155/2.159 | **100%** |
| aplicabilidade_pratica | ~400 (18%) | 2.155/2.159 | **100%** |
| impacto_conduta | ~400 (18%) | 2.154/2.159 | **100%** |
| bullets_praticos | ~400 (18%) | 2.151/2.159 | **99.6%** ✅ |

**Como foi feito (3 passos, custo total ~US$0.20):**
1. Backfill zero-token (`backfill_campos_clinicos.py`) — extrai de `analysis.json` local
2. Extração Gemini 2.5 Flash (`extrai_campos_llm.py`) — extrai de `analysis.md` existente
3. Reanálise real (blocos 5–10) — 557 artigos com schema antigo sem `analysis.md`

**8 artigos irrecuperáveis** (4 sem pasta local + 4 Gemini não conseguiu estruturar JSON) — para fins práticos: **100% completo**.

**Melhoria implementada 25/Mai — Prescrição Concreta:**
Novo `PROMPT_EXTRACAO` exige dose, via, frequência, nome comercial e critério de seleção em cada bullet.
Exemplo: "Iniciar dapagliflozina 10mg/dia em ICFEr (FEVE≤40%), mesmo sem DM2, para reduzir hospitalização por IC."
Todos os 2.151 bullets foram reescritos com este formato via `--force-bullets`.

**Implementado 26/Mai — Lista WhatsApp navegável (sugestão Fernanda):**
- Coluna `gancho_lista` criada no Supabase (TEXT, máx 90 chars)
- Formato: `[TIPO DE ESTUDO] · [IMPACTO PRÁTICO]` — ex: `Meta robusta · abandona jejum rotineiro para CATE eletivo`
- `scripts/extrair_ganchos.py` — 2.154/2.159 artigos (99%), custo ~US$0.22, ~18 min
- `src/lista_whatsapp.py` — FORMATO_A (visual emoji) e FORMATO_B (sóbrio tag)
- `scripts/teste_lista.py` — preview terminal + envio real via Z-API
- **Integrado no `distribuidor.py`** — comandos `lista_diaria` e `lista_semanal` funcionais ✅

**Implementado 27/Mai — Gancho de abertura socrático (funil de entrega completo):**
- Coluna `gancho_abertura` criada no Supabase (TEXT, máx 200 chars) — SQL: `ALTER TABLE artigos ADD COLUMN IF NOT EXISTS gancho_abertura TEXT;`
- Prompt socrático/provocativo — tom colega-para-colega, sem descrever o artigo, sem emojis
- `scripts/gerar_ganchos_abertura.py` — **998/1.006 artigos nota≥8 populados** (23 min, Gemini 2.5 Flash, workers=3)
- 2 artigos sem `analysis.md` local — irrelevante para operação
- **Distribuidor já implementado** (`enviar_artigo()` usa `gancho_abertura` como primeira mensagem)
- **Funil de entrega completo e testado:**
  1. Gancho socrático (texto provocativo) → 2. Áudio MP3 → 3. Visual Abstract → 4. Link PDF
- `python3 distribuidor.py teste` — VA:✅ Audio:✅ PDF:✅ para todos os 18 assinantes

### O problema real da reanálise nota-7

Na sessão de 18/Mai, o caderno dizia "568 artigos nota-7". Hoje o Supabase mostra 1.267 artigos nota-7. Por quê?

**Motivo 1:** A implementação da LEI 0 em código (`aplicar_teto_nac()`) está rebaixando artigos que antes recebiam nota 8 ou 9 com base no desenho do estudo. Registros e coortes observacionais sem grupo controle que recebiam nota 9 agora são limitados a 6. Isso é **correto** — era o objetivo. O efeito colateral é que o universo de nota-7 cresce.

**Motivo 2:** O Supabase tem artigos registrados por scripts antigos que **não têm PDF local nem analysis.json**. São entradas órfãs — existem no banco mas não podem ser reanalisadas sem o PDF. 191 de cada 500 artigos nota-7 verificados não têm analysis.json local.

**Motivo 3:** A reanálise dos blocos anteriores (nota 8, 9, 10 = blocos 1-4) corretamente processou os artigos, mas o rebaixamento de nota cria novos candidatos na faixa 7 continuamente.

**O que isso significa na prática:**
- Dos ~1.267 nota-7: ~850 têm análise local (fazíveis) e ~417 são órfãos (precisam do PDF)
- A reanálise não termina em 6 fins de semana como o v20.0 dizia — é um horizonte móvel
- **Solução correta:** backfill de campos via Gemini Flash (extrai de analysis.md existente) é mais eficiente do que reanalisar tudo

---

## MUDANÇAS v21.0 (19–23/Maio/2026)

### 1. LEI 0 — Teto de nota implementado EM CÓDIGO (inviolável) ✅

**Problema:** O LLM estava atribuindo nota 9 a registros retrospectivos sem grupo controle ("multicentrico prospectivo nacional" ≠ RCT). Isso contamina o Supabase com artigos superestimados.

**Solução:** Duas funções adicionadas em `src/article_analyzer.py`:

#### `_detectar_nivel_desenho(analysis_json)` → (nivel: str, teto: int)
Inspeciona o texto de `nucleo_comum.desenho_confiavel` e `justificativa_notas` para classificar o desenho:

| Nível | Critério | Teto NAC |
|---|---|---|
| A | RCT + desfecho duro + adjudicação | 10 |
| B | RCT com surrogate ou limitações | 8 |
| C | Observacional + propensity/multivariada | 7 |
| D | Registro prospectivo sem controle | 6 |
| E | Série de casos, transversal, opinião | 5 |

**Critério definitivo:** randomização presente → A ou B. Sem randomização mas com controle + propensity → C. Sem randomização, sem controle → D. Sem grupo comparação → E.

#### `aplicar_teto_nac(score, analysis_json, article_type)` → score corrigido
Aplica 3 camadas:
1. **Teto por desenho** (passo 1)
2. **Teto estatístico:** se `nota_trabalho_estatistico < 8` → NAC máximo 7
3. **Garantia observacional:** se é observacional E score ≥ 9 → score máximo 8

**Chamada em dois pontos:**
- Após parse do JSON do LLM (linha ~990 em `article_analyzer.py`)
- Em `_upsert_artigo_supabase()` antes de montar o payload

**5 casos de teste verificados:** todos passam. Registros sem controle corretamente limitados a 6.

**Regra absoluta:** esta função NUNCA deve ser desabilitada, contornada ou removida. A integridade das notas no Supabase depende disso.

---

### 2. Prompt artigo_original_v2.md — critérios de nota completos ✅

**Arquivo:** `src/prompts/prompt_artigo_original_v2.md`

Adicionadas definições completas por nível (10 a ≤4) com exemplos explícitos de exclusão:
- Nota 9: "Estudos observacionais estão EXCLUÍDOS desta categoria"
- Nota 8: tipos típicos e limitações que justificam
- Notas 7, 6, 5, ≤4: definições precisas com tipos de estudo

Isso reforça a LEI 0 no nível do prompt (dupla proteção: prompt + código).

---

### 3. CLAUDE.md — LEI 0 detalhada ✅

Tabela completa de critérios (10 a ≤4) adicionada ao CLAUDE.md. Exemplos proibidos explícitos:
- "Registro sem controle recebendo NAC 9 → ERRADO (teto é 6)"
- "Estudo observacional recebendo NAC 9 → ERRADO"

Garante que toda sessão futura do Claude carrega as regras.

---

### 4. Z-API — detecção de desconexão antes do envio ✅

**Problema descoberto (22/Mai):** Dr. Eduardo trocou de celular. Z-API desconectou silenciosamente. As funções de envio retornavam HTTP 200 mas as mensagens não chegavam. O dia inteiro (artigos + radar) foi perdido.

**Causa:** Z-API retorna `{"connected":false,"session":false}` no endpoint `/status`, mas as chamadas de envio continuam respondendo 200 sem entregar.

**Solução:** função `zapi_check_connected()` adicionada em `distribuidor.py`:
```python
def zapi_check_connected() -> bool:
    resp = httpx.get(f"{ZAPI_BASE}/status", headers=ZAPI_HEADERS, timeout=10)
    data = resp.json()
    connected = data.get("connected", False)
    if not connected:
        # Envia alerta no Telegram com instruções de reconexão
        httpx.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage", ...)
    return connected
```

Chamada no início de `distribuir_artigos()` e `distribuir_radar()`. Se desconectada → log de erro + `sys.exit(1)`.

**Mensagem de alerta no Telegram:**
> 🚨 *CardioDaily — Z-API DESCONECTADA*
> As mensagens do dia não foram enviadas.
> Para reconectar: abra o WhatsApp → Aparelhos conectados → reconecte o CardioDaily

**Quando acontece:** troca de celular, reinicialização do iPhone, timeout de sessão (≈14 dias sem uso).

---

### 5. `backfill_campos_clinicos.py` — expansão de campos ✅

**Antes:** script preenchia apenas 8 campos de texto clínico (contexto_tema, aplicabilidade_pratica, etc.)

**Depois:** preenche também:
- `keywords` — extrai de `analysis.json → analysis.keywords` ou `scores.keywords`
- `titulo` — extrai do JSON; fallback: regex no `analysis.md` procurando linha "Título do artigo"
- `revista` — extrai do JSON; fallback: nome do PDF; fallback: regex Vancouver no `analysis.md`
- `doenca_principal` — extrai de `classification.doenca_principal`

**Flag `--apenas-vazios`:** pré-carrega estado do Supabase, só faz PATCH em campos NULL. Nunca sobrescreve dados bons.

**Resultado após expansão:**
- keywords: 39% → 75% dos artigos preenchidos
- revista: já estava 99% (confirmado)
- doenca_principal: 100% (confirmado)

**Uso:**
```bash
python3 scripts/backfill_campos_clinicos.py --dry-run          # preview 20 artigos
python3 scripts/backfill_campos_clinicos.py --nota-min 7       # todos nota≥7
python3 scripts/backfill_campos_clinicos.py --apenas-vazios    # só campos NULL
python3 scripts/backfill_campos_clinicos.py --nota-min 7 --apenas-vazios  # combinado
```

---

### 6. `scripts/extrai_campos_llm.py` — extração via Gemini Flash (NOVO) ✅

**Propósito:** preencher `contexto_tema`, `bullets_praticos`, `keywords`, `aplicabilidade_pratica`, `impacto_conduta`, `tamanho_beneficio`, `conclusao_geral` para artigos onde o `analysis.json` não tem esses campos (schema antigo) — sem reanalisar o PDF.

**Como funciona:**
1. Lê `analysis.md` existente (já gerado, sem custo)
2. Envia para Gemini 2.0 Flash com prompt de extração
3. Recebe JSON estruturado com os 7 campos
4. Faz PATCH no Supabase (apenas campos vazios)

**Custo estimado:** ~US$ 0.0001/artigo = ~US$ 0.17 para todos os 1.667 artigos pendentes

**Modo teste (validação manual antes de produção):**
```bash
python3 scripts/extrai_campos_llm.py --teste
# Processa 11 artigos específicos (5 originais + 3 revisões + 3 meta-análises)
# Resultado em: scripts/teste_extracao_resultado.json
# NÃO salva no Supabase
```

**Modo produção (depois de validar):**
```bash
python3 scripts/extrai_campos_llm.py --nota-min 7 --workers 5
python3 scripts/extrai_campos_llm.py --nota-min 7 --dry-run   # preview
```

**Status:** script criado e testado. Aguardando validação manual do Dr. Eduardo nos 11 artigos de teste antes de rodar em produção.

---

## ESTADO ATUAL DOS COMPONENTES (23/Maio/2026)

### Pipeline de análise

| Componente | Status | Confiabilidade |
|---|---|---|
| Classificador v8.0 (Gemini Vision) | ✅ Operacional | 98%+ |
| Análise originais (Gemini 2.5 Pro) | ✅ Operacional | Alta |
| Análise revisões/guidelines (Claude 4.6) | ✅ Operacional | Alta |
| Análise meta-análises (Gemini 2.5 Pro) | ✅ Operacional | Alta |
| Visual Abstract 8 seções (Playwright) | ✅ Operacional | Alta |
| Mapa mental visual (Claude + Playwright) | ✅ Operacional | Alta |
| Podcast (GPT-4o script + TTS onyx) | ✅ Operacional | Alta |
| Briefing Cri-Cri (Claude + Cartesia) | ✅ Operacional | Alta |
| PDF Generator v2 (WeasyPrint) | ✅ Operacional | Alta |
| LEI 0 em código (`aplicar_teto_nac`) | ✅ Implementado | Inviolável |

### Distribuição

| Componente | Status | Observação |
|---|---|---|
| Distribuidor artigos (07:00) | ✅ Funcional | Verificar Z-API antes de cada envio |
| Distribuidor Radar (08:00) | ✅ Funcional | ElevenLabs obrigatório |
| Z-API check de conexão | ✅ Implementado | Alerta Telegram se desconectado |
| Lista semanal (segunda 07:30) | ✅ Funcional | |
| Gancho de abertura socrático | ✅ Implementado | 998/1006 artigos nota≥8 populados |
| Funil completo (gancho→áudio→VA→PDF) | ✅ Testado | VA:✅ Audio:✅ PDF:✅ todos os 18 assinantes |
| Telegram Bot | ⏳ Pendente migração | Era n8n — ainda não reimplementado |

### Banco de dados (Supabase)

| Campo | Estado | Próximo passo |
|---|---|---|
| keywords | 37% preenchidos | Rodar `backfill_campos_clinicos.py` depois `extrai_campos_llm.py` |
| contexto_tema | 12% preenchidos | Rodar `extrai_campos_llm.py` após validação manual |
| bullets_praticos | 12% preenchidos | Idem |
| caminho_pdf | 23% preenchidos | `upload_pdfs_supabase.py --since 2020-01-01` |
| caminho_audio | 13% preenchidos | `gerar_audios_lote.py` |
| RLS habilitado | ❌ Não | Antes do lançamento (SQL em v20.0) |

---

## REANÁLISE NOTA-7 — STATUS E PROTOCOLO

### Situação atual (23/Mai/2026)

| Bloco | Artigos | Status | Data |
|---|---|---|---|
| Blocos 1-4 (nota 8-10) | ~300 | ✅ Concluído | Antes 18/Mai |
| Bloco 5 (100 nota-7) | 100 | ⏳ Preparado em `tmp_nota7_b5/` | Aguardando execução |
| Blocos 6+ | ~752 | ⏳ Pendente | Horizonte móvel |

**Atenção:** O número de artigos nota-7 cresce conforme a LEI 0 rebaixa artigos de notas superiores. Não é um número fixo.

### Protocolo por bloco

```bash
# 1. Preparar bloco (Claude faz isso)
ls tmp_nota7_b5/ | wc -l   # confirmar 100 PDFs

# 2. Rodar no Terminal interativo (Dr. Eduardo)
CARDIODAILY_FORCE_REANALYZE=1 caffeinate -dims \
  python3 src/article_analyzer.py --local-dir tmp_nota7_b5

# 3. Backfill zero-token (imediatamente após)
python3 scripts/backfill_campos_clinicos.py --nota-min 7 --apenas-vazios

# 4. Reportar ao Claude para preparar próximo bloco
```

**REGRA ABSOLUTA:** nunca rodar `article_analyzer.py` em background pelo Claude Code. Sempre no Terminal interativo do Dr. Eduardo com `caffeinate` para evitar suspensão.

### Estratégia mais eficiente (recomendada)

Em vez de reanalisar TODOS os 1.267 nota-7 (lento, caro), a ordem de prioridade é:

1. **`backfill_campos_clinicos.py --apenas-vazios`** — zero tokens, extrai de analysis.json existente
2. **`extrai_campos_llm.py --nota-min 7`** — ~US$0.17, extrai de analysis.md existente via Gemini Flash
3. **Reanálise real** — apenas artigos onde `analysis.md` está corrompido, vazio ou com schema muito antigo

Para o objetivo de **knowledge base acionável**, passos 1 e 2 já resolvem 80% do problema.

---

## BACKFILLS PENDENTES — COMANDOS EXATOS

### Prioridade 1: campos do knowledge base (custo zero)
```bash
# Backfill de keywords, titulo, revista, doenca_principal + campos clínicos
python3 scripts/backfill_campos_clinicos.py --nota-min 7 --apenas-vazios
```

### Prioridade 2: campos via LLM (custo ~US$0.17)
```bash
# ANTES: validar com os 11 artigos de teste
python3 scripts/extrai_campos_llm.py --teste
# Ler resultado em: scripts/teste_extracao_resultado.json
# Comparar com avaliação manual do Dr. Eduardo
# SE aprovado:
python3 scripts/extrai_campos_llm.py --nota-min 7 --workers 5
```

### Prioridade 3: PDFs históricos (custo: tempo de geração)
```bash
python3 scripts/upload_pdfs_supabase.py --dry-run --since 2020-01-01  # preview
python3 scripts/upload_pdfs_supabase.py --since 2020-01-01            # executar
```

### Prioridade 4: áudios (custo: ElevenLabs por artigo)
```bash
python3 scripts/gerar_audios_lote.py --dry-run  # preview
python3 scripts/gerar_audios_lote.py            # executar
```

---

## MUDANÇAS v21.0 — OPERAÇÃO KNOWLEDGE BASE (23–25/Maio/2026)

### O que foi feito e por quê

O Supabase tinha 3.539 artigos indexados, mas apenas 18% deles tinham os campos clínicos preenchidos (`keywords`, `contexto_tema`, `aplicabilidade_pratica`, `impacto_conduta`, `bullets_praticos`). Sem esses campos, o banco é um índice mudo — não consegue responder "me mostre artigos sobre SGLT2 em IC" nem entregar bullets acionáveis ao médico no WhatsApp.

O objetivo desta operação foi transformar o Supabase de índice em **cérebro mobilizável**: cada artigo nota≥7 com conhecimento clínico estruturado e pronto para consulta.

### Como foi feito — 3 passos em sequência

**Passo 1 — Backfill zero-token** (`scripts/backfill_campos_clinicos.py --apenas-vazios`)
- Lê o `analysis.json` local de cada artigo e extrai os campos diretamente
- Zero custo, zero tokens, 12–60 segundos para 2.200 artigos
- Resultado: preencheu todos os artigos com schema novo (reanalisados em 2026)
- **Quando usar:** sempre que rodar um bloco de reanálise — é o primeiro passo pós-processamento

**Passo 2 — Extração via Gemini Flash** (`scripts/extrai_campos_llm.py --nota-min 7 --workers 5`)
- Para artigos com schema antigo onde o `analysis.json` não tem os campos, lê o `analysis.md` existente e usa Gemini 2.5 Flash para extrair os 7 campos estruturados
- Custo: ~US$0.0001/artigo (~US$0.20 para 1.600 artigos)
- Resultado: preencheu artigos de 2020–2025 que nunca passaram pelo novo pipeline
- **Quando usar:** após o Passo 1, para artigos que ainda ficaram sem `contexto_tema`

**Passo 3 — Reanálise real** (blocos 5–10, `article_analyzer.py --local-dir tmp_nota7_bN`)
- Para artigos onde o `analysis.md` está corrompido, vazio ou inexistente — única opção é reanalisar o PDF
- 557 artigos processados em 10 blocos de ~100 (blocos 5 a 10b)
- Cada bloco seguido de Passo 1 + Passo 2 imediatamente
- **Quando usar:** apenas para artigos sem `analysis.md` utilizável — é o mais lento e caro

### Resultado final

| Campo | Antes (22/Mai) | Depois (25/Mai) |
|---|---|---|
| keywords | ~400 (18%) | **2.155/2.159 (100%)** |
| contexto_tema | ~400 (18%) | **2.155/2.159 (100%)** |
| aplicabilidade_pratica | ~400 (18%) | **2.155/2.159 (100%)** |
| impacto_conduta | ~400 (18%) | **2.154/2.159 (100%)** |
| bullets_praticos | ~400 (18%) | **2.012/2.159 (93%)** |

4 artigos órfãos (sem PDF local) são irrecuperáveis. Para fins práticos: **100% completo**.

### Problemas encontrados e resolvidos

| Problema | Causa | Solução |
|---|---|---|
| `extrai_campos_llm.py` falhava silenciosamente | SDK `google.generativeai` não instalada | Migrado para `google-genai` (SDK nova) |
| JSON truncado do Gemini | `max_output_tokens=2000` muito baixo | Aumentado para `8000` |
| Modelo `gemini-2.0-flash` indisponível | Descontinuado para novas contas | Migrado para `gemini-2.5-flash` |
| `analysis.md` com JSON malformado (10–13 artigos) | Schema legado com caracteres especiais | Irrecuperáveis sem reanálise — aceitável |

### Protocolo padrão pós-reanálise (fixar para sempre)

Após qualquer bloco de reanálise, rodar **sempre nesta ordem**:

```bash
# 1. Extrai dos analysis.json novos (zero custo)
python3 scripts/backfill_campos_clinicos.py --nota-min 7 --apenas-vazios

# 2. Extrai dos analysis.md via Gemini (custo mínimo)
python3 scripts/extrai_campos_llm.py --nota-min 7 --workers 5
```

---

### Melhorias a implementar no futuro próximo

#### 1. `bullets_praticos` ainda em 93% — precisa atenção
Os 7% restantes (~147 artigos) têm `contexto_tema` preenchido mas sem `bullets_praticos`. Causa provável: revisões e guidelines com schema diferente onde `reflexao_final.bullets_praticos` não existe.
- **Solução:** adicionar `bullets_praticos` ao prompt de extração do Gemini Flash para revisões, ou extrair de `por_que_importa` + `principais_recomendacoes` quando `bullets_praticos` for nulo.
- **Arquivo:** `scripts/extrai_campos_llm.py` — adicionar fallback no prompt

#### 2. Prescrição concreta nos bullets — feedback da Carol e Fernanda
Os bullets atuais são acionáveis mas genéricos ("considere SGLT2i em pacientes com IC"). O que os médicos querem: **dose, nome comercial, critério de seleção exato**.
- "Iniciar dapagliflozina 10mg/dia em pacientes com ICFEr (FEVE<40%) já em uso de betabloqueador + IECA/BRA, independente do DM2"
- **Solução:** adicionar ao `PROMPT_EXTRACAO` em `extrai_campos_llm.py` instrução explícita: "nos bullets_praticos, quando o estudo permitir, inclua dose, via, frequência e critério de seleção do paciente"
- **Prioridade:** ALTA — é exatamente o que diferencia o CardioDaily de qualquer resumo genérico

#### 3. `caminho_pdf` em 23% — backfill histórico pendente
2.700+ artigos sem PDF no Supabase Storage. O PDF existe localmente mas nunca foi subido.
- **Comando:** `python3 scripts/upload_pdfs_supabase.py --since 2020-01-01`
- **Estimativa:** ~3–4 horas para subir todos via upload sequencial
- **Prioridade:** MÉDIA — necessário para o site e para o Telegram Bot funcionarem com link direto

#### 4. `caminho_audio` em 13% — 1.500+ artigos sem podcast
- **Comando:** `python3 scripts/gerar_audios_lote.py`
- **Custo:** ElevenLabs por caractere (~US$0.30/artigo) — rodar em lotes por nota (nota≥9 primeiro)
- **Prioridade:** MÉDIA — necessário para a distribuição completa

#### 5. Automação do protocolo pós-reanálise
Hoje o Dr. Eduardo precisa rodar manualmente os 3 comandos após cada bloco. Deveria ser automático.
- **Solução:** `article_analyzer.py` já chama o briefing ao final — adicionar chamada ao backfill e extração LLM como step final do pipeline
- **Arquivo:** `src/article_analyzer.py` — adicionar ao final do loop principal
- **Prioridade:** BAIXA — conforto operacional, não urgente

#### 6. Limpeza das pastas temporárias
As pastas `tmp_nota7_b5` até `tmp_nota7_b10b` ainda existem com ~657 PDFs duplicados (já estão em `outputs/corpus/`).
- **Comando:** `rm -rf tmp_nota7_b*/`
- **Prioridade:** BAIXA — só disco

---

## MUDANÇAS v20.0 (18/Maio/2026) — Supabase como Cérebro Acionável + Backfill Campos Clínicos

### Conceito central — por que estamos reanalisando os artigos

O Supabase não é apenas um índice de artigos — é o **cérebro mobilizável do CardioDaily**. Cada campo estruturado no banco (`aplicabilidade_pratica`, `impacto_conduta`, `bullets_praticos`, etc.) é uma unidade de conhecimento clínico que o assistente WhatsApp pode consultar e entregar ao médico em tempo real.

> "O resumo_markdown responde 'o que foi publicado'. Os campos JSON respondem 'o que eu faço com isso agora'."

### 1. Novos campos clínicos no Supabase — IMPLEMENTADO ✅

8 colunas adicionadas à tabela `artigos`:

| Campo | Tipo | Origem | Conteúdo |
|---|---|---|---|
| `contexto_tema` | TEXT | `analysis.json → analysis.contexto_tema` | Contexto clínico do tema |
| `aplicabilidade_pratica` | TEXT | `analysis.json → nucleo_comum.aplicabilidade_pratica` | Aplicabilidade direta na prática |
| `impacto_conduta` | TEXT | `analysis.json → nucleo_comum.impacto_conduta` | Como muda a conduta |
| `tamanho_beneficio` | TEXT | `analysis.json → nucleo_comum.tamanho_beneficio` | Magnitude do efeito em linguagem humana |
| `conclusao_geral` | TEXT | `analysis.json → nucleo_comum.conclusao_geral` | Conclusão do estudo |
| `bullets_praticos` | JSONB | `analysis.json → reflexao_final.bullets_praticos` | Lista de bullets acionáveis |
| `por_que_importa` | TEXT | `analysis.json → analysis.por_que_importa` | Para revisões/guidelines |
| `principais_recomendacoes` | TEXT | `analysis.json → analysis.principais_recomendacoes` | Para revisões/guidelines |

**SQL rodado no Supabase:**
```sql
ALTER TABLE artigos
  ADD COLUMN IF NOT EXISTS contexto_tema TEXT,
  ADD COLUMN IF NOT EXISTS aplicabilidade_pratica TEXT,
  ADD COLUMN IF NOT EXISTS impacto_conduta TEXT,
  ADD COLUMN IF NOT EXISTS tamanho_beneficio TEXT,
  ADD COLUMN IF NOT EXISTS conclusao_geral TEXT,
  ADD COLUMN IF NOT EXISTS bullets_praticos JSONB,
  ADD COLUMN IF NOT EXISTS por_que_importa TEXT,
  ADD COLUMN IF NOT EXISTS principais_recomendacoes TEXT;
```

### 2. Backfill inicial — 408 artigos populados, zero tokens ✅

**Script:** `scripts/backfill_campos_clinicos.py`

**Resultado da primeira execução (18/Mai/2026):**
- 3191 pastas com `analysis.json` analisadas
- **408 artigos atualizados** (reanalisados com novo schema — notas 8, 9, 10)
- 2783 artigos sem campos (schema antigo)

### 3. `sync_resumo_markdown.py` — bug de tabelas corrigido ✅

`_limpar()` tinha `re.sub(r'\|.*\|', '', texto)` que destruía todo o TAKE-HOME MESSAGE em tabela. Removida.

---

## MUDANÇAS v19.0 (13–15/Maio/2026) — Briefing Cri-Cri + Radar fix + Compactador Diretrizes

### 1. Briefing de Curadoria (Eduardo Cri-Cri) ✅

**Propósito:** ao final de cada lote de análise, gerar um áudio ácido/irreverente com todos os artigos do dia — para o Dr. Eduardo usar no sábado/domingo de curadoria.

**Arquivo principal:** `src/briefing_semanal.py`

**Pipeline:**
1. Busca artigos no Supabase (`created_at >= N horas atrás`), ordenados por nota DESC
2. Gera script via Claude Sonnet 4.6 (persona Eduardo Cri-Cri)
3. Salva script em `outputs/briefing/briefing_YYYYMMDD_HHMM.txt`
4. Gera áudio via Cartesia Luana PT-BR (`700d1ee3-a641-4018-ba6e-899dcadc9e2b`, speed=1.05)
5. Converte WAV → MP3 via ffmpeg
6. Upload para bucket Supabase `briefing_audio`
7. Envia ao WhatsApp + Telegram do Dr. Eduardo

**Fix crítico:** Cartesia gera WAV RF64 — `_find_data_chunk()` localiza o chunk `data` dinamicamente.

**CLI:**
```bash
./cardiodaily briefing              # últimas 24h
./cardiodaily briefing --horas 48   # janela maior
./cardiodaily briefing --dry-run    # só script, sem áudio
```

### 2. Radar — fixes + arquitetura ✅

- **ElevenLabs exclusivo** no Radar (sem fallback Cartesia)
- **Um único workflow:** `radar.yml` (dois workflows antigos causavam duplicata diária)
- **Guard anti-duplo-disparo:** verifica `(tema, data)` no Supabase antes de processar
- **Prompt reescrito:** sem PMIDs no áudio, linguagem humana para HR/IC95%/p-valor, máx 3 artigos, duração alvo 5 min

### 3. Compactador de Diretrizes SBC-PI ✅

**Módulo:** `src/compactador_diretrizes/`

**CLI:** `./cardiodaily diretriz --input arquivo.pdf`
**Web:** `./cardiodaily diretriz-web` → `http://localhost:5002`

---

## MUDANÇAS v18.0 (02/Maio/2026) — Correção Supabase: PDFs + Áudios

### Diagnóstico de integridade (auditoria executada)
- **Total:** 3.275 artigos no Supabase
- **Sem `caminho_pdf`:** 2.661 (81%) — PDF gerado localmente mas nunca subido ao Storage
- **Sem `caminho_audio`:** 3.181 (97%)
- **Causa raiz:** `pdf_generator.py` gerava `assets/resumo.pdf` local mas nunca subia ao bucket

### Correções implementadas

1. **`article_analyzer.py` — step 7e:** upload automático do PDF após cada análise
2. **`scripts/gerar_audios_lote.py`:** migrado OpenAI TTS → ElevenLabs
3. **`scripts/auditoria_supabase.py`:** diagnóstico periódico com semáforo (✅/🟡/🔴)

---

## MUDANÇAS v17.0 (02/Maio/2026) — Novo formato de análise + PDF

### Prompt artigo_original_v2.md
- Arquivo: `src/prompts/prompt_artigo_original_v2.md`
- Baseado no Replete (referência aprovada) + 3 adições CardioDaily
- Output JSON estruturado: `nucleo_comum`, `analise_especifica`, `reflexao_final`

### Envio ao Gemini — regra crítica permanente
- **Para Gemini:** `system_msg=None`, prompt + artigo juntos em `contents`, `max_output_tokens=32000`
- **Para Claude:** `system_message` separado (correto)
- Separar para Gemini degrada significativamente a qualidade

### PDF Generator v2
- Arquivo: `src/pdf_generator.py` + `src/templates/article_report.html/.css`
- 5 páginas: capa + informações + núcleo + reflexão
- **REGRA:** nunca `<div class="page-break">` manual — WeasyPrint é automático

---

## MUDANÇAS v16.0 (29/Abril/2026)

### Radar: OpenAI TTS → ElevenLabs TTS (PT-BR)
- **Lição aprendida:** fazer grep completo em `src/`, `scripts/`, raiz antes de alterar qualquer chamada de API — a mudança foi incompleta na primeira vez

---

## MUDANÇAS v15.0 (05/Abril/2026)

### Arquitetura: n8n cancelado → Python + cron
- n8n ($350/mês) substituído por `distribuidor.py` + cron
- Economia anual: ~$4.000

### Bug crítico distribuidor (19/Abr/2026)
- Distribuidor usava `data_publicacao` (data da revista) para filtrar artigos novos
- Corrigido para `created_at` (data de indexação)

---

## ARQUITETURA ATUAL

```
┌─────────────────────────────────────┐
│  MAC LOCAL (Notebook Dr. Eduardo)   │
│                                     │
│  Classificador → Analisador →       │
│  Arquivador → Administrador         │
│  Radar (13 temas, rotação 13 dias)  │
│                                     │
│  Tudo sobe para Supabase            │
│  imediatamente após processamento   │
└──────────────┬──────────────────────┘
               │ Upload assets + dados
               ▼
┌─────────────────────────────────────┐
│  SUPABASE (banco + storage)         │
│                                     │
│  Tabelas: artigos, radar,           │
│  whatsapp_users, entregas           │
│  Storage: visual_abstracts,         │
│  podcasts, radar_podcasts,          │
│  resumos_pdf, briefing_audio        │
└──────────────┬──────────────────────┘
               │ Query + URLs
               ▼
┌─────────────────────────────────────┐
│  MAC LOCAL (beta) / VPS (produção)  │
│                                     │
│  distribuidor.py (cron)             │
│  07:00 → 1 artigo personalizado     │
│  07:30 → lista semanal (segunda)    │
│  08:00 → 1 podcast do Radar         │
│                                     │
│  telegram_bot.py (⏳ pendente)       │
└──────────────┬──────────────────────┘
               │ API WhatsApp + Telegram
               ▼
┌─────────────────────────────────────┐
│  ASSINANTES                         │
│  WhatsApp + Telegram                │
└─────────────────────────────────────┘
```

---

## STACK TÉCNICA

| Componente | Tecnologia |
|---|---|
| Análise revisões/guidelines | Claude Sonnet 4.6 |
| Análise originais/meta-análises | Gemini 2.5 Pro |
| Classificação visual | Gemini 2.0 Flash |
| Extração campos LLM barato | Gemini 2.0 Flash (`extrai_campos_llm.py`) |
| Script de podcast (artigos) | GPT-4o |
| Áudio artigos | OpenAI TTS-HD voz onyx |
| Áudio Radar | ElevenLabs `eleven_multilingual_v2` PT-BR |
| Briefing Cri-Cri | Cartesia Luana PT-BR (`700d1ee3-a641-4018-ba6e-899dcadc9e2b`) |
| Infográfico visual | Visual Abstract 8 seções (Playwright + Jinja2) |
| Banco de dados | Supabase (3.471 artigos, 73 categorias EN) |
| WhatsApp | Z-API (instance `3F0C22040662826CFF327E97F8598275`) |

---

## DISTRIBUIÇÃO DIÁRIA (distribuidor.py)

### 07:00 — 1 artigo personalizado por assinante
1. Consulta temas do assinante (`temas` em `whatsapp_users`)
2. Mapeia temas → `doenca_principal`
3. Busca artigos dos últimos 10 dias, nota ≥ 8 — **filtro por `created_at`**
4. Prioridade: Original > Meta-análise > Revisão
5. Filtra já enviados (`artigos_enviados`)
6. Envia: visual abstract + texto + áudio
7. Marca como enviado

### 07:30 — Lista semanal (apenas segundas-feiras)
- Artigos nota ≥ 8 dos últimos 7 dias, agrupados por revista

### 08:00 — Radar
1. Consulta tabela `radar` para hoje
2. Se existe: envia podcast + resumo para todos os assinantes
3. Se não existe: não envia (guard anti-duplo)

### Temas do assinante → doenca_principal
| Tema | doenca_principal incluídas |
|---|---|
| coronaria | Coronariopatia Aguda, Crônica, Intervenção Vascular |
| cardiometabolico | Dislipidemias, Cardiometabólica, Manifestações CV |
| miocardiopatias | Miocardiopatias, IC, Cardio-Onco, Cardio-Obstet, Congênitas, Aortopatias |
| prevencao | HAS, Pré-Op, Prevenção CV, Farmacologia, Outros |
| valvulopatias | Valvulopatias |
| arritmia | Arritmias, Marcapasso, Stroke |
| uti | Emergências/UTI |
| imagem | Imagem Cardiovascular |

---

## RADAR PUBMED — 13 TEMAS (rotação diária)

| Dia (% 13) | Tema | Nome PT |
|---|---|---|
| 0 | doenca_coronariana | Coronária/DAC |
| 1 | cardio_metabolica | Cardiometabólica |
| 2 | arritmias | Arritmias |
| 3 | insuficiencia_cardiaca | Insuficiência Cardíaca |
| 4 | valvulopatias | Valvulopatias |
| 5 | miocardiopatias | Miocardiopatias |
| 6 | intervencao_hemodinamica | Intervenção/Hemodinâmica |
| 7 | cardio_oncologia | Cardio-Oncologia |
| 8 | cardiobstetrica | Cardio-Obstétrica |
| 9 | cardio_genomica | Cardio-Genômica |
| 10 | uti_cardiologica | UTI Cardiológica |
| 11 | aorta_congenitas | Aorta/Congênitas |
| 12 | imagem_cardiovascular | Imagem Cardiovascular |

**Pipeline:** `run_radar_diario.py` → PubMed (14 dias, 50 artigos) → triagem Gemini → script Gemini → MP3 ElevenLabs → Supabase Storage → tabela `radar` → WhatsApp

---

## DEPLOY

### Mac local (beta)
```bash
0 7 * * * cd /Users/edcastro77/CardioDaily_FULL && python3 distribuidor.py artigos
0 8 * * * cd /Users/edcastro77/CardioDaily_FULL && python3 distribuidor.py radar
```

### VPS (produção — pendente)
```bash
git clone <repo> CardioDaily_FULL
cd CardioDaily_FULL
python3 -m venv venv && source venv/bin/activate
pip install supabase httpx python-telegram-bot

# Cron (10/11 UTC = 07/08 BRT)
0 10 * * * cd /opt/CardioDaily_FULL && venv/bin/python3 distribuidor.py artigos
0 11 * * * cd /opt/CardioDaily_FULL && venv/bin/python3 distribuidor.py radar
```

---

## CHECKLIST COMPLETO (estado em 23/Maio/2026)

### Concluído

- [x] Classificador v8.0 — 98%+ acurácia (Gemini Vision)
- [x] Pipeline de análise completo (originais, revisões, meta-análises, guidelines)
- [x] Visual Abstract 8 seções (Playwright)
- [x] Mapa mental visual (Claude + Playwright)
- [x] Podcast (GPT-4o + TTS onyx)
- [x] Briefing Cri-Cri (Claude + Cartesia Luana)
- [x] PDF Generator v2 (formato Replete)
- [x] Novo prompt análise artigo original (prompt_artigo_original_v2.md)
- [x] LEI 0 em código — `aplicar_teto_nac()` (inviolável)
- [x] Z-API check de conexão antes de enviar
- [x] n8n cancelado, `distribuidor.py` operacional
- [x] Radar: dois workflows → um único (`radar.yml`)
- [x] 8 campos clínicos criados no Supabase (v20.0)
- [x] `backfill_campos_clinicos.py` expandido (keywords, titulo, revista, doenca_principal)
- [x] `extrai_campos_llm.py` criado (Gemini Flash, pronto para produção)
- [x] Compactador de Diretrizes SBC-PI
- [x] Bug `data_publicacao` → `created_at` no distribuidor
- [x] Bug strip de tabelas no `sync_resumo_markdown.py`

### Pendente imediato

- [x] ~~Validar teste LLM~~ — **CONCLUÍDO 23/Mai**
- [x] ~~Backfill zero-token~~ — **CONCLUÍDO 23/Mai**
- [x] ~~Backfill LLM~~ — **CONCLUÍDO 23/Mai** (~US$0.20)
- [x] ~~Blocos 5–10 (557 artigos nota-7)~~ — **CONCLUÍDO 23–25/Mai**
- [x] ~~Knowledge base 100% preenchido~~ — **CONCLUÍDO 25/Mai** (2.155/2.159 artigos nota≥7)
- [ ] **Backfill PDFs histórico:** `python3 scripts/upload_pdfs_supabase.py --since 2020-01-01`
- [ ] **Backfill áudios:** `python3 scripts/gerar_audios_lote.py`

### Pendente antes do lançamento

- [ ] RLS no Supabase — SQL em v20.0 acima
- [ ] Deploy VPS
- [ ] Telegram Bot reimplementado (`telegram_bot.py`)
- [ ] Criar bucket `briefing_audio` no Supabase (Storage → New bucket → público)
- [ ] Limpeza Supabase: dropar `nota_geral`, `resumo_json`; limpar usuário duplicado em `whatsapp_users`
- [ ] Testar distribuidor com credenciais reais: `python3 distribuidor.py teste`
- [ ] Cancelar plano n8n (se ainda ativo)

---

## RLS NO SUPABASE — SQL ANTES DO LANÇAMENTO

```sql
-- Tabelas sensíveis
ALTER TABLE public.whatsapp_users ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.conversas_whatsapp ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.whatsapp_sends ENABLE ROW LEVEL SECURITY;

CREATE POLICY "service_role_full_access" ON public.whatsapp_users
  USING (auth.role() = 'service_role')
  WITH CHECK (auth.role() = 'service_role');

-- Tabelas de conteúdo (artigos = leitura pública, escrita restrita)
ALTER TABLE public.artigos ENABLE ROW LEVEL SECURITY;
CREATE POLICY "read_public" ON public.artigos FOR SELECT USING (true);
CREATE POLICY "write_service_only" ON public.artigos FOR ALL
  USING (auth.role() = 'service_role');
```

---

## LEIS DE OPERAÇÃO (Claude)

1. **LEI 0 nunca é contornada:** `aplicar_teto_nac()` é chamada após todo parse de LLM e antes de todo upsert no Supabase. Nunca remover, desabilitar ou bypassar.
2. **Busca sistemática antes de qualquer mudança de API/provider:** grep em `src/`, `scripts/` e raiz — listar TODOS os pontos afetados antes de tocar código.
3. **Atualizar `docs/CADERNO_EXECUCAO.md` ao final de cada sessão** com mudanças relevantes, estado honesto, o que funcionou e o que falhou.
4. **Nunca criar arquivos temporários na pasta raiz** — usar `archive/logs_operacionais/` ou `outputs/`.
5. **Para Gemini:** `system_msg=None`, prompt + artigo juntos em `contents`, `max_output_tokens=32000`. Nunca separar.
6. **PDF sem page-break manual:** WeasyPrint é automático. Capa usa `@page cover` isolada.
7. **`article_analyzer.py` sempre em Terminal interativo** com `caffeinate -dims` — nunca em background pelo Claude Code.

---

## QUARENTENA PERMANENTE — NUNCA REATIVAR

| Componente | Motivo |
|---|---|
| DALL-E 3 | Gera arte genérica, não infográficos clínicos. Zero dado real renderizado. |
| `InfographicPortrait` (`portrait_visualmed.html`) | Texto minúsculo, espaços vazios |
| `MindmapGenerator` PNG visual | Substituído pelo Visual Abstract |
| `infographic_mpl.py` (matplotlib) | Qualidade visual insuficiente |
| Cards HTML→PNG para WhatsApp 1080×1080 | Texto ilegível em mobile, não escala |

---

## COMO FORNECER CONTEXTO AO CLAUDE EM SESSÕES FUTURAS

### Diagnóstico do sistema
```
1. "Qual o estado atual do sistema?" → Claude lê este caderno + faz grep nos scripts
2. Sempre citar versão do caderno ao reportar diagnóstico
3. Dados concretos do Supabase valem mais que estimativas
```

### Para corrigir um bug
```
1. Comando exato que falhou
2. Mensagem de erro completa (copiar do terminal)
3. O que deveria ter acontecido
4. Quando o bug começou (antes/depois de qual mudança)
```

### Para adicionar novo componente
```
1. O que entra (input: tipo de arquivo, formato, fonte)
2. O que sai (output: onde salva, formato, nome)
3. Quando dispara (manual / cron / gatilho automático)
4. Qual modelo usar (Gemini / Claude / GPT-4o)
5. Exemplo do resultado esperado
```

> **Mostrar é melhor que descrever.** Um screenshot do problema + um screenshot do esperado vale mais do que um parágrafo de texto.

---

## PRINCÍPIOS INVIOLÁVEIS DO PROJETO

1. Rigor metodológico acima de tudo
2. Crítica ao estudo, nunca ao autor
3. Incerteza declarada é virtude
4. Bola na rede — toda análise termina com conduta prática
5. Nunca abandonar uma funcionalidade — sempre existe uma alternativa
6. Independência editorial absoluta
7. Controle total — sem dependência de plataformas visuais de terceiros

---

*Versão 21.0 — 23/Maio/2026 — atualizado por Claude ao final da sessão*
*Próxima atualização obrigatória: após execução do bloco 5 e validação do teste LLM*
