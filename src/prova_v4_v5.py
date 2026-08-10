"""
prova_v4_v5.py — O v4 CONTRA O v5, NOS 111 ARTIGOS DO GABARITO DO DR. EDUARDO.

═══════════════════════════════════════════════════════════════════════════════════════
O QUE ESTA PROVA RESPONDE — E O QUE ELA NÃO RESPONDE
═══════════════════════════════════════════════════════════════════════════════════════

RESPONDE:
  1. ACURÁCIA — quantos cada versão acerta contra o gabarito que o Dr. Eduardo conferiu à mão.
  2. ONDE ERRA — o par (certo → dito), para saber se o erro é grave (meta virando original,
     que troca o motor) ou leve (revisão narrativa virando minirrevisão).
  3. REPETIBILIDADE — a mesma pergunta, duas vezes. Em 10/Ago o MESMO artigo
     ("Alcohol-Related Liver Disease: A Review") saiu `revisao_geral` numa rodada e
     `revisao_sistematica_meta_analise` na seguinte, as DUAS com confiança alta. Acurácia sem
     repetibilidade é sorte medida uma vez.
  4. POR SINAL (só v5) — quando o v5 erra, QUAL sinal falhou. No v4 isso é impossível: ele
     devolve um veredito e ninguém sabe de onde veio.

NÃO RESPONDE:
  · se o gabarito está certo. Ele é do Dr. Eduardo e vale como verdade — mas em 31/Jul, dos 3
    "erros" do v2, DOIS eram do gabarito (os artigos DECLARAVAM PRISMA). Divergência não é
    automaticamente erro do modelo.
  · como cada versão se comporta em artigo que não está no gabarito.

═══════════════════════════════════════════════════════════════════════════════════════
COMO É JUSTO
═══════════════════════════════════════════════════════════════════════════════════════
· O MESMO texto (páginas 1–3) vai para as duas versões. Extraído uma vez, reusado.
· O MESMO modelo. A prova compara PROMPT, não modelo — deixar cadeia de fallback responder
  falsearia o experimento, então não há fallback: erro de rede re-tenta o MESMO modelo.
· Temperatura 0 onde o modelo aceita.
· Nada é escrito fora do CSV desta prova. Não move arquivo, não fala com o Supabase, e o plano
  de voo fica SILENCIADO (`voo.silenciar`) — em 10/Ago descobri que as minhas próprias
  ferramentas de simulação estavam sujando o registro de produção.

    python3 src/prova_v4_v5.py --dry-run     # o que faria, quanto custa, sem gastar
    python3 src/prova_v4_v5.py               # roda (retoma de onde parou)
    python3 src/prova_v4_v5.py --placar      # só recalcula o placar do CSV existente
"""
import os
import sys
import csv
import time
import glob

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

import voo as _VOO
_VOO.silenciar(True)                    # simulação NUNCA escreve no plano de voo (10/Ago)

import modelos as M
import precos as P
import classificador_prompt as V4
import classificador_prompt_v5 as V5
from prova_classificador import chamar          # mesma chamada da prova antiga: sem fallback

_ROOT = os.path.dirname(_HERE)
GABARITO = os.path.join(_ROOT, "outputs", "PROVA", "gabarito.csv")
SAIDA = os.path.join(_ROOT, "outputs", "PROVA", "prova_v4_v5.csv")

MODELO = os.getenv("CD_M_CLASSIF", "gpt-5.6-luna")   # o medido em 99,1 % — não mudar sem refazer tudo
RODADAS = 2                                          # 2 = mede repetibilidade. 1 = só acurácia.

# tipos que, se trocados, mudam o MOTOR e portanto a NOTA (LEI 8). Erro aqui é grave.
_GRAVE = {"artigo_original", "revisao_sistematica_meta_analise", "guideline", "revisao_geral"}


def _acha_pdfs():
    """Casa cada linha do gabarito com o PDF no acervo. O acervo se move (o analisador manda o
    PDF para _PUBLICADOS/_RECUSADOS quando termina), então a busca é por nome em qualquer pasta."""
    todos = {}
    for r, _, fs in os.walk(os.path.join(_ROOT, "ARTIGOS")):
        for f in fs:
            if f.lower().endswith(".pdf"):
                todos.setdefault(f, os.path.join(r, f))
    linhas, sem_pdf = [], []
    for g in csv.DictReader(open(GABARITO, encoding="utf-8-sig")):
        n = g["arquivo"]
        certo = (g.get("CORRECAO") or "").strip() or (g.get("classificador_disse") or "").strip()
        cam = todos.get(n)
        if not cam:
            cand = [v for k, v in todos.items()
                    if k.startswith(n[:42]) or n.startswith(k.replace(".pdf", "")[:42])]
            cam = cand[0] if cand else None
        (linhas if cam else sem_pdf).append((n, certo, cam))
    return linhas, sem_pdf


def _feitos():
    if not os.path.exists(SAIDA):
        return set(), []
    r = list(csv.DictReader(open(SAIDA, encoding="utf-8")))
    return {(x["arquivo"], x["versao"], x["rodada"]) for x in r}, r


def rodar(dry=False):
    linhas, sem_pdf = _acha_pdfs()
    feitos, _ = _feitos()
    falta = [(n, c, p, v, r) for (n, c, p) in linhas
             for v in ("v4", "v5") for r in range(1, RODADAS + 1)
             if (n, v, str(r)) not in feitos]

    print("═" * 88)
    print(" PROVA v4 × v5 — os dois prompts, o mesmo texto, o mesmo modelo")
    print("═" * 88)
    print(f"   gabarito conferido à mão pelo Dr. Eduardo : {len(linhas) + len(sem_pdf)} artigos")
    print(f"   PDF encontrado no acervo                  : {len(linhas)}")
    if sem_pdf:
        print(f"   sem PDF (arquivado/removido)              : {len(sem_pdf)} — ficam de fora")
    print(f"   modelo    : {MODELO}   ·   rodadas por versão: {RODADAS} (mede repetibilidade)")
    print(f"   chamadas  : {len(falta)} restantes de {len(linhas) * 2 * RODADAS}")
    # custo pelo MEDIDO, não pelo chute: mediana real das 736 leituras já feitas (uso.jsonl)
    unit = P.custo(MODELO, entrada=4482, saida=260)
    print(f"   custo     : ~US$ {len(falta) * unit:.2f}   ({P.aviso()[:52]}…)")
    print()
    if dry:
        print("   --dry-run: nada foi chamado, nada foi gasto, nada foi escrito.")
        return 0
    if not falta:
        print("   Tudo já rodado. Use --placar.")
        return placar()

    novo = not os.path.exists(SAIDA)
    fh = open(SAIDA, "a", newline="", encoding="utf-8")
    w = csv.DictWriter(fh, fieldnames=["arquivo", "certo", "versao", "rodada", "tipo", "confianca",
                                       "porque", "prova", "estrutura", "metodos_seleciona",
                                       "registro_revisao", "sintese_quantitativa",
                                       "abstract_cabecalhos", "linha_de_tipo", "erro"])
    if novo:
        w.writeheader()

    cache_txt, t0 = {}, time.time()
    for i, (nome, certo, pdf, versao, rodada) in enumerate(falta, 1):
        try:
            if pdf not in cache_txt:                       # o MESMO texto para as duas versões
                cache_txt[pdf] = V4.paginas_1a3(pdf)
            txt = cache_txt[pdf]
            mod = V4 if versao == "v4" else V5
            saida, _, _ = chamar(MODELO, mod.montar(txt))
            if versao == "v4":
                tipo, conf, prova = V4.ler_resposta(saida)
                linha = dict(tipo=tipo, confianca=conf, porque="(v4 decide sozinho)", prova=prova)
            else:
                tipo, conf, prova, porque, s = V5.classificar(saida)
                linha = dict(tipo=tipo, confianca=conf, porque=porque, prova=prova,
                             estrutura=s.get("estrutura", ""),
                             metodos_seleciona=s.get("metodos_seleciona", ""),
                             registro_revisao=s.get("registro_revisao", "")[:60],
                             sintese_quantitativa=s.get("sintese_quantitativa", "")[:60],
                             abstract_cabecalhos=s.get("abstract_cabecalhos", "")[:60],
                             linha_de_tipo=s.get("linha_de_tipo", "")[:40])
            erro = ""
        except Exception as e:
            linha, erro = dict(tipo="", confianca="", porque="", prova=""), f"{type(e).__name__}: {e}"[:120]
        w.writerow({"arquivo": nome, "certo": certo, "versao": versao, "rodada": rodada,
                    "erro": erro, **linha})
        fh.flush()
        marca = "✅" if linha.get("tipo") == certo else ("💥" if erro else "❌")
        print(f"  {i:>4}/{len(falta)} {marca} {versao} r{rodada} {nome[:44]:44s} → {linha.get('tipo') or erro[:24]}")
    fh.close()
    print(f"\n   {time.time() - t0:.0f}s")
    return placar()


def placar():
    if not os.path.exists(SAIDA):
        print("Nada rodado ainda.")
        return 1
    R = [x for x in csv.DictReader(open(SAIDA, encoding="utf-8")) if not x["erro"]]
    print()
    print("═" * 88)
    print(" PLACAR")
    print("═" * 88)

    # ── 1. ACURÁCIA ──
    print(f"\n   {'versão':8s} {'acertos':>10s} {'de':>5s} {'acurácia':>10s} {'erros GRAVES':>14s}")
    for v in ("v4", "v5"):
        d = [x for x in R if x["versao"] == v]
        if not d:
            continue
        ok = sum(1 for x in d if x["tipo"] == x["certo"])
        grave = sum(1 for x in d if x["tipo"] != x["certo"]
                    and x["certo"] in _GRAVE and x["tipo"] in _GRAVE)
        print(f"   {v:8s} {ok:>10} {len(d):>5} {100 * ok / len(d):>9.1f}% {grave:>14}")
    print("   (GRAVE = trocou entre original/meta/diretriz/revisão — muda o MOTOR e a NOTA)")

    # ── 2. REPETIBILIDADE ──
    print(f"\n   ── REPETIBILIDADE (a mesma pergunta, {RODADAS} vezes) ──")
    for v in ("v4", "v5"):
        por = {}
        for x in R:
            if x["versao"] == v:
                por.setdefault(x["arquivo"], set()).add(x["tipo"])
        com2 = {k: s for k, s in por.items() if len(s) >= 1}
        instavel = [k for k, s in por.items() if len(s) > 1]
        if com2:
            print(f"   {v}: {len(com2) - len(instavel)} de {len(com2)} deram a MESMA resposta "
                  f"nas {RODADAS} rodadas ({100 * (len(com2) - len(instavel)) / len(com2):.1f}%)")
            for k in instavel[:5]:
                print(f"        ⚠️ instável: {k[:52]} → {sorted(por[k])}")

    # ── 3. ONDE CADA UM ERRA ──
    for v in ("v4", "v5"):
        errs = [x for x in R if x["versao"] == v and x["tipo"] != x["certo"]]
        if not errs:
            print(f"\n   ── {v}: NENHUM ERRO ──")
            continue
        print(f"\n   ── ONDE O {v} ERRA ({len(errs)}) ──")
        vistos = set()
        for x in errs:
            k = (x["arquivo"], x["tipo"])
            if k in vistos:
                continue
            vistos.add(k)
            g = "🔴 GRAVE" if x["certo"] in _GRAVE and x["tipo"] in _GRAVE else "  leve"
            print(f"   {g}  certo={x['certo'][:26]:26s} disse={x['tipo'][:26]:26s} {x['arquivo'][:36]}")
            if v == "v5":
                print(f"           porque: {x['porque'][:70]}")
                print(f"           sinais: estrutura={x['estrutura'][:12]} · seleciona={x['metodos_seleciona'][:10]}"
                      f" · registro={'SIM' if x['registro_revisao'] not in ('', 'NAO') else 'não'}"
                      f" · síntese={'SIM' if x['sintese_quantitativa'] not in ('', 'NAO') else 'não'}")

    # ── 4. QUEM SALVOU QUEM ──
    v4 = {x["arquivo"]: x for x in R if x["versao"] == "v4" and x["rodada"] == "1"}
    v5 = {x["arquivo"]: x for x in R if x["versao"] == "v5" and x["rodada"] == "1"}
    ganhou = [a for a in v5 if a in v4 and v5[a]["tipo"] == v5[a]["certo"] != v4[a]["tipo"]]
    perdeu = [a for a in v5 if a in v4 and v4[a]["tipo"] == v4[a]["certo"] != v5[a]["tipo"]]
    print(f"\n   ── O QUE MUDOU ──")
    print(f"   o v5 ACERTA e o v4 errava : {len(ganhou)}")
    for a in ganhou[:8]:
        print(f"        {a[:50]}  ({v4[a]['tipo']} → {v5[a]['tipo']})")
    print(f"   o v5 ERRA e o v4 acertava : {len(perdeu)}   ← se >0, é regressão")
    for a in perdeu[:8]:
        print(f"        ⚠️ {a[:48]}  ({v4[a]['tipo']} → {v5[a]['tipo']})  porque: {v5[a]['porque'][:44]}")

    print(f"\n   → {SAIDA}")
    return 0


if __name__ == "__main__":
    if "--placar" in sys.argv:
        sys.exit(placar())
    sys.exit(rodar(dry="--dry-run" in sys.argv))
