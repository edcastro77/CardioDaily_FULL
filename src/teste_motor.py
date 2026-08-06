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


# ══════════════ N · O REUSO DE STAGING NÃO PODE IGNORAR A PASTA (o erro fatídico, 03/Ago) ══════════════
def teste_reuso_de_staging():
    """O laço de blocos reusava o staging só porque existia `_OK`. A pasta do staging é indexada
    pelo NOME DO ARQUIVO — então mover o PDF de META_ANALISES para REVISOES não mudava nada: o
    `_OK` continuava lá e a análise VELHA era republicada. A correção manual do Dr. Eduardo era
    jogada fora num `continue`, que também pulava as três travas que moram dentro de `processar()`.

    Esta trava é pura: monta stagings de mentira em disco temporário, sem LLM e sem rede."""
    import os, json, tempfile, sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import rodar_em_blocos as R

    SCHEMA = {"original": "fracao_ejecao", "meta": "qualidade_meta",   # 04/Ago: meta ganhou schema
              "diretriz": "agree", "revisao_narrativa": "qualidade_revisao"}
    PASTA = {"original": "ARTIGOS_ORIGINAIS", "meta": "META_ANALISES",
             "diretriz": "GUIDELINES", "revisao_narrativa": "REVISOES"}

    with tempfile.TemporaryDirectory() as tmp:
        import analisador as AN

        def montar(tipo_gravado, com_ok=True, com_schema=True, com_carimbo=True, pasta_do_pdf=None):
            d = os.path.join(tmp, f"art_{tipo_gravado}_{com_ok}_{com_schema}_{com_carimbo}")
            os.makedirs(d, exist_ok=True)
            f = {}
            if tipo_gravado is not None:
                f["tipo_documento"] = tipo_gravado
            if com_schema and tipo_gravado:
                f[SCHEMA[tipo_gravado]] = "qualquer coisa"
            json.dump(f, open(os.path.join(d, "art_fatos.json"), "w"))
            if com_ok:
                open(os.path.join(d, "_OK"), "w").write("")
            # 04/Ago — o CARIMBO DO PROMPT virou o primeiro portão do reuso. Um staging de mentira
            # sem `_versoes.json` é, com razão, recusado: é exatamente o caso "staging anterior a
            # 04/Ago, prompt desconhecido". Este teste mede a regra do TIPO, então carimba certo.
            if com_carimbo:
                alvo = pasta_do_pdf or (pdf(tipo_gravado) if tipo_gravado else pdf("original"))
                json.dump(AN.versoes_atuais(alvo),
                          open(os.path.join(d, "_versoes.json"), "w", encoding="utf-8"))
            return d

        pdf = lambda tipo: f"/x/CLASSIFICADOS/{PASTA[tipo]}/art.pdf"

        # 1) MESMO tipo + schema presente → reusa (senão a retomada morre e tudo vira dinheiro queimado)
        for t in SCHEMA:
            serve, _ = R._staging_serve(montar(t, pasta_do_pdf=pdf(t)), pdf(t))
            checa(f"reuso: staging '{t}' na pasta '{PASTA[t]}' PODE ser reusado", serve)

        # 2) o Dr. Eduardo MOVEU o artigo: toda combinação cruzada tem de RECUSAR o reuso
        for gravado in SCHEMA:
            for agora in SCHEMA:
                if gravado == agora:
                    continue
                serve, _ = R._staging_serve(montar(gravado, pasta_do_pdf=pdf(agora)), pdf(agora))
                checa(f"reuso: staging '{gravado}' NÃO pode ser reusado na pasta '{PASTA[agora]}'",
                      not serve, "é o erro fatídico de 03/Ago voltando")

        # 3) staging ANTIGO (sem o campo tipo_documento) = feito pela corrente quebrada → nunca reusa
        for agora in SCHEMA:
            serve, _ = R._staging_serve(montar(None, pasta_do_pdf=pdf(agora)), pdf(agora))
            checa(f"reuso: staging pré-03/Ago não serve para '{PASTA[agora]}'", not serve)

        # 4b) O CARIMBO DO PROMPT (04/Ago) — *"se não tem certeza que foi com ESTE prompt, apaga
        #     TUDO e começa do zero"*. Sem `_versoes.json` = staging anterior a 04/Ago = não serve.
        for t2 in SCHEMA:
            serve, pq = R._staging_serve(montar(t2, com_carimbo=False, pasta_do_pdf=pdf(t2)), pdf(t2))
            checa(f"reuso: staging SEM carimbo de prompt não serve ({t2})", not serve, pq)
        # carimbo de OUTRO prompt (simulado trocando um hash) também não serve
        d_falso = montar("meta", pasta_do_pdf=pdf("meta"))
        v = json.load(open(os.path.join(d_falso, "_versoes.json")))
        v["redator"] = "redator_meta_prompt.md@0000deadbeef"
        json.dump(v, open(os.path.join(d_falso, "_versoes.json"), "w"))
        serve, pq = R._staging_serve(d_falso, pdf("meta"))
        checa("reuso: carimbo com hash DIFERENTE não serve", not serve, pq)

        # 4) sem _OK nunca reusa · sem o schema do tipo nunca reusa (a _staging_atual de 27/Jul, viva)
        for t in SCHEMA:
            serve, _ = R._staging_serve(montar(t, com_ok=False, pasta_do_pdf=pdf(t)), pdf(t))
            checa(f"reuso: sem _OK não reusa ({t})", not serve)
            serve, _ = R._staging_serve(montar(t, com_schema=False, pasta_do_pdf=pdf(t)), pdf(t))
            checa(f"reuso: sem o schema de '{t}' não reusa", not serve)


# ══════════════ N+1 · PDF SEM PASTA DE TIPO NÃO ENTRA NA FILA (LEI 8) ══════════════
def teste_pdf_sem_pasta_nao_entra():
    """Um PDF solto na raiz de CLASSIFICADOS é um PDF SEM TIPO — e o `tipo_do_documento` devolvia
    'original' calado, escolhendo motor e prompt no chute. Adivinhar é a segunda fonte de verdade
    que a LEI 8 proíbe."""
    import os, tempfile, sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import rodar_em_blocos as R

    with tempfile.TemporaryDirectory() as tmp:
        for d in ("ARTIGOS_ORIGINAIS", "REVISOES", "GUIDELINES", "PASTA_INVENTADA"):
            os.makedirs(os.path.join(tmp, d), exist_ok=True)
            open(os.path.join(tmp, d, "a.pdf"), "w").write("x")
        open(os.path.join(tmp, "solto.pdf"), "w").write("x")          # na raiz
        fila, fora = R._pdfs_na_fila(tmp)
        checa("fila: só entram PDFs de pasta de tipo conhecida", len(fila) == 3, f"veio {len(fila)}")
        checa("fila: PDF na raiz de CLASSIFICADOS fica de FORA",
              any(f.endswith("solto.pdf") for f in fora))
        checa("fila: PDF em pasta inventada fica de FORA",
              any("PASTA_INVENTADA" in f for f in fora))


# ══════════════ N+2 · O NULL DO NHLBI SOBREVIVE À CONVERSÃO P/ O GOOGLE (03/Ago) ══════════════
def teste_schema_do_google():
    """O `responseSchema` do Google é OpenAPI, não JSON Schema: não aceita `type` como lista.
    Nossos FATOS usam `["boolean","null"]` para separar os TRÊS estados do NHLBI —
    true=fez · false=NÃO fez · null=NÃO REPORTA. Perder o null na conversão apagaria a diferença
    entre "o estudo não cegou" e "o estudo não conta se cegou", que é meia nota de rigor.
    Função pura: sem rede, sem LLM."""
    import os, sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import llm_client as L
    import analise as A

    conv = L._schema_para_gemini
    checa("google: [boolean,null] vira nullable",
          conv({"type": ["boolean", "null"]}) == {"type": "boolean", "nullable": True})
    checa("google: [number,null] vira nullable",
          conv({"type": ["number", "null"]}) == {"type": "number", "nullable": True})
    checa("google: [integer,null] vira nullable",
          conv({"type": ["integer", "null"]}) == {"type": "integer", "nullable": True})
    checa("google: tipo simples não é mexido", conv({"type": "string"}) == {"type": "string"})
    checa("google: additionalProperties é removido",
          "additionalProperties" not in conv({"type": "object", "additionalProperties": False}))
    checa("google: enum sobrevive",
          conv({"type": "string", "enum": ["a", "b"]}).get("enum") == ["a", "b"])

    # e agora nos SCHEMAS DE VERDADE: nenhum `type` pode continuar sendo lista em lugar nenhum
    def varre(s, caminho=""):
        ruins = []
        if isinstance(s, dict):
            if isinstance(s.get("type"), list):
                ruins.append(caminho or "<raiz>")
            for k, v in s.items():
                ruins += varre(v, f"{caminho}.{k}" if caminho else k)
        elif isinstance(s, list):
            for i, v in enumerate(s):
                ruins += varre(v, f"{caminho}[{i}]")
        return ruins

    # ⚠️ 04/Ago — ESTA LISTA ERA CHUMBADA e dizia
    #      ("SCHEMA_FATOS", "SCHEMA_FATOS_DIRETRIZ", "SCHEMA_FATOS_REVISAO")
    # Quando o SCHEMA_FATOS_META nasceu (03/Ago), ninguém o acrescentou aqui — e a bateria
    # continuou dando APROVADO, porque um teste que não olha para o schema novo não tem como
    # reprovar. A meta-análise rodou em produção com a conversão para o Google NUNCA testada.
    #
    # É o mesmo defeito que custou os 10 artigos, com outra roupa: uma lista escrita à mão que
    # não cresce quando o sistema cresce. A cura é a mesma — DESCOBRIR em vez de LISTAR.
    for nome in sorted(n for n in dir(A)
                       if n.startswith("SCHEMA_FATOS") and isinstance(getattr(A, n), dict)):
        original = getattr(A, nome)
        ruins = varre(conv(original))
        checa(f"google: {nome} sem `type` em lista após conversão", not ruins,
              f"sobrou em {ruins[:4]}")
        # e a conversão NÃO pode perder campo: mesmo número de propriedades no topo
        checa(f"google: {nome} não perde propriedades",
              len(conv(original).get("properties", {})) == len(original.get("properties", {})))


# ══════════════ N+3 · O ESTUDO NEGATIVO NÃO PODE SER PUNIDO POR SER NEGATIVO (04/Ago) ══════════════
def teste_nulo_informativo():
    """O caso que quase inverteu o produto: a meta de dados individuais de betabloqueador pós-IAM com
    FE preservada (NEJM 2026 — 5 RCTs, 17.801 pacientes) levou NOTA 4/10, que na escala do CardioDaily
    é "não serve de base para conduta".

    Palavras do Dr. Eduardo: *"antes eu ensinava o MONABICHA aos residentes. O M caiu, o O caiu, o B
    deixou de ser mantra. Se o meu programa está na contramão disto, meu programa está totalmente
    errado."* Metade da cardiologia que ele ensina veio de estudo NEGATIVO.

    A regra: `ausencia_de_efeito_demonstrada` não tem teto — MAS só vale com as DUAS provas
    (IC exclui benefício relevante + poder declarado). Sem elas, o motor rebaixa para `incerto`."""

    def rc(classe, ic=None):
        d = {"classificacao": classe}
        if ic is not None:
            d["ic_exclui_beneficio_relevante"] = ic
        return d

    # ── 1) o nulo DEMONSTRADO não tem teto: pode chegar ao topo, como qualquer positivo forte
    bom = _bom(pergunta="intervencao", desenho="rct", efeito_grande=True,
               relevancia_clinica=rc("ausencia_de_efeito_demonstrada", ic=True))
    r = N.score(bom)
    checa("nulo demonstrado: SEM teto de MCID", r["teto_mcid"] == 10, f"veio {r['teto_mcid']}")
    checa("nulo demonstrado: pode chegar a 10", r["aplic"] == 10, f"veio {r['aplic']}")
    checa("nulo demonstrado: NUNCA cai na faixa de descarte (<6)", r["aplic"] >= 6)

    # ── 2) o caso REAL: sem o conserto, este artigo levava teto 6 e era jogado fora
    reboot = _bom(pergunta="intervencao", desenho="meta", desfecho_duro=True,
                  relevancia_clinica=rc("ausencia_de_efeito_demonstrada", ic=True))
    r = N.score(reboot)
    checa("betabloqueador pós-IAM (nulo, poder ok, IC exclui): publica", r["aplic"] >= 6,
          f"veio {r['aplic']} — é o bug de 04/Ago voltando")

    # ── 3) DEIXAR DE FAZER também é mudar conduta
    forte = _bom(pergunta="intervencao", desenho="rct", efeito_grande=True, desfecho_duro=True,
                 relevancia_clinica=rc("ausencia_de_efeito_demonstrada", ic=True))
    r = N.score(forte)
    checa("nulo demonstrado com nota alta: muda_conduta = SIM", r["muda_conduta"] == "SIM",
          f"veio {r['muda_conduta']} — 'retirar a droga' É conduta")

    # ── 4) o motor NÃO aceita a palavra do modelo sem prova
    sem_ic = _bom(pergunta="intervencao", desenho="rct", efeito_grande=True,
                  relevancia_clinica=rc("ausencia_de_efeito_demonstrada", ic=False))
    checa("nulo SEM 'IC exclui benefício' → rebaixa p/ incerto (teto 7)",
          N.score(sem_ic)["teto_mcid"] == 7, f"veio {N.score(sem_ic)['teto_mcid']}")
    sem_poder = _bom(pergunta="intervencao", desenho="rct", efeito_grande=True, poder_ok=False,
                     relevancia_clinica=rc("ausencia_de_efeito_demonstrada", ic=True))
    checa("nulo SEM poder declarado → rebaixa p/ incerto (teto 7)",
          N.score(sem_poder)["teto_mcid"] == 7, f"veio {N.score(sem_poder)['teto_mcid']}")
    checa("nulo sem prova nenhuma: muda_conduta = NÃO", N.score(sem_poder)["muda_conduta"] == "NÃO")

    # ── 5) e os tetos ANTIGOS continuam valendo — o conserto não pode abrir a porta pro lixo
    for classe, teto in (("significativo_mas_abaixo_do_mcid", 6), ("nao_relevante", 6), ("incerto", 7)):
        r = N.score(_bom(pergunta="intervencao", desenho="rct", efeito_grande=True,
                         relevancia_clinica=rc(classe)))
        checa(f"teto antigo intacto: {classe} ≤ {teto}", r["teto_mcid"] == teto, f"veio {r['teto_mcid']}")


# ══════════════ N+4 · O EXTRATOR DA META E OS 6 DOMÍNIOS (04/Ago) ══════════════
def teste_extrator_da_meta():
    """O motor META lia `a["qualidade_meta"]` desde que foi escrito — e o extrator NUNCA produziu
    esse bloco. Medido em 04/Ago: `conclusoes` (25% do peso) ficava travado em 6 para sempre,
    `vies_estudos` (15%) idem. Uma meta PERFEITA não passava de ~7,7 por construção.

    Função pura: sem LLM, sem rede."""
    import os, sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import analise as A

    # ── o schema existe e cobre o que o motor procura ──
    campos = set(A.SCHEMA_FATOS_META["properties"]["qualidade_meta"]["properties"])
    for c in ("k_estudos", "n_bases", "protocolo_registrado", "vies_mudou_interpretacao",
              "heterogeneidade_investigada", "conclusao_alem_da_evidencia", "limitacoes_reconhecidas"):
        checa(f"meta: o extrator produz '{c}' (o motor já lia)", c in campos)
    for c in ("intervalo_predicao_reportado", "tau2_reportado", "peso_maior_estudo_pct",
              "excluidos_listados_com_motivo", "extracao_em_duplicata", "grade_usado",
              "teste_funnel_indicado", "modelo_apropriado_p_heterogeneidade"):
        checa(f"meta: campo novo do PRISMA/AMSTAR-2 '{c}' está no schema", c in campos)

    def meta(**qm):
        return _bom(pergunta="intervencao", desenho="meta", tipo_documento="meta",
                    qualidade_nhlbi={"pergunta_focada": True, "elegibilidade_predefinida": True,
                                     "busca_sistematica_abrangente": True, "revisao_em_duplicata": True,
                                     "qualidade_estudos_avaliada": True, "vies_publicacao_avaliado": True,
                                     "heterogeneidade_avaliada": True, "i2_valor": 20.0},
                    qualidade_meta=dict(k_estudos=12, n_bases=4, **qm))

    # ── os campos da ESCADA (04/Ago) ──
    for c in ("mistura_ecr_observacional_no_primario", "so_ecr_baixo_risco_vies",
              "trim_and_fill_feito", "trim_and_fill_perdeu_significancia",
              "desfecho_primario_duro", "nnt_agrupado", "tsa_feita", "tsa_cruzou_fronteira",
              "analise_sensibilidade_leave_one_out", "subgrupo_pre_especificado",
              "meta_regressao", "q_cochran_p"):
        checa(f"meta: campo da ESCADA '{c}' está no schema", c in campos)

    # ══ 04/Ago — EU MEXI NO TESTE, NÃO NA REGRA, E ESTÁ ESCRITO AQUI ══════════════════════
    # Este fixture chamava-se "impecável" e não trazia NENHUM fato da Escada. Depois que o
    # Dr. Eduardo especificou a Escada de Avaliação Crítica, "impecável" passou a significar
    # MAIS COISA: não basta caprichar no método (os 6 domínios), tem de passar nos degraus —
    # só ECR de baixo risco, heterogeneidade explorada, robusto ao Trim-and-Fill, desfecho DURO.
    # O fixture antigo batendo no teto 8 é o motor OBEDECENDO à regra nova, não um defeito.
    # Por isso quem muda é o fixture. Se um dia eu afrouxar a regra para o teste passar, é
    # porque errei — a regra é dele, o teste é meu.
    ESCADA_OK = dict(so_ecr_baixo_risco_vies=True,
                     mistura_ecr_observacional_no_primario=False,
                     analise_sensibilidade_leave_one_out=True,
                     subgrupo_pre_especificado=True,
                     trim_and_fill_feito=True,
                     trim_and_fill_perdeu_significancia=False,
                     desfecho_primario_duro=True, nnt_agrupado=18,
                     tsa_feita=True, tsa_cruzou_fronteira=True)

    # ── o teto sumiu: uma meta impecável agora ALCANÇA o topo ──
    perfeita = meta(protocolo_registrado=True, extracao_em_duplicata=True,
                    excluidos_listados_com_motivo=True, vies_mudou_interpretacao=True,
                    heterogeneidade_investigada=True, tau2_reportado=True,
                    intervalo_predicao_reportado=True, funnel_plot_feito=True,
                    grade_usado=True, limitacoes_reconhecidas=True, **ESCADA_OK)
    # ⚠️ A HISTÓRIA DESTE TESTE, porque ela ensina (04/Ago):
    # 1ª versão: cobrei `aplic >= 9`. Reprovou em 8, porque `_TETO_INTERVENCAO["meta"] = 8` capava
    #   por cima. O reflexo errado seria afrouxar a LEI 0 para o teste passar — não fiz, avisei.
    # 2ª versão: passei a medir a ponderação (`nota_meta`) e travei `aplic == 8`.
    # 3ª e atual: o Dr. Eduardo decidiu — *"a nota da meta tem que ser SOMATÓRIA, não tem muito o
    #   que ficar inventando"*. O teto genérico de 8 saiu; a hierarquia dele vive DENTRO do
    #   `nota_meta` (observacionais 7, rede sem transitividade 8), onde é específica.
    s_perf, dom_perf, _ = N.nota_meta(perfeita)
    checa("meta impecável: a somatória dos 6 domínios chega a 9+", s_perf >= 9,
          f"veio {s_perf} — o bloco qualidade_meta não está sendo lido")
    checa("meta impecável: os 6 domínios foram medidos, não chutados", dom_perf is not None)
    checa("SOMATÓRIA É A NOTA: nada capa a meta por cima da ponderação",
          N.score(perfeita)["aplic"] == s_perf,
          f"somatória={s_perf} nota={N.score(perfeita)['aplic']} — voltou algum teto genérico")
    checa("meta de RCTs impecável PODE chegar a 10 (IPD é o melhor tipo)",
          N.score(perfeita)["aplic"] == 10, f"veio {N.score(perfeita)['aplic']}")

    # ── e o vazio continua sendo punido (o conserto não pode virar régua frouxa) ──
    s_vazia, _, _ = N.nota_meta(meta())
    checa("meta sem nenhum dos fatos novos vale MENOS que a impecável",
          s_vazia < s_perf, f"impecável={s_perf} vazia={s_vazia}")

    # ── PRISMA 13d: o intervalo de predição que cruza o nulo derruba a heterogeneidade ──
    d1 = N.dominios_meta(perfeita)
    d2 = N.dominios_meta(meta(heterogeneidade_investigada=True, intervalo_predicao_reportado=True,
                              intervalo_predicao_cruza_nulo=True))
    checa("PRISMA: predição que cruza o nulo baixa a heterogeneidade",
          d2["heterogeneidade"] < d1["heterogeneidade"])

    # ── Cochrane cap.13: com k<10 NÃO se testa funnel — nem prêmio, nem castigo ──
    poucos = _bom(pergunta="intervencao", desenho="meta", tipo_documento="meta",
                  qualidade_nhlbi={"i2_valor": 20.0, "vies_publicacao_avaliado": False},
                  qualidade_meta={"k_estudos": 6, "modelo_estatistico": "aleatorio"})
    checa("Cochrane: k<10 não é punido por não ter funnel",
          N.dominios_meta(poucos)["vies_publicacao"] == 7,
          f"veio {N.dominios_meta(poucos)['vies_publicacao']}")

    # ── a hierarquia da tabela do Dr. Eduardo: observacional NUNCA equivale a RCT ──
    obs = dict(perfeita); obs["desenhos_incluidos"] = "observacionais"
    checa("meta de OBSERVACIONAIS tem teto 7 ('nunca equivale a RCT')",
          N.nota_meta(obs)[0] <= 7 and N.score(obs)["aplic"] <= 7,
          f"ponderação={N.nota_meta(obs)[0]} aplic={N.score(obs)['aplic']}")

    # ── dominância: se um estudo carrega o peso, a meta É aquele estudo ──
    dom = N.dominios_meta(meta(heterogeneidade_investigada=True, peso_maior_estudo_pct=72.0))
    checa("dominância ≥60% do peso derruba a heterogeneidade", dom["heterogeneidade"] <= 6)

    # ── subgrupo tratado como principal é o clássico: reprova as conclusões ──
    sub = N.dominios_meta(meta(limitacoes_reconhecidas=True, subgrupo_tratado_como_principal=True))
    checa("subgrupo vendido como resultado principal → conclusões 3", sub["conclusoes"] == 3)


# ══════════════ N+5 · A IPD PRÉ-PLANEJADA NÃO PODE SER PUNIDA POR SER IPD (04/Ago) ══════════════
def teste_ipd_nao_e_punida():
    """*"Você deu 7 para um artigo que é praticamente 10 — não comemore, resolva, está errado."*

    A meta de betabloqueador pós-IAM (NEJM 2026 — IPD PRÉ-PLANEJADA, 5 RCTs, 17.801 pacientes,
    desfecho duro, tirou uma droga da prática) saía 7. O motivo era o de sempre, uma camada abaixo:
    o INSTRUMENTO NÃO SERVIA PARA O OBJETO. A régua de 6 domínios foi desenhada para meta de dados
    AGREGADOS, que nasce de busca na literatura. Uma IPD pré-planejada não busca base nenhuma —
    os ensaios combinam juntar os dados ANTES de o resultado existir.

    O sistema cobrava dela: bases pesquisadas, funnel plot, heterogeneidade clínica. Três coisas que
    numa IPD ou não se aplicam ou são a razão dela existir."""

    NHLBI = {"pergunta_focada": True, "elegibilidade_predefinida": True, "i2_valor": 20.0,
             "heterogeneidade_avaliada": True, "qualidade_estudos_avaliada": True}
    # 04/Ago — a Escada exige que o fixture DIGA o que a IPD do NEJM é: 5 ECRs, RoB 2, nenhum
    # observacional na mistura. Não é afrouxar a régua; é o fixture parar de omitir o que o
    # artigo real declara. (O `desfecho_duro=True` já vem do _bom e agora o crivo o enxerga.)
    QM = dict(so_ecr_baixo_risco_vies=True, mistura_ecr_observacional_no_primario=False,
              k_estudos=5, n_total=17801, n_bases=1, protocolo_registrado=True,
              busca_sistematica_abrangente=False, heterogeneidade_investigada=True,
              tau2_reportado=True, heterogeneidade_clinica_relevante=True,
              teste_funnel_indicado=False, rob_ferramenta="RoB 2",
              limitacoes_reconhecidas=True, conclusao_alem_da_evidencia=False,
              modelo_estatistico="fixo")

    def meta(tipo):
        return _bom(pergunta="intervencao", desenho="meta", tipo_documento="meta",
                    desfecho_duro=True, qualidade_nhlbi=dict(NHLBI),
                    qualidade_meta=dict(QM, tipo_meta=tipo))

    ipd, agr = meta("ipd"), meta("dados_agregados")
    d_ipd, d_agr = N.dominios_meta(ipd), N.dominios_meta(agr)

    # ── 1) os três domínios que mudam, e SÓ eles ──
    checa("IPD: busca não é punida por ter 1 base", d_ipd["busca"] >= 9,
          f"veio {d_ipd['busca']} (agregada dá {d_agr['busca']})")
    checa("IPD: viés de publicação é 10 (eliminado por desenho)", d_ipd["vies_publicacao"] == 10,
          f"veio {d_ipd['vies_publicacao']}")
    checa("IPD: heterogeneidade clínica não capa (é o que a IPD examina)",
          d_ipd["heterogeneidade"] > d_agr["heterogeneidade"],
          f"ipd={d_ipd['heterogeneidade']} agregada={d_agr['heterogeneidade']}")
    for k in ("pico", "vies_estudos", "conclusoes"):
        checa(f"IPD: '{k}' NÃO muda (não é privilégio, é instrumento certo)",
              d_ipd[k] == d_agr[k], f"ipd={d_ipd[k]} agregada={d_agr[k]}")

    # ── 2) o caso REAL: o artigo do MONABICHA precisa publicar com áudio ──
    s_ipd, _, _ = N.nota_meta(ipd)
    checa("betabloqueador pós-IAM (IPD do NEJM): nota ≥ 8", s_ipd >= 8,
          f"veio {s_ipd} — era 5 em 03/Ago e 7 na 1ª tentativa de 04/Ago")
    checa("betabloqueador: a nota é a SOMATÓRIA, sem teto por cima",
          N.score(ipd)["aplic"] == s_ipd, "voltou algum teto sobre a meta")

    # ── 3) e a meta AGREGADA continua sendo cobrada do que é dela ──
    checa("agregada com 1 base ainda é punida na busca", d_agr["busca"] <= 7,
          f"veio {d_agr['busca']} — a régua da agregada não pode afrouxar junto")
    checa("agregada com heterogeneidade clínica ainda capa", d_agr["heterogeneidade"] <= 5)

    # ── 4) a ferramenta de RoB vive no bloco da META, e o motor tem de ler de lá ──
    sem_nhlbi = _bom(pergunta="intervencao", desenho="meta", tipo_documento="meta",
                     qualidade_nhlbi={"i2_valor": 20.0},
                     qualidade_meta=dict(QM, tipo_meta="ipd"))
    checa("RoB 2 declarado em qualidade_meta conta como viés avaliado",
          N.dominios_meta(sem_nhlbi)["vies_estudos"] > 3,
          "o motor só olhava o qualidade_nhlbi e achava que ninguém avaliou")


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
    # 06/Ago — A DIRETRIZ NÃO RESPONDE "muda conduta", RESPONDE "confie quanto?"
    checa("diretriz exemplar: RECOMENDADA", r["muda_conduta"] == "RECOMENDADA",
          f"veio {r['muda_conduta']}")


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
    # 06/Ago — ELE MUDOU ESTA REGRA: *"este termo muda conduta se aplica a um RCT — as revisões
    # irão me ajudar a ORGANIZAR O CONHECIMENTO"*. A NOTA continua podendo chegar a 10 (decisão
    # dele de 02/Ago, que segue valendo acima); o que sai é o CAMPO, que faz uma pergunta que a
    # revisão não responde.
    checa("revisão NÃO responde 'muda conduta'", r["muda_conduta"].startswith("N/A"),
          f"veio {r['muda_conduta']} — revisão não testa intervenção, não há conduta a mudar")
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


# ══════════════ 3e · A CASCATA DO CLASSIFICADOR (02/Ago) — o que o LLM NÃO decide ══════════════
def teste_mapa_pubmed():
    """O ERRO REAL DE 02/Ago, que não pode voltar.

    O classificador novo (prompt v3, 99,1 % medido) foi para produção e REPETIU os erros antigos:
    revisão sistemática em REVISOES, Scientific Statement em REVISOES. O LLM não tinha culpa —
    ele NUNCA FOI CHAMADO. O mapa de pubtype do PubMed decide ANTES dele, e mandava:
        ("revisao_geral", {"Review", "Systematic Review"})
      1. "Systematic Review" → revisao_geral  = violação da D-01, que eu tinha corrigido no PROMPT
         e deixado viva AQUI (consertei onde achei, não procurei a regra no resto do sistema)
      2. "Review" tratado como AUTORITATIVO — mas é o balde genérico do PubMed: Scientific Statement,
         revisão narrativa e state-of-the-art são todos "Review". Curto-circuitava o LLM.

    Estas travas são de FUNÇÃO PURA: rodam sem rede, sem PubMed, sem custo. Se alguém reescrever a
    tabela, a Chave 8 reprova antes de virar 350 análises erradas."""
    from classificador_pubmed import map_pubtype, PUBTYPE_GENERICO

    # D-01 (Dr. Eduardo, 31/07): revisão sistemática É meta-análise, MESMA TRILHA.
    for pt in (["Systematic Review"], ["Systematic Review", "Journal Article"],
               ["Meta-Analysis"], ["Systematic Review", "Meta-Analysis"]):
        checa(f"D-01: {pt} → trilha da meta",
              map_pubtype(pt) == "revisao_sistematica_meta_analise", f"veio {map_pubtype(pt)}")

    # "Review" SOZINHO não decide nada — tem de descer até o LLM ler o rótulo impresso
    for pt in (["Review"], ["Review", "Journal Article"], ["Journal Article"], []):
        checa(f"{pt} NÃO é autoritativo (desce p/ o LLM)", map_pubtype(pt) is None,
              f"decidiu {map_pubtype(pt)} e calaria o LLM")
    checa("'Review' está declarado como genérico", "Review" in PUBTYPE_GENERICO)

    # o que o PubMed sabe de verdade continua mandando
    for pt, esperado in ((["Practice Guideline"], "guideline"),
                         (["Guideline"], "guideline"),
                         (["Randomized Controlled Trial"], "artigo_original"),
                         (["Observational Study"], "artigo_original"),
                         (["Editorial"], "ponto_de_vista")):
        checa(f"{pt} → {esperado}", map_pubtype(pt) == esperado, f"veio {map_pubtype(pt)}")

    # PRECEDÊNCIA: um documento com vários rótulos não pode cair no mais fraco
    checa("Practice Guideline vence Review",
          map_pubtype(["Review", "Practice Guideline"]) == "guideline")
    checa("Meta-Analysis vence Review",
          map_pubtype(["Review", "Meta-Analysis"]) == "revisao_sistematica_meta_analise")
    checa("RCT vence Journal Article",
          map_pubtype(["Journal Article", "Randomized Controlled Trial"]) == "artigo_original")

    # ── F-02 · BRIEF REPORT → MINIRREVISÃO (aberta desde 31/Jul, consertada em 02/Ago) ──
    # O Dr. Eduardo reportou em 31/Jul ("SEGUNDA FALHA - BRIEF REPORTING COMO ARTIGO ORIGINAL"),
    # ficou no docs/FALHAS_AUDITORIA.md como F-02, e em 02/Ago voltou idêntica: "errou 6 artigos
    # originais que eram minirevisões — todos tinham acima do título BRIEF REPORT".
    # A palavra "brief" não existia em NENHUM bloco do classificador. Esta trava impede o retorno.
    from classificador_ouro import rotulo_topo
    CORPO = "\nEfeito da droga X em 400 pacientes randomizados\nMethods: we enrolled 400 patients"
    for rot in ("BRIEF REPORT", "Brief Report", "brief reports", "BRIEF COMMUNICATION",
                "Short Report", "RESEARCH BRIEF", "Short Communication"):
        checa(f"F-02: '{rot}' → minirevisao", rotulo_topo(rot + CORPO)[0] == "minirevisao",
              f"veio {rotulo_topo(rot + CORPO)[0]}")
    # e os outros rótulos não podem ter sido contaminados
    for rot, esperado in (("EDITORIAL", "ponto_de_vista"), ("Viewpoint", "ponto_de_vista"),
                          ("RESEARCH LETTER", "DESCARTE"), ("Correspondence", "DESCARTE"),
                          ("ORIGINAL INVESTIGATION", None), ("Seminar", None),
                          ("CLINICAL RESEARCH", None)):
        checa(f"'{rot}' continua → {esperado}", rotulo_topo(rot + CORPO)[0] == esperado,
              f"veio {rotulo_topo(rot + CORPO)[0]}")
    # 'brief' NO MEIO do texto não pode disparar (é rótulo de LINHA INTEIRA, no topo)
    checa("'brief report' no meio de uma frase NÃO dispara",
          rotulo_topo("Original Article\nWe present a brief report of our findings")[0] is None)
    # e o prompt (bloco 3) tem de dizer a mesma coisa — LEI 9
    import classificador_prompt as _CP
    checa("bloco 3: BRIEF REPORT também está no prompt", "BRIEF REPORT" in _CP.PROMPT)
    checa("bloco 3: SEMINAR também está no prompt", "SEMINAR" in _CP.PROMPT)
    checa("prompt foi versionado ao mudar (senão a prova não refaz)",
          _CP.PROMPT_VERSAO != "v3", f"continua {_CP.PROMPT_VERSAO}")

    # ── "SEM BASE" NÃO SE MEDE POR TAMANHO (erro meu, medido em 03/Ago no lote real) ──
    # A regra original exigia 12 caracteres de prova. Seis artigos foram para REVISAO_HUMANA com
    # confiança ALTA citando o RÓTULO IMPRESSO da revista — a prova mais forte que o prompt aceita.
    # Quanto MELHOR o rótulo (curto e canônico), mais eu recusava. Estes são os casos REAIS do lote.
    def sem_base(conf, prova):
        return (conf == "baixa") or not (prova or "").strip()

    for conf, prova, nome in [("alta", "REVIEW", "Circulation Arrhythmia"),
                              ("alta", "FRONTIERS", "Circulation MACE-Cog"),
                              ("alta", "Viewpoint", "JAMA Cardiology"),
                              ("alta", "VIEWPOINT", "JAMA Cardio-Onc"),
                              ("alta", "TRIBUTE", "JACC Braunwald"),
                              ("alta", "A Review", "JAMA Atrial Dyssynchrony")]:
        checa(f"rótulo curto NÃO vai p/ revisão humana: {prova!r} ({nome})",
              not sem_base(conf, prova), f"{len(prova)} chars foram recusados")
    # e o que DEVE ir para revisão humana continua indo
    checa("confiança baixa → revisão humana", sem_base("baixa", "ORIGINAL INVESTIGATION"))
    checa("sem trecho nenhum → revisão humana", sem_base("alta", ""))
    checa("só espaço em branco → revisão humana", sem_base("alta", "   "))
    checa("confiança alta com prova → NÃO vai", not sem_base("alta", "Original Investigation"))

    # ── DOI EMPRESTADO: o PDF traz o DOI de OUTRO artigo (caso real do Seminar do Lancet) ──
    from classificador_pubmed import doi_e_deste_artigo as ok
    LANCET = ("Seminar www.thelancet.com Vol 407 March 7, 2026 Lancet 2026; 407: 1000-13 "
              "Department of Cardiovascular and Metabolic Medicine, University of Liverpool "
              "Atrial fibrillation Deirdre A Lane, Gregory Y H Lip. Atrial fibrillation affects "
              "approximately 37.6 million people worldwide. The Atrial fibrillation Better Care "
              "pathway is recommended for integrated care.")
    emprestado = {"title": "The Atrial Fibrillation Better Care Pathway for Integrated Care of "
                           "Atrial Fibrillation: A Systematic Review and Meta-Analysis",
                  "journal": "Thrombosis and haemostasis"}
    checa("DOI emprestado é PEGO (Seminar do Lancet com DOI da Thieme)",
          not ok(emprestado, LANCET), "passou como se fosse deste artigo")
    # e o do próprio artigo continua valendo — a trava não pode acusar inocente
    for bom in ({"title": "Atrial fibrillation", "journal": "Lancet"},
                {"title": "Atrial fibrillation", "journal": "The Lancet"},
                {"title": "", "journal": "Lancet"},                       # só a revista bate
                {"title": "Atrial fibrillation", "journal": ""}):         # só o título bate
        checa(f"DOI verdadeiro NÃO é acusado ({bom})", ok(bom, LANCET))
    checa("sem metadado nenhum, não acusa", ok({}, LANCET))
    checa("sem texto, não acusa", ok(emprestado, ""))
    # palavra genérica de revista não pode salvar um DOI emprestado
    checa("'Journal'/'Cardiology' sozinhas não validam a revista",
          not ok({"title": "Outro artigo totalmente diferente sobre insuficiencia renal cronica",
                  "journal": "Journal of Cardiology"}, LANCET))

    # A TABELA em si, não o texto do arquivo. (1ª versão desta trava era grep e se acusou sozinha:
    # eu tinha CITADO a linha errada no comentário que a documenta. Conferir estrutura, não string.)
    from classificador_pubmed import _PUBTYPE_PRIORITY
    destinos = {canon for canon, _ in _PUBTYPE_PRIORITY}
    checa("nenhum pubtype decide 'revisao_geral' (é o balde genérico — quem decide é o LLM)",
          "revisao_geral" not in destinos, f"tabela devolve {sorted(destinos)}")
    for canon, gat in _PUBTYPE_PRIORITY:
        if "Systematic Review" in gat:
            checa("D-01 na tabela: 'Systematic Review' só na trilha da meta",
                  canon == "revisao_sistematica_meta_analise", f"está em '{canon}'")
        checa(f"'Review' genérico não entrou em '{canon}'", "Review" not in gat)


# ══════════════ 3f · A PASTA MANDA — prompt E motor (03/Ago, tarefa #34) ══════════════
def teste_a_pasta_manda():
    """O ERRO QUE ISTO IMPEDE — palavras do Dr. Eduardo, 03/Ago:
    'consertei manualmente os artigos nas pastas e na primeira análise ele me lê uma REVISÃO
     com PROMPT DE ARTIGO ORIGINAL... A PASTA DE REVISÃO SÓ PODE APLICAR PROMPT DE REVISÃO.'

    O código escolhia o prompt pela PASTA só para GUIDELINES e REVISOES; para ARTIGOS_ORIGINAIS
    e META_ANALISES olhava o campo `desenho` dos FATOS. Duas fontes de verdade (LEI 8 proíbe).
    Resultado: a correção MANUAL da pasta era ignorada — que é o pior tipo de bug, porque
    desfaz em silêncio o trabalho que a pessoa acabou de fazer à mão."""
    from analisador import escolher_prompt, tipo_do_documento

    ESPERADO = {"ARTIGOS_ORIGINAIS": "redator_original_prompt.md",
                "META_ANALISES":     "redator_meta_prompt.md",
                "GUIDELINES":        "redator_guideline_prompt.md",
                "REVISOES":          "redator_revisao_prompt.md",
                "MINIRREVISOES":     "redator_revisao_prompt.md",
                "EDITORIAIS":        "redator_revisao_prompt.md"}
    # os FATOS mentem de propósito, em TODAS as combinações. A pasta tem de vencer sempre.
    for pasta, prompt in ESPERADO.items():
        for desenho in ("rct", "meta", "coorte", "nao_classificavel", "serie_de_casos", None):
            p = f"/x/CLASSIFICADOS/{pasta}/artigo.pdf"
            got = escolher_prompt({"desenho": desenho}, p)
            checa(f"pasta {pasta} + fatos(desenho={desenho}) → {prompt}", got == prompt,
                  f"veio {got}")
    # e o MOTOR também obedece à pasta (o analisador injeta tipo_documento antes de pontuar)
    MOTOR = {"ARTIGOS_ORIGINAIS": "ORIGINAL", "META_ANALISES": "META",
             "GUIDELINES": "DIRETRIZ", "REVISOES": "REVISAO"}
    for pasta, motor in MOTOR.items():
        fatos = _bom(pergunta="intervencao", desenho="rct")          # os fatos dizem RCT
        fatos["tipo_documento"] = tipo_do_documento(f"/x/CLASSIFICADOS/{pasta}/a.pdf")
        r = N.score(fatos)
        checa(f"pasta {pasta} + fatos(desenho=rct) → motor {motor}", r["motor"] == motor,
              f"veio {r['motor']}")
    # PDF fora das pastas conhecidas: cai em 'original', que é a rede
    checa("PDF solto → prompt original (rede)",
          escolher_prompt({"desenho": "meta"}, "/tmp/qualquer.pdf") == "redator_original_prompt.md")


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



def teste_todo_schema_tem_a_capa():
    """Todo extrator PEDE título, revista e ano — senão o contrato recusa lá na frente.

    ═══ O QUE ESTA TRAVA TERIA EVITADO (03→04/Ago/2026) ═══

    O `SCHEMA_FATOS_META` foi escrito do zero, com os blocos de método da meta-análise: PRISMA,
    Cochrane, AMSTAR-2, GRADE. Ficou bom no que se propunha e não tinha a CAPA — titulo, revista,
    ano — que o extrator do artigo original já pedia desde sempre.

    Ninguém percebeu, porque nada a montante quebra: o LLM responde, o JSON valida, o motor
    pontua, o redator escreve, o áudio é gerado, o visual é renderizado. Dez meta-análises
    saíram com nota 6 a 9, pacote completo. **O defeito só aparece no PORTÃO DE PUBLICAÇÃO**,
    depois de tudo pago:

        "data_publicacao: ausente · titulo vazio · revista vazia"   × 10

    O portão estava certo. Faltava alguém comparar duas listas — o que o schema PEDE e o que o
    contrato EXIGE — e isso é uma função pura, custa microssegundos, e não precisa de LLM,
    de rede, nem do Dr. Eduardo rodando nada.

    É a LEI 9 em forma de teste: a regra "todo artigo tem capa" mora no schema, no prompt, no
    ficha_site e no pdf_analise. Aqui a gente prova que o PRIMEIRO bloco da corrente não a perdeu.
    """
    import analise as A
    exigidos = {"titulo", "revista", "ano"}
    schemas = {n: getattr(A, n) for n in dir(A)
               if n.startswith("SCHEMA_FATOS") and isinstance(getattr(A, n), dict)}
    assert schemas, "nenhum SCHEMA_FATOS* encontrado em analise.py — a varredura ficou cega"
    for nome, esq in sorted(schemas.items()):
        tem = set(esq.get("properties", {}))
        falta = exigidos - tem
        assert not falta, (
            f"{nome} não pede {sorted(falta)}. O contrato de publicação EXIGE esses campos: "
            f"artigo nenhum deste tipo vai conseguir subir, e você só descobre isso DEPOIS de "
            f"pagar a análise inteira (foi o que aconteceu com 10 metas em 03/Ago).")
    return f"{len(schemas)} schema(s) com a capa completa"


def teste_escada_da_meta():
    """A ESCADA DE AVALIAÇÃO CRÍTICA — especificação do Dr. Eduardo, 04/Ago/2026.

    O caso que a originou: TOCILIZUMABE na COVID-19. Em 2021 as meta-análises — inclusive a nota
    técnica do Ministério da Saúde — diziam que a droga não reduzia mortalidade, apoiadas num
    conjunto que MISTURAVA ECR com estudo observacional. O RECOVERY, um ensaio só com N adequado,
    encerrou a discussão sozinho. A conta da meta estava certa; a matéria-prima é que não prestava.

    Função pura: sem LLM, sem rede, sem banco.
    """
    def m(**qm):
        return _bom(pergunta="intervencao", desenho="meta", tipo_documento="meta",
                    qualidade_nhlbi={"pergunta_focada": True, "elegibilidade_predefinida": True,
                                     "busca_sistematica_abrangente": True, "revisao_em_duplicata": True,
                                     "qualidade_estudos_avaliada": True, "vies_publicacao_avaliado": True,
                                     "heterogeneidade_avaliada": True, "i2_valor": qm.pop("i2", 20.0)},
                    qualidade_meta={**dict(k_estudos=12, n_bases=4, protocolo_registrado=True,
                                           vies_mudou_interpretacao=True, grade_usado=True,
                                           limitacoes_reconhecidas=True, funnel_plot_feito=True,
                                           heterogeneidade_investigada=True), **qm})

    OK = dict(so_ecr_baixo_risco_vies=True, mistura_ecr_observacional_no_primario=False,
              analise_sensibilidade_leave_one_out=True, trim_and_fill_feito=True,
              trim_and_fill_perdeu_significancia=False, desfecho_primario_duro=True,
              tsa_feita=True, tsa_cruzou_fronteira=True)

    topo = N.score(m(**OK))["aplic"]
    checa("escada: meta que passa nos 4 crivos chega ao topo", topo >= 9, f"veio {topo}")

    # DEGRAU 2 — o caso tocilizumabe: misturou ECR com observacional → FATAL, teto 5
    r = N.score(m(**{**OK, "mistura_ecr_observacional_no_primario": True}))
    checa("escada D2: misturar ECR com observacional é FATAL (teto 5)", r["aplic"] <= 5,
          f"veio {r['aplic']} — é o erro que atrasou o tocilizumabe")

    # DEGRAU 4 — o efeito não sobreviveu ao Trim-and-Fill → FATAL, teto 5
    r = N.score(m(**{**OK, "trim_and_fill_perdeu_significancia": True}))
    checa("escada D4: perder significância no Trim-and-Fill é FATAL (teto 5)", r["aplic"] <= 5,
          f"veio {r['aplic']} — 'se perdeu, não use'")

    # DEGRAU 3 — I² alto SEM exploração → em cima do muro (teto 6)
    r = N.score(m(i2=78.0, **{**OK, "analise_sensibilidade_leave_one_out": False,
                              "heterogeneidade_investigada": False}))
    checa("escada D3: I² alto sem explorar fica em cima do muro (teto 6)", r["aplic"] <= 6,
          f"veio {r['aplic']}")
    # e I² alto EXPLORADO não é punido do mesmo jeito
    r2 = N.score(m(i2=78.0, **OK))
    checa("escada D3: I² alto porém EXPLORADO não cai para 6", r2["aplic"] > 6, f"veio {r2['aplic']}")

    # DEGRAU 5 — desfecho substituto não chega a 9.
    # A asserção é sobre o TETO da própria escada, não só sobre a nota final: o crivo 4 também
    # capa em 8, então olhar só o número não distingue quem capou. Sabotando o TETO_SURROGATE eu
    # vi a trava NÃO morder — trava que não distingue a causa não prova a causa.
    sub = m(**{**OK, "desfecho_primario_duro": False})
    teto_sub, degraus_sub, _ = N.escada_meta(sub)
    checa("escada D5: desfecho SUBSTITUTO capa em 8 NA ESCADA", teto_sub <= 8, f"teto veio {teto_sub}")
    checa("escada D5: o degrau 5 DIZ que o desfecho é substituto",
          "SUBSTITUTO" in degraus_sub.get("5_utilidade", ""), degraus_sub.get("5_utilidade"))
    checa("escada D5: e a nota final não passa de 8", N.score(sub)["aplic"] <= 8)

    # k<10 não é castigo (Cochrane cap. 13): o teste de assimetria nem era indicado
    r = N.score(m(**{**OK, "k_estudos": 6, "trim_and_fill_feito": False, "funnel_plot_feito": False}))
    checa("escada D4: com k<10 não se cobra teste de viés (Cochrane)", r["aplic"] >= 9,
          f"veio {r['aplic']} — cobrar teste sem poder é punir quem fez certo")

    # NNT é EXTRA que valoriza, NÃO régua (correção do Dr. Eduardo, 04/Ago)
    sem_nnt = N.score(m(**OK))["aplic"]
    com_nnt = N.score(m(**{**OK, "nnt_agrupado": 12}))["aplic"]
    checa("escada D5: NNT é extra, não régua — sua ausência NÃO derruba a nota",
          sem_nnt == com_nnt, f"sem NNT={sem_nnt} com NNT={com_nnt}")
    return "escada: 4 crivos, 2 falhas fatais, 2 tetos"


def teste_bicondicional_nota_e_conduta():
    """A REGRA MAIS IMPORTANTE DE TODAS, nas palavras do Dr. Eduardo (04/Ago/2026):

        *"Toda nota 9 e 10 muda conduta! Se muda a conduta é 9 ou 10, e se é 9 ou 10 é porque
        muda conduta."*

    É uma BICONDICIONAL — nota e `muda_conduta` são o mesmo fato dito de dois jeitos. Até 04/Ago
    eram calculados por TRÊS caminhos independentes que discordavam entre si, e o resultado foi
    medido no Supabase: TRÊS meta-análises publicadas com nota 9 e "muda_conduta: NÃO", ZERO com SIM.

    Esta trava varre TODAS as fixtures e TODOS os desenhos. Se algum dia alguém reintroduzir um
    segundo caminho, morre aqui — e não no banco, depois de publicado.
    """
    casos = []
    for nome, fx in N.FIXTURES.items():
        casos.append((nome, N.score(dict(fx))))
    for d in ("rct", "meta", "coorte", "registro", "observacional_ajustado", "transversal",
              "serie_de_casos", "caso_controle"):
        for q in PERGUNTAS:
            casos.append((f"{d}/{q}", N.score(_bom(pergunta=q, desenho=d))))

    ruins = []
    for nome, r in casos:
        a, md = r["aplic"], r["muda_conduta"]
        if md.startswith("N/A"):
            checa_silencioso = a <= 8
            if not checa_silencioso:
                ruins.append(f"{nome}: N/A mas nota {a}")
            continue
        if (a >= 9) != (md == "SIM"):
            ruins.append(f"{nome}: nota {a} com muda_conduta={md}")
    checa(f"BICONDICIONAL 9/10 ⟺ muda conduta ({len(casos)} casos)", not ruins,
          "; ".join(ruins[:4]))
    return f"{len(casos)} casos, nenhuma contradição"


def teste_escala_de_aplicabilidade_da_meta():
    """A ESCALA que o Dr. Eduardo ditou, número por número (04/Ago/2026):

        0/4 crivos → 4     1/4 → 5     2/4 → 6     3/4 → 8     4/4 → 9 ou 10

    Repare no salto 2→3 (6 para 8) e na ausência do 7: é de propósito, é a régua dele.

    ERRO QUE ELA CORRIGE: eu tinha feito os 4 crivos apenas CAPAREM em 8. Quem falhava nos
    QUATRO ficava com a mesma nota de quem falhava em UM — o algoritmo de beira do leito virava
    um interruptor, quando na escada dele é uma ESCALA. A prova do absurdo foi um PROTOCOLO de
    revisão sistemática (BMJ Open): zero estudos incluídos, zero estimativa de efeito, reprovou
    nos 4 crivos e ficou com 8, porque os 6 domínios de MÉTODO eram bons. Ele viu e disse:
    *"mas o protocolo passa pela escala de aplicabilidade"*.

    Função pura: sem LLM, sem rede, sem banco.
    """
    checa("escala: a tabela é exatamente a que o Dr. Eduardo ditou",
          N.TETO_POR_CRIVO == {4: 10, 3: 8, 2: 6, 1: 5, 0: 4},
          f"veio {N.TETO_POR_CRIVO}")
    checa("escala: não existe teto 7 (o salto 2→3 é 6→8, de propósito)",
          7 not in N.TETO_POR_CRIVO.values())

    def m(**qm):
        return _bom(pergunta="intervencao", desenho="meta", tipo_documento="meta",
                    qualidade_nhlbi={"pergunta_focada": True, "elegibilidade_predefinida": True,
                                     "busca_sistematica_abrangente": True, "revisao_em_duplicata": True,
                                     "qualidade_estudos_avaliada": True, "vies_publicacao_avaliado": True,
                                     "heterogeneidade_avaliada": True, "i2_valor": qm.pop("i2", 20.0)},
                    qualidade_meta={**dict(k_estudos=12, n_bases=4, protocolo_registrado=True,
                                           vies_mudou_interpretacao=True, grade_usado=True,
                                           limitacoes_reconhecidas=True, funnel_plot_feito=True,
                                           heterogeneidade_investigada=True), **qm})

    TUDO = dict(so_ecr_baixo_risco_vies=True, mistura_ecr_observacional_no_primario=False,
                analise_sensibilidade_leave_one_out=True, trim_and_fill_feito=True,
                trim_and_fill_perdeu_significancia=False, desfecho_primario_duro=True,
                tsa_feita=True, tsa_cruzou_fronteira=True)

    # derruba os crivos um a um e confere o teto de CADA degrau da escala
    quedas = [
        ({}, 4, 10),
        ({"desfecho_primario_duro": False, "desfecho_duro": None}, 3, 8),
        ({"desfecho_primario_duro": False, "desfecho_duro": None,
          "i2": 78.0, "analise_sensibilidade_leave_one_out": False,
          "heterogeneidade_investigada": False}, 2, 6),
        ({"desfecho_primario_duro": False, "desfecho_duro": None,
          "i2": 78.0, "analise_sensibilidade_leave_one_out": False,
          "heterogeneidade_investigada": False, "so_ecr_baixo_risco_vies": False}, 1, 5),
    ]
    for extra, n_esperado, teto in quedas:
        dd = extra.pop("desfecho_duro", "manter")
        a = m(**{**TUDO, **extra})
        if dd is None:
            a["desfecho_duro"] = None          # o crivo tem 2 fontes: derruba as duas
        n = sum(1 for v in N.crivos_beira_do_leito(a).values() if v)
        checa(f"escala: {n_esperado}/4 crivos", n == n_esperado, f"contou {n}")
        checa(f"escala: {n_esperado}/4 → teto {teto}",
              N.TETO_POR_CRIVO[n] == teto, f"tabela diz {N.TETO_POR_CRIVO[n]}")

    # o PROTOCOLO: falha em tudo → 4, e 4 está ABAIXO do corte de publicação (6).
    # Um protocolo não tem estudos incluídos: logo não tem I², não tem k, não tem efeito.
    # (Meu 1º fixture deixava o I²=20 do molde e o crivo da heterogeneidade PASSAVA — dava 1/4.
    #  Protocolo com heterogeneidade baixa é contradição: não há o que ser heterogêneo.)
    prot = m(i2=None, **{k: False for k in TUDO})
    prot["qualidade_meta"]["k_estudos"] = 0
    prot["qualidade_meta"]["heterogeneidade_investigada"] = False
    prot["qualidade_meta"]["funnel_plot_feito"] = False
    prot["desfecho_duro"] = None
    r = N.score(prot)
    checa("escala: protocolo (0/4 crivos) vai para 4 e NÃO publica", r["aplic"] <= 4,
          f"veio {r['aplic']} — um protocolo não tem resultado clínico para oferecer")

    # e o crivo do desfecho duro tem DUAS fontes — a nova e a antiga
    a = m(**{**TUDO, "desfecho_primario_duro": None})
    a["desfecho_duro"] = True
    checa("escala: `desfecho_duro` do topo vale quando o campo novo cala",
          N.crivos_beira_do_leito(a)["desfecho_duro"],
          "campo novo ignorando o antigo — foi o que derrubou a IPD do NEJM para 6")
    return "escala 0→4 · 1→5 · 2→6 · 3→8 · 4→9/10"


def teste_carimbo_ve_o_motor():
    """O carimbo do staging tem de vigiar o CÓDIGO que dá a nota, não só os prompts.

    ═══ 04/Ago/2026, 21h39 — A RODADA QUE NÃO FEZ NADA ═══

    O Dr. Eduardo rodou a Chave 2 logo depois de a régua da meta ser reescrita (Escada, escala de
    aplicabilidade, bicondicional). A rodada terminou em segundos, com "reusado (staging pronto)"
    nos 24. Ele desconfiou sozinho — *"foi muito rápido, está certo isso?"* — e não estava:

    O `versoes_atuais` listava só o hash dos PROMPTS. Nenhum prompt tinha mudado desde a rodada
    anterior; o que mudou foi o MOTOR. Como o motor não estava no carimbo, o guarda viu tudo igual,
    reaproveitou o staging e REPUBLICOU as notas da régua velha. Medido no Supabase logo depois:
    um artigo com nota 9 e "muda_conduta: NÃO" — a contradição recém-matada, de volta no banco.

    AGRAVANTE MEU: numa auditoria que ELE pediu ("veja se não faltou commitar nada, se está tudo
    pronto"), eu conferi prompts, schemas, redatores, bateria e cadeias de modelo — e NÃO conferi
    o carimbo, que era o que decidia se a rodada faria alguma coisa. E ainda escrevi na mensagem
    do commit, como fato, que os 24 seriam reanalisados. Não medi.

    Esta trava existe para que o carimbo cego não volte: função pura, sem LLM, sem rede.
    """
    import os, sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import analisador as AN

    v = AN.versoes_atuais("x/META_ANALISES/y.pdf")

    # 1 · o CÓDIGO que dá a nota tem de estar no carimbo
    for chave, arq in (("motor", "notas_prototipo.py"), ("extracao", "analise.py")):
        checa(f"carimbo: vigia o código '{arq}'", chave in v and arq in str(v.get(chave)),
              f"carimbo tem só {sorted(v)} — mudar a régua não invalidaria o staging")

    # 2 · e mudar esse código PRECISA mudar o carimbo (senão a vigilância é decorativa)
    if "motor" not in v:
        return "carimbo SEM o motor — as travas acima já acusaram"   # não quebra: já reprovou
    alvo = os.path.join(os.path.dirname(os.path.abspath(AN.__file__)), "notas_prototipo.py")
    antes = v["motor"]
    with open(alvo, "rb") as fh:
        conteudo = fh.read()
    try:
        with open(alvo, "ab") as fh:
            fh.write(b"\n# sabotagem do teste\n")
        depois = AN.versoes_atuais("x/META_ANALISES/y.pdf")["motor"]
        checa("carimbo: mexer no motor MUDA o carimbo", antes != depois,
              f"antes={antes} depois={depois} — o carimbo não enxerga a mudança")
    finally:
        with open(alvo, "wb") as fh:
            fh.write(conteudo)

    # 3 · e os prompts continuam vigiados (não troquei uma cegueira por outra)
    for chave in ("extrator", "redator", "acri", "audio", "gancho"):
        checa(f"carimbo: continua vigiando o prompt '{chave}'", chave in v)
    return f"carimbo com {len(v)} itens: código + prompts"


def teste_diretriz_nao_tem_porta():
    """A DIRETRIZ SOBE SEMPRE — a exceção da LEI 10, e SÓ ela (05/Ago/2026).

    Palavras do Dr. Eduardo: *"as diretrizes — precisamos manter esta classificação mas não
    teremos nenhum impedimento para subir. Mesmo com as limitações, é o que tem para hoje."*
    E, sobre o alcance: *"ESTA REGRA SÓ VALE PARA DIRETRIZ."*

    POR QUE NÃO É BRECHA NA LEI 10: o CardioDaily é um filtro porque, para uma meta ruim, existe
    outra melhor — reter não custa nada ao leitor. Com diretriz é o contrário: não existe "outra
    diretriz de fibrilação atrial", existe A diretriz. Reter não protege ninguém, só esconde o
    documento que rege a prática e pelo qual o médico será cobrado.

    Medido em 04/Ago: 13 de 31 diretrizes ficavam retidas com nota 4 e 5 — ESC, AHA, ESPEN, NICE.

    Esta trava existe para que ninguém "arrume" isso achando que é bug, e para que a exceção NÃO
    vaze para os outros três tipos.
    """
    import os, sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import analisador as AN

    # 1 · diretriz sobe em QUALQUER nota, com o pacote completo
    for nota in range(0, 11):
        ents, sobe = AN.decidir_entregaveis(nota, "diretriz")
        checa(f"diretriz nota {nota}: SOBE", sobe, "ficou retida")
        for peca in ("ACRI", "texto", "infografico", "audio"):
            checa(f"diretriz nota {nota}: leva '{peca}'", peca in ents, f"veio {ents}")

    # 2 · e a exceção NÃO vaza para os outros três (ordem expressa dele)
    for tipo in ("original", "meta", "revisao_narrativa", None):
        for nota in (0, 3, 5):
            _, sobe = AN.decidir_entregaveis(nota, tipo)
            checa(f"{tipo} nota {nota}: RETÉM (a LEI 10 continua valendo)", not sobe,
                  "a exceção da diretriz vazou para outro tipo")
        _, sobe6 = AN.decidir_entregaveis(6, tipo)
        checa(f"{tipo} nota 6: sobe", sobe6)

    # 3 · o áudio da diretriz é OUTRO prompt, e o carimbo tem de enxergar isso
    #    (senão mexer no roteiro da diretriz não invalida o staging dela — LEI 9)
    a_dir = AN.versoes_atuais("x/GUIDELINES/y.pdf")["audio"]
    a_out = AN.versoes_atuais("x/META_ANALISES/y.pdf")["audio"]
    checa("diretriz: áudio usa prompt PRÓPRIO", "diretriz" in a_dir, f"veio {a_dir}")
    checa("os outros tipos: áudio segue o prompt comum", "diretriz" not in a_out, f"veio {a_out}")
    checa("carimbo distingue os dois roteiros", a_dir != a_out)

    # 4 · o predicado é UM só (não espalhado em cinco `if`)
    checa("existe o predicado único eh_diretriz", hasattr(AN, "eh_diretriz"))
    checa("eh_diretriz reconhece", AN.eh_diretriz("diretriz") and AN.eh_diretriz(" Diretriz "))
    checa("eh_diretriz não confunde", not AN.eh_diretriz("meta") and not AN.eh_diretriz(None))
    return "diretriz sem porta · exceção contida nos outros 3 tipos"


def teste_keywords_em_portugues():
    """As palavras-chave são como o assinante ACHA o artigo. Os 4 tipos, prompt E schema.

    ═══ 05/Ago — DOIS BURACOS DIFERENTES, ACHADOS EM SEQUÊNCIA ═══

    (1) O prompt da DIRETRIZ pedia os termos "EM INGLÊS", com todas as letras. O focused update de
        dislipidemia do ESC subiu com `dyslipidaemia`, `LDL cholesterol`, `bempedoic acid`.
        Medido no Supabase: 18 de 18 diretrizes com termo em inglês, só 4 com português.
        Achado em um prompt, corrigido em três (o do artigo original e o da revisão tinham igual).

    (2) O prompt da META **não dizia NADA** — embora o schema peça o campo. Cada meta saía de um
        jeito: das 11 publicadas, 7 com inglês e 9 com português. O Dr. Eduardo cobrou:
        *"não acredito que depois de analisar meta ontem umas 10 vezes você deu este vacilo"*.
        Ele estava certo: eu reescrevi aquele prompt seção por seção e nunca perguntei
        "e as palavras-chave?".

    Por isso esta trava cobra as DUAS coisas nos QUATRO tipos: a regra no PROMPT e a descrição no
    SCHEMA. Campo sem instrução é campo preenchido a esmo — e a esmo, em inglês.
    """
    import os, sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import analise as A
    aqui = os.path.dirname(os.path.abspath(__file__))

    PROMPTS = {"analise_prompt.md": "SCHEMA_FATOS",
               "analise_meta_prompt.md": "SCHEMA_FATOS_META",
               "analise_diretriz_prompt.md": "SCHEMA_FATOS_DIRETRIZ",
               "analise_revisao_prompt.md": "SCHEMA_FATOS_REVISAO"}

    for arq, esq in PROMPTS.items():
        caminho = os.path.join(aqui, arq)
        if not os.path.exists(caminho):
            checa(f"prompt '{arq}' existe", False); continue
        t = open(caminho, encoding="utf-8").read()
        # 1 · a INSTRUÇÃO não pode pedir inglês (o texto que EXPLICA o erro antigo pode citá-lo)
        checa(f"{arq}: não pede keywords em inglês",
              "termos clínicos específicos EM INGLÊS" not in t,
              "voltou a pedir inglês — o acervo fica invisível para quem paga a assinatura")
        # 2 · e tem de DIZER a regra (campo sem instrução vira preenchimento a esmo)
        checa(f"{arq}: manda as keywords em PORTUGUÊS",
              "PORTUGUÊS BRASILEIRO" in t,
              "o prompt pede o campo e não diz o idioma — foi o buraco da meta")
        # 3 · o SCHEMA também carrega a regra: o modelo lê os dois
        d = str((getattr(A, esq)["properties"].get("keywords") or {}).get("description") or "")
        checa(f"{esq}: keywords tem descrição em português",
              "PORTUGUÊS BRASILEIRO" in d,
              "schema sem description — o modelo preenche como quiser")
    return "4 prompts + 4 schemas com a regra das palavras-chave"


def teste_ficha_sem_contradicao():
    """A LINHA DO BANCO não pode dizer duas coisas diferentes sobre o mesmo fato.

    ═══ 05/Ago — TRÊS DEFEITOS QUE SÓ APARECERAM OLHANDO A TABELA INTEIRA ═══

    O Dr. Eduardo cobrou uma revisão dos 4 schemas coluna por coluna — *"você só se concentra em
    atividades de curto prazo"* — e ele estava certo: os três achados abaixo são invisíveis quando
    se olha peça por peça, e óbvios quando se olha a linha inteira.

    1 · `tipo_documento: diretriz` E `tipo_estudo: artigo_original` NA MESMA LINHA, 18 de 18.
        O `tipo_estudo` vinha do campo `tipo` do CANÔNICO — e o canônico de uma diretriz grava
        `tipo: "artigo_original"`, porque quem o escreve não recebe o tipo da pasta. Duas colunas
        respondendo a mesma pergunta: o mesmo padrão do `muda_conduta` em 3 caminhos (04/Ago) e
        do `desfecho_duro` em 2 campos. Agora `tipo_estudo` é DERIVADO de `tipo_documento`.

    2 · `data_publicacao` sempre em AAAA-01-01 — 29 de 29 linhas. O focused update do ESC é de
        NOVEMBRO e estava gravado como janeiro: erro de até 11 meses, que quebra ordenação por
        data e qualquer agenda de envio. O mês existia no nome do arquivo (posto lá pelo
        classificador, com metadado do PubMed) e estava sendo descartado.

    3 · `gancho_lista` IDÊNTICO a `contexto_tema` em 9 de 18 diretrizes. São campos com função
        diferente — a isca da lista e o "por que importa" do card. Repetir não é buraco de dado,
        é buraco EDITORIAL: o leitor lê a mesma frase duas vezes.

    Função pura: lê o STAGING em disco, não chama LLM nem banco.
    """
    import os, sys, glob
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import ficha_site as F

    raiz = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "outputs", "STAGING")
    pastas = [p for p in sorted(glob.glob(os.path.join(raiz, "*"))) if os.path.isdir(p)]
    if not pastas:
        return "STAGING vazio — nada a conferir (não é falha)"

    COERENTE = {"diretriz": "diretriz_pratica_clinica",
                "meta": "revisao_sistematica_meta_analise",
                "revisao_narrativa": "revisao_narrativa",
                "original": "artigo_original"}
    mau_tipo, mau_data, mau_gancho, n, vazias = [], [], [], 0, []
    for p in pastas:
        # ═══ 06/Ago — PASTA VAZIA NÃO É FICHA INCOERENTE, É LIXO DE INTERRUPÇÃO ═══
        # Quando o Dr. Eduardo deu Ctrl-C na rodada dos 255, ficou uma pasta criada e sem NENHUM
        # arquivo dentro. A `montar()` devolvia uma ficha em branco e a trava acusava "tipo_estudo
        # incoerente" — apontando para o defeito errado. Pasta sem canônico não tem o que conferir:
        # é contada à parte e reportada como lixo, que é o que ela é.
        if not glob.glob(os.path.join(p, "*_CANONICO.md")):
            vazias.append(os.path.basename(p)[:34])
            continue
        try:
            fi = F.montar(p)
        except Exception:
            continue
        n += 1
        base = os.path.basename(p)
        td, te = fi.get("tipo_documento"), fi.get("tipo_estudo")
        if td in COERENTE and te != COERENTE[td]:
            mau_tipo.append(f"{base[:28]}: {td}/{te}")
        # o mês do NOME do arquivo tem de sobreviver até a data_publicacao
        dt = str(fi.get("data_publicacao") or "")
        if len(base) >= 7 and base[4] == "-" and base[:4].isdigit() and base[5:7].isdigit():
            if dt[:7] and dt[:7] != base[:7]:
                mau_data.append(f"{base[:28]}: nome {base[:7]} × data {dt[:7]}")
        if (fi.get("gancho_lista") or "") and fi.get("gancho_lista") == fi.get("contexto_tema"):
            mau_gancho.append(base[:28])

    checa(f"ficha: tipo_estudo coerente com tipo_documento ({n} pacotes)", not mau_tipo,
          "; ".join(mau_tipo[:3]))
    checa(f"ficha: o MÊS do nome sobrevive na data_publicacao", not mau_data,
          "; ".join(mau_data[:3]))
    checa(f"ficha: gancho_lista ≠ contexto_tema", not mau_gancho,
          "iguais em: " + ", ".join(mau_gancho[:3]))
    if vazias:
        print(f"      ⚠️  {len(vazias)} pasta(s) VAZIA(s) no STAGING (lixo de rodada interrompida): "
              + ", ".join(vazias[:3]) + ("…" if len(vazias) > 3 else ""))
    return f"{n} pacotes: tipo coerente · mês preservado · gancho distinto"


def teste_contrato_espelha_a_tabela():
    """O CONTRATO e a TABELA têm de listar as MESMAS colunas — nem a mais, nem a menos.

    ═══ 05/Ago — A COLUNA `descartado` FOI APAGADA (decisão do Dr. Eduardo) ═══

    Ela nasceu para ele marcar "esse eu não quero" sem apagar. Mas NADA no sistema jamais escreveu
    `true`: o `ficha_site` gravava `False` fixo e ninguém lia. Coluna morta. E em 04/Ago ele decidiu
    que artigo reprovado tem a LINHA APAGADA (retratação no publicador) — o que tirou o último
    sentido possível dela: o que é descartado não existe mais.

    A varredura da LEI 9 achou SEIS blocos usando a coluna, e a ORDEM importou: se o `ALTER TABLE`
    viesse antes, o painel de curadoria e o backfill quebrariam (os dois filtravam
    `descartado=eq.false`, e o PostgREST erra quando a coluna não existe), e o publicador também
    (validava o tipo no preflight). Código primeiro, banco depois.

      ficha_site · publicador · contrato · administrador (×2) · painel_curadoria · backfill

    Esta trava impede que a coluna renasça em UM bloco só — que é como um buraco começa.
    Função pura: não fala com o banco, só compara as listas do código.
    """
    import os, sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import contrato as C, publicador as P, ficha_site as F

    MORTAS = ("descartado",)
    for col in MORTAS:
        checa(f"contrato NÃO lista a coluna morta '{col}'",
              col not in getattr(C, "COLUNAS", ()) and col not in str(getattr(C, "COLUNAS", "")),
              "a coluna foi apagada da tabela — listá-la faz o preflight cobrar o que não existe")
        checa(f"publicador NÃO valida o tipo de '{col}'",
              col not in getattr(P, "TIPOS", {}),
              "preflight cobrando coluna inexistente → erro 400 no próximo insert")

    # e o payload não pode mandar coluna que a tabela não tem
    import glob
    pastas = [p for p in sorted(glob.glob(os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "outputs", "STAGING", "*")))
        if os.path.isdir(p)]
    if pastas:
        try:
            pay = P._payload_site(F.montar(pastas[0]))
            for col in MORTAS:
                checa(f"payload NÃO manda '{col}'", col not in pay,
                      "o insert vai falhar: a coluna não existe mais na tabela")
        except Exception:
            pass
    return f"colunas mortas fora do código: {', '.join(MORTAS)}"


def teste_acri_nao_diz_sim_nao_para_todo_mundo():
    """BLOCO 7 (LEI 9) — o ACRI é a peça que o ASSINANTE LÊ, e ela mandava SIM/NÃO para todos.

    A varredura de 06/Ago achou, no `acri_prompt.md`:
        "Depois o título curto · revista · ano · **Nota X/10 · muda conduta SIM/NÃO**."

    Consertar o MOTOR e deixar o PROMPT pedindo SIM/NÃO é o erro que a LEI 9 nomeia: o bloco que
    sobrou continua rodando, e roda em silêncio. Aqui roda impresso, na frente do assinante.
    """
    import os as _os
    txt = open(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)),
                             "acri_prompt.md"), encoding="utf-8").read()
    checa("ACRI não pede SIM/NÃO cego", "muda conduta SIM/NÃO**." not in txt,
          "o prompt ainda manda imprimir SIM/NÃO em diretriz e revisão")
    for termo in ("RECOMENDADA COM RESSALVAS", "revisão narrativa"):
        checa(f"ACRI sabe o caso: {termo}", termo in txt, "o prompt não cobre este tipo")


def teste_arr_por_ano_nao_e_dividida_de_novo():
    """06/Ago — TAXA DE INCIDÊNCIA ≠ RISCO CUMULATIVO. São denominadores diferentes.

    ═══ O DEFEITO ═══
    Existia UM campo, `arr_pct`, e o motor SEMPRE dividia por `seguimento_anos`. Isso está certo
    para incidência ACUMULADA (denominador em pessoas) e ERRADO para densidade de incidência
    (denominador em pessoas-TEMPO), onde o "por ano" já está dentro do número.

        acumulada .... "16,3% vs 21,2% em 18,2 meses"       → 4,9 pts ÷ 1,52 = 3,2 %/ano  ✓
        taxa ......... "141 vs 330 por 100.000 pessoas-ano" → 0,189 %/ano, NÃO dividir

    O número 2,0 é 2,0: nada nele diz qual é. O erro andava nos DOIS sentidos — uma ARR de 2,0%/ano
    em 5 anos virava 0,4%/ano e reprovava um ensaio que muda conduta; e o inverso aprovava lixo.

    ═══ O QUE FOI MEDIDO ANTES DE CONSERTAR ═══
    129 pacotes · `arr_pct` preenchido em 8 · dupla divisão em ZERO. O defeito ainda não mordeu.
    Mas o mecanismo apareceu nos primeiros 20 artigos originais, com as palavras do extrator no
    JAMA Coffee: *"NNT não calculável, pois não foram fornecidos riscos cumulativos"* — ele tinha
    "189 por 100.000 pessoas-ano" na mão e desistiu, porque o campo pedia o que o artigo não dava.
    """
    def _art(**rc):
        base = dict(classificacao="robusto", tipo_desfecho="composto",
                    desfecho_primario="morte CV/IAM/AVC", mcid_reportado=False)
        base.update(rc)
        return dict(pergunta="intervencao", desenho="rct", open_label=False, poder_ok=True,
                    desfecho_duro=True, extrapolavel=True, retrospectivo=False,
                    desenho_apropriado=True, qualidade_entrada=True, follow_up_completo=True,
                    eventos_min_grupo=800, falhas_fatais=[], tipo_documento="original",
                    financiamento_papel="público", relevancia_clinica=base)

    # ── O CASO QUE INVERTIA: 2,0 %/ano num estudo de 5 anos ──
    # anticoagulação em FA: AVC 1,5%/ano vs 3,5%/ano. A diferença É 2,0 %/ano, EXCEDE o limiar.
    r = N.score(_art(arr_ano_pct=2.0))
    checa("ARR/ano de 2,0 excede o limiar (não é dividida)", r["aplic"] >= 9,
          f"nota={r['aplic']} — a taxa foi dividida de novo e virou 0,4%/ano")

    # o mesmo número, gravado como ACUMULADO em 5 anos, TEM de ser dividido → 0,4%/ano → teto 6
    r2 = N.score(_art(arr_pct=2.0, seguimento_anos=5.0))
    checa("a mesma 2,0 ACUMULADA em 5 anos é capada", r2["aplic"] <= 6,
          f"nota={r2['aplic']} — parou de dividir o acumulado, e isso aprova lixo")

    # ── o JAMA Coffee, com o número que o extrator tinha e não usou ──
    c = N.score(_art(arr_ano_pct=0.189, tipo_desfecho="tempo_ate_evento",
                     desfecho_primario="Demência incidente"))
    checa("Coffee: 0,189 %/ano NÃO excede → teto 6", c["aplic"] <= 6, f"nota={c['aplic']}")

    # ── 06/Ago: A CONTA IMPRESSA PARA O REDATOR TEM DE FECHAR ──
    # O campo `teto_mcid` do retorno vinha só do teto POR RÓTULO e ignorava a CONTA conferida.
    # O redator recebia "MCID 10 · rigor 9" e a nota 6 — aritmética que não fecha, com o delator
    # dizendo o contrário na linha seguinte. Ou ele inventa a explicação, ou desiste.
    checa("o campo teto_mcid reflete a conta, não só o rótulo", c["teto_mcid"] <= 6,
          f"campo diz {c['teto_mcid']} e a nota é {c['aplic']} — a conta do veredito não fecha")
    ver = N.veredito_completo(c)
    import re as _re
    m = _re.search(r"MENOR entre:(.+)", ver)
    if m:
        nums = [int(x) for x in _re.findall(r"\b(\d{1,2})\b", m.group(1))]
        checa("algum domínio do veredito produz a nota", nums and min(nums) == c["aplic"],
              f"domínios {nums} · nota {c['aplic']}")

    # ── o texto do delator diz QUAL base foi usada (auditável) ──
    _, _, txt = N._limiar_cardiodaily(_art(arr_ano_pct=2.0))
    checa("o delator declara a base 'taxa/ano'", "taxa/ano" in txt, f"veio {txt!r}")
    _, _, txt2 = N._limiar_cardiodaily(_art(arr_pct=2.0, seguimento_anos=5.0))
    checa("e declara a divisão quando é acumulada", "acumulada" in txt2, f"veio {txt2!r}")

    # ── precedência: se vierem os dois (não deviam), o já-anualizado manda ──
    d = N.score(_art(arr_ano_pct=2.0, arr_pct=2.0, seguimento_anos=5.0))
    checa("os dois preenchidos: o ARR/ano tem precedência", d["aplic"] >= 9, f"nota={d['aplic']}")

    # ── BLOCO 4 da LEI 9: o PROMPT tem de PEDIR o campo, senão o schema fica vazio ──
    # Sabotagem de 06/Ago: tirei `arr_ano_pct` do prompt e a bateria PASSOU. Motor certo + schema
    # certo + prompt calado = campo eternamente null, e a régua vira decoração. Foi exatamente
    # isto que aconteceu com as palavras-chave da meta (05/Ago): o schema pedia, o prompt não
    # dizia nada, e cada artigo saiu de um jeito.
    import os as _os
    _d = _os.path.dirname(_os.path.abspath(__file__))
    for _p in ("analise_prompt.md", "analise_meta_prompt.md"):
        _t = open(_os.path.join(_d, _p), encoding="utf-8").read()
        checa(f"{_p} pede arr_ano_pct", "`arr_ano_pct`" in _t,
              "o schema pede e o prompt não fala — campo nasce null")
        checa(f"{_p} explica pessoas-ano", "pessoas-ano" in _t.lower(),
              "sem o exemplo do denominador, o modelo não sabe qual campo usar")

    # ── e o schema pede os campos novos, nos DOIS lugares (bloco 4 da LEI 9) ──
    import analise as _A
    for nome in ("SCHEMA_FATOS", "SCHEMA_FATOS_META"):
        s = getattr(_A, nome, None)
        if s is None:
            continue
        # ⚠️ chave EXATA, com aspas. `campo in str(schema)` é frouxo: `arr_ano_pct` é substring de
        # `arr_ano_pct_off`, e a sabotagem de 06/Ago passou por isso. Trava que não morde não é trava.
        txt = str(s)
        for campo in ("arr_ano_pct", "arr_ano_ic_inf_pct"):
            checa(f"{nome} pede {campo}", f"'{campo}'" in txt or f'"{campo}"' in txt,
                  "o motor lê um campo que o schema não pede — nasce null para sempre")


def teste_diretriz_recomenda_em_vez_de_mudar_conduta():
    """06/Ago — A DIRETRIZ SEMPRE MUDA ALGO. O QUE VARIA É QUANTO CONFIAR NELA.

    ═══ O CASO, IMPRESSO ═══
    O Dr. Eduardo mandou o PDF que o CardioDaily JÁ PUBLICOU — "Imagem Vascular na
    Cardio-Oncologia", statement ESC 2026 — e o veredito na peça dizia:

            min(…) = 6/10          MUDA CONDUTA: NÃO

    No MESMO documento: `aplicável no Brasil 10/10`, e mensagens-chave que são ordens diretas
    ("faça ECG de 12 derivações e estratificação HFA-ICOS"; "eco basal é recomendado, classe I").
    A peça mandava fazer cinco coisas e dizia que não mudava conduta.

    ═══ POR QUE A PERGUNTA ERA ERRADA ═══
    Palavras dele: *"ninguém escreve uma diretriz que não muda nada — então o que muda é o GRAU
    COM QUE PODEMOS ACREDITAR NELA."* Perguntar se uma diretriz muda conduta é perguntar se chove
    na chuva. O que o médico precisa é do peso: aquele statement tem 68,8% das recomendações em
    nível C e metade das Classe I apoiadas em nível C — é isso que o 6 está dizendo.

    ⚠️ NÃO É PORTA. A LEI 10 continua: a diretriz sobe em QUALQUER nota, inclusive NÃO RECOMENDADA.
    A recomendação avisa; não retém.
    """
    r = N.score(_diretriz())
    checa("diretriz responde com RECOMENDAÇÃO, não com SIM/NÃO",
          r["muda_conduta"] not in ("SIM", "NÃO"), f"veio {r['muda_conduta']}")

    # ── a escala inteira, nota por nota (é a régua dele; se mudar, tem de ser por decisão dele) ──
    for nota, esperado in ((10, "RECOMENDADA"), (8, "RECOMENDADA"),
                           (7, "RECOMENDADA COM RESSALVAS"), (6, "RECOMENDADA COM RESSALVAS"),
                           (5, "REFERÊNCIA, NÃO AUTORIDADE"), (4, "REFERÊNCIA, NÃO AUTORIDADE"),
                           (3, "NÃO RECOMENDADA"), (0, "NÃO RECOMENDADA")):
        checa(f"diretriz nota {nota} → {esperado}",
              N.recomendacao_da_diretriz(nota) == esperado,
              f"veio {N.recomendacao_da_diretriz(nota)}")

    # ── o caso real dele: o statement de cardio-oncologia, nota 6 ──
    checa("statement cardio-oncologia (6) = RECOMENDADA COM RESSALVAS",
          N.recomendacao_da_diretriz(6) == "RECOMENDADA COM RESSALVAS")
    checa("e a nota 6 vem com o PORQUÊ, não só o rótulo",
          "opinião" in N.motivo_da_recomendacao(6))

    # ── A LEI 10: recomendação NÃO É PORTA ──
    from analisador import decidir_entregaveis
    pecas, sobe = decidir_entregaveis(3, tipo="diretriz")
    checa("diretriz NÃO RECOMENDADA ainda sobe (LEI 10)", sobe,
          "a recomendação virou porta — a exceção da diretriz foi revogada")


def teste_revisao_nao_diz_muda_conduta():
    """06/Ago — A REVISÃO ORGANIZA CONHECIMENTO; ELA NÃO MUDA CONDUTA.

    ═══ O QUE FOI MEDIDO NO LOTE REAL ═══
    Rodando as 119 revisões, a distribuição das notas saiu assim:

        revisao_narrativa .... 19 em nota 8 · 8 em nota 9   (27 de 48 acima de 7)
        original ............. 4 em nota 8 · ZERO em 9      (PLATO, TRITON e DAPA-HF em 8)

    Pela bicondicional (04/Ago), as 8 revisões em 9 foram gravadas com `muda_conduta: SIM` — e os
    três RCTs que mudaram a cardiologia moderna, com `NÃO`. O CardioDaily estava afirmando que uma
    revisão de fisiopatologia muda a conduta e que o ticagrelor não muda.

    ═══ O QUE ERROU, E O QUE NÃO ERROU ═══
    A NOTA não errou: ela mede o que o Dr. Eduardo mandou medir em 02/Ago — qualidade da base
    (viés de seleção) × utilidade prática (conduta acionável, custo Brasil). Uma revisão pode e
    deve chegar a 10 quando organiza excepcionalmente bem. Ele reafirmou isso hoje:
    *"a pontuação reflete a qualidade do material utilizado e a quantidade de informações
    aplicáveis que ela de fato entrega"*.

    O que errou foi o CAMPO. `muda_conduta` responde a uma pergunta de INTERVENÇÃO — houve braço,
    houve desfecho, a prática deve mudar? Uma revisão não tem nada disso. Nota 10 nela significa
    "organiza excepcionalmente bem", não "prescreva".

    Fui EU quem aplicou a bicondicional aqui em 04/Ago sem varrer o que ela significaria numa
    revisão — a LEI 9, que ele escreveu depois de eu cometer exatamente este erro.

    ⚠️ A BICONDICIONAL NÃO FOI ENFRAQUECIDA. Ela continua inteira onde nasceu: intervenção e
    diretriz. Esta trava reprova nos DOIS sentidos.
    """
    r = N.score(_revisao())
    checa("revisão: nota pode chegar a 10 (decisão de 02/Ago, mantida)", r["aplic"] == 10,
          f"veio {r['aplic']} — o teto dele foi revogado sem ele pedir")
    checa("revisão: muda_conduta é N/A", r["muda_conduta"].startswith("N/A"),
          f"veio {r['muda_conduta']}")

    # e uma revisão FRACA também não diz "NÃO muda conduta" — ela simplesmente não responde
    fraca = N.score(_revisao(conduta_acionavel=False, traz_valores_corte_ou_doses=False))
    checa("revisão fraca também não responde a pergunta", fraca["muda_conduta"].startswith("N/A"),
          f"veio {fraca['muda_conduta']} — 'NÃO' insinua que a pergunta cabia")

    # ── O OUTRO SENTIDO: a bicondicional segue INTEIRA na intervenção ──
    rct = dict(pergunta="intervencao", desenho="rct", open_label=False, poder_ok=True,
               desfecho_duro=True, extrapolavel=True, retrospectivo=False, desenho_apropriado=True,
               qualidade_entrada=True, follow_up_completo=True, eventos_min_grupo=800,
               falhas_fatais=[], tipo_documento="original", financiamento_papel="público",
               relevancia_clinica=dict(classificacao="robusto", tipo_desfecho="composto",
                                       desfecho_primario="morte CV/IAM/AVC", arr_pct=1.9,
                                       seguimento_anos=1.0, mcid_reportado=False))
    s = N.score(rct)
    checa("RCT nota ≥9 continua dizendo SIM", s["aplic"] >= 9 and s["muda_conduta"] == "SIM",
          f"nota={s['aplic']} conduta={s['muda_conduta']} — a bicondicional foi enfraquecida")


def teste_independencia_nao_cruza_o_nove():
    """06/Ago — O DESCONTO DE INDÚSTRIA NÃO CONVERTE "muda conduta" EM "não muda" (opção A).

    ═══ O QUE ACONTECEU, MEDIDO NA PRIMEIRA RODADA REAL ═══
    O Dr. Eduardo rodou os artigos originais e os três primeiros RCTs de peso saíram assim:

        TRITON-TIMI 38 (Prasugrel, 2007) .... nota 8 · muda_conduta NÃO
        PLATO (Ticagrelor, 2009) ............ nota 8 · muda_conduta NÃO
        DAPA-HF (Dapagliflozina, 2019) ...... nota 8 · muda_conduta NÃO

    Os três com `teto_desenho: 10`, `nota_trabalho_estatistico: 9`, ARR/ano acima do limiar da
    casa, e o MESMO delator: `independência editorial −1.0 (indústria envolvida)`.

    O motor tinha reconhecido tudo — RCT duplo-cego, poder ok, desfecho duro. O desconto derrubou
    9 → 8, e a BICONDICIONAL leu o 8 e escreveu que o ticagrelor não muda conduta.

    ═══ POR QUE É ESTRUTURAL ═══
    Quase todo ensaio de fase 3 em cardiologia é patrocinado. Desconto integral + bicondicional,
    juntos, tornavam quase impossível um artigo original chegar a 9 — e o produto perdia a frase
    mais valiosa que vende: "isto muda sua prática".

    ═══ A REGRA (decisão dele) ═══
    Nota ≥9 ANTES do desconto → o desconto desce no máximo até 9, e o delator DIZ quanto teria
    sido descontado. Financiamento vira ressalva declarada, não rebaixamento de categoria.
    Abaixo de 9, o desconto continua valendo INTEIRO — a regra de 05/Ago não foi revogada.
    """
    base = dict(pergunta="intervencao", desenho="rct", open_label=False, poder_ok=True,
                desfecho_duro=True, extrapolavel=True, retrospectivo=False,
                desenho_apropriado=True, qualidade_entrada=True, follow_up_completo=True,
                eventos_min_grupo=800, falhas_fatais=[], tipo_documento="original",
                relevancia_clinica=dict(classificacao="robusto", tipo_desfecho="composto",
                                        desfecho_primario="morte CV/IAM/AVC",
                                        arr_pct=1.9, seguimento_anos=1.0, mcid_reportado=False))

    limpo = N.score({**base, "financiamento_papel": "público"})
    checa("PLATO acadêmico chega a 9", limpo["aplic"] >= 9, f"veio {limpo['aplic']}")

    pago = N.score({**base, "financiamento_papel": "indústria envolvida"})
    checa("PLATO patrocinado NÃO cai abaixo de 9", pago["aplic"] >= N.PISO_INDEPENDENCIA,
          f"veio {pago['aplic']} — o desconto cruzou a fronteira e a bicondicional vai dizer "
          f"que o ticagrelor não muda conduta")
    checa("PLATO patrocinado mantém muda_conduta SIM", pago["muda_conduta"] == "SIM",
          f"veio {pago['muda_conduta']}")
    checa("e o delator DECLARA o desconto que não foi aplicado",
          any("ressalva declarada" in f for f in pago.get("flags", [])),
          "o leitor tem de ver que houve indústria, mesmo sem a nota cair")

    # ── ABAIXO de 9 o desconto continua inteiro: a regra de 05/Ago não virou letra morta ──
    b8 = {**base, "open_label": True}          # open-label → teto 8
    s_lim = N.score({**b8, "financiamento_papel": "público"})
    s_pag = N.score({**b8, "financiamento_papel": "indústria envolvida"})
    checa("abaixo de 9 o desconto de indústria continua descontando",
          s_pag["aplic"] < s_lim["aplic"],
          f"público={s_lim['aplic']} vs indústria={s_pag['aplic']} — o piso virou anistia geral")


def teste_independencia_editorial():
    """QUEM PAGOU pesa na nota — e pesa DIFERENTE em cada tipo, por decisão do dono (05/Ago).

    ═══ O QUE A VARREDURA DOS 4 SCHEMAS ACHOU ═══
    Cada motor tratava dinheiro de um jeito, e ninguém tinha decidido isso — foi acumulado:
        DIRETRIZ .. 6 campos, 20% da nota    REVISÃO ... 2 campos, 15%
        ORIGINAL .. 1 campo, IGNORADO        META ...... NENHUM campo

    Um RCT patrocinado, com o financiador desenhando o estudo e escrevendo o manuscrito, tirava a
    MESMA nota de um ensaio acadêmico independente. É onde o ceticismo do Dr. Eduardo é mais
    afiado ("especialmente estudos patrocinados pela indústria" — CLAUDE.md) e era o único ponto
    cego do sistema.

    RÉGUA DELE: diretriz até 20% · os outros três até 10%.
    A REVISÃO ficou nos 15% que ele mesmo aprovou em 02/Ago — baixar seria revogar decisão dele
    sem que ele pedisse (LEI 3). Está registrado aqui para não parecer esquecimento.
    """
    # ── o desconto por papel do financiador (ORIGINAL) ──
    for texto, esperado in (("indústria envolvida", 1.0),
                            ("indústria fora da análise/escrita", 0.3),
                            ("público", 0.0), ("outro", 0.0)):
        d, _ = N.desconto_independencia({"financiamento_papel": texto})
        checa(f"independência ORIGINAL '{texto}' → −{esperado}", abs(d - esperado) < 0.01,
              f"veio −{d}")

    # ── e na META, que não perguntava NADA até hoje ──
    for qm, esperado, nome in (
        ({"conflitos_declarados": False}, 1.0, "sem declaração de conflito"),
        ({"conflitos_declarados": True, "financiamento_industria": True,
          "autores_industria_fora_da_analise": None}, 1.0, "indústria sem separação declarada"),
        ({"conflitos_declarados": True, "financiamento_industria": True,
          "autores_industria_fora_da_analise": True}, 0.3, "indústria com análise independente"),
        ({"conflitos_declarados": True, "financiamento_industria": False}, 0.0, "sem indústria"),
    ):
        d, _ = N.desconto_independencia({"qualidade_meta": qm})
        checa(f"independência META: {nome} → −{esperado}", abs(d - esperado) < 0.01, f"veio −{d}")

    # ── o teto é 10% da escala: NUNCA pode passar de 1,0 ponto ──
    piores = [{"financiamento_papel": "indústria envolvida"},
              {"qualidade_meta": {"conflitos_declarados": False}}]
    for p in piores:
        d, _ = N.desconto_independencia(p)
        checa("independência: o desconto nunca passa de 1,0 (=10%)", d <= 1.0, f"veio −{d}")

    # ── os 4 schemas PERGUNTAM sobre dinheiro (a meta era o buraco) ──
    import os, sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import analise as A
    TERMOS = ("financiamento", "conflito")
    for nome in ("SCHEMA_FATOS", "SCHEMA_FATOS_META", "SCHEMA_FATOS_DIRETRIZ", "SCHEMA_FATOS_REVISAO"):
        todos = []
        def varre(d):
            for k, v in (d.get("properties") or {}).items():
                todos.append(k)
                if isinstance(v, dict) and v.get("type") == "object":
                    varre(v)
        varre(getattr(A, nome))
        tem = any(t in c for c in todos for t in TERMOS)
        checa(f"{nome} pergunta sobre financiamento/conflito", tem,
              "schema cego a patrocínio — foi o buraco da meta até 05/Ago")
    return "4 schemas perguntam · desconto ≤ 1,0 ponto em ORIGINAL e META"


def teste_mcid_confere_a_conta():
    """O MCID: a CONTA manda no RÓTULO — e o rótulo nunca é PROMOVIDO pela conta (05/Ago).

    O extrator produzia NOVE campos de relevância clínica (mcid_valor, mcid_reportado,
    mcid_fonte_metodo, efeito_observado, efeito_excede_limiar, ic_sustenta_relevancia,
    para_desfecho_duro, tipo_desfecho, desfecho_primario) — e o motor lia UM: `classificacao`.

    O modelo fazia a conta campo por campo e o código perguntava só "e aí, como você classifica?".
    A conta era feita e jogada fora; ficava o rótulo — justamente a parte em que o LLM é menos
    confiável. Palavras do Dr. Eduardo: *"devemos usar este esquema que é muito bom — e deve pesar
    muito"*.

    A REGRA-MÃE, e é assimétrica de propósito: os fatos podem REBAIXAR o rótulo, nunca PROMOVÊ-LO.
    Cautela não se desfaz por número.
    """
    def rc(**kw): return {"relevancia_clinica": kw}

    t, _ = N.mcid_conferido(rc(classificacao="robusto", efeito_excede_limiar=True,
                               ic_sustenta_relevancia=True, mcid_reportado=True,
                               mcid_valor="ARR 3%", tipo_desfecho="tempo_ate_evento"))
    checa("MCID: conta fecha → sem teto", t == 10, f"veio {t}")

    t, m = N.mcid_conferido(rc(classificacao="robusto", efeito_excede_limiar=False,
                               mcid_reportado=True, mcid_valor="ARR 3%"))
    checa("MCID: NÃO excede o limiar → teto 6 (o rótulo não salva)", t <= 6, f"veio {t}")
    checa("MCID: e o motivo é dito", any("não excede" in x.lower() or "NÃO excede" in x for x in m))

    t, _ = N.mcid_conferido(rc(classificacao="robusto", efeito_excede_limiar=True,
                               ic_sustenta_relevancia=False, mcid_reportado=True, mcid_valor="ARR 3%"))
    checa("MCID: IC não sustenta → teto 7", t == 7, f"veio {t}")

    t, _ = N.mcid_conferido(rc(classificacao="robusto", mcid_reportado=False, mcid_valor=""))
    checa("MCID: 'robusto' sem limiar declarado → teto 8", t <= 8, f"veio {t}")

    t, _ = N.mcid_conferido(rc(classificacao="robusto", efeito_excede_limiar=True,
                               ic_sustenta_relevancia=True, mcid_reportado=True,
                               mcid_valor="Lp(a) -20%", tipo_desfecho="surrogate"))
    checa("MCID: 'robusto' sobre desfecho SUBSTITUTO → teto 8", t <= 8, f"veio {t}")

    # ── A REGRA-MÃE: a conta NÃO promove ──
    fatos = _bom(pergunta="intervencao", desenho="rct", efeito_grande=True,
                 relevancia_clinica={"classificacao": "incerto", "efeito_excede_limiar": True,
                                     "ic_sustenta_relevancia": True, "mcid_reportado": True,
                                     "mcid_valor": "ARR 5%", "tipo_desfecho": "tempo_ate_evento"})
    r = N.score(fatos)
    checa("MCID: conta boa NÃO promove rótulo 'incerto' (teto 7 fica)", r["aplic"] <= 7,
          f"veio {r['aplic']} — a cautela do extrator foi desfeita por número")

    # ── e o silêncio não pune: fatos ausentes não inventam teto ──
    t, _ = N.mcid_conferido(rc(classificacao="robusto"))
    checa("MCID: campos ausentes não capam sozinhos (null ≠ false)", t >= 8, f"veio {t}")
    return "5 conferências · a conta rebaixa, nunca promove"


def teste_revisao_valoriza_tabela():
    """A TABELA COMPARATIVA vale ponto na revisão narrativa (05/Ago/2026).

    ═══ O CAMPO QUE ERA EXTRAÍDO E IGNORADO ═══

    `tem_tabela_comparativa` estava no `SCHEMA_FATOS_REVISAO` desde que a trilha nasceu e NENHUM
    bloco do sistema o lia. Achado na varredura dos 4 schemas — a que o Dr. Eduardo mandou fazer
    depois de dizer, com razão, que eu só olhava o curto prazo.

    A ironia: é a TAREFA #25 da lista dele, pendente desde 30/Jul — "Perícia com TABELAS". Ele
    sabe que tabela é o que separa revisão útil de prosa; o extrator já perguntava; o motor não
    escutava. Uma revisão que compara as opções LADO A LADO entrega conduta pronta para o plantão;
    uma que descreve em prosa obriga o leitor a montar a tabela na cabeça.

    REGRA: VALORIZA, não capa. +1 em `conduta_acionavel` (30% da utilidade), igual ao
    `traz_valores_corte_ou_doses`. Mesma lógica do NNT na meta: crédito a quem organizou,
    sem reprovar quem não organizou.
    """
    def rev(**qr):
        base = dict(n_condutas_acionaveis=6, traz_valores_corte_ou_doses=True)
        return {"qualidade_revisao": {**base, **qr}}

    com = N.dominios_revisao_util(rev(tem_tabela_comparativa=True))["conduta_acionavel"]
    sem = N.dominios_revisao_util(rev(tem_tabela_comparativa=False))["conduta_acionavel"]
    mudo = N.dominios_revisao_util(rev(tem_tabela_comparativa=None))["conduta_acionavel"]

    checa("revisão: tabela comparativa VALORIZA", com > sem, f"com={com} sem={sem}")
    checa("revisão: quem NÃO tem tabela não é punido", sem == mudo,
          f"sem={sem} não-informado={mudo} — `false` não pode valer menos que o silêncio")
    checa("revisão: o bônus não estoura o teto 10", com <= 10, f"veio {com}")

    # o campo tem de continuar existindo no schema (senão o bônus vira letra morta)
    import os, sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import analise as A
    q = A.SCHEMA_FATOS_REVISAO["properties"]["qualidade_revisao"]["properties"]
    checa("revisão: 'tem_tabela_comparativa' está no schema", "tem_tabela_comparativa" in q)
    return "tabela comparativa: +1 em conduta_acionavel, sem punir quem não tem"


def teste_mcid_so_onde_faz_sentido():
    """O bloco de RELEVÂNCIA CLÍNICA existe em ORIGINAL e META — e NÃO em diretriz/revisão.

    ═══ DECISÃO DO DR. EDUARDO, 05/Ago — "OPÇÃO A" ═══

    Ele perguntou se os 9 campos de MCID seriam extraídos nos QUATRO schemas. A medição mostrou:
        ORIGINAL .. 12 campos, completo        DIRETRIZ .. não tem o bloco
        META ...... 9 campos (faltavam 3)      REVISÃO ... não tem o bloco

    A META ganhou os 3 que faltavam (`mcid_fonte_metodo`, `para_desfecho_duro`,
    `ic_sustenta_relevancia`): uma meta TEM efeito agregado com magnitude e IC, a pergunta se
    aplica a ela inteira.

    DIRETRIZ e REVISÃO ficaram DE FORA, e isto é decisão, não esquecimento. Elas não têm UM
    efeito: uma diretriz tem dezenas de recomendações, cada uma com seu desfecho e sua magnitude.
    Obrigar o modelo a responder "qual o efeito_observado?" faria com que ele escolhesse UMA
    recomendação arbitrária para representar o documento — e o motor caparia a nota da diretriz
    inteira com base nesse recorte. É a mesma classe de erro que derrubou a IPD de betabloqueador
    do NEJM para 4/10: **o instrumento não serve para o objeto**.

    E as duas já têm a pergunta equivalente, na granularidade certa:
        REVISÃO  → `traz_magnitude_efeito` ("trouxe o número ou só o adjetivo?")
        DIRETRIZ → `riscos_beneficios_considerados` + os tetos de % nível C e Classe I em nível C

    Esta trava existe para que ninguém "complete" os 4 schemas achando que é simetria.
    """
    import os, sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import analise as A

    DOZE = ["desfecho_primario", "tipo_desfecho", "efeito_observado", "mcid_reportado",
            "mcid_valor", "mcid_fonte_metodo", "para_desfecho_duro", "efeito_excede_limiar",
            "ic_sustenta_relevancia", "ic_exclui_beneficio_relevante", "classificacao",
            "frase_chave"]

    # ── TEM: original e meta, com os 12 ──
    for nome in ("SCHEMA_FATOS", "SCHEMA_FATOS_META"):
        rc = (getattr(A, nome)["properties"].get("relevancia_clinica") or {}).get("properties") or {}
        checa(f"{nome}: tem o bloco relevancia_clinica", bool(rc))
        falta = [c for c in DOZE if c not in rc]
        checa(f"{nome}: os 12 campos do MCID", not falta, f"faltam {falta}")
        prompt = "analise_prompt.md" if nome == "SCHEMA_FATOS" else "analise_meta_prompt.md"
        t = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), prompt),
                 encoding="utf-8").read()
        mudos = [c for c in DOZE if c not in t]
        checa(f"{prompt}: explica os 12 campos", not mudos, f"não cita {mudos}")

    # ── NÃO TEM, DE PROPÓSITO: diretriz e revisão ──
    for nome, alternativa in (("SCHEMA_FATOS_DIRETRIZ", "riscos_beneficios_considerados"),
                              ("SCHEMA_FATOS_REVISAO", "traz_magnitude_efeito")):
        s = getattr(A, nome)
        checa(f"{nome}: NÃO tem relevancia_clinica (opção A, 05/Ago)",
              "relevancia_clinica" not in s["properties"],
              "o bloco foi acrescentado: um documento multi-recomendação não tem UM efeito, e o "
              "motor caparia a nota inteira por um recorte arbitrário")
        # e a pergunta equivalente TEM de existir — senão a dimensão some de vez
        todos = []
        def varre(d):
            for k, v in (d.get("properties") or {}).items():
                todos.append(k)
                if isinstance(v, dict) and v.get("type") == "object":
                    varre(v)
        varre(s)
        checa(f"{nome}: mantém o equivalente '{alternativa}'", alternativa in todos,
              "sem MCID e sem o equivalente, a magnitude do efeito sumiu do tipo")
    return "MCID em ORIGINAL e META (12 campos) · diretriz e revisão com o equivalente"


def teste_mcid_cardiodaily():
    """QUANDO O ARTIGO CALA, O CARDIODAILY APLICA O LIMIAR DELE (opção B, 05/Ago/2026).

    ═══ O QUE A MEDIÇÃO MOSTROU, ANTES DE GASTAR UM CENTAVO ═══
    Nas 24 meta-análises do lote:
        mcid_reportado = false ........... 21 de 24
        efeito_excede_limiar = null ...... 22 de 24
        ic_sustenta_relevancia = null .... 24 de 24   ← NUNCA respondido

    Os tetos 6 e 7 da régua nova eram DECORATIVOS: `null` não capa (de propósito) e o extrator
    respondia `null` corretamente, porque **21 de 24 metas não dizem o que consideram
    clinicamente relevante**. Não era falha do extrator: é a fotografia da literatura.

    Decisão dele: quem decide o que importa para o paciente é o cardiologista, não o autor.
    Os limiares vivem em `mcid_cardiodaily.py` — números, não código de motor.

    DUAS REGRAS QUE ESTA TRAVA GUARDA:
      · a régua da casa entra no SILÊNCIO do artigo, NUNCA por cima do que ele mediu;
      · se a casa mediu, a nota não é punida por "sem limiar declarado" — seria cobrar duas
        vezes a mesma ausência.
    """
    import os, sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import mcid_cardiodaily as MC

    # ── a tabela existe e tem números de verdade ──
    checa("MCID casa: ARR/ano relevante é 1,0%", MC.ARR_ANO_RELEVANTE == 1.0,
          f"veio {MC.ARR_ANO_RELEVANTE} — é a régua dele, não muda sozinha")
    checa("MCID casa: NNT impactante = 25 (valoriza, não é régua)", MC.NNT_IMPACTANTE == 25)
    for chave in ("ldl", "pas", "feve", "nt-probnp", "kccq", "tc6m", "vo2", "lp(a)"):
        v = MC.LIMIAR_SUBSTITUTO.get(chave)
        checa(f"MCID casa: limiar de '{chave}' existe e é > 0", v and v[0] > 0, f"veio {v}")

    # ── reconhece o desfecho pelo NOME, escrito como o extrator escreve ──
    for nome, esperado in (("LDL-colesterol", 30.0), ("NT-proBNP aos 12 meses", 30.0),
                           ("KCCQ-OSS", 5.0), ("teste de caminhada de 6 minutos", 30.0),
                           ("pressão arterial sistólica", 5.0)):
        lim = MC.limiar_do_desfecho(nome)
        checa(f"MCID casa: reconhece '{nome[:26]}'", lim and lim[0] == esperado,
              f"veio {lim}")
    checa("MCID casa: NÃO inventa limiar para desfecho desconhecido",
          MC.limiar_do_desfecho("escore de fragilidade de Rockwood") is None,
          "limiar inventado é pior que limiar ausente")

    # ── contínuo que casa com a tabela É substituto (o furo do LDL) ──
    checa("MCID casa: LDL declarado como 'continuo' É substituto",
          MC.eh_substituto("continuo", "LDL-colesterol"),
          "olhar só o tipo_desfecho deixava LDL chegar a teto 10")
    checa("MCID casa: mortalidade NÃO é substituto",
          not MC.eh_substituto("tempo_ate_evento", "mortalidade total"))

    # ── o motor aplica: desfecho duro ──
    def duro(arr, ic, anos):
        return {"desfecho_duro": True, "relevancia_clinica": {
            "classificacao": "robusto", "desfecho_primario": "mortalidade total",
            "tipo_desfecho": "tempo_ate_evento", "mcid_reportado": False,
            "arr_pct": arr, "arr_ic_inf_pct": ic, "seguimento_anos": anos}}
    t, _ = N.mcid_conferido(duro(3.0, 2.2, 1.0))
    checa("MCID casa: ARR 3,0%/ano com IC 2,2% → sem teto", t == 10, f"veio {t}")
    t, _ = N.mcid_conferido(duro(0.8, 0.2, 3.0))
    checa("MCID casa: ARR 0,27%/ano → teto 6", t <= 6, f"veio {t}")
    t, _ = N.mcid_conferido(duro(2.4, 1.8, 2.0))
    checa("MCID casa: ponto passa, IC não sustenta → teto 7", t == 7, f"veio {t}")

    # ── e substituto: mede, mas o teto 8 continua ──
    sub = {"relevancia_clinica": {"classificacao": "robusto", "desfecho_primario": "LDL-colesterol",
                                  "tipo_desfecho": "continuo", "mcid_reportado": False,
                                  "delta_substituto": 42.0}}
    t, mot = N.mcid_conferido(sub)
    checa("MCID casa: substituto medido continua com teto 8", t == 8, f"veio {t}")
    checa("MCID casa: e o motivo cita o limiar da casa",
          any("limiar CardioDaily" in m for m in mot), mot)

    # ── A REGRA-MÃE 1: não entra por cima do que o ARTIGO mediu ──
    do_artigo = {"desfecho_duro": True, "relevancia_clinica": {
        "classificacao": "robusto", "desfecho_primario": "mortalidade total",
        "tipo_desfecho": "tempo_ate_evento", "mcid_reportado": True, "mcid_valor": "ARR 5%",
        "efeito_excede_limiar": False,        # o ARTIGO julgou: não excede
        "arr_pct": 9.0, "arr_ic_inf_pct": 8.0, "seguimento_anos": 1.0}}  # e a casa acharia que sim
    t, _ = N.mcid_conferido(do_artigo)
    checa("MCID casa: o limiar DO ARTIGO prevalece sobre o da casa", t <= 6,
          f"veio {t} — a régua da casa entra no silêncio, não por cima do autor")

    # ── A REGRA-MÃE 2: sem número, a casa não mede (e o silêncio não vira teto) ──
    t, mot = N.mcid_conferido({"desfecho_duro": True, "relevancia_clinica": {
        "classificacao": "robusto", "desfecho_primario": "mortalidade", "mcid_reportado": False}})
    checa("MCID casa: sem número, a casa NÃO inventa medida",
          not any("limiar CardioDaily" in m for m in mot), mot)
    return "limiares da casa: ARR ≥1%/ano + 20 substitutos · entram só no silêncio do artigo"

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
              teste_os_quatro_motores_nao_se_misturam, teste_veredito_aberto, teste_mapa_pubmed,
              teste_a_pasta_manda, teste_reuso_de_staging, teste_pdf_sem_pasta_nao_entra,
              teste_schema_do_google, teste_nulo_informativo, teste_extrator_da_meta,
              teste_ipd_nao_e_punida,
              teste_gabarito_dos_artigos, teste_contrato_de_saida,
              teste_todo_schema_tem_a_capa,
              teste_escada_da_meta, teste_bicondicional_nota_e_conduta,
              teste_escala_de_aplicabilidade_da_meta, teste_carimbo_ve_o_motor,
              teste_diretriz_nao_tem_porta, teste_keywords_em_portugues,
              teste_ficha_sem_contradicao, teste_contrato_espelha_a_tabela,
              teste_independencia_editorial, teste_mcid_confere_a_conta,
              teste_revisao_valoriza_tabela, teste_mcid_so_onde_faz_sentido,
              teste_mcid_cardiodaily]

    # ═══ 06/Ago — A LISTA FIXA DEIXAVA TRAVA ESCRITA E NUNCA CHAMADA ═══
    # Escrevi `teste_independencia_nao_cruza_o_nove`, rodei a bateria, saiu APROVADO — e a trava
    # não tinha rodado UMA vez: não estava nesta lista. É o mesmo defeito do `teste_schema_do_google`
    # (lista chumbada que omitia o SCHEMA_FATOS_META), e é o pior tipo de defeito de prova: dá
    # APROVADO por ausência. Agora o runner VARRE o módulo e recolhe toda função `teste_*` — a lista
    # acima fica só para fixar a ORDEM de leitura do relatório.
    _vistos = {f.__name__ for f in testes}
    _mod = sys.modules[__name__]
    for _nome in sorted(vars(_mod)):
        if _nome.startswith("teste_") and _nome not in _vistos and callable(getattr(_mod, _nome)):
            testes.append(getattr(_mod, _nome))

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
