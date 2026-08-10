"""
custo.py — LÊ O `uso.jsonl` E DIZ PARA ONDE O DINHEIRO FOI.

═══════════════════════════════════════════════════════════════════════════════════════
POR QUE ESTE ARQUIVO EXISTE
═══════════════════════════════════════════════════════════════════════════════════════

Em 09/Ago/2026 o Dr. Eduardo perguntou quanto custaria analisar agosto. Eu respondi
"US$ 0,30 por artigo" — um número que eu tinha CHUTADO semanas antes e chumbado na tela da
Chave 2 (`CENT=$((NP * 30))`). Ele decidiu com base nele. Duas vezes.

Só que o `llm_client.py:41` grava, desde 27/Jul, uma linha por chamada de LLM em
`outputs/uso.jsonl` — tokens de entrada, de saída, de cache, etapa, artigo, stop_reason.
Havia **3.767 chamadas registradas. Ninguém nunca tinha lido o arquivo.**

Quando li, o chute estava 55 % acima do real, e três coisas apareceram sozinhas:

  · o Sonnet custava 2× o terra na extração — e a troca de 04/Ago já tinha cortado o gasto
    pela metade sem ninguém saber (o registro prova: 0 de 456 extrações caíram no fallback)
  · 385 de 845 extrações eram REPETIÇÃO de terra arrasada — 7 artigos extraídos 6 vezes
  · 45 chamadas terminaram em `max_tokens`/`length` — perícia CORTADA no meio, publicada
    sem ninguém ver, porque truncamento não levanta exceção: devolve texto que parece pronto

Nenhuma das três exigia gastar um centavo para descobrir. Exigia LER.

═══════════════════════════════════════════════════════════════════════════════════════
O QUE ELE NÃO FAZ, DE PROPÓSITO
═══════════════════════════════════════════════════════════════════════════════════════

· Não chama modelo, não fala com banco, não escreve nada além da tela. Custo zero, sempre.
· Não afirma dinheiro como se fosse fato. TOKEN é medido; DINHEIRO é derivado da tabela de
  `precos.py`, que nunca foi conferida contra fatura. O aviso vai impresso em toda saída.
· Não cruza a nota do artigo com o custo dele. Tentei em 09/Ago e o cruzamento estava ERRADO:
  359 dos 460 canônicos eram de 25–27/Jul enquanto o custo era de 06–07/Ago — nota de um
  motor, dinheiro de outro. É o mesmo erro dos _RECUSADOS: ler uma versão e supor que é a
  atual. Enquanto não houver como amarrar rodada↔nota com segurança, este programa NÃO
  responde "quanto custa um artigo nota 6". Responde o que ele pode provar.

    python3 src/custo.py                → os últimos 7 dias
    python3 src/custo.py 30             → os últimos 30 dias
    python3 src/custo.py --tudo         → o histórico inteiro
    python3 src/custo.py --por-artigo   → só o número (a Chave 2 lê daqui)
"""
import os
import sys
import json
import datetime
import collections

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
import precos as P

USO = os.path.join(_HERE, "..", "outputs", "uso.jsonl")

# As etapas que rodam DEPOIS da régua (só para nota ≥6, ou diretriz sempre).
# Serve para responder "quanto do gasto está do lado certo da porta?"
POS_REGUA = {"redator", "redator_original", "redator_meta", "redator_guideline", "redator_revisao",
             "acri", "gancho_abertura", "script_audio", "script_audio_diretriz", "visual"}


def ler(dias=7, tudo=False):
    """Lê o uso.jsonl. Best-effort: linha corrompida é pulada, não derruba o relatório."""
    if not os.path.exists(USO):
        return []
    corte = ""
    if not tudo:
        corte = (datetime.datetime.now() - datetime.timedelta(days=dias)).strftime("%Y-%m-%d")
    out = []
    for l in open(USO, encoding="utf-8", errors="ignore"):
        l = l.strip()
        if not l:
            continue
        try:
            d = json.loads(l)
        except Exception:
            continue
        if corte and str(d.get("ts", ""))[:10] < corte:
            continue
        out.append(d)
    return out


def por_artigo(linhas):
    """US$ por artigo, só dos artigos cujo nome foi registrado.

    ⚠️ Um artigo REANALISADO aparece com o custo somado de todas as suas rodadas — que é o
    que o Dr. Eduardo de fato pagou. A mediana é a estimativa honesta para "vou rodar N
    artigos": ela absorve a cauda das diretrizes de 200 páginas sem ser puxada por ela.
    """
    d = collections.defaultdict(float)
    for x in linhas:
        a = x.get("artigo")
        if a and a != "?":
            d[a] += P.custo_da_linha(x)
    return sorted(d.values())


def mediana(v):
    return v[len(v) // 2] if v else 0.0


def relatorio(dias=7, tudo=False):
    L = ler(dias, tudo)
    titulo = "histórico inteiro" if tudo else f"últimos {dias} dias"
    print("═" * 82)
    print(f" CUSTO · o que o registro de uso mostra — {titulo}")
    print("═" * 82)
    if not L:
        print()
        print("   Nenhuma chamada registrada no período.")
        print(f"   O arquivo é {os.path.abspath(USO)}")
        print("   Se você rodou a Chave 2 hoje e isto está vazio, o problema é o REGISTRO.")
        return 1
    print(f" {len(L):,} chamadas · {L[0]['ts'][:10]} → {L[-1]['ts'][:10]}")
    print(f" {P.aviso()}")

    # ── 1. POR ETAPA — onde o dinheiro está ──
    pe = collections.defaultdict(lambda: [0.0, 0])
    for x in L:
        e = x.get("etapa") or "?"
        pe[e][0] += P.custo_da_linha(x)
        pe[e][1] += 1
    tot = sum(v[0] for v in pe.values())
    print()
    print("   ── ONDE O DINHEIRO ESTÁ ──")
    print(f"   {'etapa':24s} {'chamadas':>9s} {'US$':>9s} {'%':>6s}")
    for e, (v, n) in sorted(pe.items(), key=lambda x: -x[1][0]):
        print(f"   {e[:24]:24s} {n:>9,} {v:>9.2f} {100 * v / max(tot, 1):>5.1f}%")
    print(f"   {'TOTAL':24s} {len(L):>9,} {tot:>9.2f}")
    pos = sum(v for e, (v, _) in pe.items() if e in POS_REGUA)
    print(f"   ({100 * pos / max(tot, 1):.0f}% é DEPOIS da régua — só artigo aprovado paga)")

    # ── 2. POR MODELO — e o cache ──
    print()
    print("   ── POR MODELO ──")
    pm = collections.defaultdict(lambda: {"n": 0, "i": 0, "o": 0, "c": 0, "v": 0.0})
    for x in L:
        m = pm[x.get("modelo") or "?"]
        m["n"] += 1
        m["i"] += x.get("input") or 0
        m["o"] += x.get("output") or 0
        m["c"] += (x.get("cache_read") or 0)
        m["v"] += P.custo_da_linha(x)
    print(f"   {'modelo':26s} {'n':>7s} {'input':>12s} {'cache':>7s} {'US$':>9s}")
    for m, v in sorted(pm.items(), key=lambda x: -x[1]["v"]):
        pc = 100 * v["c"] / max(v["i"], 1)
        alerta = "  ← sem cache" if v["i"] > 1_000_000 and pc < 1 else ""
        print(f"   {str(m)[:26]:26s} {v['n']:>7,} {v['i']:>12,} {pc:>6.1f}% {v['v']:>9.2f}{alerta}")

    # ── 3. POR ARTIGO — o número que a Chave 2 precisa ──
    va = por_artigo(L)
    if va:
        print()
        print(f"   ── POR ARTIGO ({len(va)} artigos com nome registrado) ──")
        print(f"      mediana US$ {mediana(va):.3f}   ·   média US$ {sum(va) / len(va):.3f}"
              f"   ·   p90 US$ {va[int(.9 * len(va))]:.3f}")
        print(f"      com Batch API (−50%): US$ {mediana(va) * P.BATCH:.3f}")

    # ── 4. REANÁLISE — o dinheiro que a terra arrasada custa ──
    ex = [x for x in L if x.get("etapa") == "extracao" and x.get("artigo") not in (None, "?")]
    if ex:
        c = collections.Counter(x["artigo"] for x in ex)
        rep = len(ex) - len(c)
        print()
        print("   ── REANÁLISE (terra arrasada) ──")
        print(f"      {len(c)} artigos → {len(ex)} extrações = {len(ex) / len(c):.2f}× por artigo")
        if rep:
            unit = sum(P.custo_da_linha(x) for x in ex) / len(ex)
            print(f"      {rep} extrações foram repetição ≈ US$ {rep * unit:.2f}")
            print("      (não é desperdício: prompt mudou, a análise velha não valia mais.")
            print("       Zera sozinho quando o motor parar de mudar.)")

    # ── 5. TRUNCAMENTO — o defeito que não levanta exceção ──
    tr = [x for x in L if x.get("stop_reason") in ("length", "max_tokens", "FinishReason.MAX_TOKENS")]
    print()
    if tr:
        print(f"   ⚠️  {len(tr)} chamada(s) TRUNCARAM por limite de tokens")
        print("       Truncamento não dá erro: devolve texto que PARECE pronto e está cortado.")
        for e, n in collections.Counter(x.get("etapa") for x in tr).most_common(5):
            print(f"         {str(e):24s} {n}")
    else:
        print("   ✓ nenhuma chamada truncada no período.")

    print()
    print("═" * 82)
    print("   TOKEN é medido pelo provedor. DINHEIRO sai de src/precos.py — corrija a tabela")
    print("   com a sua fatura e rode isto de novo: o histórico se recalcula sem gastar nada.")
    return 0


def main():
    args = sys.argv[1:]
    if "--por-artigo" in args:
        # Saída CRUA, para a Chave 2 ler. Sem enfeite, sem aviso — só o número.
        #
        # ⚠️ JANELA CURTA DE PROPÓSITO. A cadeia de modelos muda: em 04/Ago o terra virou
        # primário da extração e o custo caiu pela metade no mesmo dia. Uma janela de 14 dias
        # devolve US$ 0,314 — a média entre duas máquinas diferentes, que não descreve nenhuma
        # das duas. A de 7 dias devolve US$ 0,199, que é a máquina de HOJE. Foi somando épocas
        # como se fossem uma que eu errei a projeção de agosto em 80 %.
        # Se a semana teve pouco movimento, alarga — melhor número velho que número de 3 artigos.
        for dias_janela in (7, 30, 90):
            va = por_artigo(ler(dias=dias_janela))
            if len(va) >= 30:
                print(f"{mediana(va):.4f}")
                return 0
        print(f"{mediana(va):.4f}" if va else "")
        return 0
    dias, tudo = 7, "--tudo" in args
    for a in args:
        if a.isdigit():
            dias = int(a)
    return relatorio(dias, tudo)


if __name__ == "__main__":
    sys.exit(main())
