"""
caixa_preta.py — LÊ O PLANO DE VOO E DIZ ONDE PROCURAR.

═══════════════════════════════════════════════════════════════════════════════════════
O QUE ESTE PROGRAMA RESPONDE
═══════════════════════════════════════════════════════════════════════════════════════

Três perguntas, e só três:

    1. O QUE RODOU HOJE?           — e o que devia ter rodado e não rodou.
    2. QUEM NÃO CHEGOU AO DESTINO? — em que trecho parou, com a mensagem de erro real.
    3. ONDE EU PROCURO?            — a zona de busca daquele trecho, ordenada por probabilidade.

Não é um log bonito. Log a gente já tinha — 26 arquivos em `outputs/LOGS`, e mesmo assim
levei uma tarde para descobrir por que o Radar não chegou em 09/Ago. A diferença é que o log
conta o que o programa DISSE, e o plano de voo conta ONDE O ARTIGO ESTAVA quando parou.

═══════════════════════════════════════════════════════════════════════════════════════
O QUE ELE NÃO FAZ, DE PROPÓSITO
═══════════════════════════════════════════════════════════════════════════════════════

· Não chama modelo, não fala com banco, não escreve nada. Custo zero, sempre.
· Não adivinha a causa. Ele diz o TRECHO e as causas CONHECIDAS daquele trecho — a zona de
  busca. Quem decide qual delas é, olhando a mensagem de erro, é o Dr. Eduardo (ou eu).
· Não substitui o `ensaio_seco.py`. Aquele responde "o que ACONTECERIA se eu rodasse";
  este responde "o que ACONTECEU quando você rodou".

    python3 src/caixa_preta.py              → as últimas 24h
    python3 src/caixa_preta.py 72           → as últimas 72h
    python3 src/caixa_preta.py radar        → só o que tem 'radar' no nome
"""
import os
import sys
import datetime
from collections import defaultdict, Counter

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
import voo as VOO

# ═══════════════════════════════════════════════════════════════════════════════════════
# O DESTINO DE CADA BLOCO — qual waypoint significa "chegou"
# ═══════════════════════════════════════════════════════════════════════════════════════
#
# 09/Ago, na primeira prova do V·2: um artigo que terminou em C5_MOVEU (o destino do
# classificador) apareceu com a zona de busca do C6_DIARIO — que é waypoint de RODADA, não
# de artigo. A resposta estava tecnicamente certa e praticamente inútil.
# Daí esta tabela: cada bloco tem um destino, e chegar nele é sucesso, não silêncio.
DESTINO = {
    "CLASSIFICADOR": "C5_MOVEU",     # o C6_DIARIO é da rodada inteira, não do artigo
    "ANALISADOR": "A4_OK",
    "PUBLICADOR": "P4_BANCO",
    "ENTREGA": "E5_ENVIOU",
}
# waypoints que pertencem à RODADA, não a um artigo — não entram na conta de "quem não chegou"
DE_RODADA = {"C6_DIARIO", "E4_LISTA", "E5_ENVIOU"}


def _voo_por_artigo(linhas):
    """Agrupa as marcas por artigo, preservando a ordem cronológica."""
    d = defaultdict(list)
    for l in linhas:
        a = l.get("artigo")
        if a:
            d[a].append(l)
    return d


def _chegou(marcas):
    """O artigo alcançou o destino do bloco mais avançado por onde passou?"""
    blocos = {VOO.bloco_do_waypoint(m["wp"]) for m in marcas if VOO.bloco_do_waypoint(m["wp"])}
    if not blocos:
        return False, None
    # o bloco mais avançado que este artigo tocou
    ordem = ["CLASSIFICADOR", "ANALISADOR", "PUBLICADOR", "ENTREGA"]
    ultimo_bloco = max(blocos, key=lambda b: ordem.index(b) if b in ordem else -1)
    alvo = DESTINO.get(ultimo_bloco)
    for m in marcas:
        if m["wp"] == alvo and m["ok"]:
            return True, ultimo_bloco
    return False, ultimo_bloco


def relatorio(horas=24, filtro=""):
    linhas = VOO.ler(desde_horas=horas)
    if filtro:
        linhas = [l for l in linhas if filtro.lower() in str(l.get("artigo", "")).lower()]

    print("═" * 82)
    print(" CAIXA-PRETA · o que aconteceu de verdade")
    print(f" últimas {horas}h" + (f" · filtro '{filtro}'" if filtro else "") +
          f" · {len(linhas)} marca(s)")
    print("═" * 82)

    if not linhas:
        print()
        print("   Nenhuma marca no período.")
        print()
        print("   Isso pode significar DUAS coisas muito diferentes:")
        print("     1. nada rodou (nenhuma chave foi clicada, nenhum workflow disparou)")
        print("     2. rodou, mas o registro não está sendo gravado")
        print()
        print(f"   O arquivo é {VOO.VOO}")
        print("   Se ele não existe e você rodou algo hoje, o problema é o registro, não a rodada.")
        return 1

    # ── 1. O QUE RODOU, POR BLOCO ──
    por_bloco = defaultdict(lambda: {"ok": 0, "falha": 0})
    for l in linhas:
        b = VOO.bloco_do_waypoint(l["wp"]) or "?"
        por_bloco[b]["ok" if l["ok"] else "falha"] += 1
    print()
    print("   ── O QUE RODOU ──")
    print(f"   {'bloco':18s} {'marcas ok':>10s} {'falhas':>8s}")
    for b in ("CLASSIFICADOR", "ANALISADOR", "PUBLICADOR", "ENTREGA"):
        if b in por_bloco:
            c = por_bloco[b]
            print(f"   {b:18s} {c['ok']:>10d} {c['falha']:>8d}")
        else:
            print(f"   {b:18s} {'—':>10s} {'—':>8s}   (não rodou no período)")

    # ── 2. QUEM NÃO CHEGOU ──
    artigos = _voo_por_artigo(linhas)
    parados = []
    for art, marcas in artigos.items():
        ok, bloco = _chegou(marcas)
        if not ok:
            u = marcas[-1]
            if u["wp"] in DE_RODADA and u["ok"]:
                continue
            parados.append((art, u, bloco))

    # ═══ RETIDO NÃO É FALHA ═══
    # Nota <6 é a LEI 10 funcionando: *"o CardioDaily publica muito menos e reprova muito
    # mais — esta é a regra"*. Misturar os dois numa lista só é o mesmo erro de leitura que
    # em 09/Ago me fez contar 90 artigos publicados como retidos: números certos, conclusão
    # errada, porque as categorias estavam trocadas.
    retidos = [(a, u, b) for a, u, b in parados
               if u["wp"] == "P2_CONTRATO" and "FICA retido" in str(u.get("erro", ""))]
    falhas = [x for x in parados if x not in retidos]

    print()
    if retidos:
        print(f"   ── {len(retidos)} RETIDO(S) PELA RÉGUA — não é falha, é o produto ──")
        for a, u, _ in retidos[:6]:
            print(f"       nota {u.get('nota', '?')} · {a[:62]}")
        if len(retidos) > 6:
            print(f"       … e mais {len(retidos) - 6}")

    print()
    if not falhas:
        print(f"   ✅ nenhuma falha: os {len(artigos) - len(retidos)} artigos que deviam chegar chegaram.")
    else:
        print(f"   ── {len(falhas)} DE {len(artigos)} NÃO CHEGARAM ──")
        parados = falhas
        # agrupa pelo TRECHO: 40 artigos parados no mesmo ponto é UM problema, não 40
        por_trecho = defaultdict(list)
        for art, u, bloco in parados:
            trecho, _ = VOO.zona_de_busca(u["wp"], ok_ultimo=u["ok"])
            por_trecho[(trecho, u["wp"], u["ok"])].append((art, u.get("erro", "")))

        for (trecho, wp, ok), itens in sorted(por_trecho.items(), key=lambda x: -len(x[1])):
            print()
            print(f"   ▸ {trecho}   —   {len(itens)} artigo(s)")
            print(f"     ({VOO.descricao(wp)})")
            # a mensagem de erro REAL, que é a pista principal
            erros = Counter(e[:110] for _, e in itens if e)
            for e, n in erros.most_common(2):
                print(f"     erro: {e}" + (f"   ({n}×)" if n > 1 else ""))
            for a, _ in itens[:4]:
                print(f"       · {a[:66]}")
            if len(itens) > 4:
                print(f"       … e mais {len(itens) - 4}")
            # ── 3. ONDE PROCURAR ──
            _, causas = VOO.zona_de_busca(wp, ok_ultimo=ok)
            if causas:
                print(f"     ZONA DE BUSCA:")
                for i, c in enumerate(causas, 1):
                    print(f"       {i}. {c}")

    # ── O SILÊNCIO: o que NÃO apareceu e devia aparecer todo dia ──
    print()
    print("   ── SILÊNCIO (o que não deu sinal) ──")
    tem_radar = any(l["wp"].startswith("E1") and l["ok"] for l in linhas)
    tem_envio = any(l["wp"] == "E5_ENVIOU" for l in linhas)
    if horas >= 24:
        if not tem_radar:
            print("   ⚠️  o RADAR não reportou geração nas últimas 24h.")
            _, causas = VOO.zona_de_busca("E1_RADAR", ok_ultimo=False)
            for i, c in enumerate(causas[:3], 1):
                print(f"       {i}. {c}")
        if not tem_envio:
            print("   ⚠️  nenhuma ENTREGA reportada nas últimas 24h.")
        if tem_radar and tem_envio:
            print("   ✓ radar e entrega deram sinal no período.")
    print()
    print("═" * 82)
    print("   O plano de voo mostra ONDE parou. A causa exata está na mensagem de erro")
    print("   e no log da rodada — mas você já sabe em que trecho procurar.")
    return 0


def main():
    horas, filtro = 24, ""
    for a in sys.argv[1:]:
        if a.isdigit():
            horas = int(a)
        else:
            filtro = a
    return relatorio(horas, filtro)


if __name__ == "__main__":
    sys.exit(main())
