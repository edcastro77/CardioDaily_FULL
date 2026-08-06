"""
analisador.py — O APP ANALISADOR (Elo 4), autocontido e modular.
Lê CLASSIFICADOS/<tipo>/ → por artigo: analise → notas → registro canônico → entregáveis POR LIMIAR
→ grava tudo LOCAL numa pasta de STAGING. NÃO sobe (é do publicador). NÃO limpa (é do arquivador).

PORTAS (Dr. Eduardo):  ≤5 fica · ≥6 sobe (canônico+ACRI+texto) · ≥7 +infográfico · ≥8 +áudio
Uso:  python analisador.py <pasta_CLASSIFICADOS>        (roda a corrente)
      python analisador.py --gabarito                   (só mostra a lógica das portas)
"""
import os, sys, json, re, fitz

_HERE = os.path.dirname(os.path.abspath(__file__))


def _carregar_env():
    """Acha o CardioDaily_FULL/.env subindo as pastas — funciona de qualquer local (lab, ferramentas...)."""
    from dotenv import load_dotenv
    d = _HERE
    for _ in range(8):
        cand = os.path.join(d, "CardioDaily_FULL", ".env")
        if os.path.exists(cand):
            load_dotenv(cand, override=True); return
        d = os.path.dirname(d)
    load_dotenv(override=True)


_carregar_env()


def eh_diretriz(tipo):
    """UM lugar só decide se é diretriz. Os 5 portões que olham nota consultam este predicado.

    05/Ago: a exceção da diretriz precisa valer nos CINCO pontos que decidem por nota —
    a porta (decidir_entregaveis), a geração do visual, a do áudio, e as duas checagens do _OK.
    Espalhar `tipo == "diretriz"` em cinco `if` é como a regra ficou em três lugares e discordou
    (o buraco do muda_conduta, 04/Ago). Um predicado, cinco chamadas."""
    return (tipo or "").strip().lower() == "diretriz"


def decidir_entregaveis(nota, tipo=None):
    """As portas por nota. Devolve (lista_de_entregaveis, sobe?).

    ═══ 05/Ago/2026 — A DIRETRIZ NÃO TEM PORTA. É A EXCEÇÃO DA LEI 10. ═══

    Palavras do Dr. Eduardo: *"as diretrizes — precisamos manter esta classificação mas não
    teremos nenhum impedimento para subir. Mesmo com as limitações, é o que tem para hoje."*

    POR QUE A EXCEÇÃO É COERENTE, e não uma brecha na LEI 10:
    A LEI 10 diz que o CardioDaily é um FILTRO — ele existe para dizer "olhei 24 metas e 12 não
    prestam". Isso funciona porque, para uma meta ruim, existe outra melhor: o cardiologista não
    perde nada se ela for retida.

    Com DIRETRIZ é o contrário. Não existe "outra diretriz de fibrilação atrial melhor" — existe
    A diretriz. Se ela é fraca, o médico precisa saber que é fraca **e mesmo assim precisa dela**,
    porque é o que a sociedade publicou e é o que vai ser cobrado dele. Reter uma diretriz não
    protege ninguém: só esconde o documento que rege a prática.

    Por isso, para diretriz: NOTA CONTINUA VALENDO (e aparece, com justificativa), mas NÃO retém.
    Medido em 04/Ago: 13 de 31 diretrizes ficavam retidas com nota 4 e 5 — ESC, AHA, ESPEN, NICE.

    ⚠️ Vale SÓ para diretriz. Meta, revisão e artigo original mantêm a porta em 6 (ordem expressa
    dele: "ESTA REGRA SÓ VALE PARA DIRETRIZ").
    """
    if eh_diretriz(tipo):
        # sobe SEMPRE, com pacote completo: ACRI (palavras-chave cuidadas), visual e áudio LONGO
        return ["canonico", "ACRI", "texto", "infografico", "audio"], True
    if nota < 6:
        return ["canonico(retido)"], False          # ≤5 FICA — retém local, não publica
    ents = ["canonico", "ACRI", "texto"]             # ≥6 SOBE
    if nota >= 7:
        ents.append("infografico")                   # ≥7
    if nota >= 8:
        ents.append("audio")                         # ≥8
    return ents, True


# ─────────── PERÍCIA POR TIPO — 01/Ago/2026 (fim do prompt único "superficializado") ───────────
# Até hoje UM prompt servia todos os tipos, e a estrutura dele era de ARTIGO ORIGINAL: pedia
# randomização, braços, titulação de dose e desfecho primário. Meta-análise não tem braço; diretriz
# não tem desfecho primário; revisão narrativa não tem análise estatística. O Dr. Eduardo apontou
# isso em 26/Jul ("um prompt para 5 direções só é possível superficializando") e estava certo.
#
# A escolha é pelo campo `desenho` dos FATOS — o DADO CANÔNICO, não a pasta. A pasta pode estar
# errada (o classificador acerta 91,9%); os fatos vêm da leitura do artigo.
_PROMPT_POR_DESENHO = {
    "rct": "redator_original_prompt.md",
    "coorte": "redator_original_prompt.md",
    "registro": "redator_original_prompt.md",
    "observacional_ajustado": "redator_original_prompt.md",
    "transversal": "redator_original_prompt.md",
    "caso_controle": "redator_original_prompt.md",
    "antes_depois_sem_controle": "redator_original_prompt.md",
    "serie_de_casos": "redator_original_prompt.md",
    "meta": "redator_meta_prompt.md",
}
# guideline e revisão não são "desenho" no schema dos fatos — vêm da pasta do classificador.
_PROMPT_POR_PASTA = {
    "GUIDELINES": "redator_guideline_prompt.md",
    "REVISOES": "redator_revisao_prompt.md",
    "META_ANALISES": "redator_meta_prompt.md",
    "ARTIGOS_ORIGINAIS": "redator_original_prompt.md",
}

# ═══ FONTE ÚNICA DO TIPO — LEI 8 (02/Ago/2026) ═══
# "o classificador não pode errar — se ele colocar um trabalho na caixa errada, vamos usar o motor
#  errado, o prompt errado, análise e notas erradas" (Dr. Eduardo).
# A PASTA é o registro da decisão do classificador. Esta função é o ÚNICO lugar onde essa decisão é
# lida. Quem precisa saber o tipo — o EXTRATOR, o MOTOR e o PROMPT — chama daqui, não deduz por conta.
_TIPO_POR_PASTA = {
    "ARTIGOS_ORIGINAIS": "original",
    "META_ANALISES": "meta",
    "GUIDELINES": "diretriz",
    "REVISOES": "revisao_narrativa",
    "EDITORIAIS": "revisao_narrativa",
    "MINIRREVISOES": "revisao_narrativa",
}


# ═══════════ CARIMBO DE VERSÃO DO PROMPT — 04/Ago/2026 ═══════════
# Pergunta do Dr. Eduardo: *"ele está aproveitando um monte de coisas que já tinham sido feitas —
# por qual prompt?"*. A resposta era: NINGUÉM SABIA. Existem TRÊS níveis de reaproveitamento
# (o pacote inteiro no rodar_em_blocos, os FATOS aqui, e cada PEÇA no `_peca`) e nenhum registrava
# a versão do prompt que gerou o conteúdo.
#
# O estrago possível: em 04/Ago o prompt da meta mudou TRÊS vezes numa madrugada (árvore de
# porteiras, regra do nulo, tipo_meta obrigatório). Um staging feito às 03h seria reaproveitado às
# 05h como se fosse novo — e o conserto não pegaria, em silêncio. É a MESMA classe de buraco do
# `_OK` de 27/Jul e do reuso que ignorava a pasta em 03/Ago: reaproveitamento que preserva o erro.
#
# Agora cada pacote leva um `_versoes.json` com o hash do conteúdo de CADA prompt que o produziu.
# Se o prompt mudou, a peça correspondente é refeita. Não é preciso lembrar de nada: o arquivo conta.
def hash_prompt(nome):
    """12 dígitos do sha1 do CONTEÚDO do prompt. Muda uma vírgula, muda o hash."""
    import hashlib
    try:
        return hashlib.sha1(open(os.path.join(_HERE, nome), "rb").read()).hexdigest()[:12]
    except OSError:
        return "?"


def hash_arquivo_src(nome):
    """SHA1 do conteúdo de um arquivo de `src/` — para carimbar CÓDIGO, não só prompt."""
    import hashlib
    try:
        return hashlib.sha1(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), nome),
                                 "rb").read()).hexdigest()[:12]
    except Exception:
        return "?"


def versoes_atuais(pdf_path=""):
    """O carimbo de tudo que MUDA A SAÍDA deste tipo de documento.

    ═══ 04/Ago/2026, 21h40 — O CARIMBO SÓ OLHAVA OS PROMPTS ═══

    O Dr. Eduardo rodou a Chave 2 depois de a régua da meta ser reescrita (Escada + escala de
    aplicabilidade + bicondicional) e a rodada terminou em SEGUNDOS: "reusado (staging pronto)"
    nos 24. Ele desconfiou na hora — *"foi muito rápido, está certo isso?"* — e não estava.

    A causa: este carimbo listava só o hash dos PROMPTS. Eu não tinha mexido em prompt nenhum
    depois da rodada anterior; mexi no MOTOR. Como o motor não estava no carimbo, o guarda viu
    tudo igual e reaproveitou — republicando notas calculadas com a régua VELHA. Medido no
    Supabase logo depois: um artigo com nota 9 e "muda_conduta: NÃO", a contradição que a gente
    tinha acabado de matar, de volta no banco.

    É a família de erro do dia inteiro: uma decisão que depende de N coisas, e o guarda olha uma.

    Agora entram TAMBÉM os arquivos de CÓDIGO que determinam a nota. Mudar a régua passa a
    invalidar o staging sozinho — sem depender de eu lembrar de avisar.
    """
    from analise import PROMPT_ARQ_POR_TIPO
    tipo = tipo_do_documento(pdf_path)
    return {
        # ── o CÓDIGO que decide a nota (não é prompt, mas muda a saída do mesmo jeito) ──
        "motor":    f"notas_prototipo.py@{hash_arquivo_src('notas_prototipo.py')}",
        "extracao": f"analise.py@{hash_arquivo_src('analise.py')}",   # os SCHEMAS moram aqui
        "extrator": f"{PROMPT_ARQ_POR_TIPO[tipo]}@{hash_prompt(PROMPT_ARQ_POR_TIPO[tipo])}",
        "redator":  f"{_PROMPT_POR_TIPO_DOC[tipo]}@{hash_prompt(_PROMPT_POR_TIPO_DOC[tipo])}",
        "acri":     f"acri_prompt.md@{hash_prompt('acri_prompt.md')}",
        "audio":    (f"script_audio_diretriz_prompt.md@{hash_prompt('script_audio_diretriz_prompt.md')}"
                     if tipo == "diretriz" else
                     f"script_audio_prompt.md@{hash_prompt('script_audio_prompt.md')}"),
        "gancho":   f"gancho_abertura_prompt.md@{hash_prompt('gancho_abertura_prompt.md')}",
    }


def versoes_gravadas(dst):
    import json as _j
    try:
        return _j.load(open(os.path.join(dst, "_versoes.json"), encoding="utf-8"))
    except Exception:
        return {}


_PROMPT_POR_TIPO_DOC = {
    "original": "redator_original_prompt.md",
    "meta": "redator_meta_prompt.md",
    "diretriz": "redator_guideline_prompt.md",
    "revisao_narrativa": "redator_revisao_prompt.md",
}


def tipo_do_documento(pdf_path=""):
    """O tipo decidido pelo classificador. 'original' é a rede quando não há pasta (teste avulso)."""
    return _TIPO_POR_PASTA.get(os.path.basename(os.path.dirname(pdf_path or "")), "original")


def escolher_prompt(fatos=None, pdf_path=""):
    """Qual perícia este documento merece. **A PASTA MANDA. PONTO.**

    ═══ FECHADO EM 03/Ago/2026 — a tarefa #34, e o erro que ela causou ═══

    Palavras do Dr. Eduardo, depois de consertar as pastas na mão e ver o resultado:
        "consertei manualmente os artigos nas pastas e na primeira análise ele me lê uma
         REVISÃO com PROMPT DE ARTIGO ORIGINAL... A PASTA DE REVISÃO SÓ PODE APLICAR PROMPT
         DE REVISÃO — A PASTA DE ORIGINAL SÓ PODE APLICAR PROMPT DE ARTIGO ORIGINAL."

    O CÓDIGO ANTIGO fazia isto: para GUIDELINES e REVISOES obedecia a pasta; para
    ARTIGOS_ORIGINAIS e META_ANALISES olhava o campo `desenho` dos FATOS. Duas fontes de
    verdade para a MESMA pergunta — exatamente o que a LEI 8 proíbe. Consequência real:
    o Dr. Eduardo move um artigo para a pasta certa, o extrator devolve `desenho=rct`,
    e a perícia sai com o prompt de artigo original mesmo assim. A correção manual dele
    era simplesmente IGNORADA.

    Eu sabia do buraco desde 02/Ago (deixei escrito aqui mesmo) e adiei "até o classificador
    melhorar". Errado: enquanto o classificador não fica bom, a correção MANUAL é a única
    verdade que existe — e era justamente ela que o código descartava.

    Agora: pasta → tipo → prompt. Uma decisão, um lugar. Se a pasta estiver errada, o
    conserto é mover o arquivo; e mover o arquivo passa a FUNCIONAR.
    """
    tipo = tipo_do_documento(pdf_path)
    return _PROMPT_POR_TIPO_DOC[tipo]


# ─────────── FIM DO CORTE SILENCIOSO — 01/Ago/2026 ───────────
# O analisador cortava o artigo em 40.000 caracteres e seguia sem avisar. Medido no acervo real:
#   KDIGO 2026 Diabetes (183 pág, 452.404 chars) → lidos 8,8%
#   AHA/ACC/ADA/ASN 2026 (109 pág, 641.116 chars) → lidos 6,2%
# A perícia saía inteira e convincente sobre 6% do documento. Provado em 01/Ago que o corte NÃO era
# limite de tecnologia: a diretriz da SBC de 130 páginas (246.542 tokens) foi lida INTEIRA pelos 4
# modelos, e saiu perícia com 108 tabelas em 70 s por US$ 0,42. O corte era entulho.
# Fica um teto de SEGURANÇA (não de qualidade) — e, se ele morder, o fato é REGISTRADO, nunca calado.
TETO_SEGURANCA_CHARS = 1_200_000


def texto_para_pericia(texto):
    """Devolve (texto, aviso). O aviso vai para o veredito e para o canônico — corte nunca é silencioso."""
    if len(texto) <= TETO_SEGURANCA_CHARS:
        return texto, ""
    aviso = (f"⚠️ DOCUMENTO TRUNCADO: {len(texto):,} caracteres, teto de segurança "
             f"{TETO_SEGURANCA_CHARS:,} — a perícia cobre {100*TETO_SEGURANCA_CHARS//len(texto)}% do texto.")
    return texto[:TETO_SEGURANCA_CHARS], aviso


_RE_NOTA_APLIC = re.compile(r"Nota\s+(\d{1,2})/10")
_RE_NOTA_RIGOR = re.compile(r"Rigor\s+(\d{1,2})/10")


def conferir_veredito(ver, contexto=None):
    """TRAVA DO VEREDITO VAZIO — 01/Ago/2026.

    POR QUE EXISTE (medido, não suposto): num teste com `{fatos}` e `{veredito}` VAZIOS,
    3 de 4 modelos (sonnet-5, terra, opus-4-8) **inventaram as duas notas** e escreveram a perícia
    inteira como se elas fossem do motor. Só o gpt-5.6-sol percebeu e recusou:
        "Não é possível produzir a versão final sem inventar as duas notas obrigatórias."
    Em produção o motor preenche — MAS basta o veredito falhar uma vez para a nota publicada ser
    ficção. A nota é o coração do produto: ela não pode depender da honestidade do modelo do dia.

    Aqui o veredito é conferido ANTES de gastar token: sem as duas notas legíveis, ninguém é chamado.
    Levanta ValueError → o artigo volta pra fila (não vira perícia com nota inventada)."""
    v = (ver or "").strip()
    if not v:
        raise ValueError("VEREDITO VAZIO: o motor não devolveu veredito — perícia NÃO será gerada "
                         "(3 de 4 modelos inventam as notas quando ele falta; medido 01/Ago/2026).")
    if "SEM NOTA" in v:                       # rota fora da escala clínica: legítimo, mas não peria
        raise ValueError(f"SEM NOTA ({v[:80]}): artigo fora da escala clínica não gera perícia.")
    ma, mr = _RE_NOTA_APLIC.search(v), _RE_NOTA_RIGOR.search(v)
    if not (ma and mr):
        raise ValueError(f"VEREDITO ILEGÍVEL (faltam as duas notas): {v[:160]!r}")
    a, g = int(ma.group(1)), int(mr.group(1))
    if not (0 <= a <= 10 and 0 <= g <= 10):
        raise ValueError(f"VEREDITO COM NOTA FORA DA ESCALA: aplicabilidade={a}, rigor={g}")
    if contexto is not None and v not in contexto:
        raise ValueError("VEREDITO NÃO CHEGOU AO CONTEXTO: o modelo receberia a ordem de usar as "
                         "notas do contexto, e o contexto não as tem.")
    return a, g


def _gerar(prompt_file, contexto, max_tokens):
    """Gera um entregável via CLIENTE UNIFICADO (cadeia ESCRITA cross-provider) REAPROVEITANDO o CONTEXTO
    do artigo (prompt caching): o bloco 'contexto' entra 1x e os próximos leem a ~10%. A instrução vai à parte."""
    _carregar_env()
    import llm_client, modelos as M
    llm_client.contexto_uso(etapa=prompt_file.replace("_prompt.md", "").replace(".md", ""))   # p/ o log de uso
    p = open(os.path.join(_HERE, prompt_file)).read()
    instrucao = (p.replace("{fatos}", "(use os FATOS do contexto acima)")
                  .replace("{veredito}", "(use o VEREDITO do contexto acima)")
                  .replace("{article_text}", "(use o TEXTO do contexto acima)"))
    # PISO DE TAMANHO: saída vazia/truncada não pode passar como boa. RETENTAMOS 1x antes de desistir — é a
    # rede de segurança contra o retorno vazio pontual (foi o que derrubava o ACRI; NÃO era thinking, medido 27/07).
    minimo = 3000 if prompt_file.startswith("redator_") else \
        {"acri_prompt.md": 400, "script_audio_prompt.md": 900,
         "script_audio_diretriz_prompt.md": 3000}.get(prompt_file, 1)
    # A PERÍCIA tem cadeia própria (gpt-5.6-terra), decidida por medição em 01/Ago. O resto
    # (ACRI, roteiro de áudio, gancho) segue na ESCRITA — não foram testados, não se mexe às cegas.
    cadeia = M.PERICIA if prompt_file.startswith("redator_") else M.ESCRITA
    txt, n = "", 0
    for tentativa in (1, 2):
        txt = llm_client.gerar(cadeia, instrucao, contexto=contexto, max_tokens=max_tokens, temperatura=0.4)
        n = len((txt or "").strip())
        if n >= minimo:
            return txt
    raise ValueError(f"{prompt_file}: saída CURTA demais ({n} chars, mínimo {minimo}) — "
                     f"modelo {llm_client._ULTIMO_MODELO[0]}, max_tokens={max_tokens} (após 2 tentativas).")


def _peca(dst, nome, minimo, gerar):
    """RETOMADA POR ENTREGÁVEL: só (re)gera o que ainda NÃO existe e passa o tamanho mínimo. Um artigo que
    morreu no gancho (a última peça) reaproveita extração/ACRI/perícia já pagas — não refaz do zero.
    Mesma régua de tamanho do _conferir_entregaveis."""
    caminho = os.path.join(dst, nome)
    if os.path.exists(caminho) and os.path.getsize(caminho) >= minimo:
        # 04/Ago — O CARIMBO MANDA. Antes bastava o arquivo existir para ser reaproveitado, e o
        # prompt que o gerou podia ser de duas horas atrás. Pergunta do Dr. Eduardo: *"ele está
        # aproveitando um monte de coisas que já tinham sido feitas — POR QUAL PROMPT?"*. Ninguém
        # sabia. Agora sabe: se o prompt desta peça mudou, ela é REFEITA.
        # (o carimbo já foi conferido lá em cima: se o prompt mudou, este arquivo nem existe mais)
        print(f"       ↻ {nome.split('_')[-1]} já pronto — reaproveitado (não regera)")
        return open(caminho, encoding="utf-8").read()
    txt = gerar()
    open(caminho, "w", encoding="utf-8").write(txt)
    return txt


def processar(pdf, staging):
    """Corrente por artigo. Só gera o que a porta liberou (economiza geração cara). Grava no STAGING.
    RETOMÁVEL por entregável: reaproveita peças já geradas (fatos, canônico, ACRI, perícia, PDF, visual, áudio)."""
    import shutil, glob, llm_client
    import analise as A, notas_prototipo as N, pipeline as P
    base = os.path.splitext(os.path.basename(pdf))[0]
    llm_client.contexto_uso(artigo=base)                       # p/ o log de uso (uso.jsonl) saber o artigo
    dst = os.path.join(staging, base); os.makedirs(dst, exist_ok=True)

    # ═══════════ TERRA ARRASADA — 04/Ago/2026 ═══════════
    # Ordem do Dr. Eduardo, depois de perguntar "por qual prompt?" e descobrir que ninguém sabia:
    #     *"se não tem certeza que foi com ESTE prompt, tem que apagar TUDO — tudo, tudo — que tiver
    #      deste artigo no sistema e começar do zero."*
    #
    # Ele está certo, e é mais simples do que o que eu estava construindo (refazer peça por peça).
    # Reaproveitamento PARCIAL é o que sangrou este projeto a noite inteira: sobra uma peça velha,
    # ela é internamente coerente, ninguém percebe, e o conserto não pega. Aqui não tem meio-termo:
    # se o carimbo não bater EXATAMENTE, o pacote inteiro vai embora e o artigo recomeça.
    #
    # Sem carimbo (`_versoes.json` ausente) = staging anterior a 04/Ago = feito por prompt
    # desconhecido = APAGA. Custa uma re-análise, uma vez só, e é de propósito.
    _vnow = versoes_atuais(pdf)
    _vold = versoes_gravadas(dst)
    _tem_coisa = bool(glob.glob(os.path.join(dst, "*")))
    if _tem_coisa and _vold != _vnow:
        _difs = ([f"{k}: {_vold.get(k,'—')} → {v}" for k, v in _vnow.items() if _vold.get(k) != v]
                 if _vold else ["sem carimbo: staging anterior a 04/Ago, prompt desconhecido"])
        print(f"       🔥 TERRA ARRASADA — {len(_difs)} prompt(s) mudaram; apagando o pacote inteiro:")
        for d in _difs[:5]:
            print(f"          · {d}")
        for _p in glob.glob(os.path.join(dst, "*")):
            shutil.rmtree(_p, ignore_errors=True) if os.path.isdir(_p) else os.remove(_p)

    # FATOS cacheados no staging → retoma a extração (a etapa de maior input). Só extrai se não houver cache.
    fatos_cache = os.path.join(dst, base + "_fatos.json")
    fatos = None
    if os.path.exists(fatos_cache) and os.path.getsize(fatos_cache) > 50:
        cache = json.load(open(fatos_cache, encoding="utf-8"))
        # SÓ reaproveita se o cache tem o schema ATUAL **DO TIPO DESTE DOCUMENTO** (LEI 8).
        #
        # ⚠️ O BURACO QUE ISTO FECHA (achado em 02/Ago, ANTES do lote — teria estragado a rodada
        # inteira em silêncio). Desde 02/Ago cada tipo tem um EXTRATOR e um SCHEMA próprios:
        #   diretriz → bloco `agree` + contagem de classe/nível   ·   revisão → bloco `qualidade_revisao`
        # O cheque antigo perguntava só por 'fracao_ejecao', que é campo do schema do ARTIGO ORIGINAL.
        # Consequência: um artigo que o classificador NOVO move para GUIDELINES, mas que já tinha
        # staging da rodada antiga, traria os fatos VELHOS (com 'fracao_ejecao') — o cache seria dado
        # como bom, o extrator da diretriz NUNCA rodaria, e o motor AGREE receberia zero fatos.
        # Resultado: rigor 5 por prudência em TODA diretriz e TODA revisão do lote, sem nenhum aviso.
        tipo_doc = tipo_do_documento(pdf)
        _CHAVE_DO_TIPO = {"diretriz": "agree", "revisao_narrativa": "qualidade_revisao",
                  "meta": "qualidade_meta"}   # 04/Ago: a meta ganhou schema próprio
        chave = _CHAVE_DO_TIPO.get(tipo_doc, "fracao_ejecao")
        if chave in cache:
            fatos = cache
            print("       ↻ fatos reaproveitados (staging) — não re-extrai")
        else:
            print(f"       ↻ cache SEM o schema de '{tipo_doc}' (falta '{chave}') — re-extraindo")
    reextraiu = False
    if fatos is None:
        fatos = A.extrair_fatos(pdf, tipo=tipo_do_documento(pdf))
        # 04/Ago 04h30 — A LINHA FORA DE ORDEM QUE JOGAVA A RODADA INTEIRA FORA.
        # O `tipo_documento` era gravado 20 linhas ABAIXO, depois deste json.dump. Ou seja: NUNCA
        # entrava no arquivo. E é justamente o campo que a `_staging_serve` procura para decidir se
        # um staging pode ser reaproveitado. Resultado medido nos 6 artigos em disco: TODOS davam
        # "staging é de 'antes de 03/Ago'" e seriam RE-ANALISADOS na próxima Chave 2.
        # O Dr. Eduardo teria pago duas vezes por 24 metas, e depois duas vezes por 431.
        fatos["tipo_documento"] = tipo_do_documento(pdf)
        json.dump(fatos, open(fatos_cache, "w", encoding="utf-8"), ensure_ascii=False)
        reextraiu = True
    if reextraiu:
        # FATOS NOVOS → todos os derivados (canônico/ACRI/perícia/PDF/visual/áudio/ficha) estão OBSOLETOS:
        # foram feitos com fatos/nota/prompts VELHOS (ICFER, nota sem teto LEI 0). Apaga p/ regerar limpo —
        # senão o _peca reusa a perícia velha e o conserto não pega. (buraco de reuso, 27/07)
        for nome in (base + "_CANONICO.md", base + "_ACRI.txt", base + "_analise.md",
                     base + "_analise.pdf", base + "_analise.html", base + "_visual.png",
                     base + "_audio.mp3", base + "_gancho_abertura.txt",
                     "_SITE.json", "_OK", "_REVISAR_publicacao.txt"):
            try: os.remove(os.path.join(dst, nome))
            except OSError: pass
        shutil.rmtree(os.path.join(dst, "assets"), ignore_errors=True)
        print("       ↻ derivados velhos apagados (re-extração) — regerando limpos")
    # ═══ A PASTA MANDA NO MOTOR TAMBÉM (03/Ago/2026) ═══
    # Não bastava consertar o prompt: o MOTOR também escolhia a régua pelo campo `desenho` dos
    # fatos. Um artigo que o Dr. Eduardo move para REVISOES tem de ser julgado pelo motor da
    # REVISÃO — não pelo motor do artigo original só porque o extrator leu `desenho=rct`.
    # Injetar aqui é o que faz `notas_prototipo.tipo_do_documento()` obedecer à pasta:
    # ela lê `fatos["tipo_documento"]` ANTES de olhar `desenho`.
    fatos["tipo_documento"] = tipo_do_documento(pdf)
    r = N.score(fatos)
    ents, sobe = decidir_entregaveis(r["aplic"], fatos.get("tipo_documento"))
    # ROTA FORA DA ESCALA CLÍNICA (01/Ago/2026): pré-clínico e 'não classificável' não recebem nota —
    # 'Rigor None/10' seria mentira com cara de número. Diz-se o que é: por que não há nota.
    # VEREDITO ABERTO (02/Ago/2026): o redator deixa de receber o NÚMERO NU e passa a receber os
    # DOMÍNIOS MEDIDOS que o produziram. Medido em 02/Ago com a mesma revisão narrativa e dois
    # vereditos inventados (6/10 e 9/10): 86% dos parágrafos mudaram, e o MESMO fato foi usado para
    # justificar as duas notas opostas. O número nu era o volante da perícia inteira.
    ver = N.veredito_completo(r)
    texto = "".join(p.get_text() for p in fitz.open(pdf))
    texto, aviso_corte = texto_para_pericia(texto)
    if aviso_corte:
        print(f"       {aviso_corte}")
        ver += f" | {aviso_corte}"

    # CONTEXTO COMPARTILHADO — reaproveitamento p/ gastar menos tokens (exigência do Dr. Eduardo).
    # O artigo entra UMA vez, fica em cache, e ACRI/redator/áudio reusam a ~10% do custo.
    contexto = ("CONTEXTO DO ARTIGO — use SOMENTE o que está aqui.\n\n"
                f"FATOS (dado canônico):\n{json.dumps(fatos, ensure_ascii=False, indent=1)}\n\n"
                f"VEREDITO DO MOTOR (use estes números, não invente outros — e EXPLIQUE as notas a "
                f"partir dos domínios medidos abaixo, nunca a partir do dígito):\n{ver}\n\n"
                f"TEXTO DO ARTIGO:\n{texto}")   # INTEIRO (o corte de 40k caiu em 01/Ago — ver texto_para_pericia)

    # TRAVA DO VEREDITO (01/Ago/2026): confere ANTES de qualquer chamada de LLM. Só as peças que
    # CITAM as notas dependem disto (perícia, ACRI, áudio) — e são justamente as que vão ao assinante.
    if sobe:
        conferir_veredito(ver, contexto)

    can = os.path.join(dst, base + "_CANONICO.md")             # canônico SEMPRE (retido ou publicado); reaproveita se já existe
    if not (os.path.exists(can) and os.path.getsize(can) >= 200):
        P.registro_canonico(pdf, fatos)                        # MESMOS fatos/nota da porta
        shutil.move(os.path.join(_HERE, base + "_CANONICO.md"), can)

    if sobe:                                                   # ≥6
        _peca(dst, base + "_ACRI.txt",    400,  lambda: _gerar("acri_prompt.md", contexto, 8000))
        # PERÍCIA POR TIPO (01/Ago): o prompt sai dos FATOS, não é mais um só para todos.
        # 32k de saída: medido em 01/Ago, o maior gasto real foi 22.455 tokens (Sonnet na diretriz
        # de 130 páginas, e ~15k disso era raciocínio). 32k dá folga sem truncar.
        prompt_pericia = escolher_prompt(fatos, pdf)
        print(f"       perícia: {prompt_pericia}  (desenho={fatos.get('desenho')})")
        _peca(dst, base + "_analise.md", 3000,  lambda: _gerar(prompt_pericia, contexto, 32000))
        if not (os.path.exists(os.path.join(dst, base + "_analise.pdf"))
                and os.path.getsize(os.path.join(dst, base + "_analise.pdf")) >= 10000):
            try:                                               # PDF da análise crítica (peça central do site)
                from pdf_analise import gerar_pdf_de_pasta
                gerar_pdf_de_pasta(dst)
            except Exception as e:
                print(f"       ⚠️  PDF da análise não gerado ({type(e).__name__}: {e}) — rende na Mac")
    _diretriz = eh_diretriz(fatos.get("tipo_documento"))
    if r["aplic"] >= 7 or _diretriz:                           # Visual Abstract — diretriz SEMPRE (05/Ago)
        if os.path.exists(os.path.join(dst, base + "_visual.png")) and \
           os.path.getsize(os.path.join(dst, base + "_visual.png")) >= 50000:
            print("       ↻ Visual Abstract já pronto — reaproveitado")
        else:
            try:
                _gerar_visual_abstract(fatos, r, dst, base)
            except Exception as e:
                print(f"       ⚠️  Visual Abstract não gerado ({type(e).__name__}: {e}) — rende na Mac")
    if r["aplic"] >= 8 or _diretriz:                           # áudio — diretriz SEMPRE (05/Ago)
        from voz_utils import cacar_ingles, falar
        mp3 = os.path.join(dst, base + "_audio.mp3")
        if os.path.exists(mp3) and os.path.getsize(mp3) >= 100000:
            print("       ↻ áudio já pronto — reaproveitado")
        else:
            # 05/Ago — ÁUDIO POR TIPO. A diretriz ganhou roteiro próprio, LONGO (6-8 min, 900-1200
            # palavras, contra ~500 do artigo) e com uma obrigação que os outros não têm: dizer a
            # NOTA e a JUSTIFICATIVA dela. Ordem do Dr. Eduardo: uma diretriz sobe mesmo com nota
            # baixa, e o ouvinte precisa saber por que ela é fraca e por que mesmo assim importa.
            _pa = "script_audio_diretriz_prompt.md" if _diretriz else "script_audio_prompt.md"
            _min = 3000 if _diretriz else 900
            roteiro = _peca(dst, base + "_roteiro_audio.txt", _min, lambda: _gerar(_pa, contexto, 16000 if _diretriz else 8000))
            if cacar_ingles(roteiro):
                open(os.path.join(dst, "_REVISAR_termos_ingles.txt"), "w").write(", ".join(cacar_ingles(roteiro)))
            falar(roteiro, mp3)                                # config do .env; ElevenLabs = só Radar
        try:                                                   # gancho de abertura (distribuição diária) — no PORTÃO, não por fora
            _peca(dst, base + "_gancho_abertura.txt", 20,
                  lambda: _gerar("gancho_abertura_prompt.md", contexto, 2000).strip()[:200])
        except Exception as e:
            print(f"       ⚠️  gancho de abertura não gerado ({type(e).__name__}: {e})")
    _conferir_entregaveis(dst, base, r["aplic"], fatos.get("tipo_documento"))  # BURACO ZERO: faltou algo → erro, volta pra fila
    json.dump(_vnow, open(os.path.join(dst, "_versoes.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)                   # QUAL prompt fez cada peça deste pacote
    open(os.path.join(dst, "_OK"), "w").write("")             # só aqui: artigo COMPLETO de verdade
    return base, r["aplic"], r["muda_conduta"], ents, sobe


def _conferir_entregaveis(dst, base, nota, tipo_doc=None):
    """BURACO ZERO no nível do artigo: só é 'pronto' se TUDO que a porta manda existir e ter tamanho.
    Antes o _OK era escrito mesmo faltando peça (ex.: nota ≥7 sem Visual Abstract), e o artigo saía da
    fila incompleto — depois era recusado no Publicador. Agora falha aqui e volta pra fila."""
    def _ok(padrao, minimo):
        import glob
        achados = glob.glob(os.path.join(dst, padrao))
        return any(os.path.getsize(a) >= minimo for a in achados)

    faltando = []
    if not _ok(base + "_CANONICO.md", 200):
        faltando.append("canônico")
    _dir = eh_diretriz(tipo_doc)
    if nota >= 6 or _dir:
        if not _ok(base + "_ACRI.txt", 400):      faltando.append("ACRI")
        if not _ok(base + "_analise.md", 3000):   faltando.append("perícia (≥3k)")
        if not _ok(base + "_analise.pdf", 10000): faltando.append("PDF da perícia")
    if (nota >= 7 or _dir) and not _ok(base + "_visual.png", 50000):
        faltando.append("Visual Abstract")
    if (nota >= 8 or _dir) and not _ok(base + "_audio.mp3", 100000):
        faltando.append("áudio")
    if faltando:
        raise RuntimeError(f"INCOMPLETO (nota {nota}) — faltou: {', '.join(faltando)}. "
                           f"Artigo volta pra fila (buraco zero).")


def _gerar_visual_abstract(fatos, r, dst, base):
    """≥7: gera o Visual Abstract de 8 seções — o ÚNICO visual permitido (CLAUDE.md) — pelo gerador
    OFICIAL do FULL (Claude + Playwright, template de 8 seções). Automático, sem NotebookLM.
    Ponte de nomes: a perícia (_analise.md) vira analysis.md (entrada do gerador); o PNG sai em
    assets/visual_abstract.png e é copiado p/ <base>_visual.png (onde a ficha_site procura: *_visual*)."""
    import shutil
    from pathlib import Path
    # ═══ 06/Ago — O VISUAL ABSTRACT ERA O ÚLTIMO PONTO OLHANDO O `desenho` DOS FATOS ═══
    #
    # A LEI 8 diz, com todas as letras: *"o tipo é decidido UMA vez, no classificador, e todo o
    # resto OBEDECE"*, e o CLAUDE.md nomeia exatamente este defeito — *"a escolha do prompt olhava
    # a PASTA e a escolha do motor olhava o campo `desenho` dos FATOS"*. Em 03/Ago consertamos o
    # prompt e o motor. O Visual Abstract ficou com a fonte velha, e ninguém notou porque ele não
    # quebra: ele escolhe o molde errado e desenha bonito.
    #
    # MEDIDO em 06/Ago, no lote das revisões: `📋 Tipo detectado: artigo original` em 48 de 48.
    # O extrator da revisão não preenche `desenho` (o log mostra `desenho=None` em toda linha),
    # `None` vira `""`, `""` não casa com "revis", e o else entrega "original". Resultado: 48 cards
    # de revisão narrativa desenhados com o molde de RCT — MÉTODOS, POPULAÇÃO, PRINCIPAIS
    # RESULTADOS, "NNT não calculável" — numa peça que não tem população nem desfecho.
    #
    # SEGUNDO DEFEITO, EMPILHADO: o vocabulário não batia. Aqui se diz `revisao_narrativa` (é o que
    # `_TIPO_POR_PASTA` grava); o gerador só reconhece `("metanalise", "revisao")`. Mesmo recebendo
    # o tipo certo, ele cairia no `_detectar_tipo_artigo` — o adivinhador. Por isso o `.get` abaixo
    # TRADUZ, em vez de repassar cru.
    # A fonte é `fatos["tipo_documento"]` — o campo que o analisador grava A PARTIR DA PASTA
    # (LEI 8) e que o motor usa para escolher qual dos 4 motores roda. É a MESMA fonte, e é isso
    # que faz dela a certa: uma pergunta, uma resposta, um lugar.
    _TIPO_P_VISUAL = {"meta": "metanalise", "revisao_narrativa": "revisao",
                      "diretriz": "revisao", "original": "original"}
    _td = (fatos.get("tipo_documento") or "").strip().lower()
    tipo = _TIPO_P_VISUAL.get(_td, "original")
    ana = os.path.join(dst, base + "_analise.md")
    if os.path.exists(ana):
        shutil.copy(ana, os.path.join(dst, "analysis.md"))     # o gerador lê analysis.md da pasta
    os.makedirs(os.path.join(dst, "assets"), exist_ok=True)
    from infographics.visual_abstract_generator import VisualAbstractGenerator
    va = VisualAbstractGenerator().gerar_png(Path(dst), canonical_type=tipo, upload_supabase=False)
    if va and Path(str(va)).exists():
        shutil.copy(str(va), os.path.join(dst, base + "_visual.png"))   # onde a ficha_site/contrato procuram


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--gabarito":
        # DEMO: aplica as portas às notas conhecidas do gabarito
        import notas_prototipo as N
        print(f"{'ARTIGO':22} {'NOTA':>4}  {'STATUS':6}  ENTREGÁVEIS")
        print("-"*78)
        for nome, a in N.FIXTURES.items():
            gab = a.get("gabarito")
            nota = int(str(gab).split("-")[0]) if isinstance(gab, str) else gab
            ents, sobe = decidir_entregaveis(nota)
            status = "SOBE" if sobe else "FICA"
            print(f"{nome:22} {nota:>4}  {status:6}  {' + '.join(ents)}")
    else:
        import argparse
        ap = argparse.ArgumentParser(description="Analisador (Elo 4) — lê CLASSIFICADOS/, grava no staging")
        ap.add_argument("pasta", help="pasta CLASSIFICADOS (percorre as subpastas de tipo)")
        ap.add_argument("--max", type=int, default=0, help="processar no máximo N artigos (teste)")
        a = ap.parse_args()
        pasta = os.path.expanduser(a.pasta)
        # STAGING dentro do FULL (outputs/STAGING) — GOLDEN GATE: gera local, não sobe (é do publicador)
        staging = os.path.abspath(os.path.join(_HERE, "..", "outputs", "STAGING"))
        # percorre as subpastas (ARTIGOS_ORIGINAIS, META_ANALISES, GUIDELINES, ...)
        pdfs = []
        for root, _, files in os.walk(pasta):
            for f in sorted(files):
                if f.lower().endswith(".pdf") and not f.startswith("._"):
                    pdfs.append(os.path.join(root, f))
        pdfs = sorted(pdfs)
        if a.max:
            pdfs = pdfs[:a.max]
        print(f"ANALISADOR — {len(pdfs)} artigo(s)  →  {staging}")
        print("(GOLDEN GATE: revise o staging antes de publicar)\n")
        for pdf in pdfs:
            base = os.path.splitext(os.path.basename(pdf))[0]
            if os.path.exists(os.path.join(staging, base, "_OK")):   # RETOMÁVEL: pula os já concluídos
                print(f"  {base[:46]:46} ⏭️  já pronto (pulado)")
                continue
            try:
                base, nota, mc, ents, sobe = processar(pdf, staging)
                print(f"  {base[:46]:46} nota {nota:>2} · {'SOBE' if sobe else 'FICA'} · {' + '.join(ents)}")
            except Exception as e:
                print(f"  ⚠️  {os.path.basename(pdf)[:46]:46} ERRO: {type(e).__name__}: {e}")
