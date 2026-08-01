"""
notas_prototipo.py — PROTÓTIPO do bloco `notas` (laboratório, LEI DO CLONE).
Planta: PLANTA_BLOCO_NOTAS.md. Régua-chave:
    aplicabilidade = min(teto_desenho[por tipo de pergunta], teto_validade_externa, nota_estatistica)
O `notas` é DETERMINÍSTICO: recebe FATOS (o dado canônico que o bloco `analise` extrai) e aplica regras.
Aqui os fatos dos 6 artigos estão hard-coded como FIXTURES pra travar a regressão contra o gabarito do Dr. Eduardo.
"""

# ─────────────────────────── ROTAS FORA DA ESCALA CLÍNICA ───────────────────────────
# Decisão do Dr. Eduardo, 01/Ago/2026.
# Nenhum dos 6 instrumentos do NHLBI cobre estudo pré-clínico (animal / in vitro) — e isso não é
# lacuna dos instrumentos, é a resposta: PRÉ-CLÍNICO NÃO É ESTUDO CLÍNICO. Não há paciente, logo não
# há aplicabilidade clínica para pontuar. Dar nota de aplicabilidade a camundongo é ERRO DE CATEGORIA.
# Foi exatamente isso que produziu o NAC 8/10 no RND3-ACAT1-PDHA1 (Circulation, 27/Jul/2026) —
# reproduzido no motor em 01/Ago: pre_clinico + etiologia + coleta boa devolvia 8.
# 'nao_classificavel' é a escotilha do extrator: se ele não soube dizer o que é, o motor NÃO chuta.
ROTA_CLINICA = "CLINICA"
ROTA_FRONTEIRA = "FORA_DA_ESCALA_CLINICA"     # pré-clínico: publicável como ciência de fronteira, sem NAC
ROTA_HUMANA = "REVISAO_HUMANA"                # o extrator não soube: quem decide é o Dr. Eduardo

DESENHOS_FORA_DA_ESCALA = {"pre_clinico": ROTA_FRONTEIRA, "nao_classificavel": ROTA_HUMANA}


def rota(a):
    """Antes de qualquer nota: este artigo pertence à escala clínica?"""
    return DESENHOS_FORA_DA_ESCALA.get(a.get("desenho"), ROTA_CLINICA)


# ─────────────────────────── AS REGRAS ───────────────────────────

# TETO POR DESENHO — matriz aprovada pelo Dr. Eduardo em 01/Ago/2026, ancorada nos 6 instrumentos
# do NHLBI (docs/METODO_AVALIACAO_ESTUDOS.md) e coerente com a tabela A–E da LEI 0 (CLAUDE.md).
#
# O BURACO QUE ISTO FECHA (medido em 01/Ago): fora de 'intervencao' o motor IGNORAVA o desenho —
# coorte, transversal, série de casos e até pré-clínico devolviam TODOS 8. Era a causa real do
# "padrão de nota 8" que o Dr. Eduardo viu nas análises de segunda-feira.
_TETO_INTERVENCAO = {          # "funciona no meu paciente?" — exige controle e randomização
    "meta": 8,                 # meta de RCTs
    "observacional_ajustado": 7,   # nível C: controle + propensity/multivariada robusta
    "caso_controle": 6,
    "coorte": 6,               # nível D: sem randomização, sem adjudicação central
    "registro": 6,             # registro prospectivo SEM grupo controle
    "transversal": 5,          # nível E
    "antes_depois_sem_controle": 5,
    "serie_de_casos": 5,
}
_TETO_NAO_INTERVENCAO = {      # etiologia / prognóstico / diagnóstico
    "rct": 8,                  # análise secundária de RCT respondendo pergunta não-interventiva
    "meta": 8,
    "coorte": 8,               # só PROSPECTIVA e impecável chega a 8 (ver abaixo); retrospectiva cai p/ 7
    "observacional_ajustado": 7,
    "caso_controle": 7,        # NHLBI Case-Control: controles concorrentes, mesma população
    "registro": 7,
    "transversal": 6,          # não separa exposição de desfecho no tempo
    "antes_depois_sem_controle": 5,
    "serie_de_casos": 5,       # NHLBI Case Series: sem comparação, viés de seleção
}


def teto_desenho(a):
    """REGRA 0 — teto POR TIPO DE PERGUNTA × DESENHO."""
    q = a["pergunta"]
    d = a.get("desenho")
    if q == "intervencao":
        if d == "rct":
            # Nível B (teto 8): sem cegamento, OU poder limítrofe — MAS parada precoce por
            # benefício não conta como "poder ruim" (o benefício foi esmagador). US Carvedilol.
            if a.get("open_label") or (not a.get("poder_ok", True)
                                       and not a.get("parado_cedo_por_beneficio")):
                return 8
            return 10               # Nível A: RCT duro, cegado, poder ok (ou parado por benefício)
        return _TETO_INTERVENCAO.get(d, 6)
    # etiologia / prognostico / diagnostico: aquisição de dados impecável = PISO 8.
    # (Sem viés de desfecho: não damos 10 porque a história deu razão. Somos críticos com o método atual;
    #  a excelência da COLETA — codebook, lab calibrado, follow-up — é o que sustenta o 8.)
    teto = _TETO_NAO_INTERVENCAO.get(d, 6)
    # LEI 0 — RETROSPECTIVO NÃO PEGA O PISO 8. O piso 8 é do Framingham: coorte PROSPECTIVA, coleta
    # desenhada antes. Um estudo RETROSPECTIVO (análise secundária/post-hoc, acurácia sobre exames já
    # feitos) é observacional que a régua do CLAUDE.md capa em 7 (Nível C: controle + ajuste) — nunca 8.
    if a.get("retrospectivo"):
        teto = min(teto, 7)
    # o 8 do Framingham EXIGE a coleta impecável; sem ela, mesmo a coorte prospectiva não passa de 7
    if teto >= 8 and not (a.get("desenho_apropriado") and a.get("qualidade_entrada")
                          and a.get("follow_up_completo")):
        teto = 7
    return teto


# ─────────────────────────── FALHAS FATAIS (F1–F8) ───────────────────────────
# Decisão do Dr. Eduardo, 01/Ago/2026: falha fatal REPROVA, não desconta → teto 4.
# São as que os próprios instrumentos tratam como desqualificantes; o NHLBI usa a expressão
# literal "fatal flaw" para o dropout diferencial. Fonte: docs/METODO_AVALIACAO_ESTUDOS.md §4.
FALHAS_FATAIS = {
    "F1": "dropout diferencial ≥15 pp entre braços (NHLBI: 'fatal flaw')",
    "F2": "randomização não é ao acaso (alternância, data, prontuário)",
    "F3": "perda de seguimento >20% sem análise de sensibilidade",
    "F4": "participação <50% dos elegíveis",
    "F5": "meta sem heterogeneidade nem viés de publicação avaliados",
    "F6": "caso-controle com controles de população diferente",
    "F7": "série de casos não consecutiva",
    "F8": "desfecho trocado após o início (não pré-especificado)",
}
TETO_FALHA_FATAL = 4


def falhas_fatais(a):
    """Devolve a lista de falhas fatais presentes. Aceita as duas fontes:
    a lista 'falhas_fatais' que o extrator devolve E os limiares numéricos do bloco NHLBI —
    porque limiar medido não depende do humor do modelo."""
    achadas = [f for f in (a.get("falhas_fatais") or []) if f in FALHAS_FATAIS]
    n = a.get("qualidade_nhlbi") or {}

    def _num(chave):
        v = n.get(chave)
        return v if isinstance(v, (int, float)) else None

    dd, perda, part = _num("dropout_diferencial_pp"), _num("perda_seguimento_pct"), _num("participacao_elegiveis_pct")
    if dd is not None and dd >= 15:
        achadas.append("F1")
    if n.get("randomizacao_adequada") is False:
        achadas.append("F2")
    if perda is not None and perda > 20:
        achadas.append("F3")
    if part is not None and part < 50:
        achadas.append("F4")
    if a.get("desenho") == "meta" and n.get("heterogeneidade_avaliada") is False \
            and n.get("vies_publicacao_avaliado") is False:
        achadas.append("F5")
    if n.get("controles_mesma_populacao") is False:
        achadas.append("F6")
    if n.get("casos_consecutivos") is False:
        achadas.append("F7")
    if n.get("desfechos_prespecificados") is False:
        achadas.append("F8")
    return sorted(set(achadas))


# ─────────────────────── MCID — RELEVÂNCIA CLÍNICA COMO TETO ───────────────────────
# Decisão do Dr. Eduardo, 01/Ago/2026. Até hoje a `relevancia_clinica` era extraída (paga em TODO
# artigo) e JOGADA FORA pelo motor. Significância estatística não é relevância clínica: um p<0,001
# num efeito abaixo da diferença mínima clinicamente importante não muda conduta de ninguém.
TETO_MCID = {
    "significativo_mas_abaixo_do_mcid": 6,   # ← o teto que o Dr. Eduardo aprovou
    "nao_relevante": 6,                      # ← MESMO teto: é pelo menos tão ruim quanto o de cima.
                                             #   [ESCOLHA MINHA — deixar sem teto seria incoerente.
                                             #    Se quiser 5, é uma linha.]
    "incerto": 7,                            # [ESCOLHA MINHA] efeito de relevância duvidosa não
                                             #   deveria "mudar a prática amanhã" (≥8)
}


def teto_mcid(a):
    """REGRA 3 — o efeito é clinicamente relevante, não só estatisticamente significativo?"""
    rc = a.get("relevancia_clinica") or {}
    return TETO_MCID.get((rc.get("classificacao") or "").strip().lower(), 10)


# ──────────────── NHLBI CONTÁVEL — o rigor vira auditável, critério a critério ────────────────
# Decisão do Dr. Eduardo, 01/Ago/2026 (proposta §5.2 do METODO_AVALIACAO_ESTUDOS.md).
# A nota de rigor deixa de ser só uma escada de condições e passa a poder ser MOSTRADA: "este estudo
# cumpriu 9 dos 14 critérios do NHLBI para ensaio controlado; falhou em alocação sigilosa, cegamento
# do avaliador e ITT". É o que dá autoridade — e é o que o concorrente não tem.
#
# ESCOLHA MINHA, explícita para o Dr. Eduardo desfazer: a contagem só pode BAIXAR o rigor, nunca
# SUBIR. Motivo: cumprir critério de relato não prova que o estudo é bom, mas falhar prova que é
# frágil. Assim a contagem entra como TETO e não pode inflar nota nenhuma — nem quebrar o gabarito.
_CRITERIOS_NHLBI = {
    "controlled_intervention": ["randomizacao_adequada", "alocacao_sigilosa", "participantes_cegados",
                                "avaliadores_desfecho_cegados", "grupos_similares_basal", "adesao_alta",
                                "cointervencoes_similares", "poder_80_declarado",
                                "desfechos_prespecificados", "itt_verdadeiro",
                                "pergunta_objetivo_claro", "populacao_definida"],
    "systematic_review": ["pergunta_focada", "elegibilidade_predefinida", "busca_sistematica_abrangente",
                          "revisao_em_duplicata", "qualidade_estudos_avaliada",
                          "estudos_listados_com_caracteristicas", "vies_publicacao_avaliado",
                          "heterogeneidade_avaliada"],
    "observational_cohort": ["populacao_mesma_origem", "exposicao_antes_desfecho",
                             "janela_temporal_suficiente", "exposicao_medida_repetida",
                             "exposicao_valida_consistente", "desfecho_valido_consistente",
                             "avaliadores_cegados_exposicao", "confundidores_ajustados",
                             "pergunta_objetivo_claro", "populacao_definida",
                             "tamanho_amostral_justificado"],
    "case_control": ["controles_mesma_populacao", "casos_definidos_diferenciados",
                     "selecao_aleatoria_elegiveis", "controles_concorrentes",
                     "exposicao_precedeu_condicao", "avaliadores_exposicao_cegados",
                     "confundidores_ajustados", "pergunta_objetivo_claro", "populacao_definida"],
    "before_after": ["participantes_representativos", "todos_elegiveis_incluidos",
                     "estatistica_examina_mudanca", "serie_temporal_interrompida",
                     "pergunta_objetivo_claro", "populacao_definida"],
    "case_series": ["casos_consecutivos", "sujeitos_comparaveis", "seguimento_adequado",
                    "pergunta_objetivo_claro", "populacao_definida"],
}
# proporção de critérios CUMPRIDOS (entre os que o artigo respondeu) → teto de rigor.
# [ESCOLHA MINHA] espelha o good/fair/poor do NHLBI numa régua de 10.
_FAIXAS_NHLBI = [(0.80, 10), (0.60, 8), (0.40, 6), (0.00, 5)]
MIN_CRITERIOS_RESPONDIDOS = 5      # abaixo disto a proporção é instável → não se usa a contagem


def contagem_nhlbi(a):
    """Devolve (cumpre, falha, nao_reporta, teto, criterios_que_falharam).
    teto=10 significa 'não capa' — ou porque o estudo cumpre tudo, ou porque não há dado suficiente."""
    n = a.get("qualidade_nhlbi") or {}
    inst = n.get("instrumento")
    campos = _CRITERIOS_NHLBI.get(inst)
    if not campos:
        return 0, 0, 0, 10, []
    cumpre = [c for c in campos if n.get(c) is True]
    falha = [c for c in campos if n.get(c) is False]
    silencio = [c for c in campos if c in n and n.get(c) is None] or \
               [c for c in campos if c not in n]
    respondidos = len(cumpre) + len(falha)
    if respondidos < MIN_CRITERIOS_RESPONDIDOS:
        return len(cumpre), len(falha), len(silencio), 10, falha
    prop = len(cumpre) / respondidos
    teto = next(t for lim, t in _FAIXAS_NHLBI if prop >= lim)
    return len(cumpre), len(falha), len(silencio), teto, falha


def teto_externa(a):
    """REGRA 1 — validade externa não-extrapolável = TETO 7 (não desconto).
    Só se aplica a INTERVENÇÃO ('funciona no MEU paciente?'). Etiologia/prognóstico não capam:
    fator de risco biológico generaliza (Framingham=10 mesmo sendo de uma cidade específica)."""
    if a["pergunta"] != "intervencao":
        return 10
    return 7 if not a.get("extrapolavel", True) else 10


# TETO DO RIGOR POR DESENHO — decisão do Dr. Eduardo, 01/Ago/2026.
# O buraco: `nota_estatistica` começava em 9 para QUALQUER coisa que não fosse RCT duplo-cego, porque
# a base era `a.get("base_qualidade", 9)` — um número fixo que NÃO conhecia o desenho. Resultado:
# uma SÉRIE DE CASOS recebia "Rigor 9/10". O teto de aplicabilidade a segurava em 5, então não
# vazava para o assinante — MAS o `analisador.py` injeta essa linha no contexto do redator com a
# instrução "use estes números, não invente outros". Numa coorte (NAC 6) o "Rigor 9" ia parar
# DENTRO do texto da perícia que o assinante lê.
# Regra: não existe estatística impecável em desenho frágil. O rigor não pode passar do que o
# desenho permite medir. Os delatores continuam descendo A PARTIR daqui.
_TETO_RIGOR_DESENHO = {
    "rct": 10,                        # o único que pode chegar a 10 (duplo-cego + desfecho duro + efeito grande)
    "meta": 9,
    # coorte = 8 e NÃO 7: o piso 8 do Framingham é gabarito do Dr. Eduardo — coorte PROSPECTIVA com
    # coleta impecável (codebook, lab calibrado, follow-up) tem estatística de primeira. Quem derruba
    # a coorte fraca é o próprio `nota_estatistica` (garbage-in → 5) e o teto de aplicabilidade
    # (retrospectivo → 7). Pus 7 aqui na 1ª tentativa e o teste_motor REPROVOU, acusando o Framingham.
    "coorte": 8,
    "observacional_ajustado": 7,      # propensity/multivariada robusta
    "caso_controle": 7,
    "registro": 6,
    "transversal": 6,
    "antes_depois_sem_controle": 5,
    "serie_de_casos": 5,
}


def teto_rigor(a):
    """Quanto de rigor estatístico o DESENHO permite, antes de qualquer delator."""
    return _TETO_RIGOR_DESENHO.get(a.get("desenho"), 6)


def nota_estatistica(a):
    """Qualidade metodológica DENTRO do tipo. Começa alto; desce com os delatores."""
    # base 10 só para o desenho apropriado IMPECÁVEL de etiologia/prognóstico/diagnóstico
    q = a["pergunta"]
    impecavel_obs = (q in ("etiologia", "prognostico", "diagnostico")
                     and a.get("desenho_apropriado") and a.get("qualidade_entrada")
                     and a.get("follow_up_completo") and not a.get("dicotomizou_continuo"))
    # aquisição impecável = piso 8 (sem viés de desfecho/hindsight); senão 9 (interv/meta) ou menos (obs falho)
    if impecavel_obs:
        s = 8
    elif q in ("etiologia", "prognostico", "diagnostico"):
        s = 7 if a.get("qualidade_entrada", True) else 5
    elif (q == "intervencao" and a.get("desenho") == "rct" and not a.get("open_label")
          and a.get("desfecho_duro") and a.get("efeito_grande")):
        s = 10  # RCT duplo-cego, desfecho duro, efeito DISRUPTIVO (RRR enorme) = landmark
    else:
        s = a.get("base_qualidade", 9)
    # TETO DO RIGOR PELO DESENHO (01/Ago/2026) — aplicado ANTES dos delatores, para que eles
    # continuem descendo a partir de um ponto de partida honesto. Sem isto, série de casos partia de 9.
    tr = teto_rigor(a)
    fl = []
    if s > tr:
        fl.append(f"rigor limitado pelo desenho ({a.get('desenho')}) → teto {tr}")
        s = tr
    # REGRA 2 — eventos / poder real. EXCEÇÃO: parado CEDO POR BENEFÍCIO → os poucos eventos são
    # CONSEQUÊNCIA do benefício esmagador (seria antiético continuar) → NÃO penaliza. (US Carvedilol)
    if a.get("parado_cedo_por_beneficio"):
        fl.append("parado cedo por benefício (feature — não penaliza eventos)")
    else:
        ev = a.get("eventos_min_grupo")   # eventos do desfecho PRIMÁRIO/composto, não só mortalidade
        if ev is not None and ev < 30:
            s = min(s, 6); fl.append(f"<30 eventos/grupo (={ev})")
        if a.get("eventos_nao_alcancados"):
            s = min(s, 7); fl.append("não alcançou os eventos previstos")
        if a.get("taxa_obs") and a.get("taxa_esp") and a["taxa_obs"] < 0.7 * a["taxa_esp"]:
            s = min(s, 7); fl.append("taxa observada <70% da esperada")
    if a.get("margem_ni") and a.get("taxa_basal") and a["margem_ni"] > 2 * a["taxa_basal"]:
        s = min(s, 7); fl.append("margem NI > 2× basal")
    # RCT — validade interna
    if a.get("conclusao_nao_bate_desenho"):
        s = min(s, 7); fl.append("conclusão ≠ desenho (ex.: estratégia≠droga)")
    if a.get("itt_falso"):
        s = min(s, 7); fl.append("ITT falso (exclusão assimétrica)")
    # META — Bisturi
    if a.get("contaminacao_incluidos"):
        s = min(s, 5); fl.append("estudos incluídos contaminados")
    if a.get("ni_mal_interpretada"):
        s = min(s, 6); fl.append("não-inferioridade mal interpretada")
    if a.get("i2_alto_sem_investigar"):
        s = min(s, 6); fl.append("I² ≥80% sem investigação")
    # OBSERVACIONAL — dado de entrada
    if a["pergunta"] in ("etiologia", "prognostico", "diagnostico"):
        if not a.get("qualidade_entrada", True):
            s = min(s, 5); fl.append("garbage-in (dado de entrada ruim)")
        if a.get("dicotomizou_continuo"):
            s = min(s, 7); fl.append("dicotomizou variável contínua")
    # flags informativas
    if a.get("open_label"):
        fl.append("open-label → teto desenho 8")
    return s, fl


def muda_conduta(a, aplic):
    """REGRA 4 — checklist 'mudar a prática', NUNCA a autoridade."""
    if a["pergunta"] != "intervencao":
        return "N/A (não é intervenção)"
    ok = (aplic >= 8
          and a.get("efeito_relevante_consistente", False)
          and a.get("extrapolavel", True)
          and a.get("sem_evidencia_conflitante_melhor", True)
          and a.get("beneficio_supera_risco", True))
    return "SIM" if ok else "NÃO"


def score(a):
    # PASSO 0 — o artigo pertence à escala clínica? (pré-clínico / não classificável saem ANTES.)
    # aplic=0 de propósito: 0 < 6, então a porta do analisador já RETÉM sozinha, sem quebrar nenhuma
    # comparação numérica lá na frente (r["aplic"] >= 7 etc.). Quem lê a decisão lê o campo 'rota'.
    r0 = rota(a)
    if r0 != ROTA_CLINICA:
        motivo = ("estudo pré-clínico (animal/in vitro): não há paciente, logo não há aplicabilidade "
                  "clínica para pontuar — nenhum instrumento do NHLBI cobre este desenho"
                  if r0 == ROTA_FRONTEIRA else
                  "o extrator não conseguiu classificar o desenho: o motor NÃO chuta")
        return {"trabalho": None, "aplic": 0, "teto_desenho": None, "teto_externa": None,
                "muda_conduta": "N/A", "rota": r0, "falhas_fatais": [], "flags": [motivo]}

    s, fl = nota_estatistica(a)
    td, te = teto_desenho(a), teto_externa(a)

    # PASSO 1 — CONTAGEM NHLBI: o rigor vira auditável e SÓ PODE BAIXAR (nunca inflar).
    cum, falh, sil, tn, criterios_falhos = contagem_nhlbi(a)
    if tn < s:
        fl.append(f"NHLBI: cumpre {cum} de {cum + falh} critérios respondidos → teto de rigor {tn}"
                  + (f" (falhou: {', '.join(criterios_falhos[:4])})" if criterios_falhos else ""))
        s = tn

    # PASSO 2 — falha fatal REPROVA (não desconta): teto 4, independente do resto.
    ff = falhas_fatais(a)
    tf = TETO_FALHA_FATAL if ff else 10
    for f in ff:
        fl.append(f"FALHA FATAL {f}: {FALHAS_FATAIS[f]}")

    # PASSO 3 — relevância clínica (MCID): significância estatística não basta.
    tm = teto_mcid(a)
    if tm < 10:
        rc = (a.get("relevancia_clinica") or {}).get("classificacao")
        fl.append(f"relevância clínica '{rc}' → teto {tm}")

    aplic = min(td, te, s, tf, tm)       # ← a régua-chave
    return {"trabalho": s, "aplic": aplic, "teto_desenho": td, "teto_externa": te,
            "teto_falha_fatal": tf, "teto_mcid": tm, "muda_conduta": muda_conduta(a, aplic),
            "rota": ROTA_CLINICA, "falhas_fatais": ff,
            "nhlbi": {"cumpre": cum, "falha": falh, "nao_reporta": sil, "teto": tn,
                      "criterios_falhos": criterios_falhos},
            "flags": fl}


# ─────────────────────────── FIXTURES (fatos dos 6 artigos) + GABARITO ───────────────────────────
FIXTURES = {
    "EXCEL": dict(gabarito=8, pergunta="intervencao", desenho="rct", open_label=True,
                  poder_ok=True, desfecho_duro=True, extrapolavel=True, base_qualidade=9,
                  efeito_relevante_consistente=True, beneficio_supera_risco=True),
    "NOBLE": dict(gabarito=7, pergunta="intervencao", desenho="rct", open_label=True,
                  desfecho_duro=True, extrapolavel=True, base_qualidade=9,
                  eventos_nao_alcancados=True),
    "EPCAT III (Canada)": dict(gabarito=6, pergunta="intervencao", desenho="rct", open_label=False,
                  poder_ok=True, desfecho_duro=True, extrapolavel=False, base_qualidade=9,
                  eventos_min_grupo=3, taxa_obs=0.48, taxa_esp=0.7, margem_ni=0.7, taxa_basal=0.45),
    "ISAR-REACT 5": dict(gabarito=7, pergunta="intervencao", desenho="rct", open_label=True,
                  desfecho_duro=True, extrapolavel=True, base_qualidade=9,
                  conclusao_nao_bate_desenho=True, itt_falso=True),
    "US Carvedilol": dict(gabarito=10, pergunta="intervencao", desenho="rct", open_label=False,
                  poder_ok=True, desfecho_duro=True, extrapolavel=True,
                  parado_cedo_por_beneficio=True, efeito_grande=True,
                  efeito_relevante_consistente=True, sem_evidencia_conflitante_melhor=True,
                  beneficio_supera_risco=True),
    "Framingham": dict(gabarito=8, pergunta="etiologia", desenho="coorte",
                  desenho_apropriado=True, qualidade_entrada=True, follow_up_completo=True,
                  extrapolavel=True),
    "Matharu (meta)": dict(gabarito="5-6", pergunta="intervencao", desenho="meta",
                  extrapolavel=True, base_qualidade=9,
                  contaminacao_incluidos=True, ni_mal_interpretada=True),
}

if __name__ == "__main__":
    print(f"{'ARTIGO':22} {'GAB':>5} {'CALC':>5}  {'bate?':6} tetos(des/ext) stat  muda_conduta")
    print("-"*100)
    ok = 0
    for nome, a in FIXTURES.items():
        gab = a.pop("gabarito")
        r = score(a)
        calc = r["aplic"]
        bate = (str(calc) == str(gab)) or (isinstance(gab, str) and "-" in gab
                                           and int(gab.split("-")[0]) <= calc <= int(gab.split("-")[1]))
        ok += bate
        print(f"{nome:22} {str(gab):>5} {calc:>5}  {'✅' if bate else '❌':6} "
              f"{r['teto_desenho']:>3}/{r['teto_externa']:<3}      {r['trabalho']:>3}   {r['muda_conduta']}")
        print(f"    flags: {', '.join(r['flags']) or '—'}")
    print("-"*100)
    print(f"GABARITO: {ok}/{len(FIXTURES)} baterem")
