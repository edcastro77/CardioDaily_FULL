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


# ══════════════ 3b · MOTOR DA DIRETRIZ (AGREE) — 02/Ago/2026 ══════════════
def _diretriz(**kw):
    """Uma diretriz EXEMPLAR: método declarado, independência preservada, evidência forte."""
    a = dict(
        tipo_documento="diretriz", tipo_documento_norm="diretriz", aplicavel_brasil=True,
        recomendacoes=dict(sistema_graduacao="ACC/AHA", total=100,
                           n_classe_I=40, n_classe_IIa=30, n_classe_IIb=20, n_classe_III=10,
                           n_nivel_A=50, n_nivel_B=30, n_nivel_C=20, n_classe_I_nivel_C=4),
        agree=dict(busca_sistematica_declarada=True, criterios_selecao_evidencia=True, n_bases=4,
                   forcas_limitacoes_descritas=True, vinculo_recomendacao_evidencia=True,
                   metodo_formular_recomendacao=True, riscos_beneficios_considerados=True,
                   opcoes_apresentadas=True, revisao_externa=True, plano_atualizacao=True,
                   financiamento_declarado=True, conflitos_declarados=True,
                   politica_gestao_conflitos=True, pct_membros_com_conflito=20),
    )
    for k, v in kw.items():
        if k in ("recomendacoes", "agree"):
            a[k] = {} if v is None else {**a[k], **v}   # None = APAGA o bloco (mesclar {} não apaga nada)
        else:
            a[k] = v
    return a


def teste_diretriz_nao_cai_no_motor_errado():
    """LEI 8: se o classificador diz DIRETRIZ, é o motor da diretriz — mesmo que o extrator tenha
    devolvido desenho='nao_classificavel'. Era esse o buraco do laudo da Nature Reviews."""
    r = N.score(_diretriz())
    checa("diretriz usa o motor DIRETRIZ", r["motor"] == "DIRETRIZ", f"veio {r['motor']}")
    r = N.score(_diretriz(desenho="nao_classificavel"))
    checa("tipo do classificador manda sobre o desenho do extrator",
          r["motor"] == "DIRETRIZ" and r["rota"] == N.ROTA_CLINICA, f"veio {r['motor']}/{r['rota']}")
    checa("diretriz não é jogada em REVISAO_HUMANA pelo desenho", r["aplic"] > 0)
    # e o inverso: um artigo original NÃO pode cair no motor da diretriz
    r = N.score(_bom(pergunta="intervencao", desenho="rct"))
    checa("artigo original continua no motor ORIGINAL", r["motor"] == "ORIGINAL")


def teste_diretriz_exemplar():
    r = N.score(_diretriz())
    checa("diretriz exemplar: rigor alto", r["trabalho"] >= 9, f"veio {r['trabalho']}")
    checa("diretriz exemplar: 20% nível C não capa", r["teto_nivel_c"] == 10,
          f"veio {r['teto_nivel_c']}")
    checa("diretriz exemplar: aplicabilidade 10", r["aplic"] == 10, f"veio {r['aplic']}")
    checa("diretriz exemplar: muda conduta", r["muda_conduta"] == "SIM")


def teste_diretriz_nivel_c():
    """A pergunta-assinatura: quanto disto é opinião de especialista com cara de evidência?"""
    for nc, teto in ((20, 10), (35, 8), (60, 7), (85, 6)):
        rec = dict(n_nivel_A=(100 - nc) // 2, n_nivel_B=100 - nc - (100 - nc) // 2, n_nivel_C=nc)
        r = N.score(_diretriz(recomendacoes=rec))
        checa(f"{nc}% nível C → teto {teto}", r["teto_nivel_c"] == teto, f"veio {r['teto_nivel_c']}")
        checa(f"{nc}% nível C: aplicabilidade respeita o teto", r["aplic"] <= teto,
              f"veio {r['aplic']}")
    # monotônica: mais opinião nunca pode dar nota MAIOR
    notas = [N.score(_diretriz(recomendacoes=dict(n_nivel_A=0, n_nivel_B=100 - nc, n_nivel_C=nc)))["aplic"]
             for nc in range(0, 101, 5)]
    checa("teto do nível C é monotônico (mais opinião nunca sobe a nota)",
          all(x >= y for x, y in zip(notas, notas[1:])), f"{notas}")
    # não contou nível → NÃO capa (senão todo documento silencioso seria punido)
    r = N.score(_diretriz(recomendacoes=dict(n_nivel_A=None, n_nivel_B=None, n_nivel_C=None)))
    checa("nível não contabilizado não capa", r["teto_nivel_c"] == 10, f"veio {r['teto_nivel_c']}")
    checa("e o silêncio é REGISTRADO nas flags",
          any("não contabilizado" in f for f in r["flags"]))


def teste_diretriz_classe_I_em_nivel_C():
    """Ordem forte sobre evidência fraca — teto próprio de 7, aprovado em 02/Ago."""
    r = N.score(_diretriz(recomendacoes=dict(n_classe_I=40, n_classe_I_nivel_C=24)))   # 60%
    checa("60% das Classe I em nível C → teto 7", r["teto_classe_i_em_c"] == 7,
          f"veio {r['teto_classe_i_em_c']}")
    checa("e a aplicabilidade cai para 7", r["aplic"] == 7, f"veio {r['aplic']}")
    checa("a razão aparece nas flags", any("Classe I" in f for f in r["flags"]))
    r = N.score(_diretriz(recomendacoes=dict(n_classe_I=40, n_classe_I_nivel_C=19)))   # 47,5%
    checa("47% das Classe I em nível C NÃO capa", r["teto_classe_i_em_c"] == 10,
          f"veio {r['teto_classe_i_em_c']}")
    # ESCOLHA REGISTRADA: não pode punir duas vezes — Classe I em C NÃO derruba o rigor também,
    # senão o teto 7 que o Dr. Eduardo aprovou viraria letra morta.
    rig_com = N.score(_diretriz(recomendacoes=dict(n_classe_I=40, n_classe_I_nivel_C=40)))["trabalho"]
    rig_sem = N.score(_diretriz())["trabalho"]
    checa("Classe I em C não desconta no RIGOR (só na aplicabilidade)", rig_com == rig_sem,
          f"rigor com={rig_com} sem={rig_sem}")


def teste_diretriz_tipo_documento():
    r = N.score(_diretriz(tipo_documento_norm="scientific_statement"))
    checa("scientific statement ≤ 7", r["aplic"] <= 7, f"veio {r['aplic']}")
    r = N.score(_diretriz(tipo_documento_norm="position_paper"))
    checa("position paper ≤ 7", r["aplic"] <= 7, f"veio {r['aplic']}")
    r = N.score(_diretriz(agree=dict(busca_sistematica_declarada=False)))
    checa("diretriz sem metodologia declarada ≤ 7", r["aplic"] <= 7, f"veio {r['aplic']}")


def teste_diretriz_falha_fatal_G1():
    """A ÚNICA falha fatal aprovada pelo Dr. Eduardo (02/Ago): normativa sem classe nem nível."""
    r = N.score(_diretriz(recomendacoes=dict(sistema_graduacao="nenhum")))
    checa("G1: diretriz normativa sem graduação → ≤4", r["aplic"] <= N.TETO_FALHA_FATAL,
          f"veio {r['aplic']}")
    checa("G1 aparece nas falhas fatais", "G1" in r["falhas_fatais"])
    checa("G1 aparece nas flags", any("G1" in f for f in r["flags"]))
    # scientific statement NÃO é normativo → G1 não se aplica (foi assim que ele aprovou)
    r = N.score(_diretriz(tipo_documento_norm="scientific_statement",
                          recomendacoes=dict(sistema_graduacao="nenhum")))
    checa("statement sem graduação NÃO é falha fatal", "G1" not in r["falhas_fatais"],
          f"acusou {r['falhas_fatais']}")
    # e as RECUSADAS não podem ter voltado como fatais
    for recusada in ("G2", "G3", "G4"):
        checa(f"{recusada} continua RECUSADA como falha fatal",
              recusada not in N.FALHAS_FATAIS_DIRETRIZ)


def teste_diretriz_recusadas_ainda_pesam():
    """G2/G3/G4 não reprovam — mas não somem: derrubam o RIGOR pelos domínios do AGREE."""
    base = N.score(_diretriz())["trabalho"]
    r = N.score(_diretriz(agree=dict(conflitos_declarados=False)))        # ex-G2
    checa("conflito não declarado derruba o rigor", r["trabalho"] < base,
          f"base={base} veio={r['trabalho']}")
    r = N.score(_diretriz(agree=dict(revisao_externa=False)))             # parte da ex-G4
    checa("sem revisão externa derruba o rigor", r["trabalho"] < base)
    r = N.score(_diretriz(agree=dict(politica_gestao_conflitos=False,
                                     pct_membros_com_conflito=70)))       # ex-G3
    checa("painel com 70% de conflito e sem política derruba o rigor", r["trabalho"] < base)
    r = N.score(_diretriz(agree=dict(busca_sistematica_declarada=False,
                                     criterios_selecao_evidencia=False)))
    checa("sem busca declarada derruba o rigor", r["trabalho"] < base)


def teste_diretriz_brasil_e_silencio():
    r = N.score(_diretriz(aplicavel_brasil=False))
    checa("não executável no Brasil → teto 7", r["aplic"] <= 7, f"veio {r['aplic']}")
    checa("e a razão fica registrada", any("Brasil" in f for f in r["flags"]))
    # AGREE em branco: NÃO inventa nota — retém (LEI 8: na dúvida, revisão humana)
    r = N.score(_diretriz(agree=None))
    checa("AGREE vazio → rigor de prudência", r["trabalho"] == N.RIGOR_DIRETRIZ_SEM_FATOS,
          f"veio {r['trabalho']}")
    checa("AGREE vazio → documento RETIDO (não publica)", r["aplic"] < 6, f"veio {r['aplic']}")
    checa("AGREE vazio → diz que não avaliou", any("não avaliável" in f for f in r["flags"]))
    # idade é FATO, nunca teto (o Dr. Eduardo não aprovou teto por idade)
    nova, velha = N.score(_diretriz(idade_anos=1)), N.score(_diretriz(idade_anos=9))
    checa("idade NÃO capa a nota", nova["aplic"] == velha["aplic"])
    checa("mas a idade é registrada", any("anos" in f for f in velha["flags"]))


def teste_diretriz_contrato():
    """A corrente faz r['aplic'] >= 6/7/8 e lê 'flags'. Nada pode vir None."""
    for a in (_diretriz(), _diretriz(agree=None), _diretriz(recomendacoes=dict(sistema_graduacao="nenhum"))):
        r = N.score(a)
        for chave in ("trabalho", "aplic", "muda_conduta", "flags", "rota", "motor", "falhas_fatais"):
            checa(f"diretriz: chave '{chave}' presente", chave in r)
        checa("diretriz: 'aplic' é int", isinstance(r["aplic"], int), f"veio {type(r['aplic']).__name__}")
        checa("diretriz: 'trabalho' é int", isinstance(r["trabalho"], int))
        checa("diretriz: NAC nunca excede o rigor", r["aplic"] <= r["trabalho"],
              f"NAC={r['aplic']} rigor={r['trabalho']}")


# ══════════════ 3c · MOTOR DA REVISÃO NARRATIVA — 02/Ago/2026 ══════════════
def _revisao(**kw):
    """A revisão do EXEMPLO do Dr. Eduardo: silenciadores genéticos — eficazes, R$ 750 mil no
    Brasil, fáceis de usar, baixíssimos efeitos adversos, e o julgamento da implementação."""
    q = dict(metodo_busca_declarado=True, escopo_declarado=True, n_referencias=90,
             ano_referencia_mais_recente=2025, pct_referencias_ultimos_5_anos=65,
             afirmacoes_sem_citacao="raras", atribui_nivel_evidencia=True,
             apresenta_contra_evidencia=True, tom_promocional=False,
             conflitos_declarados=True, financiamento_industria=False, limitacoes_reconhecidas=True,
             n_condutas_acionaveis=14, traz_valores_corte_ou_doses=True, traz_magnitude_efeito=True,
             traz_custo_acesso=True, traz_seguranca=True, traz_em_quem_nao_usar=True)
    q.update(kw.pop("qualidade_revisao", None) or {})
    a = dict(tipo_documento="revisao_narrativa", qualidade_revisao=({} if kw.pop("vazio", False) else q))
    a.update(kw)
    return a


def teste_revisao_pode_chegar_a_10():
    """A CORREÇÃO do Dr. Eduardo em 02/Ago: 'PODE CHEGAR A 10 — a revisão não tem graduação
    estatística, ela se baseia em quanto ela me ajuda na prática'. Eu ia dar teto 6. Errado."""
    r = N.score(_revisao())
    checa("revisão usa o motor REVISAO", r["motor"] == "REVISAO", f"veio {r['motor']}")
    checa("revisão exemplar CHEGA a 10", r["aplic"] == 10, f"veio {r['aplic']}")
    checa("revisão exemplar: rigor alto", r["trabalho"] >= 9, f"veio {r['trabalho']}")
    checa("revisão exemplar: muda conduta", r["muda_conduta"] == "SIM")
    checa("NÃO existe teto por categoria", r["teto_desenho"] == 10, f"veio {r['teto_desenho']}")
    # e a rota não pode jogá-la fora, mesmo com desenho não classificável
    r = N.score(_revisao(desenho="nao_classificavel"))
    checa("tipo manda sobre o desenho", r["motor"] == "REVISAO" and r["aplic"] == 10,
          f"{r['motor']}/{r['aplic']}")


def teste_revisao_fala_por_cima():
    """'SE FALA POR CIMA, ELA TEM NOTA BAIXA' — a superficialidade é medida pela CONTAGEM."""
    rasa = N.score(_revisao(qualidade_revisao=dict(
        n_condutas_acionaveis=0, traz_valores_corte_ou_doses=False, traz_magnitude_efeito=False,
        traz_custo_acesso=False, traz_seguranca=False, traz_em_quem_nao_usar=False)))
    checa("revisão que fala por cima tem nota baixa", rasa["aplic"] <= 4, f"veio {rasa['aplic']}")
    checa("e o motor DIZ que ela fala por cima", "por cima" in rasa["faixa_revisao"],
          f"veio {rasa['faixa_revisao']}")
    # o rigor pode continuar BOM numa revisão rasa — são eixos diferentes, e isso é o ponto
    checa("rigor e utilidade são eixos independentes", rasa["trabalho"] >= 8,
          f"rigor veio {rasa['trabalho']}")
    # monotônica: mais conduta acionável nunca pode dar nota MENOR
    notas = [N.score(_revisao(qualidade_revisao=dict(n_condutas_acionaveis=n)))["utilidade"]
             for n in range(0, 21)]
    checa("mais conduta acionável nunca baixa a utilidade",
          all(x <= y for x, y in zip(notas, notas[1:])), f"{notas}")


def teste_revisao_custo_brasil():
    """'CUSTAM 750 MIL REAIS NO BRASIL' — o dado que ele nomeou como o que faz a revisão valer."""
    com = N.score(_revisao())["utilidade"]
    sem = N.score(_revisao(qualidade_revisao=dict(traz_custo_acesso=False)))["utilidade"]
    checa("custo/acesso no Brasil pesa de verdade", com - sem >= 1, f"com={com} sem={sem}")
    for campo in ("traz_magnitude_efeito", "traz_seguranca", "traz_em_quem_nao_usar"):
        s = N.score(_revisao(qualidade_revisao={campo: False}))["utilidade"]
        checa(f"'{campo}' ausente derruba a utilidade", s < com, f"com={com} sem={s}")


def teste_revisao_vies_de_selecao():
    """'o principal viés é a SELEÇÃO INVISÍVEL' — palavras dele, peso 0,30."""
    base = N.score(_revisao())["trabalho"]
    r = N.score(_revisao(qualidade_revisao=dict(afirmacoes_sem_citacao="frequentes")))
    checa("afirmações sem citação derrubam o rigor", r["trabalho"] < base - 1,
          f"base={base} veio={r['trabalho']}")
    r = N.score(_revisao(qualidade_revisao=dict(tom_promocional=True, financiamento_industria=True)))
    checa("revisão promocional com dinheiro de indústria derruba o rigor", r["trabalho"] <= base - 2,
          f"base={base} veio={r['trabalho']}")
    # A TRAVA CENTRAL: revisão riquíssima porém enviesada NÃO chega a 10 — o rigor segura.
    checa("revisão útil mas enviesada não vira 10", r["aplic"] < 10, f"veio {r['aplic']}")
    checa("e a utilidade dela continua alta (os eixos não se contaminam)", r["utilidade"] == 10,
          f"veio {r['utilidade']}")
    # o que ele RECUSOU como falha fatal continua vivo dentro do rigor
    checa("nenhuma falha fatal na revisão (decisão dele)", N.FALHAS_FATAIS_REVISAO == {})
    checa("revisão nunca acusa falha fatal", r["falhas_fatais"] == [])


def teste_revisao_atualidade():
    """Teto próprio, aprovado por ele: 'uma revisão de IC escrita antes dos SGLT2 ensina errado'."""
    for ano, teto in ((2025, 10), (2022, 10), (2021, 6), (2018, 5)):
        r = N.score(_revisao(qualidade_revisao=dict(ano_referencia_mais_recente=ano)))
        checa(f"referência de {ano} → teto {teto}", r["teto_atualidade"] == teto,
              f"veio {r['teto_atualidade']}")
        checa(f"referência de {ano}: a nota respeita o teto", r["aplic"] <= teto, f"veio {r['aplic']}")
    # monotônica
    notas = [N.score(_revisao(qualidade_revisao=dict(ano_referencia_mais_recente=y)))["aplic"]
             for y in range(2010, 2027)]
    checa("revisão mais antiga nunca tem nota maior",
          all(x <= y for x, y in zip(notas, notas[1:])), f"{notas}")
    # sem o dado, NÃO capa (não punir o silêncio do extrator)
    r = N.score(_revisao(qualidade_revisao=dict(ano_referencia_mais_recente=None,
                                                defasagem_anos=None)))
    checa("sem ano de referência não capa", r["teto_atualidade"] == 10, f"veio {r['teto_atualidade']}")


def teste_revisao_contrato_e_silencio():
    r = N.score(_revisao(vazio=True))
    checa("revisão sem fatos → nota de prudência", r["aplic"] == N.RIGOR_REVISAO_SEM_FATOS,
          f"veio {r['aplic']}")
    checa("revisão sem fatos → RETIDA (não publica)", r["aplic"] < 6)
    checa("revisão sem fatos → diz que não avaliou", any("não avaliável" in f for f in r["flags"]))
    for a in (_revisao(), _revisao(vazio=True),
              _revisao(qualidade_revisao=dict(n_condutas_acionaveis=0))):
        r = N.score(a)
        for chave in ("trabalho", "aplic", "muda_conduta", "flags", "rota", "motor", "falhas_fatais"):
            checa(f"revisão: chave '{chave}' presente", chave in r)
        checa("revisão: 'aplic' é int", isinstance(r["aplic"], int))
        checa("revisão: NAC nunca excede o rigor", r["aplic"] <= r["trabalho"],
              f"NAC={r['aplic']} rigor={r['trabalho']}")


def teste_os_quatro_motores_nao_se_misturam():
    """LEI 8: cada tipo, seu motor. Nenhum documento pode cair no motor do vizinho."""
    esperado = {"original": "ORIGINAL", "meta": "META", "diretriz": "DIRETRIZ",
                "revisao_narrativa": "REVISAO"}
    casos = {"original": _bom(pergunta="intervencao", desenho="rct"),
             "meta": _bom(pergunta="intervencao", desenho="meta",
                          qualidade_nhlbi={"pergunta_focada": True, "elegibilidade_predefinida": True,
                                           "busca_sistematica_abrangente": True}),
             "diretriz": _diretriz(), "revisao_narrativa": _revisao()}
    for tipo, fatos in casos.items():
        r = N.score(fatos)
        checa(f"{tipo} → motor {esperado[tipo]}", r["motor"] == esperado[tipo],
              f"veio {r['motor']}")
    # o campo `tipo_documento` (que o classificador vai gravar) manda sobre o `desenho` do extrator
    for tipo in ("diretriz", "revisao_narrativa"):
        r = N.score(dict(casos[tipo], tipo_documento=tipo, desenho="nao_classificavel"))
        checa(f"tipo_documento='{tipo}' manda sobre desenho='nao_classificavel'",
              r["motor"] == esperado[tipo], f"veio {r['motor']}")
    # MAS a escotilha do ARTIGO ORIGINAL continua valendo: se o extrator não soube dizer o desenho de
    # um ESTUDO, o motor NÃO chuta — vai para revisão humana. Não confundir com o caso acima: lá o
    # desenho é irrelevante (diretriz não tem desenho); aqui ele é a informação que faltou.
    r = N.score(dict(casos["original"], tipo_documento="original", desenho="nao_classificavel"))
    checa("artigo original sem desenho continua indo p/ revisão humana", r["rota"] == N.ROTA_HUMANA,
          f"veio {r['rota']}")
    checa("e a saída da rota traz 'motor' (contrato)", "motor" in r)
    # nenhum motor pode devolver uma chave que outro não devolva — o painel lê todos igual
    for tipo, fatos in casos.items():
        r = N.score(fatos)
        for chave in ("trabalho", "aplic", "muda_conduta", "rota", "motor", "falhas_fatais", "flags"):
            checa(f"{tipo}: contrato tem '{chave}'", chave in r)


# ══════════════ 3d · VEREDITO ABERTO — o redator não recebe mais o número nu (02/Ago) ══════════════
def teste_veredito_aberto():
    """MEDIDO em 02/Ago: a mesma revisão com veredito 6/10 e 9/10 produziu 86% de parágrafos
    diferentes, e o MESMO fato justificou as duas notas. O número nu era o volante da perícia.
    Agora o redator recebe os DOMÍNIOS MEDIDOS. Estas travas protegem esse bloco."""
    import re
    # a PRIMEIRA linha é contrato de máquina: `analisador.conferir_veredito` lê com estas regex
    RE_A, RE_R = re.compile(r"Nota\s+(\d{1,2})/10"), re.compile(r"Rigor\s+(\d{1,2})/10")
    casos = {
        "ORIGINAL": _bom(pergunta="intervencao", desenho="rct", efeito_grande=True),
        "META": _bom(pergunta="intervencao", desenho="meta",
                     qualidade_nhlbi={"pergunta_focada": True, "elegibilidade_predefinida": True,
                                      "busca_sistematica_abrangente": True, "i2_valor": 30},
                     qualidade_meta={"k_estudos": 12, "protocolo_registrado": True}),
        "DIRETRIZ": _diretriz(), "REVISAO": _revisao(),
    }
    for motor, fatos in casos.items():
        r = N.score(fatos)
        v = N.veredito_completo(r)
        primeira = v.split("\n")[0]
        ma, mr = RE_A.search(primeira), RE_R.search(primeira)
        checa(f"{motor}: 1ª linha tem 'Nota N/10'", bool(ma), f"veio {primeira!r}")
        checa(f"{motor}: 1ª linha tem 'Rigor N/10'", bool(mr), f"veio {primeira!r}")
        # a regex faz .search no bloco INTEIRO: o 1º match tem que ser a nota, não um domínio
        checa(f"{motor}: a regex do analisador pega a NOTA, não um domínio",
              int(RE_A.search(v).group(1)) == r["aplic"]
              and int(RE_R.search(v).group(1)) == r["trabalho"],
              f"regex leu {RE_A.search(v).group(1)}/{RE_R.search(v).group(1)}, "
              f"motor deu {r['aplic']}/{r['trabalho']}")
        checa(f"{motor}: o bloco diz de qual motor veio", motor in v)
        checa(f"{motor}: manda explicar a partir dos domínios",
              "não do número" in v or "nunca a partir" in v or "DESTES domínios" in v)
        checa(f"{motor}: o bloco é multilinha (tem a abertura)", v.count("\n") >= 3,
              f"veio {v.count(chr(10))} quebras")
    # cada motor mostra os SEUS domínios com peso
    for motor, chave, pesos in (("META", "dominios_meta", N.PESOS_META),
                                ("DIRETRIZ", "dominios_agree", N.PESOS_DIRETRIZ),
                                ("REVISAO", "dominios_revisao_rigor", N.PESOS_REVISAO_RIGOR)):
        r = N.score(casos[motor])
        v = N.veredito_completo(r)
        checa(f"{motor}: mostra os pesos", "peso" in v)
        for k in (r.get(chave) or {}):
            checa(f"{motor}: domínio '{k}' aparece com rótulo em português",
                  N._ROTULOS.get(k, k) in v, f"não achei '{N._ROTULOS.get(k, k)}'")
    # ORIGINAL: os delatores e os tetos continuam visíveis
    r = N.score(_bom(pergunta="intervencao", desenho="registro"))
    v = N.veredito_completo(r)
    checa("ORIGINAL: mostra os tetos que produziram a nota", "teto do desenho" in v)
    checa("ORIGINAL: mostra os delatores", "DELATORES" in v)
    # rota fora da escala: continua dizendo SEM NOTA (a trava do analisador depende disso)
    v = N.veredito_completo(N.score(_bom(pergunta="etiologia", desenho="pre_clinico")))
    checa("pré-clínico: veredito diz SEM NOTA", v.startswith("SEM NOTA"), f"veio {v[:60]!r}")
    checa("pré-clínico: NÃO traz 'Nota N/10' (senão a trava deixaria passar)",
          not RE_A.search(v), f"veio {v[:90]!r}")


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
              teste_diretriz_nao_cai_no_motor_errado, teste_diretriz_exemplar,
              teste_diretriz_nivel_c, teste_diretriz_classe_I_em_nivel_C,
              teste_diretriz_tipo_documento, teste_diretriz_falha_fatal_G1,
              teste_diretriz_recusadas_ainda_pesam, teste_diretriz_brasil_e_silencio,
              teste_diretriz_contrato,
              teste_revisao_pode_chegar_a_10, teste_revisao_fala_por_cima,
              teste_revisao_custo_brasil, teste_revisao_vies_de_selecao,
              teste_revisao_atualidade, teste_revisao_contrato_e_silencio,
              teste_os_quatro_motores_nao_se_misturam, teste_veredito_aberto,
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
