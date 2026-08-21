"""
reavaliar_regua_19ago.py — devolver à fila os artigos que a régua velha reprovou.

═══════════════════════════ POR QUE ISTO EXISTE ═══════════════════════════

Em 19/Ago o Dr. Eduardo rodou os 100 artigos originais que mudaram a história da insuficiência
cardíaca. Saíram 65 publicados e 29 recusados. Palavras dele:

    "o meu sistema negou 29 dos artigos mais importantes da história da cardiologia."

A medição mostrou que a régua estava errada em quatro pontos (PARTE 18 do CADERNO). Corrigida,
**20 pacotes de todo o acervo passam a publicar e ZERO deixa de publicar**.

Este programa devolve esses artigos à fila. Ele NÃO reanalisa nada e NÃO fala com o Supabase:
só recalcula a nota a partir dos FATOS que já estão em disco, apaga o que ficou velho e move
o PDF de volta. Quem analisa e publica continua sendo a Chave 2 (LEI 5 — portão único).

═══════════════════ O CUSTO QUE ESTE PROGRAMA EXISTE PARA EVITAR ═══════════════════

O analisador tem a regra da **TERRA ARRASADA**: se o hash de qualquer prompt mudou, ele apaga
o pacote INTEIRO e re-extrai. É uma boa regra — nasceu em 04/Ago, quando o prompt da meta mudou
três vezes numa madrugada e um staging das 03h seria reaproveitado às 05h em silêncio.

Só que hoje eu mexi no `analise_prompt.md` e no `analise_meta_prompt.md`. Sem nenhuma cautela,
a próxima Chave 2 apagaria os **279 pacotes** e re-extrairia TUDO — a etapa mais cara da
corrente, paga de novo, por uma mudança que não invalida um único fato já extraído.

**Por que a mudança NÃO invalida:** ela é ADITIVA. Acrescentou duas palavras ao enum
(`dano_demonstrado`, `nao_inferioridade_demonstrada`) e um campo (`troca_desfecho_declarada`).
Nada do que já foi extraído mudou de significado — os fatos velhos apenas são mais
conservadores do que poderiam ser, e o motor já promove sozinho quando o método prova.

⚠️ **E ISTO É EXATAMENTE O QUE O COMENTÁRIO DA TERRA ARRASADA ADVERTE** — "reaproveitamento que
preserva o erro". Por isso a exceção é ESTREITA e declarada:
  · re-carimba SÓ os dois prompts de extração, SÓ porque a mudança é aditiva;
  · os artigos que REALMENTE precisam do vocabulário novo têm os fatos APAGADOS de propósito
    (lista `PRECISAM_REEXTRAIR`), e vão pagar extração de novo — como devem.
Se um dia a mudança do prompt não for aditiva, NÃO se usa este programa: deixa a terra arrasar.

Uso:
    python3 scripts/reavaliar_regua_19ago.py            # ENSAIO — não toca em nada
    python3 scripts/reavaliar_regua_19ago.py --executar
"""
import os
import sys
import json
import glob
import shutil
import argparse

_AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(_AQUI)
SRC = os.path.join(RAIZ, "src")
sys.path.insert(0, SRC)

STAGING = os.path.join(RAIZ, "outputs", "STAGING")
CLASSIFICADOS = os.path.join(RAIZ, "ARTIGOS", "CLASSIFICADOS")
RECUSADOS = os.path.join(CLASSIFICADOS, "_RECUSADOS")

PORTA_PUBLICACAO = 6          # LEI 10 · o mesmo número do portão

# Para onde volta o PDF, pelo tipo que o extrator registrou (LEI 8 — o tipo decide tudo).
PASTA_DO_TIPO = {
    "original": "ARTIGOS_ORIGINAIS",
    "meta": "META_ANALISES",
    "diretriz": "GUIDELINES",
    "revisao_narrativa": "REVISOES",
}

# Estes CINCO dependem de vocabulário que os fatos em disco não têm. Não adianta recalcular:
# o campo não existe. Os fatos são apagados de propósito para a Chave 2 extrair de novo.
#   · APPRAISE-2 → `dano_demonstrado` (sangramento HR 2,59 · ensaio interrompido por dano)
#   · SOLOIST-WHF e SCORED → `troca_desfecho_declarada` (patrocinador cortou a verba, dito no artigo)
#   · COMPANION e RESHAPE → idem F8
PRECISAM_REEXTRAIR = (
    "2011-08-The_New_England_journal_-Apixaban_with_antiplatelet",
    "2021-01-The_New_England_journal_-Sotagliflozin",
    "2024-11-The_New_England_journal_-Transcatheter_Valve_Repair",
    "NEJMoa032423",
    "PIIS0140673603138007",
)

# O que fica VELHO quando a nota muda. A perícia, o ACRI e o áudio CITAM a nota em prosa —
# um texto que diz "nota 5, não muda conduta" não pode acompanhar um artigo que agora tira 9.
# Os FATOS ficam: eles não mudaram, e são a parte cara.
DERIVADOS_DA_NOTA = ("_ACRI.txt", "_analise.md", "_analise.pdf", "_visual.png",
                     "_audio.mp3", "_roteiro_audio.txt", "_CANONICO.md", "_gancho.txt")


def nota_antiga(pasta):
    """A nota que está gravada no canônico do pacote (a que a régua velha deu)."""
    import re
    g = glob.glob(os.path.join(pasta, "*_CANONICO.md"))
    if not g:
        return None
    m = re.search(r"nota_aplicabilidade_clinica:\s*(\d+)", open(g[0], encoding="utf-8").read())
    return int(m.group(1)) if m else None


def recalcular(pasta):
    """(antes, agora, fatos) a partir do disco. ZERO chamada de LLM, zero rede."""
    import notas_prototipo as N
    fj = glob.glob(os.path.join(pasta, "*_fatos.json"))
    if not fj:
        return None, None, None
    try:
        fatos = json.load(open(fj[0], encoding="utf-8"))
        return nota_antiga(pasta), N.score(fatos)["aplic"], fatos
    except Exception:
        return None, None, None


def recarimbar_extracao(pasta):
    """Atualiza SÓ os hashes dos prompts de extração no `_versoes.json`.

    Assim a Chave 2 não vê "o extrator mudou" e não arrasa o pacote. Todos os OUTROS carimbos
    (redator, ACRI, áudio, gancho, motor) ficam intactos — se algum deles mudar de verdade, a
    terra arrasada continua funcionando como sempre.
    """
    import analisador as A
    v = os.path.join(pasta, "_versoes.json")
    if not os.path.exists(v):
        return False
    d = json.load(open(v, encoding="utf-8"))
    for chave, arq in (("extracao", "analise.py"),
                       ("extrator", "analise_prompt.md"),
                       ("extrator_meta", "analise_meta_prompt.md")):
        if chave in d:
            d[chave] = f"{arq}@{A.hash_prompt(arq)}"
    json.dump(d, open(v, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return True


def pdf_no_recusados(base):
    p = os.path.join(RECUSADOS, base + ".pdf")
    return p if os.path.exists(p) else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--executar", action="store_true",
                    help="sem isto, ENSAIO: mostra tudo e não toca em nada")
    ap.add_argument("--incluir-publicados", action="store_true",
                    help="também refaz os que JÁ foram publicados e mudaram de nota "
                         "(custa perícia + ACRI + áudio de novo em cada um)")
    a = ap.parse_args()
    seco = not a.executar

    print("═" * 78)
    print("REAVALIAÇÃO COM A RÉGUA DE 19/Ago — " +
          ("ENSAIO (nada é tocado)" if seco else "EXECUTANDO"))
    print("═" * 78)
    print("Recalcula a nota a partir dos FATOS em disco. Nenhuma chamada de LLM, "
          "nenhuma linha no Supabase.\n")

    subiram, cairam, iguais, sem_fatos = [], [], 0, []
    for pasta in sorted(glob.glob(os.path.join(STAGING, "*"))):
        if not os.path.isdir(pasta):
            continue
        base = os.path.basename(pasta)
        antes, agora, fatos = recalcular(pasta)
        if agora is None:
            sem_fatos.append(base); continue
        if antes is None or antes == agora:
            iguais += 1; continue
        (subiram if (antes < PORTA_PUBLICACAO <= agora) else
         cairam if (antes >= PORTA_PUBLICACAO > agora) else subiram
         ).append((base, antes, agora, fatos))

    # ⚠️ A TRAVA MAIS IMPORTANTE DESTE PROGRAMA. Se a régua nova tirar a porta de alguém,
    # eu quebrei algo — a LEI 10 não foi afrouxada, e nada devia DESCER. Para tudo.
    if cairam:
        print(f"⛔ {len(cairam)} artigo(s) DEIXARIAM de publicar. Isso não era para acontecer.")
        for b, x, y, _ in cairam:
            print(f"     {x} → {y}   {b[:60]}")
        print("   Nada foi tocado. Me mostre esta tela antes de seguir.")
        return 1

    print(f"pacotes com a mesma nota : {iguais}")
    print(f"pacotes que MUDARAM      : {len(subiram)}")
    if sem_fatos:
        print(f"pacotes sem fatos.json   : {len(sem_fatos)} (ignorados — não dá para recalcular)")
    print()

    # ═══ DOIS GRUPOS, E MISTURÁ-LOS SERIA UM BURACO ═══
    # A minha primeira versão deste programa apagava a perícia de TODOS os que mudaram de nota.
    # Só que uma parte deles JÁ FOI PUBLICADA e está em `_PUBLICADOS` — fora da fila. Apagar a
    # perícia deles deixaria o pacote órfão (sem perícia no disco) E o Supabase com a nota velha,
    # sem nada para reconstruir. Ficaria pior do que estava.
    #
    # Grupo A · o PDF está em `_RECUSADOS`  → volta para a fila, a Chave 2 refaz e publica.
    # Grupo B · JÁ PUBLICADO com nota nova  → não se toca sem ordem. A nota velha é
    #           CONSERVADORA (todas subiram), então o que está no ar não está errado — está
    #           subestimado. Trazer de volta custa perícia + ACRI + áudio de novo.
    #           Só com `--incluir-publicados`, e a decisão é do dono.
    grupo_a = [x for x in subiram if pdf_no_recusados(x[0])]
    grupo_b = [x for x in subiram if not pdf_no_recusados(x[0])]

    if grupo_b:
        print(f"⚠️  {len(grupo_b)} pacote(s) MUDARAM de nota mas NÃO estão em _RECUSADOS "
              f"(já publicados ou já na fila):")
        for b, x, y, _ in grupo_b:
            print(f"      {x} → {y}   {b[:58]}")
        print("    A nota que está no ar é CONSERVADORA — subestima, não erra. Não vou tocar")
        print("    sem sua ordem: use --incluir-publicados se quiser refazer (custa perícia,")
        print("    ACRI e áudio de novo em cada um).\n")
    if not a.incluir_publicados:
        subiram = grupo_a

    # ── duplicatas: o mesmo artigo analisado 2× e 3× (medido em 19/Ago: 5 análises, 2 artigos) ──
    import re as _re
    _sem_sufixo = {}
    for x in subiram:
        chave = _re.sub(r" \(\d+\)$", "", x[0])
        _sem_sufixo.setdefault(chave, []).append(x[0])
    _dups = {k: v for k, v in _sem_sufixo.items() if len(v) > 1}
    if _dups:
        print("⚠️  DUPLICATAS na fila (o mesmo PDF foi analisado e pago mais de uma vez):")
        for k, v in _dups.items():
            print(f"      {k[:50]} → {len(v)} cópias: {', '.join(x[len(k):] or '(original)' for x in v)}")
        print("    Vou devolver todas; apagar cópia é decisão sua e não custa nada agora.\n")

    volta_pra_fila = 0
    for base, antes, agora, fatos in subiram:
        pasta = os.path.join(STAGING, base)
        pdf = pdf_no_recusados(base)
        tipo = fatos.get("tipo_documento") or "original"
        destino = PASTA_DO_TIPO.get(tipo, "ARTIGOS_ORIGINAIS")
        reextrai = any(k in base for k in PRECISAM_REEXTRAIR)

        marca = "🔼" if agora >= PORTA_PUBLICACAO > antes else "  "
        print(f" {marca} {antes} → {agora}  {base[:52]}")
        print(f"      derivados velhos apagados (a perícia dizia nota {antes})"
              + ("  ·  🔁 FATOS TAMBÉM (precisa do vocabulário novo)" if reextrai else ""))
        if pdf:
            print(f"      PDF volta: _RECUSADOS → {destino}")
            volta_pra_fila += 1
        else:
            print("      (o PDF não está em _RECUSADOS — nada a mover)")

        if seco:
            continue

        for suf in DERIVADOS_DA_NOTA:
            f = os.path.join(pasta, base + suf)
            if os.path.exists(f):
                os.remove(f)
        for extra in ("_OK", "assets"):
            p = os.path.join(pasta, extra)
            if os.path.isdir(p):
                shutil.rmtree(p, ignore_errors=True)
            elif os.path.exists(p):
                os.remove(p)
        if reextrai:
            for f in glob.glob(os.path.join(pasta, "*_fatos.json")):
                os.remove(f)
        else:
            recarimbar_extracao(pasta)
        if pdf:
            alvo = os.path.join(CLASSIFICADOS, destino)
            os.makedirs(alvo, exist_ok=True)
            shutil.move(pdf, os.path.join(alvo, os.path.basename(pdf)))

    # ── os pacotes que NÃO mudaram de nota também precisam do re-carimbo ──
    # Senão a próxima Chave 2 arrasa os 250 restantes e re-extrai tudo, do nada.
    if not seco:
        n = 0
        for pasta in glob.glob(os.path.join(STAGING, "*")):
            if os.path.isdir(pasta) and recarimbar_extracao(pasta):
                n += 1
        print(f"\n   _versoes.json re-carimbado em {n} pacote(s) — a extração NÃO será refeita "
              f"à toa (a mudança do prompt foi aditiva).")

    print("\n" + "═" * 78)
    if seco:
        print("ENSAIO — nada foi tocado. Para valer:")
        print("   python3 scripts/reavaliar_regua_19ago.py --executar")
    else:
        print(f"PRONTO · {volta_pra_fila} PDF(s) de volta à fila · "
              f"{len(subiram)} pacote(s) com derivados limpos.")
        print("Agora rode a CHAVE 2. Ela vai refazer perícia/ACRI/áudio com a nota nova")
        print("e publicar. Os FATOS são reaproveitados — só os cinco da lista re-extraem.")
    print("═" * 78)
    return 0


if __name__ == "__main__":
    sys.exit(main())
