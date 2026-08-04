"""reparar_capa.py — devolve TÍTULO, REVISTA e ANO aos pacotes já analisados (04/Ago/2026).

═══ POR QUE EXISTE ═══

O `SCHEMA_FATOS_META` foi escrito sem os campos de identificação. As meta-análises saíram do
analisador com `titulo: ""`, `revista: ""`, `ano: ""` no canônico — e o contrato recusou dez
artigos já pagos, com perícia, PDF, áudio e visual prontos.

O buraco no schema já foi tapado; daqui pra frente o extrator devolve a capa. Mas os pacotes
que JÁ existem continuam sem ela, e re-analisar custaria dinheiro para recuperar dado que não
precisa de LLM nenhum.

═══ POR QUE PELO DOI, E NÃO PELO NOME DO ARQUIVO ═══

De manhã eu usei o NOME DA PASTA como 2ª fonte. Funcionou para a revista e o ano, e falhou para
o título: o Dr. Eduardo abriu o PDF e leu

    "Impact of Catheter Ablation on LVEF in Patients with Atrial Fibrillation and Hea"

cortado no meio da palavra. A causa é banal e minha: o classificador corta o título em 90
caracteres para montar o NOME DO ARQUIVO — o que é correto para um nome de arquivo, e errado
como fonte de um título. Nome de arquivo é apelido, não é dado.

O DOI está no canônico. O PubMed devolve o título INTEIRO. É a mesma fonte que o classificador
já usa para nomear, consultada agora sem o corte. Custa zero: E-utilities é aberto.

NÃO fala com o Supabase · NÃO chama LLM · NÃO move arquivo · só reescreve as 3 linhas do
frontmatter do canônico e regera o PDF.
"""
import os, re, sys, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from classificador_pubmed import pubmed_lookup, europepmc_lookup


def _campo(txt, chave):
    m = re.search(rf'^(\s*){chave}:\s*"(.*?)"\s*$', txt, re.M)
    return (m.group(2).strip() if m else ""), bool(m)


def _por(txt, chave, valor):
    valor = (valor or "").replace('"', "'").strip()
    if not valor:
        return txt
    return re.sub(rf'^(\s*){chave}:\s*".*?"\s*$', lambda m: f'{m.group(1)}{chave}: "{valor}"',
                  txt, count=1, flags=re.M)


def reparar(pasta, forcar=False):
    can = glob.glob(os.path.join(pasta, "*_CANONICO.md"))
    if not can:
        return "sem canônico", None
    txt = open(can[0], encoding="utf-8").read()
    tit, _ = _campo(txt, "titulo"); rev, _ = _campo(txt, "revista")
    ano, _ = _campo(txt, "ano");    doi, _ = _campo(txt, "doi")
    if tit and rev and ano and not forcar:
        return "já tinha capa", tit
    if not doi or doi == "n/a":
        return "sem DOI — não dá para consultar", None

    meta = {}
    for fonte in (pubmed_lookup, europepmc_lookup):
        try:
            _, m = fonte(doi)
            if m and (m.get("title") or "").strip():
                meta = m; break
        except Exception:
            continue
    if not meta:
        return f"PubMed/EPMC não acharam o DOI {doi}", None

    novo = _por(_por(_por(txt, "titulo", meta.get("title")),
                     "revista", meta.get("journal")),
                "ano", str(meta.get("year") or "")[:4])
    if novo != txt:
        open(can[0], "w", encoding="utf-8").write(novo)
    return "reparado", (meta.get("title") or "")


if __name__ == "__main__":
    raiz = sys.argv[1] if len(sys.argv) > 1 else "outputs/STAGING"
    forcar = "--forcar" in sys.argv
    import pdf_analise as PA
    print(f"\n REPARO DA CAPA · {raiz}\n" + "─" * 92)
    n_ok = 0
    for p in sorted(glob.glob(os.path.join(raiz, "*"))):
        if not os.path.isdir(p):
            continue
        estado, tit = reparar(p, forcar)
        marca = "✅" if estado == "reparado" else ("·" if estado == "já tinha capa" else "⚠️ ")
        print(f" {marca} {estado:34} {(tit or '')[:52]}")
        if estado == "reparado":
            n_ok += 1
            try:
                PA.gerar_pdf_de_pasta(p)
            except Exception as e:
                print(f"      ⚠️  PDF não regerou: {type(e).__name__}: {str(e)[:60]}")
    print("─" * 92 + f"\n {n_ok} capa(s) reparada(s) e PDF regerado.\n")
