"""
bateria.py — PROVA DE BURACO ZERO. Roda N artigos e diz UMA coisa: passou 100% ou não passou.

Regra do Dr. Eduardo: "qualquer erro, por menor que seja, é inadmissível".
Portanto esta bateria NÃO reporta progresso ("20 passaram, 8 falharam"). Ela reporta APROVADO
(zero falha) ou REPROVADO — e, se reprovado, o diagnóstico de CADA falha com causa e artigo.

Não publica nada no Supabase. Não move arquivo da fila. É só prova, em pasta isolada.

Uso:
    python bateria.py <pasta_CLASSIFICADOS> [n=5]
Saída:
    relatório na tela + bateria_relatorio.json (para o agente iterar programaticamente)
"""
import os, sys, json, time, traceback, shutil

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
import analisador as A


def _nota_do_staging(saida, base):
    """Lê a nota do CANÔNICO já gerado (retomada): devolve (nota, sobe?) sem re-analisar."""
    import glob, re
    can = glob.glob(os.path.join(saida, base, "*_CANONICO.md"))
    m = re.search(r"nota_aplicabilidade_clinica:\s*(\d+)", open(can[0], encoding="utf-8").read()) if can else None
    nota = int(m.group(1)) if m else 0
    return nota, nota >= 6


def _pdfs(pasta, n):
    achados = []
    for root, dirs, files in os.walk(pasta):
        dirs[:] = [d for d in dirs if d not in ("_PUBLICADOS", "_RECUSADOS")]
        for f in sorted(files):
            if f.lower().endswith(".pdf") and not f.startswith("._"):
                achados.append(os.path.join(root, f))
    return sorted(achados)[:n]


def rodar(classificados, n=5, continuar=False):
    saida = os.path.join(_HERE, "..", "outputs", "_BATERIA")
    saida = os.path.abspath(saida)
    if not continuar:
        shutil.rmtree(saida, ignore_errors=True)      # padrão: prova limpa, parte do zero
    os.makedirs(saida, exist_ok=True)

    pdfs = _pdfs(classificados, n)
    if not pdfs:
        print("Nenhum PDF encontrado."); return 1

    modo = "CONTINUANDO (reaproveita staging pronto)" if continuar else "prova limpa (do zero)"
    print(f"BATERIA · {len(pdfs)} artigo(s) · {modo} · exigência: 100% sem UMA falha\n")
    result = []
    for i, pdf in enumerate(pdfs, 1):
        nome = os.path.basename(pdf)[:52]
        t0 = time.time()
        item = {"arquivo": os.path.basename(pdf), "ok": False}
        try:
            base = os.path.splitext(os.path.basename(pdf))[0]
            pronto = os.path.exists(os.path.join(saida, base, "_OK"))
            if continuar and pronto:                    # RETOMÁVEL: staging já concluído — reusa, não re-gera
                nota, sobe = _nota_do_staging(saida, base)
                ents = None
            else:
                base, nota, mc, ents, sobe = A.processar(pdf, saida)
            # PORTÃO REAL: staging completo NÃO é publicável por si. Quem RECUSA em produção é o
            # Publicador (contrato + preflight de schema). A bateria roda o MESMO gate em dry-run
            # (NÃO sobe pro Supabase) — assim "APROVADO" = "publicável", não só "arquivo existe".
            if sobe:                                        # nota ≥6 → vai pro site; tem que passar no portão
                import publicador as PUB
                pasta = os.path.join(saida, base)
                status, _n, viol = PUB.processar_pasta(pasta, publicar=False)
                if not str(status).startswith(("APROVADO", "PUBLICADO")):
                    raise RuntimeError(f"{status} no Publicador (dry-run): " + " · ".join(map(str, viol[:6])))
            item.update(ok=True, nota=nota, entregaveis=ents,
                        segundos=round(time.time() - t0))
            print(f"  [{i}/{len(pdfs)}] ✅ nota {nota:>2} · {item['segundos']}s · {nome}")
        except Exception as e:
            item.update(erro=f"{type(e).__name__}: {e}",
                        trace=traceback.format_exc()[-900:],
                        segundos=round(time.time() - t0))
            print(f"  [{i}/{len(pdfs)}] ❌ {nome}\n           → {type(e).__name__}: {str(e)[:180]}")
        result.append(item)

    falhas = [r for r in result if not r["ok"]]
    rel = {"total": len(result), "falhas": len(falhas),
           "aprovado": len(falhas) == 0, "itens": result}
    with open(os.path.join(saida, "bateria_relatorio.json"), "w", encoding="utf-8") as f:
        json.dump(rel, f, ensure_ascii=False, indent=2)

    print("\n" + "═" * 62)
    if falhas:
        print(f"REPROVADO · {len(falhas)} de {len(result)} falharam. Buraco zero NÃO atingido.")
        print("\nCAUSAS (agrupadas):")
        causas = {}
        for f in falhas:
            k = f["erro"].split(":")[0]
            causas.setdefault(k, []).append(f["arquivo"][:44])
        for k, v in sorted(causas.items(), key=lambda x: -len(x[1])):
            print(f"  • {k} ({len(v)}x)")
            for a in v[:5]:
                print(f"      - {a}")
        print(f"\nDetalhe completo: {os.path.join(saida, 'bateria_relatorio.json')}")
        print("AÇÃO: corrigir a CAUSA (não o caso) e rodar a bateria de novo até APROVADO.")
        return 1
    print(f"APROVADO · {len(result)}/{len(result)} sem uma única falha. Buraco zero atingido.")
    print("═" * 62)
    return 0


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--continuar"]
    continuar = "--continuar" in sys.argv
    cl = os.path.expanduser(args[0]) if args else ""
    n = int(args[1]) if len(args) > 1 else 5
    if not cl or not os.path.isdir(cl):
        print("uso: python bateria.py <pasta_CLASSIFICADOS> [n=5] [--continuar]"); sys.exit(1)
    sys.exit(rodar(cl, n, continuar=continuar))
