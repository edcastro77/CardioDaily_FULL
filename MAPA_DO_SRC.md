# MAPA DO src/ — o que é essencial, o que roda sozinho, o que é entulho
*Levantado em 25/07/2026 por varredura de imports a partir dos 4 botões.*

## A. A CORRENTE (19 arquivos) — o que os botões rodam

### 🔑 CHAVE 1 · CLASSIFICADOR
| Arquivo | Papel |
|---|---|
| `classificador_ouro.py` | **entrada** — lê os PDFs, decide o tipo, renomeia e move p/ `CLASSIFICADOS/<tipo>/` |
| `classificador_pubmed.py` | consulta PubMed/EuropePMC — tipo **autoritativo** (não chuta) |
| `pdf_extractor.py` | extrai o texto do PDF |
| `reprocessar_fila.py` | drena a FILA_ESPERA (ahead-of-print que ainda não indexou). **Deveria rodar todo dia — hoje está solto, sem botão nem Actions** |

### 🔑 CHAVE 2 · ANALISADOR  (o coração)
| Arquivo | Papel |
|---|---|
| `rodar_em_blocos.py` | **entrada** — roda em blocos de 20: analisa → publica → próximo bloco |
| `analisador.py` | orquestra 1 artigo: fatos → nota → entregáveis por porta → confere → `_OK` |
| `analise.py` | extrai os FATOS do PDF (saída estruturada / tool use) — `SCHEMA_FATOS` |
| `notas_prototipo.py` | **motor de rigor** — a nota determinística (LEI 0). *Sagrado* |
| `pipeline.py` | monta o registro canônico (`_CANONICO.md`) |
| `modelos.py` | **config central de modelos** — trocar modelo = 1 linha aqui |
| `llm_client.py` | cliente unificado: cadeia cross-provider, tool use, retry, cache |
| `pdf_analise.py` | perícia (markdown) → PDF WeasyPrint |
| `voz_utils.py` | roteiro → MP3 (TTS OpenAI), fatiando textos longos |
| `infographics/visual_abstract_generator.py` | Visual Abstract 8 seções (único visual permitido) |

**Portas:** <6 fica (só canônico) · ≥6 canônico+ACRI+perícia+PDF · ≥7 +Visual Abstract · ≥8 +áudio

### 🔑 (dentro da Chave 2) · PUBLICADOR
| Arquivo | Papel |
|---|---|
| `publicador.py` | sobe mídia p/ Storage + linha p/ Supabase (rascunho) |
| `contrato.py` | **o portão** — recusa buraco (campo vazio, arquivo faltando, nota <6) |
| `ficha_site.py` | monta a ficha a partir do canônico + ACRI + arquivos |

### 🔑 CHAVE 3 · ADMINISTRADOR — `administrador.py` (curadoria: ver/ouvir/aprovar + data)
### 🔑 CHAVE 4 · ARQUIVADOR — `arquivador.py` (move staging → ARQUIVO/AAAA-MM)
### 🧪 PROVA — `bateria.py` (roda N artigos: APROVADO só com zero falha)

---

## B. RODAM SOZINHOS (GitHub Actions) — não são órfãos
| Arquivo | Quando |
|---|---|
| `radar/radar_pubmed.py` | Radar diário 07:30 (via `scripts/run_radar_diario.py`) |
| `radar/journal_issue_fetcher.py` | apoio do Radar |
| `briefing_semanal.py` | briefing semanal |
| `lista_whatsapp.py` | lista semanal (via `distribuidor.py semana`) |
| `../distribuidor.py` | distribuição diária 07:00 |

---

## C. ⚠️ LEGADO PERIGOSO — o analisador ANTIGO ainda vivo
`article_analyzer.py` é o analisador **antigo** (3.200 linhas). Ele **ainda roda em produção**,
todo dia às 07:00, porque `distribuidor.py` o importa. Ou seja: **dois analisadores publicando
no mesmo Supabase** — o antigo (Actions) e o novo (Chave 2).

Satélites dele: `prompts_config_v2.py`, `taxonomy.py`, `article_validator.py`,
`audio_generator.py`, `doi_tracker.py`, `journal_utils.py`, `web_biblioteca.py`.

**Decisão pendente do Dr. Eduardo:** aposentar o caminho antigo (o `distribuidor.py` passa a só
distribuir o que a corrente nova publicou) ou mantê-los convivendo. Enquanto conviverem, há risco
de análise duplicada e divergente do mesmo artigo.

---

## Fluxo em uma linha
```
ARTIGOS/*.pdf
   └─ CHAVE 1 · classificador_ouro ──► ARTIGOS/CLASSIFICADOS/<tipo>/
        └─ CHAVE 2 · rodar_em_blocos (blocos de 20)
             ├─ analisador ─► analise(FATOS) ─► notas(NOTA) ─► pipeline(CANÔNICO)
             │                └─ perícia+PDF · Visual Abstract(≥7) · áudio(≥8)
             └─ publicador ─► contrato(PORTÃO) ─► Supabase (rascunho)
                  └─ CHAVE 3 · administrador (curar + data de envio)
                       └─ CHAVE 4 · arquivador (staging → ARQUIVO)
```
