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
    #
    # ═══ 22/Ago — ONDE HAVIA UM CASO, AGORA HÁ DOIS ═══
    # `qualidade_entrada` era booleano OBRIGATÓRIO, e o prompt só oferecia "padronizada" ou
    # "raspada de prontuário". Artigo observacional quase nunca descreve codebook — não cabe no
    # limite de palavras — então o silêncio virava `false`, e `false` capava o rigor em 5.
    # Medido: 181 observacionais do acervo com `false`, e `garbage-in` era o motivo nº 1 dos 255
    # retidos (55 artigos). Esta trava foi escrita quando os dois casos eram um só.
    r = N.score(_bom(pergunta="etiologia", desenho="coorte",
                     qualidade_entrada="nao_padronizada"))
    checa("o artigo DECLARA coleta ruim → garbage-in ainda derruba a coorte",
          r["trabalho"] <= 5, f"veio {r['trabalho']}")
    r = N.score(_bom(pergunta="etiologia", desenho="coorte",
                     qualidade_entrada="nao_informado"))
    checa("o artigo NÃO DIZ → não desconta (silêncio não é prova de coleta ruim)",
          r["trabalho"] > 5, f"veio {r['trabalho']}")
    checa("mas o delator AVISA que não foi verificado",
          any("NÃO foi descrita" in str(d) for d in (r.get("flags") or [])),
          f"flags: {r.get('flags')}")
    # o booleano ANTIGO `False` conta como "não informado": foi produzido por um prompt que não
    # oferecia "não sei". Tratá-lo como declaração seria dar valor de prova a uma resposta forçada.
    r = N.score(_bom(pergunta="etiologia", desenho="coorte", qualidade_entrada=False))
    checa("o `False` velho é lido como 'não informado'", r["trabalho"] > 5,
          f"veio {r['trabalho']} — 942 pacotes no disco têm o formato antigo")


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
    # ⚠️ 18/Ago — `nao_avaliavel` SAIU DESTA LISTA, e a linha que ele ocupava era o defeito.
    #
    # Esta trava afirmava "MCID 'nao_avaliavel' NÃO capa" — ou seja, ela CHUMBAVA o buraco:
    # "não dá para avaliar a relevância" valendo relevância máxima. Era a classificação mais
    # comum do acervo (468 de 943) e não tinha teto nenhum.
    #
    # É a TERCEIRA trava minha nesta semana que guardava o erro em vez do acerto:
    #     11/Ago  `Framingham: aplicabilidade cai para 6` — chumbava a régua que ele recusou
    #     17/Ago  `_TETO_NAO_INTERVENCAO NÃO voltou` — idem
    #     18/Ago  esta
    # Trava com a régua errada não deixa só o defeito passar: **ela impede o conserto**,
    # porque reprova quem tenta arrumar. Foi ela que reprovou o conserto de hoje.
    #
    # `nao_se_aplica` entra no lugar: etiologia/prognóstico/diagnóstico não admitem MCID, e
    # quem limita esses estudos é o DESENHO. Pôr teto de relevância seria punir duas vezes.
    for classe in ("robusto", "provavel", "nao_se_aplica"):
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
    # ═══ 06/Ago — A PORTA VIVE EM DOIS BLOCOS, E EU SÓ TINHA OLHADO UM ═══
    # Em 05/Ago implementei a exceção no `decidir_entregaveis` e escrevi esta trava mirando ali.
    # O CONTRATO (`contrato.py`) decide sozinho, e continuava recusando `nota < 6` sem saber da
    # exceção. A trava ficou VERDE e a porta continuou fechada — em silêncio, que é o pior modo.
    # MEDIDO na rodada real de 06/Ago: 13 das 31 diretrizes RECUSADAS — ESC, AHA, ESPEN, NICE,
    # AACE, KDIGO. Os documentos pelos quais o cardiologista é cobrado.
    import contrato as _C
    def _ficha(nota, tipo):
        return {"tipo_documento": tipo, "nota_aplicabilidade": nota,
                "nota_trabalho_estatistico": nota}
    for nota in (1, 3, 4, 5):
        viol = [x for x in _C.validar(_ficha(nota, "diretriz")) if "FICA retido" in x]
        checa(f"CONTRATO: diretriz nota {nota} não é barrada pela porta", not viol,
              f"{viol} — a exceção da LEI 10 não chegou ao contrato")
    # e a exceção NÃO vaza: os outros três continuam retidos abaixo de 6
    for tipo in ("original", "meta", "revisao_narrativa"):
        viol = [x for x in _C.validar(_ficha(4, tipo)) if "FICA retido" in x]
        checa(f"CONTRATO: {tipo} nota 4 continua barrado", viol,
              "a exceção da diretriz vazou — a LEI 10 caiu para todo mundo")

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

    # ═══ 10/Ago — A PRÓPRIA BATERIA SUJAVA O PLANO DE VOO ═══
    # `F.montar()` é código de produção e marca o waypoint P1_FICHA. Esta trava monta a ficha
    # de TODOS os pacotes do STAGING — 119 na rodada de 10/Ago. Medido: cada execução da
    # Chave 8 escrevia **30.881 bytes** de marcas de produção falsas no `outputs/voo.jsonl`.
    # Terceiro poluidor encontrado no mesmo dia, depois do `ensaio_seco.py` e do
    # `administrador.py` — e o mais irônico: a bateria que existe para provar que o sistema
    # está certo estava adulterando a prova de onde os artigos param.
    import voo as _V
    _V.silenciar(True)
    # 20/Ago — a ficha passou a decidir TEMA, e isso chama PubMed + LLM. A bateria não
    # pode depender de rede: trava lenta e instável é trava que se aprende a ignorar.
    os.environ['CARDIODAILY_SEM_REDE'] = '1'
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
    # AAAA-MM só vale com ano plausível (19xx/20xx) e mês 01-12 — senão é ISSN.
    _re_data = __import__('re').compile(r'^((?:19|20)\d{2}-(?:0[1-9]|1[0-2]))-')
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
        # ⚠️ 21/Ago — ESTA TRAVA LIA ISSN COMO DATA. `0066-782X-abc-122-09-...` é o ISSN dos
        # Arquivos Brasileiros de Cardiologia; ela via "0066" como ano e "78" como mês, e
        # reprovava 3 artigos legítimos. O padrão que o classificador monta é `AAAA-MM-Revista`,
        # com ano plausível e mês de 01 a 12 — e é só esse que se pode comparar.
        # Falso positivo em trava é caro de um jeito específico: ensina a ignorar o vermelho.
        _m = _re_data.match(base)
        if _m and dt[:7] and dt[:7] != _m.group(1):
            mau_data.append(f"{base[:28]}: nome {_m.group(1)} × data {dt[:7]}")
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


def teste_quem_grava_e_quem_le_apontam_para_o_mesmo_arquivo():
    """11/Ago — UM `..` A MAIS, E A APROVAÇÃO DELE CAÍA FORA DO PROJETO.

    ═══ O CASO ═══
    O `administrador.py` mora em `CardioDaily_FULL/src/` e montava a agenda com DOIS `..`:
        gravava em : ~/projetos/saidas/agenda_envio.csv          ← fora do projeto
        lida em    : ~/projetos/CardioDaily_FULL/saidas/…        ← dentro
    Enquanto ninguém lia o arquivo, o erro era INVISÍVEL: o painel dizia "Agendado para
    <data>", a fila aparecia na tela — porque `ler_agenda` lia do mesmo lugar errado — e tudo
    parecia funcionar. Só apareceu quando a Chave 21 passou a procurar no lugar certo.

    ═══ POR QUE ISTO MERECE UMA TRAVA ═══
    É o TERCEIRO erro do mesmo formato em dois dias, e o formato é sempre este: duas pontas
    concordando sobre uma coisa errada, ou discordando sobre uma coisa certa, sem nada
    quebrando no meio.
        09/Ago  o `agenda_envio.csv` era gravado e ninguém lia
        10/Ago  `tributo` (o tipo) e `DESCARTAR` (o destino) eram a mesma coisa com dois nomes
        11/Ago  gravar e ler o MESMO nome, em pastas diferentes
    Nada disso levanta exceção. É sempre internamente coerente e sempre gasta a confiança do
    Dr. Eduardo num "eu aprovei e não chegou".

    Esta trava confere, por CÁLCULO e não por leitura, que quem grava e quem lê a agenda
    apontam para o mesmo lugar.

    ═══ 19/Ago — A AGENDA MUDOU DE CASA, E ESTA TRAVA VIROU UMA BOMBA ═══
    Em 17/Ago a agenda saiu do CSV e foi para a tabela `agenda_envio` do Supabase — porque o
    robô que envia roda na NUVEM e nunca veria um arquivo do Mac dele. Certo. O que ficou
    errado foi ISTO AQUI: a trava continuou procurando `AD.AGENDA`, que deixou de existir.

    E o efeito não foi "uma trava reprova". Foi **`AttributeError` no meio da bateria** — o
    runner morria ali, e as ~20 travas seguintes (entre elas as do envio, do MCID e do OCR)
    **nunca rodavam**. Do lado de fora isso não parece falha de prova: parece bateria quebrada.
    É a mesma família do `teste_independencia_nao_cruza_o_nove` de 06/Ago (trava escrita e
    nunca chamada), com um agravante: aqui ela derrubava as outras junto.

    Regra que fica: **trava que fala de coisa que pode ser aposentada CHECA a existência
    antes de tocar.** Recusar é o trabalho dela; explodir não.

    A REGRA que esta trava guarda não mudou — só mudou o endereço. Continua sendo: quem
    GRAVA e quem LÊ a agenda têm de apontar para o MESMO lugar. Hoje esse lugar é uma tabela.
    """
    import os
    import re

    src = os.path.dirname(os.path.abspath(__file__))
    raiz = os.path.dirname(src)

    # ── 1) O CSV é HISTÓRIA. Se ele voltar, é porque alguém reabriu a porta local. ──
    import administrador as AD
    checa("a agenda NÃO voltou para o CSV local (o robô da nuvem não enxerga o Mac)",
          not hasattr(AD, "AGENDA"),
          "o administrador voltou a ter AD.AGENDA — a fila some para quem envia")

    # ── 2) quem GRAVA e quem LÊ falam da MESMA tabela ──
    # ⚠️ Olhar só `sb.table("…")` NÃO serve: o Administrador fala com o Supabase por REST
    # (`{url}/rest/v1/agenda_envio`) e o distribuidor pelo cliente (`sb.table("agenda_envio")`).
    # Duas formas de dizer a mesma coisa — a trava tem de aceitar as duas, ou reprova o certo.
    def _cita_a_tabela(caminho):
        t = open(caminho, encoding="utf-8").read()
        return ('/rest/v1/agenda_envio' in t) or re.search(r'table\(\s*["\']agenda_envio["\']', t)

    checa("o Administrador grava na tabela agenda_envio", bool(_cita_a_tabela(AD.__file__)),
          "o painel aprova e não escreve na fila que o robô lê")

    dist = os.path.join(raiz, "distribuidor.py")
    if os.path.exists(dist):
        checa("o distribuidor LÊ a mesma tabela agenda_envio", bool(_cita_a_tabela(dist)),
              "o envio procura a fila em outro lugar — aprovado no painel, nada no WhatsApp")

        # ⚠️ O CSV pode (e deve) aparecer nos COMENTÁRIOS — é o registro histórico de 09 a
        # 14/Ago, e apagá-lo custaria a memória de por que a agenda mudou de casa. O que não
        # pode é o CSV voltar a ser CÓDIGO. Por isso a busca é no ast, ignorando docstring.
        import ast as _ast
        arvore = _ast.parse(open(dist, encoding="utf-8").read())
        docs = set()
        for n in _ast.walk(arvore):
            if isinstance(n, (_ast.Module, _ast.FunctionDef, _ast.ClassDef)) and n.body \
                    and _ast.get_docstring(n, clean=False) is not None:
                docs.add(id(n.body[0].value))
        vivo = [n.value for n in _ast.walk(arvore)
                if isinstance(n, _ast.Constant) and isinstance(n.value, str)
                and id(n) not in docs and "agenda_envio.csv" in n.value]
        nomes = [t.id for n in _ast.walk(arvore) if isinstance(n, _ast.Assign)
                 for t in n.targets if isinstance(t, _ast.Name) and t.id == "AGENDA_CSV"]
        checa("e o CSV não voltou a ser CÓDIGO no envio", not vivo and not nomes,
              f"strings vivas={vivo} · variáveis={nomes} — duas fontes de verdade para a mesma fila")


def teste_uma_tabela_de_teto_e_o_protocolo_nao_pontua():
    """11/Ago — *"COMO QUE O SISTEMA ME DÁ NOTA 8 PARA ISSO?"*

    Duas perguntas dele, mesma raiz: desenho fraco recebendo nota alta. As causas eram
    DIFERENTES, e as duas estão travadas aqui.

    ═══ CAUSA 1 · HAVIA DUAS TABELAS DE TETO ═══
    O motor guardava `_TETO_INTERVENCAO` (coorte 6) e `_TETO_NAO_INTERVENCAO` (coorte 8), e
    escolhia entre elas pelo tipo de PERGUNTA. Coorte de prognóstico pegava 8. A LEI 0 diz
    *"coorte sem adjudicação central → 6"* e *"observacional recebendo NAC 8 → ERRADO"*.
    Família do dia: duas fontes de verdade, no lugar mais caro que existe — a nota.
    MEDIDO: 147 de 683 artigos (22 %) acima do teto do próprio desenho.
    Decisão dele, com os números na mesa: UMA tabela, a da LEI 0.

    ═══ CAUSA 2 · PROTOCOLO DE ESTUDO ═══
    Três "Rationale and Design" no Supabase, **todos com nota 8**. O extrator leu randomização,
    dois braços e desfecho primário e escreveu `rct` — CORRETAMENTE, porque o desenho descrito
    é de RCT. O motor deu o teto do RCT, 10. Ninguém errou: faltava a palavra `protocolo` no
    vocabulário. Um protocolo não tem resultado; não há o que aplicar à beira do leito.

    ⚠️ O QUE ESTA TRAVA **NÃO** PODE DEIXAR PASSAR NO SENTIDO CONTRÁRIO: o Framingham. Ele
    perde aplicabilidade (8→6) mas **mantém rigor 8**. Se a coleta impecável parar de valer no
    rigor, a régua virou cega — e aí não é a LEI 10, é preguiça.
    """
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import notas_prototipo as N

    # ── 1) AS DUAS TABELAS FICAM. Elas não discordam: respondem perguntas diferentes ──
    #
    # ⚠️ ESTA TRAVA JÁ ESTEVE ESCRITA AO CONTRÁRIO, no mesmo dia. Eu tinha posto
    # `a tabela morta _TETO_NAO_INTERVENCAO NÃO voltou` e chamado a unificação de "decisão
    # dele". Não era: eu propus, ele aceitou sem ver o caso-limite, e recusou assim que viu
    # (*"o Framingham agora tira 6 — isto obviamente está errado!"*). Uma trava que chumba a
    # régua errada não deixa só o defeito passar — **ela impede o conserto**, porque reprova
    # quem tenta arrumar. É o pior tipo de trava que existe.
    for viva in ("_TETO_INTERVENCAO", "_TETO_NAO_INTERVENCAO"):
        checa(f"{viva} existe", hasattr(N, viva),
              "as duas tabelas respondem PERGUNTAS diferentes; para etiologia/prognóstico o "
              "RCT é impossível e a coorte prospectiva é o teto que a pergunta admite")
    checa("_TETO_NAO_INTERVENCAO['coorte'] continua 8",
          getattr(N, "_TETO_NAO_INTERVENCAO", {}).get("coorte") == 8,
          "capar a coorte de etiologia em 6 é dizer que nenhum estudo de fator de risco pode "
          "ser aplicável — o Framingham mudou a cardiologia mais que quase todo RCT")
    checa("_TETO_INTERVENCAO['coorte'] continua 6",
          getattr(N, "_TETO_INTERVENCAO", {}).get("coorte") == 6,
          "para INTERVENÇÃO existe RCT; coorte não pode subir")

    # e o RCT de verdade continua podendo chegar a 10
    a = {"desenho": "rct", "pergunta": "intervencao", "retrospectivo": False,
         "poder_ok": True, "open_label": False}
    checa("RCT de intervenção continua podendo chegar a 10", N.teto_desenho(a) == 10,
          f"veio {N.teto_desenho(a)} — a régua ficou cega, não severa")

    # ── 2) O SELO PROSPECTIVO — a subida NOMEADA, e ela não se ganha por silêncio ──
    #
    # ⚠️ Esta parte da trava já esteve ESCRITA AO CONTRÁRIO, hoje mesmo. Eu tinha posto
    # `Framingham: aplicabilidade cai para 6` e chamado isso de "a decisão dele". O Dr.
    # Eduardo recusou: *"não pode. Isto obviamente está errado!"*. Para etiologia o RCT é
    # impossível — a coorte prospectiva é o teto que a pergunta admite. Uma trava que
    # chumba a régua errada é pior que trava nenhuma: ela IMPEDE o conserto.
    FRAM = {"pergunta": "etiologia", "desenho": "coorte", "retrospectivo": False,
            "desenho_apropriado": True, "qualidade_entrada": True, "follow_up_completo": True,
            "extrapolavel": True, "tipo_documento": "original"}
    fr = N.score(dict(FRAM))
    checa("Framingham (selo completo): aplicabilidade 8", fr["aplic"] == 8,
          f"veio {fr['aplic']} — capar o Framingham em 6 é dizer que nenhum estudo de fator "
          f"de risco pode ser aplicável")
    checa("Framingham: rigor 8", fr["trabalho"] == 8, f"veio {fr['trabalho']}")

    # o caso NEGATIVO — e é o que realmente estava quebrado: silêncio virava selo.
    # Medido em 11/Ago: 18 das 27 coortes com nota 8 tinham `retrospectivo: null`.
    for rot, mud in (("silêncio sobre retrospectivo", {"retrospectivo": None}),
                     ("declarada retrospectiva", {"retrospectivo": True}),
                     ("seguimento não informado", {"follow_up_completo": None}),
                     ("seguimento incompleto", {"follow_up_completo": False}),
                     ("qualidade da coleta não informada", {"qualidade_entrada": None}),
                     ("desenho inapropriado", {"desenho_apropriado": False})):
        a = dict(FRAM)
        a.update(mud)
        checa(f"sem selo ({rot}): coorte cai de 8 para 7", N.teto_desenho(a) == 7,
              f"veio {N.teto_desenho(a)} — o selo está sendo dado de graça")
        ok, falta = N.selo_prospectivo(a)
        checa(f"sem selo ({rot}): o motivo é dito, não é silêncio", (not ok) and bool(falta),
              "reprovou sem dizer o que faltou — o redator não tem como explicar a nota")

    # O CASO QUE ORIGINOU TUDO, nomeado: silêncio não é selo.
    a = dict(FRAM)
    a["retrospectivo"] = None
    checa("SILÊNCIO sobre `retrospectivo` NÃO concede o teto 8", N.teto_desenho(a) == 7,
          f"veio {N.teto_desenho(a)} — 18 das 27 coortes com nota 8 tinham esse campo em "
          f"branco; `if a.get('retrospectivo')` lia None como 'não é retrospectivo'")

    # e a pergunta de intervenção não sobe nunca — para ela existe RCT
    a = dict(FRAM)
    a["pergunta"] = "intervencao"
    checa("coorte de INTERVENÇÃO não passa de 6 nem com o selo completo",
          N.teto_desenho(a) == 6, f"veio {N.teto_desenho(a)}")

    # ── 3) PROTOCOLO não pontua, nas DUAS portas ──
    checa("o motor conhece a rota do protocolo", hasattr(N, "ROTA_PROTOCOLO"), "sumiu")
    for q in ("intervencao", "prognostico"):
        r = N.score({"desenho": "protocolo", "pergunta": q, "tipo_documento": "original",
                     "retrospectivo": False, "poder_ok": True, "open_label": False,
                     "desfecho_duro": True, "extrapolavel": True})
        checa(f"protocolo/{q}: sai da escala clínica",
              r["rota"] == getattr(N, "ROTA_PROTOCOLO", "?"), f"veio {r['rota']}")
        checa(f"protocolo/{q}: aplicabilidade 0 (não passa em porta nenhuma)", r["aplic"] == 0,
              f"veio {r['aplic']} — um ensaio que ainda não aconteceu viraria perícia e áudio")

    # o schema tem de aceitar a palavra, senão o extrator nunca consegue dizê-la
    try:
        import analise as A
        enum = A.SCHEMA_FATOS["properties"]["desenho"]["enum"]
        checa("o schema de extração aceita `protocolo`", "protocolo" in enum,
              "sem isso o extrator é obrigado a escrever `rct` num protocolo — foi assim que "
              "três deles saíram com nota 8")
    except Exception as e:
        checa("dá para ler o schema de extração", False, f"{type(e).__name__}: {e}")

    # ── 4) o classificador descarta protocolo pelo TÍTULO, antes de gastar análise ──
    try:
        import classificador_pubmed as CP
        pegar = ["…: Design and Rationale of the PRAISE-MR Trial",
                 "…: Rationale and Design of the LEVEL Trial",
                 "Semaglutide in HFpEF: Study Protocol for a Randomized Controlled Trial"]
        passar = ["Dapagliflozin in Patients with Heart Failure and Reduced Ejection Fraction",
                  "Sudden Cardiac Death Due to Myocardial Infarction With Obstructive and "
                  "Nonobstructive Coronary Arteries",
                  "Study design considerations in cardiovascular outcome trials: a review",
                  "Machine learning for the design of new cardiovascular drugs"]
        checa("o classificador reconhece protocolo pelo título",
              all(CP.eh_protocolo(t) for t in pegar),
              f"escapou: {[t[:40] for t in pegar if not CP.eh_protocolo(t)]}")
        falsos = [t for t in passar if CP.eh_protocolo(t)]
        checa("e NÃO pega artigo com resultado (falso positivo custa artigo bom)", not falsos,
              f"pegou indevidamente: {[t[:50] for t in falsos]}")
        checa("protocolo é descartado antes de custar análise",
              CP.eh_descartavel([], pegar[0], "ORIGINAL RESEARCH\n" + pegar[0]),
              "passou pelo descarte — o 'ORIGINAL RESEARCH' impresso no topo o protegeria, "
              "que é exatamente por que a checagem vem ANTES do rotulo_protege")
    except Exception as e:
        checa("dá para testar o classificador", False, f"{type(e).__name__}: {e}")


def teste_o_filtro_de_data_nao_esconde_por_conta_propria():
    """11/Ago — FILTRO DE DATA DE PUBLICAÇÃO NA CHAVE 3.

    Pedido dele: *"fica aparecendo artigos de 1999 na curadoria"* · *"preciso de filtro de
    data — data de inicio das buscas e final"*.

    ═══ AS DUAS DECISÕES QUE FORAM DELE (LEI 6) ═══
    1. **Qual data.** Medido antes de perguntar: `data_publicacao` vai de 1951 a out/2026;
       `created_at` só cobre 5→11/ago, porque o banco foi refeito. Ele escolheu a data de
       PUBLICAÇÃO — é a que produz o artigo de 1999.
    2. **O padrão é VAZIO, mostra tudo.** Um filtro que já vem ligado é armadilha de memória:
       um dia ele procura um artigo, não acha, e a causa é uma régua que ele não lembra que
       existe. Nada some sem ele mandar.

    ═══ O QUE A TRAVA GUARDA ═══
    As três formas de o filtro esconder coisa em silêncio — todas do mesmo formato que nos
    custou o dia 11/Ago (a tela plausível para o motivo errado):
      · vir ligado de fábrica;
      · engolir uma data malformada e filtrar por ela;
      · esconder o artigo que não TEM data no metadado — punir o artigo pelo defeito do dado.
    """
    import ast
    import os

    raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ad = os.path.join(raiz, "src", "administrador.py")
    t = open(ad, encoding="utf-8").read()
    try:
        arv = ast.parse(t)
    except SyntaxError as e:
        checa("administrador.py compila", False, str(e))
        return

    # 1) o padrão dos dois campos é string vazia
    achou = {}
    for no in ast.walk(arv):
        if isinstance(no, ast.Call) and isinstance(no.func, ast.Attribute) \
                and no.func.attr == "text_input":
            rot = no.args[0].value if no.args and isinstance(no.args[0], ast.Constant) else ""
            if str(rot).startswith(("De ", "Até")):
                v = next((k.value for k in no.keywords if k.arg == "value"), None)
                achou[str(rot)] = (v.value if isinstance(v, ast.Constant) else "<?>")
    checa("existem os dois campos de data (De · Até)", len(achou) == 2,
          f"achei {sorted(achou)} — o filtro que ele pediu tem começo E fim")
    for rot, val in achou.items():
        checa(f"o campo «{rot}» começa VAZIO", val == "",
              f"vem preenchido com {val!r} — esconde artigo sem ele mandar")

    # 2) NENHUM atalho vem marcado
    for no in ast.walk(arv):
        if isinstance(no, ast.Call) and isinstance(no.func, ast.Attribute) \
                and no.func.attr == "radio":
            ops = next((a for a in no.args[1:] if isinstance(a, ast.List)), None)
            if ops and any(isinstance(e, ast.Constant) and "dias" in str(e.value)
                           for e in ops.elts):
                idx = next((k.value for k in no.keywords if k.arg == "index"), None)
                i = idx.value if isinstance(idx, ast.Constant) else 0
                primeiro = ops.elts[0].value if isinstance(ops.elts[0], ast.Constant) else "?"
                checa("o atalho de data começa em «nenhum»", i == 0 and primeiro == "—",
                      f"abre marcado em {primeiro!r} (index={i}) — filtra sem ele pedir")

    # 3) a função passa() — comportamento, não leitura
    fn = next((n for n in arv.body if isinstance(n, ast.FunctionDef) and n.name == "passa"), None)
    checa("o painel tem a função passa()", fn is not None, "sumiu — não há filtro nenhum")
    if fn is None:
        return

    def roda(artigos, d_ini="", d_fim=""):
        ns = {"nmin": 1, "nmax": 10, "f_tipo": [], "f_rev": [], "f_tema": [], "busca": "",
              "_d_ini": d_ini, "_d_fim": d_fim,
              "_dia": lambda a: str(a.get("data_publicacao") or "")[:10]}
        exec(compile(ast.Module(body=[fn], type_ignores=[]), "<passa>", "exec"), ns)
        return [a for a in artigos if ns["passa"](a)]

    base = [{"titulo": "RALES", "data_publicacao": "1999-09-02", "nota_aplicabilidade": 9},
            {"titulo": "PLATO", "data_publicacao": "2009-09-10", "nota_aplicabilidade": 9},
            {"titulo": "de hoje", "data_publicacao": "2026-08-10", "nota_aplicabilidade": 8},
            {"titulo": "SEM DATA", "data_publicacao": None, "nota_aplicabilidade": 9}]

    checa("sem data digitada, o filtro não esconde NADA",
          len(roda(base)) == 4,
          f"escondeu {4 - len(roda(base))} com os campos vazios — o padrão dele é mostrar tudo")

    r = [a["titulo"] for a in roda(base, d_ini="2026-01-01")]
    checa("«De» corta o que é mais antigo", "RALES" not in r and "de hoje" in r, f"devolveu {r}")

    r = [a["titulo"] for a in roda(base, d_fim="2010-12-31")]
    checa("«Até» corta o que é mais novo", "de hoje" not in r and "RALES" in r, f"devolveu {r}")

    # o coração: artigo sem data NUNCA é escondido pelo filtro de data
    for i, f in (("2026-01-01", ""), ("", "2010-12-31"), ("2026-07-01", "2026-08-01")):
        r = [a["titulo"] for a in roda(base, i, f)]
        checa(f"artigo SEM data sobrevive ao filtro ({i or '—'} … {f or '—'})",
              "SEM DATA" in r,
              "sumiu — seria punir o artigo pelo defeito do metadado, e ele nunca saberia")


def teste_o_painel_enxerga_o_pacote_onde_o_arquivador_o_deixou():
    """11/Ago — O ACRI SUMIA DO PAINEL À MEDIDA QUE O SISTEMA ERA USADO.

    ═══ O CASO ═══
    O Dr. Eduardo: *"concerta o acri que nao esta mais aparecendo no administrador"*.

    O painel monta uma ponte entre a linha do Supabase e o pacote no disco, para mostrar o
    ACRI que ele copia e cola no grupo. O índice varria SÓ `outputs/STAGING/`. Mas a Chave 4
    (Arquivador) **move** o pacote concluído para `outputs/ARQUIVO/AAAA-MM/` — é o trabalho
    dela, e ela faz certo.

        STAGING    196 pacotes ·  147 ACRI    ← o índice olhava só aqui
        ARQUIVO    864 pacotes ·  571 ACRI    ← invisível

    MEDIDO: dos 37 artigos nota 9 que o painel lista por padrão, **26 não achavam pacote
    nenhum** (11/37). Depois de varrer as duas árvores: **37/37, todos com ACRI**.

    ═══ POR QUE MERECE TRAVA ═══
    O defeito PIORA COM O USO. Cada rodada do Arquivador esvazia mais um pedaço do painel, e
    ninguém é avisado: o artigo continua na lista, ele clica, e o bloco do ACRI só não desenha.
    É a mesma família da semana — duas pontas, uma escreve num lugar novo e a outra continua
    lendo o velho, sem nada quebrando no meio:
        09/Ago  o `agenda_envio.csv` era gravado e ninguém lia
        11/Ago  gravar e ler o MESMO nome, em pastas diferentes (dois `..`)
        11/Ago  DOIS telefones do dono, e a trava comparando com o velho
        11/Ago  o pacote muda de pasta e o painel fica olhando a antiga

    Esta trava não pergunta "existe uma variável _ARQUIVO?" — ela CONTA quantos pacotes o
    índice do painel alcança e reprova se o ARQUIVO ficar de fora.
    """
    import os
    import glob
    import re

    raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out = os.path.join(raiz, "outputs")
    stg = os.path.join(out, "STAGING")
    arq = os.path.join(out, "ARQUIVO")

    def canonicos(base):
        return (glob.glob(os.path.join(base, "*", "*_CANONICO.md")) +
                glob.glob(os.path.join(base, "*", "*", "*_CANONICO.md")))

    n_stg, n_arq = len(canonicos(stg)), len(canonicos(arq))

    # 1) o código do painel varre as DUAS árvores
    ad = os.path.join(raiz, "src", "administrador.py")
    t = open(ad, encoding="utf-8").read()
    try:
        import ast
        arv = ast.parse(t)
        fn = next((n for n in ast.walk(arv)
                   if isinstance(n, ast.FunctionDef) and n.name == "indice_do_disco"), None)
    except SyntaxError as e:
        fn = None
        checa("administrador.py compila", False, str(e))
    checa("o painel tem um indice_do_disco", fn is not None, "sumiu — a ponte com o ACRI acabou")

    checa("o painel conhece a pasta ARQUIVO",
          bool(re.search(r"_ARQUIVO\s*=.*ARQUIVO", t)),
          "só conhece o STAGING — todo pacote já arquivado perde o ACRI no painel, "
          f"e hoje isso são {n_arq} pacotes")

    if fn is not None:
        nomes = {n.id for n in ast.walk(fn) if isinstance(n, ast.Name)}
        checa("o índice varre STAGING **e** ARQUIVO",
              "_RAIZES" in nomes or {"_STAGING", "_ARQUIVO"} <= nomes,
              "varre uma árvore só — o defeito PIORA a cada rodada da Chave 4")

    # 2) A PROVA QUE IMPORTA — e ela precisa usar as raízes DO PAINEL.
    #
    #    ⚠️ A primeira versão desta checagem recalculava o índice aqui, com `(arq, stg)`
    #    escritos por mim. Ou seja: media o DISCO, não o painel. Na sabotagem eu apontei o
    #    painel só para o STAGING e esta linha continuou ✅ — porque ela nem olhava para o
    #    painel. Trava que mede a coisa errada dá o mesmo resultado com e sem o defeito.
    #    Agora as raízes são LIDAS do administrador.py e usadas como ele as usa.
    raizes_do_painel = None
    try:
        ns = {"__file__": ad, "_os": os}
        corpo = []
        for no in ast.parse(t).body:
            if isinstance(no, ast.Assign) and any(
                    isinstance(a, ast.Name) and a.id in ("_OUT", "_STAGING", "_ARQUIVO", "_RAIZES")
                    for a in no.targets):
                corpo.append(no)
        exec(compile(ast.Module(body=corpo, type_ignores=[]), "<raizes>", "exec"), ns)
        raizes_do_painel = ns.get("_RAIZES") or tuple(
            v for k, v in ns.items() if k in ("_ARQUIVO", "_STAGING"))
    except Exception as e:
        checa("dá para ler as raízes que o painel usa", False, f"{type(e).__name__}: {e}")

    checa("o painel define alguma raiz de busca", bool(raizes_do_painel),
          "não achei _RAIZES nem _STAGING/_ARQUIVO — a ponte com o ACRI não existe")

    if raizes_do_painel and n_arq:
        alcance = set()
        for base in raizes_do_painel:
            for can in canonicos(base):
                try:
                    txt = open(can, encoding="utf-8", errors="replace").read(4000)
                except Exception:
                    continue
                m = re.search(r'doi:\s*"([^"]+)"', txt)
                if m:
                    alcance.add(m.group(1).strip().lower())
        so_stg = set()
        for can in canonicos(stg):
            try:
                txt = open(can, encoding="utf-8", errors="replace").read(4000)
            except Exception:
                continue
            m = re.search(r'doi:\s*"([^"]+)"', txt)
            if m:
                so_stg.add(m.group(1).strip().lower())
        checa("as raízes DO PAINEL alcançam os pacotes arquivados",
              len(alcance) > len(so_stg),
              f"o painel alcança {len(alcance)} DOI e o STAGING sozinho já tem {len(so_stg)} — "
              f"os {n_arq} pacotes do ARQUIVO estão fora do alcance dele")

    # 3) o ttl do cache não pode ser curto: 1.015 pacotes levam ~7s para indexar
    #
    #    ⚠️ Este pedaço já reprovou o código CERTO uma vez. Eu casava o decorador com
    #    `@st\.cache_data\(ttl=(\d+)[^)]*\)` — e a mensagem do spinner é
    #    "Lendo os pacotes no disco (STAGING + ARQUIVO)…", com parênteses DENTRO da string.
    #    O `[^)]*\)` fechava no parêntese do texto e o casamento morria ali. Regex contando
    #    parêntese é ilusão de precisão; agora acha o `def` pelo ast e lê o ttl do decorador.
    ttl = None
    tem_cache = False
    if fn is not None:
        for dec in fn.decorator_list:
            alvo = dec.func if isinstance(dec, ast.Call) else dec
            if "cache_data" in ast.dump(alvo):
                tem_cache = True
                if isinstance(dec, ast.Call):
                    for kw in dec.keywords:
                        if kw.arg == "ttl" and isinstance(kw.value, ast.Constant):
                            ttl = kw.value.value
    checa("o índice do disco tem cache", tem_cache,
          "sem cache, cada clique relê ~1.000 pastas do disco")
    if tem_cache:
        checa("o cache do índice dura ao menos 15 minutos", isinstance(ttl, int) and ttl >= 900,
              f"ttl={ttl}s — a cada expiração ele espera ~7s parado no meio da curadoria")


def teste_o_envio_sobrevive_ao_dia_vazio():
    """17/Ago — O CRON MORREU NO CAMINHO MAIS COMUM: O DIA SEM NADA AGENDADO.

    ═══ O CASO ═══
        UnboundLocalError: cannot access local variable 'selecionados'
        distribuidor.py, em distribuir_artigos

    Em 14/Ago eu removi o bloco do "livro de bordo" com um recorte por ÍNDICE de texto
    (`t[:i] + t[j:]`) e levei junto o `else:` que tratava a fila vazia. O arquivo compilou,
    a bateria inteira passou, e o defeito ficou invisível — porque só aparece quando NÃO há
    nada agendado, que é o dia comum.

    Medido no GitHub Actions: 15 e 16/Ago o cron enviou certo. 17/Ago a fila estava vazia às
    07:00 e o processo morreu com exit code 1, sem mandar nada e sem avisar ninguém.

    ⚠️ E EU DIAGNOSTIQUEI ERRADO. Olhei a tabela `agenda_envio`, vi `enviado_em IS NULL`, e
    disse ao Dr. Eduardo que "o robô rodou, não achou nada e foi embora corretamente". Ele
    abriu o log do Actions e me mostrou a exceção. **Dado ausente não diz a causa da
    ausência** — banco vazio e programa morto produzem exatamente a mesma linha.

    ═══ POR QUE ESTA TRAVA É DIFERENTE DAS OUTRAS ═══
    As outras leem o código. Esta EXECUTA `distribuir_artigos` inteira, com um Supabase que
    devolve lista vazia — o caminho que quebrou. Nenhuma leitura de fonte teria pego isto:
    o arquivo estava sintaticamente perfeito.
    """
    import os
    import sys
    import types

    for m in ("supabase", "httpx", "dotenv"):
        sys.modules.setdefault(m, types.ModuleType(m))
    sys.modules["supabase"].create_client = lambda *a, **k: None
    sys.modules["supabase"].Client = object
    sys.modules["dotenv"].load_dotenv = lambda *a, **k: None
    sys.modules["httpx"].get = sys.modules["httpx"].post = lambda *a, **k: None
    sys.modules["httpx"].Timeout = lambda *a, **k: None
    sys.modules["httpx"].Client = lambda *a, **k: None
    for k, v in (("SUPABASE_URL", "x"), ("SUPABASE_SERVICE_KEY", "x"), ("ZAPI_BASE", "x"),
                 ("ZAPI_CLIENT_TOKEN", "x"), ("EDUARDO_PHONE", "5527996089248"),
                 ("CD_PULAR_CHECK_ZAPI", "1")):
        os.environ.setdefault(k, v)
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    try:
        import distribuidor as D
    except Exception as e:
        checa("dá para importar o distribuidor", False, f"{type(e).__name__}: {e}")
        return

    class _R:
        def __init__(s, d):
            s.data = d

    class _SBVazio:
        """o Supabase de um dia sem curadoria: tudo responde lista vazia"""
        def table(s, *a): return s
        def select(s, *a, **k): return s
        def eq(s, *a, **k): return s
        def is_(s, *a, **k): return s
        def gte(s, *a, **k): return s
        def order(s, *a, **k): return s
        def limit(s, *a, **k): return s
        def execute(s): return _R([])

    conectar, enviar = D.conectar_supabase, D.zapi_send_text
    D.conectar_supabase = lambda: _SBVazio()
    D.zapi_send_text = lambda p, m: True
    try:
        import io
        import logging
        buf = io.StringIO()
        h = logging.StreamHandler(buf)
        logging.getLogger().addHandler(h)
        try:
            D.distribuir_artigos(dry_run=False)
            checa("o envio SOBREVIVE ao dia sem nada agendado", True)
            saida = buf.getvalue()
            # 17/Ago — o resumo gritava "NADA FOI ENTREGUE e HAVIA artigo aprovado" mesmo
            # com a fila vazia. Alarme que toca no dia normal é alarme que se aprende a
            # ignorar — e foi assim que 12 e 13/Ago passaram em branco.
            checa("e NÃO grita alarme falso no dia vazio",
                  "NADA FOI ENTREGUE" not in saida,
                  "diz 'havia artigo aprovado' quando não havia — o alarme perde o valor")
        except Exception as e:
            checa("o envio SOBREVIVE ao dia sem nada agendado", False,
                  f"{type(e).__name__}: {e} — é o defeito de 17/Ago voltando")
        finally:
            logging.getLogger().removeHandler(h)
    finally:
        D.conectar_supabase, D.zapi_send_text = conectar, enviar


def teste_a_agenda_mora_na_nuvem_e_nao_repete_mensagem():
    """14/Ago — O ENVIO PASSOU A RODAR COMO O RADAR, E A AGENDA SAIU DO DISCO.

    ═══ O CASO ═══
    *"programei os artigos ontem que deveria receber nos próximos 3 dias, mas não funcionou"*
    e, depois: *"por que o sistema não usa o mesmo do radar, que envia todos os dias
    independente de como meu computador estiver ligado ou não?"*

    A primeira resposta era "nada roda sozinho" (o cron foi desligado em 27/Jul). Eu montei
    um agendador no macOS — que só funciona com o notebook ligado às 07:00, e ele é
    plantonista. **Aquilo resolvia o meu problema, não o dele.** Ele perguntou o óbvio, e o
    óbvio estava certo: o Radar roda na nuvem porque não depende de NADA no Mac dele. O envio
    de artigos era idêntico, com UMA diferença — a agenda morava em `saidas/agenda_envio.csv`,
    e a nuvem não enxerga o disco dele. Era um arquivo.

    ═══ E A TABELA COMEU O LIVRO DE BORDO ═══
    Na mesma tarde eu tinha criado um segundo arquivo local (`saidas/enviados.csv`) para
    impedir mensagem repetida entre o agendador e a Chave 21. Durou uma hora: com a agenda na
    tabela, `enviado_em` responde "já saiu?" NA MESMA LINHA que responde "está agendado?".
    Dois arquivos que podem discordar viraram uma linha que não pode.

    ═══ O QUE A TRAVA GUARDA ═══
    1. o distribuidor lê a AGENDA DO SUPABASE, não de arquivo — senão volta a depender do Mac;
    2. a consulta pede `enviado_em IS NULL` — senão o cron das 07:00 e um clique às 10:00
       mandam os mesmos artigos duas vezes;
    3. falha de leitura devolve `None`, não `[]` — `[]` significaria "nada aprovado hoje", a
       mensagem certa pelo motivo errado. Mesma família do `retrospectivo: null` de 11/Ago:
       tratar "não sei" como "não";
    4. o carimbo é artigo por artigo, não no fim do laço;
    5. o AVISO DIÁRIO existe — foi a ausência dele que fez os dias 12 e 13 passarem em branco
       sem ninguém perceber. Envio automático sem aviso é pior que manual.
    """
    import os
    import sys
    import types

    for m in ("supabase", "httpx", "dotenv"):
        sys.modules.setdefault(m, types.ModuleType(m))
    sys.modules["supabase"].create_client = lambda *a, **k: None
    sys.modules["supabase"].Client = object
    sys.modules["dotenv"].load_dotenv = lambda *a, **k: None
    sys.modules["httpx"].get = sys.modules["httpx"].post = lambda *a, **k: None
    sys.modules["httpx"].Timeout = lambda *a, **k: None
    sys.modules["httpx"].Client = lambda *a, **k: None
    os.environ.setdefault("SUPABASE_URL", "x")
    os.environ.setdefault("SUPABASE_SERVICE_KEY", "x")
    os.environ.setdefault("ZAPI_BASE", "x")
    os.environ.setdefault("ZAPI_CLIENT_TOKEN", "x")
    os.environ.setdefault("EDUARDO_PHONE", "5527996089248")
    raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, raiz)
    try:
        import distribuidor as D
    except Exception as e:
        checa("dá para importar o distribuidor", False, f"{type(e).__name__}: {e}")
        return

    fonte = open(os.path.join(raiz, "distribuidor.py"), encoding="utf-8").read()

    # 1) a agenda vem do SUPABASE, não de arquivo
    checa("fila_aprovada recebe o cliente do Supabase",
          "def fila_aprovada(sb" in fonte,
          "ainda lê arquivo — o envio volta a depender do Mac dele estar ligado")
    checa('a consulta é na tabela `agenda_envio`',
          'table("agenda_envio")' in fonte, "não achei a tabela na consulta")
    for morto in ("AGENDA_CSV", "LIVRO_CSV", "ja_enviados_hoje"):
        vivos = [n for n, l in enumerate(fonte.splitlines(), 1)
                 if morto in l and not l.strip().startswith("#")]
        checa(f"o arquivo local `{morto}` não é mais lido", not vivos,
              f"linha(s) {vivos} — duas agendas é o defeito que custou 09, 10 e 11/Ago")

    # 2) só o que AINDA NÃO SAIU
    checa("a consulta pede `enviado_em IS NULL`",
          'is_("enviado_em", "null")' in fonte,
          "sem isto o cron das 07:00 e um clique às 10:00 mandam os mesmos artigos 2x")
    checa("existe marcar_enviado()", "def marcar_enviado(" in fonte,
          "sem carimbo, todo disparo do dia repete tudo")
    checa("o carimbo é artigo por artigo, não no fim do laço",
          "marcar_enviado(sb, artigo[" in fonte,
          "se carimbar só no fim, uma queda no meio perde o registro do que já saiu")

    # ── daqui para baixo é pela ÁRVORE do código, não por procurar texto ──
    #
    # ⚠️ DUAS destas checagens já aprovaram o defeito, hoje, na bancada:
    #   · `"_avisar_do_dia(total" in fonte` casava com a linha do **def**, não com a chamada.
    #     Sabotei removendo a chamada e a trava continuou ✅.
    #   · o `return None` era procurado no arquivo INTEIRO, e outras funções têm `return None`.
    # Procurar texto num arquivo de 1.500 linhas é achar o que se quer, não o que existe.
    import ast as _a
    try:
        arv = _a.parse(fonte)
    except SyntaxError as e:
        checa("distribuidor.py compila", False, str(e))
        return

    def _fn(nome):
        return next((n for n in _a.walk(arv)
                     if isinstance(n, _a.FunctionDef) and n.name == nome), None)

    def _chamadas(dentro):
        return {n.func.id for n in _a.walk(dentro)
                if isinstance(n, _a.Call) and isinstance(n.func, _a.Name)}

    # 3) erro de leitura ≠ dia vazio
    fa = _fn("fila_aprovada")
    checa("existe fila_aprovada", fa is not None, "sumiu")
    if fa is not None:
        devolve_none = any(isinstance(n, _a.Return) and isinstance(n.value, _a.Constant)
                           and n.value.value is None for n in _a.walk(fa))
        checa("fila_aprovada devolve None quando NÃO CONSEGUE LER", devolve_none,
              "devolver [] num erro de rede faz o log dizer 'nada aprovado' — a mensagem "
              "certa pelo motivo errado, o defeito que passamos a semana caçando")
    da = _fn("distribuir_artigos")
    if da is not None:
        trata = any(isinstance(n, _a.Compare) and isinstance(n.ops[0], _a.Is)
                    and isinstance(n.comparators[0], _a.Constant)
                    and n.comparators[0].value is None
                    and isinstance(n.left, _a.Name) and n.left.id == "aprovados"
                    for n in _a.walk(da))
        checa("quem chama distingue None de lista vazia", trata,
              "a distinção existe na função e some em quem usa — vira decoração")

    # 4) o aviso diário — o conserto do silêncio dos dias 12 e 13
    av = _fn("_avisar_do_dia")
    checa("existe o aviso diário", av is not None,
          "sem aviso, um envio automático que falha é invisível: ele para de conferir")
    checa("o aviso é CHAMADO no fim do envio",
          da is not None and "_avisar_do_dia" in _chamadas(da),
          "a função existe e ninguém chama — trava aprovando por ausência")
    if av is not None:
        textos = " ".join(n.value for n in _a.walk(av)
                          if isinstance(n, _a.Constant) and isinstance(n.value, str))
        for pedaco, porque in (("nada saiu hoje", "o dia sem envio ficaria em silêncio — "
                                                  "que é o defeito original"),
                               ("falhou", "a falha ficaria só no log da nuvem, que ele não lê"),
                               ("DESTINATÁRIO", "sem destinatário o envio roda e não entrega")):
            checa(f"o aviso cobre o caso «{pedaco}»", pedaco.lower() in textos.lower(), porque)

    # 5) e o cron existe, senão nada disso roda
    wf = os.path.join(raiz, ".github", "workflows", "artigos-diarios.yml")
    if os.path.exists(wf):
        y = open(wf, encoding="utf-8").read()
        checa("o workflow de artigos tem cron",
              "schedule:" in y and "cron:" in y,
              "só workflow_dispatch — volta a depender de alguém apertar o botão")


def teste_um_telefone_do_dono_e_um_so():
    """11/Ago — A TRAVA DE SEGURANÇA IA PULAR O DONO DO SISTEMA.

    ═══ O CASO ═══
    O `distribuidor.py` guardava DOIS telefones do Dr. Eduardo, e eles não eram o mesmo:

        DR_EDUARDO_PHONE = "5527996089248"   chumbado no fim do arquivo
        EDUARDO_PHONE    = "55279881…"       no .env — e é ESTE que a Z-API confirmou
                                             conectado ("phone":"5527988149519" em /device)

    O portão do beta é `if BETA_PAUSADO and phone != DR_EDUARDO_PHONE: pular`. Depois que o
    `buscar_assinantes_ativos` passou a cair no `_eduardo_do_env()` (conserto de 11/Ago, quando
    a consulta ao Supabase devolvia lista VAZIA sem levantar exceção), o destinatário passou a
    vir do .env — e o portão o compararia com o número velho e o PULARIA, imprimindo
    "⏸️ Beta pausado — pulando Dr. Eduardo". Ele leria essa linha sem ter como saber que o
    sistema guardava dois números dele e escolhia o errado para se comparar.

    ═══ POR QUE MERECE TRAVA ═══
    É o QUARTO erro do mesmo formato em três dias — duas fontes para o mesmo fato, uma delas
    velha, e nada quebrando no meio:
        09/Ago  o `agenda_envio.csv` era gravado e ninguém lia
        10/Ago  `tributo` (o tipo) e `DESCARTAR` (o destino): a mesma coisa com dois nomes
        11/Ago  gravar e ler o MESMO nome, em pastas diferentes
        11/Ago  DOIS telefones do dono, e a trava de segurança usando o velho
    E este é o pior da série, porque a peça que erra é justamente a que existe para PROTEGER:
    o portão do beta impede que o sistema mande mensagem para estranho — e mandaria para
    ninguém.

    Confere três coisas, por CÁLCULO:
      1. o telefone vem do .env, não do código;
      2. quem monta o destinatário usa a MESMA variável que o portão compara;
      3. a comparação é por DÍGITOS — '+55 27 98814-9519' e '5527988149519' são o mesmo
         telefone, e o `!=` de string diz que não são.
    """
    import os
    import re

    raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    dist = os.path.join(raiz, "distribuidor.py")
    if not os.path.exists(dist):
        checa("distribuidor.py existe", False, "sumiu")
        return
    t = open(dist, encoding="utf-8").read()

    # 1) o telefone do dono vem do .env
    m = re.search(r"^DR_EDUARDO_PHONE\s*=\s*(.+)$", t, re.M)
    checa("DR_EDUARDO_PHONE existe", bool(m), "sumiu — o portão do beta não tem com quem comparar")
    if m:
        checa("o telefone do dono vem do .env, não do código",
              "EDUARDO_PHONE" in m.group(1) and "environ" in m.group(1),
              f"está chumbado: {m.group(1).strip()} — envelhece sem ninguém perceber")

    # 2) quem MONTA o destinatário usa a MESMA variável que o portão COMPARA
    #
    #    ⚠️ Esta checagem já nasceu ERRADA uma vez, hoje mesmo, na bancada: eu procurava
    #    "DR_EDUARDO_PHONE" no corpo da função — e a DOCSTRING da função cita esse nome. Na
    #    sabotagem, troquei o código por `os.getenv("EDUARDO_PHONE")` e a trava continuou
    #    dizendo ✅, porque leu o comentário. Uma trava que aprova olhando para o texto errado
    #    é pior que trava nenhuma: ela dá confiança falsa. Agora a leitura é da ÁRVORE do
    #    código (ast), onde comentário e docstring não existem.
    try:
        import ast as _ast
        arv = _ast.parse(t)
        fn = next((n for n in _ast.walk(arv)
                   if isinstance(n, _ast.FunctionDef) and n.name == "_eduardo_do_env"), None)
    except SyntaxError as e:
        fn = None
        checa("distribuidor.py compila", False, str(e))
    checa("_eduardo_do_env existe", fn is not None,
          "sumiu — sem ele a lista vazia não tem plano B")
    if fn is not None:
        # ⚠️ Segunda versão desta checagem. A primeira procurava o nome DR_EDUARDO_PHONE em
        #    QUALQUER lugar do corpo — e a função tem um `if not DR_EDUARDO_PHONE:` logo na
        #    entrada. Na sabotagem troquei o valor do telefone por os.getenv() e a trava
        #    continuou ✅, porque o nome ainda aparecia na guarda. Olhar "em algum lugar" não
        #    prova nada: o que importa é de onde sai o VALOR da chave "phone".
        valor = None
        for d in _ast.walk(fn):
            if isinstance(d, _ast.Dict):
                for k, v in zip(d.keys, d.values):
                    if isinstance(k, _ast.Constant) and k.value == "phone":
                        valor = v
        checa("o destinatário tem uma chave 'phone'", valor is not None,
              "sumiu — o distribuidor não sabe para onde mandar")
        if valor is not None:
            checa("o telefone do destinatário É o DR_EDUARDO_PHONE",
                  isinstance(valor, _ast.Name) and valor.id == "DR_EDUARDO_PHONE",
                  f"vem de `{_ast.dump(valor)[:60]}…` — é uma TERCEIRA grafia do mesmo número, "
                  f"e o portão do beta compara com a OUTRA")

    # 3) NENHUMA comparação de telefone em texto cru
    cruas = [n for n, l in enumerate(t.splitlines(), 1)
             if re.search(r"phone\s*[!=]=\s*DR_EDUARDO_PHONE", l)
             and not l.strip().startswith("#")
             and "so_digitos" not in l]
    checa("nenhuma comparação de telefone é feita em texto cru",
          not cruas,
          f"linha(s) {cruas} comparam string — '+55 27…' e '5527…' são o mesmo telefone")

    # 4) a função de normalizar existe e FAZ o que promete
    #
    #    ⚠️ Terceira armadilha da mesma trava, e a pior. Eu recortava o código do so_digitos
    #    com regex + .split("\n\n") — e a DOCSTRING dela tem linha em branco. O recorte cortava
    #    no meio da docstring, o exec levantava SyntaxError, e a exceção matava a bateria
    #    INTEIRA: as outras 60 travas nem rodavam. É o mesmo defeito de 08/Ago (a sabotagem 3
    #    derrubou a bateria em vez de reprovar). Trava que explode não reprova — some.
    #    Agora recorta pela ÁRVORE, e o que der errado vira REPROVAÇÃO, nunca exceção.
    fn_sd = None
    if fn is not None or True:
        try:
            arv2 = _ast.parse(t)
            fn_sd = next((n for n in _ast.walk(arv2)
                          if isinstance(n, _ast.FunctionDef) and n.name == "so_digitos"), None)
        except Exception:
            fn_sd = None
    checa("so_digitos() existe no distribuidor", fn_sd is not None,
          "sem ela a comparação volta a ser por string e o número vai sujo para a Z-API")
    if fn_sd is not None:
        try:
            ns = {}
            exec(compile(_ast.Module(body=[fn_sd], type_ignores=[]), "<so_digitos>", "exec"), ns)
            f = ns["so_digitos"]
            checa("so_digitos normaliza a pontuação",
                  f("+55 (27) 98814-9519") == f("5527988149519") == "5527988149519",
                  f'devolveu {f("+55 (27) 98814-9519")!r} e {f("5527988149519")!r} — '
                  f"o portão pularia o dono e a Z-API recusaria o número")
            checa("so_digitos aguenta vazio e None", f("") == "" and f(None) == "",
                  "quebra quando o telefone não existe — e é exatamente aí que ela é chamada")
        except Exception as e:
            checa("so_digitos roda", False, f"{type(e).__name__}: {e}")


def teste_pagina_so_separa_revisao_de_ponto_de_vista():
    """10/Ago — O DR. EDUARDO TEVE DE REPETIR A REGRA PORQUE EU A ESTIQUEI.

    Ele deu o critério: *"em praticamente todos os pontos de vista que vi tem menos de 3 páginas
    — se tem mais de 5 páginas, independente do que for, fica como revisão"*. Ao ver o risco,
    ele mesmo delimitou: *"estou diferenciando apenas revisão de ponto de vista — isto não se
    aplica a artigo original, que no caso seria obrigatório o IMRD."*

    Eu escrevi a R4 e mesmo assim estiquei em dois lugares: pus "(e para reconhecer tributo)" e
    a frase "não existe revisão, original nem meta com menos de 3 páginas". Ele voltou: *"o
    número de páginas só é útil para avaliar se estamos diante de uma revisão ou ponto de vista.
    Não deve ser usado para nenhuma outra ocasião."*

    POR QUE A REGRA APERTADA IMPORTA — medido no gabarito de 105 antes de eu codar:
        artigo_original                  28 de 29 têm >5 páginas
        revisao_sistematica_meta_analise  8 de  8
        guideline                         6 de  7
        minirevisao                      28 de 46
    Uma régua de página solta no prompt viraria 70 dos 105 em revisão. O tributo se reconhece
    pelo RÓTULO IMPRESSO (TRIBUTE, IN MEMORIAM), não pelo tamanho — e é assim que ele está
    implementado, no `classificador_pubmed.eh_tributo`.
    """
    import os
    import re
    import classificador_prompt as CP

    p = CP.PROMPT
    checa("a R4 existe no prompt", "R4 ·" in p, "a regra da página sumiu")
    checa("a R4 tem a PROIBIÇÃO explícita de usar página noutra decisão",
          "NENHUMA outra decisão" in p,
          "a trava textual sumiu — a régua de página volta a poder decidir qualquer coisa")

    # o bloco da R4, isolado: nele NÃO pode aparecer nenhum outro tipo como consequência
    m = re.search(r"R4 ·.*?(?=\nR5 ·)", p, re.S)
    checa("o bloco da R4 foi encontrado", bool(m), "a numeração das regras mudou — refazer a trava")
    if m:
        bloco = m.group(0)
        # as únicas duas saídas permitidas da régua de página
        saidas = set(re.findall(r"→\s*([a-z_]+)", bloco))
        checa(f"a R4 só decide revisao_geral e ponto_de_vista (achei {sorted(saidas)})",
              saidas <= {"revisao_geral", "ponto_de_vista"},
              "a régua de página voltou a decidir outro tipo — foi assim que eu estiquei a regra "
              "dele em 10/Ago, e ela transformaria 70 dos 105 artigos do gabarito em revisão")

    # e o campo tem de continuar chegando ao modelo (senão a R4 é decoração — o defeito de 06/Ago)
    montado = CP.montar("texto qualquer", paginas=7)
    checa("o total de páginas chega ao prompt", "Total de páginas do PDF: 7" in montado,
          "o campo parou de viajar: a R4 vira letra morta e ninguém percebe")
    checa("sem o número, o prompt diz 'não informado' em vez de mentir 0",
          "não informado" in CP.montar("texto", paginas=0),
          "um PDF que não abriu passaria como se tivesse 0 páginas → viraria ponto de vista")


def teste_o_llm_le_todo_artigo():
    """10/Ago — O RÓTULO IMPRESSO DECIDIA 34% DOS ARTIGOS E O LLM NUNCA ERA CHAMADO.

    ═══ O QUE ACONTECEU ═══
    Quatro artigos foram para a caixa errada na rodada de 10/Ago. Nos QUATRO, a coluna `modelo`
    do diário estava VAZIA: o juiz que lê as páginas 1–3 — medido em 110/111 = 99,1 % no
    gabarito conferido à mão pelo Dr. Eduardo — **nunca foi chamado**. Uma camada de cima
    respondeu antes.

    A camada era o RÓTULO IMPRESSO ("ORIGINAL RESEARCH"), que decidia 240 dos 703 artigos e
    rodava DEPOIS do PubMed e ANTES do LLM. Revista carimba meta-análise como ORIGINAL RESEARCH
    o tempo todo: é o nome da SEÇÃO, não o desenho do estudo.
        · "Incidence and Predictors of Extracranial Bleeding"  → rótulo ORIGINAL RESEARCH ARTICLE
        · "Bradyarrhythmia … A Systematic Scoping Review"      → rótulo ORIGINAL RESEARCH

    ═══ POR QUE A CASCATA EXISTIA, E POR QUE O ARGUMENTO CAIU ═══
    Ela existia para poupar chamadas de LLM. MEDIDO em 736 leituras reais: US$ 0,001 por artigo,
    mediana de 4.482 tokens de entrada. Ler os 740 artigos de um mês inteiro custa **US$ 0,72**.
    O histórico completo de classificação custou US$ 0,71.
    A economia era de 56 centavos por mês. O preço dela foi um Nature Medicine com nota 3.

    ═══ O DESENHO QUE O DR. EDUARDO ESCOLHEU ═══
    O LLM lê TODO artigo. As camadas determinísticas que sobrevivem DECIDINDO são as que têm
    autoridade humana atrás: o mapa de revista (curadoria dele), o rótulo NEGATIVO (editorial
    rouba o DOI do artigo comentado), o descarte, o título que declara meta, e o PubMed
    (catalogação da NLM — foi ele que sabia do `Scoping Review` que o meu mapa ignorava).
    O rótulo IMPRESSO vira CONFERÊNCIA: se discordar do LLM, ninguém escolhe no escuro — vai
    para REVISAO_HUMANA. LEI 8, ponto 4.
    """
    import os
    import re
    import classificador_ouro as C
    import classificador_pubmed as P

    # 1) o mapa do PubMed continua sem inventar decisão para o balde genérico
    #    (`Scoping Review` NÃO entra: a `teste_mapa_pubmed` de 02/Ago proíbe pubtype decidindo
    #     `revisao_geral`, e ela está certa — com o LLM lendo todos, quem resolve é ele)
    checa("PubMed 'Scoping Review' NÃO decide sozinho (vai ao LLM)",
          P.map_pubtype(["Journal Article", "Scoping Review"]) is None,
          "voltou a remendar o mapa com caso particular em vez de deixar o juiz ler")
    checa("PubMed 'Systematic Review' continua na trilha da meta (D-01)",
          P.map_pubtype(["Systematic Review"]) == "revisao_sistematica_meta_analise",
          "a D-01 do Dr. Eduardo (31/Jul) foi quebrada")
    checa("PubMed 'Practice Guideline' continua diretriz",
          P.map_pubtype(["Practice Guideline"]) == "guideline", "diretriz deixou de ser reconhecida")

    # 2) ": A Review" é revisão narrativa; "Systematic Review and Meta-Analysis" NÃO é
    checa("': A Review' é reconhecido como revisão narrativa",
          C.titulo_diz_revisao_narrativa("Gastroparesis: A Review."),
          "as revisões da JAMA voltam a cair na trilha da meta citando 'We conducted a PubMed search'")
    checa("'Systematic Review and Meta-Analysis' NÃO é narrativa",
          not C.titulo_diz_revisao_narrativa("Omega-3 and AF: A Systematic Review and Meta-Analysis"),
          "a trava está roubando meta-análise de verdade para a trilha da revisão")
    checa("'A Randomized Trial' não é revisão",
          not C.titulo_diz_revisao_narrativa("Effects of X on Y: A Randomized Trial"),
          "a trava está pegando ensaio clínico")

    # 3) VARREDURA: só DUAS camadas podem decidir antes do LLM
    #    Decisão do Dr. Eduardo, 10/Ago: mapa de revista (curadoria dele, 86 artigos e 100 % de
    #    acerto medido) e LIXO (relato de caso: "= LIXO", não se paga leitura para jogar fora).
    #    Tudo o mais é conferência. Esta varredura é a guarda da ordem — se alguém acrescentar um
    #    `elif` decidindo antes do LLM, o juiz volta a ser calado e ninguém percebe.
    src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "classificador_ouro.py"), encoding="utf-8").read()
    bloco = re.search(r"TRAVA: rede caiu.*?\n(\s+)else:\n", src, re.S)
    checa("o bloco da cascata foi encontrado", bool(bloco), "a estrutura mudou — refazer a trava")
    if bloco:
        decisores = re.findall(r"^\s+elif (.+?):\s*$", bloco.group(0), re.M)
        checa(f"só 2 camadas decidem antes do LLM (achei {len(decisores)})", len(decisores) == 2,
              "camada nova decidindo antes do juiz: " + " | ".join(d[:40] for d in decisores))
        checa("uma delas é o mapa de revista",
              any("mapa_revista" in d for d in decisores), "o mapa do Dr. Eduardo saiu da cascata")
        checa("a outra é o descarte de relato de caso",
              any("eh_descartavel" in d for d in decisores), "o filtro de lixo saiu da cascata")
        checa("o PubMed NÃO decide mais (60,0 % contra 99,1 % do LLM)",
              not any("map_pubtype" in d for d in decisores),
              "o PubMed voltou a decidir — ele erra 4 em 10 quando opina, medido no gabarito")
        checa("o rótulo impresso NÃO decide mais",
              not any("rotulo_original" in d or "rotulo_topo" in d for d in decisores),
              "a camada que decidia 240 de 703 e produziu os erros de 10/Ago voltou")

    # 4) NADA DE REVISÃO HUMANA POR DISCORDÂNCIA
    # *"a llm tem que acertar - nada de revisão humana - só teremos que fazer revisão humana se
    #  formos incompetentes em fazer os filtros corretos para a llm ler no início!"*
    checa("discordância NÃO desvia o artigo para revisão humana",
          "DISCORDÂNCIA: rótulo" not in src,
          "voltou a mandar divergência para fila manual — isso transfere ao Dr. Eduardo o custo "
          "de um filtro mal feito, em vez de consertar o filtro")
    checa("a conferência é registrada no diário", '"conferencia"' in src,
          "sem a coluna, a divergência não vira conserto de filtro: some")

    # 4) A TRAVA `CAIXA ERRADA` DEPENDE DE UM CAMPO ATRAVESSAR TRÊS ARQUIVOS
    # Sabotagem de 10/Ago: bastou a ficha mandar `_desenho: ""` e a trava do contrato PAROU de
    # disparar — sem erro, sem aviso, dando aprovado. É o defeito de 06/Ago (motor certo +
    # schema certo + prompt calado = campo null para sempre) e o de 05/Ago (palavras-chave da
    # meta sem instrução). Trava que depende de campo ausente não é trava: é decoração que dá
    # APROVADO POR AUSÊNCIA — o mesmo pecado do runner de lista fixa.
    import contrato as CT
    fake = {"tipo_documento": "original", "_desenho": "meta", "nota_aplicabilidade": 8}
    achou = any("CAIXA ERRADA" in x for x in CT.validar(fake, checar_arquivos=False))
    checa("contrato: desenho de meta na trilha de original é RETIDO", achou,
          "a rede de segurança da LEI 8 sumiu — meta volta a ser julgada com a régua do original")
    limpo = {"tipo_documento": "original", "_desenho": "coorte", "nota_aplicabilidade": 8}
    checa("contrato: coorte na trilha de original passa (não pode acusar inocente)",
          not any("CAIXA ERRADA" in x for x in CT.validar(limpo, checar_arquivos=False)),
          "a trava está retendo artigo original legítimo")
    fs = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "ficha_site.py"),
              encoding="utf-8").read()
    checa("a ficha carrega o desenho até o contrato", '"_desenho": desenho' in fs,
          "o campo parou de viajar: a trava acima vira decoração e aprova por ausência")


def teste_o_instrumento_nao_mente():
    """10/Ago — A CHAVE 18 RELATOU 155 DESAPARECIDOS NUMA RODADA SEM UM ÚNICO DEFEITO.

    ═══ O CASO REAL ═══
    A primeira rodada grande com o plano de voo terminou limpa: 41 artigos recusados, TODOS
    nota <6 (2 com nota 0, 3 com 3, 8 com 4, 28 com 5) — a LEI 10 exatamente como o Dr. Eduardo
    a escreveu. A caixa-preta relatou:

        ── 155 DE 281 NÃO CHEGARAM ──
        ▸ silêncio entre P3_MIDIA e P4_BANCO   —   114 artigo(s)
        ▸ falha reportada em P2_CONTRATO       —    35 artigo(s)   erro: bloco A do ACRI vazio
        ▸ silêncio entre P1_FICHA e P2_CONTRATO —    6 artigo(s)

    Nenhum dos três era verdade. TRÊS defeitos, todos do INSTRUMENTO:

    1. IDENTIDADE (os 114) — o P3_MIDIA marcava `artigo=objeto`, e objeto é o nome do arquivo
       no Storage (`10.1016/j.ahj.2026.107510.pdf`). Os outros marcam o nome do PACOTE. Medido:
       P1↔P2 tinham 119 nomes em comum de 119; P3↔P4 tinham ZERO de 114. Toda mídia enviada com
       SUCESSO virava um artigo desaparecido. É a LEI 9 dentro do próprio vigia.

    2. CAUSA CORTADA (os 35) — a classificação "retido" procurava a frase "FICA retido" dentro
       da mensagem, e a mensagem guardava só as 3 primeiras violações. A linha da nota era a
       quarta. Ver `caixa_preta.e_retido`.

    3. O OBSERVADOR (os 6) — o `ensaio_seco.py`, que promete "custo zero, não escreve nada",
       chama `ficha_site.montar()`, que marca P1_FICHA. Cada ensaio meu injetava 119 marcas
       falsas de produção. P1 ficou com 222 marcas para 119 artigos, e artigos que tinham
       chegado ao P2 às 23:49 apareciam parados no P1 — porque a caixa-preta lê a ÚLTIMA marca,
       e as últimas eram minhas.

    ═══ POR QUE ISTO É PIOR QUE UM BUG COMUM ═══
    O plano de voo existe para o Dr. Eduardo poder confiar no que o sistema relata. Um vigia
    que grita "155 sumiram" quando nada sumiu não é inofensivo: gasta a noite dele procurando
    defeito que não existe, e da próxima vez que gritar de verdade ele não vai acreditar.
    """
    import os
    import caixa_preta as CP
    import voo as V

    # ── 1. RETIDO É DECIDIDO PELO NÚMERO ──
    sintomas = ("contexto_tema: ausente: bloco A do ACRI vazio · impacto_conduta: ausente · "
                "gancho_lista: sem gancho")          # a mensagem REAL, sem a linha da nota
    checa("nota 4 sem a frase na mensagem ainda é RETIDO",
          CP.e_retido({"wp": "P2_CONTRATO", "ok": False, "nota": 4, "erro": sintomas}),
          "voltou a depender de achar texto — 35 reprovados viraram 'falha do ACRI' em 10/Ago")
    checa("nota 7 recusado é FALHA, não retenção",
          not CP.e_retido({"wp": "P2_CONTRATO", "ok": False, "nota": 7, "erro": "tema fora da lista"}),
          "um artigo BOM que não subiu está sendo escondido na lista de 'retidos pela régua'")
    checa("DIRETRIZ com nota 4 é FALHA (ela não tem porta — 05/Ago)",
          not CP.e_retido({"wp": "P2_CONTRATO", "ok": False, "nota": 4,
                           "tipo_documento": "diretriz", "erro": sintomas}),
          "a exceção da diretriz vazou: diretriz retida ficaria escondida como 'é a régua'")
    checa("marca de SUCESSO nunca é retenção",
          not CP.e_retido({"wp": "P2_CONTRATO", "ok": True, "nota": 4}),
          "artigo que PASSOU no contrato entrando na lista de retidos")

    # ── 2. SIMULAÇÃO NÃO ESCREVE NO PLANO DE VOO ──
    tam = (lambda: os.path.getsize(V.VOO) if os.path.exists(V.VOO) else 0)
    antes_flag = V.silenciado()
    V.silenciar(True)
    a = tam()
    for i in range(30):
        V.marcar("P1_FICHA", artigo=f"__trava_{i}")
    checa("com voo.silenciar(), 30 marcas não escrevem 1 byte", tam() == a,
          "a simulação voltou a sujar o registro — foi assim que 6 artigos que chegaram ao fim "
          "apareceram parados no P1_FICHA")
    V.silenciar(antes_flag)

    # ── 3. TODO WAYPOINT DE ARTIGO USA A IDENTIDADE DO PACOTE ──
    _src = os.path.dirname(os.path.abspath(__file__))
    txt = open(os.path.join(_src, "publicador.py"), encoding="utf-8").read()
    ruins = [l.strip() for l in txt.splitlines()
             if "_VOO.marcar" in l and ("artigo=objeto" in l or "artigo=os.path.basename(str(local_path" in l)]
    checa("nenhum waypoint marca o artigo com o nome do arquivo do Storage", not ruins,
          "voltou a identidade dupla: " + (ruins[0][:80] if ruins else ""))
    checa("o ensaio_seco silencia o voo antes de simular",
          "silenciar(True)" in open(os.path.join(_src, "ensaio_seco.py"), encoding="utf-8").read(),
          "o ensaio voltou a injetar marcas de produção falsas")
    checa("o administrador silencia o voo antes de ler a ficha",
          "silenciar(True)" in open(os.path.join(_src, "administrador.py"), encoding="utf-8").read(),
          "abrir o painel volta a escrever marcas de produção")


def teste_nenhum_modulo_usado_sem_import():
    """10/Ago — `NameError: name '_VOO' is not defined`, DEZ ARTIGOS SEGUIDOS.

    ═══ O CASO REAL ═══
    Em 09/Ago instrumentei o `publicador.py` com o plano de voo: 8 chamadas a `_VOO.marcar(...)`.
    Esqueci o `import voo as _VOO`. O `ficha_site.py` tinha, o `analisador.py` tinha, o
    `rodar_em_blocos.py` tinha — o publicador não. Disse "testei aqui" e mandei rodar.

    No dia seguinte o Dr. Eduardo clicou a Chave 2 e o primeiro bloco fechou assim:
        ═══ BLOCO 1 fechado · publicados 0 · recusados 0 · falhas neste bloco 10 ═══
    Dez artigos analisados e pagos, publicação recusada em todos.

    ═══ POR QUE NADA PEGOU, E É O PONTO ═══
    `NameError` NÃO existe em tempo de compilação. Tudo isto passa com um módulo assim:
        · `python3 -c "import publicador"`   → passa (o nome só falta quando a LINHA roda)
        · `ast.parse(...)`                    → passa (é sintaxe válida)
        · `python3 -m py_compile`             → passa
        · a bateria inteira                   → passa (ela não toca no publicador, que precisa
                                                do Supabase, e eu não consigo chamar o Supabase)
    Ou seja: TODAS as minhas verificações eram cegas para esta classe de defeito, e a palavra
    "testei aqui" estava tecnicamente certa e praticamente inútil — o publicador não estava
    dentro de "aqui" nenhum.

    ═══ A IRONIA QUE NÃO PODE SE REPETIR ═══
    O defeito estava DENTRO do sistema de vigilância, que existe justamente para achar defeitos.
    A `voo.marcar()` foi escrita para nunca levantar exceção — e essa proteção não vale nada se
    o próprio NOME do módulo não existe: o erro acontece ANTES de entrar na função protegida.
    O instrumento derrubou o voo.

    ═══ O QUE ESTA TRAVA FAZ ═══
    Varre todo .py de `src/` e `scripts/` e procura o padrão exato do estrago: um nome usado
    como `ALGUMACOISA.metodo(...)` que NUNCA é ligado no arquivo — nem import, nem atribuição,
    nem argumento, nem `global`. É de propósito ESTREITO: só acusa acesso a atributo de nome nu,
    que é a forma de "módulo esquecido". Não tenta ser um linter.
    """
    import os
    import ast
    import builtins

    raizes = [os.path.dirname(os.path.abspath(__file__)),
              os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts")]
    # os dunder do módulo não estão em `builtins` mas existem sempre
    embutidos = set(dir(builtins)) | {'__file__', '__name__', '__doc__', '__package__'} | {"__file__", "__name__", "__doc__", "self", "cls"}
    achados = []

    for raiz in raizes:
        if not os.path.isdir(raiz):
            continue
        for nome in sorted(os.listdir(raiz)):
            if not nome.endswith(".py"):
                continue
            caminho = os.path.join(raiz, nome)
            try:
                arvore = ast.parse(open(caminho, encoding="utf-8", errors="ignore").read())
            except Exception:
                continue          # sintaxe quebrada é outro problema, e o compile já pega

            ligados = set()
            for no in ast.walk(arvore):
                if isinstance(no, ast.Import):
                    for a in no.names:
                        ligados.add(a.asname or a.name.split(".")[0])
                elif isinstance(no, ast.ImportFrom):
                    for a in no.names:
                        ligados.add(a.asname or a.name)
                elif isinstance(no, ast.Name) and isinstance(no.ctx, (ast.Store, ast.Del)):
                    ligados.add(no.id)
                elif isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    ligados.add(no.name)
                elif isinstance(no, ast.arg):
                    ligados.add(no.arg)
                elif isinstance(no, ast.Global):
                    ligados.update(no.names)
                elif isinstance(no, ast.ExceptHandler) and no.name:
                    ligados.add(no.name)
                elif isinstance(no, (ast.With, ast.AsyncWith)):
                    for it in no.items:
                        for alvo in ast.walk(it.optional_vars) if it.optional_vars else []:
                            if isinstance(alvo, ast.Name):
                                ligados.add(alvo.id)

            # o padrão do estrago: NOME.atributo(...) com NOME nunca ligado
            for no in ast.walk(arvore):
                if (isinstance(no, ast.Attribute) and isinstance(no.value, ast.Name)
                        and isinstance(no.value.ctx, ast.Load)):
                    alvo = no.value.id
                    if alvo not in ligados and alvo not in embutidos:
                        achados.append(f"{nome}:{no.lineno} → {alvo}.{no.attr}")

    unicos = sorted(set(achados))
    checa("nenhum módulo é usado sem import", not unicos,
          "NameError esperando a hora de acontecer (compila, importa, e quebra no artigo real): "
          + " | ".join(unicos[:5]) + (f" … e mais {len(unicos) - 5}" if len(unicos) > 5 else ""))


def teste_uma_tabela_de_precos():
    """09/Ago — DUAS TABELAS DE PREÇO, E ELAS DISCORDAVAM (LEI 9).

    ═══ O CASO REAL ═══
    Ao responder "quanto custa rodar agosto", achei o preço escrito em DOIS arquivos:

        modelo             prova_extracao.py      prova_classificador.py
        gpt-5.6-terra        1,25 / 10,00            2,00 / 12,00
        gpt-5.6-sol          1,25 / 10,00            5,00 / 25,00
        claude-sonnet-5      3,00 / 15,00            2,00 / 10,00

    A mesma pergunta tinha duas respostas, com 22 % de diferença na conta do mês — e é com essa
    conta que o Dr. Eduardo decide se roda a fila ou se espera. É a LEI 9 inteira: uma regra que
    mora em vários blocos, consertada num só, rodando errado em silêncio no outro.

    ═══ O QUE ESTA TRAVA GUARDA ═══
    1. A tabela vive em `precos.py` e em lugar NENHUM mais.
    2. A conta desconta o cache antes de recobrar — somar input + cache é cobrar duas vezes.
    3. Modelo fora da tabela devolve 0.0 e NÃO levanta exceção: isto roda dentro de log e de
       relatório, e relatório que quebra é pior que relatório aproximado.
    4. Enquanto `CONFERIDO_EM` for None, `aviso()` grita ESTIMATIVA. Um número de dinheiro sem
       aviso vira fato na cabeça de quem lê — foi assim que o meu chute de US$ 0,30 virou a
       base de duas decisões.
    """
    import os
    import re
    import precos as _P

    # 1) a conta bate, e o cache desconta em vez de somar
    cheio = _P.custo("gpt-5.6-terra", entrada=1_000_000, saida=0)
    checa("1M de input no terra custa o preço de tabela", abs(cheio - 1.25) < 1e-9,
          f"deu {cheio} — esperado 1,25")
    meio = _P.custo("gpt-5.6-terra", entrada=1_000_000, saida=0, cache_leitura=1_000_000)
    checa("input TODO vindo do cache custa 10%", abs(meio - 0.125) < 1e-9,
          f"deu {meio} — se der 1,375 é porque somou input + cache, cobrando o token duas vezes")
    checa("Batch corta pela metade",
          abs(_P.custo("gpt-5.6-terra", entrada=1_000_000, saida=0, batch=True) - 0.625) < 1e-9,
          "o desconto de lote não está sendo aplicado")

    # 2) modelo desconhecido não pode derrubar relatório
    # O try/except é a própria coisa testada: se `custo()` levantar, a exceção subiria daqui e
    # MATARIA a bateria inteira — as outras 57 travas nem apareceriam na tela. Foi o que a
    # sabotagem 3 de 09/Ago mostrou: "💥 CRASHOU (não é reprova!)". Crash é pior que reprova,
    # porque reprova diz o que está errado e crash esconde tudo o que estava certo.
    try:
        _v = _P.custo("modelo-que-nao-existe", entrada=9999, saida=9999)
        _erro = None
    except Exception as e:
        _v, _erro = None, f"{type(e).__name__}: {e}"
    checa("modelo fora da tabela devolve 0.0 sem explodir", _v == 0.0,
          f"levantou {_erro}" if _erro else f"devolveu {_v!r} — isto roda dentro de log e de relatório")

    # 3) o aviso de estimativa existe enquanto ninguém conferiu a fatura
    if _P.CONFERIDO_EM is None:
        checa("sem fatura conferida, o aviso diz ESTIMATIVA", "ESTIMATIVA" in _P.aviso(),
              "a tabela nunca foi conferida e o relatório não avisa — vira fato na cabeça de quem lê")

    # 4) VARREDURA: ninguém pode ter escrito uma segunda tabela por fora
    _src = os.path.dirname(os.path.abspath(__file__))
    padrao = re.compile(r"\(\s*\d+\.\d+\s*,\s*\d+\.\d+\s*\)")   # o formato (entrada, saída)
    reincidentes = []
    for nome in sorted(os.listdir(_src)):
        if not nome.endswith(".py") or nome in ("precos.py", "teste_motor.py"):
            continue
        try:
            txt = open(os.path.join(_src, nome), encoding="utf-8", errors="ignore").read()
        except Exception:
            continue
        for linha in txt.splitlines():
            if linha.lstrip().startswith("#"):
                continue
            # uma tabela de preço = nome de modelo + par de floats na MESMA linha
            if padrao.search(linha) and re.search(r"(claude-|gpt-5|gemini-|grok-)", linha):
                reincidentes.append(f"{nome}: {linha.strip()[:70]}")
    checa("a tabela de preços mora só em precos.py", not reincidentes,
          "voltou a existir preço fora do precos.py — " + " | ".join(reincidentes[:3]))


def teste_doi_sintetico_para_quem_nao_tem():
    """06/Ago — A COLUNA `doi` É NOT NULL, E O NICE NÃO TEM DOI.

    ═══ O CASO REAL ═══
    Na rodada das diretrizes, a linha do NICE (NG136) foi recusada pelo Postgres:
        Supabase 400 {"code":"23502"} — Failing row contains (uuid, null, hypertension-in-adults…)
    A segunda coluna é `doi`, e ela é NOT NULL. O publicador já sabia conviver sem DOI na hora de
    resolver o conflito ("sem DOI cai no doc_id"), mas a linha nem chegava a entrar.

    Nem todo documento tem DOI, e isso não é defeito do dado: o NICE publica por código próprio.
    Medido: 2 de 131 pacotes sem DOI — os dois, NICE.

    ═══ A DECISÃO DELE (opção A, com o prefixo que ELE escolheu) ═══
    Gravar um identificador sintético com o prefixo **`Sintetico_`**. O prefixo é o ponto: quem
    olhar a coluna vê na hora que não é DOI de verdade e não vai tentar resolver no doi.org.
    Era a minha única objeção à opção A, e o prefixo dele a resolve.
    """
    import ficha_site as _F
    # sem DOI → sintético COM o prefixo
    d = _F._doi_ou_sintetico("", "hypertension-in-adults-ng136")
    checa("sem DOI gera sintético", bool(d), "voltou vazio — o Postgres recusa a linha (23502)")
    checa("o sintético usa o prefixo 'Sintetico_'", str(d).startswith("Sintetico_"),
          f"veio {d!r} — sem o prefixo, alguém vai achar que é DOI de verdade")
    checa("e é derivado do doc_id (único)", "hypertension-in-adults-ng136" in str(d), f"veio {d!r}")

    # 'n/a' é ausência disfarçada — o extrator escreve isso
    checa("'n/a' também vira sintético",
          str(_F._doi_ou_sintetico("n/a", "x-y")).startswith("Sintetico_"))

    # COM DOI → o DOI de verdade, intocado. Um sintético por cima de DOI real seria bem pior.
    real = "10.1161/CIR.0000000000001440"
    checa("com DOI real, nada muda", _F._doi_ou_sintetico(real, "qualquer") == real,
          "o sintético atropelou um DOI verdadeiro")
    checa("DOI real não ganha prefixo",
          not _F._doi_ou_sintetico(real, "qualquer").startswith("Sintetico_"))


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

    # ═══════════════════════════════════════════════════════════════════════════════════
    # ⚠️ 22/Ago/2026 — O QUE ESTAVA ESCRITO AQUI FOI REVOGADO, E VALE SABER O QUÊ.
    #
    # Este bloco afirmava: *"ABAIXO de 9 o desconto continua inteiro: a regra de 05/Ago não
    # virou letra morta"*, e testava exatamente `{**base, "open_label": True}` — que é o
    # EXCEL: teto 8 por não dar para cegar, rigor 9, patrocínio Abbott. A trava exigia que o
    # desconto derrubasse 8 → 7.
    #
    # Ele, lendo a nota do EXCEL: *"não tem como o EXCEL — estudo que muda a cardiologia —
    # não estar com nota 9... ou eu tô muito doido"*, e depois: *"como um estudo que avalia
    # uma galera que racha o peito e no outro braço coloca stent poderia ser cego?"*
    #
    # Eu propus tirar o teto de open-label. **Estava errado** — o gabarito dele de 11/Ago já
    # dizia EXCEL 8, NOBLE 7, ISAR-REACT 5 7, todos open-label. O teto 8 é a calibração dele.
    # O que faltava era outra coisa: o desconto de indústria descia inteiro logo abaixo do
    # piso 9, e levava o 8 dele para 7.
    #
    # A DECISÃO (dele, 22/Ago, com a revogação declarada): **rigor ≥9 → o desconto de
    # independência não rebaixa; vira ressalva declarada.** É a mesma frase de 06/Ago
    # (*"financiamento é ressalva declarada, não rebaixamento de categoria"*) — que nunca foi
    # limitada ao 9; fui eu que a implementei só ali.
    #
    # O QUE **NÃO** FOI REVOGADO: patrocinado E mal feito continua levando o desconto inteiro.
    # O que passou a mandar é o RIGOR, não a altura da nota. Medido antes de valer: mesmo
    # `fatos`, motor de ontem contra o de hoje, 1011 artigos — **22 mudam, todos 7→8, nenhum
    # desce**. Gabarito dos 7 fixtures: 7/7 continuam batendo.
    # ═══════════════════════════════════════════════════════════════════════════════════
    b8 = {**base, "open_label": True}          # open-label → teto 8, rigor 9 (o caso do EXCEL)
    s_lim = N.score({**b8, "financiamento_papel": "público"})
    s_pag = N.score({**b8, "financiamento_papel": "indústria envolvida"})
    checa("EXCEL: rigor 9 protege — indústria NÃO derruba o 8 para 7",
          s_pag["aplic"] == s_lim["aplic"] == 8,
          f"público={s_lim['aplic']} vs indústria={s_pag['aplic']}")

    # ── e o que sobra da regra de 05/Ago: RIGOR ABAIXO DE 9 leva o desconto inteiro ──
    # Sem isto a revogação viraria "indústria não pesa nunca", que NÃO foi o que ele decidiu.
    b8f = {**b8, "itt_falso": True, "base_qualidade": 7}     # mesmo teto 8, rigor derrubado
    f_lim = N.score({**b8f, "financiamento_papel": "público"})
    f_pag = N.score({**b8f, "financiamento_papel": "indústria envolvida"})
    checa("mas rigor <9 continua descontando inteiro (patrocinado E mal feito)",
          f_pag["aplic"] < f_lim["aplic"],
          f"rigor {f_pag['trabalho']} · público={f_lim['aplic']} vs indústria={f_pag['aplic']}"
          " — a revogação virou anistia geral")


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

def teste_o_nulo_conclusivo_vale_como_resposta():
    """19/Ago — O DINAMIT tirou 5, e o Dr. Eduardo leu o artigo inteiro para me explicar por quê.

    ═══ O QUE ELE DISSE (a régua, nas palavras dele) ═══
      *"O estudo apresentou nitidamente qual seria o tamanho da amostra necessária, randomizou
       e ALCANÇOU o tamanho da amostra pra responder a pergunta. Não adianta colocar CDI
       profilático em paciente pós-infarto na fase aguda. O fato de não mostrar benefício não
       significa que não impacta a prática clínica — por isso que é nota para APLICABILIDADE
       clínica. Me interessa saber se eu tenho que prescrever, se tenho que brigar com a
       operadora de saúde, ou se eu posso falar pro paciente: 'cara, desencana, tão te
       colocando na cabeça que isso vai te ajudar e não vai'."*

    Ou seja: **quem autoriza o crédito do nulo não é a largura do IC — é o ensaio ter sido
    desenhado com poder para a pergunta e ter ENTREGUE o que planejou.** "Não faça" é uma
    conduta, e mudar para "não faça" é mudar conduta.

    ═══ QUATRO CIRCULARIDADES DERRUBAVAM O MESMO ARTIGO ═══
    O DINAMIT levava 5, e cada degrau era o motor punindo o estudo pelo próprio achado:
      1. `taxa observada <70% da esperada` — a mortalidade veio MENOR que a prevista, e os
         investigadores recalcularam a amostra de 525 para 674 e entregaram os 674. O motor
         tinha `poder_ok: true` e `eventos_nao_alcancados: false` no MESMO JSON e ouviu
         `taxa_obs`. Mérito lido como falha.
      2. `open-label → teto desenho 8` — não se cega implante de CDI, e o desfecho é MORTE POR
         TODAS AS CAUSAS com adjudicação externa. Nas palavras dele: *"quantificar a presença
         ou não de morte é relativamente fácil — o endpoint é muito franco e muito pouco
         plausível de ser distorcido."*
      3. `MCID conferido → teto 6: o efeito NÃO excede o limiar` — é o ACHADO. Pedir que o
         ensaio negativo prove um benefício para ter direito de dizer que não há benefício.
      4. `o benefício NÃO supera o risco → teto 8` — idem: é a notícia, não o defeito.

    Esta trava confere a régua DELE ponta a ponta, no DINAMIT real (fatos de 19/Ago).
    """
    dinamit = _bom(pergunta="intervencao", desenho="rct",
                   open_label=True, poder_ok=True, desfecho_duro=True, extrapolavel=True,
                   eventos_nao_alcancados=False, eventos_min_grupo=58,
                   taxa_obs=0.069, taxa_esp=0.30,          # ← a premissa que envelheceu
                   beneficio_supera_risco=False,           # ← o CDI não ajudou: é o achado
                   itt_falso=False, falhas_fatais=[],
                   financiamento_papel="indústria envolvida",
                   qualidade_nhlbi={"instrumento": "controlled_intervention",
                                    "avaliadores_desfecho_cegados": True},
                   relevancia_clinica={"classificacao": "incerto",
                                       "desfecho_primario": "Mortalidade por todas as causas",
                                       "tipo_desfecho": "tempo_ate_evento",
                                       "efeito_excede_limiar": False,
                                       "ic_sustenta_relevancia": False,
                                       "ic_exclui_beneficio_relevante": False})
    r = N.score(dinamit)
    checa("DINAMIT: o nulo conclusivo vale 9 ou 10", r["aplic"] >= 9, f"veio {r['aplic']}")
    checa("DINAMIT: e a bicondicional acompanha — MUDA CONDUTA",
          r["muda_conduta"] == "SIM", f"veio {r['muda_conduta']}")
    checa("DINAMIT: o poder recomposto NÃO é demérito",
          not any("taxa observada" in f for f in r["flags"]), " | ".join(r["flags"]))
    checa("DINAMIT: open-label não capa quando o desfecho é morte por todas as causas",
          r["teto_desenho"] == 10, f"teto_desenho {r['teto_desenho']}")
    checa("DINAMIT: o nulo não é punido pelo limiar que ele mesmo não cruzou",
          r["teto_mcid"] == 10, f"teto_mcid {r['teto_mcid']}")

    # ── O CONTROLE, e ele é o que impede a régua de virar peneira ──
    # Ensaio que NÃO entregou o que planejou continua sendo inconclusivo, e continua em 7.
    fraco = dict(dinamit); fraco["poder_ok"] = False
    checa("mas o ensaio SEM poder continua inconclusivo (teto 7)",
          N.score(fraco)["aplic"] <= 7, f"veio {N.score(fraco)['aplic']}")
    sem_eventos = dict(dinamit); sem_eventos["eventos_nao_alcancados"] = True
    checa("e o que NÃO alcançou os eventos também", N.score(sem_eventos)["aplic"] <= 7,
          f"veio {N.score(sem_eventos)['aplic']}")
    mole = dict(dinamit)
    mole["relevancia_clinica"] = dict(dinamit["relevancia_clinica"],
                                      desfecho_primario="Morte cardiovascular ou hospitalização por IC")
    checa("open-label VOLTA a capar quando o desfecho é composto/julgado",
          N.score(mole)["teto_desenho"] == 8, f"teto {N.score(mole)['teto_desenho']}")
    return "nulo com poder e N entregues = resposta · sem eles, continua inconclusivo"


def teste_as_duas_gemeas_dano_e_nao_inferioridade():
    """19/Ago — APPRAISE-2 e VALIANT reprovaram por FALTA DE PALAVRA, não por régua.

    · APPRAISE-2: eficácia nula E sangramento maior HR 2,59 (1,50–4,46), p=0,001 — ensaio
      INTERROMPIDO por dano. O motor chamou de `incerto` e deu 5. Dano demonstrado é resposta
      conclusiva: o ensaio tirou a droga da prática.
    · VALIANT: atingiu NÃO-INFERIORIDADE vs captopril. Provou o que propôs, e o motor não
      tinha a palavra.

    As duas são gêmeas da `ausencia_de_efeito_demonstrada` de 04/Ago — mesmo denominador:
    **o ensaio respondeu à pergunta que fez.**
    """
    for classe in ("dano_demonstrado", "nao_inferioridade_demonstrada"):
        checa(f"'{classe}' existe no motor", classe in N.TETO_MCID, "categoria não criada")
        checa(f"'{classe}' não tem teto de relevância", N.TETO_MCID.get(classe) == 10,
              f"veio {N.TETO_MCID.get(classe)}")
        r = N.score(_bom(pergunta="intervencao", desenho="rct", efeito_grande=True,
                         relevancia_clinica={"classificacao": classe,
                                             "desfecho_primario": "mortalidade por todas as causas"}))
        checa(f"'{classe}' chega a 9/10", r["aplic"] >= 9, f"veio {r['aplic']}")
        checa(f"'{classe}' DIZ o porquê de não ter teto (o redator precisa da frase)",
              any("SEM teto" in f for f in r["flags"]), " | ".join(r["flags"]))

    # a palavra tem de existir nos DOIS extratores, senão o motor espera algo que nunca chega
    import os as _os
    aqui = _os.path.dirname(_os.path.abspath(__file__))
    for arq in ("analise.py", "analise_prompt.md", "analise_meta_prompt.md"):
        t = open(_os.path.join(aqui, arq), encoding="utf-8").read()
        for classe in ("dano_demonstrado", "nao_inferioridade_demonstrada"):
            checa(f"{arq} conhece '{classe}'", classe in t,
                  "o motor tem a categoria e o extrator não pode escrevê-la")
    return "dano e não-inferioridade demonstrados valem como resposta, e o extrator sabe dizê-los"


def teste_independencia_nao_cruza_o_portao_da_publicacao():
    """19/Ago — Eu consertei UMA fronteira em 06/Ago e deixei a outra. LEI 9.

    Dos 27 marcos da IC reprovados, **QUINZE estavam exatamente em 5**, com o mesmo delator
    final: `independência editorial −1.0`. Sem ele, 6 — e 6 publica. CARE-HF, MIRACLE,
    I-PRESERVE, COMMANDER-HF, OPTIMAAL, DINAMIT, CAT, STEP-HFpEF.

    O argumento de 06/Ago — *"financiamento é ressalva declarada, não rebaixamento de
    categoria"* — vale igual aqui e vale MAIS: no 9 o desconto trocava a frase que acompanha o
    artigo; no 6 ele decide se o artigo EXISTE para o assinante. E a premissa é a mesma que já
    estava escrita: **quase todo ensaio de fase 3 em cardiologia é patrocinado.** Um desconto
    que quase todos levam não separa ninguém — só encolhe o acervo.
    """
    checa("o piso da publicação é o MESMO número do portão (LEI 10, nota ≥6)",
          N.PISO_PUBLICACAO == 6, f"veio {N.PISO_PUBLICACAO}")

    base = dict(pergunta="intervencao", desenho="rct", open_label=False, poder_ok=True,
                desfecho_duro=True, extrapolavel=True, efeito_grande=False,
                financiamento_papel="indústria envolvida")

    # ── EM CIMA DA FRONTEIRA: teto 6, desconto levaria a 5 → tem de parar em 6 ──
    # É o caso dos quinze. `significativo_mas_abaixo_do_mcid` capa em 6 pela tabela do MCID.
    na_fronteira = dict(base, relevancia_clinica={
        "classificacao": "significativo_mas_abaixo_do_mcid",
        "desfecho_primario": "desfecho composto"})
    r = N.score(na_fronteira)
    checa("indústria NÃO derruba um 6 para 5 (fronteira da publicação)",
          r["aplic"] >= N.PISO_PUBLICACAO, f"veio {r['aplic']}")
    checa("e o delator DIZ que o desconto foi contido, e em qual fronteira",
          any("piso" in f and "publicação" in f for f in r["flags"]), " | ".join(r["flags"]))

    # ── O CONTROLE: o desconto NÃO pode virar "indústria não pesa nunca" ──
    #
    # ⚠️ 22/Ago — ESTE BLOCO AFIRMAVA *"entre as fronteiras (8→7) o desconto vale integral"*,
    # e foi REVOGADO por decisão dele no mesmo dia: o que protege o artigo passou a ser o
    # RIGOR ≥9, em qualquer altura da escala — não a nota ter chegado a 9. O caso que forçou a
    # revisão foi o EXCEL (teto 8 porque não dá para cegar esternotomia contra stent, rigor 9,
    # patrocínio Abbott): a regra velha o mandava para 7, e o gabarito dele diz 8.
    #
    # O CONTROLE CONTINUA EXISTINDO — mudou só o critério. Aqui o rigor é derrubado de
    # propósito (ITT falso), e aí sim o desconto tem de levar 8 → 7, sem piso no meio.
    # Sem esta metade, "financiamento é ressalva" viraria "financiamento não importa", que é o
    # oposto do que ele pediu em 05/Ago e que continua valendo para quem NÃO provou o método.
    # ⚠️ a 1ª versão desta checagem fixava `== 7`, e o fixture derrubou o rigor para 7 — o que
    # já leva a nota a 7 ANTES do desconto, que então desce para 6. O desconto tinha aplicado
    # certinho; errada era a asserção, que media o NÚMERO em vez do EFEITO. Trava que crava
    # número quebra quando outra regra mexe na conta, e manda procurar defeito onde não há.
    entre = dict(base, itt_falso=True, base_qualidade=7,
                 relevancia_clinica={"classificacao": "nao_avaliavel",
                                     "desfecho_primario": "desfecho composto"})
    e_lim = N.score({**entre, "financiamento_papel": "público"})
    e_pag = N.score(entre)
    checa("rigor <9: o desconto de indústria continua descontando",
          e_pag["aplic"] < e_lim["aplic"],
          f"rigor {e_pag['trabalho']} · público={e_lim['aplic']} vs indústria={e_pag['aplic']}"
          " — o desconto sumiu para todo mundo")
    return "o desconto não cruza 9 nem 6, e rigor ≥9 o transforma em ressalva declarada"


def teste_f8_so_e_fatal_se_a_troca_foi_silenciosa():
    """19/Ago — decisão do Dr. Eduardo. A F8 zerou 7 dos 100 marcos da IC para nota 3.

    Entre eles SOLOIST-WHF e SCORED, onde a troca do desfecho foi ANUNCIADA pelos autores com
    justificativa: o patrocinador cortou o financiamento e os ensaios encerraram cedo. Está
    escrito no artigo. A fraude que a F8 existe para pegar é o outcome switching SILENCIOSO —
    trocar depois de olhar os dados e não contar. Transparência não pode custar nota 3.
    """
    silencioso = _bom(pergunta="intervencao", desenho="rct", efeito_grande=True,
                      qualidade_nhlbi={"instrumento": "controlled_intervention",
                                       "desfechos_prespecificados": False})
    checa("troca SILENCIOSA continua sendo falha fatal",
          "F8" in N.falhas_fatais(silencioso), str(N.falhas_fatais(silencioso)))
    checa("e derruba a nota para ≤4", N.score(silencioso)["aplic"] <= 4,
          f"veio {N.score(silencioso)['aplic']}")

    declarado = _bom(pergunta="intervencao", desenho="rct", efeito_grande=True,
                     qualidade_nhlbi={"instrumento": "controlled_intervention",
                                      "desfechos_prespecificados": False,
                                      "troca_desfecho_declarada": True})
    checa("troca DECLARADA e justificada não é falha fatal",
          "F8" not in N.falhas_fatais(declarado), str(N.falhas_fatais(declarado)))

    # o extrator precisa poder responder — motor com a regra e prompt calado = campo null p/ sempre
    import os as _os
    aqui = _os.path.dirname(_os.path.abspath(__file__))
    for arq in ("analise.py", "analise_prompt.md"):
        checa(f"{arq} pergunta se a troca foi declarada",
              "troca_desfecho_declarada" in open(_os.path.join(aqui, arq), encoding="utf-8").read(),
              "o motor lê um campo que ninguém preenche — vale como 'não declarou' para sempre")
    return "F8 pega o switching silencioso, não a transparência"


def teste_nenhum_nome_e_usado_antes_de_existir():
    """21/Ago — 32 artigos falharam na publicação por um nome no escopo errado.

        NameError: name 'NAO_SE_APLICA' is not defined      × 32, na hora de publicar

    `NAO_SE_APLICA` era variável LOCAL do `montar()`. Quando escrevi `_decidir_tema` — outra
    função, acima dela — usei o nome achando que era constante de módulo. **Compilou.** O
    `py_compile` não olha escopo, meu teste de fumaça pegou um ramo que retorna antes, e a
    bateria roda em modo offline, que também retorna antes. Passou por três checagens e quebrou
    na quarta, que era a produção dele.

    ═══ É A TERCEIRA VEZ, E SEMPRE A MESMA FORMA ═══
        10/Ago  `_VOO` usado antes do import — custou 10 artigos PAGOS
        11/Ago  `re as _re` importado na linha 256, usado na 173 (administrador)
        21/Ago  `NAO_SE_APLICA` local usada por outra função — 32 artigos
    Nome definido depois de onde é usado compila sempre e quebra sempre — e só na hora que o
    caminho é percorrido de verdade, que costuma ser em produção, com dinheiro na mesa.

    Esta trava varre por `ast` os módulos da corrente e reprova QUALQUER nome global usado numa
    função que não exista no módulo. Não depende de o caminho ser exercitado.
    """
    import ast
    import builtins
    import os as _os
    aqui = _os.path.dirname(_os.path.abspath(__file__))
    MODULOS = ("ficha_site.py", "contrato.py", "publicador.py", "analisador.py",
               "analise.py", "notas_prototipo.py", "tema_mesh.py", "tema_llm.py",
               "administrador.py", "classificador_ouro.py", "ocr_pdf.py",
               "card_acri.py")   # 22/Ago: 16 cards falharam e ele não estava na lista
    # os dunder do módulo não estão em `builtins` mas existem sempre
    embutidos = set(dir(builtins)) | {'__file__', '__name__', '__doc__', '__package__'}

    for arq in MODULOS:
        caminho = _os.path.join(aqui, arq)
        if not _os.path.exists(caminho):
            continue
        arvore = ast.parse(open(caminho, encoding="utf-8").read())

        # tudo que o MÓDULO define no topo: funções, classes, atribuições, imports
        no_topo = set()
        for n in arvore.body:
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                no_topo.add(n.name)
            elif isinstance(n, (ast.Import, ast.ImportFrom)):
                for a in n.names:
                    no_topo.add((a.asname or a.name).split(".")[0])
            elif isinstance(n, ast.Assign):
                # ⚠️ `for t in n.targets: if isinstance(t, ast.Name)` NÃO pega
                # `MIN_FRASE, MAX_FRASE = 60, 150` — o alvo ali é um Tuple, não um Name.
                # Achado em 22/Ago no card_acri.py: a trava acusaria duas constantes que
                # existem. `ast.walk` no alvo resolve tupla, lista e aninhamento.
                for t in n.targets:
                    for sub in ast.walk(t):
                        if isinstance(sub, ast.Name):
                            no_topo.add(sub.id)
            elif isinstance(n, (ast.If, ast.Try, ast.For, ast.While, ast.With)):
                for sub in ast.walk(n):        # nomes criados dentro de if/try do topo valem
                    if isinstance(sub, ast.Assign):
                        for t in sub.targets:
                            for s2 in ast.walk(t):
                                if isinstance(s2, ast.Name):
                                    no_topo.add(s2.id)
                    elif isinstance(sub, (ast.Import, ast.ImportFrom)):
                        for a in sub.names:
                            no_topo.add((a.asname or a.name).split(".")[0])
                    elif isinstance(sub, (ast.FunctionDef, ast.ClassDef)):
                        no_topo.add(sub.name)

        for fn in [n for n in arvore.body
                   if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]:
            # o que a função cria localmente: parâmetros, atribuições, imports, laços, with, except
            # ⚠️ OS PARÂMETROS DAS FUNÇÕES ANINHADAS CONTAM. A primeira versão desta trava só
            # pegava os args da função de fora, e `ast.walk` desce nas internas — então `pat`,
            # `de_onde`, `valor` e `s` (parâmetros de closures) apareciam como "nome que não
            # existe". 22 falsos positivos, e eu quase reportei defeito onde não havia.
            # Trava que grita sem motivo é pior que trava que falta: ensina a ignorar o vermelho.
            local = set()
            for f2 in [fn] + [x for x in ast.walk(fn)
                              if isinstance(x, (ast.FunctionDef, ast.AsyncFunctionDef,
                                                ast.Lambda)) and x is not fn]:
                a2 = f2.args
                local.update(a.arg for a in a2.args + a2.kwonlyargs + a2.posonlyargs)
                if a2.vararg:
                    local.add(a2.vararg.arg)
                if a2.kwarg:
                    local.add(a2.kwarg.arg)
            usados = []
            for n in ast.walk(fn):
                if isinstance(n, ast.Assign):
                    for t in n.targets:
                        for sub in ast.walk(t):
                            if isinstance(sub, ast.Name):
                                local.add(sub.id)
                elif isinstance(n, (ast.AugAssign, ast.AnnAssign, ast.NamedExpr)):
                    if isinstance(n.target, ast.Name):
                        local.add(n.target.id)
                elif isinstance(n, (ast.Import, ast.ImportFrom)):
                    for a in n.names:
                        local.add((a.asname or a.name).split(".")[0])
                elif isinstance(n, (ast.For, ast.AsyncFor, ast.comprehension)):
                    alvo = n.target
                    for sub in ast.walk(alvo):
                        if isinstance(sub, ast.Name):
                            local.add(sub.id)
                elif isinstance(n, ast.ExceptHandler) and n.name:
                    local.add(n.name)
                elif isinstance(n, ast.withitem) and n.optional_vars is not None:
                    for sub in ast.walk(n.optional_vars):
                        if isinstance(sub, ast.Name):
                            local.add(sub.id)
                elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    local.add(n.name)
                elif isinstance(n, ast.Global):
                    local.update(n.names)
                elif isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load):
                    usados.append((n.id, n.lineno))

            for nome, linha in usados:
                if nome in local or nome in no_topo or nome in embutidos:
                    continue
                checa(f"{arq}:{linha} · {fn.name}() usa '{nome}', que não existe no módulo",
                      False,
                      "nome definido depois de onde é usado — compila e quebra em produção")
    return "nenhum nome usado antes de existir (a família do _VOO, do _re e do NAO_SE_APLICA)"


def teste_sem_tema_nao_sobe_e_ninguem_mais_escreve():
    """20/Ago — 117 de 616 linhas com `tema` NULL, e o portão não sabia que a coluna existia.

    ═══ O QUE ACONTECEU ═══
    Ele abriu o Supabase e viu a coluna vazia: *"e aí todos os nossos portões e nossas regras —
    mais uma vez indo para o espaço. Por que diachos o Supabase está cheio de buraco?"*

    Medido antes de responder qualquer coisa:
        até 17/Ago .... 21 sem tema em 507
        18/Ago ........ 18 em 26
        19/Ago ........ 78 em 83
    O buraco começa no dia seguinte ao que eu rodei o `marcar_temas.py` — e a causa não é o
    portão falhando: **é a máquina de temas nunca ter estado no caminho dele.** Eu construí o
    classificador em 17/Ago, rodei UMA vez por um script que dá PATCH direto em `artigos`
    (segundo portão, LEI 5 violada por mim) e dei por resolvido.

    ═══ AS DECISÕES DELE QUE ESTA TRAVA GUARDA ═══
    · *"sem tema não sobe"* — vira porta no contrato.
    · *"não tem cabimento uma diretriz subir sem tema"* — UMA regra para os quatro tipos. Eu
      tinha proposto exceção para diretriz invocando a LEI 10, e misturei duas coisas: aquela
      exceção é sobre a NOTA, não sobre o tema.
    · *"inadmissível não ter tema — então não é cardiologia e medicina, estamos falando do
      cosmo"* — por isso `nao_classificavel` NÃO existe; quem decide é o tripé, e quando ele
      não fecha a resposta é `fora_do_escopo`.
    · NULL nunca (LEI 11): `Sem tema` e `Não se aplica` são TEXTO que se lê e se entende.
    """
    import ast
    import os as _os
    import temas as _T
    aqui = _os.path.dirname(_os.path.abspath(__file__))

    # ── 1) o portão CONHECE as 4 colunas (era isto que faltava: coluna fora da lista = coluna cega)
    contrato = open(_os.path.join(aqui, "contrato.py"), encoding="utf-8").read()
    publicador = open(_os.path.join(aqui, "publicador.py"), encoding="utf-8").read()
    for col in ("tema", "tema_secundario", "tema_origem", "mesh_terms"):
        checa(f"contrato conhece a coluna {col}", f'"{col}"' in contrato, "coluna cega")
        checa(f"publicador conhece a coluna {col}", f'"{col}"' in publicador, "coluna cega")

    # ── 2) SEM TEMA NÃO SOBE, e a diretriz não é exceção ──
    import contrato as C
    # ⚠️ 22/Ago — este fixture nasceu com `"mesh_terms": []`, e era a trava CONSAGRANDO o buraco:
    # enquanto ela dizia que `[]` era uma ficha legítima, o contrato tinha licença para deixar
    # 208 de 704 linhas subirem vazias. Fixture é regra escrita em outro lugar (LEI 9).
    base = {"doc_id": "x", "doi": "10.1/x", "titulo": "T", "revista": "R",
            "tema_secundario": "Não se aplica",
            "mesh_terms": ["Heart Failure"], "mesh_origem": "pubmed"}
    for tipo in ("original", "meta", "diretriz", "revisao_narrativa"):
        f = dict(base, tipo_documento=tipo, tema=_T.SEM_TEMA, tema_origem="fora_do_escopo")
        v = C.validar(f, checar_arquivos=False)
        checa(f"'{_T.SEM_TEMA}' RETÉM a linha ({tipo})",
              any("tema" in str(x) for x in v), f"passou: {v}")
    f = dict(base, tipo_documento="diretriz", tema="Arritmias/Anticoagulantes", tema_origem="llm")
    v = C.validar(f, checar_arquivos=False)
    checa("mas a diretriz COM tema não é barrada pelo tema",
          not any("tema:" in str(x) for x in v), str(v))

    # ── 3) o vazio tem nome (LEI 11): as duas origens NÃO podem virar a mesma palavra ──
    checa("'fora_do_escopo' e 'falha_do_classificador' são distinguíveis",
          "fora_do_escopo" in contrato and "falha_do_classificador" in contrato,
          "'não é cardiologia' e 'o programa quebrou' pedem consertos opostos")

    # ── 4) NINGUÉM MAIS ESCREVE (LEI 5) ──
    mt = _os.path.join(_os.path.dirname(aqui), "scripts", "marcar_temas.py")
    if _os.path.exists(mt):
        arv = ast.parse(open(mt, encoding="utf-8").read())
        gravar = next((n for n in ast.walk(arv)
                       if isinstance(n, ast.FunctionDef) and n.name == "gravar"), None)
        checa("marcar_temas.gravar existe para poder ser recusada", gravar is not None, "")
        if gravar:
            corpo = gravar.body
            i0 = 1 if (corpo and isinstance(corpo[0], ast.Expr)
                       and isinstance(corpo[0].value, ast.Constant)) else 0
            checa("marcar_temas.gravar RECUSA antes de qualquer PATCH (segundo portão fechado)",
                  bool(corpo[i0:]) and isinstance(corpo[i0], ast.Raise),
                  "o PATCH direto em `artigos` voltou — é a LEI 5 outra vez")
    return "sem tema não sobe (nem diretriz) · e só o publicador escreve"


def teste_mudar_a_regua_nao_manda_re_extrair():
    """19/Ago — ajustar a régua custava uma rodada COMPLETA de extração. À toa.

    Hoje a régua mudou quatro vezes. Cada mudança altera o hash do `notas_prototipo.py`, e a
    TERRA ARRASADA apagava o pacote inteiro **incluindo os FATOS**. Na tela dele, 20 vezes:

        🔥 TERRA ARRASADA — 1 prompt(s) mudaram
           · motor: notas_prototipo.py@eed35fef → @22944c66

    Com 279 pacotes em disco, isso é **uma rodada completa paga a cada ajuste de regra** — e ele
    já disse, com todas as letras: *"eu não tenho dinheiro para você ficar rasgando por conta de
    erros infantis."*

    **Os FATOS não dependem do motor.** O extrator lê o PDF e escreve o que o artigo diz; o motor
    recalcula a nota do zero, deterministicamente, toda vez. Mudar o motor não torna um fato
    falso — torna a NOTA diferente. Quem envelhece é a perícia, o ACRI e o áudio, que citam a
    nota em prosa.

    A ordem de 04/Ago (*"apaga TUDO"*) continua INTACTA onde foi dada: no prompt de EXTRAÇÃO.
    O erro era aplicar a mesma pena a um carimbo que não toca em fato nenhum.

    ⚠️ Esta trava confere as DUAS metades. Só a primeira faria "nunca arrasa", que é pior que o
    defeito original — seria o reaproveitamento que preserva o erro, contra o qual a terra
    arrasada foi criada.
    """
    import ast
    import os as _os
    fonte = open(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "analisador.py"),
                 encoding="utf-8").read()
    arvore = ast.parse(fonte)

    # 1) existe a lista dos carimbos que AINDA arrasam, e o motor NÃO está nela
    carimbos = None
    for n in ast.walk(arvore):
        if isinstance(n, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "_CARIMBOS_DE_EXTRACAO" for t in n.targets):
            carimbos = {e.value for e in n.value.elts if isinstance(e, ast.Constant)}
    checa("existe a lista dos carimbos que arrasam", carimbos is not None, "sumiu")
    if carimbos:
        checa("o EXTRATOR continua arrasando o pacote (ordem de 04/Ago, intacta)",
              "extrator" in carimbos and "extracao" in carimbos, str(sorted(carimbos)))
        checa("o MOTOR não arrasa — mudar a régua não re-extrai",
              "motor" not in carimbos, "o motor voltou para a lista: cada ajuste de régua "
                                       "vira uma rodada de extração paga")

    # 2) a metade que impede virar peneira: sem carimbo nenhum, arrasa igual
    checa("staging SEM carimbo continua sendo arrasado (origem desconhecida)",
          "(not _vold)" in fonte,
          "pacote anterior a 04/Ago passaria a ser reaproveitado às cegas")

    # 3) e o caminho brando não pode deixar para trás justamente o que cita a nota
    so_nota = None
    for n in ast.walk(arvore):
        if isinstance(n, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "_SO_A_NOTA" for t in n.targets):
            so_nota = {e.value for e in n.value.elts if isinstance(e, ast.Constant)}
    checa("a limpeza branda existe", so_nota is not None, "sumiu")
    if so_nota:
        for peca in ("_ACRI.txt", "_analise.md", "_analise.pdf", "_CANONICO.md",
                     "_audio.mp3", "_visual.png"):
            checa(f"a limpeza branda apaga {peca} (ele CITA a nota em prosa)",
                  peca in so_nota, str(sorted(so_nota)))
        checa("e NÃO apaga os fatos — é o que esta regra existe para preservar",
              not any("fatos" in x for x in so_nota), str(sorted(so_nota)))
    return "régua nova refaz a perícia; extração só se o extrator mudar"


def teste_carimbo_nao_e_texto_do_artigo():
    """19/Ago — O V-HEFT: o PDF que PARECIA legível e não era.

    Ele baixou os 100 originais que mudaram a história da IC. Cinco eram scan. Um deles, o
    V-HeFT I (Cohn, NEJM 1986), não vinha vazio — vinha com **257 caracteres por página**,
    idênticos nas 6: o carimbo "Downloaded from nejm.org…". A checagem da corrente era
    `if texto.strip()` — e 257 caracteres passam nela. A cascata inteira decidia em cima de
    um carimbo, e nenhum waypoint acusava, porque do ponto de vista do código deu tudo certo.

    É a família de defeito que este arquivo já persegue: **a ausência do dado lida como o
    caso favorável.** Aqui a ausência tinha até um valor plausível por cima.

    Esta trava vem da decisão DELE (*"caso o programa não consiga ler estes arquivos, qual
    opção existe"*), não da minha implementação: carimbo não é texto de artigo, e PDF bom
    não paga o preço do OCR.
    """
    import ocr_pdf as O

    carimbo = ("The New England Journal of Medicine\nDownloaded from nejm.org at BOSTON "
               "UNIVERSITY on September 6, 2013. For personal use only. No other uses "
               "without permission.\nCopyright 1986 Massachusetts Medical Society. "
               "All rights reserved.\n") * 6
    serve, motivo = O.texto_e_util(carimbo, n_paginas=6)
    checa("OCR: o carimbo do NEJM NÃO é texto do artigo", not serve, motivo)
    checa("OCR: e o motivo DIZ o porquê (o programa explica, não só recusa)",
          "carimbo" in motivo or "caracteres por página" in motivo, motivo)

    serve, motivo = O.texto_e_util("", n_paginas=3)
    checa("OCR: PDF sem camada de texto continua sendo recusado", not serve, motivo)

    # ⚠️ O CONTROLE — é ele que impede a trava de virar "recusa tudo e passa".
    # Medido em 6 PDFs reais do acervo (Elsevier): 34.000–56.000 caracteres, 0,02–0,06 s.
    # Se o artigo bom cair no OCR, cada rodada de 800 artigos ganha ~5 horas de espera.
    artigo = "\n".join(f"Linha {i} do texto do artigo, com conteudo distinto em cada uma "
                       f"delas e comprimento acima de quarenta caracteres." for i in range(300))
    serve, motivo = O.texto_e_util(artigo, n_paginas=6)
    checa("OCR: artigo de verdade NÃO entra no OCR (senão a rodada quadruplica)", serve, motivo)

    # E o caso que o teste antigo já pegava tem de continuar pego: página curta demais.
    serve, _ = O.texto_e_util("Título do artigo\nAutores\n" * 3, n_paginas=6)
    checa("OCR: densidade baixa reprova mesmo com linhas distintas", not serve, "")
    return "carimbo ≠ artigo · e o artigo bom não paga o preço do OCR"


def teste_texto_ilegivel_nao_chega_no_llm():
    """19/Ago — O SAVE Trial saiu `nota 0` DEPOIS de gastar.

    ```
    🔴 FATOS: só 172 caracteres por página … OCR falhou
    analisado  1992_SAVE_TRIAL_NEJM   nota 0
    ```
    Extração, motor, veredito e perícia rodaram em cima de 1.557 caracteres de carimbo de
    download. **Pagou LLM para não produzir nada.** É o 🔴 BUG que o CLAUDE.md já nomeia —
    *"Editorial/Comment entra na fila e vira perícia — QUEIMA DINHEIRO"* — com outra roupa.

    Não era decisão a tomar: a LEI 10 manda reprovar mais, e ele já disse *"não tenho
    dinheiro para você ficar rasgando por conta de erros infantis"*. Eu perguntei mesmo assim,
    e perguntar o que já está decidido é gastar o tempo dele.

    A trava confere que a parada acontece **ANTES** da chamada de LLM, nos dois pontos que
    pagam: o extrator de FATOS e a perícia.
    """
    import ast
    import os as _os
    import ocr_pdf as O

    checa("existe uma exceção própria para texto ilegível",
          issubclass(O.TextoIlegivel, Exception), "")

    aqui = _os.path.dirname(_os.path.abspath(__file__))
    for arq, marco in (("analise.py", "llm_client"), ("analisador.py", "conferir_veredito")):
        txt = open(_os.path.join(aqui, arq), encoding="utf-8").read()
        arvore = ast.parse(txt)
        linhas_raise = [n.lineno for n in ast.walk(arvore) if isinstance(n, ast.Raise)
                        and ast.dump(n).count("TextoIlegivel")]
        checa(f"{arq} levanta TextoIlegivel", bool(linhas_raise), "não levanta — volta a pagar")
        if linhas_raise:
            # o marco é a primeira coisa CARA do arquivo; a parada tem de vir antes dela
            linhas_marco = [i for i, l in enumerate(txt.splitlines(), 1)
                            if marco in l and not l.strip().startswith("#")]
            if linhas_marco:
                checa(f"{arq}: a parada vem ANTES de gastar ({marco})",
                      min(linhas_raise) < max(linhas_marco),
                      f"raise na linha {min(linhas_raise)} · {marco} na {max(linhas_marco)}")
    return "PDF ilegível para antes do LLM — nos dois pontos que pagam"


def teste_ocr_esta_nos_cinco_pontos_que_leem_pdf():
    """LEI 9 aplicada ao OCR: esta regra mora em CINCO blocos, não em um.

    Consertar só o classificador seria o erro de 02/Ago outra vez — o bloco que sobra roda
    **em silêncio**. Os cinco pontos vivos que abrem PDF na corrente:

      1. classificador_ouro.py   — a cascata (título, DOI, descarte)
      2. classificador_prompt.py — `paginas_1a3()`, **o texto que o LLM lê**
      3. analisador.py           — o texto que vai para a perícia
      4. analise.py              — o extrator de FATOS, de onde sai a NOTA
      5. minirevisao.py          — a trilha da minirrevisão

    Fora da corrente e propositalmente NÃO ligados: `classificador_prompt_v5.py` e
    `prova_v4_v5.py` (experimento), `gabarito.py`/`prova_lote.py` (medição), e
    `classificador_pubmed.classificar_pasta` (entrada antiga, ninguém chama).
    """
    import ast
    import os as _os
    aqui = _os.path.dirname(_os.path.abspath(__file__))
    for arq in ("classificador_ouro.py", "classificador_prompt.py", "analisador.py",
                "analise.py", "minirevisao.py"):
        arvore = ast.parse(open(_os.path.join(aqui, arq), encoding="utf-8").read())
        importa = any(
            (isinstance(n, ast.Import) and any(a.name == "ocr_pdf" for a in n.names)) or
            (isinstance(n, ast.ImportFrom) and n.module == "ocr_pdf")
            for n in ast.walk(arvore))
        chama = any(isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                    and n.func.attr == "extrair" for n in ast.walk(arvore))
        checa(f"OCR ligado em {arq}", importa and chama,
              f"importa={importa} chama_extrair={chama}")
    return "os 5 pontos que abrem PDF passam pelo detector de carimbo"

def teste_mesh_nunca_sobe_vazio():
    """`mesh_terms` vazio deixou de ser resposta — e a queda prevista deixou de ser falha.

    ═══ 22/Ago/2026 — OS DOIS DEFEITOS DO DIA, um de cada lado da mesma moeda ═══

    O Dr. Eduardo rodou a Chave 18 por curiosidade. A tela dizia `CLASSIFICADOR · 70 falhas`.
    Medido: **70 de 70 chegaram em C5_MOVEU.** Não havia falha nenhuma — eram as camadas
    `C2_DOI` e `C3_PUBMED` calando e a cascata caindo para o LLM, como desenhada.

    Puxando esse fio, o buraco de verdade apareceu do outro lado: **208 de 704 linhas com
    `mesh_terms` vazio.** E o contrato AUTORIZAVA, por escrito — a linha dizia que `[]`
    significava "procurei e não achou" e era legítimo. As palavras dele: *"não aceito — null e
    [] na prática são a mesma coisa para mim"*.

    Não é preciosismo de coluna: `mesh_terms` é por onde o **Pesquisador** acha material. Vazio,
    o artigo existe no banco e é invisível para quem procura.

    E a medida que definiu o conserto — 25 dos 169 com DOI real, perguntando ao PubMed naquele
    instante: **0/25 já tinham MeSH.** Esperar a NLM não era opção; daí o `mesh_llm`, que propõe
    e AMARRA ao vocabulário oficial, descartando o que não resolve.

    Os dois defeitos são o mesmo defeito em espelho: **um chamava de falha o que estava certo,
    o outro chamava de certo o que era falha.** Os dois nascem de uma palavra que serve para
    duas coisas diferentes.
    """
    import ast as _ast
    import os as _os
    aqui = _os.path.dirname(_os.path.abspath(__file__))
    import contrato as C

    ok = {"doc_id": "x", "doi": "10.1/x", "titulo": "Titulo bom", "revista": "R",
          "tema": "Arritmias/Anticoagulantes", "tema_secundario": "Não se aplica",
          "tema_origem": "llm", "tipo_documento": "original",
          "mesh_terms": ["Heart Failure", "Humans"], "mesh_origem": "pubmed"}

    def furou(f, palavra):
        return any(palavra in str(x) for x in C.validar(f, checar_arquivos=False))

    # ── 1) o vazio NÃO sobe — nem lista vazia, nem NULL, nem em diretriz ──
    for tipo in ("original", "meta", "diretriz", "revisao_narrativa"):
        checa(f"mesh_terms [] RETÉM ({tipo})",
              furou(dict(ok, tipo_documento=tipo, mesh_terms=[]), "mesh_terms"),
              "o contrato voltou a aceitar coluna vazia — foi assim que 208 linhas subiram")
        checa(f"mesh_terms NULL RETÉM ({tipo})",
              furou(dict(ok, tipo_documento=tipo, mesh_terms=None), "mesh_terms"), "")
    # a diretriz não tem porta de NOTA (LEI 10) — isso nunca foi licença para subir sem conteúdo
    checa("a exceção da diretriz não vale para buraco de coluna",
          furou(dict(ok, tipo_documento="diretriz", mesh_terms=[]), "mesh_terms"),
          "a LEI 10 fala da NOTA; buraco de coluna é outra conversa")

    # ── 2) a PROCEDÊNCIA é obrigatória, e 'falha' não é procedência válida ──
    checa("mesh_origem vazia RETÉM", furou(dict(ok, mesh_origem=""), "mesh_origem"), "")
    checa("mesh_origem 'falha' RETÉM", furou(dict(ok, mesh_origem="falha"), "mesh_origem"),
          "'falha' é defeito de programa — nunca sobe como se fosse origem")
    checa("ficha completa PASSA", not furou(ok, "mesh"), str(C.validar(ok, checar_arquivos=False)))

    # ── 3) a AMARRA existe e descarta o que não é descritor oficial ──
    ml = open(_os.path.join(aqui, "mesh_llm.py"), encoding="utf-8").read()
    arv = _ast.parse(ml)
    nomes = {n.name for n in _ast.walk(arv) if isinstance(n, _ast.FunctionDef)}
    for f in ("resolver", "amarrar", "descritores"):
        checa(f"mesh_llm.{f} existe", f in nomes, "a amarra é o que impede descritor inventado")
    checa("o que não resolve é DESCARTADO, não gravado",
          "descartados.append" in ml and "MIN_DESCRITORES" in ml,
          "descritor inventado é pior que faltando: entra na busca e nunca casa")

    # ── 4) o publicador confere contra a TABELA REAL, não só contra o que ele declara ──
    pub = open(_os.path.join(aqui, "publicador.py"), encoding="utf-8").read()
    checa("publicador confere as colunas no banco", "def conferir_colunas" in pub,
          "sem isso, coluna que só existe no código vira 400 mudo em TODA linha")
    checa("e diz o ALTER TABLE exato", "ADD COLUMN IF NOT EXISTS" in pub, "")

    # ── 5) a queda prevista é LISTA EXPLÍCITA — nunca regra genérica ──
    #
    # A primeira versão do conserto dizia "ok=false mas o artigo chegou ⇒ queda prevista". Rodei:
    # o PUBLICADOR passou a mostrar 28 quedas, e ali NÃO existe cascata — eram recusas de
    # verdade que passaram numa rodada seguinte. A regra genérica escondia recusa atrás de
    # palavra tranquilizadora: o mesmo defeito, de cabeça para baixo.
    cx = open(_os.path.join(aqui, "caixa_preta.py"), encoding="utf-8").read()
    checa("a caixa-preta tem lista explícita de queda prevista", "_QUEDA_PREVISTA" in cx, "")
    checa("e ela só contém waypoints do classificador",
          all(w in cx for w in ("C2_DOI", "C3_PUBMED")), "")
    corpo = cx[cx.index("_QUEDA_PREVISTA"):cx.index("_QUEDA_PREVISTA") + 400]
    checa("nenhum waypoint de PUBLICADOR/ANALISADOR entrou na lista",
          not any(w in corpo for w in ("P1_", "P2_", "P3_", "P4_", "A1_", "A2_")),
          "queda prevista só existe onde alguém DESENHOU uma camada de baixo")

def teste_quem_so_le_nao_paga_pela_ficha_inteira():
    """`ficha_site.montar()` custa dinheiro desde 20/Ago. Quem só LÊ o disco não pode chamá-la.

    ═══ 22/Ago/2026 — O TRAVAMENTO DA CHAVE 3 ═══

    Palavras dele: *"o administrador não está funcionando. Eu carreguei vários artigos."*

    O painel de curadoria monta um índice do STAGING para achar o card e o ACRI de cada artigo.
    Precisava de UMA coisa por pasta: o `doc_id`. E o jeito que eu deixei de obtê-lo era chamar
    `montar()` — a ficha inteira, em TODAS as pastas. Medido: **410 pastas.**

    Até 19/Ago isso era só desperdício: `montar()` era determinístico e barato, e o cabeçalho
    do arquivo dizia, com todas as letras, "NÃO chama LLM". Em 20/Ago eu liguei o TEMA dentro
    dele (PubMed + LLM) e em 22/Ago o MeSH. Abrir a Chave 3 passou a disparar até **820
    chamadas de modelo** — cerca de uma hora — para descobrir nomes de arquivo que estavam ali,
    no disco, de graça. Medido depois do conserto: **0,30 s para as 410**, 409 resolvidos.

    E não dava erro: um `except Exception: pass` engolia tudo e a tela só ficava pendurada.
    **Defeito que espera é pior que defeito que grita** — ninguém vai procurar a causa de uma
    coisa que "está lenta hoje".

    ⚠️ É A LEI 9, cometida por mim, pela segunda vez na mesma semana. Quando `montar()` ficou
    caro, quem travou primeiro foi a BATERIA. Eu consertei a bateria (`CARDIODAILY_SEM_REDE=1`)
    e segui em frente **sem varrer quem mais chamava `montar()`**. Eram três:

        administrador.py  · só queria o doc_id  → doc_id_da_pasta()      [travava a Chave 3]
        rodar_em_blocos.py· só queria o doc_id  → doc_id_da_pasta()      [pagava DUAS vezes
                                                  por artigo, dentro da própria Chave 2]
        ensaio_seco.py    · precisa da ficha    → mantido, mas a tela parou de dizer
                                                  "CUSTO ZERO", que era mentira desde 20/Ago

    A regra que fica: **quem só quer saber ONDE está o pacote não paga pelo que ele SIGNIFICA.**
    """
    import ast as _ast
    import os as _os
    aqui = _os.path.dirname(_os.path.abspath(__file__))
    raiz = _os.path.dirname(aqui)

    import ficha_site as _F
    checa("ficha_site.doc_id_da_pasta existe", hasattr(_F, "doc_id_da_pasta"),
          "sem ela, quem precisa do doc_id volta a chamar montar()")

    # ── 1) o caminho barato NÃO toca em rede: nem LLM, nem PubMed ──
    fonte = open(_os.path.join(aqui, "ficha_site.py"), encoding="utf-8").read()
    arv = _ast.parse(fonte)
    fn = next((n for n in _ast.walk(arv)
               if isinstance(n, _ast.FunctionDef) and n.name == "doc_id_da_pasta"), None)
    checa("doc_id_da_pasta é uma função", fn is not None, "")
    if fn:
        chamadas = {getattr(n.func, "id", "") or getattr(n.func, "attr", "")
                    for n in _ast.walk(fn) if isinstance(n, _ast.Call)}
        for proibida in ("montar", "classificar", "descritores", "_decidir_tema",
                         "_mesh_do_doi", "_mesh_com_plano_b", "urlopen", "gerar_json"):
            checa(f"doc_id_da_pasta não chama {proibida}", proibida not in chamadas,
                  "o caminho barato deixou de ser barato")

    # ── 2) QUEM PODE chamar montar(): só o portão e o ensaio (que avisa o custo) ──
    PODEM = {"publicador.py", "ficha_site.py", "ensaio_seco.py", "teste_motor.py"}
    culpados = []
    for sub in ("src", "scripts"):
        d = _os.path.join(raiz, sub)
        if not _os.path.isdir(d):
            continue
        for nome in sorted(_os.listdir(d)):
            if not nome.endswith(".py") or nome in PODEM:
                continue
            txt = open(_os.path.join(d, nome), encoding="utf-8", errors="ignore").read()
            try:
                a = _ast.parse(txt)
            except SyntaxError:
                continue
            for n in _ast.walk(a):
                # `X.montar(...)` onde X é o ficha_site importado com qualquer apelido
                if (isinstance(n, _ast.Call) and isinstance(n.func, _ast.Attribute)
                        and n.func.attr == "montar"
                        and isinstance(n.func.value, _ast.Name)
                        and ("ficha" in n.func.value.id.lower()
                             or n.func.value.id in ("F", "_F"))):
                    culpados.append(f"{sub}/{nome}:{n.lineno}")
    checa("ninguém fora do portão chama ficha_site.montar()", not culpados,
          "chamam e vão pagar por isso: " + ", ".join(culpados))

    # ── 3) o ensaio seco NÃO pode mais anunciar grátis ──
    # ⚠️ a 1ª versão desta checagem procurava "CUSTO ZERO" no ARQUIVO INTEIRO — e reprovou por
    # causa do meu próprio comentário explicando o conserto. Trava que não distingue o que o
    # programa DIZ do que o programador ESCREVEU obriga a apagar a explicação para ficar verde,
    # e explicação apagada é como o defeito volta. Ela olha só o que vai para a TELA.
    ens = open(_os.path.join(aqui, "ensaio_seco.py"), encoding="utf-8").read()
    impresso = []
    for n in _ast.walk(_ast.parse(ens)):
        if isinstance(n, _ast.Call) and getattr(n.func, "id", "") == "print":
            for arg in _ast.walk(n):
                if isinstance(arg, _ast.Constant) and isinstance(arg.value, str):
                    impresso.append(arg.value)
    tela = " ".join(impresso)
    # ⚠️ e a 2ª versão usou `.upper()`, o que pegou a linha `(ensaio, custo zero)` — que fala do
    # `reparar_notas.py`, outro programa, e que É de graça (não chama `montar()`; a checagem
    # acima prova). Trava larga demais reprova o certo, e quem apaga o certo para ficar verde
    # está trocando a prova pelo placar. É o BANNER que precisa dizer a verdade.
    checa("o BANNER do ensaio não anuncia 'CUSTO ZERO'", "CUSTO ZERO" not in tela,
          "ele chama montar() por pacote — dizer grátis é o instrumento mentindo (LEI 7)")
    checa("o BANNER do ensaio avisa que CHAMA O MODELO", "CHAMA O MODELO" in tela,
          "quem vai gastar precisa saber ANTES de apertar")

def teste_a_tela_explica_a_nota_em_vez_de_so_exibir():
    """Nota abaixo de 6 no painel: ou a tela diz POR QUE é legítima, ou ela GRITA.

    ═══ 22/Ago/2026 ═══
    Palavras dele, ao ver a Chave 3: **"5 não sobe!"**

    E ele está certo — pela LEI 10, meta, revisão e artigo original abaixo de 6 ficam retidos.
    Medido no banco naquele minuto: **18 linhas com nota <6, e as 18 são diretriz** — a única
    exceção que existe, criada por ele em 05/Ago (*"não teremos nenhum impedimento para subir;
    mesmo com as limitações, é o que tem para hoje"*). Zero violação.

    O defeito era da TELA. O `buscar()` pedia `nota_aplicabilidade` e **não pedia
    `tipo_documento`**: no painel, um 5 de diretriz ficava idêntico a um 5 que furou a regra.
    O banco já guardava a resposta certa (`muda_conduta = "REFERÊNCIA, NÃO AUTORIDADE"`) e ela
    não chegava à tela onde ele decide.

    **Número sem critério faz o dono desconfiar do sistema inteiro** — e desconfiança para a
    operação, o que custa mais caro que buraco. A régua do CardioDaily só vale se ele puder ler
    o veredito e conferir o raciocínio; foi para isso que o VEREDITO ABERTO existe no redator
    desde 02/Ago. A curadoria estava sem ele.
    """
    import ast as _ast
    import os as _os
    aqui = _os.path.dirname(_os.path.abspath(__file__))
    adm = open(_os.path.join(aqui, "administrador.py"), encoding="utf-8").read()

    # ── 1) o painel PEDE ao banco o que precisa para explicar ──
    for col in ("tipo_documento", "muda_conduta", "nota_aplicabilidade"):
        checa(f"o painel pede '{col}' ao Supabase", f"{col}" in adm.split("def ler_agenda")[0],
              "coluna que o painel não pede é critério que ele não pode mostrar")

    # ── 2) diretriz: a tela diz que a exceção existe, e de quem foi ──
    checa("a tela nomeia a exceção da diretriz", "05/Ago" in adm and "DIRETRIZ" in adm,
          "sem a data e o dono da decisão, parece defeito do programa")

    # ── 3) não-diretriz abaixo de 6: a tela GRITA em vez de exibir em silêncio ──
    checa("nota <6 fora de diretriz vira erro na tela", "st.error" in adm and "LEI 10" in adm,
          "se o buraco voltar, tem que aparecer na tela dele, não num relatório meu")

    # ── 4) o tema mostrado é o dos 13, não o vocabulário velho de 8 ──
    #     Ele já apontou isto em 20/Ago: "a lista de temas está podre" — a busca por OBSTETRIC
    #     devolvia zero de 520 porque a tela lia `doenca_principal`, outra lista.
    arv = _ast.parse(adm)
    legenda = [n for n in _ast.walk(arv)
               if isinstance(n, _ast.Call) and getattr(n.func, "attr", "") == "caption"]
    fonte_legenda = " ".join(_ast.dump(n) for n in legenda)
    checa("a legenda do artigo mostra `tema`, não `doenca_principal`",
          "doenca_principal" not in fonte_legenda,
          "duas listas de tema na mesma tela — o defeito de 20/Ago voltando")

    # ── 5) a regra que a tela afirma é a MESMA que o contrato aplica (uma fonte só) ──
    import contrato as C
    base = {"doc_id": "x", "doi": "10.1/x", "titulo": "Titulo bom", "revista": "R",
            "tema": "Arritmias/Anticoagulantes", "tema_secundario": "Não se aplica",
            "tema_origem": "llm", "mesh_terms": ["Heart Failure"], "mesh_origem": "pubmed",
            "nota_aplicabilidade": 5}
    for tipo in ("original", "meta", "revisao_narrativa"):
        v = C.validar(dict(base, tipo_documento=tipo), checar_arquivos=False)
        checa(f"nota 5 RETIDA no contrato ({tipo})", any("< 6" in str(x) for x in v),
              "a tela diria 'deveria estar retido' e o portão deixaria passar")
    v = C.validar(dict(base, tipo_documento="diretriz"), checar_arquivos=False)
    checa("nota 5 PASSA no contrato (diretriz)", not any("< 6" in str(x) for x in v),
          "a exceção de 05/Ago sumiu do portão — 13 diretrizes voltariam a ser retidas")

def teste_recusa_pela_regua_nao_e_a_mesma_coisa_que_bug_meu():
    """Três destinos, três significados — e o defeito NÃO tira o artigo da fila.

    ═══ 22/Ago/2026 ═══
    Palavras dele: *"esta categoria de recusados era para situações raras de artigos que não se
    enquadram... desde quando o classificador tem autonomia para pegar um artigo de revisão ou
    original e dar nota e excluir?"*

    Ele estava certo nos dois pontos. O classificador nunca fez isso — ele descarta caso/carta
    para `DESCARTE`. Quem enchia `_RECUSADOS` era o publicador, com um `else` que não perguntava
    o motivo. MEDIDO nos 267 que estavam lá:

        255  a RÉGUA segurou (nota 0, 3, 4, 5) — decisão de produto, LEI 10
          9  DEFEITO NOSSO — inclusive **DOIS artigos nota 9**
          3  sem registro

    E `_pdfs_na_fila` ignorava a pasta: tudo que entrava saía da fila PARA SEMPRE. Um vericiguat
    nota 9, com perícia, áudio e visual prontos, exilado por uma sigla trocada no NOSSO texto.

    Dois defeitos independentes, achados puxando o mesmo fio:
      · o contrato exigia nota 1–10 e o motor produz **0** de propósito (pré-clínico, protocolo).
        43 artigos de bancada apareciam como "programa quebrado". Decisão dele: o motor está
        certo, a faixa passa a ser 0–10 — e 0 continua retido, porque 0 < 6.
      · **e eu repeti o defeito dentro do conserto**: mandei os 9 de `_DEFEITO` para uma pasta
        que NÃO é pasta de tipo. Pela LEI 8, PDF fora de pasta de tipo não entra na fila — eu
        os teria tornado invisíveis de outro jeito. Por isso a checagem 3 abaixo existe.
    """
    import ast as _ast
    import os as _os
    import types as _types
    aqui = _os.path.dirname(_os.path.abspath(__file__))
    raiz = _os.path.dirname(aqui)

    fonte = open(_os.path.join(aqui, "rodar_em_blocos.py"), encoding="utf-8").read()
    arv = _ast.parse(fonte)
    fn = next((n for n in arv.body
               if isinstance(n, _ast.FunctionDef) and n.name == "_destino_da_recusa"), None)
    checa("_destino_da_recusa existe", fn is not None,
          "sem ela o publicador volta ao `else` cego que não pergunta o motivo")
    if not fn:
        return
    mod = _types.ModuleType("_rb")
    mod.__dict__.update(RETIDOS="_RETIDOS_PELA_REGUA", DEFEITO="_DEFEITO")
    exec(compile(_ast.Module(body=[fn], type_ignores=[]), "<rb>", "exec"), mod.__dict__)
    decidir = mod._destino_da_recusa

    # ── 1) os casos REAIS de 22/Ago, um a um ──
    regua = ["contexto_tema: ausente: bloco A do ACRI vazio",
             "impacto_conduta: ausente: bloco I do ACRI vazio",
             "gancho_lista: ausente: sem gancho no ACRI",
             "nota 5 < 6: por regra o artigo FICA retido",
             "contexto_tema vazio ou raso (<40 chars)",
             "caminho_pdf ausente/inexistente: ''"]
    casos = [
        ("VICTORIA nota 9 · sigla trocada", 9,
         ["INVERSÃO FE: estudo de fração REDUZIDA mas o texto usa a sigla 'ICFEP'"], "_DEFEITO"),
        ("os 32 do NameError", None,
         ["preflight de schema: NameError: NAO_SE_APLICA"], "_DEFEITO"),
        ("nota 8 com coluna faltando no banco", 8,
         ["coluna 'mesh_origem' declarada aqui mas AUSENTE na tabela artigos"], "_DEFEITO"),
        ("EXCEL 2016 · a régua segurou", 5, regua, "_RETIDOS_PELA_REGUA"),
        ("pré-clínico da Circulation · nota 0", 0,
         [x.replace("nota 5", "nota 0") for x in regua], "_RETIDOS_PELA_REGUA"),
    ]
    for nome, nota, viol, esperado in casos:
        d, _m = decidir(viol, nota)
        checa(f"{nome} → {esperado}", d == esperado, f"foi para {d}")

    # ── 2) o defeito NÃO tira o artigo da fila (é o que o faz voltar sozinho) ──
    checa("_DEFEITO fora de FILA_FORA", "FILA_FORA" in fonte and '"_DEFEITO"' not in
          fonte.split("FILA_FORA =")[1].split(")")[0],
          "se `_DEFEITO` entrar na lista, bug meu vira artigo perdido para sempre")
    trecho = fonte[fonte.index("destino, motivo = _destino_da_recusa"):][:900]
    checa("em DEFEITO o publicador NÃO chama _tirar_da_fila",
          "_tirar_da_fila" not in trecho.split("else:")[0],
          "mover o PDF em caso de defeito é exilá-lo por erro nosso")

    # ── 3) NENHUM PDF pode acabar fora de uma pasta de TIPO (LEI 8) ──
    # Esta checagem nasce de um erro MEU, cometido dentro do próprio conserto: mandei 9 PDFs
    # para `_DEFEITO`, que não é pasta de tipo — e `_pdfs_na_fila` os teria ignorado.
    import analisador as _A
    for pasta in ("_DEFEITO", "_RETIDOS_PELA_REGUA", "_RECUSADOS"):
        d = _os.path.join(raiz, "ARTIGOS", "CLASSIFICADOS", pasta)
        if not _os.path.isdir(d):
            continue
        pdfs = [f for f in _os.listdir(d) if f.lower().endswith(".pdf")]
        if pasta == "_DEFEITO":
            checa("_DEFEITO não guarda PDF (só o registro)", not pdfs,
                  f"{len(pdfs)} PDF(s) ali — fora de pasta de tipo, invisíveis para a fila")
    checa("as pastas de retenção não são pastas de tipo",
          all(p not in _A._TIPO_POR_PASTA for p in ("_DEFEITO", "_RETIDOS_PELA_REGUA")),
          "se virarem, o artigo retido volta à fila e é reanalisado (e pago) todo mês")

    # ── 4) o contrato aceita 0, e 0 continua retido ──
    import contrato as C
    base = {"doc_id": "x", "doi": "10.1/x", "titulo": "Titulo bom", "revista": "R",
            "tema": "Arritmias/Anticoagulantes", "tema_secundario": "Não se aplica",
            "tema_origem": "llm", "mesh_terms": ["Heart Failure"], "mesh_origem": "pubmed",
            "tipo_documento": "original"}
    v0 = C.validar(dict(base, nota_aplicabilidade=0), checar_arquivos=False)
    checa("nota 0 NÃO é 'inválida' (o motor a produz de propósito)",
          not any("inválida" in str(x) for x in v0),
          "43 artigos pré-clínicos apareciam como defeito de programa")
    checa("mas nota 0 continua RETIDA pela LEI 10", any("< 6" in str(x) for x in v0), "")
    vneg = C.validar(dict(base, nota_aplicabilidade=-1), checar_arquivos=False)
    checa("nota negativa continua inválida", any("inválida" in str(x) for x in vneg),
          "alargar a faixa não é abrir a porteira")

def teste_o_desconto_de_industria_nao_rebaixa_quem_provou_o_metodo():
    """A TERCEIRA fronteira: 8, e só para rigor ≥9.

    ═══ 22/Ago/2026 — O EXCEL, E COMO EU QUASE REVOGUEI O GABARITO DELE ═══

    Ele, olhando a nota do EXCEL: *"não tem como o EXCEL — estudo que muda a cardiologia — não
    estar com nota 9... ou eu tô muito doido"*, e em seguida: *"como um estudo que avalia uma
    galera que racha o peito e no outro braço coloca stent poderia ser cego?"*

    A segunda pergunta está certa como física, e eu peguei essa razão e propus tirar o teto de
    open-label. **Ele concordou — e a proposta contradizia o gabarito que ele mesmo marcou.**
    Só descobri porque fui abrir o arquivo antes de codar:

        EXCEL          gabarito 8   (open-label, rigor 9)
        NOBLE          gabarito 7   (open-label)
        ISAR-REACT 5   gabarito 7   (open-label)

    A calibração inteira dos ensaios abertos foi feita em 11/Ago com estes três, sabendo que
    ninguém cega esternotomia contra punção femoral. Teto 8 não é castigo por não terem cegado
    — é quanta certeza aquele desenho consegue entregar quando o composto inclui IAM julgado.
    Tirá-lo teria levado o EXCEL a 10 e quebrado os três gabaritos.

    **O que faltava era outra coisa:** o EXCEL saía em 7, não 8, porque o desconto de indústria
    (Abbott) descia inteiro — a nota parava em 8, abaixo do piso 9 de 06/Ago.

    A REGRA (decisão dele, 22/Ago): **rigor ≥9 → o desconto de independência não rebaixa.**
    Mesma frase de 06/Ago, agora com o critério explícito: o que protege o artigo não é a nota
    que tirou, é o MÉTODO ter se provado. Patrocinado e mal feito leva o desconto inteiro.

    MEDIDO — mesmo `fatos`, motor de ontem contra o de agora, 1011 artigos únicos:
        **22 mudam, TODOS de 7 → 8. Nenhum desce.**
    """
    import notas_prototipo as N

    def caso(**kw):
        base = dict(pergunta="intervencao", desenho="rct", desfecho_duro=True,
                    extrapolavel=True, poder_ok=True, base_qualidade=9,
                    efeito_relevante_consistente=True, beneficio_supera_risco=True,
                    tipo_documento="original")
        base.update(kw)
        return N.score(base)

    # ── 1) o caso do EXCEL: open-label (teto 8) + rigor 9 + indústria → FICA em 8 ──
    r = caso(open_label=True, financiamento_papel="indústria envolvida")
    checa("EXCEL: teto 8 por open-label", r["teto_desenho"] == 8, f"veio {r['teto_desenho']}")
    checa("rigor 9 (o método se provou)", r["trabalho"] >= 9, f"veio {r['trabalho']}")
    checa("indústria NÃO derruba para 7", r["aplic"] == 8, f"veio {r['aplic']}")
    checa("e o delator DIZ que o desconto não foi aplicado por inteiro",
          any("não aplicado por inteiro" in str(f).lower() or
              "NÃO aplicado por inteiro" in str(f) for f in (r.get("flags") or [])),
          f"flags: {r.get('flags')}")

    # ── 2) patrocinado E mal feito continua levando o desconto inteiro ──
    r = caso(open_label=True, financiamento_papel="indústria envolvida",
             base_qualidade=7, itt_falso=True)
    checa("rigor <9 → desconto INTEIRO (a régua não afrouxou)", r["aplic"] < 8,
          f"veio {r['aplic']} com rigor {r['trabalho']}")

    # ── 3) as fronteiras antigas continuam de pé ──
    r = caso(financiamento_papel="indústria envolvida")          # cegado → teto 10
    checa("a fronteira do 'muda conduta' (9) sobrevive", r["aplic"] >= 9, f"veio {r['aplic']}")
    checa("PISO_INDEPENDENCIA continua 9", N.PISO_INDEPENDENCIA == 9, "")
    checa("PISO_PUBLICACAO continua 6 (= a porta da LEI 10)", N.PISO_PUBLICACAO == 6, "")

    # ── 4) O GABARITO DELE É A TRAVA MAIOR — nenhuma regra nova pode revogá-lo ──
    # É o que teria pegado a minha proposta de tirar o teto de open-label, se eu tivesse codado.
    from notas_prototipo import FIXTURES
    for nome, fx in FIXTURES.items():
        a = dict(fx)
        gab = a.pop("gabarito")
        calc = N.score(a)["aplic"]
        bate = (str(calc) == str(gab)) or (isinstance(gab, str) and "-" in gab and
                                           int(gab.split("-")[0]) <= calc <= int(gab.split("-")[1]))
        checa(f"gabarito do Dr. Eduardo: {nome} = {gab}", bate, f"o motor deu {calc}")

def teste_minirrevisao_processada_sai_da_fila():
    """O estado é FÍSICO também na minirrevisão — 22/Ago/2026.

    Pergunta dele: *"as minirrevisões que já foram processadas, por que não saem da pasta —
    para uma pasta de minirrevisões já processadas?"*

    Porque esta trilha nasceu fora da regra que o resto do projeto adotou. O
    `rodar_em_blocos.py` diz, no cabeçalho: *"NÃO usa 'pular por marcador' (que sempre dá
    problema). O estado é FÍSICO: o que está na fila ainda falta; o que saiu da fila, acabou."*

    A minirrevisão fazia o oposto: pulava por `_OK` na pasta de SAÍDA e deixava o PDF na fila
    para sempre. MEDIDO em 22/Ago: **107 PDFs na pasta, 100 já processados, 7 realmente
    pendentes** — e ele não tinha como ver isso abrindo a pasta.

    Dois problemas, e o segundo é o grave:
      · a pasta mente sobre o que falta;
      · marcador é o MESMO mecanismo do erro fatídico de 03/Ago (staging com `_OK`
        reaproveitado com o prompt errado, e a correção manual dele indo para o lixo num
        `continue`). Lá o projeto trocou por estado físico; aqui tinha ficado como estava.

    O `_OK` continua, como cinto de segurança de quem rodar apontando para um arquivo só —
    mas quem manda é o disco, e o ramo que pula TAMBÉM move.
    """
    import ast as _ast
    import os as _os
    aqui = _os.path.dirname(_os.path.abspath(__file__))
    fonte = open(_os.path.join(aqui, "minirevisao.py"), encoding="utf-8").read()
    arv = _ast.parse(fonte)

    checa("existe _tirar_da_fila na minirrevisão",
          any(isinstance(n, _ast.FunctionDef) and n.name == "_tirar_da_fila"
              for n in _ast.walk(arv)),
          "sem ela o PDF processado fica na fila para sempre")

    fn = next((n for n in _ast.walk(arv)
               if isinstance(n, _ast.FunctionDef) and n.name == "processar_pdf"), None)
    checa("processar_pdf existe", fn is not None, "")
    if fn:
        chamadas = [n for n in _ast.walk(fn) if isinstance(n, _ast.Call)
                    and getattr(n.func, "id", "") == "_tirar_da_fila"]
        # DUAS: uma no ramo que pula (`_OK` já existe) e uma no fim do processamento.
        # Sem a do ramo que pula, os 100 já feitos nunca sairiam — só os novos.
        checa("o PDF sai da fila NOS DOIS caminhos (já feito · acabou de fazer)",
              len(chamadas) >= 2, f"achei {len(chamadas)} chamada(s)")

    checa("a varredura NÃO desce em _FEITAS",
          "FILA_FORA" in fonte and "_FEITAS" in fonte,
          "senão o próximo run reencontra tudo e a pasta nunca esvazia")
    tf = next((n for n in _ast.walk(arv)
               if isinstance(n, _ast.FunctionDef) and n.name == "_tirar_da_fila"), None)
    if tf:
        corpo = _ast.dump(tf)
        # LEI 12: confere destino e tamanho ANTES de mover. `ARTIGOS/` não está no git.
        checa("confere se o destino já existe antes de mover", "exists" in corpo, "")
        checa("confere o tamanho da origem (não move arquivo de 0 byte)",
              "getsize" in corpo, "foi assim que um gabarito dele morreu em 20/Ago")
        checa("MOVE, não copia nem apaga", "move" in corpo and "remove" not in corpo, "")

def teste_titulo_curto_nao_e_titulo_quebrado():
    """"Syncope" é o nome do artigo, não um buraco de extração — 26/Ago/2026.

    Ele: *"me explica por que ele recusou o artigo de síncope do NEJM — revisão maravilhosa!"*

    A régua não tinha nada a ver. O que barrou foi UMA LINHA do contrato:

        if len(titulo.strip()) < 10:
            "titulo vazio ou curto demais (<10 chars) — cheira a buraco de nome"

    **O artigo se chama "Syncope".** Sete caracteres. É uma Review do NEJM, e o NEJM dá títulos
    de uma palavra às revisões: Syncope · Hypertension · Myocarditis. O dado estava CERTO e a
    trava reprovou pelo FORMATO.

    A regra confundia duas coisas que só se parecem:
        "o título NÃO VEIO"  → defeito de extração ("", "Mo", "Article", "n/a")
        "o título é CURTO"   → o artigo é assim

    O 10 nasceu como sintoma de extração quebrada — e sintoma não é diagnóstico. É o mesmo
    erro de forma do `qualidade_entrada` (22/Ago): tratar a ausência de um sinal como prova
    do caso ruim, quando o certo é olhar o que o dado DIZ.

    Agora decide o CONTEÚDO do título mais a integridade do resto da identidade: título curto
    passa se for palavra de verdade E revista e data estiverem íntegras — porque extração que
    quebra no título quebra em tudo.
    """
    import contrato as C
    base = dict(revista="The New England Journal of Medicine", data_publicacao="2026-08-01")

    def passa(t, **kw):
        return not C._titulo_furou(dict(base, **kw, titulo=t))

    # ── 1) O CASO REAL, e os irmãos dele no NEJM ──
    for t in ("Syncope", "Hypertension", "Myocarditis", "Atrial Fibrillation"):
        checa(f"título de uma palavra passa: {t!r}", passa(t),
              "o NEJM dá títulos de uma palavra às revisões — não é buraco")

    # ── 2) O QUE A TRAVA EXISTIA PARA PEGAR continua sendo pego ──
    for t, porque in (("", "vazio"),
                      ("Mo", "o `ModuleNotFoundError` decapitado por um [:110] em 19/Ago"),
                      ("Article", "rótulo genérico, não é o nome do artigo"),
                      ("n/a", "ausência com nome de dado"),
                      ("10.1056", "código, não título"),
                      ("---", "pontuação")):
        checa(f"ainda barra {t!r} ({porque})", not passa(t), "voltou a passar lixo de extração")

    # ── 3) O CURTO SÓ PASSA SE O RESTO DA IDENTIDADE SUSTENTAR ──
    # É o que distingue "o artigo se chama assim" de "a extração quebrou em tudo".
    checa("curto + sem revista → barra", not passa("Syncope", revista=""),
          "extração que quebra no título quebra na revista também")
    checa("curto + data inválida → barra", not passa("Syncope", data_publicacao="2026"),
          "idem para a data")
    checa("curto + identidade íntegra → passa", passa("Syncope"), "")

    # ── 4) e o título longo de sempre não foi afetado ──
    checa("título normal passa", passa("Vericiguat in Patients with Heart Failure"), "")

def teste_pool_pre_especificado_nao_e_meta_analise():
    """FIDELIO + FIGARO + FINEARTS não foram garimpados na literatura — 26/Ago/2026.

    Palavras dele, sobre o FINE-HEART: *"não é meta-análise, é uma análise pré-especificada de
    um conjunto de 3 trials que fazem parte do mesmo projeto. Este tem que ser analisado como
    artigo original."*

    O enum de `desenho` só tinha `meta`, então o extrator chamava de meta o que não é — e a
    consequência não foi um rótulo feio, foi **nota 3**:

        FALHA FATAL F5: "meta sem heterogeneidade nem viés de publicação avaliados"
        NHLBI: falhou em `busca_sistematica_abrangente`, `vies_publicacao_avaliado`

    Critérios de revisão sistemática cobrados de uma análise que NÃO FAZ BUSCA. Não há
    literatura a garimpar (são os ensaios do próprio programa) e não há universo de estudos
    alheios em que caiba viés de publicação. Cobrar isso é reprovar o artigo por não ter feito
    o que não cabia. Depois do conserto: **nota 6, rigor 9** — e o que segura passou a ser a
    régua de verdade (ARR 0,16 %/ano abaixo do limiar de 1,0 %/ano que ele fixou).

    DECISÃO DELE, 26/Ago: teto de desenho **10, igual ao RCT** — *"dados individuais,
    randomizados, plano pré-especificado, comitê de adjudicação. Se o desenho entrega isso,
    não há razão para capar — quem derruba depois é o rigor e o MCID."*
    E pool POST-HOC (juntaram depois de ver o resultado) continua sendo `meta`, na Escada.
    """
    import notas_prototipo as N
    import contrato as C
    import analisador as A

    # ── 1) o valor existe em TODOS os blocos que decidem por `desenho` (LEI 9) ──
    import os as _os, json as _json
    aqui = _os.path.dirname(_os.path.abspath(__file__))
    import analise as AN
    enum = AN.SCHEMA_FATOS["properties"]["desenho"]["enum"]
    checa("SCHEMA conhece pool_pre_especificado", "pool_pre_especificado" in enum, "")
    prompt = open(_os.path.join(aqui, "analise_prompt.md"), encoding="utf-8").read()
    checa("o PROMPT ensina a diferença (senão o campo nasce morto)",
          "pool_pre_especificado" in prompt and "MESMO PROGRAMA" in prompt.upper(),
          "schema sem prompt = campo que nunca é preenchido (o defeito de 06/Ago)")
    checa("o redator é o de ARTIGO ORIGINAL",
          A._PROMPT_POR_DESENHO.get("pool_pre_especificado") == "redator_original_prompt.md",
          "no prompt da meta o texto cobraria PRISMA de quem não fez busca")
    checa("teto de RIGOR = 10 (como o rct, não 9 como a meta)",
          N._TETO_RIGOR_DESENHO.get("pool_pre_especificado") == 10, "")

    def caso(**kw):
        base = dict(pergunta="intervencao", desenho="pool_pre_especificado", desfecho_duro=True,
                    extrapolavel=True, poder_ok=True, base_qualidade=9, open_label=False,
                    tipo_documento="original", efeito_relevante_consistente=True,
                    beneficio_supera_risco=True)
        base.update(kw)
        return N.score(base)

    # ── 2) teto de DESENHO 10, e o motor é o ORIGINAL ──
    r = caso()
    checa("teto de desenho 10", r["teto_desenho"] == 10, f"veio {r['teto_desenho']}")
    checa("motor ORIGINAL, não META", r["motor"] == "ORIGINAL", f"veio {r['motor']}")

    # ── 3) a F5 declarada pelo extrator NÃO vale para quem não é meta ──
    # Era a lista do extrator entrando por cima do desenho: duas fontes para o mesmo fato,
    # e a que não sabia do desenho ganhando. LEI 9.
    r = caso(falhas_fatais=["F5"])
    checa("F5 (falha de meta) não conta no pool", "F5" not in (r.get("falhas_fatais") or []),
          f"falhas: {r.get('falhas_fatais')} — o artigo é zerado por não ter feito busca")
    # e continua contando numa meta de verdade
    r = N.score(dict(pergunta="intervencao", desenho="meta", desfecho_duro=True,
                     extrapolavel=True, tipo_documento="meta", falhas_fatais=["F5"]))
    checa("mas F5 continua fatal numa META de verdade",
          "F5" in (r.get("falhas_fatais") or []), "a régua da meta não pode ter afrouxado")

    # ── 4) o NHLBI cobrado é o do ENSAIO, não o da revisão sistemática ──
    r = caso(qualidade_nhlbi={"instrumento": "systematic_review",
                              "busca_sistematica_abrangente": False,
                              "vies_publicacao_avaliado": False,
                              "randomizacao_adequada": True, "alocacao_sigilosa": True})
    checa("não é reprovado por não ter feito busca sistemática",
          not any("busca" in str(c) for c in (r.get("nhlbi") or {}).get("criterios_falhos", [])),
          f"criterios_falhos: {(r.get('nhlbi') or {}).get('criterios_falhos')}")

    # ── 4b) A MISTURA DE POPULAÇÕES É A PERGUNTA, NÃO O DEFEITO (26/Ago) ──
    # Ele: *"no FINE-ARTS os 3 trabalhos pegam populações um pouco diferentes — em um é renal
    # crônico com diabetes, no outro sem diabetes... vamos misturar e ver se os efeitos se
    # mantêm."*  Numa meta comum, heterogeneidade alta é problema. Aqui é o experimento.
    # Decisão dele: NÃO capa — mas o delator DIZ, porque quem decide se aquele agrupado cabe
    # no paciente da frente é o leitor.
    for rot, kw, esperado in (
            ("efeito se manteve", dict(pool_efeito_consistente=True), "SE MANTEVE"),
            ("um ensaio destoou", dict(pool_efeito_consistente=False), "NÃO se manteve"),
            ("o artigo não diz", {}, "não diz")):
        r = caso(pool_populacoes="DRC com diabetes, DRC sem diabetes e ICFEp", **kw)
        d = [f for f in (r.get("flags") or []) if "agrupada" in f]
        checa(f"pool · o delator diz o caso '{rot}'",
              bool(d) and esperado in d[0], f"flags: {d or r.get('flags')}")
        checa(f"pool · '{rot}' NÃO capa a nota", r["teto_desenho"] == 10,
              f"teto {r['teto_desenho']} — penalizar seria reprovar pela pergunta que o estudo faz")
    # e o campo só existe onde faz sentido
    r = N.score(dict(pergunta="intervencao", desenho="rct", desfecho_duro=True, poder_ok=True,
                     tipo_documento="original", pool_populacoes="isto não deveria ser lido"))
    checa("o delator do pool NÃO aparece num RCT comum",
          not any("agrupada" in str(f) for f in (r.get("flags") or [])), "")

    # ── 5) o CONTRATO não acusa mais caixa errada ──
    ficha = {"tipo_documento": "original", "desenho": "pool_pre_especificado",
             "doc_id": "x", "doi": "10.1/x", "titulo": "Effects of Finerenone on Sudden Death",
             "revista": "JACC", "data_publicacao": "2026-08-01",
             "tema": "Cardiometabólica", "tema_secundario": "Não se aplica", "tema_origem": "llm",
             "mesh_terms": ["Heart Failure"], "mesh_origem": "pubmed", "nota_aplicabilidade": 6}
    checa("contrato NÃO acusa CAIXA ERRADA",
          not any("CAIXA ERRADA" in str(x) for x in C.validar(ficha, checar_arquivos=False)),
          "o FINE-HEART ficaria preso em _REVISAO_HUMANA para sempre")
    # mas uma META de verdade na pasta de original continua sendo denunciada (LEI 8)
    checa("e continua acusando quando o desenho é META mesmo",
          any("CAIXA ERRADA" in str(x)
              for x in C.validar(dict(ficha, desenho="meta"), checar_arquivos=False)), "")

def teste_a_meta_de_dados_individuais_e_reconhecida():
    """`eh_ipd` nunca foi verdadeiro em produção — o campo morava em dois lugares (26/Ago/2026).

    Ele, explicando por que o NEJM publica tão pouca meta-análise: *"a única que eu vi foi a que
    pegou os dados reais dos pacientes para fazer uma única tabela — aumenta muito o poder de
    excluir que os dados possam ter sido afetados por alguma interferência (lei dos grandes
    números: maior amostra, maior precisão)"*. E a distinção: *"em meta-análises os autores em
    geral analisam RESULTADO versus RESULTADO — eles não podem juntar tudo num pacote só
    porque não têm a tabela."*

    ═══ MEDIDO NO DISCO, e é o defeito que mais custou desta conversa ═══
        tipo_meta NO TOPO dos fatos       : dados_agregados 46 · rede 4 · **ipd 4** · None 44
        tipo_meta DENTRO de qualidade_meta: None 98

    O extrator grava no TOPO (é onde o schema o declara). O motor procurava DENTRO de
    `qualidade_meta`. Um nome, dois lugares — e **`eh_ipd` nunca foi verdadeiro, nenhuma vez**.
    As 4 metas de dados individuais do acervo foram julgadas como meta de resultados, cobradas
    de funnel plot e Trim-and-Fill que não lhes cabem: numa IPD os ensaios entraram no acordo
    ANTES de o resultado existir, não há gaveta de onde puxar estudo faltante.

    A régua da IPD existe no código desde 04/Ago (`"eliminado POR DESENHO"`) e nunca rodou.

    ⚠️ E HAVIA UMA PISTA: a checagem da meta em REDE já lia `m.get("tipo_meta") or
    a.get("tipo_meta")` — os dois lugares. Alguém (eu) esbarrou no problema, consertou ALI, e
    não varreu os outros dois pontos. LEI 9 inteira numa linha.

    MEDIDO depois do conserto, 1072 artigos únicos: **2 mudam** (7→8 no NEJM Beta-Blockers
    after MI, 3→4 no JACC Quality of Life). Cirúrgico.
    """
    import notas_prototipo as N

    # ── 1) LEITURA ÚNICA: o campo é lido pela função, nunca solto ──
    import os as _os, re as _re
    fonte = open(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)),
                               "notas_prototipo.py"), encoding="utf-8").read()
    corpo = fonte[fonte.index("def tipo_meta_de(a):"):]
    corpo = corpo[corpo.index('"""', corpo.index('"""') + 3):]      # depois do docstring
    soltas = [l for l in fonte.splitlines()
              if 'get("tipo_meta")' in l
              and "def tipo_meta_de" not in l
              and 'm.get("tipo_meta") or a.get("tipo_meta")' not in l
              and l.strip().startswith(("m =", "return str(m.get"))]
    checa("nenhuma leitura solta de tipo_meta fora da função canônica",
          len([l for l in fonte.splitlines()
               if 'get("tipo_meta")' in l]) <= 2,
          "voltou a haver duas fontes para o mesmo campo")

    # ── 2) o campo é achado NOS DOIS níveis (fatos velhos e novos) ──
    checa("acha no TOPO (é onde o extrator grava)",
          N.eh_ipd({"tipo_meta": "ipd"}), "os 4 IPD do acervo estão assim")
    checa("acha DENTRO de qualidade_meta (onde o motor procurava)",
          N.eh_ipd({"qualidade_meta": {"tipo_meta": "ipd"}}), "")
    checa("prospectiva também conta como IPD",
          N.eh_ipd({"tipo_meta": "prospectiva"}), "combinam antes de o resultado existir")
    checa("dados_agregados NÃO é IPD", not N.eh_ipd({"tipo_meta": "dados_agregados"}),
          "aqui há estimativa alheia a somar — o GIGO que capa a meta em 8/9")
    checa("sem o campo, não é IPD", not N.eh_ipd({}), "silêncio não vira prêmio (LEI 11)")

    # ── 3) o TETO: a IPD chega a 10, a meta comum não ──
    def teto(tm):
        f = {"pergunta": "intervencao", "desenho": "meta", "tipo_meta": tm,
             "desfecho_duro": True, "extrapolavel": True}
        return N.teto_desenho(f), N.teto_rigor(f)
    td_i, tr_i = teto("ipd")
    td_a, tr_a = teto("dados_agregados")
    checa("IPD: teto de desenho 10", td_i == 10, f"veio {td_i}")
    checa("IPD: teto de rigor 10", tr_i == 10, f"veio {tr_i}")
    checa("meta comum continua capada", td_a < 10 and tr_a < 10,
          f"desenho {td_a} · rigor {tr_a} — o GIGO da meta de estimativas não foi revogado")

    # ── 4) Trim-and-Fill não é falha fatal numa IPD ──
    base = {"desenho": "meta", "qualidade_meta": {"trim_and_fill_perdeu_significancia": True}}
    checa("M2 é fatal na meta de resultados",
          "M2" in N.falhas_fatais_meta(dict(base, tipo_meta="dados_agregados")), "")
    checa("M2 NÃO é fatal na IPD",
          "M2" not in N.falhas_fatais_meta(dict(base, tipo_meta="ipd")),
          "Trim-and-Fill estima estudos não publicados; na IPD não há gaveta")


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
              teste_mcid_cardiodaily,
              teste_carimbo_nao_e_texto_do_artigo,
              teste_ocr_esta_nos_cinco_pontos_que_leem_pdf]

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
