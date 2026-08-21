"""
backfill_tema.py — os artigos que já estão no Supabase SEM tema.

═══ POR QUE ELES EXISTEM ═══
Em 17/Ago construí a máquina de temas e rodei UMA vez pelo `marcar_temas.py` — um script que
dá PATCH direto em `artigos`, ou seja, um SEGUNDO PORTÃO (LEI 5, que o Dr. Eduardo já tinha
enunciado para mim: *"não pode ter dois portões"*). Enquanto ele rodava, o banco parecia certo.
Parou, o `publicador.py` continuou publicando sem saber que a coluna existia, e o buraco cresceu:

    até 17/Ago .... 21 sem tema em 507
    18/Ago ........ 18 em 26
    19/Ago ........ 78 em 83

A torneira foi fechada (o tema agora é decidido em `ficha_site._decidir_tema`, dentro do portão).
Este programa enxuga o chão — **e não escreve no banco**: ele lista o que falta e prepara a fila
para o portão, exatamente como a LEI 5 manda.

⚠️ POR QUE NÃO DAR UM UPDATE DIRETO, JÁ QUE SERIA "SÓ UMA COLUNA"
Foi esse raciocínio que criou o problema. Uma coluna hoje, duas amanhã, e volta a existir um
caminho de escrita que ninguém audita. O portão custa uma re-análise; o buraco custa confiança.

Uso:
    python3 scripts/backfill_tema.py             # ENSAIO: mostra quem falta e onde está o pacote
    python3 scripts/backfill_tema.py --preparar  # devolve os PDFs à fila para a Chave 2 refazer
"""
import argparse
import json
import os
import shutil
import sys
import urllib.parse
import urllib.request

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "src"))
from dotenv import load_dotenv
load_dotenv(os.path.join(RAIZ, ".env"))

STAGING = os.path.join(RAIZ, "outputs", "STAGING")
CLASSIFICADOS = os.path.join(RAIZ, "ARTIGOS", "CLASSIFICADOS")
PASTA_DO_TIPO = {"original": "ARTIGOS_ORIGINAIS", "meta": "META_ANALISES",
                 "diretriz": "GUIDELINES", "revisao_narrativa": "REVISOES"}


def sem_tema():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    h = {"apikey": key, "Authorization": f"Bearer {key}"}
    q = urllib.parse.urlencode({
        "select": "doc_id,titulo,tipo_documento,nota_aplicabilidade,created_at",
        "tema": "is.null", "limit": "2000"})
    return json.load(urllib.request.urlopen(
        urllib.request.Request(f"{url}/rest/v1/artigos?{q}", headers=h), timeout=60))


def pacote_de(titulo):
    """A pasta do STAGING deste artigo, se ainda existir (o nome vem do PDF)."""
    import glob
    import unicodedata
    alvo = unicodedata.normalize("NFKD", (titulo or "").lower())
    alvo = alvo.encode("ascii", "ignore").decode()[:38]
    for p in glob.glob(os.path.join(STAGING, "*")):
        if not os.path.isdir(p):
            continue
        c = glob.glob(os.path.join(p, "*_CANONICO.md"))
        if not c:
            continue
        t = open(c[0], encoding="utf-8").read()[:4000].lower()
        t = unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode()
        if alvo and alvo[:38] in t:
            return p
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preparar", action="store_true",
                    help="devolve os PDFs à fila (a Chave 2 refaz e o portão preenche o tema)")
    a = ap.parse_args()

    faltam = sem_tema()
    print("═" * 74)
    print(f"ARTIGOS NO SUPABASE SEM TEMA: {len(faltam)}")
    print("═" * 74)
    if not faltam:
        print("Nenhum. A torneira está fechada e o chão está seco.")
        return 0

    por_dia = {}
    for r in faltam:
        por_dia[(r.get("created_at") or "?")[:10]] = por_dia.get((r.get("created_at") or "?")[:10], 0) + 1
    for dia in sorted(por_dia):
        print(f"   {dia}   {por_dia[dia]:>3}")

    achados, orfaos = [], []
    for r in faltam:
        p = pacote_de(r.get("titulo"))
        (achados if p else orfaos).append((r, p))

    print(f"\n  com pacote no STAGING : {len(achados)}  → a Chave 2 refaz e o portão preenche")
    print(f"  SEM pacote            : {len(orfaos)}  → precisam do PDF de volta na fila")

    if orfaos:
        print("\n  ── sem pacote (o staging foi arquivado) ──")
        for r, _ in orfaos[:10]:
            print(f"     [{r.get('tipo_documento')}] {(r.get('titulo') or '')[:58]}")
        if len(orfaos) > 10:
            print(f"     … e mais {len(orfaos) - 10}")

    if not a.preparar:
        print("\n" + "═" * 74)
        print("ENSAIO — nada foi tocado. Para preparar a fila:")
        print("   python3 scripts/backfill_tema.py --preparar")
        print("═" * 74)
        return 0

    # ── preparar = reabrir o pacote E devolver o PDF à fila ──
    #
    # ⚠️ A PRIMEIRA VERSÃO SÓ APAGAVA O `_OK`, E ISSO NÃO BASTA. Ele rodou, viu "96 pacotes
    # reabertos", abriu a Chave 2 e encontrou **fila vazia** — de novo. A Chave 2 monta a fila
    # pelos PDFs em `ARTIGOS/CLASSIFICADOS/<tipo>/`, não pelo STAGING. E estes 96 já tinham sido
    # publicados: o PDF estava em `_PUBLICADOS`, fora da fila. Medido: 96 de 96.
    # Reabrir o staging sem devolver o PDF é abrir a porta de uma sala vazia.
    #
    # NÃO apaga os FATOS: eles não dependem do tema, e são a parte cara (regra de 19/Ago).
    n = movidos = 0
    for r, p in achados:
        f = os.path.join(p, "_OK")
        if os.path.exists(f):
            os.remove(f) if os.path.isfile(f) else shutil.rmtree(f, ignore_errors=True)
            n += 1
        # ── LEI 12: conferir ANTES de mover ──
        origem = os.path.join(CLASSIFICADOS, "_PUBLICADOS", os.path.basename(p) + ".pdf")
        destino_dir = os.path.join(CLASSIFICADOS,
                                   PASTA_DO_TIPO.get(r.get("tipo_documento"), "ARTIGOS_ORIGINAIS"))
        destino = os.path.join(destino_dir, os.path.basename(origem))
        if not os.path.exists(origem):
            continue                                  # já está na fila, ou foi arquivado
        if os.path.exists(destino):
            continue                                  # não sobrescreve nada
        if os.path.getsize(origem) < 1024:
            print(f"   ⚠️  PDF suspeito ({os.path.getsize(origem)} bytes), não movido: "
                  f"{os.path.basename(origem)}")
            continue
        os.makedirs(destino_dir, exist_ok=True)
        shutil.move(origem, destino)
        movidos += 1

    print(f"\n✔ {n} pacote(s) reabertos (o `_OK` saiu; os FATOS ficaram).")
    print(f"✔ {movidos} PDF(s) devolvidos de _PUBLICADOS para a fila.")
    print("  Rode a CHAVE 2: ela refaz a ficha, o portão preenche o tema, e o upsert atualiza")
    print("  a linha que já existe (idempotente, LEI 5 — nenhuma linha duplicada).")
    if orfaos:
        print(f"\n⚠️  Os {len(orfaos)} sem pacote continuam sem tema. Para eles é preciso pôr o PDF")
        print("   de volta em ARTIGOS/CLASSIFICADOS/<tipo>/ — e isso é decisão sua, não minha.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
