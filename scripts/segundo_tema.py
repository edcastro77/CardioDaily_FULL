"""
segundo_tema.py — preenche o `tema_secundario` que está NULL, agora que o MeSH chegou.

═══ POR QUE ═══
Medido em 21/Ago: **282 de 616** com `tema_secundario IS NULL`. Olhando por dia, a causa fica
óbvia e é minha:

    06 a 17/Ago ..... 507 linhas · 275 NULL · 6 "Não se aplica"
    19/Ago ..........  83 linhas ·   2 NULL · 29 "Não se aplica"

No dia 19 quase não há NULL porque foi o lote que passou pelo portão DEPOIS da LEI 11 — quando
`None` virou texto. Os 275 anteriores foram gravados quando vazio ainda era vazio.

E mudou outra coisa: o `MESH_IMPORTAR.sql` encheu `mesh_terms` em 254 linhas. **Muitas dessas
linhas decidiram o tema quando ainda não tinham descritor nenhum.** Agora têm — e o 2º tema sai
justamente daí.

Por isso a ORDEM importa, e inverter estragaria:
    ① recalcular o 2º tema com o MeSH que chegou   ← tema DE VERDADE
    ② só o que sobrar vira "Não se aplica"          ← o vazio com nome (LEI 11)
Se marcar "não se aplica" primeiro, some o artigo que teria segundo tema.

⚠️ O PISO CONTINUA EM 0,40 — decisão dele, 21/Ago: *"tendo as keywords, acho que não fará tanta
diferença. Mantém o 0.4."* O 2º tema só existe quando tem pelo menos 40 % do peso do 1º; abaixo
disso é ruído, e o assinante receberia coisa que não pediu.

⚠️ NÃO ESCREVE NO BANCO (LEI 5): gera `saidas/SEGUNDO_TEMA.sql` para ele rodar.

Uso:  python3 scripts/segundo_tema.py
"""
import collections
import json
import os
import sys
import urllib.parse
import urllib.request

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "src"))
from dotenv import load_dotenv
load_dotenv(os.path.join(RAIZ, ".env"))
import tema_mesh as TM
from temas import TEMAS

SQL = os.path.join(RAIZ, "saidas", "SEGUNDO_TEMA.sql")
NAO_SE_APLICA = "Não se aplica"


def main():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    h = {"apikey": key, "Authorization": f"Bearer {key}"}
    q = urllib.parse.urlencode({
        "select": "doc_id,titulo,tema,tema_secundario,mesh_terms",
        "tema_secundario": "is.null", "limit": "3000"})
    linhas = json.load(urllib.request.urlopen(
        urllib.request.Request(f"{url}/rest/v1/artigos?{q}", headers=h), timeout=60))
    print(f"{len(linhas)} linha(s) com tema_secundario NULL\n")

    mapa = json.load(open(os.path.join(RAIZ, "src", "dados", "mesh_para_tema.json"),
                          encoding="utf-8"))
    freq = collections.Counter(json.load(open(
        os.path.join(RAIZ, "src", "dados", "mesh_freq.json"), encoding="utf-8")))

    achou, na, sem_mesh = [], [], 0
    for r in linhas:
        ms = r.get("mesh_terms") or []
        if not ms:
            sem_mesh += 1
            na.append(r)
            continue
        p, s, _margem, _det = TM.decidir(ms, mapa, freq)
        # ⚠️ O 2º tema é o que o MeSH aponta E que seja DIFERENTE do principal já gravado.
        # Sem esta checagem, um artigo cujo MeSH concorda com o LLM ganharia o MESMO tema nas
        # duas colunas — e o card mostraria "Insuficiência Cardíaca · Insuficiência Cardíaca".
        cand = next((c for c in (p, s) if c and c != r.get("tema") and c in TEMAS), None)
        (achou if cand else na).append((r, cand) if cand else r)

    def esc(x):
        return str(x).replace("'", "''")

    with open(SQL, "w", encoding="utf-8") as f:
        f.write("-- 2º TEMA (21/Ago/2026). Duas etapas, nesta ordem — inverter estragaria.\n")
        f.write("-- Piso 0,40 mantido por decisao dele: 2o tema so com >=40% do peso do 1o.\n")
        f.write("-- So toca onde tema_secundario IS NULL: nao sobrescreve nada.\n\n")
        f.write("BEGIN;\n\n-- (1) os que o MeSH resolveu — tema DE VERDADE\n")
        for r, cand in achou:
            f.write(f"UPDATE artigos SET tema_secundario='{esc(cand)}' "
                    f"WHERE doc_id='{esc(r['doc_id'])}' AND tema_secundario IS NULL;\n")
        f.write("\n-- (2) o que sobrou: o vazio ganha NOME (LEI 11), nunca fica NULL\n")
        f.write(f"UPDATE artigos SET tema_secundario='{esc(NAO_SE_APLICA)}' "
                f"WHERE tema_secundario IS NULL;\n")
        f.write("\nSELECT count(*) FILTER (WHERE tema_secundario IS NULL) AS nulos,\n")
        f.write("       count(*) FILTER (WHERE tema_secundario = 'Não se aplica') AS nao_se_aplica,\n")
        f.write("       count(*) FILTER (WHERE tema_secundario NOT IN ('Não se aplica')) AS com_2o_tema\n")
        f.write("FROM artigos;\nCOMMIT;\n")

    print(f"✔ {SQL}")
    print(f"   com 2º tema de verdade : {len(achou)}")
    print(f"   viram 'Não se aplica'  : {len(na)}  (destes, {sem_mesh} não têm MeSH)")
    if achou:
        print("\n   exemplos do que ganhou 2º tema:")
        for r, c in achou[:8]:
            print(f"     [{r.get('tema')}] + {c}")
            print(f"        {(r.get('titulo') or '')[:66]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
