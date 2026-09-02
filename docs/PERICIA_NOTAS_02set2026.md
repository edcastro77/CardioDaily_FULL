# PERÍCIA DAS NOTAS — CardioDaily_FULL · 02/Set/2026

**Pergunta do Dr. Eduardo:** *"preciso entender que o sistema não está se desviando e usando
um mecanismo acessório para dar notas de formas diferentes."*

**Método:** varredura estática de TODO arquivo executável (.py, .command, .md de prompt,
workflows) por 4 peritos independentes em paralelo (clusters: legado · corrente nova ·
ferramentas de reparo · prompts) + prova dinâmica com o Conferidor de Notas (Chave 16)
sobre 695 pacotes e a linha do Supabase.

---

## VEREDITO GERAL

**NÃO existe mecanismo acessório vivo dando nota.** O nascedouro é UM (o motor
`notas_prototipo.score()`, função pura, `min` de tetos, sem LLM/rede/aleatoriedade) e o
portão de publicação é UM (`publicador.py`). Os prompts vivos são blindados. O legado está
guardado. **PORÉM a perícia achou 4 fraquezas reais** — nenhuma é "outra régua"; todas são
da família *"a nota certa pode não estar onde você olha"*.

---

## O QUE ESTÁ DE PÉ (com evidência)

| elo | prova |
|---|---|
| Motor puro | `notas_prototipo.score()` sem import de LLM/requests/random; seleciona sub-motor pela PASTA (LEI 8) |
| Extratores não dão nota | `analise_prompt.md:1` *"Sua função NÃO é opinar nem dar nota"* (idem diretriz/revisão/meta); schemas só têm FATOS booleanos/contáveis — nenhum campo 0–10 |
| Redatores não contrariam | os 5 redatores + ACRI + áudio: *"use EXATAMENTE esta nota... não recalcule"* + ABORTAM se o veredito vier vazio (medido: 3 de 4 modelos inventavam nota) |
| Pipeline copia cru | `pipeline.py:49-54` interpola `r["aplic"]` sem round/fallback/clamp |
| Peças leem o canônico | card_acri:153 · pdf_analise:228 · visual_abstract:648 (o bug histórico de perguntar nota ao modelo foi corrigido e está documentado no próprio arquivo) |
| Legado neutralizado | `article_analyzer`: guardas em process_article:2061, process_all:3027, main:3170; o escritor `_upsert_artigo_supabase:447` só é chamado APÓS o raise (inalcançável); `ingerir_artigos`/`indexar_corpus` com SystemExit/RuntimeError antes da escrita |
| distribuidor (07:00, Actions) | só LÊ nota (order by); único PATCH do analyzer que ele usa grava `caminho_pdf`, nunca nota |
| Ferramentas de reparo | `reparar_notas`, `ensaio_seco`, `reavaliar_regua_19ago`: TODAS recalculam via `N.score()` e NÃO tocam o Supabase; conferir_notas só lê |
| Anti-fóssil na fila | carimbo `motor@hash` em `_versoes.json`: motor mudou → staging não serve → reanalisa (`rodar_em_blocos:225-228`; analisador `_SO_A_NOTA:389`) |

---

## AS 4 FRAQUEZAS ENCONTRADAS

### F1 · NOTAS FÓSSEIS NO SUPABASE — 13 divergências em 8 artigos (MEDIDO)
O carimbo anti-fóssil protege quem está NA FILA. Quem já publicou e saiu **não é revisitado
quando o motor muda**. O Conferidor achou, HOJE, no banco: 8 divergências de aplicabilidade
+ 5 de rigor, nos dois sentidos (banco 8 onde o motor diz 9; banco 9 onde o motor diz 7).
Os 8 artigos: Lancet S0140673626003491 · Defining Sex-Specific Severity (JACC) ·
Pathology-Based SPECT/CT (⚠️ é o nº 5 do gabarito dos 4 momentos) · Myocardial Scar AI-MRI ·
Coronary Artery Calcium (JACC) · "Estatina e idosos" · PIIS014067361832484X ·
PIIS0140673626003028 (os dois últimos com nome cru — a mesma falha de renomear do REACT).
O remédio existe (`reparar_notas.py` + republicar pelo portão) mas é MANUAL — se ninguém
roda, o site mostra nota que o motor de hoje nega.

### F2 · O PORTÃO VALIDA FORMATO, NÃO VERDADE
`contrato.py:178` confere int 0–10 e a porta ≥6 — **não recomputa pelo motor**. Um canônico
com nota adulterada (ou fóssil publicado direto por `publicador.py <pasta>`, que não checa
carimbo) passa e sobe. Ninguém a jusante do pipeline recomputa.

### F3 · A CHAVE 16 ESTAVA CEGA NO PDF — aprovado por ausência DENTRO do instrumento de prova
`conferir_notas._texto_do_pdf` depende de **pypdf, que não está no venv**, e o
`except: return None` transforma a dependência ausente em "PDF: ilegível". Resultado
medido: **533 de 695 PDFs "ilegíveis"** — a camada que confere a nota impressa no PDF do
assinante NUNCA conferiu nada (fitz extrai o texto dos mesmos PDFs normalmente).

### F4 · Higienes menores
- `ficha_site.py`: a NOTA vem do canônico (:507) mas `veredito_dominios` é recalculado ao
  vivo (:441-458) — num canônico fóssil, a nota e os domínios "que a explicam" podem
  contar histórias diferentes na MESMA linha do banco.
- `script_audio_diretriz_prompt.md`: único prompt vivo sem a cláusula literal "não
  recalcule a nota".
- `src/prompts/*_v2/v3.md` (+`prompts_config_v2.py`): PEDEM nota ao LLM — mortos, só
  alcançáveis pelo analyzer aposentado, mas são casca reanimável.
- `scripts/backfill_datas_crossref_2026.py:61`: único PATCH direto vivo em `artigos`
  (grava só `data_publicacao`, nunca nota — mas é um segundo portão de fato).
- 2 pacotes sem canônico no STAGING (lixo de rodada interrompida, incl. o semaglutide
  retido pela inversão ICFEr).

---

## RECOMENDAÇÕES (prioridade; decisão do dono)

1. **Republicar os 8 fósseis** — `reparar_notas.py --aplicar` + portão. Custo ~zero.
2. **O portão passa a CONFERIR A VERDADE**: contrato (ou preflight do publicador) recomputa
   `N.score(fatos)` e recusa se divergir da ficha. Fecha F1-na-publicação e F2 de uma vez —
   e fica ESSENCIAL para a régua dos 4 momentos, que vai exigir republicação em massa.
3. **Consertar a Chave 16**: pypdf no requirements + a falha de dependência REPROVAR com a
   causa dita, nunca virar "ilegível" (trava anti-ausência no próprio conferidor).
4. **Conferidor no Actions semanal** (junto da auditoria) — fóssil passa a ser acusado
   sozinho, toda segunda.
5. Higienes do F4 (arquivar casca v2; alinhar prompt de áudio-diretriz; carimbo no
   publicador direto).

**Vocabulário LEI 7:** esta perícia é LEITURA — nada foi alterado. Os números do Conferidor
rodaram nesta máquina com o banco real.
