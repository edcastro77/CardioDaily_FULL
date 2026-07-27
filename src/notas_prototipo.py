"""
notas_prototipo.py — PROTÓTIPO do bloco `notas` (laboratório, LEI DO CLONE).
Planta: PLANTA_BLOCO_NOTAS.md. Régua-chave:
    aplicabilidade = min(teto_desenho[por tipo de pergunta], teto_validade_externa, nota_estatistica)
O `notas` é DETERMINÍSTICO: recebe FATOS (o dado canônico que o bloco `analise` extrai) e aplica regras.
Aqui os fatos dos 6 artigos estão hard-coded como FIXTURES pra travar a regressão contra o gabarito do Dr. Eduardo.
"""

# ─────────────────────────── AS REGRAS ───────────────────────────

def teto_desenho(a):
    """REGRA 0 — teto POR TIPO DE PERGUNTA (matriz 2×2 do Dr. Eduardo)."""
    q = a["pergunta"]
    if q == "intervencao":
        d = a["desenho"]
        if d == "rct":
            # Nível B (teto 8): sem cegamento, OU poder limítrofe — MAS parada precoce por
            # benefício não conta como "poder ruim" (o benefício foi esmagador). US Carvedilol.
            if a.get("open_label") or (not a.get("poder_ok", True)
                                       and not a.get("parado_cedo_por_beneficio")):
                return 8
            return 10               # Nível A: RCT duro, cegado, poder ok (ou parado por benefício)
        if d == "meta":
            return 8                # meta de RCTs (o Bisturi decide a nota real)
        if d == "observacional_ajustado":
            return 7
        return 6                    # registro sem controle
    # etiologia / prognostico / diagnostico: aquisição de dados impecável = PISO 8.
    # (Sem viés de desfecho: não damos 10 porque a história deu razão. Somos críticos com o método atual;
    #  a excelência da COLETA — codebook, lab calibrado, follow-up — é o que sustenta o 8.)
    # LEI 0 — RETROSPECTIVO NÃO PEGA O PISO 8. O piso 8 é do Framingham: coorte PROSPECTIVA, coleta
    # desenhada antes. Um estudo RETROSPECTIVO (análise secundária/post-hoc, acurácia sobre exames já
    # feitos) é observacional que a régua do CLAUDE.md capa em 7 (Nível C: controle + ajuste) — nunca 8.
    # "Observacional recebendo NAC 8 → ERRADO (teto é 6 ou 7)". Por isso o teto retrospectivo é 7.
    if a.get("retrospectivo"):
        return 7
    if a.get("desenho_apropriado") and a.get("qualidade_entrada") and a.get("follow_up_completo"):
        return 8
    return 7


def teto_externa(a):
    """REGRA 1 — validade externa não-extrapolável = TETO 7 (não desconto).
    Só se aplica a INTERVENÇÃO ('funciona no MEU paciente?'). Etiologia/prognóstico não capam:
    fator de risco biológico generaliza (Framingham=10 mesmo sendo de uma cidade específica)."""
    if a["pergunta"] != "intervencao":
        return 10
    return 7 if not a.get("extrapolavel", True) else 10


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
    fl = []
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
    s, fl = nota_estatistica(a)
    td, te = teto_desenho(a), teto_externa(a)
    aplic = min(td, te, s)               # ← a régua-chave
    return {"trabalho": s, "aplic": aplic, "teto_desenho": td,
            "teto_externa": te, "muda_conduta": muda_conduta(a, aplic), "flags": fl}


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
