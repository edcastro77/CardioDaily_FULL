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

    # ── o teto sumiu: uma meta impecável agora ALCANÇA o topo ──
    perfeita = meta(protocolo_registrado=True, extracao_em_duplicata=True,
                    excluidos_listados_com_motivo=True, vies_mudou_interpretacao=True,
                    heterogeneidade_investigada=True, tau2_reportado=True,
                    intervalo_predicao_reportado=True, funnel_plot_feito=True,
                    grade_usado=True, limitacoes_reconhecidas=True)
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
    QM = dict(k_estudos=5, n_total=17801, n_bases=1, protocolo_registrado=True,
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
              teste_todo_schema_tem_a_capa]
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
