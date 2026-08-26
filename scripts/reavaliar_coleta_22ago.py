"""
reavaliar_coleta_22ago.py — devolver à fila quem caiu por "garbage-in" que era só SILÊNCIO.

═══════════════════════════ POR QUE ISTO EXISTE ═══════════════════════════
Palavras dele, ao ler a lista dos 255 retidos: *"está me dando agonia ler esta lista"*.

O motivo nº 1 da lista era `garbage-in (dado de entrada ruim)` — **55 artigos**. E não era
veredito: o campo `qualidade_entrada` era um BOOLEANO OBRIGATÓRIO, e o prompt só oferecia
"padronizada" ou "raspada de prontuário". Artigo observacional quase nunca descreve codebook ou
laboratório calibrado — não cabe no limite de palavras. Diante do silêncio o modelo marcava
`false`, e `false` capava o rigor em 5, que capava a aplicabilidade.

MEDIDO no acervo: **181 observacionais com `false`** (56 etiologia · 96 prognóstico · 29
diagnóstico), sem nenhuma forma de saber quantos eram "o artigo disse que era ruim" e quantos
eram "o artigo não disse nada".

É a assinatura desta casa, invertida: em julho a ausência era lida como o caso FAVORÁVEL; aqui
era lida como o DESFAVORÁVEL. O certo é a ausência ter NOME (LEI 11) — e o vocabulário de três
valores já existia em `relevancia_clinica` (`incerto`).

MEDIDO DEPOIS DO CONSERTO, com o motor rodando sobre os FATOS já em disco:
    252 reavaliados · **93 SOBEM** · 159 iguais · **0 caem**
    os 93 vão de 5 para 7 — todos passam a ser publicáveis.

═══════════════════ O CUSTO QUE ESTE PROGRAMA EXISTE PARA EVITAR ═══════════════════
Mexi no `analise_prompt.md`. Pela regra da **TERRA ARRASADA** (04/Ago), a próxima Chave 2 veria
"o extrator mudou" e apagaria os **942 pacotes** do disco para re-extrair tudo — a etapa mais
cara da corrente, paga de novo.

**Por que NÃO precisa re-extrair:** o motor passou a entender os DOIS formatos
(`notas_prototipo.coleta_padronizada`). O booleano velho `False` é lido como "não informado", de
propósito: foi produzido por um prompt que não oferecia "não sei", e tratá-lo como declaração
seria dar valor de prova a uma resposta forçada. Nenhum fato já extraído mudou de significado.

⚠️ Como em 19/Ago, a exceção é ESTREITA: re-carimba SÓ os carimbos de extração. Se o redator, o
ACRI, o áudio ou o motor mudarem de verdade, a terra arrasada continua funcionando.

Este programa NÃO chama modelo, NÃO fala com o Supabase e roda em dois tempos (LEI 12).
Quem analisa e publica continua sendo a Chave 2 (LEI 5 — portão único).

Uso:  python3 scripts/reavaliar_coleta_22ago.py              # ensaio
      python3 scripts/reavaliar_coleta_22ago.py --executar
"""
import glob
import json
import os
import re
import shutil
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "src"))
CLASSIFICADOS = os.path.join(RAIZ, "ARTIGOS", "CLASSIFICADOS")
RETIDOS = os.path.join(CLASSIFICADOS, "_RETIDOS_PELA_REGUA")
PISO = 6                                   # a porta da LEI 10

PASTA_DO_TIPO = {"original": "ARTIGOS_ORIGINAIS", "meta": "META_ANALISES",
                 "diretriz": "GUIDELINES", "revisao_narrativa": "REVISOES",
                 "revisao_geral": "REVISOES",
                 "revisao_sistematica_meta_analise": "META_ANALISES"}
# derivados que nasceram da nota VELHA e precisam ser refeitos com a nova
DERIVADOS = ("_ACRI.txt", "_analise.md", "_analise.pdf", "_analise.html", "_visual.png",
             "_audio.mp3", "_roteiro_audio.txt", "_CANONICO.md", "_gancho_abertura.txt",
             "_card.png", "_REVISAR_publicacao.txt")


def pacote(base):
    for pat in (os.path.join(RAIZ, "outputs", "STAGING", base),
                os.path.join(RAIZ, "outputs", "ARQUIVO", "*", base)):
        for p in glob.glob(pat):
            if os.path.isdir(p):
                return p
    return None


def nota_antiga(p):
    for c in glob.glob(os.path.join(p, "*_CANONICO.md")):
        m = re.search(r"nota_aplicabilidade_clinica:\s*(-?\d+)",
                      open(c, encoding="utf-8", errors="ignore").read())
        if m:
            return int(m.group(1))
    return None


def recalcular(p):
    """(nota_nova, tipo) a partir dos FATOS em disco. Custo ZERO — nenhum modelo."""
    import notas_prototipo as N
    fj = glob.glob(os.path.join(p, "*_fatos.json"))
    if not fj:
        return None, None
    fatos = json.load(open(fj[0], encoding="utf-8"))
    try:
        return N.score(fatos).get("aplic"), fatos.get("tipo_documento")
    except Exception as e:
        print(f"      ⚠️  motor falhou em {os.path.basename(p)[:40]}: {type(e).__name__}: {e}")
        return None, fatos.get("tipo_documento")


def recarimbar_extracao(p):
    """Só os carimbos de EXTRAÇÃO — os outros ficam, para a terra arrasada seguir viva."""
    import analisador as A
    v = os.path.join(p, "_versoes.json")
    if not os.path.exists(v):
        return False
    try:
        d = json.load(open(v, encoding="utf-8"))
    except Exception:
        return False
    for chave, arq in (("extracao", "analise.py"), ("extrator", "analise_prompt.md"),
                       ("extrator_meta", "analise_meta_prompt.md")):
        if chave in d:
            d[chave] = f"{arq}@{A.hash_prompt(arq)}"
    json.dump(d, open(v, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return True


def main():
    executar = "--executar" in sys.argv
    if not os.path.isdir(RETIDOS):
        print(f"⛔ não achei {RETIDOS}")
        return 1

    sobem, iguais, caem, sem_tipo = [], 0, [], []
    for f in sorted(os.listdir(RETIDOS)):
        if not f.lower().endswith(".pdf"):
            continue
        base = os.path.splitext(f)[0]
        p = pacote(base)
        if not p:
            continue
        velha = nota_antiga(p)
        nova, tipo = recalcular(p)
        if velha is None or nova is None:
            continue
        if nova > velha:
            destino = PASTA_DO_TIPO.get(str(tipo).lower())
            if not destino:
                sem_tipo.append((f, tipo))
            elif nova >= PISO:
                sobem.append((velha, nova, f, p, destino))
            else:
                iguais += 1          # subiu, mas continua abaixo da porta: fica retido
        elif nova < velha:
            caem.append((velha, nova, f))
        else:
            iguais += 1

    print("═" * 80)
    print(f" REAVALIAR · o silêncio deixou de ser condenação" +
          ("" if executar else "   ·   E N S A I O"))
    print("═" * 80)
    print(f"\n   SOBEM e passam da porta (≥{PISO}): {len(sobem)}")
    for v, n, f, _p, d in sorted(sobem, key=lambda x: -x[1])[:20]:
        print(f"      {v} → {n}   [{d[:18]:<18}] {f[:52]}")
    if len(sobem) > 20:
        print(f"      … e mais {len(sobem)-20}")
    print(f"\n   sem mudança (ou ainda abaixo da porta): {iguais}")
    if caem:
        print(f"\n   ⚠️  CAEM DE NOTA: {len(caem)} — confira ANTES de executar")
        for v, n, f in caem[:10]:
            print(f"      {v} → {n}   {f[:60]}")
    if sem_tipo:
        print(f"\n   ⚠️  {len(sem_tipo)} subiram mas sem tipo reconhecível — não movo (LEI 8)")
        for f, t in sem_tipo[:5]:
            print(f"      tipo={t!r}  {f[:56]}")

    if not executar:
        print("\n" + "─" * 80)
        print("   ENSAIO — nada foi tocado. Para valer:")
        print("     python3 scripts/reavaliar_coleta_22ago.py --executar")
        return 0

    # ── 1) os que sobem: apaga o derivado velho, devolve o PDF à pasta de TIPO ──
    movidos = 0
    for _v, _n, f, p, destino in sobem:
        for suf in DERIVADOS:
            for alvo in glob.glob(os.path.join(p, "*" + suf)):
                os.remove(alvo)
        ok = os.path.join(p, "_OK")
        if os.path.exists(ok):
            os.remove(ok)                    # sem `_OK` o analisador refaz as peças
        origem = os.path.join(RETIDOS, f)
        alvo = os.path.join(CLASSIFICADOS, destino, f)
        if not os.path.exists(origem):
            continue
        if os.path.exists(alvo):
            print(f"   ⚠️  já existe em {destino}, NÃO mexi: {f[:50]}")
            continue
        os.makedirs(os.path.dirname(alvo), exist_ok=True)
        shutil.move(origem, alvo)
        movidos += 1

    # ── 2) TODO pacote do disco precisa do re-carimbo, senão a terra arrasa 942 ──
    n_carimbo = 0
    for p in (glob.glob(os.path.join(RAIZ, "outputs", "STAGING", "*")) +
              glob.glob(os.path.join(RAIZ, "outputs", "ARQUIVO", "*", "*"))):
        if os.path.isdir(p) and recarimbar_extracao(p):
            n_carimbo += 1

    print("\n" + "─" * 80)
    print(f"   ✔ {movidos} PDF(s) de volta à fila, com os derivados velhos apagados")
    print(f"   ✔ _versoes.json re-carimbado em {n_carimbo} pacote(s) — a extração NÃO será")
    print(f"     refeita, e você não paga de novo pelos fatos que já estão no disco")
    print(f"\n   PRÓXIMO PASSO: CHAVE 2. Ela refaz perícia, ACRI, visual e áudio com a nota")
    print(f"   NOVA e publica. A extração é reaproveitada.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
