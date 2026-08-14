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

# 11/Ago — PROTOCOLO entra aqui, pelo MESMO argumento do pré-clínico, e o argumento é de
# categoria, não de qualidade: um protocolo não tem resultado. Não há desfecho medido, não há
# N final, não há efeito. "Aplicabilidade clínica" é a única coisa que a nota mede, e não há o
# que aplicar. Dar nota de aplicabilidade a um ensaio que ainda não aconteceu é o mesmo erro
# de categoria que dar nota a camundongo.
#
# O caminho normal é o protocolo nem chegar aqui: o classificador o descarta pelo título
# (`eh_protocolo`, em classificador_pubmed.py). Esta é a SEGUNDA porta — se um escapar com
# título atípico, o motor recusa em vez de premiar. Foi a falta desta rede que deixou três
# protocolos saírem com nota 8: o extrator escreveu `rct` (o desenho descrito É de RCT) e o
# motor deu o teto do RCT, 10. Ninguém errou; faltava a palavra `protocolo` no vocabulário.
ROTA_PROTOCOLO = "PROTOCOLO_SEM_RESULTADO"

DESENHOS_FORA_DA_ESCALA = {"pre_clinico": ROTA_FRONTEIRA,
                           "protocolo": ROTA_PROTOCOLO,
                           "nao_classificavel": ROTA_HUMANA}


def rota(a):
    """Antes de qualquer nota: este artigo pertence à escala clínica?"""
    return DESENHOS_FORA_DA_ESCALA.get(a.get("desenho"), ROTA_CLINICA)


# ─────────────────────────── AS REGRAS ───────────────────────────

# ─────────────────────────────────────────────────────────────────────────────────────
# LÁPIDE — 11/Ago/2026
#
# Aqui viviam `_TETO_INTERVENCAO` e `_TETO_NAO_INTERVENCAO`, DUAS tabelas de teto que
# discordavam entre si (coorte 6 vs 8, transversal 5 vs 6, registro 6 vs 7), e o motor
# escolhia entre elas pelo tipo de PERGUNTA. Foram substituídas por `_TETO_LEI0`, logo
# abaixo — uma só, a tabela A–E do CLAUDE.md.
#
# Estão APAGADAS, não comentadas. Tabela morta que continua no arquivo é convite: alguém
# lê `_TETO_NAO_INTERVENCAO["coorte"] = 8`, acha que é a régua, e o defeito volta por uma
# porta que a gente mesmo deixou encostada. Se o histórico for preciso, ele está no git e
# no CADERNO_EXECUCAO.md.
# ─────────────────────────────────────────────────────────────────────────────────────


# ═══════════════════════════════════════════════════════════════════════════════════════
# 11/Ago/2026 — HAVIA DUAS TABELAS DE TETO, E ELAS DISCORDAVAM. A LEI 0 VOLTOU A MANDAR.
#
#   *"VC PRECISA CRIAR UMA MANEIRA DE BLOQUEAR DESENHO DE ESTUDOS DE RECEBEREM NOTAS
#     ALTAS... SE FOR DESENHO — COMO QUE O SISTEMA ME DÁ NOTA 8 PARA ISSO?"* — Dr. Eduardo
#
# A maneira já existia: é a LEI 0, a tabela A–E do CLAUDE.md. O que não existia era ela ser
# a ÚNICA. O motor guardava duas, e escolhia pela PERGUNTA:
#
#     _TETO_INTERVENCAO       coorte 6 · transversal 5 · registro 6 · caso_controle 6
#     _TETO_NAO_INTERVENCAO   coorte 8 · transversal 6 · registro 7 · caso_controle 7
#
# Uma coorte de prognóstico caía na segunda e pegava teto 8. A LEI 0 diz, com todas as
# letras: *"Registro prospectivo SEM grupo controle, coorte sem adjudicação central → 6"* e
# *"Observacional sem propensity score recebendo NAC 8 → ERRADO"*.
#
# É a família de defeito da semana inteira — duas fontes de verdade para o mesmo fato, e
# nada quebrando no meio — só que no lugar mais caro que existe: a NOTA. Não era o modelo
# errando; era o código com duas réguas e uma chave para escolher entre elas.
#
# MEDIDO em 683 artigos com desenho avaliável, antes de mudar uma linha:
#     147 (22 %) estavam acima do teto do próprio desenho
#      74 coorte 7→6 · 27 coorte 8→6 · 21 transversal 6→5 · 14 transversal 7-8→5
#       6 observacional_ajustado 8→7 · 3 caso_controle 7→5 · 2 registro 7→6
#     Visual Abstract (≥7): 253 → 133      áudio (≥8): 77 → 40
#
# Um deles era o JACC de morte súbita que ele APROVOU E MANDOU no WhatsApp em 11/Ago:
# coorte, etiologia, nota 8. Pela LEI 0 é 6 — e 6 não vai para o Visual Abstract nem para
# o áudio.
#
# Decisão dele, com esses números na mesa: **UMA TABELA SÓ, a da LEI 0.** Nas palavras que
# ele já tinha escrito na LEI 10: *"CardioDaily publica muito menos e reprova muito mais —
# esta é a regra."*
#
# O QUE MORREU JUNTO: o "piso 8 do Framingham". O argumento era honesto — coleta impecável,
# codebook, laboratório calibrado, seguimento completo — mas ele valia como ARGUMENTO, não
# como teto. Coleta boa continua contando: entra na `nota_trabalho_estatistico`, que é o
# outro termo do `min()`. O que não pode é coleta boa TRANSFORMAR coorte em quase-RCT.
# ═══════════════════════════════════════════════════════════════════════════════════════
_TETO_LEI0 = {                 # a tabela A–E do CLAUDE.md — o teto BASE de todo desenho
    "rct": 10,                 # A — teto; o refinamento de cegamento/poder vem abaixo
    "meta": 10,                # A — meta de RCTs; a escada da LEI 10 desce a partir daqui
    "observacional_ajustado": 7,   # C — controle + propensity/multivariada robusta
    "coorte": 6,               # D — sem randomização, sem adjudicação central
    "registro": 6,             # D — registro prospectivo SEM grupo controle
    "caso_controle": 5,        # E
    "transversal": 5,          # E
    "antes_depois_sem_controle": 5,
    "serie_de_casos": 5,       # E
}

# ═══════════════════════════════════════════════════════════════════════════════════════
# 11/Ago/2026, 19h30 — A CORREÇÃO DA CORREÇÃO. EU ERREI, E O DR. EDUARDO PEGOU.
#
#   *"não pode — o Framingham agora tira 6 — isto obviamente está errado!"*
#
# Ele está certo, e o erro foi MEU: eu recomendei "uma tabela só" com o selo de recomendado,
# e o que eu fiz foi APAGAR UMA DISTINÇÃO CIENTÍFICA LEGÍTIMA porque o portão dela estava
# frouxo. Consertar o portão era o trabalho; apagar a regra foi preguiça disfarçada de rigor.
#
# ═══ POR QUE A DISTINÇÃO É LEGÍTIMA ═══
# Para ETIOLOGIA e PROGNÓSTICO o RCT é impossível — e frequentemente antiético. Ninguém
# randomiza gente para fumar, para ter LDL alto, para envelhecer. A COORTE PROSPECTIVA É o
# teto do que a pergunta admite. Capar em 6 significa dizer que nenhum estudo de fator de
# risco pode ser muito aplicável, o que é falso: o Framingham mudou a prática de cardiologia
# mais que quase todo RCT já publicado. O próprio GRADE prevê SUBIR observacional por efeito
# grande, dose-resposta e confundimento que iria contra o achado.
#
# ═══ ONDE ESTAVA O BURACO DE VERDADE — MEDIDO, NÃO SUPOSTO ═══
# O portão do "piso 8" já existia:
#     if teto >= 8 and not (desenho_apropriado and qualidade_entrada and follow_up_completo)
#     if a.get("retrospectivo"): teto = min(teto, 7)
#
# Das 27 coortes que chegaram a 8:
#     18  tinham `retrospectivo: null`   ← o extrator NÃO RESPONDEU
#      8  tinham `retrospectivo: False`  ← declarada prospectiva
#      1  tinha  `retrospectivo: True`   ← e passou assim mesmo
#
# `if a.get("retrospectivo")` lê `None` como falso. Ou seja: **SILÊNCIO DO EXTRATOR VIRAVA
# "É PROSPECTIVA"**. Dois terços dos casos. Este projeto já corrigiu exatamente este erro na
# contagem NHLBI e nos fatos da meta — *"não confunda 'não reportado' com 'não fez'"* está
# escrito no próprio analise_prompt.md. Aqui ele estava vivo, e premiando em vez de punir.
#
# E os três booleanos são MOLES: nas 192 coortes o LLM diz True em 59 %, 79 % e 70 %. Três
# julgamentos narrativos que, quando caem juntos, entregam o crachá de Framingham.
#
# ═══ A REGRA AGORA ═══
# O teto 8 da coorte não é um piso que se ganha por silêncio: é um SELO que se conquista, e
# só com o artigo DECLARANDO cada item. Silêncio não qualifica — reprova.
# ═══════════════════════════════════════════════════════════════════════════════════════
_TETO_SELO_PROSPECTIVO = {     # só para pergunta NÃO-interventiva, e só com o selo abaixo
    "coorte": 8,               # o caso Framingham: prospectiva, coleta desenhada antes
    "registro": 7,             # registro prospectivo com coleta padronizada
    "caso_controle": 6,        # NHLBI: controles concorrentes, mesma população
    "transversal": 6,          # transversal cego com padrão-ouro (acurácia diagnóstica)
}


def selo_prospectivo(a):
    """O artigo PROVA que é a coorte que a pergunta merecia? Silêncio NÃO conta.

    Devolve (True, "") ou (False, o que faltou). Cada item exige um `True` EXPLÍCITO nos
    FATOS: `None` reprova. Foi ler `None` como "tudo bem" que deu 8 a 18 coortes em que o
    extrator simplesmente não respondeu se o estudo era retrospectivo.
    """
    faltou = []
    # 1. PROSPECTIVA declarada. `retrospectivo` tem de ser False EXPLÍCITO — não None.
    if a.get("retrospectivo") is not False:
        faltou.append("não está declarado que a coleta é prospectiva"
                      if a.get("retrospectivo") is None else "é retrospectiva")
    # 2-4. os três do NHLBI, cada um com True explícito
    for campo, dito in (("desenho_apropriado", "o desenho não é o apropriado para a pergunta"),
                        ("qualidade_entrada", "a qualidade da coleta não está demonstrada"),
                        ("follow_up_completo", "o seguimento não está declarado completo")):
        if a.get(campo) is not True:
            faltou.append(dito + (" (o artigo não informa)" if a.get(campo) is None else ""))
    return (not faltou), "; ".join(faltou)


def teto_desenho(a):
    """REGRA 0 — teto por DESENHO, com UMA subida nomeada e conquistada.

    Base: a tabela A–E da LEI 0 (`_TETO_LEI0`). Duas coisas podem mexer nela:
      · a PERGUNTA + o SELO PROSPECTIVO podem SUBIR — só para etiologia/prognóstico/
        diagnóstico, onde o RCT é impossível, e só com o selo inteiro (ver acima);
      · tudo o mais só ABAIXA.
    """
    q = a["pergunta"]
    d = a.get("desenho")
    teto = _TETO_LEI0.get(d, 6)

    # A ÚNICA SUBIDA DO MOTOR, e ela é nominal: pergunta que o RCT não pode responder +
    # selo prospectivo COMPLETO. Sem o selo, fica na tabela A–E e ponto.
    if q != "intervencao" and d in _TETO_SELO_PROSPECTIVO:
        ok, _ = selo_prospectivo(a)
        if ok:
            teto = max(teto, _TETO_SELO_PROSPECTIVO[d])

    if d == "rct":
        # Nível B (teto 8): sem cegamento, OU poder limítrofe — MAS parada precoce por
        # benefício não conta como "poder ruim" (o benefício foi esmagador). US Carvedilol.
        if a.get("open_label") or (not a.get("poder_ok", True)
                                   and not a.get("parado_cedo_por_beneficio")):
            teto = min(teto, 8)
        # RCT respondendo pergunta NÃO-interventiva é análise secundária: não foi para isso
        # que ele foi randomizado. Continua valendo o 8 que já valia.
        if q != "intervencao":
            teto = min(teto, 8)

    # ⚠️ NÃO PONHA TETO 8 NA META AQUI. Eu tentei, agora há pouco, e é uma REGRESSÃO: em
    # 04/Ago o Dr. Eduardo removeu exatamente essa régua — *"a nota da meta-análise tem que
    # ser somatória, não tem muito o que ficar inventando"*. O `_TETO_INTERVENCAO["meta"]=8`
    # era um teto colocado POR CIMA da ponderação dos 6 domínios que ele desenhou: uma meta
    # impecável saía 8 de qualquer jeito e o scorecard não decidia nada. Quem capa a meta é
    # a ESCADA da LEI 10, dentro de `nota_meta` (IPD/RCT sem teto · observacional 7 · rede
    # sem transitividade 8 · contaminação 5 · NI mal lida 6 · I² alto 6), e o `veredito`
    # força `td = 10` para a meta logo abaixo. Peguei isto porque a tabela de casos mostrou
    # meta/prognóstico com teto 10 e meta/intervenção com 8 — invertido, e sem sentido.

    # RETROSPECTIVO desce mais um degrau, nunca sobe. `is True` de propósito: aqui o `None`
    # NÃO desce (não vamos punir o silêncio), mas ele também não SOBE — quem lida com o
    # silêncio é o selo acima, que exige `False` explícito. As duas leituras do mesmo campo
    # são assimétricas de caso pensado: para BAIXAR exige-se prova; para SUBIR também.
    if a.get("retrospectivo") is True:
        teto = min(teto, 7)

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


# ═══════════════════════════════════════════════════════════════════════════════════════
# INDEPENDÊNCIA EDITORIAL — 05/Ago/2026
#
# A varredura dos 4 schemas mostrou que cada um tratava DINHEIRO de um jeito, e ninguém tinha
# decidido isso — foi acumulado:
#     DIRETRIZ ...... 6 campos, 20% da nota (domínio `independencia` do AGREE)
#     REVISÃO ....... 2 campos, 15% (domínio `conflitos`)
#     ORIGINAL ...... 1 campo (`financiamento_papel`) — extraído e JOGADO FORA
#     META .......... NADA — o schema nem perguntava
#
# Ou seja: um RCT patrocinado, com o financiador desenhando o estudo e escrevendo o manuscrito,
# tirava a mesma nota de um ensaio acadêmico independente. É onde o ceticismo do Dr. Eduardo é
# mais afiado ("especialmente estudos patrocinados pela indústria", CLAUDE.md) e era o único
# lugar cego do sistema.
#
# RÉGUA DELE (05/Ago): diretriz até 20% · os outros três até 10%.
#   · a DIRETRIZ já tinha 20% — nada muda.
#   · a REVISÃO já tinha 15%, peso que ELE aprovou em 02/Ago. NÃO foi mexido: baixar para 10%
#     seria eu revogar uma decisão dele sem que ele pedisse (LEI 3).
#   · ORIGINAL e META ganham este desconto: até 1,0 ponto = 10% da escala de 0 a 10.
# 06/Ago — A FRONTEIRA QUE O DESCONTO DE INDEPENDÊNCIA NÃO CRUZA (opção A do Dr. Eduardo).
# Nota ≥9 significa "muda conduta" (a bicondicional). Financiamento não pode, sozinho, converter
# um ensaio que se provou por método num ensaio que "não muda conduta" — isso é afirmação clínica
# falsa, e foi o que aconteceu com PLATO, TRITON e DAPA-HF na primeira rodada real.
PISO_INDEPENDENCIA = 9

DESCONTO_INDEPENDENCIA = {
    "industria envolvida": 1.0,        # o financiador desenhou, analisou ou escreveu
    "indústria envolvida": 1.0,
    "industria fora da analise/escrita": 0.3,
    "indústria fora da análise/escrita": 0.3,
    "publico": 0.0, "público": 0.0, "outro": 0.0,
}


def desconto_independencia(a):
    """Quanto a nota perde por dependência do financiador. Devolve (desconto, motivo)."""
    # ORIGINAL: o campo é textual (`financiamento_papel`)
    fp = (a.get("financiamento_papel") or "").strip().lower()
    if fp:
        for chave, d in DESCONTO_INDEPENDENCIA.items():
            if chave in fp:
                return d, (f"financiamento: {fp}" if d else "")
        if "indust" in fp or "indúst" in fp:
            return 0.6, f"financiamento: {fp} (papel não declarado)"
    # META: campos booleanos (acrescentados em 05/Ago)
    m = a.get("qualidade_meta") or {}
    if m.get("conflitos_declarados") is False:
        return 1.0, "nenhuma declaração de conflito de interesse"
    if m.get("financiamento_industria") and not m.get("autores_industria_fora_da_analise"):
        return 1.0, "financiada pela indústria, sem separação declarada da análise"
    if m.get("financiamento_industria"):
        return 0.3, "financiada pela indústria, com análise declarada independente"
    return 0.0, ""


# ═══════════════════════════════════════════════════════════════════════════════════════
# MCID CONFERIDO — o motor CHECA A CONTA, não aceita o rótulo (05/Ago/2026)
#
# O extrator já lia NOVE campos de relevância clínica: mcid_reportado, mcid_valor,
# mcid_fonte_metodo, efeito_observado, efeito_excede_limiar, ic_sustenta_relevancia,
# para_desfecho_duro, tipo_desfecho, desfecho_primario.
#
# E o motor usava UM: `classificacao`. O modelo fazia a conta, campo por campo, e no fim o
# código perguntava só "e aí, como você classifica?". A conta era feita e jogada fora; ficava
# o rótulo — que é justamente a parte em que o LLM é menos confiável.
#
# Palavras do Dr. Eduardo, 05/Ago: *"devemos usar este esquema que é muito bom — e deve pesar
# muito"*. Agora os FATOS mandam, e a regra-mãe é: **o rótulo pode ser rebaixado pela conta,
# nunca promovido por ela.** Se o modelo diz "robusto" e o efeito não passa do limiar, o motor
# corta. Se diz "incerto" e a conta é boa, continua incerto — cautela não se desfaz por número.
TETO_MCID_NAO_EXCEDE   = 6   # efeito NÃO passa do limiar clinicamente importante
TETO_MCID_IC_NAO_SUSTENTA = 7  # o ponto passa, mas o IC não sustenta a relevância
TETO_MCID_SEM_LIMIAR   = 8   # disse "robusto" sem limiar declarado: é opinião, não medida
TETO_MCID_SURROGATE    = 8   # rótulo alto sobre desfecho substituto


_SURROGATE = ("surrogate", "biomarcador", "biomarker", "prom", "substituto")


def _limiar_cardiodaily(a):
    """Quando o ARTIGO não declara MCID, o CARDIODAILY aplica o SEU (opção B, 05/Ago).

    ═══ POR QUE ═══
    Medido nas 24 metas: `mcid_reportado = false` em 21, `efeito_excede_limiar = null` em 22,
    `ic_sustenta_relevancia = null` em 24 de 24 — NUNCA respondido. Os tetos 6 e 7 da régua nova
    eram decorativos, porque `null` não capa (de propósito) e o extrator não tinha contra o que
    comparar. **21 de 24 meta-análises não dizem o que consideram clinicamente relevante.**

    Decisão do Dr. Eduardo: quem decide o que importa para o paciente é o cardiologista, não o
    autor do artigo. Os limiares vivem em `mcid_cardiodaily.py` — um arquivo de NÚMEROS, que ele
    edita sem tocar em motor.

    Devolve (excede, ic_sustenta, explicacao) — cada um True/False/None. `None` continua sendo
    "não dá para saber", e continua NÃO capando: aqui a gente só preenche o silêncio quando TEM
    o número. Sem número, o silêncio permanece.
    """
    try:
        import mcid_cardiodaily as MC
    except Exception:
        return None, None, ""
    rc = a.get("relevancia_clinica") or {}
    td = (rc.get("tipo_desfecho") or "").strip().lower()
    nome = rc.get("desfecho_primario") or ""

    # ── DESFECHO DURO: a régua é a ARR POR ANO ──
    duro = bool(a.get("desfecho_duro")) or td in ("binario", "tempo_ate_evento", "composto")
    if duro and not MC.eh_substituto(td, nome):
        # ═══ 06/Ago — DUAS FORMAS DE REPORTAR, DOIS CAMPOS (opção A, decisão do Dr. Eduardo) ═══
        #
        # O artigo dá a diferença de risco de dois jeitos, com DENOMINADORES diferentes:
        #
        #   INCIDÊNCIA ACUMULADA (denominador = pessoas)
        #       "16,3% vs 21,2% dos pacientes em 18,2 meses" → 4,9 pontos ACUMULADOS
        #       precisa dividir pelo tempo:  4,9 / 1,52 = 3,2 %/ano   ← DAPA-HF, e o motor acerta
        #
        #   DENSIDADE DE INCIDÊNCIA (denominador = pessoas-TEMPO)
        #       "141 vs 330 por 100.000 PESSOAS-ANO" → 0,189 %/ano, o "por ano" JÁ está no número
        #       dividir de novo é dividir duas vezes
        #
        # Até hoje existia UM campo (`arr_pct`) e o motor SEMPRE dividia. O número 2,0 é 2,0: não há
        # nada nele que diga se é acumulado ou anual, e o motor não tinha como perceber. O erro
        # andava nos dois sentidos — uma ARR de 2,0%/ano em 5 anos de seguimento virava 0,4%/ano e
        # reprovava um ensaio que muda conduta; e risco cumulativo lido como taxa aprovava o que
        # devia reprovar.
        #
        # MEDIDO em 06/Ago, nos 129 pacotes: `arr_pct` preenchido em 8, e ZERO com dupla divisão.
        # O defeito ainda não mordeu. Mas o mecanismo apareceu, com as palavras do extrator, já nos
        # primeiros 20 artigos originais (JAMA Coffee): *"diferença de taxas de 189 por 100.000
        # pessoas-ano; NNT não calculável, pois não foram fornecidos riscos cumulativos"* — ele
        # TINHA o número e desistiu, porque o campo pedia acumulado e o artigo oferecia taxa.
        # Coorte longa em cardiologia quase sempre reporta em pessoas-ano (Framingham, NHS, HPFS,
        # UK Biobank), e faltam 235 artigos originais na fila.
        #
        # A REGRA: `arr_ano_pct` tem PRECEDÊNCIA e NÃO é dividido. Se o extrator preencheu os dois
        # (não devia), o já-anualizado manda — é o mais específico, e não depende de `seguimento_anos`
        # estar certo.
        arr_ano = _n(rc.get("arr_ano_pct"))
        ic_ano = _n(rc.get("arr_ano_ic_inf_pct"))
        if arr_ano is not None:
            arr_ano, base = abs(arr_ano), "taxa/ano"
            ic_ano = None if ic_ano is None else abs(ic_ano)
        else:
            arr = _n(rc.get("arr_pct"))
            anos = _n(rc.get("seguimento_anos")) or 1.0
            if arr is None or anos <= 0:
                return None, None, ""
            arr_ano, base = abs(arr) / anos, f"acumulada ÷ {anos:g} ano(s)"
            ic_inf = _n(rc.get("arr_ic_inf_pct"))
            ic_ano = None if ic_inf is None else abs(ic_inf) / anos
        excede = arr_ano >= MC.ARR_ANO_RELEVANTE
        # o IC sustenta se o limite INFERIOR (o mais conservador) também passa do limiar
        sustenta = None if ic_ano is None else ic_ano >= MC.ARR_ANO_RELEVANTE
        txt = (f"limiar CardioDaily p/ desfecho duro: ARR {arr_ano:.2f}%/ano ({base}) "
               f"{'≥' if excede else '<'} {MC.ARR_ANO_RELEVANTE}%/ano")
        return excede, sustenta, txt

    # ── DESFECHO SUBSTITUTO: a tabela de limiares consagrados ──
    lim = MC.limiar_do_desfecho(nome)
    if not lim:
        return None, None, ""
    valor, unidade, fonte = lim
    delta = _n(rc.get("delta_substituto"))
    if delta is None:
        return None, None, ""
    excede = abs(delta) >= valor
    txt = (f"limiar CardioDaily p/ {nome[:40]}: Δ {abs(delta):g} {unidade} "
           f"{'≥' if excede else '<'} {valor:g} ({fonte[:40]})")
    return excede, None, txt


def mcid_conferido(a):
    """Confere a CONTA do MCID contra o rótulo. Devolve (teto, [motivos])."""
    rc = dict(a.get("relevancia_clinica") or {})
    c = (rc.get("classificacao") or "").strip().lower()
    teto, motivos = 10, []

    # ═══ 05/Ago — O ARTIGO CALOU? O CARDIODAILY RESPONDE (opção B) ═══
    # Só preenche o que estava em `null`: se o extrator conseguiu julgar contra o limiar DO ARTIGO,
    # aquilo vale — o autor sabe do desfecho dele. O limiar da casa entra no SILÊNCIO, não por cima.
    if rc.get("efeito_excede_limiar") is None or rc.get("ic_sustenta_relevancia") is None:
        _ex, _sus, _txt = _limiar_cardiodaily({**a, "relevancia_clinica": rc})
        if _txt:
            if rc.get("efeito_excede_limiar") is None and _ex is not None:
                rc["efeito_excede_limiar"] = _ex
            if rc.get("ic_sustenta_relevancia") is None and _sus is not None:
                rc["ic_sustenta_relevancia"] = _sus
            motivos.append(_txt)

    # 1 · o efeito passa do limiar? (o fato manda no rótulo)
    if rc.get("efeito_excede_limiar") is False:
        teto = min(teto, TETO_MCID_NAO_EXCEDE)
        motivos.append(f"o efeito NÃO excede o limiar clinicamente importante (rótulo dizia '{c}')")
    # 2 · o IC INTEIRO sustenta a relevância, ou só o ponto?
    elif rc.get("ic_sustenta_relevancia") is False:
        teto = min(teto, TETO_MCID_IC_NAO_SUSTENTA)
        motivos.append("o efeito pontual excede o limiar, mas o IC 95% não sustenta a relevância")
    # 3 · rótulo alto SEM limiar declarado é opinião, não medida
    #     ⚠️ 05/Ago: NÃO dispara se o limiar do CARDIODAILY foi aplicado com sucesso. Se a casa
    #     mediu contra a régua dela (`mcid_cardiodaily.py`), a relevância deixou de ser juízo —
    #     virou medida, só que com o nosso metro em vez do metro do autor. Punir aí seria cobrar
    #     duas vezes a mesma ausência: o artigo não declarou, e nós resolvemos.
    _casa_mediu = any("limiar CardioDaily" in m for m in motivos)
    if (c in ("robusto", "provavel") and rc.get("mcid_reportado") is False
            and not rc.get("mcid_valor") and not _casa_mediu):
        teto = min(teto, TETO_MCID_SEM_LIMIAR)
        motivos.append(f"'{c}' sem MCID/limiar declarado — é juízo, não medida")
    # 4 · rótulo alto sobre desfecho SUBSTITUTO
    #     ⚠️ 05/Ago: olhar só o `tipo_desfecho` deixava LDL passar. O extrator escreve
    #     `tipo_desfecho: "continuo"` para LDL, PA, FEVE, KCCQ — o que é verdade e não diz nada
    #     sobre ser substituto. Quem sabe é o NOME do desfecho, e o `mcid_cardiodaily` tem a
    #     tabela: contínuo que casa com a lista de substitutos É substituto.
    #     Pego ao testar: 'LDL −42 mg/dL' chegava a teto 10.
    td = (rc.get("tipo_desfecho") or "").strip().lower()
    _nome = rc.get("desfecho_primario") or ""
    try:
        import mcid_cardiodaily as _MC
        _eh_sub = _MC.eh_substituto(td, _nome)
    except Exception:
        _eh_sub = any(s in td for s in _SURROGATE)
    if c in ("robusto", "provavel") and _eh_sub:
        teto = min(teto, TETO_MCID_SURROGATE)
        motivos.append(f"desfecho substituto ({_nome[:30] or td}) não sustenta '{c}'")
    return teto, motivos


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

    # ═══════════ 04/Ago — A IPD PRÉ-PLANEJADA É OUTRO ANIMAL ═══════════
    # O Dr. Eduardo abriu a meta de betabloqueador do NEJM (IPD pré-planejada, 5 RCTs, 17.801
    # pacientes, desfecho duro, tirou uma droga da prática) e disse: *"você deu 7 para um artigo que
    # é praticamente 10 — está errado"*. Estava mesmo, e o motivo é o de sempre, uma camada abaixo:
    # o INSTRUMENTO NÃO SERVIA PARA O OBJETO.
    #
    # A régua de 6 domínios foi desenhada para meta de DADOS AGREGADOS, que nasce de uma busca na
    # literatura. Uma IPD PRÉ-PLANEJADA não busca base de dados nenhuma: os ensaios combinam juntar
    # os dados ANTES de os resultados existirem. Perguntar "quantas bases você pesquisou?" a ela é o
    # mesmo que perguntar randomização a uma meta — foi o erro que este projeto passou o dia
    # consertando, e ele reapareceu um degrau mais fundo.
    #
    # O que muda, e por quê (Cochrane cap. 26 · Riley/Tierney/Stewart, IPD-MA):
    #   BUSCA .............. numa colaboração prospectiva, o "achar todos os estudos" está resolvido
    #                        POR DESENHO. Não se pontua por número de bases.
    #   VIÉS DE PUBLICAÇÃO . é ELIMINADO por construção — os ensaios entraram antes de o resultado
    #                        existir. Isso é melhor do que qualquer funnel plot pode provar.
    #   HETEROGENEIDADE .... a clínica deixa de ser defeito: com dado de paciente dá para TESTAR
    #                        interação de verdade, que é a razão de a IPD existir.
    eh_ipd = (m.get("tipo_meta") or "").strip().lower() in ("ipd", "prospectiva")

    # a) PICO — pergunta focada e elegibilidade pré-definida
    d["pico"] = 10 if (q.get("pergunta_focada") and q.get("elegibilidade_predefinida")) else \
                7 if q.get("pergunta_focada") else 4

    # b) BUSCA — bases, protocolo registrado, duplicata, literatura cinzenta
    bases = _n(m.get("n_bases"), 0) or 0
    if eh_ipd:
        # colaboração prospectiva: "achar todos" está resolvido por desenho. O que ainda vale
        # perguntar é se havia protocolo ANTES (impede troca de desfecho) e revisão em duplicata.
        b = 9 if m.get("protocolo_registrado") else 6
    else:
        b = 4
        if q.get("busca_sistematica_abrangente"):
            b = 7
        if bases >= 3:
            b += 1
    if m.get("protocolo_registrado"):
        b += 1                                   # PROSPERO
    if q.get("revisao_em_duplicata") or m.get("extracao_em_duplicata"):
        b += 1
    # 04/Ago — itens CRÍTICOS do AMSTAR-2 que não entravam em lugar nenhum:
    if m.get("excluidos_listados_com_motivo"):
        b += 1                                   # quase ninguém cumpre; quem cumpre merece
    if m.get("restricao_idioma"):
        b -= 1                                   # restringir idioma é fonte conhecida de viés
    d["busca"] = min(max(b, 0), 10)

    # c) VIÉS DOS INCLUÍDOS — e a pergunta que separa: MUDOU a interpretação ou foi check-box?
    # 04/Ago: o extrator da meta grava a ferramenta em `qualidade_meta.rob_ferramenta`. Ler só o
    # `qualidade_nhlbi` fazia o motor achar que ninguém avaliou viés, mesmo com "RoB 2" escrito lá.
    avaliou = q.get("qualidade_estudos_avaliada") or bool((m.get("rob_ferramenta") or "").strip())
    if not avaliou:
        d["vies_estudos"] = 3
    elif m.get("vies_mudou_interpretacao"):
        d["vies_estudos"] = 10
    else:
        d["vies_estudos"] = 6                    # avaliou, mas não usou → check-box
    # 04/Ago — CONTAMINAÇÃO É VIÉS DOS ESTUDOS INCLUÍDOS, e é AQUI que ela pesa (15%).
    # Antes ela capava a NOTA INTEIRA em 5, por fora da ponderação. Foi o que derrubou a meta de
    # betabloqueador do NEJM de 7 para 5 — abaixo do corte de publicação. Um defeito real de método
    # tem de baixar o DOMÍNIO dele, não anular os outros cinco.
    if a.get("contaminacao_incluidos"):
        d["vies_estudos"] = min(d["vies_estudos"], 4)

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
    # ═══ 04/Ago — O PRISMA 2020 (item 13d) PEDE TRÊS COISAS, NÃO UMA ═══
    # I² é a PROPORÇÃO da variabilidade, não a QUANTIDADE. Quem responde "no meu próximo paciente,
    # que efeito espero?" é o INTERVALO DE PREDIÇÃO — e é comum o IC agregado excluir o nulo e a
    # predição incluir. Quando isso acontece, a meta é muito menos acionável do que o resumo diz.
    if m.get("intervalo_predicao_reportado"):
        d["heterogeneidade"] = min(d["heterogeneidade"] + 1, 10)
    if m.get("tau2_reportado"):
        d["heterogeneidade"] = min(d["heterogeneidade"] + 1, 10)
    if m.get("intervalo_predicao_cruza_nulo"):
        d["heterogeneidade"] = min(d["heterogeneidade"], 6)
    # heterogeneidade CLÍNICA não aparece no I²: populações/doses/tempos diferentes demais para somar
    if m.get("heterogeneidade_clinica_relevante") and not eh_ipd:
        d["heterogeneidade"] = min(d["heterogeneidade"], 5)
    # DOMINÂNCIA: se um estudo carrega a maior parte do peso, a meta É aquele estudo
    peso = _n(m.get("peso_maior_estudo_pct"))
    if peso is not None and peso >= 60:
        d["heterogeneidade"] = min(d["heterogeneidade"], 6)

    # e) VIÉS DE PUBLICAÇÃO — funnel/Egger/Begg feito?
    # 04/Ago: a Cochrane (cap. 13) diz para NÃO testar assimetria de funnel com k<10 — o teste não tem
    # poder e o resultado engana. Cobrar um teste que não deveria existir é punir quem fez certo.
    if eh_ipd:
        d["vies_publicacao"] = 10                # eliminado POR DESENHO: os ensaios entraram antes
                                                 # de o resultado existir. Nenhum funnel prova tanto.
    elif m.get("teste_funnel_indicado") is False or (k is not None and k < 10):
        d["vies_publicacao"] = 7                 # não era indicado: nem prêmio, nem castigo
    else:
        d["vies_publicacao"] = 9 if (q.get("vies_publicacao_avaliado")
                                     or m.get("funnel_plot_feito")) else 3

    # f) CONCLUSÕES — o maior peso: foram além do que os dados permitem?
    # não-inferioridade mal interpretada é erro de CONCLUSÃO (25%), não teto do total — 04/Ago
    if (a.get("ni_mal_interpretada") or a.get("conclusao_nao_bate_desenho")
            or m.get("conclusao_alem_da_evidencia")
            or m.get("subgrupo_tratado_como_principal")):
        d["conclusoes"] = 3                      # tratar subgrupo como resultado principal é o clássico
    elif m.get("limitacoes_reconhecidas"):
        d["conclusoes"] = 9
    else:
        d["conclusoes"] = 6
    # 04/Ago — o GRADE (PRISMA 15) é a certeza DA EVIDÊNCIA, diferente da qualidade DA REVISÃO.
    # Uma revisão impecável de evidência fraca continua sendo evidência fraca — e o leitor tem de saber.
    if m.get("grade_usado"):
        d["conclusoes"] = min(d["conclusoes"] + 1, 10)
    if (m.get("certeza_desfecho_primario") or "") in ("baixa", "muito_baixa"):
        d["conclusoes"] = min(d["conclusoes"], 6)
    # modelo fixo com heterogeneidade alta é erro estatístico, não escolha
    if m.get("modelo_apropriado_p_heterogeneidade") is False:
        d["conclusoes"] = min(d["conclusoes"], 5)
    # contar o mesmo paciente duas vezes (cluster/crossover/multi-braço) estreita o IC falsamente
    if m.get("unidade_analise_problema"):
        d["conclusoes"] = min(d["conclusoes"], 5)
    return d


# ═══════════════════════════════════════════════════════════════════════════════════════
# A ESCADA DE AVALIAÇÃO CRÍTICA DE META-ANÁLISES — 04/Ago/2026
# Especificação do Dr. Eduardo, para ele e para os residentes do Hospital Rio Doce.
#
# ═══ O CASO QUE A ORIGINOU: TOCILIZUMABE NA COVID-19 ═══
#
# Em 2021 as meta-análises diziam que o tocilizumabe não valia o investimento. A própria nota
# técnica do Ministério da Saúde (CCATES, abril/2021) concluiu, com "certeza moderada", que a
# droga reduzia ventilação mecânica mas NÃO reduzia mortalidade — apoiando-se num conjunto que
# misturava ECRs pequenos com estudos observacionais. O RECOVERY, UM único ensaio com N
# adequado e desenho que sustentava validade interna e externa, encerrou a discussão sozinho:
# reduzia mortalidade.
#
# Palavras dele: *"uma meta-análise só é tão boa quanto os estudos que a compõem. Quando
# combinamos vários estudos pequenos, retrospectivos, heterogêneos e propensos a vieses, a
# meta-análise propaga e amplifica esses erros em uma estimativa combinada matematicamente
# bonita, mas clinicamente enganosa."*  GIGO — garbage in, garbage out.
#
# Por isso a Escada é uma camada POR CIMA dos 6 domínios ponderados. A ponderação mede o
# CAPRICHO da revisão; a Escada mede se a MATÉRIA-PRIMA presta. Uma revisão pode ser impecável
# em método e clinicamente enganosa — foi exatamente o caso do tocilizumabe.
#
# Vale para TODAS as metas, inclusive rede e IPD (decisão dele, 04/Ago).
# ═══════════════════════════════════════════════════════════════════════════════════════

TETO_FALHA_ESCADA = 5     # as duas falhas fatais (degraus 2 e 4) — aprovado por ele
TETO_MURO = 6             # "em cima do muro": I² alto sem exploração (degrau 3)
TETO_SURROGATE = 8        # desfecho substituto: bom, mas não é 9/10 (degrau 5)
NNT_QUE_VALORIZA = 25     # EXTRA que valoriza — NÃO é régua (correção dele, 04/Ago)

FALHAS_FATAIS_META = {
    "M1": ("misturou ECR com estudo observacional no desfecho primário — ACC/AHA e Cochrane: "
           "desenhos diferentes NUNCA se combinam quantitativamente. Foi o erro do tocilizumabe"),
    "M2": ("o efeito perdeu significância após o ajuste Trim-and-Fill (Duval & Tweedie) — "
           "o resultado positivo era ilusão de publicação seletiva"),
}


def falhas_fatais_meta(a):
    m = a.get("qualidade_meta") or {}
    f = []
    if m.get("mistura_ecr_observacional_no_primario"):
        f.append("M1")
    if m.get("trim_and_fill_perdeu_significancia"):
        f.append("M2")
    return f


def heterogeneidade_explorada(a):
    """DEGRAU 3 — I² alto obriga a EXPLORAR, não só a reportar.

    Regra de ouro do decisor: se I² > 50% e os autores só jogaram tudo num modelo de efeitos
    aleatórios sem explicar a variação, o efeito médio é "matematicamente inútil para a decisão
    à beira do leito". Vale qualquer uma das três explorações legítimas.
    """
    m = a.get("qualidade_meta") or {}
    return bool(m.get("analise_sensibilidade_leave_one_out")
                or m.get("subgrupo_pre_especificado")
                or m.get("meta_regressao")
                or m.get("heterogeneidade_investigada"))


def escada_meta(a):
    """Aplica a Escada. Devolve (teto, degraus, falhas) — o teto é o MENOR dos tetos dos degraus."""
    q = a.get("qualidade_nhlbi") or {}
    m = a.get("qualidade_meta") or {}
    i2 = _n(q.get("i2_valor"))
    k = _n(m.get("k_estudos"))
    degraus, teto = {}, 10

    # DEGRAU 1 · registro e protocolo — sinal amarelo, não mata (já pesa no domínio `busca`)
    degraus["1_protocolo"] = "PROSPERO" if m.get("protocolo_registrado") else "sem registro prévio"

    # DEGRAU 2 · qualidade de entrada (GIGO) — FATAL
    if m.get("mistura_ecr_observacional_no_primario"):
        degraus["2_entrada"] = "FATAL: misturou ECR com observacional no desfecho primário"
        teto = min(teto, TETO_FALHA_ESCADA)
    elif m.get("so_ecr_baixo_risco_vies"):
        degraus["2_entrada"] = "só ECR de baixo risco de viés"
    else:
        degraus["2_entrada"] = f"ferramenta de viés: {m.get('rob_ferramenta') or 'não declarada'}"

    # DEGRAU 3 · heterogeneidade — TETO 6 se alto e não explorado
    if i2 is None:
        degraus["3_heterogeneidade"] = "I² não reportado"
    elif i2 > 50 and not heterogeneidade_explorada(a):
        degraus["3_heterogeneidade"] = f"I²={i2:.0f}% ALTO e não explorado — em cima do muro"
        teto = min(teto, TETO_MURO)
    elif i2 > 50:
        degraus["3_heterogeneidade"] = f"I²={i2:.0f}% alto, mas explorado (sensibilidade/subgrupo/meta-regressão)"
    else:
        degraus["3_heterogeneidade"] = f"I²={i2:.0f}%"

    # DEGRAU 4 · viés de publicação — FATAL se o Trim-and-Fill matou o efeito
    if m.get("trim_and_fill_perdeu_significancia"):
        degraus["4_vies_publicacao"] = "FATAL: efeito não sobreviveu ao Trim-and-Fill"
        teto = min(teto, TETO_FALHA_ESCADA)
    elif m.get("trim_and_fill_feito"):
        degraus["4_vies_publicacao"] = "robusto ao Trim-and-Fill"
    elif k is not None and k < 10:
        # Cochrane cap. 13: com k<10 o teste não tem poder. Cobrar é punir quem fez certo.
        degraus["4_vies_publicacao"] = f"k={k:.0f}<10: teste de assimetria não indicado (Cochrane)"
    else:
        degraus["4_vies_publicacao"] = "funnel/Egger" if m.get("funnel_plot_feito") else "não avaliado"

    # DEGRAU 5 · utilidade clínica — desfecho SUBSTITUTO não chega a 9/10
    duro = m.get("desfecho_primario_duro")
    if duro is False:
        degraus["5_utilidade"] = "desfecho SUBSTITUTO (Lp(a), GLS, FEVE) — não é desfecho duro"
        teto = min(teto, TETO_SURROGATE)
    elif duro:
        nnt = _n(m.get("nnt_agrupado"))
        extra = f" · NNT {nnt:.0f}" + (" (impactante)" if nnt <= NNT_QUE_VALORIZA else "") if nnt else ""
        degraus["5_utilidade"] = "desfecho DURO" + extra
    else:
        degraus["5_utilidade"] = "tipo de desfecho não declarado"
    return teto, degraus, falhas_fatais_meta(a)


# ═══ A ESCALA DE APLICABILIDADE DA META — os crivos GRADUAM, não só capam (04/Ago/2026) ═══
#
# Régua ditada pelo Dr. Eduardo, número por número:
#
#      0/4 crivos → 4       1/4 → 5       2/4 → 6       3/4 → 8       4/4 → 9 ou 10
#
# ERRO MEU, QUE ELE PEGOU: eu tinha feito os 4 crivos apenas CAPAREM em 8. Com isso, quem
# falhava nos QUATRO ficava com a mesma nota de quem falhava em UM — o algoritmo de beira do
# leito virava um interruptor, quando na escada dele é uma ESCALA.
#
# A prova do absurdo foi o protocolo do BMJ Open: um PROTOCOLO de revisão sistemática, sem
# nenhum estudo incluído e sem estimativa de efeito, reprovou nos 4 crivos e ficou com 8 —
# porque os 6 domínios de MÉTODO eram bons. Um protocolo é metodologicamente impecável e
# clinicamente vazio. Palavras dele: *"mas o protocolo passa pela escala de aplicabilidade"*.
# Passa: e é a escala que tem de dizer que ele não serve, não os domínios de método.
#
# Repare no salto 2→3 crivos (6 → 8) e na ausência do 7: é de propósito, é a régua dele.
TETO_POR_CRIVO = {4: 10, 3: 8, 2: 6, 1: 5, 0: 4}


def crivos_beira_do_leito(a):
    """O ALGORITMO DE BEIRA DO LEITO — os 4 crivos que autorizam nota 9/10.

    Palavras do Dr. Eduardo: *"se ela passar pelos seguintes crivos, então temos em mãos um
    estudo de impacto real, capaz de fundamentar uma recomendação com alto nível de evidência
    (LOE A) para guiar o tratamento dos pacientes e o ensino dos residentes."*

    E é AQUI que a regra mais importante do CardioDaily fica verdadeira POR CONSTRUÇÃO:
    **toda nota 9/10 muda conduta, e o que muda conduta é 9 ou 10.** São o mesmo fato dito de
    dois jeitos. Até 04/Ago essa regra era calculada em TRÊS lugares que discordavam entre si —
    e três meta-análises subiram ao Supabase com nota 9 e "muda_conduta: NÃO".
    Agora existe uma conta só, e a contradição deixa de ser possível.
    """
    m = a.get("qualidade_meta") or {}
    q = a.get("qualidade_nhlbi") or {}
    i2 = _n(q.get("i2_valor"))
    return {
        # 1 · só ECR de baixo risco de viés
        "so_ecr_baixo_risco": bool(m.get("so_ecr_baixo_risco_vies"))
                              and not m.get("mistura_ecr_observacional_no_primario"),
        # 2 · I² baixo, OU alto porém isolado e explicado
        "heterogeneidade_ok": (i2 is not None and i2 < 25) or
                              (i2 is not None and heterogeneidade_explorada(a)),
        # 3 · robusto ao Trim-and-Fill (ou teste não indicado por k<10)
        "robusto_vies_publicacao": not m.get("trim_and_fill_perdeu_significancia")
                                   and bool(m.get("trim_and_fill_feito")
                                            or (_n(m.get("k_estudos")) or 99) < 10),
        # 4 · desfecho DURO (o NNT<25 é extra que valoriza, não régua — decisão dele, 04/Ago)
        #     ⚠️ DUAS FONTES para a MESMA pergunta: `desfecho_duro` no topo dos fatos (que todo
        #     extrator preenche desde sempre) e `desfecho_primario_duro` dentro do bloco da meta
        #     (que eu criei hoje). Ler só o novo fazia a IPD de betabloqueador do NEJM — desfecho
        #     MORTALIDADE, declarado no campo antigo — reprovar no crivo do desfecho duro.
        #     É o mesmo erro do dia inteiro: campo novo que ignora o campo velho que já respondia.
        "desfecho_duro": bool(m.get("desfecho_primario_duro") if m.get("desfecho_primario_duro") is not None
                              else a.get("desfecho_duro")),
    }


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

    # 04/Ago — A HIERARQUIA DA PRÓPRIA TABELA DO DR. EDUARDO, aplicada em código:
    #   IPD de RCTs .............. o melhor tipo, quando bem feita → sem teto
    #   meta de RCTs ............. padrão-ouro                     → sem teto
    #   meta de OBSERVACIONAIS ... "nunca equivale a RCT"          → teto 7
    #   meta de rede ............. depende da transitividade       → teto 8 se não avaliada
    if (m.get("desenhos_incluidos") or a.get("desenhos_incluidos")) == "observacionais":
        s = min(s, 7)
    if (m.get("tipo_meta") or a.get("tipo_meta")) == "rede" and not m.get("transitividade_avaliada"):
        s = min(s, 8)

    # ═══ 04/Ago — OS TETOS CLÁSSICOS VIRARAM DOMÍNIO ═══
    # Ordem do Dr. Eduardo: *"a nota da meta-análise tem que ser SOMATÓRIA — não tem muito o que
    # ficar inventando"*. Estes três capavam o TOTAL por fora da ponderação que ele desenhou:
    #     contaminação dos incluídos → teto 5   ·   NI mal interpretada → 6   ·   I² alto → 6
    # Não sumiram: cada um foi para o DOMÍNIO a que pertence, onde pesa o que ele mandou pesar —
    #     contaminação  → vies_estudos (15%)   ·   NI mal interpretada → conclusoes (25%)
    #     I² alto sem investigar → heterogeneidade (15%), onde já estava
    # Assim um defeito real continua doendo, mas não anula os outros cinco domínios. Foi isso que
    # derrubou a meta de betabloqueador do NEJM de 7 para 5, abaixo do corte de publicação.

    # ═══ A ESCADA (04/Ago) — por cima da ponderação, nunca por baixo ═══
    # A ponderação mede o CAPRICHO da revisão; a Escada mede se a MATÉRIA-PRIMA presta.
    # Uma revisão pode ser impecável em método e clinicamente enganosa: foi o tocilizumabe.
    teto_esc, degraus, fatais = escada_meta(a)
    s = min(s, teto_esc)

    # O TOPO SÓ COM OS 4 CRIVOS. Sem eles a meta é boa, não é definitiva — e "definitiva" é
    # exatamente o que 9/10 significa no CardioDaily, porque 9/10 obriga a mudar conduta.
    cr = crivos_beira_do_leito(a)
    n_crivos = sum(1 for v in cr.values() if v)
    s = min(s, TETO_POR_CRIVO[n_crivos])
    # TSA que cruzou a fronteira: novo estudo não vira o resultado → o 10 fica autorizado
    if s >= 9 and not (a.get("qualidade_meta") or {}).get("tsa_cruzou_fronteira"):
        s = min(s, 9)

    frase = next(f for lim, f in FAIXA_META if s >= lim)
    if fatais:
        frase = "REPROVADO NA ESCADA — " + "; ".join(FALHAS_FATAIS_META[k] for k in fatais)
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


# ═══════════════════════════════════════════════════════════════════════════════════════
# A RECOMENDAÇÃO DA DIRETRIZ — 4 faixas, decisão do Dr. Eduardo em 06/Ago/2026
# ═══════════════════════════════════════════════════════════════════════════════════════
#
# A nota AGREE deixa de responder "muda conduta?" (pergunta sem sentido numa diretriz) e passa a
# responder a que o médico realmente faz: **confio nisto o quanto?**
#
# As frases são para serem lidas em voz alta no áudio e caberem no card. Nada de jargão AGREE aqui
# — o jargão fica na justificativa, traduzido ("a maior parte é opinião de especialista").
#
# ⚠️ ISTO NÃO É UMA PORTA. A LEI 10 continua valendo: **a diretriz sobe em QUALQUER nota**, mesmo
# NÃO RECOMENDADA. Palavras dele em 05/Ago: não existe "outra diretriz de fibrilação atrial",
# existe A diretriz — se é fraca, o médico precisa saber que é fraca E mesmo assim precisa dela,
# porque é por ela que vai ser cobrado. A recomendação AVISA; ela não retém.
RECOMENDACAO_DIRETRIZ = (
    (8, "RECOMENDADA",
        "base sólida; pode seguir"),
    (6, "RECOMENDADA COM RESSALVAS",
        "útil, mas parte relevante das recomendações é opinião — leia com olho crítico"),
    (4, "REFERÊNCIA, NÃO AUTORIDADE",
        "é o documento que existe sobre o tema; não é prova, é consenso"),
    (0, "NÃO RECOMENDADA",
        "método frágil demais para sustentar as recomendações que faz"),
)


def recomendacao_da_diretriz(nota):
    """A nota AGREE vira a frase que o cardiologista usa. Devolve só o rótulo (é o que vai para a
    coluna `muda_conduta` — reuso decidido por ele, para não precisar de ALTER TABLE)."""
    for piso, rotulo, _ in RECOMENDACAO_DIRETRIZ:
        if nota >= piso:
            return rotulo
    return RECOMENDACAO_DIRETRIZ[-1][1]


def motivo_da_recomendacao(nota):
    """A frase de apoio — o PORQUÊ, para a perícia, o card e o áudio."""
    for piso, _, motivo in RECOMENDACAO_DIRETRIZ:
        if nota >= piso:
            return motivo
    return RECOMENDACAO_DIRETRIZ[-1][2]


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
            # ═══ 06/Ago — A DIRETRIZ NÃO RESPONDE "MUDA CONDUTA". ELA RESPONDE "CONFIE QUANTO?" ═══
            #
            # Palavras do Dr. Eduardo: *"a diretriz muda várias coisas — pela atualização. Ninguém
            # escreve uma diretriz que não muda nada. Então o que muda é o GRAU COM QUE PODEMOS
            # ACREDITAR NELA, baseado na nota que o motor calcula. Podemos ajustar o nome e
            # recomendar ou não recomendar."*
            #
            # O CASO QUE ORIGINOU. Ele mandou o PDF do "Imagem Vascular na Cardio-Oncologia"
            # (statement ESC 2026) que o CardioDaily já publicou, e o veredito impresso na peça diz:
            #
            #       min(…) = 6/10        MUDA CONDUTA: NÃO
            #
            # No mesmo documento: `aplicável no Brasil 10/10`, e mensagens-chave que são ordens
            # diretas — "faça ECG de 12 derivações e estratificação HFA-ICOS", "eco basal é
            # recomendado para risco alto (classe I)". A peça mandava fazer cinco coisas e dizia
            # que não mudava conduta. Não era teoria: já tinha saído impresso.
            #
            # POR QUE A PERGUNTA ERA ERRADA. Uma diretriz existe PARA mudar conduta — é a definição
            # dela. Perguntar se muda é perguntar se chove na chuva. O que varia, e o que o médico
            # precisa saber, é QUANTO acreditar: o statement acima tem 68,8% das recomendações em
            # nível C e metade das Classe I apoiadas em nível C. É isso que a nota 6 está dizendo.
            #
            # A ESCALA (4 faixas, decisão dele em 06/Ago) — a nota AGREE vira uma frase que o
            # cardiologista usa: recomendo, recomendo com ressalva, é o que existe, não recomendo.
            "muda_conduta": recomendacao_da_diretriz(aplic),
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
    # ═══ 05/Ago — A TABELA COMPARATIVA (o campo que era extraído e ignorado) ═══
    # `tem_tabela_comparativa` estava no schema desde que a trilha da revisão nasceu, e NENHUM
    # bloco do sistema o lia. Achado na varredura dos 4 schemas que o Dr. Eduardo mandou fazer.
    #
    # E a ironia é que ele é a TAREFA #25 da lista dele — "Perícia com TABELAS (características
    # basais, desfechos, limitações)", pendente desde 30/Jul. O dono sabe que tabela é o que separa
    # revisão útil de prosa; o extrator já perguntava; o motor não escutava.
    #
    # Uma revisão que compara as opções LADO A LADO entrega conduta pronta para o plantão. Uma que
    # descreve em prosa obriga o leitor a montar a tabela na cabeça — que é justamente o trabalho
    # que ele não tem tempo de fazer às 3 da manhã.
    #
    # VALORIZA, não capa: +1 ponto, igual ao `traz_valores_corte_ou_doses` acima. Mesma lógica do
    # NNT na meta-análise — quem organizou merece o crédito, quem não organizou não é reprovado.
    if q.get("tem_tabela_comparativa"):
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
            # ═══ 06/Ago — A REVISÃO NÃO TEM `muda_conduta`. ELA ORGANIZA CONHECIMENTO. ═══
            #
            # Palavras do Dr. Eduardo: *"este termo muda conduta se aplica a um RCT — as revisões
            # irão me ajudar a ORGANIZAR O CONHECIMENTO. E a pontuação reflete a qualidade do
            # material utilizado e a quantidade de informações aplicáveis que ela de fato entrega."*
            #
            # O QUE ACONTECEU. Em 02/Ago ele corrigiu a minha proposta de teto 6 e autorizou a
            # revisão a chegar a 10 — por UTILIDADE PRÁTICA ("quanto ela me ajuda"). Em 04/Ago veio
            # a bicondicional (nota ≥9 ⟺ muda conduta), e eu a apliquei aqui sem varrer o que ela
            # significaria numa revisão. Resultado medido em 06/Ago, no lote real: 8 revisões
            # narrativas com nota 9 gravadas dizendo `muda_conduta: SIM`, enquanto PLATO, TRITON e
            # DAPA-HF diziam NÃO. O CardioDaily afirmava que uma revisão de fisiopatologia muda a
            # conduta e que o ticagrelor não muda.
            #
            # Não foi a NOTA que errou — a nota faz o que ele mandou: mede base × utilidade. Foi o
            # CAMPO, que responde a uma pergunta que a revisão não faz. Uma revisão não testa
            # intervenção, não tem braço, não tem desfecho: não há conduta a mudar, há conhecimento
            # a organizar. Nota 10 aqui significa "organiza excepcionalmente bem", não "prescreva".
            #
            # A bicondicional continua INTEIRA onde ela nasceu: intervenção (RCT e meta de
            # intervenção) e diretriz. Mesmo tratamento que o motor do ORIGINAL já dá quando
            # `pergunta != "intervencao"`.
            "muda_conduta": "N/A (revisão organiza conhecimento, não testa intervenção)",
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
    """REGRA 4 — checklist 'mudar a prática', NUNCA a autoridade.

    ═══ 04/Ago — A REGRA MAIS IMPORTANTE DO CARDIODAILY, E O BURACO QUE ELA ABRIU ═══

    Palavras do Dr. Eduardo: *"toda nota 9 e 10 muda conduta! Se muda a conduta é 9 ou 10, e se
    é 9 ou 10 é porque muda conduta."* É uma BICONDICIONAL: a nota e o `muda_conduta` são o mesmo
    fato dito de dois jeitos, não duas perguntas independentes.

    Só que estavam sendo calculados por CAMINHOS SEPARADOS — a nota de um lado, este checklist do
    outro. Um artigo podia passar de 9 na nota e reprovar no checklist (que exige
    `efeito_relevante_consistente`). Aconteceu 3 vezes: três meta-análises subiram ao Supabase com
    nota 9 e "muda_conduta: NÃO", medido em 04/Ago.

    O conserto NÃO é ajustar o limiar: é INVERTER A HIERARQUIA. O checklist continua existindo e
    continua sendo a pergunta certa — mas como INSUMO, cortando a nota. Quem reprova aqui não
    chega a 9. Assim a bicondicional passa a ser verdadeira POR CONSTRUÇÃO, e não por conferência
    de alguém que lembre de olhar.
    """
    if a["pergunta"] != "intervencao":
        return "N/A (não é intervenção)"
    # ⚠️ 04/Ago — `a.get(k, True)` NÃO devolve o padrão quando a chave EXISTE valendo None.
    # `sem_evidencia_conflitante_melhor: null` (= "o artigo não conta") virava falso, e o checklist
    # reprovava. É a REGRA MÃE dos prompts — *null é "não reportado", false é "não fez"* — violada
    # DENTRO do motor. Ficou invisível enquanto o checklist só escrevia um rótulo; virou teto de nota
    # em 04/Ago e derrubou 11 travas da bateria de uma vez, inclusive o "melhor RCT possível".
    def _sim(chave, padrao=True):
        v = a.get(chave)
        return padrao if v is None else bool(v)

    comum = (aplic >= 8 and _sim("extrapolavel") and _sim("sem_evidencia_conflitante_melhor"))
    # 04/Ago — DEIXAR DE FAZER TAMBÉM É CONDUTA. Exigir `efeito_relevante_consistente` fazia com que
    # NENHUM estudo negativo pudesse dizer SIM: por construção, um nulo não tem "efeito relevante".
    # Era por isso que o trabalho que TIROU o betabloqueador do pós-IAM saía com "muda conduta: NÃO".
    rc = a.get("relevancia_clinica") or {}
    if (rc.get("classificacao") or "").strip().lower() == "ausencia_de_efeito_demonstrada":
        return "SIM" if (comum and _nulo_esta_demonstrado(rc, a)) else "NÃO"
    # ⚠️ 04/Ago — MESMA PERGUNTA, DUAS VEZES. `efeito_relevante_consistente` e o MCID perguntam a
    # MESMA coisa: "esse efeito importa para o paciente?". O MCID já responde, com vocabulário mais
    # fino (robusto / provavel / incerto / abaixo do MCID / ausência demonstrada). Exigir o booleano
    # ADEMAIS do MCID fazia o melhor RCT possível — efeito grande, MCID robusto — reprovar só porque
    # o extrator deixou aquele campo em `null`. Punia o SILÊNCIO do extrator, não o estudo:
    # o mesmo erro que este projeto já corrigiu na contagem NHLBI e nos fatos da meta.
    _cls = ((a.get("relevancia_clinica") or {}).get("classificacao") or "").strip().lower()
    _relevante = _sim("efeito_relevante_consistente", False) or _cls in ("robusto", "provavel")
    ok = comum and _relevante and _sim("beneficio_supera_risco")
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
        motivo = {
            ROTA_FRONTEIRA: "estudo pré-clínico (animal/in vitro): não há paciente, logo não há "
                            "aplicabilidade clínica para pontuar — nenhum instrumento do NHLBI "
                            "cobre este desenho",
            ROTA_PROTOCOLO: "PROTOCOLO: o ensaio ainda não aconteceu. O artigo descreve como o "
                            "estudo VAI ser feito — não há desfecho medido, não há N final, não "
                            "há efeito. Não há o que aplicar à beira do leito, e aplicabilidade "
                            "clínica é a única coisa que a nota mede.",
        }.get(r0, "o extrator não conseguiu classificar o desenho: o motor NÃO chuta")
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
    # ═══════════ 04/Ago — NA META, A SOMATÓRIA É A NOTA ═══════════
    # Palavras do Dr. Eduardo: *"a nota da meta-análise tem que ser somatória — não tem muito o que
    # ficar inventando"*. E ele está certo: o `_TETO_INTERVENCAO["meta"] = 8` era uma régua EXTRA,
    # colocada POR CIMA da ponderação dos 6 domínios que ele próprio desenhou. O resultado era que
    # uma meta impecável — os 6 domínios em 10 — saía com 8 de qualquer jeito, e os domínios não
    # mudavam nada de 8 para cima. O scorecard existia e não decidia.
    #
    # A hierarquia da tabela DELE continua valendo, mas ela vive DENTRO do `nota_meta`, onde é
    # específica em vez de genérica:
    #     IPD de RCTs / meta de RCTs .... sem teto  (🟢 "melhor tipo" / "padrão-ouro")
    #     meta de OBSERVACIONAIS ........ teto 7    ("nunca equivale a RCT")
    #     meta de REDE sem transitividade teto 8
    # mais os tetos clássicos que já estavam lá: contaminação (5), NI mal interpretada (6),
    # I² alto sem investigar (6).
    if eh_meta:
        td = 10

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

    # ═══ 04/Ago — NA META, A SOMATÓRIA É A NOTA ═══
    # A ordem do Dr. Eduardo foi cumprida pela METADE em 03/Ago: eu tirei o teto de DESENHO e deixei
    # três outros em cima (NHLBI, validade externa, MCID) — e ainda avisei que estava deixando, como
    # se fosse prudência. Não era. A conta do betabloqueador provou: somatória 7, nota final 5.
    # O MCID em especial é o teto que pune ESTUDO NEGATIVO, e não tem lugar numa régua de MÉTODO:
    # os 6 domínios medem como o trabalho foi FEITO, e método não tem sinal.
    if eh_meta:
        aplic = s
    else:
        aplic = min(td, te, s, tf, tm)   # ← a régua-chave (artigo original)

    # ═══ 05/Ago — O MCID CONFERIDO: a CONTA manda no RÓTULO ═══
    # Vale para ORIGINAL e META. O extrator produz 9 campos de relevância clínica e até hoje o
    # motor lia UM (`classificacao`). Agora os fatos podem REBAIXAR o rótulo — nunca promovê-lo.
    _t_mcid, _mot_mcid = mcid_conferido(a)
    if _t_mcid < 10:
        aplic = min(aplic, _t_mcid)
        for _m in _mot_mcid:
            fl.append(f"MCID conferido → teto {_t_mcid}: {_m}")
    # ═══ 06/Ago — A CONTA QUE O REDATOR RECEBIA NÃO FECHAVA ═══
    # `tm` vem do `teto_mcid(a)` (o teto pelo RÓTULO, de 01/Ago); `_t_mcid` vem do `mcid_conferido`
    # (a CONTA conferida, de 05/Ago). Só o primeiro ia para o campo `teto_mcid` do retorno — e é
    # esse campo que o `veredito_completo` imprime para o redator. Resultado, com o JAMA Coffee:
    #
    #     APLICABILIDADE = o MENOR entre: desenho 10 · externa 10 · falha fatal 10 · MCID 10 · rigor 9
    #     Nota 6/10
    #
    # Nenhum dos números da conta produz 6. O delator dizia "MCID conferido → teto 6" na linha de
    # baixo, contradizendo a linha de cima. O VEREDITO ABERTO existe justamente para o redator
    # explicar a nota a partir dos domínios (medido em 02/Ago: com o número nu, 86% dos parágrafos
    # mudavam) — e ele estava recebendo domínios que não somam a nota. Ou ele inventa, ou desiste.
    tm = min(tm, _t_mcid)

    # ═══ 05/Ago — INDEPENDÊNCIA EDITORIAL: até 10% (1,0 ponto) ═══
    # Régua do Dr. Eduardo. A DIRETRIZ tem os 20% dela no domínio AGREE e a REVISÃO tem 15% no
    # domínio `conflitos`; os dois motores não passam por aqui. Este desconto é de ORIGINAL e META,
    # que até hoje eram CEGOS a financiamento (o `financiamento_papel` era extraído e ignorado).
    _desc, _mot_ind = desconto_independencia(a)
    if _desc:
        # ═══ 06/Ago — O DESCONTO NÃO CRUZA A FRONTEIRA DO 9 (opção A, decisão do Dr. Eduardo) ═══
        #
        # O QUE ACONTECEU. Na primeira rodada real dos artigos originais, TRITON-TIMI 38, PLATO e
        # DAPA-HF — três dos ensaios que mais mudaram a cardiologia moderna — saíram assim:
        #
        #     teto_desenho: 10 · nota_trabalho_estatistico: 9 · desconto −1,0 → aplicabilidade 8
        #     muda_conduta: "NÃO"
        #
        # O motor tinha reconhecido tudo: RCT duplo-cego, poder ok, desfecho duro, ARR/ano acima do
        # limiar da casa. Então o desconto de indústria derrubou 9 → 8, e a BICONDICIONAL leu o 8 e
        # concluiu que o ticagrelor não muda conduta.
        #
        # POR QUE ISSO ERA ESTRUTURAL, NÃO UM AJUSTE FINO. Quase todo ensaio de fase 3 em
        # cardiologia é patrocinado (PLATO e DAPA-HF são AstraZeneca; TRITON é Daiichi Sankyo/Lilly;
        # SPRINT e ISCHEMIA são a exceção). Desconto integral + bicondicional, juntos, tornavam
        # quase impossível um artigo original chegar a 9 — e o CardioDaily perdia a capacidade de
        # dizer "isto muda sua prática", que é a frase mais valiosa que ele vende.
        #
        # Nenhuma das duas regras estava errada sozinha. Elas se atropelavam porque o desconto
        # entrava DEPOIS, no mesmo lugar onde a bicondicional lê.
        #
        # A REGRA: financiamento é RESSALVA DECLARADA, não rebaixamento de categoria. Se a nota
        # ANTES do desconto já era ≥9 (o estudo se provou por método), o desconto desce no máximo
        # até 9 — e o delator diz, na perícia, quanto TERIA sido descontado. O leitor vê as duas
        # coisas: que o ensaio é bom, e quem pagou por ele.
        # Abaixo de 9 o desconto continua valendo integral, como ele definiu em 05/Ago.
        _antes = aplic
        aplic = max(0, int(round(aplic - _desc)))
        if _antes >= PISO_INDEPENDENCIA and aplic < PISO_INDEPENDENCIA:
            aplic = PISO_INDEPENDENCIA
            fl.append(f"independência editorial: {_mot_ind} — desconto de {_desc:.1f} NÃO aplicado "
                      f"por inteiro; a nota tinha se provado por método ({_antes}) e o financiamento "
                      f"vira ressalva declarada, não rebaixamento (piso {PISO_INDEPENDENCIA})")
        else:
            fl.append(f"independência editorial −{_desc:.1f} ({_mot_ind})")

    # ═══ 04/Ago — A BICONDICIONAL: 9/10 ⟺ MUDA CONDUTA ═══
    # *"Toda nota 9 e 10 muda conduta! Se muda a conduta é 9 ou 10, e se é 9 ou 10 é porque muda
    # conduta."* — Dr. Eduardo, e ele chama de a regra mais importante de todas.
    #
    # Até hoje a nota saía de um caminho e o `muda_conduta` de OUTRO (o checklist da REGRA 4).
    # Dois caminhos independentes para o MESMO fato: a definição de buraco. Resultado medido no
    # Supabase em 04/Ago: TRÊS meta-análises com nota 9 e "muda_conduta: NÃO". Zero com SIM.
    #
    # O conserto não é mexer no limiar — é inverter a hierarquia. O checklist continua sendo a
    # pergunta certa, mas como INSUMO: quem reprova nele NÃO CHEGA A 9. Depois disso, o
    # `muda_conduta` é lido da própria nota. Uma conta, um lugar, contradição impossível.
    # A META tem escada PRÓPRIA (os 4 crivos de beira do leito, já aplicados dentro do nota_meta).
    # Cobrar dela TAMBÉM o checklist do artigo original é o erro de sempre — o instrumento errado
    # para o objeto: `efeito_relevante_consistente` é pergunta de ensaio, não de revisão.
    # O checklist da REGRA 4 era, em quase tudo, REDUNDANTE com tetos que já existem:
    #   `extrapolavel`  → já é o teto_externa       ·  relevância clínica → já é o teto_mcid
    # Manter os dois era julgar o mesmo defeito duas vezes por caminhos que discordavam.
    # Sobraram DUAS perguntas que só ele fazia — e elas viram TETO, no lugar certo:
    if a.get("beneficio_supera_risco") is False:
        aplic = min(aplic, 8)
        fl.append("o benefício NÃO supera o risco → teto 8 (não se muda conduta para piorar)")
    if a.get("sem_evidencia_conflitante_melhor") is False:
        aplic = min(aplic, 8)
        fl.append("existe evidência conflitante MELHOR → teto 8 (não é a palavra final)")
    if a.get("pergunta") != "intervencao":
        _muda = "N/A (não é intervenção)"   # prognóstico/diagnóstico: não há conduta a mudar
    else:
        _muda = "SIM" if aplic >= 9 else "NÃO"

    r = {"trabalho": s, "aplic": aplic, "teto_desenho": td, "teto_externa": te,
         "teto_falha_fatal": tf, "teto_mcid": tm, "muda_conduta": _muda,
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
    # ⚠️ 11/Ago — ESTE GABARITO FOI PARA 6 E VOLTOU PARA 8 NO MESMO DIA. VALE REGISTRAR POR QUÊ.
    #
    # Eu propus "uma tabela de teto só" e RECOMENDEI a opção. O Dr. Eduardo aceitou, eu troquei
    # o gabarito para 6 — e ele leu o resultado e recusou na hora: *"não pode. O Framingham
    # agora tira 6. Isto obviamente está errado!"*. Ele tinha razão, e o erro foi meu.
    #
    # O QUE EU FIZ DE ERRADO: apaguei uma distinção CIENTÍFICA legítima porque o PORTÃO dela
    # estava frouxo. Para etiologia e prognóstico o RCT é impossível — ninguém randomiza gente
    # para fumar. A coorte prospectiva É o teto do que a pergunta admite, e o Framingham mudou
    # a cardiologia mais que quase todo RCT já publicado. Consertar o portão era o trabalho.
    #
    # O BURACO REAL, medido: das 27 coortes com nota 8, **18 tinham `retrospectivo: null`** —
    # o extrator não respondeu, e `if a.get("retrospectivo")` lê None como falso. SILÊNCIO
    # VIRAVA "É PROSPECTIVA". Agora o selo exige `False` explícito e os três NHLBI em `True`
    # explícito: `None` reprova. Ver `selo_prospectivo()`.
    #
    # Este fixture é o caso POSITIVO do selo — tudo declarado. O caso negativo mora na trava
    # `teste_o_selo_prospectivo_nao_se_ganha_por_silencio`.
    "Framingham": dict(gabarito=8, pergunta="etiologia", desenho="coorte",
                  retrospectivo=False,          # ← declarado, não silenciado. É o ponto todo.
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
