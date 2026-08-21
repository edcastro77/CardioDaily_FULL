"""
mesh_faltantes.py — busca no PubMed os descritores MeSH que faltam, e gera o SQL.

═══ POR QUE ═══
Medido em 20/Ago, varrendo as 29 colunas da tabela `artigos`: **25 estão a zero de nulos**, e o
buraco está concentrado em duas — `mesh_terms` (290 = 47 %) e `tema_secundario` (284 = 46 %).
Os 290 nunca foram buscados: o `puxar_mesh.py` rodou uma vez, em 17/Ago, nos 449 que existiam.

**Custo: ZERO.** O MeSH é do PubMed, é de graça, e é humano (indexador da NLM).

⚠️ `NULL` e `[]` são A MESMA COISA — decisão dele, 20/Ago: *"não aceito, null e [] na prática são
a mesma coisa para mim."* Ele está certo, e eu estava criando uma distinção que não muda nenhuma
ação: se o artigo não tem descritor, ele não aparece na busca — o motivo é irrelevante para quem
procura. Pior, seria significado embutido num detalhe de TIPO em vez de escrito, que é
exatamente a forma de esconder informação contra a qual a LEI 11 existe.
Logo: `mesh_terms` é sempre array, vazio é vazio, e a varredura tenta de novo em TODOS os vazios.

Este programa **NÃO escreve no banco** (LEI 5): gera `saidas/MESH_IMPORTAR.sql` para ele rodar.

Uso:  python3 scripts/mesh_faltantes.py          # continua de onde parou
      python3 scripts/mesh_faltantes.py --zero
"""
import json
import os
import sys
import urllib.parse
import urllib.request

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "src"))
sys.path.insert(0, os.path.join(RAIZ, "scripts"))
from dotenv import load_dotenv
load_dotenv(os.path.join(RAIZ, ".env"))
import puxar_mesh as PM

CACHE = os.path.join(RAIZ, "saidas", "mesh_buscado.json")
SQL = os.path.join(RAIZ, "saidas", "MESH_IMPORTAR.sql")


def sem_mesh():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    h = {"apikey": key, "Authorization": f"Bearer {key}"}
    # vazio E nulo: para ele são a mesma coisa, e a varredura trata os dois igual
    q = urllib.parse.urlencode({"select": "doc_id,doi,titulo", "limit": "3000",
                                "or": "(mesh_terms.is.null,mesh_terms.eq.{})"})
    return json.load(urllib.request.urlopen(
        urllib.request.Request(f"{url}/rest/v1/artigos?{q}", headers=h), timeout=60))


def main():
    if "--zero" in sys.argv and os.path.exists(CACHE):
        os.remove(CACHE)
    achado = json.load(open(CACHE, encoding="utf-8")) if os.path.exists(CACHE) else {}

    linhas = sem_mesh()
    print(f"{len(linhas)} artigo(s) sem MeSH · {len(achado)} já buscados\n")

    # só quem tem DOI de verdade dá para procurar (o DOI sintético não existe no PubMed)
    pendentes = [r for r in linhas
                 if r["doc_id"] not in achado
                 and (r.get("doi") or "").startswith("10.")
                 and "cardiodaily" not in (r.get("doi") or "").lower()]
    print(f"  com DOI buscável: {len(pendentes)}")

    LOTE = 20
    for i in range(0, len(pendentes), LOTE):
        bloco = pendentes[i:i + LOTE]
        try:
            pmids = PM.doi_para_pmid([r["doi"] for r in bloco])
            mesh = PM.mesh_de([p for p in pmids.values() if p])
        except Exception as e:
            print(f"   ⚠️ lote {i//LOTE+1} falhou: {type(e).__name__}: {e}")
            continue
        for r in bloco:
            pm = pmids.get((r.get("doi") or "").lower())
            achado[r["doc_id"]] = mesh.get(pm, []) if pm else []
        json.dump(achado, open(CACHE, "w", encoding="utf-8"), ensure_ascii=False)
        com = sum(1 for v in achado.values() if v)
        print(f"   {min(i+LOTE, len(pendentes)):>3}/{len(pendentes)}  "
              f"{com} com descritor", flush=True)

    # ── o SQL ──
    def esc(s):
        return s.replace("'", "''")

    com = {k: v for k, v in achado.items() if v}
    vazios = [k for k, v in achado.items() if not v]
    with open(SQL, "w", encoding="utf-8") as f:
        f.write("-- MeSH do PubMed para os artigos que estavam sem (20/Ago/2026). Custo: zero.\n")
        f.write("-- Vazio e nulo sao a MESMA COISA (decisao do Dr. Eduardo): quem nao tem\n")
        f.write("-- descritor recebe '{}' e entra na proxima varredura, sem precisar saber por que.\n\n")
        f.write("BEGIN;\n")
        for doc, termos in com.items():
            arr = "ARRAY[" + ",".join(f"'{esc(t)}'" for t in termos) + "]::text[]"
            f.write(f"UPDATE artigos SET mesh_terms={arr} WHERE doc_id='{esc(doc)}';\n")
        if vazios:
            f.write("\n-- procurados e sem descritor no PubMed (artigo novo, sem DOI indexado):\n")
            for doc in vazios:
                f.write(f"UPDATE artigos SET mesh_terms='{{}}'::text[] WHERE doc_id='{esc(doc)}';\n")
        f.write("\n-- e o resto, que nunca teve DOI buscavel: array vazio, nunca NULL\n")
        f.write("UPDATE artigos SET mesh_terms='{}'::text[] WHERE mesh_terms IS NULL;\n")
        f.write("\nSELECT count(*) FILTER (WHERE mesh_terms IS NULL) AS nulos,\n")
        f.write("       count(*) FILTER (WHERE cardinality(mesh_terms)=0) AS vazios,\n")
        f.write("       count(*) FILTER (WHERE cardinality(mesh_terms)>0) AS com_descritor\n")
        f.write("FROM artigos;\n")
        f.write("COMMIT;\n")

    print(f"\n✔ {SQL}")
    print(f"  {len(com)} com descritor · {len(vazios)} procurados e vazios")
    return 0


if __name__ == "__main__":
    sys.exit(main())
