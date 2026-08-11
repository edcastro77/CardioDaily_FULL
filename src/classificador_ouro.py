"""
classificador_ouro.py — CLASSIFICADOR OURO (09/Jul/2026, branch lab/religar-prompts).
Arquitetura desenhada com o Dr. Eduardo. Ver MEMORIA_CLASSIFICADOR_OURO.md e
MAPA_REVISTAS_classificador.md.

CAMADAS (reescritas em 10/Ago/2026 — este bloco descrevia um sistema que não existe mais):

  1) MAPA DE REVISTA (pelo DOI) — determinístico, grátis. DECIDE.
       Clinics (ccl/hfc/ccep/iccl) = revisão · EHJ Supplements = minirevisão ·
       JACC Case Reports = descarte. Medido no acervo: 86 artigos, 100 % na pasta certa.
       É curadoria do Dr. Eduardo, não heurística — por isso ganha de tudo.
  2) LIXO — relato de caso, research letter, TRIBUTO/IN MEMORIAM. DECIDE, e de graça:
       não se paga leitura para jogar fora.
  3) O LLM lê as PÁGINAS 1 A 3 e DECIDE TODO O RESTO.
       Modelo: a cadeia `modelos.CLASSIFICACAO` — hoje **gpt-5.6-luna** (não Sonnet: o Sonnet
       é o 3º degrau e, medido nas últimas rodadas, respondeu 0 de 229 chamadas).
       Prompt v6, seis regras ditadas pelo Dr. Eduardo sobre erro medido.
       Medido nos 105 artigos do gabarito dele: 100,0 % e repetibilidade 100 %.
  4) CONFERÊNCIA — PubMed, rótulo impresso e título OPINAM e não decidem. Quando discordam
       do LLM, a divergência vai para a coluna `conferencia` do diário.

⚠️ NÃO EXISTE MAIS revisão humana por discordância. Palavras dele, 10/Ago: *"a llm tem que
acertar — nada de revisão humana; só teremos que fazer revisão humana se formos incompetentes
em fazer os filtros corretos para a llm ler no início."* Divergência vira conserto de filtro,
não fila na mesa dele.

⚠️ E O PUBMED NÃO MANDA MAIS. Medido contra o gabarito de 111: PubMed 60,0 % de acerto e só
opina em 15 % dos artigos; o LLM, 99,1 % e opina em 100 %. Intuição dele: *"ele não tem no
escopo todos os nomes e sai colando o primeiro da reta"*. O número deu razão a ele.

TÍTULO limpo (nunca "nome troncho"): PubMed/EPMC via DOI dá título+revista+data pro rename;
se não houver, mantém o nome original. (Extração de título da 1ª página = melhoria futura.)

Uso: python src/classificador_ouro.py <PASTA> [--dry-run] [--max N]
"""
import os
import re
import shutil
import voo as VOO          # plano de voo (09/Ago) — marca posição a cada etapa crítica
import argparse

from dotenv import load_dotenv

from classificador_pubmed import (
    PDFExtractor, extrair_doi, pubmed_lookup, europepmc_lookup, map_pubtype,
    eh_descartavel, _novo_nome, doi_e_deste_artigo, FOLDERS, SUB_ANALISE, SUB_DESCARTE, SUB_REVISAO,
    RedeIndisponivel,
)

import classificador_prompt as CP     # O PROMPT: um lugar só (prova e produção leem daqui)

SUB_RETRY = "RETENTAR_REDE"  # falha de rede (não é troncho): revisar/rodar de novo

# ═══ DISJUNTOR DE REDE — 03/Ago/2026 ═══
# A trava de rede era POR ARTIGO: detectava a queda, mandava o PDF pra RETENTAR_REDE e seguia
# pro próximo — que também falhava, e o próximo, e os 364. Com a internet fora, ele marchava pelo
# lote inteiro gastando tempo e entregando um resultado sem valor nenhum.
# Palavras do Dr. Eduardo (03/Ago, ao interromper na mão no 5º artigo):
#     "a internet desconectou do nada e ele nao para..."
# Agora: N quedas SEGUIDAS = a rede está fora, não é azar de um artigo → PARA a rodada e diz o que
# já foi feito. Consecutivas de propósito: um soluço isolado não pode abortar uma rodada boa.
MAX_QUEDAS_SEGUIDAS = 3

# ═══ QUANTAS LINHAS DO TOPO CONTAM COMO "O TOPO" — MEDIDO, não chutado (03/Ago/2026) ═══
# Era 6, um número que eu inventei. Medido em 200 PDFs reais do acervo do Dr. Eduardo, olhando
# onde o RÓTULO IMPRESSO de seção aparece de fato (depois de descartar linhas em branco):
#     linha 1: 57%   ·   até a 5: 73%   ·   até a 6: 91%   ·   até a 15: 100%
# O corte em 6 perdia 9% dos rótulos — e a linha 6 é um PICO (21 dos 112), ou seja, eu tinha
# cortado exatamente em cima da concentração. Quando o rótulo escapa desta camada, o artigo cai
# no LLM sem que ninguém saiba que a via determinística falhou.
# Estender não custa NADA: é texto já lido, sem chamada de API. 15 cobre 100% do medido.
LINHAS_DO_TOPO = 15
SUB_DUP = "DUPLICATAS"       # mesmo DOI/artigo 2x: não sobrescreve (GOLDEN GATE)

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(_ROOT, ".env"), override=True)
ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY", "")
# classificação usa a cadeia EXTRACAO da modelos.py (via llm_client) — modelo vivo + thinking tratados lá

# ============================ CAMADA A — MAPA DE REVISTA ============================
# prefixo do DOI -> resultado determinístico (sem ler o abstract)
_MAPA_PREFIXO = [
    ("10.1016/j.ccl",    "revisao_geral"),  # Cardiology Clinics
    ("10.1016/j.hfc",    "revisao_geral"),  # Heart Failure Clinics
    ("10.1016/j.ccep",   "revisao_geral"),  # Cardiac Electrophysiology Clinics
    ("10.1016/j.iccl",   "revisao_geral"),  # Interventional Cardiology Clinics
    ("10.1093/eurheartjsupp", "minirevisao"),  # European Heart Journal Supplements — minirevisões de hot topics → trilha minirevisão (condutas+fluxograma, não sobe no Supabase)
    ("10.1016/j.jaccas", "DESCARTE"),       # JACC: Case Reports (Dr. Eduardo "nem abre")
]
# diretrizes/scientific statements da AHA usam DOI 10.1161/CIR.0000000000######
_AHA_STATEMENT = re.compile(r"^10\.1161/CIR\.\d", re.I)


def mapa_revista(doi):
    """Resultado determinístico pela revista (via DOI), ou None se a revista é mista."""
    if not doi:
        return None
    d = doi.lower()
    for pref, res in _MAPA_PREFIXO:
        if d.startswith(pref):
            return res
    if _AHA_STATEMENT.match(doi):
        return "guideline"
    return None


# ============================ META PELO TÍTULO ============================
# Regra do Dr. Eduardo: as revistas OBRIGAM meta-análise/revisão sistemática a declarar no TÍTULO.
# Logo, META não sai do LLM (que exagera lendo conteúdo) — sai do título. Determinístico.
#
# ⚠️ CORRIGIDO EM 02/Ago (varredura da LEI 9, bloco 1). O comentário dizia "meta-análise/revisão
# SISTEMÁTICA", mas o regex só casava "meta-analys". Uma revisão sistemática SEM meta-análise no
# título passava batido por esta camada — o que só não doeu porque o mapa do PubMed pegava depois…
# e o mapa do PubMed mandava ela para `revisao_geral`. Os dois erros se somavam em silêncio.
# D-01 (31/07): revisão sistemática = meta-análise, MESMA TRILHA. O regex agora diz isso.
_META_TITULO = re.compile(r"meta[-\s]?analys|systematic\s+review|revis[ãa]o\s+sistem[áa]tica", re.I)

# ═══ 10/Ago/2026 — ": A REVIEW" É REVISÃO NARRATIVA, E O LLM ESTAVA CHAMANDO DE META ═══
#
# CASOS REAIS, os dois da JAMA, os dois com o LLM em confiança ALTA:
#     "Gastroparesis: A Review"                   → meta, citando "A PubMed search was conducted…"
#     "Alcohol-Related Liver Disease: A Review"   → meta, citando "We conducted a PubMed search…"
#
# A trava do prompt v3 manda responder META só se o artigo DECLARAR busca/PRISMA/I²/pooled. Só que
# TODA revisão narrativa da JAMA declara que fez busca no PubMed — é a frase de método padrão da
# seção "Clinical Review & Education". A trava está pegando o vocabulário da revista, não o
# desenho do estudo. Mesmo erro do 'technique for/with' que saiu em 03/Ago.
#
# O título é a prova mais forte e mais barata que existe: quando a revista escreve ": A Review" no
# fim do título, ela está declarando o formato. Uma meta-análise de verdade escreve
# ": A Systematic Review and Meta-Analysis" — e essa continua caindo no `_META_TITULO`, que roda
# ANTES desta trava e não é afetado.
#
# Medido nos 703 artigos já classificados: 7 têm ": A Review" no título do PubMed — 3 foram para
# revisao_geral (certo), 1 para ponto_de_vista, e 3 para meta-análise (errado; 2 artigos distintos,
# um deles classificado duas vezes com respostas DIFERENTES na mesma cascata).
_REVIEW_NARRATIVA_TITULO = re.compile(
    r":\s*(a|an)\s+(narrative\s+|state[- ]of[- ]the[- ]art\s+|clinical\s+|contemporary\s+|"
    r"critical\s+|practical\s+|concise\s+)?review\s*\.?\s*$", re.I)


def titulo_diz_revisao_narrativa(titulo):
    """True se o título TERMINA em ': A Review' (e variantes) — formato declarado pela revista.

    Só vale se o `_META_TITULO` NÃO casar: ": A Systematic Review and Meta-Analysis" tem as duas
    coisas, e nesse caso quem manda é a meta.
    """
    t = (titulo or "").strip()
    if not t or _META_TITULO.search(t):
        return False
    return bool(_REVIEW_NARRATIVA_TITULO.search(t))


# ==================== RÓTULO DO TOPO — hoje só CONFERE (10/Ago/2026) ====================
# ⚠️ ESTE CABEÇALHO DIZIA 'manda antes do PubMed' e que 'o rótulo do TOPO decide o tipo'.
# Não decide mais nada. Foi rebaixado a conferência em 10/Ago: ele carimbava meta-análise como
# ORIGINAL RESEARCH e revisão como VIEWPOINT, e decidia 240 dos 703 artigos do acervo — era a
# camada que calava o juiz. As funções abaixo continuam sendo usadas para OPINAR (a coluna
# `conferencia` do diário) e para o descarte de lixo, que segue determinístico.
# O que continua verdadeiro: editorial/carta ROUBA o DOI do artigo que comenta, então quando um
# desses rótulos aparece o DOI vira suspeito (emprestado) e o PubMed não renomeia o arquivo.
_ROT_PV = re.compile(r"^(editorial(\s+comment)?|editorials|viewpoint|perspective|commentary|point of view)$", re.I)
_ROT_DESC = re.compile(r"^(research letter|letters?|letter to the editor|correspondence|reply|reply to.*)$", re.I)
# BRIEF REPORT → MINIRREVISÃO. Decisão do Dr. Eduardo (F-02 do docs/FALHAS_AUDITORIA.md, 31/Jul,
# repetida em 02/Ago: "errou 6 artigos originais que eram minirevisões — todos tinham acima do
# título BRIEF REPORT"). A falha estava registrada havia dois dias e a palavra "brief" NÃO EXISTIA
# em nenhum bloco do classificador: nem aqui, nem no prompt, nem no mapa.
_ROT_BRIEF = re.compile(r"^(brief report|brief reports|brief communication|research brief|"
                        r"brief research report|short report|short communication)$", re.I)


def rotulo_topo(texto):
    """Olha as primeiras linhas da 1ª página. Devolve (destino, rótulo) ou (None, None).
    destino ∈ {'ponto_de_vista', 'DESCARTE', 'minirevisao'}.
    Ancorado em LINHA inteira (não 'contém'), só no topo → não confunde artigo original."""
    linhas = [l.strip() for l in (texto or "")[:2000].splitlines()]
    linhas = [l for l in linhas if l and not re.fullmatch(r"[.\s·•]+", l)]
    for l in linhas[:LINHAS_DO_TOPO]:
        if _ROT_PV.match(l):
            return "ponto_de_vista", l
        if _ROT_DESC.match(l):
            return "DESCARTE", l
        if _ROT_BRIEF.match(l):
            return "minirevisao", l
    return None, None


# Rótulo POSITIVo de original (seção da revista no topo). Entra por ÚLTIMO — só antes do Sonnet,
# depois de meta-título/descarte/PubMed. Assim não rebaixa meta ([31]) nem case report ([86]).
_ROT_ORIG = re.compile(
    r"^(original (article|research|research article|research paper|investigation|clinical research)"
    r"|clinical research( article)?|clinical trial|research article|fast track.*)$", re.I)


def rotulo_original(texto):
    """Rótulo de seção que declara ARTIGO ORIGINAL (ex.: 'CLINICAL RESEARCH', 'ORIGINAL RESEARCH')."""
    linhas = [l.strip() for l in (texto or "")[:2000].splitlines()]
    linhas = [l for l in linhas if l and not re.fullmatch(r"[.\s·•]+", l)]
    for l in linhas[:LINHAS_DO_TOPO]:
        if _ROT_ORIG.match(l):
            return l
    return None


# ================== O JUIZ — o LLM lê as PÁGINAS 1 A 3 e DECIDE (10/Ago/2026) ==================
# ⚠️ ESTE CABEÇALHO DIZIA 'SONNET lê a 1ª página' e 'META já foi decidida pelo título ANTES do
# Sonnet; aqui o Sonnet NÃO tem a opção meta'. As três coisas mudaram:
#   · o modelo é a cadeia `modelos.CLASSIFICACAO` — hoje gpt-5.6-luna. O Sonnet é o 3º degrau
#     e respondeu 0 de 229 nas últimas rodadas.
#   · a leitura é das PÁGINAS 1 A 3 desde 03/Ago (o rótulo de seção mora na 2 ou na 3 com
#     frequência; foi o que levou o acerto de 54 % para 87 %).
#   · o LLM TEM a opção meta, e é ele quem decide: o título deixou de ganhar dele em 10/Ago.

_llm_erro_mostrado = False
_MODELO_USADO = None      # quem de fato respondeu na última chamada (pode não ser o primário)
_LOG = []                 # o diário da rodada: uma linha por artigo (ver REGISTRO DA DECISÃO)


def classificar_llm(caminho):
    """O JUIZ LLM da cascata — migrado para a versão MEDIDA em 02/Ago/2026 (LEI 8, tarefa #33).

    O QUE MUDOU, e por quê (três coisas, todas medidas):
      1. PROMPT: era um texto próprio, daqui, que **contradizia a DECISÃO D-01 do Dr. Eduardo**
         ("revisão sistemática É meta-análise"): mandava literalmente escolher `revisao_geral`
         quando o artigo parecesse meta. Também não conhecia `minirevisao`.
         Agora vem de `classificador_prompt.py` — o MESMO texto que a prova mede. Um só.
      2. QUANTO LÊ: era `texto[:5000]` do começo. Agora são as PÁGINAS 1 A 3, porque o RÓTULO
         IMPRESSO da seção — que é a REGRA 1 do prompt — muitas vezes só aparece na página 2 ou 3.
         (medido: detecção do rótulo subiu de 54 % para 87 %)
      3. MODELO: era a cadeia EXTRACAO (sonnet-5). Agora é a CLASSIFICACAO (gpt-5.6-luna), que
         acertou 110/111 = 99,1 % e custa 10× menos. Não é trade-off: é melhor e mais barato.

    Devolve (tipo, confianca, prova) — ou (None, "", "") em erro. Nunca engole erro em silêncio.
    A CONFIANÇA e a PROVA são novas: a produção antiga só recebia a palavra do tipo, sem nenhuma
    forma de saber se o modelo tinha base para dizê-la.
    """
    global _llm_erro_mostrado
    try:
        texto3 = CP.paginas_1a3(caminho)
    except Exception as e:
        print(f"   ⚠️ não li as páginas 1-3 de {os.path.basename(caminho)}: {type(e).__name__}")
        return None, "", ""
    if not texto3.strip():
        # ═══ 09/Ago — ERA MUDO ═══
        # `return None, "", ""` sem log. O juiz nunca é chamado, a cascata cai no último
        # degrau, e nada indica que o artigo foi julgado sem o juiz.
        VOO.marcar("C4_DECIDIU", ok=False, artigo=os.path.basename(caminho),
                   erro="páginas 1-3 vieram VAZIAS — o juiz LLM não chegou a ser consultado")
        print(f"   ⚠️ {os.path.basename(caminho)[:52]}: páginas 1-3 vazias — sem juiz LLM")
        return None, "", ""
    try:
        import llm_client, modelos as M
        # 10/Ago — o TOTAL de páginas vai junto (regra R4 do v6): é o que separa revisão de
        # ponto de vista, e o modelo não tem como contar páginas lendo texto extraído.
        out = llm_client.gerar(M.CLASSIFICACAO,
                               CP.montar(texto3, paginas=CP.total_paginas(caminho)),
                               max_tokens=700, temperatura=0)
        tipo, conf, prova = CP.ler_resposta(out)
        # QUEM RESPONDEU DE VERDADE (02/Ago). `llm_client.gerar` troca de modelo EM SILÊNCIO quando
        # o primário falha (429/timeout). Numa rodada de 383 artigos isso é provável — e o Luna
        # (99,1 % medido) seria substituído pelo Haiku (89,2 %) sem ninguém saber. Um lote inteiro
        # pode degradar sem UMA linha de aviso. Agora o troco aparece na tela e vai para o log.
        global _MODELO_USADO
        _MODELO_USADO = llm_client._ULTIMO_MODELO[0]
        if _MODELO_USADO and _MODELO_USADO != M.CLASSIFICACAO[0]:
            print(f"        ⚠️ FALLBACK: quem respondeu foi {_MODELO_USADO}, "
                  f"não {M.CLASSIFICACAO[0]} — a acurácia medida NÃO vale para esta linha")
        VOO.marcar("C4_DECIDIU", ok=bool(tipo), artigo=os.path.basename(caminho),
                   camada="juiz LLM", tipo=tipo or "", confianca=conf,
                   modelo=_MODELO_USADO or "",
                   erro=None if tipo else "o modelo respondeu fora do formato esperado")
        return (tipo or None), conf, prova
    except Exception as e:
        # ═══ 09/Ago — O ERRO SÓ APARECIA UMA VEZ POR PROCESSO ═══
        # A flag `_llm_erro_mostrado` foi criada para não encher a tela, e a intenção era boa.
        # Mas numa rodada de 383 artigos, do 2º ao 383º erro **não sobrava rastro nenhum** —
        # e é justamente esse o cenário em que o erro é o mesmo em todos: crédito acabado,
        # chave expirada, provedor fora do ar. O Radar de 09/Ago morreu assim.
        # A tela continua limpa (a flag fica), mas o VOO registra TODOS, um por artigo.
        VOO.marcar("C4_DECIDIU", ok=False, artigo=os.path.basename(caminho),
                   erro=f"{type(e).__name__}: {e}")
        if not _llm_erro_mostrado:
            print(f"   ⚠️ classificador LLM falhou: {type(e).__name__} - {e}")
            print(f"      (os próximos vão para o voo.jsonl — a tela não repete, o registro sim)")
            _llm_erro_mostrado = True
        return None, "", ""


# ============================ A CORRENTE ============================
def classificar(pasta, dry_run=True, max_n=0):
    ext = PDFExtractor()
    pdfs = sorted(f for f in os.listdir(pasta)
                  if f.lower().endswith(".pdf") and not f.startswith("._"))
    if max_n:
        pdfs = pdfs[:max_n]

    _LOG.clear()                          # cada rodada tem o seu diário
    print(f"\n{'DRY-RUN (nada é movido)' if dry_run else 'EXECUTANDO (move arquivos)'} — {len(pdfs)} PDF(s)")
    # ═══ 10/Ago — ESTA LINHA MENTIA EM TRÊS PONTOS ═══
    # Dizia "mapa de revista → descarte → Sonnet(1ª página) → revisão humana". Nenhuma das
    # três estava certa: o modelo é o gpt-5.6-luna (o Sonnet é o 3º fallback e, medido nas
    # últimas rodadas, respondeu 0 de 229); a leitura é das páginas 1 a 3 desde 03/Ago; e a
    # revisão humana por discordância acabou hoje, por decisão do Dr. Eduardo — *"a llm tem
    # que acertar"*.
    # É o mesmo defeito dos US$ 0,30 chumbados na Chave 2: uma linha escrita uma vez, nunca
    # atualizada, que o dono lê e toma como o estado do sistema. Agora ela se monta do que
    # está de fato configurado — se a cadeia ou o prompt mudarem, a tela muda junto.
    import modelos as _M
    print(f"cascata: mapa de revista → lixo (relato/carta) → LLM {_M.CLASSIFICACAO[0]} "
          f"lê as páginas 1-3 (prompt {CP.PROMPT_VERSAO}) e DECIDE o resto")
    print(f"         PubMed · rótulo impresso · título → CONFEREM (coluna `conferencia` do diário)")
    print(f"         fallback, se o primário cair: {' → '.join(_M.CLASSIFICACAO[1:])}\n")
    cont = {}
    via_mapa = via_sonnet = via_pubmed = 0
    vistos_doi = {}    # DOI confiável → nome do 1º arquivo (dedup por identidade)
    quedas_seguidas = 0   # disjuntor: N seguidas = rede fora, para a rodada
    alvos_usados = {}  # nome-alvo → 1º arquivo (rede de segurança contra colisão de nome)

    for i, nome in enumerate(pdfs, 1):
        caminho = os.path.join(pasta, nome)
        # ═══ WAYPOINT C1 — "o texto foi extraído do PDF" (09/Ago/2026) ═══
        # Era `except Exception: texto = ""`, sem UMA linha de log. A partir daqui TODAS as
        # camadas determinísticas da cascata (linhas 263-286) recebem string vazia e decidem
        # no vácuo — o artigo é classificado, movido e registrado no CSV como se tudo tivesse
        # corrido bem. O CSV grava o destino; não grava que o PDF era ilegível.
        try:
            texto = ext.extract_text(caminho)
            if texto.strip():
                VOO.marcar("C1_TEXTO", artigo=nome, n_chars=len(texto))
            else:
                # PDF que abre mas não tem camada de texto — o caso do escaneado, e é MUDO:
                # não levanta exceção, devolve string vazia.
                VOO.marcar("C1_TEXTO", ok=False, artigo=nome, n_chars=0,
                           erro="PDF abriu mas veio SEM TEXTO (provável imagem escaneada)")
                print(f"        ⚠️ {nome[:52]}: PDF sem camada de texto — a cascata vai decidir às cegas")
        except Exception as e:
            texto = ""
            VOO.marcar("C1_TEXTO", ok=False, artigo=nome, erro=f"{type(e).__name__}: {e}")
            print(f"        ⚠️ {nome[:52]}: não consegui ler o PDF — {type(e).__name__}: {str(e)[:80]}")
        doi = extrair_doi(texto)
        # ═══ WAYPOINT C2 — "o DOI foi encontrado" ═══
        # Sem DOI não há PubMed, e sem PubMed a cascata perde a camada mais confiável.
        # Não é erro (Framingham 1962 não tem DOI) — mas tem de ficar registrado.
        VOO.marcar("C2_DOI", ok=bool(doi), artigo=nome, doi=doi or "",
                   erro=None if doi else "nenhum DOI no texto extraído")

        # título/metadados p/ rename (grátis) — e pubtypes p/ o descarte determinístico
        pubtypes, meta, falha_rede = [], {}, False
        if doi:
            try:
                pubtypes, meta = pubmed_lookup(doi)
                if not meta:
                    _, meta = europepmc_lookup(doi)
                # ═══ WAYPOINT C3 — "o PubMed respondeu sobre este DOI" ═══
                # `if r.ok else []` faz um 4xx ser indistinguível de "DOI não indexado".
                # A RedeIndisponivel cobre 429/5xx/timeout; isto aqui cobre o resto.
                VOO.marcar("C3_PUBMED", ok=bool(pubtypes or meta), artigo=nome,
                           pubtypes=",".join(pubtypes)[:120] if pubtypes else "",
                           erro=None if (pubtypes or meta)
                           else "PubMed e EuropePMC não devolveram nada para este DOI")
            except RedeIndisponivel as e:
                falha_rede = True
                quedas_seguidas += 1
                print(f"        ⚠️ REDE caiu ({quedas_seguidas}/{MAX_QUEDAS_SEGUIDAS}): {e}")
            else:
                quedas_seguidas = 0        # respondeu → a rede voltou, zera o contador

        rotulado = False  # rótulo do topo disparou → DOI suspeito (emprestado), não renomear pelo PubMed
        # ZERAR POR ARTIGO (02/Ago). `conf`, `prova` e `_MODELO_USADO` só são preenchidos quando o
        # LLM roda. Sem este reset, um artigo decidido pelo PubMed herdava a confiança, o trecho e
        # o modelo DO ARTIGO ANTERIOR — o diário mentiria, e mentiria de forma convincente.
        # (Pego na revisão do diff, antes de commitar. Era o defeito mais perigoso do dia: um
        #  instrumento de medição que erra é pior que instrumento nenhum.)
        conf = prova = ""
        globals()["_MODELO_USADO"] = None

        # ═══ TRAVA DO DOI EMPRESTADO (02/Ago/2026) ═══
        # O PDF pode trazer o DOI de OUTRO artigo — e aí o PubMed responde, com autoridade, sobre o
        # documento errado. Caso real: o Seminar do Lancet "Atrial fibrillation" tinha só o DOI
        # 10.1055/a-2787-0186 (Thieme / Thrombosis & Haemostasis, do "AF Better Care Pathway", que É
        # revisão sistemática). O Seminar virou META_ANALISES e foi renomeado com o título do outro —
        # "TODAS AS VEZES", nas palavras do Dr. Eduardo. Não era o modelo: o LLM nem era chamado.
        # Aqui o metadado é CONFRONTADO com as páginas 1-3 antes de ter qualquer autoridade.
        if meta and not doi_e_deste_artigo(meta, texto[:20000]):
            print(f"        🚫 DOI EMPRESTADO: o PubMed devolveu «{(meta.get('title') or '')[:52]}»"
                  f" ({meta.get('journal') or '?'}), que não é este PDF — ignorando o PubMed")
            pubtypes, meta, rotulado = [], {}, True   # sem pubtype, sem rename, sem dedup por DOI

        # ═══════════════════════════════════════════════════════════════════════════════════
        # 10/Ago/2026 — DUAS CAMADAS DECIDEM. O LLM DECIDE O RESTO. NINGUÉM VAI PARA
        # REVISÃO HUMANA POR DISCORDÂNCIA.
        # ═══════════════════════════════════════════════════════════════════════════════════
        #
        # AS SEIS DECISÕES DO DR. EDUARDO, uma a uma, com as palavras dele:
        #
        #  1. MAPA DE REVISTA GANHA — *"TODOS OS ARTIGOS DA CLINICS (CARDIOLOGY CLINICS, HEART
        #     FAILURE CLINICS, INTERVENTIONAL CLINICS) SÃO REVISÕES. EHJ SUPPLEMENTS SÃO
        #     MINIRREVISÕES."*  Medido no acervo: 86 artigos, 100 % na pasta certa. É a camada
        #     mais confiável que existe porque não é heurística — é curadoria dele.
        #
        #  2. O PUBMED NÃO GANHA MAIS — *"não sei como você está confiando assim no PubMed. Ele
        #     não tem no escopo todos os nomes e sai colando o primeiro da reta... a impressão
        #     que eu tenho é que o PubMed vai errar mais que a LLM."*
        #     MEDIDO contra o gabarito de 111 artigos que ELE conferiu à mão:
        #         PubMed  60,0 % de acerto (9 certos, 6 errados) · e só OPINA em 15 % dos artigos
        #         LLM v3  99,1 %                                 · opina em 100 %
        #     Os 6 erros são exatamente o que ele descreveu: 2 revisões narrativas carimbadas
        #     `Systematic Review` (a revisão diz que fez busca) e 4 minirrevisões carimbadas
        #     `Editorial` (o Eugene Braunwald da JACC). Um desses erros teria mandado uma
        #     revisão narrativa para a Escada das meta-análises, a ser cobrada por Trim-and-Fill
        #     e I² que ela nunca teve.
        #
        #  3. O RÓTULO IMPRESSO NÃO GANHA — vira conferência. É a camada que decidia 240 de 703
        #     artigos e produziu os erros de 10/Ago: revista carimba meta-análise como
        #     "ORIGINAL RESEARCH" porque é o nome da SEÇÃO, não o desenho do estudo.
        #
        #  4. NADA DE REVISÃO HUMANA POR DISCORDÂNCIA — *"a llm tem que acertar. Só teremos que
        #     fazer revisão humana se formos incompetentes em fazer os filtros corretos para a
        #     llm ler no início."*  Mandar a discordância para uma fila manual seria transferir
        #     para ele o custo de um filtro mal feito. Quando as fontes divergem, vale o LLM —
        #     e a divergência fica REGISTRADA na coluna `conferencia` do diário, para virar
        #     conserto de filtro, não trabalho braçal.
        #
        #  5. RELATO DE CASO CONTINUA DETERMINÍSTICO — *"= LIXO"*. Não se paga leitura para
        #     jogar fora.
        #
        # O QUE ISSO CUSTA: US$ 0,001 por artigo · US$ 0,72 para ler os 740 do mês. O histórico
        # INTEIRO de classificação — 736 leituras — custou US$ 0,71. A cascata antiga existia
        # para poupar essa chamada; a economia era de 56 centavos por mês e o preço dela foi um
        # Nature Medicine com nota 3.
        #
        # ⚠️ DUAS CAMADAS QUE EU REBAIXEI SEM ELE MANDAR, e digo por quê (LEI 6 — se estiver
        # errado, cada uma volta em uma linha):
        #   · RÓTULO NEGATIVO (EDITORIAL/VIEWPOINT/LETTER): ela existia para proteger do DOI
        #     emprestado — editorial rouba o DOI do artigo que comenta e o PubMed carimbava o
        #     tipo do artigo COMENTADO. Com o PubMed rebaixado, o motivo dela evaporou. E o
        #     gabarito mostra o custo de mantê-la: das 6 falhas do PubMed, 4 eram minirrevisões
        #     carimbadas `Editorial`.
        #   · TÍTULO DIZ META: nunca errou até hoje, mas é a mesma família — camada que cala o
        #     juiz. A regra do Dr. Eduardo é "a LLM tem que acertar", e o título continua sendo
        #     a prova mais forte que o próprio prompt v3 manda usar (REGRA 1).
        # As duas continuam rodando como CONFERÊNCIA: opinam no diário, não mudam o destino.
        #
        # TRAVA: rede caiu → NÃO classifica, NÃO renomeia. Vai pro balde de retentar.
        conferencia = []                     # o que as camadas determinísticas ACHAM (não decidem)
        if falha_rede:
            destino, marca, via = "RETRY", "🌐", "falha de rede → retentar"
        # ── CAMADA QUE DECIDE 1/2 — MAPA DE REVISTA (curadoria do Dr. Eduardo) ──
        elif (destino := mapa_revista(doi)):
            marca, via = "🗺️", "mapa de revista"
            via_mapa += 1
        # ── CAMADA QUE DECIDE 2/2 — LIXO (relato de caso/carta): não se paga leitura ──
        elif eh_descartavel(pubtypes, meta.get("title", ""), texto):
            destino, marca, via = "DESCARTE", "⛔", f"descarte: caso/carta {pubtypes or ''}"
        else:
            # CAMADA B/C — o JUIZ LLM lê as PÁGINAS 1 A 3 com o prompt v3 (medido: 110/111 = 99,1 %)
            tipo, conf, prova = classificar_llm(caminho)
            via_sonnet += 1
            # A CONFIANÇA E A PROVA SÃO NOVAS, e mandam (LEI 8, ponto 4: "na dúvida, REVISÃO HUMANA.
            # Classificar errado custa mais caro que não classificar"). Antes a produção recebia só a
            # palavra do tipo: um chute com cara de certeza e um acerto seguro chegavam iguais.
            # Agora o modelo tem de CITAR o trecho do artigo que sustenta a resposta — sem trecho,
            # ou com confiança 'baixa', ninguém entra em pasta nenhuma.
            # SEM BASE = o modelo não sustentou a resposta. Duas coisas, e só duas:
            #   • disse que a confiança é BAIXA, ou
            #   • não citou trecho NENHUM.
            #
            # ⚠️ ERRO MEU, MEDIDO EM 03/Ago e corrigido no mesmo dia. A regra original exigia
            # 12 CARACTERES de prova — um número que eu inventei sem medir. Resultado no lote real:
            # seis artigos foram para REVISAO_HUMANA com confiança ALTA, citando o RÓTULO IMPRESSO
            # da revista, que é a REGRA 1 do prompt e a prova mais forte que existe:
            #     "REVIEW" (6) · "FRONTIERS" (9) · "Viewpoint" (9) · "TRIBUTE" (7) · "A Review" (8)
            # Quanto MELHOR o rótulo — mais curto e mais canônico — mais eu recusava.
            # Palavras do Dr. Eduardo: "está colocando artigos excelentes e que teoricamente seriam
            # fáceis de decidir em revisão humana".
            # Um rótulo de seção é uma palavra. Medir prova por tamanho é medir a coisa errada.
            sem_base = (conf == "baixa") or not (prova or "").strip()
            # `tributo` entrou em 10/Ago (regra R5 do prompt v6). O descarte determinístico
            # (`eh_descartavel` → `eh_tributo`) já pega a maioria antes de chegar aqui; esta é
            # a segunda rede, para a homenagem cujo rótulo não está nas 15 primeiras linhas.
            if tipo in ("relato_de_caso", "carta_de_pesquisa", "tributo"):
                destino, marca, via = "DESCARTE", "⛔", f"LLM: {tipo} ({conf})"
            elif tipo is None:
                destino, marca, via = "REVISAO", "🔴", "o LLM não respondeu"
            elif sem_base:
                destino, marca, via = "REVISAO", "🔴", f"LLM disse {tipo} mas SEM BASE (conf={conf or '—'})"
            elif (tipo == "revisao_sistematica_meta_analise"
                  and titulo_diz_revisao_narrativa(meta.get("title", ""))):
                # ═══ 10/Ago — O TÍTULO DA REVISTA GANHA DO LLM AQUI, E SÓ AQUI ═══
                # "Gastroparesis: A Review" e "Alcohol-Related Liver Disease: A Review" foram
                # para a trilha da meta-análise com confiança ALTA, citando como prova a frase
                # de método padrão da JAMA ("We conducted a PubMed search…"). Toda revisão
                # narrativa da JAMA tem essa frase — a trava do prompt pega o vocabulário da
                # revista, não o desenho. O título diz o formato, e uma meta de verdade se
                # anuncia como "Systematic Review and Meta-Analysis" (que o `_META_TITULO` pega
                # antes, e continua ganhando).
                destino, marca = "revisao_geral", "🏷️"
                via = f"título ': A Review' > LLM (que disse meta: {prova[:34]})"
            elif tipo in FOLDERS:
                # META deixou de ir para revisão humana: o prompt v3 tem a TRAVA DA REVISÃO
                # SISTEMÁTICA (só responde meta se o artigo DECLARAR busca/PRISMA/I²/pooled), e foi
                # com essa trava que o 99,1 % foi medido. Desconfiar aqui seria desperdiçar a trava.
                destino, marca, via = tipo, "🤖", f"LLM v3 pág.1-3 ({conf}): {prova[:60]}"

                # ═══ A CONFERÊNCIA — REGISTRA, NÃO DESVIA (10/Ago/2026) ═══
                #
                # Palavras do Dr. Eduardo: *"a llm tem que acertar - nada de revisão humana - só
                # teremos que fazer revisão humana se formos incompetentes em fazer os filtros
                # corretos para a llm ler no início!"*
                #
                # Eu tinha escrito a versão anterior mandando a discordância para REVISAO_HUMANA,
                # e ele recusou — com razão. Mandar divergência para uma fila manual transfere a
                # ele o custo de um filtro mal feito. A divergência é MATÉRIA-PRIMA DE CONSERTO:
                # ela vai para a coluna `conferencia` do diário, e é lá que a gente descobre se o
                # prompt precisa de uma regra nova. Fila manual não conserta nada — só acumula.
                #
                # As três fontes que opinam aqui, e por que NENHUMA ganha do LLM (medido contra o
                # gabarito de 111 artigos conferido à mão pelo Dr. Eduardo):
                #    LLM v3            99,1 % · opina em 100 %
                #    PubMed            60,0 % · opina em 15 %   (9 certos, 6 errados)
                #    rótulo impresso   decidia 240 de 703 e produziu os erros de 10/Ago
                for quem, opiniao in (("PubMed", map_pubtype(pubtypes) if pubtypes else None),
                                      ("rótulo impresso", "artigo_original" if rotulo_original(texto) else None),
                                      ("título", ("revisao_sistematica_meta_analise"
                                                  if _META_TITULO.search(meta.get("title", "") or texto[:250])
                                                  else None)),
                                      ("rótulo de seção", rotulo_topo(texto)[0] or None)):
                    if opiniao and opiniao != tipo:
                        conferencia.append(f"{quem} diz {opiniao}")
            else:
                destino, marca, via = "REVISAO", "🔴", f"ambíguo (LLM={tipo or 'vazio'})"

        # ═══ REGISTRO DA DECISÃO (02/Ago/2026) ═══
        # POR QUE: em 02/Ago o Dr. Eduardo rodou 383 artigos e viu erros voltarem. Eu rodei a cascata
        # inteira no PDF, camada por camada, e o código do disco classificava CERTO — mas eu não tinha
        # como saber o que tinha acontecido NA RODADA DELE, porque nada era gravado. Fiquei com duas
        # hipóteses e zero evidência, e a LEI 7 proíbe diagnosticar o que não foi olhado.
        # A partir daqui, TODA decisão fica escrita: qual camada decidiu, o que o PubMed disse, qual
        # modelo respondeu de verdade, com que confiança e citando qual trecho.
        # Uma rodada passa a responder sozinha o que antes eu tentava adivinhar.
        _LOG.append({
            "arquivo": nome, "destino": destino, "camada": via, "doi": doi or "",
            "pubtypes": "|".join(pubtypes or []),
            "pubmed_title": (meta.get("title") or "")[:90],
            "doi_emprestado": "SIM" if rotulado else "",
            "modelo": _MODELO_USADO or "", "confianca": conf or "",
            "prova": (prova or "")[:150],
            # 10/Ago — a CONFERÊNCIA vai para o diário. Sem esta coluna, "o rótulo impresso
            # discordou do LLM" seria uma decisão tomada e esquecida: o artigo iria para
            # REVISAO_HUMANA e ninguém saberia POR QUÊ, nem com que frequência isso acontece.
            # É esta coluna que vai dizer, na primeira rodada real, se a revisão humana vai
            # receber 5 artigos por mês ou 200 — o único risco de verdade deste desenho.
            "conferencia": " | ".join(conferencia)[:200],
        })

        # EXPERT OPINION / editorial → trilha MINIRREVISÃO (Dr. Eduardo 26/07): JACC/Circulation/NEJM
        # trazem minirevisões rotuladas como opinião. Vão pra ferramenta minirevisao (condutas+fluxograma),
        # NÃO pro Supabase. (EHJ Supplements já vem como 'minirevisao' pelo mapa de revista.)
        if destino == "ponto_de_vista":
            destino, via = "minirevisao", via + " → minirevisão"

        # destino tentativo → pasta
        if destino == "DESCARTE":
            dest_dir = os.path.join(pasta, SUB_DESCARTE)
        elif destino == "REVISAO":
            dest_dir = os.path.join(pasta, SUB_REVISAO)
        elif destino == "RETRY":
            dest_dir = os.path.join(pasta, SUB_RETRY)
        else:
            dest_dir = os.path.join(pasta, SUB_ANALISE, FOLDERS[destino])

        meta_nome = {} if rotulado else meta  # DOI emprestado → mantém nome original (título verídico)
        novo = _novo_nome(meta_nome, nome) if meta_nome else nome
        alvo = os.path.join(dest_dir, novo)

        # DEDUP (GOLDEN GATE: nada sobrescreve calado). DOI é a IDENTIDADE — só conta se CONFIÁVEL:
        # não emprestado por editorial/carta (rotulado) e não em balde que mantém nome original.
        chave_doi = doi if (doi and not rotulado and destino not in ("DESCARTE", "REVISAO", "RETRY")) else None
        if chave_doi and chave_doi in vistos_doi:
            # MESMO DOI = duplicata real
            destino, marca, via = "DUPLICATA", "👯", f"duplicata de: {vistos_doi[chave_doi]}"
            dest_dir = os.path.join(pasta, SUB_DUP)
            novo = nome  # mantém original, não sobrescreve o primeiro
        else:
            if chave_doi:
                vistos_doi[chave_doi] = novo
            # COLISÃO de nome entre identidades DIFERENTES (ex.: 2 capítulos Clinics cujo título
            # trunca igual) → NÃO é duplicata: desambigua o nome pra não sobrescrever nem perder.
            alvo = os.path.join(dest_dir, novo)
            if alvo in alvos_usados:
                base, ext = os.path.splitext(novo)
                cauda = doi.split("/")[-1].replace(".", "_") if doi else f"n{i}"
                novo = f"{base}__{cauda}{ext}"
                alvo = os.path.join(dest_dir, novo)
            alvos_usados[alvo] = novo

        rel = os.path.relpath(dest_dir, pasta)
        cont[rel] = cont.get(rel, 0) + 1

        # ═══ WAYPOINT C4 — "uma camada da cascata decidiu o tipo" ═══
        # Em ~90% dos artigos quem decide é uma camada determinística (mapa de revista, rótulo
        # do topo, pubtype do PubMed), e o juiz LLM nem é chamado. Registrar QUAL camada decidiu
        # é o que permite, depois, medir a acurácia de cada uma separadamente — e saber se um
        # lote ruim veio do mapa, do PubMed ou do modelo.
        VOO.marcar("C4_DECIDIU", artigo=nome, camada=via, tipo=destino)
        print(f"[{i}/{len(pdfs)}] {marca} {nome[:56]}")
        print(f"        DOI: {doi or '(não achado)'} | via: {via}")
        print(f"        → {rel}/" + (f"  ({novo})" if novo != nome else ""))

        if not dry_run:
            os.makedirs(dest_dir, exist_ok=True)
            # ═══ WAYPOINT C5 — "o PDF foi para a pasta do tipo" ═══
            # Era `shutil.move` NU. Uma exceção aqui abortava `classificar()` inteiro e o
            # diário CSV (gravado só no fim) NUNCA era escrito — perdia-se a prova da rodada
            # toda por causa de um arquivo aberto no Preview. Agora a falha é por ARTIGO.
            try:
                shutil.move(caminho, os.path.join(dest_dir, novo))
                VOO.marcar("C5_MOVEU", artigo=nome, destino=destino, novo_nome=novo)
            except Exception as e:
                VOO.marcar("C5_MOVEU", ok=False, artigo=nome, destino=destino,
                           erro=f"{type(e).__name__}: {e}")
                print(f"        ⚠️ NÃO MOVEU {nome[:48]} → {destino}: {type(e).__name__}: {str(e)[:70]}")
                continue

        # DISJUNTOR: rede fora não é problema deste artigo, é da rodada. Parar é o certo.
        if quedas_seguidas >= MAX_QUEDAS_SEGUIDAS:
            print(f"\n{'='*70}")
            print(f"⛔ REDE FORA — {quedas_seguidas} quedas SEGUIDAS. Rodada INTERROMPIDA em {i}/{len(pdfs)}.")
            print(f"   Os {len(pdfs)-i} restantes continuam na fila, intactos.")
            print(f"   Os que já foram para {SUB_RETRY}/ devem voltar pra fila quando a rede estabilizar")
            print(f"   (Chave 10 · Devolver para a Fila).")
            print(f"{'='*70}")
            break

    print("\nResumo:", ", ".join(f"{k}={v}" for k, v in sorted(cont.items())))
    # 10/Ago — a linha dizia "PubMed autoritativo" e "grátis", que era o vocabulário da cascata
    # velha. O PubMed não decide mais (60,0 % de acerto contra 99,1 % do LLM, medido no gabarito
    # do Dr. Eduardo) e o "grátis" era o argumento que custou um Nature Medicine com nota 3:
    # ler tudo custa US$ 0,001 por artigo.
    _discord = sum(1 for x in _LOG if (x.get("conferencia") or "").strip())
    print(f"Decidiram: MAPA DE REVISTA {via_mapa} | LIXO (relato/carta) {len(_LOG) - via_mapa - via_sonnet} "
          f"| LLM {via_sonnet}")
    if via_sonnet:
        print(f"CONFERÊNCIA: {_discord} de {via_sonnet} artigos tiveram alguma fonte discordando do LLM "
              f"({100 * _discord / via_sonnet:.0f} %) — coluna `conferencia` do diário.")
        print("   Discordância NÃO manda ninguém para revisão humana (decisão do Dr. Eduardo,")
        print("   10/Ago): ela é matéria-prima para consertar o filtro, não fila de trabalho manual.")

    # ─── O DIÁRIO DA RODADA (02/Ago/2026) ───
    # Sem isto, quando um lote sai errado ninguém sabe QUAL CAMADA decidiu nem QUAL MODELO respondeu —
    # e a conversa vira palpite. Uma linha por artigo, gravada ao lado dos PDFs.
    if _LOG:
        import csv as _csv, datetime as _dt
        import modelos as _M
        saida = os.path.join(pasta, f"_CLASSIFICACAO_{_dt.datetime.now():%Y%m%d-%H%M}.csv")
        try:
            with open(saida, "w", newline="", encoding="utf-8-sig") as fh:
                w = _csv.DictWriter(fh, fieldnames=list(_LOG[0].keys()))
                w.writeheader(); w.writerows(_LOG)
            VOO.marcar("C6_DIARIO", linhas=len(_LOG), arquivo=os.path.basename(saida))
            print(f"\n📋 diário da rodada: {saida}")
            primario = _M.CLASSIFICACAO[0]
            fb = [r for r in _LOG if r["modelo"] and r["modelo"] != primario]
            if fb:
                print(f"   ⚠️ {len(fb)} artigo(s) NÃO foram respondidos por {primario} "
                      f"(fallback) — a acurácia medida não vale para eles:")
                for m in sorted({r["modelo"] for r in fb}):
                    print(f"        {m}: {sum(1 for r in fb if r['modelo'] == m)}")
            emp = [r for r in _LOG if r["doi_emprestado"]]
            if emp:
                print(f"   🚫 {len(emp)} artigo(s) com DOI EMPRESTADO (PubMed ignorado)")
        except Exception as e:
            VOO.marcar("C6_DIARIO", ok=False, linhas=len(_LOG), erro=f"{type(e).__name__}: {e}")
            print(f"\n⚠️ não gravei o diário: {type(e).__name__}: {e}")

    if dry_run:
        print("(dry-run — nada foi movido.)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Classificador OURO — mapa de revista → lixo → o LLM (páginas 1-3) decide o resto")
    ap.add_argument("pasta", help="Pasta com os PDFs")
    ap.add_argument("--dry-run", action="store_true", help="Só mostra o que faria (não move)")
    ap.add_argument("--max", type=int, default=0, help="Processar no máximo N PDFs")
    a = ap.parse_args()
    classificar(os.path.expanduser(a.pasta), dry_run=a.dry_run, max_n=a.max)
