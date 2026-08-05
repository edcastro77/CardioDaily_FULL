"""
analise.py — o bloco ANALISE (homem das cavernas) ligado ao NOTAS.
Corrente ponta a ponta: PDF → analise (LLM extrai FATOS) → dado canônico → notas (nota determinística).
Uso: python analise.py <ARTIGO.pdf> [pergunta_gabarito]
"""
import os, sys, json, re, fitz
from dotenv import load_dotenv
import notas_prototipo as N

_HERE = os.path.dirname(os.path.abspath(__file__))
# acha o CardioDaily_FULL/.env subindo as pastas (funciona no lab, em ferramentas, onde for)
_d = _HERE
for _ in range(8):
    _cand = os.path.join(_d, "CardioDaily_FULL", ".env")
    if os.path.exists(_cand):
        load_dotenv(_cand, override=True); break
    _d = os.path.dirname(_d)
else:
    load_dotenv(override=True)
import anthropic

PROMPT = open(os.path.join(_HERE, "analise_prompt.md")).read()
PROMPT_DIRETRIZ = open(os.path.join(_HERE, "analise_diretriz_prompt.md")).read()
PROMPT_META = open(os.path.join(_HERE, "analise_meta_prompt.md")).read()   # 04/Ago: extrator próprio
PROMPT_REVISAO = open(os.path.join(_HERE, "analise_revisao_prompt.md")).read()

# 04/Ago — qual ARQUIVO de extrator serve cada tipo. Serve ao carimbo de versão do analisador:
# sem saber o nome do arquivo, não dá para calcular o hash e o reuso fica cego.
PROMPT_ARQ_POR_TIPO = {
    "original":          "analise_prompt.md",
    "meta":              "analise_meta_prompt.md",
    "diretriz":          "analise_diretriz_prompt.md",
    "revisao_narrativa": "analise_revisao_prompt.md",
}

_B = {"type": "boolean"}
_S = {"type": "string"}
_NUM = {"type": ["number", "null"]}
_INT = {"type": ["integer", "null"]}
_B3 = {"type": ["boolean", "null"]}   # true=fez · false=NÃO fez · null=NÃO REPORTA (NHLBI distingue os três)

# CHECKLIST NHLBI/NIH — critérios formais por desenho (docs/METODO_AVALIACAO_ESTUDOS.md).
# O LLM extrai os critérios como FATOS; a CONTAGEM e os TETOS ficam no motor (notas_prototipo), no código.
SCHEMA_NHLBI = {
    "type": "object",
    "properties": {
        "instrumento": {"type": "string",
                        "enum": ["controlled_intervention", "systematic_review", "observational_cohort",
                                 "case_control", "before_after", "case_series", "nenhum"]},
        # RCT — NHLBI Controlled Intervention (14)
        "randomizacao_adequada": _B3, "alocacao_sigilosa": _B3, "participantes_cegados": _B3,
        "avaliadores_desfecho_cegados": _B3, "grupos_similares_basal": _B3,
        "dropout_total_pct": _NUM, "dropout_diferencial_pp": _NUM,
        "adesao_alta": _B3, "cointervencoes_similares": _B3, "poder_80_declarado": _B3,
        "desfechos_prespecificados": _B3, "itt_verdadeiro": _B3,
        # META — NHLBI Systematic Review (8)
        "pergunta_focada": _B3, "elegibilidade_predefinida": _B3, "busca_sistematica_abrangente": _B3,
        "revisao_em_duplicata": _B3, "qualidade_estudos_avaliada": _B3,
        "estudos_listados_com_caracteristicas": _B3,
        "vies_publicacao_avaliado": _B3, "heterogeneidade_avaliada": _B3, "i2_valor": _NUM,
        # OBSERVACIONAL — NHLBI Cohort/Cross-Sectional (14)
        "participacao_elegiveis_pct": _NUM, "populacao_mesma_origem": _B3,
        "exposicao_antes_desfecho": _B3, "janela_temporal_suficiente": _B3,
        "exposicao_medida_repetida": _B3, "exposicao_valida_consistente": _B3,
        "desfecho_valido_consistente": _B3, "avaliadores_cegados_exposicao": _B3,
        "perda_seguimento_pct": _NUM, "confundidores_ajustados": _B3,
        # CASO-CONTROLE — NHLBI (12)
        "controles_mesma_populacao": _B3, "casos_definidos_diferenciados": _B3,
        "selecao_aleatoria_elegiveis": _B3, "controles_concorrentes": _B3,
        "exposicao_precedeu_condicao": _B3, "avaliadores_exposicao_cegados": _B3,
        # ANTES-DEPOIS SEM CONTROLE — NHLBI (11)
        "participantes_representativos": _B3, "todos_elegiveis_incluidos": _B3,
        "estatistica_examina_mudanca": _B3, "serie_temporal_interrompida": _B3,
        # SÉRIE DE CASOS — NHLBI (9)
        "casos_consecutivos": _B3, "sujeitos_comparaveis": _B3, "seguimento_adequado": _B3,
        # comuns
        "pergunta_objetivo_claro": _B3, "populacao_definida": _B3, "tamanho_amostral_justificado": _B3,
    },
    "required": ["instrumento"],
}

# SCHEMA DOS FATOS — contrato de saída estruturada (tool use). A API OBRIGA o modelo a devolver
# exatamente estes campos com estes tipos. JSON malformado ou campo faltando deixa de ser possível.
SCHEMA_FATOS = {
    "type": "object",
    "properties": {
        "titulo": _S, "revista": _S, "ano": _S,
        "pergunta": {"type": "string", "enum": ["intervencao", "etiologia", "prognostico", "diagnostico"]},
        # TAXONOMIA (30/Jul/2026): + pre_clinico, antes_depois_sem_controle, serie_de_casos e a ESCOTILHA
        # 'nao_classificavel'. O enum fechado ANTIGO (7 opções) OBRIGAVA o modelo a chutar: um estudo em
        # camundongo virou "observacional_ajustado" e recebeu NAC 8 (Circulation, 27/Jul). Dizer "não sei"
        # passou a ser possível — e é preferível a forçar categoria errada.
        "desenho": {"type": "string", "enum": ["rct", "meta", "coorte", "registro",
                                               "observacional_ajustado", "transversal", "caso_controle",
                                               "antes_depois_sem_controle", "serie_de_casos",
                                               "pre_clinico", "nao_classificavel"]},
        "retrospectivo": _B,
        "fracao_ejecao": {"type": "string",
                          "enum": ["preservada", "levemente_reduzida", "reduzida", "nao_se_aplica"]},
        "open_label": _B, "poder_ok": _B, "desfecho_duro": _B, "extrapolavel": _B,
        "eventos_min_grupo": _INT, "eventos_nao_alcancados": _B, "parado_cedo_por_beneficio": _B,
        "efeito_grande": _B, "taxa_obs": _NUM, "taxa_esp": _NUM, "margem_ni": _NUM, "taxa_basal": _NUM,
        "conclusao_nao_bate_desenho": _B, "itt_falso": _B, "qualidade_entrada": _B,
        "follow_up_completo": _B, "desenho_apropriado": _B, "dicotomizou_continuo": _B,
        "contaminacao_incluidos": _B, "ni_mal_interpretada": _B, "i2_alto_sem_investigar": _B,
        "efeito_relevante_consistente": _B, "sem_evidencia_conflitante_melhor": _B,
        "beneficio_supera_risco": _B,
        "financiamento_papel": _S, "achados_principais": _S, "aplicabilidade": _S,
        "keywords": {"type": "array", "items": {"type": "string"},
                     "description": "8-12 termos em PORTUGUÊS BRASILEIRO, como o médico busca (ex.: 'fibrilação atrial', não 'atrial fibrillation'). Exceção: sigla consagrada (TAVI, SGLT2, DOAC, FEVE) e nome de ensaio. Cubra 4 eixos sem repetir: doença · intervenção/droga · população · desfecho/conduta. Específico: 'cardiologia', 'tratamento' e 'manejo' não filtram nada."},
        "relevancia_clinica": {
            "type": "object",
            "properties": {
                "desfecho_primario": _S, "tipo_desfecho": _S, "efeito_observado": _S,
            # ═══ 05/Ago — OS NÚMEROS CRUS, para o motor aplicar o LIMIAR DO CARDIODAILY ═══
            # Medido: 21 de 24 metas NÃO declaram MCID. Sem limiar do artigo, o extrator respondia
            # `efeito_excede_limiar: null` — corretamente, pois não tinha contra o que comparar — e
            # os tetos 6 e 7 nunca disparavam. Decisão do Dr. Eduardo (opção B): quando o artigo
            # cala, o CardioDaily aplica O SEU limiar (`mcid_cardiodaily.py`).
            # Para isso o motor precisa dos NÚMEROS, não do julgamento:
            "arr_pct": _NUM,               # redução ABSOLUTA de risco, em pontos percentuais
            "arr_ic_inf_pct": _NUM,        # limite INFERIOR do IC95% da ARR (o mais conservador)
            "seguimento_anos": _NUM,       # para converter a ARR em ARR/ano
            "delta_substituto": _NUM,      # a variação do desfecho substituto (valor absoluto)
            "delta_substituto_unidade": _S,  # mg/dL · mmHg · pontos · metros · % · mL/kg/min
                "mcid_reportado": _B, "mcid_valor": _S, "mcid_fonte_metodo": _S,
                "para_desfecho_duro": _S,
                "efeito_excede_limiar": {"type": ["boolean", "null"]},
                "ic_sustenta_relevancia": {"type": ["boolean", "null"]},
                # ═══ 04/Ago/2026 — O BURACO DO ESTUDO NEGATIVO ═══
                # O IC 95% DESCARTA um benefício clinicamente relevante? É o que separa
                # "provamos que não funciona" de "não conseguimos mostrar que funciona".
                # Sem este campo, as duas coisas viravam `nao_relevante` e levavam teto 6.
                "ic_exclui_beneficio_relevante": {"type": ["boolean", "null"]},
                "classificacao": {"type": "string",
                                  "enum": ["robusto", "provavel", "incerto",
                                           # NOVO: o nulo INFORMATIVO. Poder adequado + IC estreito
                                           # que exclui benefício relevante = RESPOSTA, não fracasso.
                                           # Foi o que tirou o B do MONABICHA. Vale até 10.
                                           "ausencia_de_efeito_demonstrada",
                                           "significativo_mas_abaixo_do_mcid", "nao_relevante", "nao_avaliavel"]},
                "frase_chave": _S,
            },
            "required": ["desfecho_primario", "efeito_observado", "classificacao", "frase_chave"],
        },
        # CHECKLIST FORMAL por desenho (NHLBI) — os critérios como FATOS, não como nota
        "qualidade_nhlbi": SCHEMA_NHLBI,
        # FALHAS FATAIS (F1–F8): reprovam, não descontam. Ancoradas em instrumento internacional.
        "falhas_fatais": {"type": "array",
                          "items": {"type": "string",
                                    "enum": ["F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8"]}},
    },
    # obrigatórios: o que o motor de rigor e o canônico NÃO podem receber vazio
    "required": ["titulo", "revista", "ano", "pergunta", "desenho", "retrospectivo", "fracao_ejecao", "open_label", "poder_ok",
                 "desfecho_duro", "extrapolavel", "conclusao_nao_bate_desenho", "itt_falso",
                 "qualidade_entrada", "achados_principais", "keywords", "relevancia_clinica",
                 "aplicabilidade", "qualidade_nhlbi", "falhas_fatais"],
}


# ═══════════ SCHEMA DOS FATOS DA META-ANÁLISE — 04/Ago/2026 ═══════════
# CONSTRUÍDO PORQUE O MOTOR PROCURAVA UM BLOCO QUE NÃO EXISTIA.
# O `nota_meta` lê `a["qualidade_meta"]` desde que foi escrito — e o extrator NUNCA produziu esse
# bloco. Resultado medido: os 6 domínios do Dr. Eduardo rodavam com metade dos dados em branco.
# `conclusoes` (25% do peso) ficava travado em 6 para sempre; `vies_estudos` (15%) idem. O teto
# prático de uma meta PERFEITA era ~7,7 — nenhuma conseguia nota alta, por construção.
# Junto com o buraco do estudo negativo, é a explicação do 4/10 da meta de betabloqueador do NEJM.
#
# Instrumentos: PRISMA 2020 (BMJ 2021;372:n71/n160) · Cochrane Handbook v6.5 · AMSTAR-2 · GRADE.
SCHEMA_FATOS_META = {
    "type": "object",
    "properties": {
        # ── identificação — 04/Ago 06h: O QUE FALTAVA E RECUSOU 10 ARTIGOS ═══════════════════
        # Montei este schema pelos blocos METODOLÓGICOS (PRISMA, Cochrane, AMSTAR-2, GRADE) e não
        # copiei a IDENTIFICAÇÃO que o extrator do artigo original já pedia. Resultado: 10 metas
        # analisadas com nota 6 a 9, com perícia, PDF, áudio e visual prontos — e TODAS recusadas
        # pelo contrato com "titulo vazio · revista vazia · data_publicacao ausente".
        # O portão estava certo (LEI: o site não recebe buraco). O buraco era meu, no schema.
        "titulo": _S, "revista": _S, "ano": _S, "doi": _S, "autores": _S,
        # ── desenho ──
        "desenho": {"type": "string", "enum": ["meta"]},
        "pergunta": {"type": "string", "enum": ["intervencao", "etiologia", "prognostico", "diagnostico"]},
        "tipo_meta": {"type": "string",
                      "enum": ["ipd", "dados_agregados", "rede", "prospectiva", "nao_reportado"]},
        "desenhos_incluidos": {"type": "string",
                               "enum": ["rcts", "observacionais", "mistos", "nao_reportado"]},
        "achados_principais": _S, "aplicabilidade": _S, "keywords": {"type": "array", "items": _S, "description": "8-12 termos em PORTUGUÊS BRASILEIRO, como o médico busca (ex.: 'fibrilação atrial', não 'atrial fibrillation'). Exceção: sigla consagrada (TAVI, SGLT2, DOAC, FEVE) e nome de ensaio. Cubra 4 eixos sem repetir: doença · intervenção/droga · população · desfecho/conduta. Específico: 'cardiologia', 'tratamento' e 'manejo' não filtram nada."},

        # ── o bloco que o motor procurava e nunca recebeu ──
        "qualidade_meta": {
            "type": "object",
            "properties": {
                # tamanho
                "k_estudos": _INT, "n_total": _INT,
                # BUSCA (PRISMA 6-9 · AMSTAR-2 críticos)
                "n_bases": _INT, "data_busca": _S,
                "protocolo_registrado": _B3,           # PROSPERO/registro ANTES da revisão
                "extracao_em_duplicata": _B3,          # dois revisores independentes
                "literatura_cinzenta": _B3,
                "restricao_idioma": _B3,
                "excluidos_listados_com_motivo": _B3,  # o item que quase ninguém cumpre
                # ESTATÍSTICA (PRISMA 13 · Cochrane cap.10)
                "modelo_estatistico": {"type": "string",
                                       "enum": ["fixo", "aleatorio", "ambos", "nao_reportado"]},
                "modelo_apropriado_p_heterogeneidade": _B3,
                "medida_efeito": _S,
                "tau2_reportado": _B3,
                "intervalo_predicao_reportado": _B3,
                "intervalo_predicao_cruza_nulo": _B3,  # o IC agregado exclui o nulo e a predição não?
                "peso_maior_estudo_pct": _NUM,         # dominância: a meta É aquele estudo?
                "unidade_analise_problema": _B3,       # cluster/crossover/multi-braço contado 2×
                "heterogeneidade_investigada": _B3,
                "heterogeneidade_clinica_relevante": _B3,   # populações/doses/tempos diferentes
                # VIÉS DE PUBLICAÇÃO (Cochrane cap.13)
                "funnel_plot_feito": _B3, "egger_p": _NUM,
                "teste_funnel_indicado": _B3,          # false se k<10 (Cochrane: não testar)
                # VIÉS DOS INCLUÍDOS (AMSTAR-2)
                "rob_ferramenta": _S,
                "vies_mudou_interpretacao": _B3,
        # ── INDEPENDÊNCIA EDITORIAL — 05/Ago: a meta era o ÚNICO schema que não perguntava ──
        # Medido em 05/Ago: DIRETRIZ tinha 6 campos sobre dinheiro (20% da nota), REVISÃO tinha 2
        # (15%), ORIGINAL tinha 1 e o ignorava, e a META não tinha NENHUM. Não foi decidido: foi
        # acumulado, cada motor herdando o que veio da régua de origem. Régua do Dr. Eduardo:
        # até 10% nos três que não são diretriz. O AMSTAR-2 cobra as duas pontas — o financiamento
        # DA REVISÃO e o dos estudos incluídos.
        "conflitos_declarados": _B3,          # a revisão declara conflitos dos autores?
        "financiamento_industria": _B3,       # a revisão foi financiada pela indústria?
        "autores_industria_fora_da_analise": _B3,   # o financiador ficou FORA da análise/escrita?
        "financiamento_dos_incluidos_relatado": _B3,  # AMSTAR-2 item 10: relatou o dos estudos?
        # ═══════ A ESCADA DE AVALIAÇÃO CRÍTICA — 04/Ago/2026 ═══════════════════════════════
        # Especificação do Dr. Eduardo, a partir do caso TOCILIZUMABE/COVID-19. Em 2021 as
        # meta-análises (inclusive a nota técnica do Ministério da Saúde) diziam que o
        # tocilizumabe não reduzia mortalidade — misturando ECR com observacional. O RECOVERY,
        # UM ensaio com N adequado e desenho válido, encerrou a discussão sozinho.
        # Nas palavras dele: uma meta-análise só é tão boa quanto os estudos que a compõem;
        # somar estudos frágeis produz "uma estimativa matematicamente bonita e clinicamente
        # enganosa". GIGO — garbage in, garbage out.
        #
        # DEGRAU 2 · qualidade de entrada (as duas primeiras viram FALHA FATAL, teto 5)
        "mistura_ecr_observacional_no_primario": _B,   # ACC/AHA + Cochrane: NUNCA se combinam
        "so_ecr_baixo_risco_vies": _B,                 # crivo 1 do algoritmo de beira do leito
        # DEGRAU 3 · heterogeneidade — reportar não basta, tem de EXPLORAR
        "q_cochran_p": _NUM,                           # p<0,05 = heterogeneidade não é acaso
        "analise_sensibilidade_leave_one_out": _B,     # um outlier explica tudo?
        "subgrupo_pre_especificado": _B,               # pré-especificado, não pescado
        "meta_regressao": _B,                          # idade/dose/gravidade explicam a variação?
        # DEGRAU 4 · viés de publicação — Duval & Tweedie
        "trim_and_fill_feito": _B,
        "trim_and_fill_perdeu_significancia": _B,      # FALHA FATAL: "se perdeu, não use"
        # DEGRAU 5 · utilidade clínica — o topo da escada
        "desfecho_primario_duro": _B,                  # mortalidade/IAM, não Lp(a) nem GLS nem FEVE
        "nnt_agrupado": _NUM,                          # extra que valoriza, não régua
        "tsa_feita": _B,                               # Trial Sequential Analysis
        "tsa_cruzou_fronteira": _B,                    # cruzou = novo estudo não vira o resultado       # usou o RoB ao concluir, ou foi check-box?
                # CERTEZA (PRISMA 15 · GRADE)
                "grade_usado": _B3,
                "certeza_desfecho_primario": {"type": "string",
                                              "enum": ["alta", "moderada", "baixa", "muito_baixa",
                                                       "nao_reportado"]},
                # CONCLUSÕES (25% do peso)
                "conclusao_alem_da_evidencia": _B3,
                "subgrupo_tratado_como_principal": _B3,
                "limitacoes_reconhecidas": _B3,
                # só para meta de rede / umbrella
                "transitividade_avaliada": _B3,
                "sobreposicao_estudos_relevante": _B3,
            },
            "required": ["k_estudos", "modelo_estatistico"],
        },

        # ── o checklist NHLBI de revisão sistemática (o motor também lê daqui) ──
        "qualidade_nhlbi": {
            "type": "object",
            "properties": {
                "pergunta_focada": _B3, "elegibilidade_predefinida": _B3,
                "busca_sistematica_abrangente": _B3, "revisao_em_duplicata": _B3,
                "qualidade_estudos_avaliada": _B3, "estudos_listados_com_caracteristicas": _B3,
                "vies_publicacao_avaliado": _B3, "heterogeneidade_avaliada": _B3,
                "i2_valor": _NUM,
            },
        },

        # ── relevância clínica: MESMO bloco do artigo original (a régua é comum) ──
        "relevancia_clinica": {
            "type": "object",
            "properties": {
                "desfecho_primario": _S, "tipo_desfecho": _S, "efeito_observado": _S,
                "mcid_reportado": _B, "mcid_valor": _S,
                "efeito_excede_limiar": _B3,
            # ═══ 05/Ago — OS 3 QUE FALTAVAM PARA A META TER O MCID COMPLETO ═══
            # A varredura dos 4 schemas mostrou que a meta tinha 9 dos 12 campos de relevância
            # clínica. Uma meta-análise TEM efeito agregado com magnitude e IC — a pergunta do MCID
            # se aplica a ela inteira, e o motor agora CONFERE a conta (não aceita só o rótulo).
            # Diretriz e revisão narrativa NÃO ganham este bloco (decisão dele, opção A, 05/Ago):
            # elas não têm UM efeito, e forçar a pergunta faria o modelo escolher uma recomendação
            # arbitrária para representar o documento inteiro — o erro do instrumento errado.
            # ═══ 05/Ago — OS NÚMEROS CRUS, para o motor aplicar o LIMIAR DO CARDIODAILY ═══
            # Medido: 21 de 24 metas NÃO declaram MCID. Sem limiar do artigo, o extrator respondia
            # `efeito_excede_limiar: null` — corretamente, pois não tinha contra o que comparar — e
            # os tetos 6 e 7 nunca disparavam. Decisão do Dr. Eduardo (opção B): quando o artigo
            # cala, o CardioDaily aplica O SEU limiar (`mcid_cardiodaily.py`).
            # Para isso o motor precisa dos NÚMEROS, não do julgamento:
            "arr_pct": _NUM,               # redução ABSOLUTA de risco, em pontos percentuais
            "arr_ic_inf_pct": _NUM,        # limite INFERIOR do IC95% da ARR (o mais conservador)
            "seguimento_anos": _NUM,       # para converter a ARR em ARR/ano
            "delta_substituto": _NUM,      # a variação do desfecho substituto (valor absoluto)
            "delta_substituto_unidade": _S,  # mg/dL · mmHg · pontos · metros · % · mL/kg/min
            "mcid_fonte_metodo": _S,       # fonte (revisão | estudo prévio | diretriz | consenso)
                                           # + método (anchor-based | distribution-based)
            "para_desfecho_duro": _S,      # diferença absoluta agregada, NNT/NNH e tamanho GRADE
            "ic_sustenta_relevancia": _B3, # o IC95% INTEIRO fica além do limiar, ou só o ponto?
                "ic_exclui_beneficio_relevante": _B3,
                "classificacao": {"type": "string",
                                  "enum": ["robusto", "provavel", "incerto",
                                           "ausencia_de_efeito_demonstrada",
                                           "significativo_mas_abaixo_do_mcid", "nao_relevante",
                                           "nao_avaliavel"]},
                "frase_chave": _S,
            },
            "required": ["desfecho_primario", "efeito_observado", "classificacao", "frase_chave"],
        },

        # ── delatores que o motor já usa (tetos clássicos da meta) ──
        "extrapolavel": _B3, "poder_ok": _B3, "desfecho_duro": _B3,
        "i2_alto_sem_investigar": _B3, "contaminacao_incluidos": _B3, "ni_mal_interpretada": _B3,
        "conclusao_nao_bate_desenho": _B3,
        "falhas_fatais": {"type": "array", "items": _S},
    },
    "required": ["titulo", "revista", "ano", "desenho", "pergunta", "qualidade_meta",
                 "relevancia_clinica", "achados_principais", "aplicabilidade"],
}


# ═══════════ SCHEMA DOS FATOS DA DIRETRIZ — 02/Ago/2026 ═══════════
# Extrator SEPARADO, por LEI 8: tipo diferente → prompt diferente → motor diferente. Perguntar
# "qual foi a randomização" a um consenso é o mesmo superficializar, uma camada antes da perícia.
# Estes fatos alimentam `notas_prototipo.score_diretriz()` (AGREE ponderado + tetos de nível C).
SCHEMA_RECOMENDACOES = {
    "type": "object",
    "properties": {
        "sistema_graduacao": {"type": "string",
                              "enum": ["ACC/AHA", "ESC", "GRADE", "SBC", "outro", "nenhum"]},
        "total": _INT,
        "n_classe_I": _INT, "n_classe_IIa": _INT, "n_classe_IIb": _INT, "n_classe_III": _INT,
        "n_nivel_A": _INT, "n_nivel_B": _INT, "n_nivel_C": _INT,
        # o cruzamento das duas colunas: ordem FORTE apoiada em opinião. Teto próprio de 7.
        "n_classe_I_nivel_C": _INT,
        "n_recomendacoes_novas": _INT, "n_recomendacoes_rebaixadas": _INT,
    },
    "required": ["sistema_graduacao"],
}

SCHEMA_AGREE = {
    "type": "object",
    "properties": {
        # D3 — rigor de desenvolvimento (o coração do instrumento)
        "busca_sistematica_declarada": _B3, "n_bases": _INT, "criterios_selecao_evidencia": _B3,
        "forcas_limitacoes_descritas": _B3, "metodo_formular_recomendacao": _B3,
        "riscos_beneficios_considerados": _B3, "vinculo_recomendacao_evidencia": _B3,
        "revisao_externa": _B3, "plano_atualizacao": _B3,
        # D2 — partes interessadas
        "painel_multidisciplinar": _B3, "paciente_no_painel": _B3, "usuarios_alvo_definidos": _B3,
        "n_membros": _INT,
        # D4 — clareza (informativo; fora do rigor de propósito)
        "recomendacoes_inequivocas": _B3, "opcoes_apresentadas": _B3,
        # D6 — independência editorial
        "financiamento_declarado": _B3, "financiamento_industria": _B3,
        "conflitos_declarados": _B3, "politica_gestao_conflitos": _B3,
        "n_membros_com_conflito": _INT, "pct_membros_com_conflito": _NUM,
    },
}

SCHEMA_FATOS_DIRETRIZ = {
    "type": "object",
    "properties": {
        "titulo": _S, "revista": _S, "ano": _S, "sociedade": _S,
        "idade_anos": _NUM, "ano_versao_anterior": {"type": ["string", "null"]},
        # ESTE é o campo que o motor lê para decidir o motor (LEI 8, fonte única do tipo)
        "tipo_documento": {"type": "string", "enum": ["diretriz"]},
        "tipo_documento_norm": {"type": "string",
                                "enum": ["diretriz", "consenso", "scientific_statement", "position_paper"]},
        "aplicavel_brasil": _B,
        "recomendacoes": SCHEMA_RECOMENDACOES,
        "agree": SCHEMA_AGREE,
        "temas_principais": {"type": "array", "items": {"type": "string"}},
        "o_que_mudou": _S,
        "keywords": {"type": "array", "items": {"type": "string"},
                     "description": "8-12 termos em PORTUGUÊS BRASILEIRO, como o médico busca (ex.: 'fibrilação atrial', não 'atrial fibrillation'). Exceção: sigla consagrada (TAVI, SGLT2, DOAC, FEVE) e nome de ensaio. Cubra 4 eixos sem repetir: doença · intervenção/droga · população · desfecho/conduta. Específico: 'cardiologia', 'tratamento' e 'manejo' não filtram nada."},
        "aplicabilidade": _S,
        "falhas_fatais": {"type": "array", "items": {"type": "string", "enum": ["G1"]}},
    },
    "required": ["titulo", "revista", "ano", "sociedade", "tipo_documento", "tipo_documento_norm",
                 "aplicavel_brasil", "recomendacoes", "agree", "o_que_mudou", "keywords",
                 "aplicabilidade", "falhas_fatais"],
}


# ═══════════ SCHEMA DOS FATOS DA REVISÃO NARRATIVA — 02/Ago/2026 ═══════════
# Duas famílias de campo, porque a revisão tem DUAS notas com escalas diferentes:
#   RIGOR     → viés de seleção · abrangência · atualidade · conflitos · lacunas (Seção 4 do
#               prompt_revisao_geral_v2.md, escrita pelo Dr. Eduardo)
#   UTILIDADE → conduta acionável · magnitude · custo/acesso · segurança · em quem NÃO usar
#               (as 5 dimensões do exemplo dele: "custam 750 mil reais no Brasil")
SCHEMA_QUALIDADE_REVISAO = {
    "type": "object",
    "properties": {
        # RIGOR — viés de seleção (peso 0,30: "o principal viés é a SELEÇÃO INVISÍVEL")
        "afirmacoes_sem_citacao": {"type": ["string", "null"],
                                   "enum": ["raras", "algumas", "frequentes", None]},
        "atribui_nivel_evidencia": _B3, "apresenta_contra_evidencia": _B3, "tom_promocional": _B3,
        # RIGOR — abrangência · atualidade · conflitos · lacunas
        "metodo_busca_declarado": _B3, "escopo_declarado": _B3, "n_referencias": _INT,
        "ano_referencia_mais_recente": _INT, "pct_referencias_ultimos_5_anos": _NUM,
        "conflitos_declarados": _B3, "financiamento_industria": _B3, "limitacoes_reconhecidas": _B3,
        # UTILIDADE — o campo de maior peso é a CONTAGEM de conduta acionável: é ele que separa
        # a revisão que "fala por cima" da que muda a segunda-feira.
        "n_condutas_acionaveis": _INT, "traz_valores_corte_ou_doses": _B3,
        "traz_magnitude_efeito": _B3, "traz_custo_acesso": _B3, "traz_seguranca": _B3,
        "traz_em_quem_nao_usar": _B3, "tem_tabela_comparativa": _B3,
    },
}

SCHEMA_FATOS_REVISAO = {
    "type": "object",
    "properties": {
        "titulo": _S, "revista": _S, "ano": _S,
        "tipo_documento": {"type": "string", "enum": ["revisao_narrativa"]},
        "temas_principais": {"type": "array", "items": {"type": "string"}},
        "qualidade_revisao": SCHEMA_QUALIDADE_REVISAO,
        "o_que_ensina": _S,
        "keywords": {"type": "array", "items": {"type": "string"},
                     "description": "8-12 termos em PORTUGUÊS BRASILEIRO, como o médico busca (ex.: 'fibrilação atrial', não 'atrial fibrillation'). Exceção: sigla consagrada (TAVI, SGLT2, DOAC, FEVE) e nome de ensaio. Cubra 4 eixos sem repetir: doença · intervenção/droga · população · desfecho/conduta. Específico: 'cardiologia', 'tratamento' e 'manejo' não filtram nada."},
        "aplicabilidade": _S,
    },
    "required": ["titulo", "revista", "ano", "tipo_documento", "qualidade_revisao",
                 "o_que_ensina", "keywords", "aplicabilidade"],
}


def _parse_json_tolerante(raw):
    """Converte a resposta do modelo em dict, aguentando as malformações comuns de LLM.
    Devolve None se não der — quem chama decide (pedir de novo ao modelo)."""
    m = re.search(r"\{.*\}", raw or "", re.S)     # ignora cerca ```json e preâmbulo ("aqui está o JSON:")
    if not m:
        return None
    bruto = m.group(0)
    tentativas = [
        lambda s: s,                                                    # 1) como veio
        lambda s: re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", s),       # 2) tira caractere de controle inválido
        lambda s: re.sub(r",(\s*[}\]])", r"\1", s),                     # 3) tira vírgula sobrando antes de } ou ]
        lambda s: re.sub(r",(\s*[}\]])", r"\1",
                         re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", s)),  # 4) as duas juntas
        lambda s: re.sub(r"//[^\n]*", "",
                         re.sub(r",(\s*[}\]])", r"\1", s)),             # 5) + tira comentário // que o modelo às vezes põe
    ]
    for arruma in tentativas:
        try:
            return json.loads(arruma(bruto), strict=False)
        except Exception:
            continue
    return None


def extrair_fatos(pdf_path, tipo=None, cadeia=None):
    """FATOS do artigo via SAÍDA ESTRUTURADA (tool use): a API obriga o modelo a devolver o objeto
    no formato do SCHEMA_FATOS. JSON malformado / campo faltando deixa de ser possível — é a correção
    ESTRUTURAL da causa que derrubou 74% do run de 25/07 (antes: pedia JSON em texto e torcia).
    Rede: se o tool use falhar (provedor sem suporte), cai no caminho de texto + parsing tolerante.

    `tipo` — LEI 8 (02/Ago): o tipo é decidido UMA vez, no classificador, e o EXTRATOR obedece.
    'diretriz' usa prompt e schema próprios (AGREE + contagem de classe/nível); perguntar
    randomização e I² a um consenso é o mesmo superficializar, uma camada antes da perícia.
    Se ninguém informar, deduz da pasta do classificador — o mesmo lugar de onde o prompt deduz."""
    if tipo is None:
        try:
            from analisador import tipo_do_documento
            tipo = tipo_do_documento(pdf_path)
        except Exception:
            tipo = "original"
    # 01/Ago/2026 — CORTE DE 48.000 REVISTO. Era o mesmo entulho do analisador: numa diretriz de
    # 183 páginas (452.404 chars) os FATOS eram extraídos de 10% do documento, e os critérios NHLBI
    # (que vivem em Métodos, no meio) simplesmente não eram vistos. Teto novo com AVISO, nunca calado.
    texto = "".join(p.get_text() for p in fitz.open(pdf_path))
    TETO = 600_000
    if len(texto) > TETO:
        print(f"       ⚠️ extração truncada: {len(texto):,} chars → {TETO:,} "
              f"({100*TETO//len(texto)}% do documento)")
        texto = texto[:TETO]
    import llm_client, modelos as M
    llm_client.contexto_uso(etapa="extracao")                  # p/ o log de uso
    if tipo == "diretriz":
        modelo, esquema = PROMPT_DIRETRIZ, SCHEMA_FATOS_DIRETRIZ
        print("       extração: DIRETRIZ (AGREE + contagem de classe/nível)")
    elif tipo == "revisao_narrativa":
        modelo, esquema = PROMPT_REVISAO, SCHEMA_FATOS_REVISAO
        print("       extração: REVISÃO NARRATIVA (viés de seleção + utilidade prática)")
    elif tipo == "meta":
        # 04/Ago — LEI 8, um degrau mais fundo: perguntar randomização e cegamento a uma meta é o
        # mesmo "superficializar" que o Dr. Eduardo apontou no prompt único do redator em 26/Jul.
        modelo, esquema = PROMPT_META, SCHEMA_FATOS_META
        print("       extração: META-ANÁLISE (PRISMA 2020 + Cochrane + AMSTAR-2 + GRADE)")
    else:
        modelo, esquema = PROMPT, SCHEMA_FATOS
    prompt = modelo.replace("{article_text}", texto)
    # `cadeia` — 03/Ago: só a PROVA usa (prova_extracao.py força UM modelo por vez para medir).
    # Em produção fica None e vale a M.EXTRACAO. O lab não pode ter caminho próprio: se ele medisse
    # um código diferente do que roda, mediria outra coisa — foi o buraco do `prova_classificador`,
    # que media só o LLM enquanto a produção decidia nas camadas de cima.
    cad = cadeia or M.EXTRACAO
    try:
        return llm_client.gerar_json(cad, prompt, esquema,
                                     max_tokens=8000, nome="extrair_fatos")
    except Exception as e:
        print(f"       ↻ saída estruturada indisponível ({type(e).__name__}); tentando modo texto…")
    ultimo = ""
    for tentativa in (1, 2):
        raw = llm_client.gerar(cad, prompt, max_tokens=8000, temperatura=0).strip()
        dados = _parse_json_tolerante(raw)
        if dados is not None:
            return dados
        ultimo = raw
        if tentativa == 1:
            prompt += ("\n\nATENÇÃO: responda SOMENTE com JSON válido — sem texto antes/depois, "
                       "sem comentários, sem vírgula sobrando antes de } ou ].")
    raise ValueError(f"extração não retornou JSON válido (modelo={llm_client._ULTIMO_MODELO[0]}): {ultimo[:200]!r}")


if __name__ == "__main__":
    pdf = sys.argv[1]
    fatos = extrair_fatos(pdf)
    r = N.score(fatos)
    print("=== FATOS extraídos (dado canônico) ===")
    for k in ("titulo", "pergunta", "desenho", "open_label", "desfecho_duro", "extrapolavel",
              "eventos_min_grupo", "eventos_nao_alcancados", "conclusao_nao_bate_desenho",
              "itt_falso", "qualidade_entrada", "achados_principais"):
        print(f"  {k}: {fatos.get(k)}")
    print("\n=== NOTAS (determinístico) ===")
    print(f"  nota_estatistica: {r['trabalho']} | aplicabilidade: {r['aplic']} "
          f"| tetos des/ext: {r['teto_desenho']}/{r['teto_externa']} | muda_conduta: {r['muda_conduta']}")
    print(f"  flags: {', '.join(r['flags']) or '—'}")
