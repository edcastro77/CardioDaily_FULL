"""
prova_lote.py — MEDE A CASCATA INTEIRA num lote de tipo CONHECIDO (03/Ago/2026).

POR QUE EXISTE — o buraco que custou 45 dias.
------------------------------------------------------------------------------
Havia duas medições no projeto, e NENHUMA media o que decide:

  • `prova_classificador.py` mede **só o LLM**. Mas o LLM decide 30% dos artigos —
    os outros 70% morrem nas camadas de cima (mapa de revista, rótulo, título, PubMed),
    que NUNCA foram medidas.
  • o **gabarito** cobre 105 de 511 artigos (20%), e foi montado a partir de uma
    classificação ANTIGA — ou seja, contém justamente os artigos que o sistema velho
    já sabia tratar (LEI 10: o corpus já processado não serve de prova).

Resultado: eu media 99,1% e o Dr. Eduardo abria a pasta e via 12 erros. Os dois números
eram verdadeiros. A régua é que media a coisa errada, e eu nunca disse isso a ele.

O QUE ESTE PROGRAMA FAZ
------------------------------------------------------------------------------
Recebe uma PASTA e o TIPO QUE TODOS OS ARTIGOS DELA SÃO (o Dr. Eduardo baixa 30
meta-análises da Elsevier → ele SABE que as 30 são meta). Roda a CASCATA INTEIRA,
como a Chave 1 roda, e diz:

  • acertou quantos de quantos
  • QUAL CAMADA decidiu cada artigo, e qual camada errou
  • para cada erro: o que o PubMed disse, o que o LLM disse, e o trecho citado

NÃO MOVE NADA. NÃO PUBLICA NADA. Só lê e mede.

Uso:
  python src/prova_lote.py <PASTA> --tipo revisao_sistematica_meta_analise
  python src/prova_lote.py <PASTA> --tipo guideline
  python src/prova_lote.py <PASTA> --tipo artigo_original
"""
import os
import sys
import glob
import csv
import argparse
import collections

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

TIPOS = ("artigo_original", "revisao_sistematica_meta_analise", "revisao_geral",
         "guideline", "minirevisao", "ponto_de_vista", "DESCARTE")

# ponto_de_vista vira minirevisão na cascata (decisão do Dr. Eduardo, 26/07)
EQ = {"ponto_de_vista": "minirevisao"}
norm = lambda t: EQ.get((t or "").strip(), (t or "").strip())


def _camada(via):
    v = (via or "").lower()
    for chave, rot in (("mapa de revista", "A · mapa de revista"),
                       ("rótulo do topo", "B · rótulo do topo"),
                       ("descarte", "C · descarte"),
                       ("título: meta", "D · título=meta"),
                       ("pubmed", "E · PubMed"),
                       ("llm", "G · LLM v4"),
                       ("duplicata", "H · duplicata"),
                       ("rede", "— · rede caiu")):
        if chave in v:
            return rot
    return "? · " + v[:22]


def julgar(pdf):
    """Roda a MESMA cascata da Chave 1 num PDF. Devolve (destino, camada, detalhe)."""
    import classificador_ouro as CO
    from classificador_pubmed import (PDFExtractor, extrair_doi, pubmed_lookup,
                                      europepmc_lookup, map_pubtype, eh_descartavel,
                                      doi_e_deste_artigo, RedeIndisponivel)
    ext = PDFExtractor()
    try:
        texto = ext.extract_text(pdf)
    except Exception:
        texto = ""
    doi = extrair_doi(texto)
    pubtypes, meta = [], {}
    if doi:
        try:
            pubtypes, meta = pubmed_lookup(doi)
            if not meta:
                _, meta = europepmc_lookup(doi)
        except RedeIndisponivel as e:
            return "RETRY", "— · rede caiu", {"erro": str(e)[:60]}

    det = {"doi": doi or "", "pubtypes": "|".join(pubtypes or ""),
           "pubmed_title": (meta.get("title") or "")[:70], "conf": "", "prova": ""}

    if meta and not doi_e_deste_artigo(meta, texto[:20000]):
        det["doi_emprestado"] = "SIM"
        pubtypes, meta = [], {}

    if (d := CO.mapa_revista(doi)):
        return d, "A · mapa de revista", det
    if CO.rotulo_topo(texto)[0]:
        d, rot = CO.rotulo_topo(texto)
        det["rotulo"] = rot
        return ("minirevisao" if d == "ponto_de_vista" else d), "B · rótulo do topo", det
    if eh_descartavel(pubtypes, meta.get("title", ""), texto):
        return "DESCARTE", "C · descarte", det
    if CO._META_TITULO.search((meta.get("title", "") or texto[:250])):
        return "revisao_sistematica_meta_analise", "D · título=meta", det
    if pubtypes and map_pubtype(pubtypes):
        return map_pubtype(pubtypes), "E · PubMed", det
    if (rot_o := CO.rotulo_original(texto)):
        det["rotulo"] = rot_o
        return "artigo_original", "F · rótulo original", det

    tipo, conf, prova = CO.classificar_llm(pdf)
    det["conf"], det["prova"] = conf, prova
    if tipo in ("relato_de_caso", "carta_de_pesquisa"):
        return "DESCARTE", "G · LLM v4", det
    if tipo is None or not tipo:
        return "REVISAO_HUMANA", "G · LLM v4", det
    return ("minirevisao" if tipo == "ponto_de_vista" else tipo), "G · LLM v4", det


def main():
    ap = argparse.ArgumentParser(description="Mede a CASCATA INTEIRA num lote de tipo conhecido")
    ap.add_argument("pasta")
    ap.add_argument("--tipo", required=True, choices=TIPOS,
                    help="o que TODOS os PDFs desta pasta são (a verdade que você conhece)")
    ap.add_argument("--csv", default="", help="grava o detalhe num CSV")
    a = ap.parse_args()

    esperado = norm(a.tipo)
    pdfs = sorted(f for f in glob.glob(os.path.join(os.path.expanduser(a.pasta), "*.pdf"))
                  if not os.path.basename(f).startswith("._"))
    if not pdfs:
        print(f"Nenhum PDF em {a.pasta}"); return 1

    print(f"\n{'='*76}")
    print(f" PROVA DE LOTE · {len(pdfs)} PDF(s) · todos deveriam ser: {esperado}")
    print(f" (a cascata INTEIRA, como a Chave 1 roda — nada é movido)")
    print(f"{'='*76}\n")

    linhas, tot, err = [], collections.Counter(), collections.Counter()
    for i, p in enumerate(pdfs, 1):
        nome = os.path.basename(p)
        try:
            destino, camada, det = julgar(p)
        except Exception as e:
            destino, camada, det = f"ERRO:{type(e).__name__}", "? · exceção", {"erro": str(e)[:60]}
        ok = norm(destino) == esperado
        tot[camada] += 1
        if not ok:
            err[camada] += 1
        print(f"[{i:>3}/{len(pdfs)}] {'✅' if ok else '❌'} {nome[:52]:54} {camada}")
        if not ok:
            print(f"          deu: {destino}")
            if det.get("pubtypes"):
                print(f"          PubMed: {det['pubtypes'][:60]}")
            if det.get("prova"):
                print(f"          LLM ({det.get('conf')}): {det['prova'][:60]}")
            if det.get("rotulo"):
                print(f"          rótulo do topo: {det['rotulo'][:50]}")
            if det.get("doi_emprestado"):
                print(f"          🚫 DOI EMPRESTADO")
        linhas.append({"arquivo": nome, "esperado": esperado, "deu": destino,
                       "acertou": "sim" if ok else "NAO", "camada": camada, **det})

    T, E = sum(tot.values()), sum(err.values())
    print(f"\n{'='*76}")
    print(f" ACERTO: {T-E}/{T}  ({100*(T-E)/T:.1f}%)")
    print(f"{'='*76}\n")
    print(f" {'camada':24}{'julgou':>8}{'errou':>7}{'acerto':>9}")
    print(" " + "─"*47)
    for c in sorted(tot):
        print(f" {c:24}{tot[c]:>8}{err[c]:>7}{100*(tot[c]-err[c])/tot[c]:>8.1f}%")
    if E:
        pior = max(err, key=lambda k: err[k])
        print(f"\n ⚠️  A camada que mais erra: {pior} — {err[pior]} de {tot[pior]}")

    saida = a.csv or os.path.join(os.path.dirname(_HERE), "outputs", "PROVA",
                                  f"lote_{esperado}.csv")
    os.makedirs(os.path.dirname(saida), exist_ok=True)
    with open(saida, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=sorted({k for l in linhas for k in l}))
        w.writeheader(); w.writerows(linhas)
    print(f"\n📋 detalhe: {saida}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
