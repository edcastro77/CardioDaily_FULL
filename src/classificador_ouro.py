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
    eh_descartavel, _novo_nome, FOLDERS, SUB_ANALISE, SUB_DESCARTE, SUB_REVISAO,
    RedeIndisponivel,
)

SUB_RETRY = "RETENTAR_REDE"  # falha de rede (não é troncho): revisar/rodar de novo
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
# Logo, META não sai do Sonnet (que exagera lendo conteúdo) — sai do título. Determinístico.
_META_TITULO = re.compile(r"meta[-\s]?analys", re.I)


# ============================ RÓTULO DO TOPO (manda antes do PubMed) ============================
# Editorial/comentário/carta ROUBA o DOI do artigo que comenta → PubMed carimba errado e promove
# a artigo_original. Trava do Dr. Eduardo: o rótulo do TOPO da 1ª página decide o tipo ANTES do DOI,
# e nesses casos o DOI é suspeito (emprestado) → não renomeia pelo PubMed (título verídico > bonito).
_ROT_PV = re.compile(r"^(editorial(\s+comment)?|editorials|viewpoint|perspective|commentary|point of view)$", re.I)
_ROT_DESC = re.compile(r"^(research letter|letters?|letter to the editor|correspondence|reply|reply to.*)$", re.I)


def rotulo_topo(texto):
    """Olha as primeiras linhas da 1ª página. Devolve ('ponto_de_vista'|'DESCARTE', rótulo) ou (None, None).
    Ancorado em LINHA inteira (não 'contém'), só no topo → não confunde artigo original."""
    linhas = [l.strip() for l in (texto or "")[:600].splitlines()]
    linhas = [l for l in linhas if l and not re.fullmatch(r"[.\s·•]+", l)]
    for l in linhas[:6]:
        if _ROT_PV.match(l):
            return "ponto_de_vista", l
        if _ROT_DESC.match(l):
            return "DESCARTE", l
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
_PROMPT = """Você classifica artigos científicos de cardiologia. Leia a PRIMEIRA PÁGINA abaixo
(título, rótulo do tipo, abstract, keywords) e responda SOMENTE com UMA destas palavras exatas:
artigo_original | revisao_geral | guideline | ponto_de_vista | relato_de_caso | carta_de_pesquisa | incerto

(Meta-análise NÃO é opção aqui — já foi decidida pelo título. Se o artigo parecer meta/revisão sistemática, escolha revisao_geral.)

Como decidir — o CONTEÚDO do Methods é o juiz (a estrutura IMRD engana):
- artigo_original: coleta dados primários em sujeitos. Methods diz "recruited/enrolled/studied N patients", medições, estatística (regression, Cox, ROC, p-values). RCT ("randomized trial", "randomly assigned", "intention-to-treat", registro NCT/EudraCT) também é artigo_original.
- revisao_geral: revisão narrativa, integrativa OU sistemática. Sinais: "literature search", "we review", "state-of-the-art review", "synthesized". Se o rótulo/título diz "Review" → é revisao_geral.
- guideline: diretriz, consenso, scientific statement de sociedade. Em geral SEM IMRD (abstract narrativo). Rótulo/título "Scientific Statement"/"Guideline"/"Consensus".
- ponto_de_vista: editorial, viewpoint, perspectiva, comentário.
- relato_de_caso: relato de caso único ou descrição de técnica em paciente(s).
- carta_de_pesquisa: "research letter" / carta (formato breve).
- incerto: se não der para decidir com segurança.

PRIMEIRA PÁGINA:
{texto}
"""

_llm_erro_mostrado = False


def classify_sonnet(texto):
    """Claude Sonnet lendo a 1ª página. Rótulo canônico, 'relato_de_caso'/'carta_de_pesquisa',
    'incerto' ou None (erro). Nunca engole erro em silêncio."""
    global _llm_erro_mostrado
    if not ANTHROPIC_KEY or not texto:
        return None
    try:
        import llm_client, modelos as M              # cadeia EXTRACAO (sonnet-5) + fallback; teto folgado p/ thinking
        out = llm_client.gerar(M.EXTRACAO, _PROMPT.format(texto=texto[:5000]),
                               max_tokens=2000).strip().lower()
        for cat in ("revisao_sistematica_meta_analise", "artigo_original", "revisao_geral",
                    "guideline", "ponto_de_vista", "carta_de_pesquisa", "relato_de_caso"):
            if cat in out:
                return cat
        return "incerto"
    except Exception as e:
        if not _llm_erro_mostrado:
            print(f"   ⚠️ Sonnet falhou: {type(e).__name__} - {e}")
            _llm_erro_mostrado = True
        return None


# ============================ A CORRENTE ============================
def classificar(pasta, dry_run=True, max_n=0):
    ext = PDFExtractor()
    pdfs = sorted(f for f in os.listdir(pasta)
                  if f.lower().endswith(".pdf") and not f.startswith("._"))
    if max_n:
        pdfs = pdfs[:max_n]

    print(f"\n{'DRY-RUN (nada é movido)' if dry_run else 'EXECUTANDO (move arquivos)'} — {len(pdfs)} PDF(s)")
    print("cascata: mapa de revista → descarte → Sonnet(1ª página) → revisão humana\n")
    cont = {}
    via_mapa = via_sonnet = via_pubmed = 0
    vistos_doi = {}    # DOI confiável → nome do 1º arquivo (dedup por identidade)
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
                print(f"        ⚠️ REDE caiu: {e}")

        rotulado = False  # rótulo do topo disparou → DOI suspeito (emprestado), não renomear pelo PubMed

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
            # CAMADA B/C — Sonnet lê a 1ª página (META NÃO é opção aqui; já decidida pelo título)
            tipo = classify_sonnet(texto)
            via_sonnet += 1
            if tipo in ("relato_de_caso", "carta_de_pesquisa"):
                destino, marca, via = "DESCARTE", "⛔", f"Sonnet: {tipo}"
            elif tipo == "revisao_sistematica_meta_analise":
                # Sonnet disse meta mas o título não declara → não confiar; revisão humana
                destino, marca, via = "REVISAO", "🔴", "meta sem título → revisar"
            elif tipo in FOLDERS:
                destino, marca, via = tipo, "🤖", "Sonnet (1ª página)"
            else:
                destino, marca, via = "REVISAO", "🔴", f"ambíguo (Sonnet={tipo})"

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

    print("\nResumo:", ", ".join(f"{k}={v}" for k, v in sorted(cont.items())))
    print(f"Resolvidos: MAPA {via_mapa} | PubMed autoritativo {via_pubmed} | Sonnet {via_sonnet}  (grátis: {via_mapa + via_pubmed})")
    if dry_run:
        print("(dry-run — nada foi movido.)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Classificador OURO (mapa de revista → descarte → Sonnet)")
    ap.add_argument("pasta", help="Pasta com os PDFs")
    ap.add_argument("--dry-run", action="store_true", help="Só mostra o que faria (não move)")
    ap.add_argument("--max", type=int, default=0, help="Processar no máximo N PDFs")
    a = ap.parse_args()
    classificar(os.path.expanduser(a.pasta), dry_run=a.dry_run, max_n=a.max)
