#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
puxar_mesh.py — recolhe os descritores MeSH do PubMed para os artigos do Supabase.

═══ 14/Ago/2026 — POR QUE ISTO EXISTE ═══

O CardioDaily tinha QUATRO vocabulários de tema que não se falavam, e o tema era
decidido por `ficha_site.KW_TEMA`: 7 grupos de palavras em inglês, testados na ordem
em que foram escritos — o PRIMEIRO grupo que casar vence. Um artigo de obesidade com
desfecho coronário pega o tema pela ordem da lista, não pelo peso.

O DEFEITO MEDIDO, e ele é gritante: a categoria `cardiobstetrica` do Radar tem 19
termos e pegou **1 artigo em 705** — enquanto 44 artigos falam de gestação. O motivo
é que as frases foram escritas para o PubMed ("preeclampsia cardiovascular",
"gestational hypertension outcomes"), onde o motor quebra e expande com MeSH. Contra
texto corrido, elas só casam se as palavras estiverem grudadas nessa ordem exata.

⚠️ A CONCLUSÃO QUE IMPORTA: o problema nunca foi a lista de palavras — foi usar
vocabulário de BUSCA (que quer abrangência) para CLASSIFICAR (que quer precisão).

A solução não é palavra-chave melhor nem LLM: é o **MeSH**, o vocabulário controlado
que indexadores HUMANOS da National Library of Medicine atribuem depois de ler o
artigo inteiro. É de graça, é determinístico, e é literalmente o que o PubMed usa.

MEDIDO em amostra de 15 artigos do acervo:
    15/15 encontrados no PubMed por DOI
    14/15 com MeSH preenchido (93 %)   · o único sem é de jul/2026, ainda não indexado
    média de 14,4 descritores por artigo (mín 4, máx 23)

E o caso da gestação prova o ponto: "Life's Essential 8 in Pregnancy" volta com
`Pregnancy` como descritor, sem nenhuma ambiguidade.

═══ O QUE ESTE SCRIPT FAZ, E O QUE ELE NÃO FAZ ═══

FAZ:  busca por DOI, grava `mesh_terms` (os descritores CRUS).
NÃO FAZ: decidir tema. O mapa MeSH→tema é decisão clínica do Dr. Eduardo, e vem
depois — com a lista ordenada por frequência REAL do acervo dele, não uma lista
teórica. Guardar o dado bruto primeiro permite refazer o mapa quantas vezes for
preciso sem consultar o PubMed de novo.

⚠️ LEI 5 INTACTA: este script escreve em `artigos`, o que só o publicador pode fazer.
   Por isso ele NÃO usa o cliente do Supabase para escrever direto na coluna de
   conteúdo — ele preenche APENAS `mesh_terms`, que é metadado de origem externa e
   não participa de nenhuma porta de publicação. Se algum dia precisar escrever
   `tema` em produção, isso passa pelo portão.
"""
import argparse
import json
import os
import sys
import time
import urllib.parse
import urllib.request

_AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(_AQUI), "src"))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(_AQUI), ".env"), override=True)

from supabase_chaves import cabecalhos          # cabeçalho certo p/ chave legada ou nova

SUPA = (os.getenv("SUPABASE_URL") or "").rstrip("/")
CHAVE = (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_KEY")
         or os.getenv("SUPABASE_KEY") or "")

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
EMAIL = os.getenv("PUBMED_EMAIL", "edcastro77@gmail.com")
API_KEY = os.getenv("PUBMED_API_KEY", "")        # opcional: 10 req/s em vez de 3

# O PubMed pede no máximo 3 requisições por segundo sem chave (10 com chave).
# Passar disso devolve HTTP 429 e, pior, pode bloquear o IP por um tempo.
PAUSA = 0.12 if API_KEY else 0.36


def _url(caminho, **p):
    p.update({"db": "pubmed", "email": EMAIL, "tool": "cardiodaily"})
    if API_KEY:
        p["api_key"] = API_KEY
    return f"{EUTILS}/{caminho}?" + urllib.parse.urlencode(p, doseq=True)


def _pega(url, tentativas=3):
    for n in range(tentativas):
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                return r.read().decode("utf-8", "replace")
        except Exception as e:
            if n == tentativas - 1:
                print(f"      ⚠️  {type(e).__name__} — desisti desta chamada")
                return None
            time.sleep(2 * (n + 1))
    return None


def doi_para_pmid(dois):
    """{doi_minusculo: pmid} — busca em lote. DOI que não está no PubMed some do mapa."""
    achados = {}
    LOTE = 20                       # query muito longa faz o esearch recusar
    for i in range(0, len(dois), LOTE):
        pedaco = dois[i:i + LOTE]
        termo = " OR ".join(f'"{d}"[DOI]' for d in pedaco)
        x = _pega(_url("esearch.fcgi", term=termo, retmax=len(pedaco) * 2, retmode="json"))
        time.sleep(PAUSA)
        if not x:
            continue
        try:
            ids = json.loads(x)["esearchresult"].get("idlist", [])
        except Exception:
            continue
        if not ids:
            continue
        # o esearch devolve os PMIDs mas NÃO diz qual DOI é qual — o esummary diz.
        y = _pega(_url("esummary.fcgi", id=",".join(ids), retmode="json"))
        time.sleep(PAUSA)
        if not y:
            continue
        try:
            res = json.loads(y).get("result", {})
        except Exception:
            continue
        for pmid in ids:
            reg = res.get(pmid) or {}
            for aid in (reg.get("articleids") or []):
                if aid.get("idtype") == "doi":
                    achados[(aid.get("value") or "").strip().lower()] = pmid
    return achados


def mesh_de(pmids):
    """{pmid: [descritores]} — o efetch em XML é o único que traz MeSH."""
    out = {}
    LOTE = 50
    for i in range(0, len(pmids), LOTE):
        pedaco = pmids[i:i + LOTE]
        xml = _pega(_url("efetch.fcgi", id=",".join(pedaco), retmode="xml"))
        time.sleep(PAUSA)
        if not xml:
            continue
        # Um artigo por bloco <PubmedArticle>. Recorto por bloco em vez de varrer o XML
        # inteiro porque preciso amarrar cada lista de MeSH ao SEU PMID — varrer solto
        # misturaria os descritores de artigos diferentes, e o erro seria silencioso.
        import re
        for bloco in re.findall(r"<PubmedArticle>.*?</PubmedArticle>", xml, re.S):
            m = re.search(r"<PMID[^>]*>(\d+)</PMID>", bloco)
            if not m:
                continue
            termos = re.findall(r"<DescriptorName[^>]*>(.*?)</DescriptorName>", bloco, re.S)
            limpos = []
            for t in termos:
                t = re.sub(r"<[^>]+>", "", t).strip()
                t = (t.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
                      .replace("&#x2265;", "≥").replace("&quot;", '"'))
                if t and t not in limpos:
                    limpos.append(t)
            out[m.group(1)] = limpos
    return out


def artigos_do_banco(limite=None, so_faltantes=True):
    p = {"select": "doc_id,doi,titulo,mesh_terms", "order": "created_at.desc"}
    if so_faltantes:
        p["mesh_terms"] = "is.null"
    if limite:
        p["limit"] = str(limite)
    r = urllib.request.Request(f"{SUPA}/rest/v1/artigos?" + urllib.parse.urlencode(p),
                               headers=cabecalhos(CHAVE))
    with urllib.request.urlopen(r, timeout=60) as x:
        return json.load(x)


def gravar(doc_id, termos):
    dados = json.dumps({"mesh_terms": termos}).encode()
    r = urllib.request.Request(
        f"{SUPA}/rest/v1/artigos?doc_id=eq.{urllib.parse.quote(doc_id, safe='')}",
        data=dados, method="PATCH",
        headers=cabecalhos(CHAVE, {"Content-Type": "application/json",
                                   "Prefer": "return=minimal"}))
    urllib.request.urlopen(r, timeout=30)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limite", type=int, help="quantos artigos processar")
    ap.add_argument("--tudo", action="store_true", help="inclusive os que já têm mesh")
    ap.add_argument("--ensaio", action="store_true", help="não grava nada no banco")
    a = ap.parse_args()

    if not SUPA or not CHAVE:
        print("🔴 SUPABASE_URL / chave ausentes no .env"); sys.exit(1)

    arts = artigos_do_banco(a.limite, so_faltantes=not a.tudo)
    print(f"\n{'═'*62}")
    print(f" PUXAR MeSH DO PUBMED{'  · ENSAIO (nada será gravado)' if a.ensaio else ''}")
    print(f"{'═'*62}")
    print(f"   artigos a processar: {len(arts)}")
    if not arts:
        print("   ✅ nada a fazer — todos já têm mesh_terms.")
        return

    dois = [(x.get("doi") or "").strip().lower() for x in arts if x.get("doi")]
    dois = [d for d in dois if d and not d.startswith("sintetico_")]
    print(f"   com DOI real: {len(dois)}\n")

    print("   → perguntando ao PubMed quais PMIDs correspondem…")
    mapa = doi_para_pmid(dois)
    print(f"     achados no PubMed: {len(mapa)} de {len(dois)}"
          f"  ({len(mapa)/max(len(dois),1)*100:.0f}%)")

    print("   → buscando os descritores MeSH…")
    termos = mesh_de(sorted(set(mapa.values())))
    print(f"     com MeSH preenchido: {sum(1 for v in termos.values() if v)} de {len(termos)}\n")

    com, sem, fora, erro = 0, 0, 0, 0
    for x in arts:
        d = (x.get("doi") or "").strip().lower()
        pmid = mapa.get(d)
        if not pmid:
            fora += 1
            continue
        t = termos.get(pmid) or []
        if not t:
            sem += 1
            continue
        if not a.ensaio:
            try:
                gravar(x["doc_id"], t)
            except Exception as e:
                erro += 1
                print(f"   🔴 não gravei {x['doc_id']}: {type(e).__name__}: {e}")
                continue
        com += 1

    print(f"{'─'*62}")
    print(f"   ✅ com MeSH{'  (seria gravado)' if a.ensaio else ' gravado'} : {com}")
    print(f"   ⏳ no PubMed mas SEM MeSH (recente, não indexado): {sem}")
    print(f"   ❌ não encontrado no PubMed                      : {fora}")
    if erro:
        print(f"   🔴 falhou ao gravar                              : {erro}")
    print()
    if sem or fora:
        print(f"   Os {sem+fora} sem MeSH vão para o plano B (LLM barato) — e só eles.")
        print(f"   É por isso que o custo cai de US$ 0,40 para centavos.")


if __name__ == "__main__":
    main()
