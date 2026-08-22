"""
mesh_llm.py — O PLANO B DO MeSH: descritores propostos pelo modelo, AMARRADOS ao oficial.

═══ 22/Ago/2026 — POR QUE ESTE ARQUIVO EXISTE ═══

O `tema_llm.py` (18/Ago) resolveu o TEMA quando o PubMed ainda não indexou. Sobrou o
`mesh_terms` — e ele é o que o **Pesquisador** usa para achar material. Sem descritor, o
artigo existe no banco e é invisível para quem procura.

**MEDIDO em 22/Ago, no acervo de 704:**

    mesh_terms vazio ......................... 208  (30 %)
      · 38 anteriores à era do DOI (doc_id "Sintetico_"): CONSENSUS 1987, CIBIS-II,
           RALES, MERIT-HF, COPERNICUS, FAME — DOI não existia, não há o que buscar
      ·  1 DOI truncado ("10.2174", sem sufixo) — defeito, nunca vai resolver
      · 169 com DOI real, 157 deles de 2026

E a medida que decidiu o desenho — amostra de 25 do grupo dos 169, perguntando ao PubMed
AGORA:

    JÁ TEM MeSH hoje: 0/25
      21 estão no PubMed, sem MeSH ainda
       4 nem estão no PubMed (diretrizes SBC, Position Statements 2026)

**Zero.** Então "rodar a varredura de novo" não conserta nada hoje. O indexador humano da
NLM leva de semanas a meses, e o Dr. Eduardo já havia recusado isso como atenuante: *"não
serve como fator amenizante — devemos preencher 100 % da tabela"*. Ele tem razão, e a
medida mostra por quê: esperar significa deixar os artigos MAIS NOVOS — os que ele mais
quer entregar — fora do alcance da busca.

Decisão dele, 22/Ago: **o LLM propõe, amarrado ao vocabulário oficial, e a varredura
semanal substitui pelo MeSH autoritativo quando ele aparecer.**

═══ A AMARRA — E POR QUE ELA NÃO É ENFEITE ═══

Um descritor inventado é PIOR que descritor nenhum: ele parece indexação, entra na busca, e
nunca casa com nada — porque o Pesquisador procura pelo vocabulário real. "Heart Attack" não
existe no MeSH; o descritor é "Myocardial Infarction". Por isso toda proposta do modelo passa
por `resolver()`, e **o que não resolve é DESCARTADO**, não gravado com ressalva.

Três camadas, da mais barata para a mais cara:

    1 · cache local (`src/dados/mesh_cache_llm.json`) — só cresce, nunca expira
    2 · `mesh_arvore.json` — os 849 descritores que o acervo já usa, com sinônimos
    3 · E-utilities `db=mesh` — a NLM decide; o resultado entra no cache

⚠️ POR QUE NÃO SE BAIXA O VOCABULÁRIO INTEIRO. Tentei, em 22/Ago, e medi antes de usar: o
endpoint SPARQL da NLM **teta em 1.000 linhas e ignora o LIMIT maior**, e recusa offsets
altos com resposta vazia — sem erro. A paginação por OFFSET teria gravado um arquivo chamado
"vocabulário oficial completo" contendo um quinto do MeSH, em silêncio. Está registrado no
cabeçalho do `scripts/puxar_arvore_mesh.py`.

═══ A PROCEDÊNCIA (`mesh_origem`) ═══
Mesma razão do `tema_origem`, e a decisão de 18/Ago vale igual aqui: o MeSH humano é
auditável, o do modelo é palpite barato. Sem guardar quem propôs, o palpite vira permanente
sem ninguém perceber. Vocabulário da coluna:

    pubmed ............ descritor humano da NLM — a verdade, e substitui qualquer outro
    mesh_llm .......... proposto pelo modelo e RESOLVIDO contra o oficial
    nao_se_aplica ..... não há o que buscar (anterior à era do DOI e sem texto útil)

═══ CUSTO MEDIDO ═══
    ~2.400 tokens de entrada por artigo (título + 2 páginas)
    cadeia CLASSIFICACAO ....... ~US$ 0,0006/artigo  →  208 artigos ≈ US$ 0,13
A resolução contra a NLM é grátis e, pelo cache, converge: os 208 artigos compartilham
descritores (Humans, Heart Failure, Aged…), então a maioria das consultas some na 2ª dezena.
"""
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

_AQUI = os.path.dirname(os.path.abspath(__file__))
if _AQUI not in sys.path:
    sys.path.insert(0, _AQUI)

import llm_client
import modelos as M

CACHE = os.path.join(_AQUI, "dados", "mesh_cache_llm.json")
ARVORE = os.path.join(_AQUI, "dados", "mesh_arvore.json")
EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
PAUSA = 0.35                      # 3/s é o limite da NCBI sem chave

MIN_DESCRITORES = 4               # abaixo disto a proposta não indexa nada — é falha
MAX_DESCRITORES = 14

SCHEMA = {
    "type": "object",
    "properties": {
        "descritores": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": MIN_DESCRITORES,
            "maxItems": MAX_DESCRITORES,
        },
        "porque": {"type": "string"},
    },
    "required": ["descritores", "porque"],
    "additionalProperties": False,
}

INSTRUCAO = """Você indexa artigos para a National Library of Medicine.

Leia o artigo e escreva os DESCRITORES MeSH que um indexador humano da NLM atribuiria.

REGRAS ABSOLUTAS:

1. Use o TERMO OFICIAL do MeSH (o "Descriptor / MeSH Heading"), em INGLÊS, com a grafia
   exata da NLM — inclusive a forma invertida quando for o caso:
       "Myocardial Infarction"        (NÃO "heart attack", NÃO "infarto")
       "Heart Failure"                (NÃO "cardiac insufficiency")
       "Hypertension, Pulmonary"      (invertido, como a NLM escreve)
       "Death, Sudden, Cardiac"       (invertido)
       "Defibrillators, Implantable"  (invertido, plural)
   Se você não tem certeza da grafia oficial de um conceito, NÃO o escreva. Descritor
   inventado é pior que descritor faltando: entra na busca e nunca casa com nada.

2. NÃO use qualificadores/subheadings ("/therapy", "/drug effects"). Só o descritor.

3. Cubra as QUATRO faces do artigo, nesta ordem de importância:
       · a DOENÇA ou condição estudada
       · a INTERVENÇÃO, droga, dispositivo ou método
       · a POPULAÇÃO (inclua "Humans", "Aged", "Female", "Male" quando couber)
       · o DESENHO do estudo ("Randomized Controlled Trials as Topic", "Meta-Analysis as
         Topic", "Practice Guidelines as Topic", "Cohort Studies", "Registries")

4. Entre 6 e 12 descritores. Prefira o ESPECÍFICO ao genérico: "Atrial Fibrillation" vale
   mais que "Arrhythmias, Cardiac"; "Sodium-Glucose Transporter 2 Inhibitors" vale mais que
   "Hypoglycemic Agents". Só suba para o genérico se o artigo for mesmo genérico.

5. Em "porque", uma frase curta dizendo o que o artigo é. Em português.

Responda APENAS o JSON."""


# ─────────────────────────────────────────────────────────────────────────────
# A AMARRA
# ─────────────────────────────────────────────────────────────────────────────

def _carregar(caminho, padrao):
    try:
        with open(caminho, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return padrao


_cache = None
_sinonimos = None


def _indices():
    """(cache, sinônimo→descritor). Carregados uma vez por processo."""
    global _cache, _sinonimos
    if _cache is None:
        _cache = _carregar(CACHE, {})
    if _sinonimos is None:
        _sinonimos = {}
        for rotulo, v in (_carregar(ARVORE, {}) or {}).items():
            if not isinstance(v, dict) or not v.get("arvores"):
                continue                       # não resolveu na árvore: não serve de âncora
            _sinonimos[rotulo.strip().lower()] = rotulo
            for s in (v.get("sinonimos") or []):
                _sinonimos.setdefault(s.strip().lower(), rotulo)
    return _cache, _sinonimos


def _gravar_cache():
    if _cache is None:
        return
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    tmp = CACHE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(_cache, f, ensure_ascii=False, indent=0, sort_keys=True)
    os.replace(tmp, CACHE)             # troca atômica: nunca deixa o cache pela metade


def _perguntar_a_nlm(termo):
    """O descritor oficial, ou None. Só a NLM responde isto."""
    try:
        q = urllib.parse.urlencode({"db": "mesh", "term": f'"{termo}"[MeSH Terms]',
                                    "retmode": "json", "retmax": "1"})
        with urllib.request.urlopen(f"{EUTILS}/esearch.fcgi?{q}", timeout=25) as f:
            ids = (json.load(f)["esearchresult"].get("idlist") or [])
        if not ids:
            return None
        time.sleep(PAUSA)
        with urllib.request.urlopen(f"{EUTILS}/esummary.fcgi?db=mesh&id={ids[0]}&retmode=json",
                                    timeout=25) as f:
            res = json.load(f)["result"]
        d = res.get(ids[0]) or {}
        # o esummary do db=mesh chama o cabeçalho oficial de `ds_meshterms[0]`
        termos = d.get("ds_meshterms") or []
        return (termos[0] if termos else d.get("ds_meshui") and None) or None
    except Exception:
        return None


def resolver(termo, offline=False):
    """O descritor OFICIAL correspondente, ou None se não existe no MeSH.

    ⚠️ `None` aqui significa "não é descritor MeSH" e o chamador DESCARTA. Nunca significa
    "não consegui perguntar": quando a rede falha, `_perguntar_a_nlm` devolve None e o termo
    entraria como inexistente. Por isso a falha de rede é registrada no cache como ausência
    do PRÓPRIO REGISTRO (nada é gravado), e não como `null` — assim a próxima rodada
    pergunta de novo em vez de herdar um "não existe" que era só a rede caindo.
    """
    t = (termo or "").strip()
    if not t:
        return None
    cache, sins = _indices()
    chave = t.lower()

    if chave in cache:
        return cache[chave]                    # já resolvido (ou já sabidamente inexistente)
    if chave in sins:
        cache[chave] = sins[chave]
        return cache[chave]
    if offline:
        return None

    oficial = _perguntar_a_nlm(t)
    time.sleep(PAUSA)
    if oficial:
        cache[chave] = oficial
        cache.setdefault(oficial.strip().lower(), oficial)
        return oficial
    # não achou: grava a ausência NOMEADA, para não repetir a pergunta a cada rodada.
    # Se foi a rede, o `_perguntar_a_nlm` já devolveu None sem distinguir — e é por isso
    # que existe o `--reconferir` do script de preenchimento, que limpa os None do cache.
    cache[chave] = None
    return None


def amarrar(propostos, offline=False):
    """(oficiais, descartados) — a lista limpa e o que caiu, para poder auditar."""
    oficiais, descartados, vistos = [], [], set()
    for p in (propostos or []):
        o = resolver(p, offline=offline)
        if not o:
            descartados.append(p)
            continue
        if o.lower() in vistos:
            continue
        vistos.add(o.lower())
        oficiais.append(o)
    _gravar_cache()
    return oficiais, descartados


# ─────────────────────────────────────────────────────────────────────────────
# O PLANO B
# ─────────────────────────────────────────────────────────────────────────────

def descritores(titulo, texto, revista="", offline=False):
    """(termos_oficiais, origem, detalhe).

    origem == 'mesh_llm'  → deu certo, os termos são oficiais e conferidos
    origem == 'falha'     → o modelo ou a amarra não entregaram; QUEM CHAMA TRATA COMO FALHA,
                            nunca como "esse artigo não tem descritor".
    """
    ctx = f"REVISTA: {revista}\nTÍTULO: {titulo}\n\nTEXTO:\n{(texto or '')[:9000]}"
    ultimo = ""
    for tentativa in (1, 2):
        try:
            r = llm_client.gerar_json(M.CLASSIFICACAO, INSTRUCAO, SCHEMA,
                                      contexto=ctx, max_tokens=700, nome="mesh")
            if isinstance(r, str):
                r = json.loads(re.sub(r"^```(?:json)?|```$", "", r.strip(), flags=re.M).strip())
            props = (r or {}).get("descritores") or []
            if props:
                oficiais, fora = amarrar(props, offline=offline)
                if len(oficiais) >= MIN_DESCRITORES:
                    det = f"{len(oficiais)} de {len(props)} resolvidos"
                    if fora:
                        det += f" · descartados: {', '.join(fora[:4])}"
                    return oficiais, "mesh_llm", det
                ultimo = (f"só {len(oficiais)} de {len(props)} resolveram no MeSH oficial "
                          f"(mínimo {MIN_DESCRITORES}) · descartados: {', '.join(fora[:5])}")
            else:
                ultimo = "o modelo não devolveu descritor nenhum"
        except Exception as e:
            ultimo = f"{type(e).__name__}: {str(e)[:80]}"
        if tentativa == 1:
            time.sleep(2)
    return [], "falha", ultimo


if __name__ == "__main__":                       # prova de bancada, sem LLM
    print("amarra — resolvendo contra a NLM:\n")
    for t in ["heart attack", "Myocardial Infarction", "hypertension pulmonary",
              "SGLT2 inhibitors", "Defibrillators, Implantable", "Cardiodaily Syndrome"]:
        o = resolver(t)
        print(f"   {t:<32} → {o if o else '✗ DESCARTADO (não é descritor MeSH)'}")
    _gravar_cache()
