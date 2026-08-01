"""
teste_motor.py — a PROVA do motor de rigor (01/Ago/2026).

POR QUE: a nota é o coração do CardioDaily e nunca tinha sido testada. Em 01/Ago, medindo o motor
pela primeira vez, apareceu que FORA de 'intervencao' ele ignorava o desenho — coorte, transversal,
série de casos e PRÉ-CLÍNICO devolviam todos 8. Era a causa do "padrão de nota 8".

VANTAGEM DESTE TESTE: o motor é uma FUNÇÃO PURA. Não chama LLM, não chama rede, não chama banco.
Logo ele pode ser testado EXAUSTIVAMENTE, de graça, em menos de um segundo, quantas vezes quiser.
É o único pedaço do sistema em que "resolvido" não depende de ninguém rodar nada com dinheiro.

Uso:  python src/teste_motor.py
Saída: APROVADO (0 falhas) ou REPROVADO com a lista do que quebrou.
"""
import sys
import itertools

import notas_prototipo as N

DESENHOS = ["rct", "meta", "coorte", "registro", "observacional_ajustado", "transversal",
            "caso_controle", "antes_depois_sem_controle", "serie_de_casos",
            "pre_clinico", "nao_classificavel"]
PERGUNTAS = ["intervencao", "etiologia", "prognostico", "diagnostico"]

falhas = []


def checa(nome, condicao, detalhe=""):
    if not condicao:
        falhas.append(f"{nome}{(' — ' + detalhe) if detalhe else ''}")
    return condicao


def _bom(**kw):
    """Fatos 'bons' — o caso comum: estudo bem conduzido, sem delator nenhum."""
    base = dict(open_label=False, poder_ok=True, desfecho_duro=True, extrapolavel=True,
                desenho_apropriado=True, qualidade_entrada=True, follow_up_completo=True)
    base.update(kw)
    return base


# ══════════════ 1 · PRÉ-CLÍNICO SAI DA ESCALA (o bug do camundongo, 27/Jul) ══════════════
def teste_pre_clinico():
    for q in PERGUNTAS:
        r = N.score(_bom(pergunta=q, desenho="pre_clinico"))
        checa(f"pré-clínico/{q}: rota", r["rota"] == N.ROTA_FRONTEIRA, f"veio {r['rota']}")
        checa(f"pré-clínico/{q}: NAC", r["aplic"] == 0, f"veio {r['aplic']}")
        checa(f"pré-clínico/{q}: não publica", r["aplic"] < 6)
    # o caso REAL que quebrou: RND3-ACAT1-PDHA1, Circulation 27/Jul → dava 8
    r = N.score(_bom(pergunta="etiologia", desenho="pre_clinico"))
    checa("RND3 (camundongo) não recebe mais NAC 8", r["aplic"] != 8, f"veio {r['aplic']}")


def teste_nao_classificavel():
    for q in PERGUNTAS:
        r = N.score(_bom(pergunta=q, desenho="nao_classificavel"))
        checa(f"nao_classificavel/{q}: vai p/ humano", r["rota"] == N.ROTA_HUMANA)
        checa(f"nao_classificavel/{q}: não publica", r["aplic"] < 6)


# ══════════════ 2 · O DESENHO IMPORTA EM TODAS AS PERGUNTAS (o buraco de 01/Ago) ══════════════
def teste_desenho_importa():
    for q in PERGUNTAS:
        notas = {}
        for d in DESENHOS:
            if d in N.DESENHOS_FORA_DA_ESCALA:
                continue
            notas[d] = N.score(_bom(pergunta=q, desenho=d))["aplic"]
        checa(f"{q}: o desenho muda a nota", len(set(notas.values())) > 1,
              f"todos deram {sorted(set(notas.values()))} — o desenho está sendo ignorado")
        # hierarquia que não pode inverter, em NENHUMA pergunta
        checa(f"{q}: série de casos < coorte", notas["serie_de_casos"] < notas["coorte"],
              f"série={notas['serie_de_casos']} coorte={notas['coorte']}")
        checa(f"{q}: transversal ≤ coorte", notas["transversal"] <= notas["coorte"])
        checa(f"{q}: antes-depois < observacional ajustado",
              notas["antes_depois_sem_controle"] < notas["observacional_ajustado"])


def teste_tetos_da_lei_0():
    """Os exemplos escritos na LEI 0 do CLAUDE.md, um a um."""
    # "Registro prospectivo nacional N=190, sem randomização, sem controle → NAC máximo 6"
    r = N.score(_bom(pergunta="intervencao", desenho="registro"))
    checa("LEI 0: registro sem controle ≤ 6", r["aplic"] <= 6, f"veio {r['aplic']}")
    # "RCT com desfecho FEVE como primário → Nível B → NAC máximo 8" (open-label OU surrogate)
    r = N.score(_bom(pergunta="intervencao", desenho="rct", open_label=True))
    checa("LEI 0: RCT open-label ≤ 8", r["aplic"] <= 8, f"veio {r['aplic']}")
    # "Coorte com propensity score bem conduzida → Nível C → NAC máximo 7"
    r = N.score(_bom(pergunta="intervencao", desenho="observacional_ajustado"))
    checa("LEI 0: observacional ajustado ≤ 7", r["aplic"] <= 7, f"veio {r['aplic']}")
    # "Estudos observacionais estão EXCLUÍDOS de NAC ≥ 9"
    for d in ("coorte", "registro", "observacional_ajustado", "transversal", "caso_controle",
              "antes_depois_sem_controle", "serie_de_casos"):
        for q in PERGUNTAS:
            r = N.score(_bom(pergunta=q, desenho=d))
            checa(f"LEI 0: observacional ({d}/{q}) nunca ≥ 9", r["aplic"] < 9, f"veio {r['aplic']}")
    # "RCT MORTALIDADE bem conduzido → Nível A → pode ser 10"
    r = N.score(_bom(pergunta="intervencao", desenho="rct", efeito_grande=True))
    checa("LEI 0: RCT duplo-cego com efeito grande PODE chegar a 10", r["aplic"] == 10,
          f"veio {r['aplic']}")


def teste_teto_estatistico():
    """CLAUDE.md: 'se nota_trabalho_estatistico < 8 → aplicabilidade NÃO PODE ultrapassar 7'."""
    import random
    random.seed(7)
    for _ in range(3000):
        a = dict(pergunta=random.choice(PERGUNTAS),
                 desenho=random.choice([d for d in DESENHOS if d not in N.DESENHOS_FORA_DA_ESCALA]))
        for k in ("open_label", "poder_ok", "desfecho_duro", "extrapolavel", "retrospectivo",
                  "efeito_grande", "desenho_apropriado", "qualidade_entrada", "follow_up_completo",
                  "itt_falso", "conclusao_nao_bate_desenho", "dicotomizou_continuo",
                  "contaminacao_incluidos", "i2_alto_sem_investigar"):
            a[k] = random.random() < .5
        r = N.score(a)
        if r["trabalho"] < 8 and not checa("teto estatístico: rigor<8 ⇒ NAC≤7", r["aplic"] <= 7,
                                           f"rigor={r['trabalho']} NAC={r['aplic']} {a}"):
            return
        if not checa("NAC nunca excede o rigor", r["aplic"] <= r["trabalho"]):
            return


def teste_rigor_conhece_o_desenho():
    """01/Ago: `nota_estatistica` partia de 9 fixo — série de casos recebia 'Rigor 9/10', e esse
    número ia DENTRO do contexto do redator ('use estes números'). O rigor não pode passar do que
    o desenho permite medir."""
    for q in PERGUNTAS:
        rig = {}
        for d in DESENHOS:
            if d in N.DESENHOS_FORA_DA_ESCALA:
                continue
            rig[d] = N.score(_bom(pergunta=q, desenho=d, efeito_grande=True))["trabalho"]
        checa(f"{q}: o rigor muda com o desenho", len(set(rig.values())) > 1,
              f"todos deram {sorted(set(rig.values()))}")
        checa(f"{q}: série de casos nunca tem rigor ≥8", rig["serie_de_casos"] < 8,
              f"veio {rig['serie_de_casos']}")
        checa(f"{q}: antes-depois nunca tem rigor ≥8", rig["antes_depois_sem_controle"] < 8)
        checa(f"{q}: transversal < coorte", rig["transversal"] < rig["coorte"])
        checa(f"{q}: só RCT pode chegar a 10",
              all(v < 10 for d, v in rig.items() if d != "rct"), f"{rig}")
    # o piso 8 do Framingham TEM que sobreviver ao teto (foi o que quebrou na 1ª tentativa)
    r = N.score(_bom(pergunta="etiologia", desenho="coorte"))
    checa("Framingham: coorte prospectiva impecável mantém rigor 8", r["trabalho"] == 8,
          f"veio {r['trabalho']}")
    # e os delatores continuam descendo A PARTIR do teto, não sendo apagados por ele
    r = N.score(_bom(pergunta="etiologia", desenho="coorte", qualidade_entrada=False))
    checa("garbage-in ainda derruba a coorte", r["trabalho"] <= 5, f"veio {r['trabalho']}")


# ══════════════ 3 · FALHAS FATAIS REPROVAM (não descontam) ══════════════
def teste_falhas_fatais():
    for f in N.FALHAS_FATAIS:
        r = N.score(_bom(pergunta="intervencao", desenho="rct", efeito_grande=True, falhas_fatais=[f]))
        checa(f"{f} derruba o melhor RCT possível para ≤4", r["aplic"] <= N.TETO_FALHA_FATAL,
              f"veio {r['aplic']}")
        checa(f"{f} aparece nas flags", any(f in x for x in r["flags"]))
    # os limiares NUMÉRICOS do NHLBI valem sozinhos, sem o modelo precisar rotular
    casos = [
        ("dropout diferencial 15pp → F1", {"dropout_diferencial_pp": 15}, "F1"),
        ("dropout diferencial 14,9pp NÃO é fatal", {"dropout_diferencial_pp": 14.9}, None),
        ("perda de seguimento 21% → F3", {"perda_seguimento_pct": 21}, "F3"),
        ("perda de seguimento 20% NÃO é fatal", {"perda_seguimento_pct": 20}, None),
        ("participação 49% → F4", {"participacao_elegiveis_pct": 49}, "F4"),
        ("participação 50% NÃO é fatal", {"participacao_elegiveis_pct": 50}, None),
        ("randomização não-aleatória → F2", {"randomizacao_adequada": False}, "F2"),
        ("randomização NÃO REPORTADA (null) não acusa", {"randomizacao_adequada": None}, None),
        ("desfecho não pré-especificado → F8", {"desfechos_prespecificados": False}, "F8"),
    ]
    for nome, nhlbi, esperado in casos:
        r = N.score(_bom(pergunta="intervencao", desenho="rct", qualidade_nhlbi=nhlbi))
        if esperado:
            checa(nome, esperado in r["falhas_fatais"], f"achou {r['falhas_fatais']}")
        else:
            checa(nome, not r["falhas_fatais"], f"acusou {r['falhas_fatais']} indevidamente")


def teste_mcid():
    """01/Ago: a relevancia_clinica era extraída (paga em todo artigo) e JOGADA FORA.
    Significância estatística não é relevância clínica."""
    melhor = dict(pergunta="intervencao", desenho="rct", open_label=False, poder_ok=True,
                  desfecho_duro=True, efeito_grande=True, extrapolavel=True)
    checa("sem relevancia_clinica: nada muda", N.score(dict(melhor))["aplic"] == 10)
    for classe, teto in N.TETO_MCID.items():
        a = dict(melhor, relevancia_clinica={"classificacao": classe})
        r = N.score(a)
        checa(f"MCID '{classe}' capa em {teto}", r["aplic"] <= teto, f"veio {r['aplic']}")
        checa(f"MCID '{classe}' aparece nas flags", any("relevância clínica" in f for f in r["flags"]))
    for classe in ("robusto", "provavel", "nao_avaliavel"):
        a = dict(melhor, relevancia_clinica={"classificacao": classe})
        checa(f"MCID '{classe}' NÃO capa", N.score(a)["aplic"] == 10, f"veio {N.score(a)['aplic']}")
    # o teto do MCID não pode SUBIR nota nenhuma
    a = dict(pergunta="intervencao", desenho="serie_de_casos", extrapolavel=True,
             relevancia_clinica={"classificacao": "robusto"})
    checa("MCID nunca INFLA (série de casos robusta continua ≤5)", N.score(a)["aplic"] <= 5)


def teste_nhlbi_contavel():
    """A nota de rigor passa a ser mostrável: 'cumpriu 9 de 14 critérios'. ESCOLHA REGISTRADA:
    a contagem só BAIXA, nunca sobe — falhar critério prova fragilidade; cumprir não prova excelência."""
    melhor = dict(pergunta="intervencao", desenho="rct", open_label=False, poder_ok=True,
                  desfecho_duro=True, efeito_grande=True, extrapolavel=True)
    crit = N._CRITERIOS_NHLBI["controlled_intervention"]

    # (a) tudo cumprido → não capa
    tudo = {"instrumento": "controlled_intervention", **{c: True for c in crit}}
    r = N.score(dict(melhor, qualidade_nhlbi=tudo))
    checa("NHLBI 100% cumprido não derruba o melhor RCT", r["aplic"] == 10, f"veio {r['aplic']}")
    checa("NHLBI conta os cumpridos", r["nhlbi"]["cumpre"] == len(crit))

    # (b) metade falha → teto 6 (faixa 40–59%)
    metade = {"instrumento": "controlled_intervention"}
    for i, c in enumerate(crit):
        metade[c] = (i % 2 == 0)
    r = N.score(dict(melhor, qualidade_nhlbi=metade))
    checa("NHLBI ~50% cumprido → rigor ≤6", r["trabalho"] <= 6, f"veio {r['trabalho']}")
    checa("NHLBI lista os critérios que falharam", len(r["nhlbi"]["criterios_falhos"]) > 0)
    checa("NHLBI aparece nas flags", any("NHLBI" in f for f in r["flags"]))

    # (c) dado insuficiente NÃO pode capar (senão todo artigo sem NHLBI seria punido)
    pouco = {"instrumento": "controlled_intervention", crit[0]: True, crit[1]: False}
    r = N.score(dict(melhor, qualidade_nhlbi=pouco))
    checa("NHLBI com poucos critérios respondidos não capa", r["aplic"] == 10, f"veio {r['aplic']}")

    # (d) sem bloco NHLBI nenhum → comportamento anterior, intacto
    checa("sem NHLBI o motor não muda", N.score(dict(melhor))["aplic"] == 10)

    # (e) a contagem NUNCA sobe nota
    ruim = dict(pergunta="intervencao", desenho="serie_de_casos", extrapolavel=True,
                qualidade_nhlbi={"instrumento": "case_series",
                                 **{c: True for c in N._CRITERIOS_NHLBI["case_series"]}})
    checa("NHLBI perfeito não sobe série de casos", N.score(ruim)["aplic"] <= 5,
          f"veio {N.score(ruim)['aplic']}")


# ══════════════ 4 · REGRESSÃO: os 6 artigos do gabarito do Dr. Eduardo ══════════════
def teste_gabarito_dos_artigos():
    for nome, fatos in N.FIXTURES.items():
        a = dict(fatos)
        gab = a.pop("gabarito")
        calc = N.score(a)["aplic"]
        bate = (str(calc) == str(gab)) or (isinstance(gab, str) and "-" in gab
                                           and int(gab.split("-")[0]) <= calc <= int(gab.split("-")[1]))
        checa(f"gabarito {nome}", bate, f"esperado {gab}, veio {calc}")


# ══════════════ 5 · NÃO QUEBRAR A CORRENTE ══════════════
def teste_contrato_de_saida():
    """O analisador faz r['aplic'] >= 7 e >= 8. Se 'aplic' virar None, a corrente quebra."""
    for d in DESENHOS:
        r = N.score(_bom(pergunta="intervencao", desenho=d))
        checa(f"{d}: 'aplic' é comparável com número", isinstance(r["aplic"], int),
              f"veio {type(r['aplic']).__name__}")
        for chave in ("trabalho", "aplic", "muda_conduta", "flags", "rota"):
            checa(f"{d}: chave '{chave}' presente", chave in r)


if __name__ == "__main__":
    testes = [teste_pre_clinico, teste_nao_classificavel, teste_desenho_importa,
              teste_tetos_da_lei_0, teste_teto_estatistico, teste_rigor_conhece_o_desenho,
              teste_falhas_fatais, teste_mcid, teste_nhlbi_contavel,
              teste_gabarito_dos_artigos, teste_contrato_de_saida]
    print("\nTESTE DO MOTOR DE RIGOR · função pura · sem LLM, sem rede, sem banco\n" + "═" * 70)
    for t in testes:
        antes = len(falhas)
        t()
        n = len(falhas) - antes
        print(f"  {'❌' if n else '✅'} {t.__name__:28} {('%d falha(s)' % n) if n else 'ok'}")
    print("═" * 70)
    if falhas:
        print(f"REPROVADO · {len(falhas)} falha(s):")
        for f in falhas[:30]:
            print(f"   • {f}")
        if len(falhas) > 30:
            print(f"   … e mais {len(falhas) - 30}")
        sys.exit(1)
    print("APROVADO · o motor obedece a LEI 0, as falhas fatais e o gabarito dos 6 artigos.")
    sys.exit(0)
