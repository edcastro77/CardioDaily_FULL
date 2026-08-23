"""
ensaio_seco.py — O QUE ACONTECERIA SE EU RODASSE, SEM GASTAR NADA.

═══════════════════════════════════════════════════════════════════════════════════════
POR QUE ESTE ARQUIVO EXISTE (06/Ago/2026)
═══════════════════════════════════════════════════════════════════════════════════════

Palavras do Dr. Eduardo, depois de eu queimar US$ 9 numa rodada em que 13 de 31 diretrizes
foram recusadas por um defeito meu:

    *"eu não tenho dinheiro para você ficar rasgando por conta de erros infantis"*

Ele tem razão, e o defeito era do tipo mais barato de achar: o `contrato.py` recusava `nota < 6`
sem saber da exceção da diretriz (LEI 10, decidida em 05/Ago). Eu tinha implementado a exceção no
`decidir_entregaveis`, escrito a trava mirando ali, e não varrido o contrato — a LEI 9 inteira.

**Nada disso precisava de uma chamada de LLM para ser descoberto.** O motor é função pura, o
contrato é função pura, e os FATOS de 131 pacotes já estão no disco. Dava para saber o resultado
antes de gastar o primeiro centavo.

É isso que este programa faz: pega os pacotes que JÁ EXISTEM no STAGING, roda o motor e o contrato
em cima deles, e diz **quem publicaria, quem seria recusado e por quê** — sem tocar em API, sem
tocar em banco, sem escrever nada.

    python3 src/ensaio_seco.py                 → todos os pacotes do STAGING
    python3 src/ensaio_seco.py diretriz        → só um tipo

REGRA QUE EU ASSUMO A PARTIR DE HOJE: antes de pedir para ele clicar a Chave 2 depois de QUALQUER
mudança em motor, contrato ou porta, eu rodo isto primeiro e mostro o resultado. Se o ensaio seco
não bate com o que eu prometi, o erro é meu e é de graça.
"""
import os
import re
import sys
import glob
import json
from collections import Counter, defaultdict

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
STAGING = os.path.join(os.path.dirname(_HERE), "outputs", "STAGING")


def _canonico(pasta):
    c = glob.glob(os.path.join(pasta, "*_CANONICO.md"))
    return open(c[0], encoding="utf-8").read() if c else ""


def ensaiar(pasta):
    """Devolve (tipo, nota_disco, nota_recalculada, status, motivos). Nada é escrito."""
    import notas_prototipo as N
    import contrato as C
    import ficha_site as F

    # ═══ 10/Ago — "NADA É ESCRITO" ERA MENTIRA, E SUJAVA A ÚNICA PROVA QUE TEMOS ═══
    # `F.montar()` é código de PRODUÇÃO e marca o waypoint `P1_FICHA`. Este ensaio chama
    # `montar()` uma vez por pacote — logo, cada vez que eu rodava o ensaio (de graça, para
    # NÃO fazer o Dr. Eduardo gastar) o plano de voo ganhava 119 marcas de produção falsas.
    #
    # Medido na rodada de 10/Ago: P1_FICHA com 222 marcas para 119 artigos. Um artigo que
    # tinha chegado ao P2_CONTRATO às 23:49 aparecia na Chave 18 como "parado no P1_FICHA",
    # com zona de busca, porque a caixa-preta olha a ÚLTIMA marca — e as últimas eram minhas.
    #
    # O observador alterando o observado, na ferramenta feita justamente para observar sem
    # alterar. A linha abaixo é o conserto inteiro.
    import voo as _VOO
    _VOO.silenciar(True)

    fj = glob.glob(os.path.join(pasta, "*_fatos.json"))
    if not fj:
        return None
    try:
        fatos = json.load(open(fj[0]))
    except Exception as e:
        return ("?", None, None, "FATOS ILEGÍVEIS", [str(e)[:70]])

    tipo = fatos.get("tipo_documento") or "?"
    ct = _canonico(pasta)
    m = re.search(r"nota_aplicabilidade_clinica:\s*(\d+)", ct)
    nota_disco = int(m.group(1)) if m else None

    try:
        r = N.score(fatos)
    except Exception as e:
        return (tipo, nota_disco, None, "MOTOR QUEBROU", [str(e)[:70]])
    nota_nova = r["aplic"]

    # o CONTRATO, com a ficha real montada do disco — é exatamente o que o portão faria
    #
    # ⚠️ 22/Ago — ESTE ENSAIO DEIXOU DE SER DE GRAÇA, e isso precisa estar escrito.
    # Ele nasceu para ensaiar a régua SEM fazer o Dr. Eduardo gastar. Só que em 20/Ago o tema
    # entrou dentro de `montar()` (PubMed + LLM) e em 22/Ago o MeSH também — então cada pacote
    # ensaiado agora custa até duas chamadas de modelo. **Mantive o `montar()` de propósito:**
    # o ensaio existe para reproduzir EXATAMENTE o que o portão faria, e uma ficha fingida
    # (com `CARDIODAILY_SEM_REDE`) aprovaria coisas que o portão de verdade recusaria — trocaria
    # um custo por uma mentira, que é pior.
    # O que muda é a honestidade: o programa AVISA o custo antes de rodar (ver `main`).
    try:
        ficha = F.montar(pasta)
    except Exception as e:
        return (tipo, nota_disco, nota_nova, "FICHA QUEBROU", [str(e)[:70]])
    # a nota da ficha vem do canônico; para ensaiar a régua NOVA, substituímos pela recalculada
    ficha = dict(ficha)
    ficha["nota_aplicabilidade"] = nota_nova
    ficha["nota_trabalho_estatistico"] = r["trabalho"]
    ficha["muda_conduta"] = r["muda_conduta"]
    viol = C.validar(ficha)
    return (tipo, nota_disco, nota_nova, "PUBLICA" if not viol else "RECUSADO",
            [v[:96] for v in viol])


def main():
    filtro = (sys.argv[1].lower() if len(sys.argv) > 1 else "")
    pastas = [p for p in sorted(glob.glob(os.path.join(STAGING, "*"))) if os.path.isdir(p)]
    if not pastas:
        print("STAGING vazio — nada a ensaiar.")
        return 0

    # ═══ 22/Ago — A TELA DIZIA "CUSTO ZERO · NÃO CHAMA MODELO", E ERA MENTIRA ═══
    # Verdade até 19/Ago. Em 20/Ago o TEMA entrou dentro de `ficha_site.montar()` (PubMed +
    # LLM, LEI 5, e estava certo), e em 22/Ago o MeSH também. O ensaio chama `montar()` uma vez
    # por pacote — de propósito, porque ele existe para reproduzir o que o PORTÃO faria, e uma
    # ficha fingida aprovaria o que o portão recusaria.
    # O que não podia continuar era a TELA anunciando grátis enquanto o cartão era debitado.
    # É o mesmo defeito do "US$0,30 chumbado" da Chave 2 (C·3): instrumento que mente.
    _n = len(pastas)
    _custo = _n * 0.0012                      # ~2 chamadas da cadeia CLASSIFICACAO por pacote
    print("═" * 82)
    print(" ENSAIO SECO · o que aconteceria se você rodasse")
    print(" não fala com o banco, não escreve nada, não move arquivo")
    print(f" ⚠️  MAS CHAMA O MODELO: {_n} pacote(s) × tema + MeSH ≈ US$ {_custo:.2f}")
    print("     (desde 20/Ago o tema mora dentro da ficha; o ensaio monta a ficha de verdade")
    print("      justamente para não aprovar aqui o que o portão recusaria lá)")
    print("═" * 82)
    if _n > 40 and sys.stdin.isatty():
        _r = input(f"\n   São {_n} pacotes (~US$ {_custo:.2f}). Seguir? [s/N]: ")
        if _r.strip().lower() not in ("s", "si", "sim", "y", "yes", "ok"):
            print(f'\n⛔ CANCELADO — você digitou "{_r.strip()}", e eu esperava sim / s.')
            print("   Nada rodou, nada foi gasto.")
            return 0

    por_tipo = defaultdict(lambda: Counter())
    recusas = defaultdict(list)
    mudou_nota = []
    quebrou = []

    for p in pastas:
        r = ensaiar(p)
        if r is None:
            continue
        tipo, n_old, n_new, status, viol = r
        if filtro and filtro not in tipo.lower():
            continue
        base = os.path.basename(p)[:52]
        por_tipo[tipo][status] += 1
        if status in ("PUBLICA", "RECUSADO"):
            if n_old is not None and n_new is not None and n_old != n_new:
                mudou_nota.append((tipo, base, n_old, n_new))
            if status == "RECUSADO":
                # o motivo importa mais que o nome: agrupa por causa
                causa = viol[0].split(":")[0] if viol else "?"
                recusas[causa].append((base, n_new))
        else:
            quebrou.append((base, status, viol))

    print()
    print(f"   {'tipo':22s} {'publica':>8s} {'recusado':>9s} {'quebrou':>8s}")
    for t in sorted(por_tipo):
        c = por_tipo[t]
        q = sum(v for k, v in c.items() if k not in ("PUBLICA", "RECUSADO"))
        print(f"   {t:22s} {c['PUBLICA']:>8d} {c['RECUSADO']:>9d} {q:>8d}")

    if recusas:
        print()
        print("   ── POR QUE SERIAM RECUSADOS (agrupado pela CAUSA) ──")
        for causa, itens in sorted(recusas.items(), key=lambda x: -len(x[1])):
            print(f"\n   ▸ {causa}  —  {len(itens)} artigo(s)")
            for b, n in itens[:6]:
                print(f"       nota {n} · {b}")
            if len(itens) > 6:
                print(f"       … e mais {len(itens) - 6}")

    # ═══ 07/Ago — O ACERVO NÃO ACOMPANHA A RÉGUA, E ISSO ACONTECE EM SILÊNCIO ═══
    # A terra arrasada refaz o pacote quando o carimbo do motor muda — mas SÓ para quem está
    # na fila. Artigo publicado sai da pasta, e daí em diante fica congelado com a régua do dia
    # em que foi analisado. Foi como PLATO, TRITON e DAPA-HF ficaram com nota 8 depois de o
    # Dr. Eduardo decidir o piso de independência: 46 minutos separaram a análise da regra.
    # O card ia postar `NOTA 8/10` sem o selo MUDA CONDUTA — e o card não errou, ele copiou.
    try:
        from analisador import hash_arquivo_src as _h
        _atual = f"notas_prototipo.py@{_h('notas_prototipo.py')}"
        _velhos = 0
        for _p in pastas:
            _v = os.path.join(_p, "_versoes.json")
            if not os.path.exists(_v):
                continue
            try:
                if json.load(open(_v)).get("motor") != _atual:
                    _velhos += 1
            except Exception:
                pass
        if _velhos:
            print()
            print(f"   ⚠️  {_velhos} pacote(s) com CARIMBO DE MOTOR VELHO.")
            print("      A nota deles foi calculada por uma régua anterior. Rode:")
            print("         python3 src/reparar_notas.py        (ensaio, custo zero)")
    except Exception:
        pass

    if mudou_nota:
        print()
        print(f"   ── A NOTA MUDARIA em {len(mudou_nota)} pacote(s) ──")
        for t, b, a, n in mudou_nota[:14]:
            print(f"     {t:20s} {b:54s} {a} → {n}")

    if quebrou:
        print()
        print(f"   ── {len(quebrou)} pacote(s) QUEBRARAM no ensaio ──")
        for b, s, v in quebrou[:8]:
            print(f"     {s:16s} {b}")
            for x in v[:1]:
                print(f"                      {x}")

    print()
    print("═" * 82)
    print("   Isto é o DISCO com a régua de AGORA. Não é o que está no Supabase, e não")
    print("   substitui rodar: o que muda de verdade é o texto, e texto exige o modelo.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
