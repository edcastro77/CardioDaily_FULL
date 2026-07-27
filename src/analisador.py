"""
analisador.py — O APP ANALISADOR (Elo 4), autocontido e modular.
Lê CLASSIFICADOS/<tipo>/ → por artigo: analise → notas → registro canônico → entregáveis POR LIMIAR
→ grava tudo LOCAL numa pasta de STAGING. NÃO sobe (é do publicador). NÃO limpa (é do arquivador).

PORTAS (Dr. Eduardo):  ≤5 fica · ≥6 sobe (canônico+ACRI+texto) · ≥7 +infográfico · ≥8 +áudio
Uso:  python analisador.py <pasta_CLASSIFICADOS>        (roda a corrente)
      python analisador.py --gabarito                   (só mostra a lógica das portas)
"""
import os, sys, json, fitz

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
    minimo = {"redator_prompt.md": 3000, "acri_prompt.md": 400, "script_audio_prompt.md": 900}.get(prompt_file, 1)
    txt, n = "", 0
    for tentativa in (1, 2):
        txt = llm_client.gerar(M.ESCRITA, instrucao, contexto=contexto, max_tokens=max_tokens, temperatura=0.4)
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
    if os.path.exists(fatos_cache) and os.path.getsize(fatos_cache) > 50:
        fatos = json.load(open(fatos_cache, encoding="utf-8"))
        print("       ↻ fatos reaproveitados (staging) — não re-extrai")
    else:
        fatos = A.extrair_fatos(pdf)
        json.dump(fatos, open(fatos_cache, "w", encoding="utf-8"), ensure_ascii=False)
    r = N.score(fatos)
    ents, sobe = decidir_entregaveis(r["aplic"])
    ver = (f"Nota {r['aplic']}/10 | Rigor {r['trabalho']}/10 | Muda conduta {r['muda_conduta']} | "
           f"delatores: {', '.join(r['flags']) or 'nenhum'}")
    texto = "".join(p.get_text() for p in fitz.open(pdf))

    # CONTEXTO COMPARTILHADO — reaproveitamento p/ gastar menos tokens (exigência do Dr. Eduardo).
    # O artigo entra UMA vez, fica em cache, e ACRI/redator/áudio reusam a ~10% do custo.
    contexto = ("CONTEXTO DO ARTIGO — use SOMENTE o que está aqui.\n\n"
                f"FATOS (dado canônico):\n{json.dumps(fatos, ensure_ascii=False, indent=1)}\n\n"
                f"VEREDITO DO MOTOR (use estes números, não invente outros):\n{ver}\n\n"
                f"TEXTO DO ARTIGO:\n{texto[:40000]}")

    can = os.path.join(dst, base + "_CANONICO.md")             # canônico SEMPRE (retido ou publicado); reaproveita se já existe
    if not (os.path.exists(can) and os.path.getsize(can) >= 200):
        P.registro_canonico(pdf, fatos)                        # MESMOS fatos/nota da porta
        shutil.move(os.path.join(_HERE, base + "_CANONICO.md"), can)

    if sobe:                                                   # ≥6
        _peca(dst, base + "_ACRI.txt",    400,  lambda: _gerar("acri_prompt.md", contexto, 8000))
        _peca(dst, base + "_analise.md", 3000,  lambda: _gerar("redator_prompt.md", contexto, 16000))
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
