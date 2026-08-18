#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
marcar_temas.py — põe TEMA em todo artigo. MeSH primeiro; LLM só no que sobrar.

═══ 18/Ago/2026 — A ESTEIRA DO TEMA ═══

    1. o artigo tem `mesh_terms`?  →  motor determinístico (custo ZERO)
    2. não tem?                    →  LLM barato (cadeia CLASSIFICACAO, ~US$0,0006/artigo)
    3. nem um nem outro decidiu    →  fica SEM TEMA e aparece na revisão humana

Decisão do Dr. Eduardo: *"llm e já pode implementar que quando não tiver indexação por
mesh — que deve automaticamente rodar a llm"*. O plano B deixa de ser tarefa manual.

═══ POR QUE O MeSH VEM PRIMEIRO, SEMPRE ═══
Ele é atribuído por indexador HUMANO da NLM lendo o artigo inteiro. O LLM lê duas páginas
e chuta bem. Entre os dois, o humano ganha — e ainda é de graça.

⚠️ E POR QUE ISTO É RE-EXECUTÁVEL SEM CUSTO
A NLM indexa os artigos novos em algumas semanas. Rodando este script de novo:
  · quem já tinha MeSH não é tocado;
  · quem tinha tema do LLM e AGORA ganhou MeSH é **promovido** — o descritor humano
    substitui o palpite, de graça.
É para isso que `tema_origem` existe. Sem ela, o palpite viraria permanente em silêncio.

USO
    python3 scripts/marcar_temas.py --ensaio          # não grava nada, mostra o que faria
    python3 scripts/marcar_temas.py --limite 20       # começa pequeno
    python3 scripts/marcar_temas.py                   # tudo que falta
    python3 scripts/marcar_temas.py --promover        # re-avalia os que estão com 'llm'
"""
import argparse
import collections
import json
import os
import sys
import urllib.parse
import urllib.request

_AQUI = os.path.dirname(os.path.abspath(__file__))
_RAIZ = os.path.dirname(_AQUI)
sys.path.insert(0, os.path.join(_RAIZ, "src"))

from dotenv import load_dotenv
load_dotenv(os.path.join(_RAIZ, ".env"), override=True)

from supabase_chaves import cabecalhos
import temas as T
import tema_mesh as TM

SUPA = (os.getenv("SUPABASE_URL") or "").rstrip("/")
CHAVE = (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_KEY")
         or os.getenv("SUPABASE_KEY") or "")
MAPA = os.path.join(_RAIZ, "src", "dados", "mesh_para_tema.json")


def _get(p):
    r = urllib.request.Request(f"{SUPA}/rest/v1/artigos?" + urllib.parse.urlencode(p),
                               headers=cabecalhos(CHAVE))
    with urllib.request.urlopen(r, timeout=90) as x:
        return json.load(x)


def gravar(doc_id, tema, sec, origem):
    corpo = json.dumps({"tema": tema, "tema_secundario": sec,
                        "tema_origem": origem}).encode()
    r = urllib.request.Request(
        f"{SUPA}/rest/v1/artigos?doc_id=eq.{urllib.parse.quote(doc_id, safe='')}",
        data=corpo, method="PATCH",
        headers=cabecalhos(CHAVE, {"Content-Type": "application/json",
                                   "Prefer": "return=minimal"}))
    urllib.request.urlopen(r, timeout=30)


def texto_do_pdf(titulo):
    """As 2 primeiras páginas do PDF, se acharmos o arquivo. É o que alimenta o LLM."""
    import glob
    import re
    try:
        import pypdfium2 as pdfium
    except ImportError:
        return ""
    # o nome do arquivo vem do título; casamento frouxo pelas 4 primeiras palavras
    chave = "_".join(re.findall(r"[A-Za-z]{4,}", titulo or "")[:4])
    if not chave:
        return ""
    for padrao in (f"ARTIGOS/CLASSIFICADOS/**/*{chave[:24]}*.pdf",
                   f"outputs/**/*{chave[:24]}*.pdf"):
        for p in glob.glob(os.path.join(_RAIZ, padrao), recursive=True)[:1]:
            try:
                d = pdfium.PdfDocument(p)
                return "".join(d[i].get_textpage().get_text_range()
                               for i in range(min(2, len(d))))
            except Exception:
                pass
    return ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limite", type=int)
    ap.add_argument("--ensaio", action="store_true", help="não grava nada")
    ap.add_argument("--promover", action="store_true",
                    help="re-avalia os que estão com tema do LLM e agora têm MeSH")
    a = ap.parse_args()

    if not SUPA or not CHAVE:
        print("🔴 SUPABASE_URL / chave ausentes no .env")
        sys.exit(1)

    p = {"select": "doc_id,titulo,revista,mesh_terms,tema,tema_origem",
         "order": "created_at.desc"}
    if a.promover:
        p["tema_origem"] = "eq.llm"
        p["mesh_terms"] = "not.is.null"
    else:
        p["tema"] = "is.null"
    if a.limite:
        p["limit"] = str(a.limite)
    alvo = _get(p)

    print(f"\n{'═'*64}")
    print(f" MARCAR TEMAS{'  · ENSAIO (nada será gravado)' if a.ensaio else ''}")
    print(f"{'═'*64}")
    if a.promover:
        print(f"   artigos com tema do LLM que AGORA têm MeSH: {len(alvo)}")
    else:
        print(f"   artigos sem tema: {len(alvo)}")
    if not alvo:
        print("   ✅ nada a fazer.")
        return

    # a frequência para o peso de especificidade vem do acervo INTEIRO, não da amostra
    todos = _get({"select": "mesh_terms", "limit": "2000"})
    freq = collections.Counter(t for x in todos for t in (x.get("mesh_terms") or []))
    mapa = json.load(open(MAPA, encoding="utf-8"))

    por_mesh = [x for x in alvo if x.get("mesh_terms")]
    sem_mesh = [x for x in alvo if not x.get("mesh_terms")]
    print(f"   ├ com MeSH (grátis)     : {len(por_mesh)}")
    print(f"   └ sem MeSH (vai p/ LLM) : {len(sem_mesh)}\n")

    feitos = collections.Counter()
    erros = 0

    # ── 1 · MeSH ──
    for x in por_mesh:
        pri, sec, mg, det = TM.decidir(x.get("mesh_terms"), mapa, freq)
        if not pri or pri == T.SEM_TEMA:
            feitos["mesh não decidiu"] += 1
            continue
        if not a.ensaio:
            try:
                gravar(x["doc_id"], pri, sec, "mesh")
            except Exception as e:
                erros += 1
                print(f"   🔴 {x['doc_id']}: {type(e).__name__}: {e}")
                continue
        feitos["mesh"] += 1

    # ── 2 · LLM, só no que sobrou ──
    if sem_mesh:
        import tema_llm
        import precos
        gasto = 0.0
        for i, x in enumerate(sem_mesh, 1):
            txt = texto_do_pdf(x.get("titulo"))
            pri, sec, porque = tema_llm.classificar(
                x.get("titulo"), txt, x.get("revista", ""))
            if not pri or pri == T.SEM_TEMA:
                feitos["llm não decidiu"] += 1
                continue
            if not a.ensaio:
                try:
                    gravar(x["doc_id"], pri, sec, "llm")
                except Exception as e:
                    erros += 1
                    continue
            feitos["llm"] += 1
            if i <= 6 or i % 40 == 0:
                marca = f" [2º {sec}]" if sec else ""
                print(f"   {i:3}/{len(sem_mesh)} {pri}{marca}  ← {(x.get('titulo') or '')[:44]}")

    print(f"\n{'─'*64}")
    print(f"   tema pelo MeSH (grátis) : {feitos['mesh']}")
    print(f"   tema pelo LLM           : {feitos['llm']}")
    print(f"   sem decisão (revisão)   : {feitos['mesh não decidiu'] + feitos['llm não decidiu']}")
    if erros:
        print(f"   🔴 falhas ao gravar     : {erros}")
    if feitos["llm"]:
        import precos
        c = precos.custo("gpt-5.6-luna", entrada=2700, saida=120) * feitos["llm"]
        print(f"\n   custo estimado do LLM   : US$ {c:.3f}   ({precos.aviso()[:40]}…)")


if __name__ == "__main__":
    main()
