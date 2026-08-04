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
    "incerto": 7,                            # efeito de relevância duvidosa não muda a prática amanhã
    # ═══════════════ 04/Ago/2026 — O BURACO QUE INVERTIA O CARDIODAILY ═══════════════
    #
    # `ausencia_de_efeito_demonstrada` NÃO TEM TETO. Decisão do Dr. Eduardo, 04/Ago.
    #
    # O CASO: a meta-análise de dados individuais de betabloqueador pós-IAM com FE preservada
    # (NEJM 2026 — 5 RCTs, 17.801 pacientes) recebeu **NOTA 4/10**, que na escala do CardioDaily
    # é "confiança criticamente baixa — NÃO serve de base para conduta".
    #
    # A causa não foi o modelo nem o LLM: **o vocabulário não tinha a palavra.** O enum de
    # `classificacao` só oferecia `nao_relevante` (teto 6) para um resultado nulo. Um trabalho
    # que PROVA que a droga não ajuda era obrigado a se declarar irrelevante.
    #
    # POR QUE ISSO INVERTIA O PRODUTO — nas palavras do Dr. Eduardo:
    #   "antes eu ensinava aos residentes o MONABICHA. O M caiu (morfina reduz absorção de
    #    antiplaquetário), o O caiu (oxigênio só se SatO2<90%, senão aumenta radical livre),
    #    o B deixou de ser mantra (sem disfunção de VE, sem betabloqueador). Se o meu programa
    #    está na contramão disto, meu programa está totalmente errado."
    #
    # Metade da cardiologia que ele ensina é fruto de ESTUDO NEGATIVO. COURAGE, ISCHEMIA, ORBITA,
    # TOPCAT, CABANA, REDUCE-AMI. Um sistema que dá 4/10 para essa classe descarta exatamente o
    # conteúdo que mais muda conduta.
    #
    # A DISTINÇÃO (metodológica, não de gosto) — três coisas que caíam no mesmo balde:
    #   · significativo abaixo do MCID → p<0,05 e ninguém sente         → teto 6
    #   · INCONCLUSIVO → poder fraco ou IC largo: ainda cabe benefício  → teto 7
    #   · AUSÊNCIA DEMONSTRADA → poder ok + IC exclui benefício relevante → SEM TETO (até 10)
    "ausencia_de_efeito_demonstrada": 10,
}

# O que o extrator precisa PROVAR para merecer o crédito do nulo (decisão do Dr. Eduardo, 04/Ago):
# as DUAS coisas — o IC 95% exclui benefício clinicamente relevante E o poder foi declarado.
# Se faltar qualquer uma, o motor REBAIXA para `incerto` (teto 7) — porque aí não é "provamos que
# não funciona", é "não conseguimos mostrar". Quem decide isso é o CÓDIGO, não a palavra do modelo:
# é a mesma razão de a LEI 0 ser determinística.
def _nulo_esta_demonstrado(rc, a):
    return bool(rc.get("ic_exclui_beneficio_relevante")) and bool(a.get("poder_ok"))


def teto_mcid(a):
    """REGRA 3 — o efeito é clinicamente relevante, não só estatisticamente significativo?
    E, desde 04/Ago: o resultado NULO foi DEMONSTRADO ou apenas não encontrado?"""
    rc = a.get("relevancia_clinica") or {}
    c = (rc.get("classificacao") or "").strip().lower()
    if c == "ausencia_de_efeito_demonstrada" and not _nulo_esta_demonstrado(rc, a):
        return TETO_MCID["incerto"]          # o modelo disse; o motor não aceitou sem prova
    return TETO_MCID.get(c, 10)


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


# ═══════════════════ MOTOR DA META-ANÁLISE — 02/Ago/2026 ═══════════════════
# ORIGEM: este motor NÃO é invenção nova. Ele estava em `src/prompts/prompt_meta_analise_v2.md`,
# escrito pelo Dr. Eduardo, e foi PERDIDO quando a corrente nova unificou tudo num prompt só.
# Recuperado em 02/Ago. Os pesos são dele — e dizem o que ele pensa:
#
#     NOTA = PICO×0,15 + Busca×0,20 + Viés×0,15 + Heterogeneidade×0,15
#            + Viés de publicação×0,10 + CONCLUSÕES×0,25
#
# CONCLUSÕES tem o MAIOR peso (0,25): "os autores foram além do que a evidência permite?"
# BUSCA vem em segundo (0,20): busca ruim contamina tudo o que vem depois.
# Viés de publicação tem o MENOR (0,10): é o mais difícil de fazer e o menos decisivo.
#
# ESCOLHA DE ARQUITETURA (minha, explícita p/ o dono desfazer): no prompt v2 quem dava a nota de
# cada domínio era o LLM. Aqui os subescores são DERIVADOS DOS FATOS, no código — porque a LEI 0
# manda a nota ser determinística, e nota que depende do humor do modelo foi o que quebrou em julho.
# O LLM extrai o FATO (registrou PROSPERO? quantas bases? qual o I²? fez Egger?); o código pontua.
PESOS_META = {"pico": 0.15, "busca": 0.20, "vies_estudos": 0.15,
              "heterogeneidade": 0.15, "vies_publicacao": 0.10, "conclusoes": 0.25}

FAIXA_META = [(8.0, "Alta confiança — meta-análise bem conduzida, conclusões confiáveis"),
              (6.0, "Confiança moderada — boa no geral, limitações exigem juízo clínico"),
              (4.0, "Baixa confiança — falhas relevantes, interpretar com cautela"),
              (0.0, "Confiança criticamente baixa — NÃO serve de base para conduta")]


def _n(v, padrao=None):
    return v if isinstance(v, (int, float)) else padrao


def dominios_meta(a):
    """Os 6 domínios do Dr. Eduardo, pontuados 0–10 A PARTIR DOS FATOS (não do palpite do LLM)."""
    q = a.get("qualidade_nhlbi") or {}
    m = a.get("qualidade_meta") or {}
    d = {}

    # a) PICO — pergunta focada e elegibilidade pré-definida
    d["pico"] = 10 if (q.get("pergunta_focada") and q.get("elegibilidade_predefinida")) else \
                7 if q.get("pergunta_focada") else 4

    # b) BUSCA — bases, protocolo registrado, duplicata, literatura cinzenta
    bases = _n(m.get("n_bases"), 0) or 0
    b = 4
    if q.get("busca_sistematica_abrangente"):
        b = 7
    if bases >= 3:
        b += 1
    if m.get("protocolo_registrado"):
        b += 1                                   # PROSPERO
    if q.get("revisao_em_duplicata"):
        b += 1
    d["busca"] = min(b, 10)

    # c) VIÉS DOS INCLUÍDOS — e a pergunta que separa: MUDOU a interpretação ou foi check-box?
    if not q.get("qualidade_estudos_avaliada"):
        d["vies_estudos"] = 3
    elif m.get("vies_mudou_interpretacao"):
        d["vies_estudos"] = 10
    else:
        d["vies_estudos"] = 6                    # avaliou, mas não usou → check-box

    # d) HETEROGENEIDADE — reportar não é investigar
    i2 = _n(q.get("i2_valor"))
    if i2 is None:
        d["heterogeneidade"] = 4                 # nem reportou
    elif i2 < 25:
        d["heterogeneidade"] = 9
    elif i2 <= 50:
        d["heterogeneidade"] = 8 if m.get("heterogeneidade_investigada") else 6
    else:
        d["heterogeneidade"] = 6 if m.get("heterogeneidade_investigada") else 3
    # "I² baixo com poucos estudos não é homogeneidade — pode ser falta de poder" (v2, palavras dele)
    k = _n(m.get("k_estudos"), 99)
    if i2 is not None and i2 < 25 and k is not None and k < 5:
        d["heterogeneidade"] = min(d["heterogeneidade"], 6)

    # e) VIÉS DE PUBLICAÇÃO — funnel/Egger/Begg feito?
    d["vies_publicacao"] = 9 if q.get("vies_publicacao_avaliado") else 3

    # f) CONCLUSÕES — o maior peso: foram além do que os dados permitem?
    if a.get("conclusao_nao_bate_desenho") or m.get("conclusao_alem_da_evidencia"):
        d["conclusoes"] = 3
    elif m.get("limitacoes_reconhecidas"):
        d["conclusoes"] = 9
    else:
        d["conclusoes"] = 6
    return d


# quantos FATOS de meta o extrator precisa ter respondido para a ponderação valer.
# Abaixo disso, pontuar seria punir o SILÊNCIO do extrator, não a qualidade do estudo —
# o mesmo erro que já foi evitado na contagem NHLBI e que eu repeti aqui (pego pelo teste, 02/Ago).
MIN_FATOS_META = 3


def nota_meta(a):
    """Devolve (nota 0–10, domínios, frase da faixa).
    A ponderação é do Dr. Eduardo; os TETOS clássicos da meta continuam por cima dela."""
    q = a.get("qualidade_nhlbi") or {}
    m = a.get("qualidade_meta") or {}
    respondidos = sum(1 for k in ("pergunta_focada", "elegibilidade_predefinida",
                                  "busca_sistematica_abrangente", "revisao_em_duplicata",
                                  "qualidade_estudos_avaliada", "vies_publicacao_avaliado",
                                  "heterogeneidade_avaliada", "i2_valor")
                      if q.get(k) is not None) + len([v for v in m.values() if v is not None])

    if respondidos < MIN_FATOS_META:
        # sem dado suficiente → cai na escada antiga, e DIZ que caiu (não inventa ponderação)
        s, fl = nota_estatistica(a)
        return s, None, (f"ponderação não aplicada: só {respondidos} fato(s) de meta extraído(s) "
                         f"(mínimo {MIN_FATOS_META}) — usada a régua geral")

    d = dominios_meta(a)
    bruta = sum(d[k] * p for k, p in PESOS_META.items())
    s = int(round(bruta))

    # TETOS CLÁSSICOS DA META — vinham do motor antigo e NÃO podem se perder na ponderação.
    # Um estudo pode ter os 6 domínios altos e ainda ter engolido ensaio contaminado.
    if a.get("contaminacao_incluidos"):
        s = min(s, 5)
    if a.get("ni_mal_interpretada"):
        s = min(s, 6)
    if a.get("i2_alto_sem_investigar"):
        s = min(s, 6)

    frase = next(f for lim, f in FAIXA_META if s >= lim)
    return s, d, frase


# ═══════════════════ MOTOR DA DIRETRIZ — 02/Ago/2026 ═══════════════════
# CONSTRUÍDO COM O DR. EDUARDO. Nunca existiu antes: o `prompt_guideline_v2.md` que sobreviveu do
# CardioDaily antigo está INTITULADO "Análise de Revisões e Meta-Análises", não menciona AGREE e não
# tem bloco de notas. Até hoje uma diretriz caía no motor do artigo original — que lhe cobra
# randomização, cegamento e I². É o mesmo "superficializar" do prompt único, uma camada mais fundo.
#
# AS DUAS NOTAS, NUMA DIRETRIZ:
#   RIGOR         = como o documento foi CONSTRUÍDO (AGREE II). Não mede estatística; não há.
#   APLICABILIDADE = quanto dá para OBEDECER — dominada pela base de evidência (% nível C) e pelo Brasil.
#
# PESOS (aprovados pelo Dr. Eduardo em 02/Ago). A forma espelha a lógica que ele mesmo escreveu para a
# meta-análise: lá o maior peso era CONCLUSÕES (0,25) — "foram além do que a evidência permite?".
# Numa diretriz a pergunta idêntica é o VÍNCULO entre a recomendação e a evidência (AGREE item 12).
PESOS_DIRETRIZ = {"vinculo_evidencia": 0.25, "busca": 0.20, "independencia": 0.20,
                  "metodo_recomendacao": 0.15, "revisao_externa": 0.10, "atualizacao": 0.10}

FAIXA_DIRETRIZ = [(8.0, "Desenvolvimento rigoroso — método explícito e independência preservada"),
                  (6.0, "Desenvolvimento adequado — lacunas de método exigem leitura crítica"),
                  (4.0, "Desenvolvimento frágil — o documento não permite auditar como chegou às ordens"),
                  (0.0, "Desenvolvimento criticamente frágil — recomendações sem método rastreável")]

# Os domínios AGREE 4 (clareza) e 5 (implementação) ficam FORA do rigor de propósito:
# clareza de escrita não é rigor de método. A implementação entra na APLICABILIDADE (teto Brasil).


def dominios_diretriz(a):
    """Os 6 domínios do rigor, pontuados 0–10 A PARTIR DOS FATOS (não do palpite do LLM)."""
    g = a.get("recomendacoes") or {}
    ag = a.get("agree") or {}
    d = {}

    # a) VÍNCULO RECOMENDAÇÃO ↔ EVIDÊNCIA (AGREE 9 e 12) — o maior peso.
    # ESCOLHA REGISTRADA (minha, para o dono desfazer): "Classe I sobre nível C" NÃO entra aqui.
    # Ela é TETO DE APLICABILIDADE (7), como o Dr. Eduardo aprovou em 02/Ago. Se descontasse também
    # no rigor, o rigor cairia a 5 e — como aplic = min(..., rigor) — o teto 7 que ele aprovou viraria
    # letra morta. Punir duas vezes o mesmo defeito revoga a decisão dele por via oblíqua.
    if ag.get("vinculo_recomendacao_evidencia") is False:
        d["vinculo_evidencia"] = 4
    else:
        v = 4
        if (g.get("sistema_graduacao") or "nenhum") != "nenhum":
            v = 7                                     # cada recomendação carrega classe e nível
        if ag.get("vinculo_recomendacao_evidencia"):
            v += 2                                    # AGREE 12: o vínculo é explícito e citado
        if ag.get("forcas_limitacoes_descritas"):
            v += 1                                    # AGREE 9
        d["vinculo_evidencia"] = min(v, 10)

    # b) BUSCA E SELEÇÃO DA EVIDÊNCIA (AGREE 7, 8) — busca ruim contamina tudo o que vem depois
    b = 4
    if ag.get("busca_sistematica_declarada"):
        b = 7
    if ag.get("criterios_selecao_evidencia"):
        b += 2
    if (_n(ag.get("n_bases"), 0) or 0) >= 3:
        b += 1
    d["busca"] = min(b, 10)

    # c) INDEPENDÊNCIA EDITORIAL (AGREE 22, 23)
    # G2/G3 foram RECUSADAS como falha fatal pelo Dr. Eduardo (02/Ago) — não reprovam.
    # Mas não somem: é AQUI que conflito não declarado e ausência de política pesam.
    if ag.get("conflitos_declarados") is False:
        d["independencia"] = 2                        # nenhuma linha sobre conflito, em 2026
    else:
        c = 5
        if ag.get("conflitos_declarados"):
            c = 7
        if ag.get("politica_gestao_conflitos"):
            c += 2
        if ag.get("financiamento_declarado"):
            c += 1
        c = min(c, 10)
        pct_cf = _n(ag.get("pct_membros_com_conflito"))
        if pct_cf is not None and pct_cf >= 50 and not ag.get("politica_gestao_conflitos"):
            c = min(c, 5)                             # metade do painel com vínculo e sem política
        d["independencia"] = c

    # d) MÉTODO DE FORMULAR A RECOMENDAÇÃO (AGREE 10, 11) — votação, quórum, risco × benefício
    m = 4
    if ag.get("metodo_formular_recomendacao"):
        m = 7
    if ag.get("riscos_beneficios_considerados"):
        m += 2
    if ag.get("opcoes_apresentadas"):
        m += 1
    d["metodo_recomendacao"] = min(m, 10)

    # e) REVISÃO EXTERNA (AGREE 13) — G4 também foi recusada como fatal; pesa aqui
    d["revisao_externa"] = 9 if ag.get("revisao_externa") else \
                           3 if ag.get("revisao_externa") is False else 5

    # f) PLANO DE ATUALIZAÇÃO (AGREE 14)
    d["atualizacao"] = 9 if ag.get("plano_atualizacao") else \
                       4 if ag.get("plano_atualizacao") is False else 5
    return d


# Quantos FATOS de AGREE o extrator precisa ter respondido para a ponderação valer.
# Mesma trava da meta: abaixo disso pontuar seria punir o SILÊNCIO do extrator, não o documento.
MIN_FATOS_DIRETRIZ = 3
RIGOR_DIRETRIZ_SEM_FATOS = 5     # e 5 RETÉM (a porta do analisador publica a partir de 6) — de propósito:
                                 # LEI 8, "na dúvida, revisão humana". Diretriz cujo método não deu para
                                 # ler não vai ao assinante com nota inventada.


def nota_diretriz(a):
    """Devolve (rigor 0–10, domínios, frase da faixa) pelo AGREE ponderado."""
    ag = a.get("agree") or {}
    respondidos = sum(1 for v in ag.values() if v is not None)
    if respondidos < MIN_FATOS_DIRETRIZ:
        return (RIGOR_DIRETRIZ_SEM_FATOS, None,
                f"AGREE não avaliável: só {respondidos} item(ns) extraído(s) "
                f"(mínimo {MIN_FATOS_DIRETRIZ}) — rigor {RIGOR_DIRETRIZ_SEM_FATOS} por prudência, "
                f"o documento fica retido")
    d = dominios_diretriz(a)
    s = int(round(sum(d[k] * p for k, p in PESOS_DIRETRIZ.items())))
    return s, d, next(f for lim, f in FAIXA_DIRETRIZ if s >= lim)


# ── TETO 1: TIPO DO DOCUMENTO (o análogo do teto_desenho) ──
# DERIVADO dos fatos, não perguntado ao modelo: "tem metodologia declarada?" é a conjunção de
# busca sistemática declarada + sistema de graduação. Assim o teto não depende de um juízo do LLM.
def teto_tipo_documento(a):
    t = (a.get("tipo_documento_norm") or "diretriz").strip().lower()
    g = a.get("recomendacoes") or {}
    ag = a.get("agree") or {}
    if t in ("scientific_statement", "position_paper"):
        return 7                                   # descreve, não ordena
    if (g.get("sistema_graduacao") or "nenhum") == "nenhum":
        return 6                                   # consenso sem classe nem nível
    if not ag.get("busca_sistematica_declarada"):
        return 7                                   # diretriz sem metodologia declarada
    return 10


# ── TETO 2: A BASE DE EVIDÊNCIA (% nível C) — a pergunta-assinatura do Dr. Eduardo ──
# "quanto desta diretriz é EVIDÊNCIA e quanto é OPINIÃO DE ESPECIALISTA com cara de evidência?"
# Régua aprovada por ele em 02/Ago. Uma diretriz majoritariamente C ainda vale 7: é o melhor que
# existe naquele tema — o problema não é dela, é do campo.
_FAIXA_NIVEL_C = [(70, 6), (50, 7), (30, 8), (0, 10)]


def pct_nivel_c(a):
    g = a.get("recomendacoes") or {}
    na, nb, nc = _n(g.get("n_nivel_A")), _n(g.get("n_nivel_B")), _n(g.get("n_nivel_C"))
    if nc is None:
        return None
    tot = sum(x for x in (na, nb, nc) if x is not None)
    return None if not tot else 100.0 * nc / tot


def teto_nivel_c(a):
    p = pct_nivel_c(a)
    if p is None:
        return 10, None                            # não contou → não capa (e o flag registra)
    return next(t for lim, t in _FAIXA_NIVEL_C if p >= lim), p


# ── TETO 3: CLASSE I APOIADA EM NÍVEL C — ordem forte sobre evidência fraca ──
# Aprovado como TETO PRÓPRIO pelo Dr. Eduardo: é falha diferente do % geral. O % geral diz "o campo
# não tem evidência"; este diz "a sociedade mandou fazer assim mesmo". É onde mora o risco ao paciente.
LIMIAR_CLASSE_I_EM_C = 50      # % das Classe I que são nível C
TETO_CLASSE_I_EM_C = 7


def pct_classe_i_em_c(a):
    g = a.get("recomendacoes") or {}
    n1, n1c = _n(g.get("n_classe_I")), _n(g.get("n_classe_I_nivel_C"))
    if n1 is None or n1c is None or not n1:
        return None
    return 100.0 * n1c / n1


def teto_classe_i_em_c(a):
    p = pct_classe_i_em_c(a)
    if p is None:
        return 10, None
    return (TETO_CLASSE_I_EM_C if p >= LIMIAR_CLASSE_I_EM_C else 10), p


# ── TETO 4: BRASIL (o análogo do teto_externa) ──
def teto_brasil(a):
    """Recomendações centrais dependem de droga sem ANVISA/CONITEC ou exame indisponível → teto 7."""
    return 7 if a.get("aplicavel_brasil") is False else 10


# ── FALHA FATAL DA DIRETRIZ (teto 4) ──
# O Dr. Eduardo aprovou UMA, em 02/Ago, e recusou explicitamente as outras três que propus:
#   G2 (nenhuma declaração de conflito) · G3 (indústria sem política) · G4 (sem busca e sem revisão)
# Elas NÃO reprovam — mas continuam derrubando o rigor pelos domínios `independencia` e
# `revisao_externa`. Deixaram de ser desqualificantes; não deixaram de pesar.
FALHAS_FATAIS_DIRETRIZ = {
    "G1": "documento NORMATIVO (dá ordens) sem classe nem nível de evidência — não é auditável",
}


def falhas_fatais_diretriz(a):
    t = (a.get("tipo_documento_norm") or "diretriz").strip().lower()
    g = a.get("recomendacoes") or {}
    achadas = [f for f in (a.get("falhas_fatais") or []) if f in FALHAS_FATAIS_DIRETRIZ]
    if t in ("diretriz", "consenso") and (g.get("sistema_graduacao") or "nenhum") == "nenhum":
        achadas.append("G1")
    return sorted(set(achadas))


def score_diretriz(a):
    """Motor da DIRETRIZ. Mesmo contrato de saída do motor original — a corrente não pode quebrar."""
    s, dom, frase = nota_diretriz(a)
    fl = ([f"AGREE [{k} {v}]" for k, v in dom.items()] if dom else [frase])

    td = teto_tipo_documento(a)
    tc, p_c = teto_nivel_c(a)
    tci, p_ic = teto_classe_i_em_c(a)
    tb = teto_brasil(a)

    if p_c is None:
        fl.append("nível de evidência não contabilizado no documento → teto do % nível C não aplicado")
    else:
        fl.append(f"{p_c:.0f}% das recomendações em nível C (opinião de especialista) → teto {tc}")
    if p_ic is not None and tci < 10:
        fl.append(f"{p_ic:.0f}% das Classe I se apoiam em nível C → teto {tci}")
    if tb < 10:
        fl.append("recomendações centrais não executáveis no Brasil → teto 7")

    ff = falhas_fatais_diretriz(a)
    tf = TETO_FALHA_FATAL if ff else 10
    for f in ff:
        fl.append(f"FALHA FATAL {f}: {FALHAS_FATAIS_DIRETRIZ[f]}")

    # IDADE: registrada como FATO, nunca como teto. O Dr. Eduardo não aprovou teto por idade, e o
    # motor só pode usar o que está DENTRO do PDF — "já foi substituída pela versão nova" é fato de fora.
    idade = _n(a.get("idade_anos"))
    if idade is not None and idade >= 5:
        fl.append(f"documento com {idade:.0f} anos — verificar se há versão mais recente (não capa a nota)")

    aplic = min(td, tc, tci, tb, tf, s)
    return {"trabalho": s, "aplic": aplic, "teto_desenho": td, "teto_externa": tb,
            "teto_falha_fatal": tf, "teto_mcid": 10,
            # ESCOLHA MINHA: numa diretriz o documento INTEIRO é conduta; o gatilho é a nota.
            "muda_conduta": "SIM" if aplic >= 8 else "NÃO",
            "rota": ROTA_CLINICA, "falhas_fatais": ff, "motor": "DIRETRIZ",
            "nhlbi": {"cumpre": 0, "falha": 0, "nao_reporta": 0, "teto": 10, "criterios_falhos": []},
            "teto_nivel_c": tc, "pct_nivel_c": p_c,
            "teto_classe_i_em_c": tci, "pct_classe_i_em_c": p_ic,
            "dominios_agree": dom, "faixa_agree": frase, "flags": fl}


# ═══════════════ MOTOR DA REVISÃO NARRATIVA — 02/Ago/2026 ═══════════════
# CONSTRUÍDO COM O DR. EDUARDO. A semente veio do `src/prompts/prompt_revisao_geral_v2.md`, Seção 4,
# escrita por ele: escopo · atualidade · viés de seleção · conflitos · lacunas reconhecidas.
#
# ⚠️ A CORREÇÃO QUE ELE FEZ EM 02/Ago, E QUE MUDOU O DESENHO INTEIRO:
# Eu ia dar TETO 6 a toda revisão narrativa, com o argumento "não é fonte de evidência primária".
# Ele recusou, e a frase dele é a especificação:
#
#   "PODE CHEGAR A 10 — A REVISÃO NÃO TEM GRADUAÇÃO ESTATÍSTICA. ELA SE BASEIA EM QUANTO ELA ME AJUDA
#    NA PRÁTICA, QUANTA INFORMAÇÃO APLICÁVEL ELA ENTREGA. SE FALA POR CIMA, ELA TEM NOTA BAIXA.
#    SE ELA EXPLICA QUE OS SILENCIADORES GENÉTICOS SÃO EXTREMAMENTE EFICIENTES — MAS CUSTAM 750 MIL
#    REAIS NO BRASIL, E QUE ISSO DIFICULTA SUA IMPLEMENTAÇÃO APESAR DAS FACILIDADES DE USO E TER
#    BAIXÍSSIMOS EFEITOS ADVERSOS — ENTÃO ELA TEM UMA NOTA MUITO ALTA."
#
# Ou seja: num documento que NÃO é estudo, "aplicabilidade clínica" quer dizer aplicabilidade MESMO —
# utilidade prática entregue — e não posição na hierarquia de evidência. NÃO existe teto por categoria.
# As 5 dimensões abaixo saíram desse exemplo: eficácia quantificada · custo/acesso no Brasil ·
# praticidade de uso · segurança · julgamento de implementação (em quem dá e em quem não dá).
PESOS_REVISAO_RIGOR = {"vies_selecao": 0.30, "abrangencia": 0.20, "atualidade": 0.20,
                       "conflitos": 0.15, "lacunas": 0.15}
# viés de seleção no topo: palavras dele no rascunho do redator, 02/Ago —
# "numa revisão narrativa, o principal viés é a SELEÇÃO INVISÍVEL".
PESOS_REVISAO_UTIL = {"conduta_acionavel": 0.30, "magnitude": 0.20, "custo_acesso": 0.20,
                      "seguranca": 0.15, "em_quem_nao_usar": 0.15}

FAIXA_REVISAO = [(9.0, "Revisão de referência — entrega conduta pronta para usar, com o preço e os limites"),
                 (7.0, "Revisão útil — ensina e orienta, com lacunas de aplicação"),
                 (5.0, "Revisão panorâmica — situa o tema, entrega pouca conduta"),
                 (0.0, "Fala por cima — não entrega informação aplicável")]

# ⚠️ O motor SÓ pontua o que está DENTRO do texto. Palavras dele no rascunho do redator: "não invente
# ausências". "Faltou o DAPA-HF" é fato de fora — o modelo inventaria, e viés invisível não se mede.
ANO_CORRENTE = 2026


def _faixa(valor, faixas, padrao):
    """faixas = [(limite, nota), ...] em ordem decrescente de limite."""
    if valor is None:
        return padrao
    return next((n for lim, n in faixas if valor >= lim), faixas[-1][1])


def dominios_revisao_rigor(a):
    """Os 5 critérios da Seção 4 do prompt dele, pontuados 0–10 A PARTIR DOS FATOS."""
    q = a.get("qualidade_revisao") or {}
    d = {}

    # a) VIÉS DE SELEÇÃO (0,30) — "os autores privilegiaram estudos que confirmam uma narrativa?"
    # O que é verificável DENTRO do texto: as afirmações têm citação? a revisão diz o que é RCT e o
    # que é observacional? ela apresenta a evidência que a CONTRARIA?
    v = {"raras": 9, "algumas": 6, "frequentes": 3}.get(q.get("afirmacoes_sem_citacao"), 5)
    if q.get("atribui_nivel_evidencia"):
        v += 1
    if q.get("apresenta_contra_evidencia"):
        v += 1
    if q.get("tom_promocional"):
        v -= 3                                    # entusiasmo desproporcional com droga nova
    d["vies_selecao"] = max(1, min(v, 10))

    # b) ABRANGÊNCIA / ESCOPO (0,20) — "abrangente ou seletiva nos estudos incluídos?"
    b = 5
    if q.get("metodo_busca_declarado"):
        b = 8                                     # ele escreveu: "algumas revisões narrativas boas
    if q.get("escopo_declarado"):                 #  declaram método — isso conta a favor"
        b += 1
    nref = _n(q.get("n_referencias"))
    if nref is not None:
        if nref < 25:
            b -= 2
        elif nref >= 75:
            b += 1
    d["abrangencia"] = max(1, min(b, 10))

    # c) ATUALIDADE (0,20) — "as referências-chave são recentes ou há lacunas temporais?"
    # DOIS relógios diferentes, de propósito:
    #   defasagem  = quão velha é a referência mais nova HOJE  → a revisão ainda vale?
    #   pct_5_anos = quão atual ela era QUANDO FOI ESCRITA     → o autor fez a lição de casa?
    dfg = _n(q.get("defasagem_anos"))
    if dfg is None and _n(q.get("ano_referencia_mais_recente")):
        dfg = ANO_CORRENTE - _n(q.get("ano_referencia_mais_recente"))
    at = 5 if dfg is None else (9 if dfg <= 2 else 7 if dfg <= 4 else 5 if dfg <= 7 else 3)
    pct5 = _n(q.get("pct_referencias_ultimos_5_anos"))
    if pct5 is not None and pct5 >= 50:
        at += 1
    d["atualidade"] = max(1, min(at, 10))

    # d) CONFLITOS (0,15) — "há financiamento da indústria? isso enviesa as conclusões?"
    if q.get("conflitos_declarados") is False:
        c = 2
    else:
        c = 8 if q.get("conflitos_declarados") else 6
        if q.get("financiamento_industria"):
            c -= 3
        if q.get("tom_promocional"):
            c -= 2
    d["conflitos"] = max(1, min(c, 10))

    # e) LACUNAS RECONHECIDAS (0,15) — "o que os próprios autores admitem que falta?"
    d["lacunas"] = 9 if q.get("limitacoes_reconhecidas") else \
                   3 if q.get("limitacoes_reconhecidas") is False else 5
    return d


def dominios_revisao_util(a):
    """A UTILIDADE PRÁTICA — as 5 dimensões do exemplo do Dr. Eduardo (silenciadores genéticos)."""
    q = a.get("qualidade_revisao") or {}
    d = {}

    # a) CONDUTA ACIONÁVEL (0,30) — "se fala por cima, ela tem nota baixa".
    # A superficialidade é medida pela CONTAGEM: quantas condutas concretas, com critério, valor de
    # corte, dose ou alvo. Uma revisão panorâmica entrega 0–2; uma que ajuda de verdade entrega 10+.
    d["conduta_acionavel"] = _faixa(_n(q.get("n_condutas_acionaveis")),
                                    [(10, 10), (6, 8), (3, 6), (1, 4), (0, 2)], 5)
    if q.get("traz_valores_corte_ou_doses"):
        d["conduta_acionavel"] = min(d["conduta_acionavel"] + 1, 10)

    # b) MAGNITUDE (0,20) — "extremamente eficientes" com NÚMERO, não só com adjetivo
    d["magnitude"] = 9 if q.get("traz_magnitude_efeito") else \
                     3 if q.get("traz_magnitude_efeito") is False else 5
    # c) CUSTO E ACESSO NO BRASIL (0,20) — "custam 750 mil reais no Brasil". É o que ele nomeou como
    #    o dado que faz a revisão valer muito. Por isso ganha 10 quando está lá.
    d["custo_acesso"] = 10 if q.get("traz_custo_acesso") else \
                        3 if q.get("traz_custo_acesso") is False else 5
    # d) SEGURANÇA (0,15) — "baixíssimos efeitos adversos": o preço biológico da conduta
    d["seguranca"] = 9 if q.get("traz_seguranca") else \
                     3 if q.get("traz_seguranca") is False else 5
    # e) EM QUEM NÃO USAR (0,15) — "isso dificulta sua implementação": o julgamento dos limites
    d["em_quem_nao_usar"] = 9 if q.get("traz_em_quem_nao_usar") else \
                            3 if q.get("traz_em_quem_nao_usar") is False else 5
    return d


MIN_FATOS_REVISAO = 3
RIGOR_REVISAO_SEM_FATOS = 5      # mesma prudência da diretriz: 5 RETÉM (a porta publica a partir de 6)

# TETO DA ATUALIDADE — aprovado pelo Dr. Eduardo em 02/Ago como teto PRÓPRIO.
# "Uma revisão de IC escrita antes dos ensaios de SGLT2 não é só fraca — ela ensina errado."
# ⚠️ REGISTRADO: a atualidade pesa DUAS vezes (domínio 0,20 do rigor E teto). Foi assim que ele
# aprovou — as duas perguntas foram feitas separadamente e ele disse sim às duas. Se ficar duro
# demais na prática, tirar o teto é apagar uma linha (`_FAIXA_TETO_ATUALIDADE`).
_FAIXA_TETO_ATUALIDADE = [(8, 5), (5, 6)]        # defasagem em anos → teto


def teto_atualidade(a):
    q = a.get("qualidade_revisao") or {}
    dfg = _n(q.get("defasagem_anos"))
    if dfg is None and _n(q.get("ano_referencia_mais_recente")):
        dfg = ANO_CORRENTE - _n(q.get("ano_referencia_mais_recente"))
    if dfg is None:
        return 10, None
    return next((t for lim, t in _FAIXA_TETO_ATUALIDADE if dfg >= lim), 10), dfg


# FALHAS FATAIS: NENHUMA. Decisão do Dr. Eduardo, 02/Ago — ele recusou R1 (promocional sem declarar
# conflito) e R2 (afirmações centrais sem citação) como desqualificantes. As duas continuam vivas
# DENTRO do rigor: `tom_promocional` derruba viés de seleção E conflitos; `afirmacoes_sem_citacao`
# frequentes leva o viés de seleção a 3. Deixaram de reprovar; não deixaram de pesar.
FALHAS_FATAIS_REVISAO = {}


def score_revisao(a):
    """Motor da REVISÃO NARRATIVA. Mesmo contrato de saída dos outros motores."""
    q = a.get("qualidade_revisao") or {}
    respondidos = sum(1 for v in q.values() if v is not None)
    if respondidos < MIN_FATOS_REVISAO:
        s = u = RIGOR_REVISAO_SEM_FATOS
        dom_r = dom_u = None
        fl = [f"revisão não avaliável: só {respondidos} fato(s) extraído(s) (mínimo "
              f"{MIN_FATOS_REVISAO}) — nota {RIGOR_REVISAO_SEM_FATOS} por prudência, documento retido"]
        frase = fl[0]
    else:
        dom_r, dom_u = dominios_revisao_rigor(a), dominios_revisao_util(a)
        s = int(round(sum(dom_r[k] * p for k, p in PESOS_REVISAO_RIGOR.items())))
        u = int(round(sum(dom_u[k] * p for k, p in PESOS_REVISAO_UTIL.items())))
        frase = next(f for lim, f in FAIXA_REVISAO if u >= lim)
        fl = ([f"rigor [{k} {v}]" for k, v in dom_r.items()]
              + [f"utilidade [{k} {v}]" for k, v in dom_u.items()])

    ta, dfg = teto_atualidade(a)
    if dfg is not None:
        fl.append(f"referência mais recente tem {dfg:.0f} ano(s)"
                  + (f" → teto {ta}" if ta < 10 else " — atual"))

    # ⚠️ SEM TETO POR CATEGORIA. Decisão do Dr. Eduardo, 02/Ago: "PODE CHEGAR A 10".
    # O rigor continua capando (uma revisão riquíssima e enviesada não vira 10) — isso preserva a
    # decisão dele de 01/Ago de NÃO afrouxar a régua ("não quero que afrouxe").
    aplic = min(u, s, ta)
    return {"trabalho": s, "aplic": aplic, "teto_desenho": 10, "teto_externa": 10,
            "teto_falha_fatal": 10, "teto_mcid": 10, "teto_atualidade": ta, "defasagem_anos": dfg,
            "utilidade": u,
            # numa revisão o que "muda conduta" é ela entregar conduta pronta E ser confiável
            "muda_conduta": "SIM" if aplic >= 8 else "NÃO",
            "rota": ROTA_CLINICA, "falhas_fatais": [], "motor": "REVISAO",
            "nhlbi": {"cumpre": 0, "falha": 0, "nao_reporta": 0, "teto": 10, "criterios_falhos": []},
            "dominios_revisao_rigor": dom_r, "dominios_revisao_util": dom_u,
            "faixa_revisao": frase, "flags": fl}


# ═══════════════════ QUAL MOTOR — FONTE ÚNICA DE VERDADE (LEI 8) ═══════════════════
# LEI 8 (02/Ago): o tipo é decidido UMA vez, no classificador, e todo o resto OBEDECE.
# Esta função é o lugar onde essa decisão é lida — UM lugar, não dois. Enquanto o classificador
# não gravar `tipo_documento` nos fatos (tarefa #34), ela cai no `desenho` como ponte.
def tipo_do_documento(a):
    t = (a.get("tipo_documento") or "").strip().lower()
    if t in ("original", "meta", "diretriz", "revisao_narrativa"):
        return t                                   # ← o campo que o CLASSIFICADOR vai gravar
    d = a.get("desenho")
    if d == "meta":
        return "meta"
    if d in ("diretriz", "revisao_narrativa"):
        return d
    return "original"


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
    comum = (aplic >= 8
             and a.get("extrapolavel", True)
             and a.get("sem_evidencia_conflitante_melhor", True))
    # 04/Ago — DEIXAR DE FAZER TAMBÉM É CONDUTA. Exigir `efeito_relevante_consistente` fazia com que
    # NENHUM estudo negativo pudesse dizer SIM: por construção, um nulo não tem "efeito relevante".
    # Era por isso que o trabalho que TIROU o betabloqueador do pós-IAM saía com "muda conduta: NÃO".
    rc = a.get("relevancia_clinica") or {}
    if (rc.get("classificacao") or "").strip().lower() == "ausencia_de_efeito_demonstrada":
        return "SIM" if (comum and _nulo_esta_demonstrado(rc, a)) else "NÃO"
    ok = (comum
          and a.get("efeito_relevante_consistente", False)
          and a.get("beneficio_supera_risco", True))
    return "SIM" if ok else "NÃO"


def score(a):
    # PASSO −1 — QUAL MOTOR (LEI 8, 02/Ago). Vem ANTES da rota de propósito: se o classificador diz
    # que é DIRETRIZ, é diretriz — mesmo que o extrator tenha devolvido desenho='nao_classificavel'.
    # Era exatamente esse o buraco do laudo da Nature Reviews: o tipo decidido em dois lugares.
    t = tipo_do_documento(a)
    if t == "diretriz":
        return score_diretriz(a)
    if t == "revisao_narrativa":
        return score_revisao(a)

    # PASSO 0 — o artigo pertence à escala clínica? (pré-clínico / não classificável saem ANTES.)
    # aplic=0 de propósito: 0 < 6, então a porta do analisador já RETÉM sozinha, sem quebrar nenhuma
    # comparação numérica lá na frente (r["aplic"] >= 7 etc.). Quem lê a decisão lê o campo 'rota'.
    r0 = rota(a)
    if r0 != ROTA_CLINICA:
        motivo = ("estudo pré-clínico (animal/in vitro): não há paciente, logo não há aplicabilidade "
                  "clínica para pontuar — nenhum instrumento do NHLBI cobre este desenho"
                  if r0 == ROTA_FRONTEIRA else
                  "o extrator não conseguiu classificar o desenho: o motor NÃO chuta")
        # 'motor' SEMPRE presente: a saída de rota era a única que não trazia a chave, e quem lê
        # r["motor"] (veredito, painel) quebrava. Pego pelo teste_motor em 02/Ago.
        # 03/Ago: e o rótulo era "ORIGINAL" FIXO — uma meta que o extrator não soube ler ia para a
        # revisão humana carimbada como artigo original. O rótulo é a PASTA, mesmo quando não pontua.
        return {"trabalho": None, "aplic": 0, "teto_desenho": None, "teto_externa": None,
                "muda_conduta": "N/A", "rota": r0, "falhas_fatais": [],
                "motor": {"meta": "META", "diretriz": "DIRETRIZ",
                          "revisao_narrativa": "REVISAO"}.get(t, "ORIGINAL"),
                "flags": [motivo]}

    # META tem motor próprio, recuperado do prompt_meta_analise_v2.md dele. ORIGINAL segue na LEI 0.
    #
    # ⚠️ 03/Ago: este ramo olhava `a["desenho"] == "meta"` — a ÚLTIMA sobra das duas fontes de
    # verdade. Um artigo que o Dr. Eduardo move para META_ANALISES, mas cujo extrator leu
    # `desenho=rct`, caía no motor ORIGINAL. O `t` acima já é a decisão da PASTA; é ele que manda.
    # Pego pelo próprio teste_motor (`teste_a_pasta_manda`) antes de rodar.
    dom_meta = frase_meta = None
    eh_meta = (t == "meta" or a.get("desenho") == "meta")
    if eh_meta:
        s, dom_meta, frase_meta = nota_meta(a)
        fl = ([f"meta [{k} {v}]" for k, v in dom_meta.items()] if dom_meta
              else [frase_meta])          # sem fatos: registra que a ponderação NÃO foi aplicada
    else:
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
    r = {"trabalho": s, "aplic": aplic, "teto_desenho": td, "teto_externa": te,
         "teto_falha_fatal": tf, "teto_mcid": tm, "muda_conduta": muda_conduta(a, aplic),
         "rota": ROTA_CLINICA, "falhas_fatais": ff,
         # o rótulo é a TRILHA que rodou, não o resultado dela. Vinha de `dom_meta` — logo, uma meta
         # sem os 6 domínios extraídos era carimbada "ORIGINAL" e o redator recebia a perícia errada.
         "motor": "META" if eh_meta else "ORIGINAL",
         "nhlbi": {"cumpre": cum, "falha": falh, "nao_reporta": sil, "teto": tn,
                   "criterios_falhos": criterios_falhos},
         "flags": fl}
    if dom_meta:
        r["dominios_meta"] = dom_meta
        r["faixa_meta"] = frase_meta
    return r


# ═══════════ O VEREDITO ABERTO — 02/Ago/2026 ═══════════
# POR QUE EXISTE (MEDIDO, não suposto). Em 02/Ago o Dr. Eduardo rodou a MESMA revisão narrativa duas
# vezes no comparativo, mudando só o número do veredito colado no painel: 6/10 e 9/10.
# Resultado medido nas duas perícias do claude-sonnet-5:
#     • 86% dos parágrafos MUDARAM (só 6 de 48 idênticos)
#     • a versão 9/10 ficou 14% MAIOR e trouxe 14 números A MAIS sobre o mesmo artigo
#     • o MESMO fato — "os autores declaram um método de busca" — foi usado para justificar
#       o 6 numa versão ("mas não configura busca sistemática") e o 9 na outra ("faz melhor
#       do que a média do gênero")
#     • ZERO contradição numérica: os 72 números da versão 6/10 aparecem todos na 9/10
#
# Ou seja: a nota NÃO é um rótulo colado no fim — é o VOLANTE. O redator recebia o NÚMERO NU e
# inventava a justificativa que coubesse. E a nota baixa fazia o modelo entregar MENOS informação
# sobre o mesmo artigo — o assinante de um artigo 6/10 lia uma perícia mais pobre, não só mais dura.
#
# O CONSERTO (aprovado pelo Dr. Eduardo, 02/Ago): o redator deixa de receber o número sozinho e passa
# a receber os DOMÍNIOS MEDIDOS que produziram o número. A explicação passa a se ancorar no fato
# medido, não no dígito.
#
# ⚠️ A PRIMEIRA LINHA É CONTRATO DE MÁQUINA: `Nota N/10 | Rigor N/10 | Muda conduta X`, exatamente
# assim. É o que `analisador.conferir_veredito` lê com regex antes de gastar token. Rótulo bonito
# ("Rigor de desenvolvimento (AGREE)") vai nas linhas de BAIXO — nunca na primeira.
_ROTULOS = {
    # meta
    "pico": "PICO / elegibilidade", "busca": "busca da literatura",
    "vies_estudos": "viés dos estudos incluídos", "heterogeneidade": "heterogeneidade",
    "vies_publicacao": "viés de publicação", "conclusoes": "conclusões vs evidência",
    # diretriz (AGREE)
    "vinculo_evidencia": "vínculo recomendação↔evidência", "independencia": "independência editorial",
    "metodo_recomendacao": "método de formular a recomendação", "revisao_externa": "revisão externa",
    "atualizacao": "plano de atualização",
    # revisão narrativa
    "vies_selecao": "viés de seleção", "abrangencia": "abrangência / escopo",
    "atualidade": "atualidade", "conflitos": "conflitos de interesse",
    "lacunas": "lacunas reconhecidas",
    "conduta_acionavel": "conduta acionável", "magnitude": "magnitude quantificada",
    "custo_acesso": "custo e acesso no Brasil", "seguranca": "segurança / efeitos adversos",
    "em_quem_nao_usar": "em quem NÃO usar",
}


def _bloco(titulo, dominios, pesos, nota):
    if not dominios:
        return []
    L = [f"  {titulo} — média ponderada = {nota}/10"]
    for k, v in dominios.items():
        L.append(f"      {_ROTULOS.get(k, k):34} {v:>2}/10   × peso {pesos[k]:.2f}")
    return L


def veredito_completo(r):
    """A linha do veredito + os DOMÍNIOS MEDIDOS que a produziram. Um lugar só: o analisador (que
    monta o contexto do redator) e a Chave 9 leem daqui — senão vira mais uma fonte de verdade."""
    if r.get("rota", ROTA_CLINICA) != ROTA_CLINICA:
        return f"SEM NOTA — {r['rota']} | {'; '.join(r['flags'])}"

    # ── linha 1: CONTRATO DE MÁQUINA. Não mexer no formato. ──
    L = [f"Nota {r['aplic']}/10 | Rigor {r['trabalho']}/10 | Muda conduta {r['muda_conduta']}", ""]
    motor = r.get("motor", "ORIGINAL")
    L.append(f"COMO O MOTOR CHEGOU NESTAS NOTAS (motor {motor}) — a sua explicação das notas tem de "
             "sair DESTES domínios medidos, não do número:")

    if motor == "META":
        L += _bloco("RIGOR (6 domínios da meta-análise)", r.get("dominios_meta"),
                    PESOS_META, r["trabalho"])
        if r.get("faixa_meta"):
            L.append(f"      → {r['faixa_meta']}")
    elif motor == "DIRETRIZ":
        L += _bloco("RIGOR DE DESENVOLVIMENTO (AGREE II)", r.get("dominios_agree"),
                    PESOS_DIRETRIZ, r["trabalho"])
        if r.get("faixa_agree"):
            L.append(f"      → {r['faixa_agree']}")
        L.append("  APLICABILIDADE — a nota é o MENOR destes tetos e do rigor:")
        p = r.get("pct_nivel_c")
        L.append(f"      tipo do documento                  teto {r['teto_desenho']}")
        L.append(f"      % em nível C (opinião)             " +
                 (f"{p:.0f}% → teto {r['teto_nivel_c']}" if p is not None
                  else "não contabilizado → não capa"))
        pi = r.get("pct_classe_i_em_c")
        if pi is not None:
            L.append(f"      Classe I apoiada em nível C        {pi:.0f}% → teto {r['teto_classe_i_em_c']}")
        L.append(f"      executável no Brasil               teto {r['teto_externa']}")
    elif motor == "REVISAO":
        L += _bloco("RIGOR — dá para confiar?", r.get("dominios_revisao_rigor"),
                    PESOS_REVISAO_RIGOR, r["trabalho"])
        L += _bloco("UTILIDADE PRÁTICA — entrega o quê?", r.get("dominios_revisao_util"),
                    PESOS_REVISAO_UTIL, r.get("utilidade"))
        if r.get("faixa_revisao"):
            L.append(f"      → {r['faixa_revisao']}")
        if r.get("teto_atualidade", 10) < 10:
            L.append(f"  TETO: referência mais recente tem {r.get('defasagem_anos'):.0f} ano(s) "
                     f"→ teto {r['teto_atualidade']}")
    else:   # ORIGINAL
        L.append(f"  APLICABILIDADE = o MENOR entre: teto do desenho {r['teto_desenho']} · "
                 f"validade externa {r['teto_externa']} · falha fatal {r.get('teto_falha_fatal', 10)} · "
                 f"MCID {r.get('teto_mcid', 10)} · rigor {r['trabalho']}")
        n = r.get("nhlbi") or {}
        if n.get("cumpre") or n.get("falha"):
            L.append(f"  NHLBI: cumpriu {n['cumpre']} de {n['cumpre'] + n['falha']} critérios respondidos"
                     + (f" — falhou em: {', '.join(n['criterios_falhos'][:5])}"
                        if n.get("criterios_falhos") else ""))
        if r.get("falhas_fatais"):
            L.append(f"  FALHAS FATAIS: {', '.join(r['falhas_fatais'])}")
        L.append("  DELATORES MEDIDOS:")
        for f in (r.get("flags") or ["nenhum"]):
            L.append(f"      • {f}")
    return "\n".join(L)


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
