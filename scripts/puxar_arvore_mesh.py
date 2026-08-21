"""
puxar_arvore_mesh.py — os números de ÁRVORE de cada descritor MeSH, direto da NLM.

═══ POR QUE ═══
O `src/dados/mesh_para_tema.json` é um dicionário que eu montei à mão em 17/Ago: 303
descritores, um por um. Media 80 % de acerto e tinha erros que só um mapa manual comete —
"Guidelines for the Prevention of Work-Related Musculoskeletal Disorders" caiu em Coronária/DAC
porque algum descritor genérico bateu.

A NLM já tem essa informação, oficial e completa: **a árvore MeSH.** Cada descritor sabe onde
mora, e a posição diz o que ele é:

    Hypertension, Pulmonary  →  D006976
        C08.381.423        doenças respiratórias
        C14.907.489.556    doenças cardiovasculares  ← C14 = cardiovascular

Um descritor de ergonomia ocupacional não está sob C14. O mapa estrutural não comete esse erro.

Decisão dele, 20/Ago: *"vale trocar o mapa à mão pela árvore oficial? SIM — faça isso, mesmo
que custe."*

═══ A FONTE ═══
    https://id.nlm.nih.gov/mesh/sparql   — pública, sem chave, sem cadastro
Documentação: https://hhs.github.io/meshrdf/sparql-and-uri-requests

Este programa só LÊ e grava um cache local. Nada de Supabase, nada de LLM, custo zero.

Uso:  python3 scripts/puxar_arvore_mesh.py          # continua de onde parou
      python3 scripts/puxar_arvore_mesh.py --zero
"""
import json
import os
import sys
import time
import urllib.parse
import urllib.request

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DESTINO = os.path.join(RAIZ, "src", "dados", "mesh_arvore.json")
FREQ = os.path.join(RAIZ, "src", "dados", "mesh_freq.json")
SPARQL = "https://id.nlm.nih.gov/mesh/sparql"
PAUSA = 0.25          # a NLM não publica limite; 4/s é educado e nunca levou 429 aqui


def consultar(query, limite=200):
    u = SPARQL + "?" + urllib.parse.urlencode(
        {"query": query, "format": "JSON", "limit": limite, "inference": "true"})
    r = urllib.request.Request(u, headers={"Accept": "application/sparql-results+json",
                                           "User-Agent": "CardioDaily/1.0"})
    return json.load(urllib.request.urlopen(r, timeout=60))["results"]["bindings"]


def em_lote(rotulos):
    """{rótulo: {id, arvores}} — VÁRIOS numa consulta só.

    ⚠️ A primeira versão perguntava UM POR UM, com duas consultas cada: 40 descritores em 2
    minutos, ou seja **40 minutos** para os 849. Com `VALUES` o SPARQL resolve o lote inteiro
    numa ida: 8 de 8 na primeira prova. A diferença não é conforto — é a diferença entre uma
    ferramenta que se roda quando precisa e uma que se evita rodar.
    """
    vals = " ".join('"{}"@en'.format(r.replace('"', '\\"')) for r in rotulos)
    q = ('PREFIX meshv: <http://id.nlm.nih.gov/mesh/vocab#>\n'
         'PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>\n'
         'SELECT ?l ?d ?tree WHERE {\n'
         f'  VALUES ?l {{ {vals} }}\n'
         '  ?d rdfs:label ?l . ?d meshv:treeNumber ?tn . ?tn rdfs:label ?tree . }')
    out = {}
    for b in consultar(q, 5000):
        r = b["l"]["value"]
        d = out.setdefault(r, {"id": b["d"]["value"].rsplit("/", 1)[-1], "arvores": set()})
        d["arvores"].add(b["tree"]["value"])
    return {k: {"id": v["id"], "arvores": sorted(v["arvores"])} for k, v in out.items()}


def sinonimos_em_lote(ids):
    """{id: [termos de entrada]} — o que o médico digita e que aponta para o descritor."""
    vals = " ".join(f"<http://id.nlm.nih.gov/mesh/{i}>" for i in ids)
    q = ('PREFIX meshv: <http://id.nlm.nih.gov/mesh/vocab#>\n'
         'PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>\n'
         'SELECT ?d ?termo WHERE {\n'
         f'  VALUES ?d {{ {vals} }}\n'
         '  ?d meshv:concept ?c . ?c meshv:term ?t . ?t rdfs:label ?termo }')
    out = {}
    for b in consultar(q, 5000):
        out.setdefault(b["d"]["value"].rsplit("/", 1)[-1], set()).add(b["termo"]["value"])
    return {k: sorted(v) for k, v in out.items()}


def main():
    if "--zero" in sys.argv and os.path.exists(DESTINO):
        os.remove(DESTINO)
    cache = json.load(open(DESTINO, encoding="utf-8")) if os.path.exists(DESTINO) else {}

    # os descritores que o acervo REALMENTE usa — não a árvore inteira (30 mil), que seria
    # varrer o oceano para pescar num aquário.
    alvos = sorted(json.load(open(FREQ, encoding="utf-8")))
    pend = [t for t in alvos if t not in cache]
    print(f"{len(alvos)} descritores no acervo · {len(cache)} já na árvore · {len(pend)} a buscar\n")

    LOTE = 60
    for i in range(0, len(pend), LOTE):
        bloco = pend[i:i + LOTE]
        try:
            achados = em_lote(bloco)
            sins = sinonimos_em_lote([v["id"] for v in achados.values()]) if achados else {}
        except Exception as e:
            print(f"   ⚠️ lote {i//LOTE+1}: {type(e).__name__}: {str(e)[:60]}")
            continue
        for t in bloco:
            v = achados.get(t)
            # ⚠️ quem NÃO resolveu entra no cache com listas vazias, de propósito: sem isso,
            # a retomada tentaria os mesmos para sempre. E "procurei e não achou" é resposta —
            # significa que a grafia não é a de descritor (é qualificador, ou termo de entrada).
            cache[t] = {"id": v["id"] if v else None,
                        "arvores": v["arvores"] if v else [],
                        "sinonimos": sins.get(v["id"], []) if v else []}
        json.dump(cache, open(DESTINO, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
        print(f"   {min(i+LOTE, len(pend)):>4}/{len(pend)}  "
              f"{sum(1 for v in cache.values() if v['arvores'])} na árvore", flush=True)
        time.sleep(PAUSA)

    json.dump(cache, open(DESTINO, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    achados = sum(1 for v in cache.values() if v.get("arvores"))
    print(f"\n✔ {DESTINO}")
    print(f"  {len(cache)} descritores · {achados} com posição na árvore · "
          f"{len(cache)-achados} sem (não são descritores, ou grafia diferente)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
