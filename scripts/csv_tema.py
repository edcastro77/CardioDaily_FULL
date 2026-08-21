"""
csv_tema.py — o tema dos artigos que estão no Supabase sem ele, em CSV para ELE corrigir.

═══ POR QUE ASSIM, E NÃO PELA CHAVE 2 ═══
Eu propus devolver 100 PDFs à fila para o portão preencher a coluna `tema`. Custo medido:
**US$ 19** — e destes, **US$ 0,08 era o tema**. O resto era perícia, ACRI, Visual Abstract e
áudio sendo refeitos sem terem mudado nada. Palavras dele:

    "não tem cabimento pagar 19 dólares, 100 reais, para consertar os buracos — de novo estas
     reanálises para consertar buracos que eram para existir..."

Ele está certo, e a decisão dele é melhor que as três opções que eu tinha listado: **este
programa só LÊ e escreve um CSV.** Ele confere na mão, corrige o que discordar, e sobe pelo
Supabase. Quem grava é ele — que é o que a LEI 12 manda para trabalho manual, e o que a LEI 5
manda para `artigos` (nenhum segundo portão nasce aqui).

⚠️ O CSV **NÃO** é a fonte da verdade daqui pra frente. A torneira já foi fechada: desde
20/Ago o tema é decidido dentro do portão (`ficha_site._decidir_tema`) em todo artigo novo.
Isto aqui é enxugar o chão de uma vez, à mão, e nunca mais.

Custo: ~US$ 0,0008/artigo (medido) → **US$ 0,09 nos 117**.

Uso:  python3 scripts/csv_tema.py          # continua de onde parou; grava a cada artigo
      python3 scripts/csv_tema.py --zero   # recomeça
"""
import csv
import json
import os
import sys
import urllib.parse
import urllib.request

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "src"))
from dotenv import load_dotenv
load_dotenv(os.path.join(RAIZ, ".env"))
import tema_llm

SAIDA = os.path.join(RAIZ, "saidas", "TEMAS_PARA_CORRIGIR.csv")
COLUNAS = ["doc_id", "titulo", "tipo_documento", "nota",
           "tema", "tema_secundario", "tema_origem",
           "onde_se_aplica", "natureza", "quem_le", "porque",
           "CORRIGIR_tema", "CORRIGIR_tema_secundario"]


def faltantes():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    h = {"apikey": key, "Authorization": f"Bearer {key}"}
    q = urllib.parse.urlencode({
        "select": "doc_id,titulo,revista,tipo_documento,nota_aplicabilidade,"
                  "contexto_tema,aplicabilidade_pratica",
        "tema": "is.null", "limit": "2000", "order": "nota_aplicabilidade.desc"})
    return json.load(urllib.request.urlopen(
        urllib.request.Request(f"{url}/rest/v1/artigos?{q}", headers=h), timeout=60))


def main():
    if "--zero" in sys.argv and os.path.exists(SAIDA):
        os.remove(SAIDA)

    # ⚠️ AQUI EU ESQUECI O `delimiter=";"` E PAGUEI DUAS VEZES POR 49 ARTIGOS.
    # O arquivo é gravado com `;` (padrão pt-BR, para o Excel abrir certo) e lido sem — então
    # cada linha virava UMA coluna só, `doc_id` saía vazio, `feitos` ficava vazio, e a retomada
    # reclassificava tudo de novo. Resultado medido: 99 linhas para 50 artigos.
    # É a família de sempre: leitura que "funciona" e devolve nada, sem erro nenhum. E é a
    # segunda vez hoje que a retomada me engana — a primeira foi ler o JSON antes de a rodada
    # terminar. Retomada tem de ser CONFERIDA, não suposta.
    feitos = set()
    if os.path.exists(SAIDA):
        with open(SAIDA, encoding="utf-8-sig") as f:
            feitos = {l["doc_id"] for l in csv.DictReader(f, delimiter=";") if l.get("tema")}
        print(f"   retomada: {len(feitos)} doc_id já no CSV (se vier 0 com arquivo cheio, "
              f"a leitura está quebrada)")

    linhas = faltantes()
    print(f"{len(linhas)} sem tema · {len(feitos)} já classificados nesta rodada\n")

    novo = not os.path.exists(SAIDA)
    with open(SAIDA, "a", newline="", encoding="utf-8-sig") as f:   # BOM: o Excel abre certo
        w = csv.DictWriter(f, fieldnames=COLUNAS, delimiter=";")     # ; = padrão pt-BR
        if novo:
            w.writeheader()
        for i, r in enumerate(linhas, 1):
            if r["doc_id"] in feitos:
                continue
            txt = " ".join(str(r.get(k) or "")
                           for k in ("contexto_tema", "aplicabilidade_pratica"))
            try:
                tema, sec, porque = tema_llm.classificar(
                    r.get("titulo") or "", txt, r.get("revista") or "")
            except Exception as e:
                tema, sec, porque = None, None, f"FALHOU {type(e).__name__}: {e}"
            # o tripé sai em colunas próprias: é o que permite ele DISCORDAR com fundamento,
            # em vez de só ver um rótulo e ter de adivinhar de onde veio.
            eixos = {"onde_se_aplica": "", "natureza": "", "quem_le": ""}
            resto = porque or ""
            if resto.startswith("[") and "]" in resto:
                dentro, resto = resto[1:resto.index("]")], resto[resto.index("]") + 1:].strip()
                for parte in dentro.split("·"):
                    if ":" in parte:
                        c, v = parte.split(":", 1)
                        c = c.strip().replace("lê", "quem_le")
                        if c in eixos:
                            eixos[c] = v.strip()
            w.writerow({"doc_id": r["doc_id"], "titulo": (r.get("titulo") or "")[:200],
                        "tipo_documento": r.get("tipo_documento") or "",
                        "nota": r.get("nota_aplicabilidade") or "",
                        "tema": tema or "", "tema_secundario": sec or "Não se aplica",
                        "tema_origem": "llm" if tema else "falha_do_classificador",
                        **eixos, "porque": resto[:300],
                        "CORRIGIR_tema": "", "CORRIGIR_tema_secundario": ""})
            f.flush()                                   # a cada linha: rodada que morre no meio
            print(f"  {i:>3}/{len(linhas)}  {tema}", flush=True)   # não perde o que já pagou

    print(f"\n✔ {SAIDA}")
    print("  Confira e preencha as colunas CORRIGIR_* só onde discordar.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
