"""
classificador_ouro.py — CLASSIFICADOR OURO (09/Jul/2026, branch lab/religar-prompts).
Arquitetura desenhada com o Dr. Eduardo. Ver MEMORIA_CLASSIFICADOR_OURO.md e
MAPA_REVISTAS_classificador.md.

CAMADAS:
  A) MAPA DE REVISTA (pelo DOI) — determinístico, grátis, instantâneo. Resolve ~90%:
       Clinics (ccl/hfc/ccep/iccl) = revisão; JACC Case Reports = descarte; AHA CIR.0 = guideline.
  D) DESCARTE determinístico — relato de caso / research letter (pubtype / título / cabeçalho).
  B/C) CLAUDE SONNET lê a PRIMEIRA PÁGINA (título+rótulo+IMRD+Methods) e decide o tipo.
       Sem espera de indexação, sem rate-limit. O CONTEÚDO do Methods é o juiz.
  Ambíguo até pro Sonnet → REVISAO_HUMANA (poucos).

TÍTULO limpo (nunca "nome troncho"): PubMed/EPMC via DOI dá título+revista+data pro rename;
se não houver, mantém o nome original. (Extração de título da 1ª página = melhoria futura.)

Uso: python src/classificador_ouro.py <PASTA> [--dry-run] [--max N]
"""
import os
import re
import shutil
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


# ============================ RÓTULO DO TOPO (manda antes do PubMed) ============================
# Editorial/comentário/carta ROUBA o DOI do artigo que comenta → PubMed carimba errado e promove
# a artigo_original. Trava do Dr. Eduardo: o rótulo do TOPO da 1ª página decide o tipo ANTES do DOI,
# e nesses casos o DOI é suspeito (emprestado) → não renomeia pelo PubMed (título verídico > bonito).
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
    linhas = [l.strip() for l in (texto or "")[:600].splitlines()]
    linhas = [l for l in linhas if l and not re.fullmatch(r"[.\s·•]+", l)]
    for l in linhas[:6]:
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
    linhas = [l.strip() for l in (texto or "")[:600].splitlines()]
    linhas = [l for l in linhas if l and not re.fullmatch(r"[.\s·•]+", l)]
    for l in linhas[:6]:
        if _ROT_ORIG.match(l):
            return l
    return None


# ============================ CAMADA B/C — SONNET lê a 1ª página ============================
# Nota: META já foi decidida pelo título ANTES do Sonnet. Aqui o Sonnet NÃO tem a opção meta.

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
        return None, "", ""
    try:
        import llm_client, modelos as M
        out = llm_client.gerar(M.CLASSIFICACAO, CP.montar(texto3), max_tokens=700, temperatura=0)
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
        return (tipo or None), conf, prova
    except Exception as e:
        if not _llm_erro_mostrado:
            print(f"   ⚠️ classificador LLM falhou: {type(e).__name__} - {e}")
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
    print("cascata: mapa de revista → descarte → Sonnet(1ª página) → revisão humana\n")
    cont = {}
    via_mapa = via_sonnet = via_pubmed = 0
    vistos_doi = {}    # DOI confiável → nome do 1º arquivo (dedup por identidade)
    quedas_seguidas = 0   # disjuntor: N seguidas = rede fora, para a rodada
    alvos_usados = {}  # nome-alvo → 1º arquivo (rede de segurança contra colisão de nome)

    for i, nome in enumerate(pdfs, 1):
        caminho = os.path.join(pasta, nome)
        try:
            texto = ext.extract_text(caminho)
        except Exception:
            texto = ""
        doi = extrair_doi(texto)

        # título/metadados p/ rename (grátis) — e pubtypes p/ o descarte determinístico
        pubtypes, meta, falha_rede = [], {}, False
        if doi:
            try:
                pubtypes, meta = pubmed_lookup(doi)
                if not meta:
                    _, meta = europepmc_lookup(doi)
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

        # TRAVA: rede caiu → NÃO classifica, NÃO renomeia. Vai pro balde de retentar.
        if falha_rede:
            destino, marca, via = "RETRY", "🌐", "falha de rede → retentar"
        # CAMADA A — mapa de revista
        elif (destino := mapa_revista(doi)):
            marca, via = "🗺️", "mapa de revista"
            via_mapa += 1
        # RÓTULO DO TOPO manda antes do PubMed (editorial/comentário/carta não vira artigo original)
        elif rotulo_topo(texto)[0]:
            destino, rot_l = rotulo_topo(texto)
            marca, via, rotulado = "🏷️", f"rótulo do topo: {rot_l}", True
        # CAMADA D — descarte determinístico
        elif eh_descartavel(pubtypes, meta.get("title", ""), texto):
            destino, marca, via = "DESCARTE", "⛔", f"descarte: caso/carta {pubtypes or ''}"
        # META pelo TÍTULO (convenção das revistas — determinístico, não depende do Sonnet)
        elif _META_TITULO.search((meta.get("title", "") or texto[:250])):
            destino, marca, via = "revisao_sistematica_meta_analise", "🏷️", "título: meta-análise"
        # PubMed AUTORITATIVO: se já tem tipo específico catalogado (RCT/Multicenter/Review/…), usa ele
        elif pubtypes and map_pubtype(pubtypes):
            destino, marca, via = map_pubtype(pubtypes), "✅", f"PubMed {pubtypes}"
            via_pubmed += 1
        # RÓTULO POSITIVO do topo (última trava determinística antes do Sonnet)
        elif (rot_o := rotulo_original(texto)):
            destino, marca, via = "artigo_original", "🏷️", f"rótulo do topo: {rot_o}"
        else:
            # CAMADA B/C — o JUIZ LLM lê as PÁGINAS 1 A 3 com o prompt v3 (medido: 110/111 = 99,1 %)
            tipo, conf, prova = classificar_llm(caminho)
            via_sonnet += 1
            # A CONFIANÇA E A PROVA SÃO NOVAS, e mandam (LEI 8, ponto 4: "na dúvida, REVISÃO HUMANA.
            # Classificar errado custa mais caro que não classificar"). Antes a produção recebia só a
            # palavra do tipo: um chute com cara de certeza e um acerto seguro chegavam iguais.
            # Agora o modelo tem de CITAR o trecho do artigo que sustenta a resposta — sem trecho,
            # ou com confiança 'baixa', ninguém entra em pasta nenhuma.
            sem_base = (conf == "baixa") or (len((prova or "").strip()) < 12)
            if tipo in ("relato_de_caso", "carta_de_pesquisa"):
                destino, marca, via = "DESCARTE", "⛔", f"LLM: {tipo} ({conf})"
            elif tipo is None:
                destino, marca, via = "REVISAO", "🔴", "o LLM não respondeu"
            elif sem_base:
                destino, marca, via = "REVISAO", "🔴", f"LLM disse {tipo} mas SEM BASE (conf={conf or '—'})"
            elif tipo in FOLDERS:
                # META deixou de ir para revisão humana: o prompt v3 tem a TRAVA DA REVISÃO
                # SISTEMÁTICA (só responde meta se o artigo DECLARAR busca/PRISMA/I²/pooled), e foi
                # com essa trava que o 99,1 % foi medido. Desconfiar aqui seria desperdiçar a trava.
                destino, marca, via = tipo, "🤖", f"LLM v3 pág.1-3 ({conf}): {prova[:60]}"
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

        print(f"[{i}/{len(pdfs)}] {marca} {nome[:56]}")
        print(f"        DOI: {doi or '(não achado)'} | via: {via}")
        print(f"        → {rel}/" + (f"  ({novo})" if novo != nome else ""))

        if not dry_run:
            os.makedirs(dest_dir, exist_ok=True)
            shutil.move(caminho, os.path.join(dest_dir, novo))

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
    print(f"Resolvidos: MAPA {via_mapa} | PubMed autoritativo {via_pubmed} | LLM {via_sonnet}  (grátis: {via_mapa + via_pubmed})")

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
            print(f"\n⚠️ não gravei o diário: {type(e).__name__}: {e}")

    if dry_run:
        print("(dry-run — nada foi movido.)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Classificador OURO (mapa de revista → descarte → Sonnet)")
    ap.add_argument("pasta", help="Pasta com os PDFs")
    ap.add_argument("--dry-run", action="store_true", help="Só mostra o que faria (não move)")
    ap.add_argument("--max", type=int, default=0, help="Processar no máximo N PDFs")
    a = ap.parse_args()
    classificar(os.path.expanduser(a.pasta), dry_run=a.dry_run, max_n=a.max)
