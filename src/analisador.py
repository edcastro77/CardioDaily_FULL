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


def decidir_entregaveis(nota):
    """As portas por nota. Devolve (lista_de_entregaveis, sobe?)."""
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


_PROMPT_POR_TIPO_DOC = {
    "original": "redator_original_prompt.md",
    "meta": "redator_meta_prompt.md",
    "diretriz": "redator_guideline_prompt.md",
    "revisao_narrativa": "redator_revisao_prompt.md",
}


def tipo_do_documento(pdf_path=""):
    """O tipo decidido pelo classificador. 'original' é a rede quando não há pasta (teste avulso)."""
    return _TIPO_POR_PASTA.get(os.path.basename(os.path.dirname(pdf_path or "")), "original")


# ⚠️ INCOERÊNCIA AINDA ABERTA (tarefa #34, 02/Ago): para ORIGINAL e META o prompt continua sendo
# escolhido pelo campo `desenho` dos FATOS, e não por esta função. São duas fontes de verdade para a
# mesma pergunta — o que a LEI 8 proíbe. NÃO foi unificado hoje de propósito: fechar tudo na pasta
# transfere 100% da decisão para o classificador, e o classificador corrigido AINDA NÃO ESTÁ EM
# PRODUÇÃO (tarefa #33, produção roda a 91,9%). Unificar antes disso PIORA hoje para melhorar depois.
# A ordem correta é: #33 (classificador em produção) → #34 (unificar aqui). Decisão do Dr. Eduardo.


def escolher_prompt(fatos, pdf_path=""):
    """Qual perícia este documento merece. FATOS mandam; a pasta é o desempate."""
    pasta = os.path.basename(os.path.dirname(pdf_path or ""))
    if pasta in ("GUIDELINES", "REVISOES"):        # tipos que o schema de fatos não distingue
        return _PROMPT_POR_PASTA[pasta]
    d = (fatos or {}).get("desenho")
    if d in _PROMPT_POR_DESENHO:
        return _PROMPT_POR_DESENHO[d]
    if pasta in _PROMPT_POR_PASTA:
        return _PROMPT_POR_PASTA[pasta]
    return "redator_original_prompt.md"            # o mais completo, como rede


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
        {"acri_prompt.md": 400, "script_audio_prompt.md": 900}.get(prompt_file, 1)
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
        _CHAVE_DO_TIPO = {"diretriz": "agree", "revisao_narrativa": "qualidade_revisao"}
        chave = _CHAVE_DO_TIPO.get(tipo_doc, "fracao_ejecao")
        if chave in cache:
            fatos = cache
            print("       ↻ fatos reaproveitados (staging) — não re-extrai")
        else:
            print(f"       ↻ cache SEM o schema de '{tipo_doc}' (falta '{chave}') — re-extraindo")
    reextraiu = False
    if fatos is None:
        fatos = A.extrair_fatos(pdf, tipo=tipo_do_documento(pdf))
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
    r = N.score(fatos)
    ents, sobe = decidir_entregaveis(r["aplic"])
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
    if r["aplic"] >= 7:                                        # Visual Abstract (8 seções) — AUTOMÁTICO
        if os.path.exists(os.path.join(dst, base + "_visual.png")) and \
           os.path.getsize(os.path.join(dst, base + "_visual.png")) >= 50000:
            print("       ↻ Visual Abstract já pronto — reaproveitado")
        else:
            try:
                _gerar_visual_abstract(fatos, r, dst, base)
            except Exception as e:
                print(f"       ⚠️  Visual Abstract não gerado ({type(e).__name__}: {e}) — rende na Mac")
    if r["aplic"] >= 8:                                        # áudio
        from voz_utils import cacar_ingles, falar
        mp3 = os.path.join(dst, base + "_audio.mp3")
        if os.path.exists(mp3) and os.path.getsize(mp3) >= 100000:
            print("       ↻ áudio já pronto — reaproveitado")
        else:
            roteiro = _peca(dst, base + "_roteiro_audio.txt", 900, lambda: _gerar("script_audio_prompt.md", contexto, 8000))
            if cacar_ingles(roteiro):
                open(os.path.join(dst, "_REVISAR_termos_ingles.txt"), "w").write(", ".join(cacar_ingles(roteiro)))
            falar(roteiro, mp3)                                # config do .env; ElevenLabs = só Radar
        try:                                                   # gancho de abertura (distribuição diária) — no PORTÃO, não por fora
            _peca(dst, base + "_gancho_abertura.txt", 20,
                  lambda: _gerar("gancho_abertura_prompt.md", contexto, 2000).strip()[:200])
        except Exception as e:
            print(f"       ⚠️  gancho de abertura não gerado ({type(e).__name__}: {e})")
    _conferir_entregaveis(dst, base, r["aplic"])              # BURACO ZERO: faltou algo → erro, volta pra fila
    open(os.path.join(dst, "_OK"), "w").write("")             # só aqui: artigo COMPLETO de verdade
    return base, r["aplic"], r["muda_conduta"], ents, sobe


def _conferir_entregaveis(dst, base, nota):
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
    if nota >= 6:
        if not _ok(base + "_ACRI.txt", 400):      faltando.append("ACRI")
        if not _ok(base + "_analise.md", 3000):   faltando.append("perícia (≥3k)")
        if not _ok(base + "_analise.pdf", 10000): faltando.append("PDF da perícia")
    if nota >= 7 and not _ok(base + "_visual.png", 50000):
        faltando.append("Visual Abstract")
    if nota >= 8 and not _ok(base + "_audio.mp3", 100000):
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
    des = (fatos.get("desenho") or "").lower()
    tipo = "metanalise" if "meta" in des else ("revisao" if ("revis" in des or "guide" in des or "diretriz" in des) else "original")
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
