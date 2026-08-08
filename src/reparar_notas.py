"""
reparar_notas.py — QUANDO A RÉGUA MUDA, O ACERVO TEM DE ACOMPANHAR.

═══════════════════════════════════════════════════════════════════════════════════════
POR QUE ESTE ARQUIVO EXISTE (07/Ago/2026)
═══════════════════════════════════════════════════════════════════════════════════════

O card do PLATO saiu com `NOTA 8/10` e sem o selo `MUDA CONDUTA`. O motor, com os MESMOS
fatos, calcula 9 e SIM. O card não errou — ele copiou fielmente um canônico velho.

    canônico do PLATO escrito ...... 06/Ago 08:56
    PISO_INDEPENDENCIA commitado ... 06/Ago 09:42   ← 46 minutos depois

O PLATO foi analisado antes de a regra existir. A Chave 2 dos 236 originais rodou às 21:47 e
DEVERIA tê-lo refeito (a terra arrasada vê o carimbo do motor) — mas não o viu, porque **ele
já tinha sido publicado de manhã, e quem publica sai da pasta**. A terra arrasada só age sobre
quem está na fila.

É o mesmo mecanismo que mordeu duas vezes esta semana:
    · artigo RECUSADO sai da fila e não volta quando a regra muda (06/Ago, 13 diretrizes)
    · artigo PUBLICADO sai da fila e não atualiza quando a régua muda (07/Ago, 3 landmarks)

═══════════════════════════════════════════════════════════════════════════════════════
POR QUE ISTO NÃO CUSTA NADA
═══════════════════════════════════════════════════════════════════════════════════════

O motor é FUNÇÃO PURA e os FATOS já estão no disco. Recalcular a nota não precisa de LLM,
não relê o PDF, não chama rede. O que custaria dinheiro seria refazer os TEXTOS — e o texto
só precisa mudar se a nota mudar, porque o redator explica a nota.

Por isso este programa faz duas coisas e mais nada:
    1. recalcula a nota de todo pacote e diz onde ela mudou   (custo ZERO)
    2. reescreve o canônico dos que mudaram                    (custo ZERO)

E DECLARA, sem esconder, o que ele NÃO conserta: a perícia, o ACRI e o áudio continuam
escritos em cima da nota velha. Para esses, é preciso reanalisar de verdade — o que custa.
Medido em 07/Ago: 3 pacotes mudam de nota em 433. Reanalisar 3 custa US$ 0,90.

⚠️ NÃO escreve no Supabase (LEI 5). Depois de reparar o disco, quem republica é o portão.
"""
import os
import re
import sys
import json
import glob

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)


def recalcular(pasta):
    """Devolve (nota_no_disco, nota_do_motor, resultado) ou None se não der para avaliar."""
    import notas_prototipo as N
    can = glob.glob(os.path.join(pasta, "*_CANONICO.md"))
    fj = glob.glob(os.path.join(pasta, "*_fatos.json"))
    if not (can and fj):
        return None
    txt = open(can[0], encoding="utf-8").read()
    m = re.search(r"nota_aplicabilidade_clinica:\s*(\d+)", txt)
    if not m:
        return None
    try:
        r = N.score(json.load(open(fj[0])))
    except Exception:
        return None
    return int(m.group(1)), r["aplic"], r


def reescrever_canonico(pasta, r):
    """Atualiza as três linhas do veredito no canônico. Cirúrgico de propósito: mexer em mais
    campos seria reescrever o que o redator produziu, e isso exige o modelo."""
    can = glob.glob(os.path.join(pasta, "*_CANONICO.md"))[0]
    t = open(can, encoding="utf-8").read()
    delatores = json.dumps([f for f in r.get("flags", [])], ensure_ascii=False)
    t = re.sub(r"(nota_aplicabilidade_clinica:\s*)\d+", rf"\g<1>{r['aplic']}", t, count=1)
    t = re.sub(r"(nota_trabalho_estatistico:\s*)\d+", rf"\g<1>{r['trabalho']}", t, count=1)
    t = re.sub(r'(muda_conduta:\s*)"[^"]*"', lambda mm: mm.group(1) + json.dumps(r["muda_conduta"], ensure_ascii=False), t, count=1)
    t = re.sub(r"(delatores:\s*)\[.*?\]", lambda mm: mm.group(1) + delatores, t, count=1, flags=re.S)
    open(can, "w", encoding="utf-8").write(t)
    return can


def main():
    aplicar = "--aplicar" in sys.argv
    staging = os.path.join(os.path.dirname(_HERE), "outputs", "STAGING")
    mudam, iguais, sem = [], 0, 0
    for p in sorted(glob.glob(os.path.join(staging, "*"))):
        if not os.path.isdir(p):
            continue
        r = recalcular(p)
        if r is None:
            sem += 1
            continue
        velha, nova, res = r
        if velha == nova:
            iguais += 1
        else:
            mudam.append((p, velha, nova, res))

    print("═" * 78)
    print(" REPARAR NOTAS · o motor é função pura — recalcular NÃO custa nada")
    print("═" * 78)
    print(f"\n   iguais: {iguais}   ·   MUDAM: {len(mudam)}   ·   não avaliáveis: {sem}\n")
    for p, v, n, res in mudam:
        print(f"   {os.path.basename(p)[:54]:56s} {v} → {n}  ({res['muda_conduta'][:22]})")
    if not mudam:
        print("   Nada a reparar: o disco está com a régua de agora.")
        return 0
    if not aplicar:
        print(f"\n   ENSAIO — nada foi escrito. Para aplicar:")
        print(f"      python3 src/reparar_notas.py --aplicar")
        return 0

    for p, v, n, res in mudam:
        reescrever_canonico(p, res)
        print(f"   ✅ canônico atualizado: {os.path.basename(p)[:52]}")
    print(f"\n   {len(mudam)} canônico(s) reparado(s).")
    print("\n   ⚠️  O QUE ISTO **NÃO** CONSERTOU — e você precisa saber:")
    print("      A perícia, o ACRI e o áudio desses artigos foram ESCRITOS em cima da nota velha.")
    print("      O redator explica a nota; se a nota mudou, o texto está justificando outro número.")
    print("      Para alinhar o texto é preciso REANALISAR (a Chave 2, com o PDF de volta na pasta).")
    print(f"      Custo: ~US$ {len(mudam) * 0.30:.2f}.")
    print("      As linhas do Supabase também seguem velhas até o portão republicar.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
