"""
reprocessar_fila.py — drena a FILA_ESPERA.
Re-consulta o PubMed/EuropePMC nos ahead-of-print que estavam esperando indexação. Quando o
artigo já foi catalogado (ganhou tipo autoritativo), classifica com autoridade e move pra análise
(ou pra descarte, se for caso/carta). Os que ainda não indexaram continuam na fila.

Feito pra rodar TODO DIA, sozinho, sem revisão humana. É o que faz o sistema "esperar em vez de
adivinhar" e mesmo assim andar sozinho.

Uso:  python src/reprocessar_fila.py <PASTA_ARTIGOS> [--dry-run]
"""
import os
import shutil
import argparse

from classificador_pubmed import (
    PDFExtractor, extrair_doi, pubmed_lookup, europepmc_lookup,
    map_pubtype, eh_descartavel, _novo_nome, FOLDERS,
    SUB_ANALISE, SUB_DESCARTE, SUB_FILA,
)


def reprocessar(pasta, dry_run=False):
    fila = os.path.join(pasta, SUB_FILA)
    if not os.path.isdir(fila):
        print(f"Sem fila em {fila} — nada a fazer.")
        return
    pdfs = sorted(f for f in os.listdir(fila)
                  if f.lower().endswith(".pdf") and not f.startswith("._"))
    ext = PDFExtractor()
    conv = desc = fica = 0
    print(f"\n{'DRY-RUN — ' if dry_run else ''}Re-check da FILA_ESPERA — {len(pdfs)} aguardando\n")

    for nome in pdfs:
        caminho = os.path.join(fila, nome)
        try:
            texto = ext.extract_text(caminho)
        except Exception:
            texto = ""
        doi = extrair_doi(texto)
        pubtypes, meta = pubmed_lookup(doi) if doi else ([], {})
        fonte = "PubMed"
        if not pubtypes and doi:
            pubtypes, meta = europepmc_lookup(doi)
            fonte = "EuropePMC"
        titulo = meta.get("title", "")

        if eh_descartavel(pubtypes, titulo, texto):
            destino_dir = os.path.join(pasta, SUB_DESCARTE)
            rot = "⛔ descarte"
            desc += 1
        else:
            tipo = map_pubtype(pubtypes) if pubtypes else None
            if tipo:
                destino_dir = os.path.join(pasta, SUB_ANALISE, FOLDERS[tipo])
                rot = f"✅ {tipo}"
                conv += 1
            else:
                print(f"  ⏳ ainda aguarda: {nome[:60]}")
                fica += 1
                continue

        novo = _novo_nome(meta, nome) if meta else nome
        print(f"  {rot}: {nome[:52]}  ({fonte})  → {os.path.relpath(destino_dir, pasta)}/")
        if not dry_run:
            os.makedirs(destino_dir, exist_ok=True)
            shutil.move(caminho, os.path.join(destino_dir, novo))

    print(f"\nResumo: {conv} indexaram e viraram análise, {desc} descartados, {fica} ainda na fila.")
    if dry_run:
        print("(dry-run — nada foi movido.)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Drena a FILA_ESPERA (re-check PubMed dos ahead-of-print)")
    ap.add_argument("pasta", help="Pasta ARTIGOS (a que tem FILA_ESPERA dentro)")
    ap.add_argument("--dry-run", action="store_true", help="Só mostra o que faria")
    a = ap.parse_args()
    reprocessar(os.path.expanduser(a.pasta), dry_run=a.dry_run)
