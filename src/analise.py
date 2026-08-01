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
        "keywords": {"type": "array", "items": {"type": "string"}},
        "relevancia_clinica": {
            "type": "object",
            "properties": {
                "desfecho_primario": _S, "tipo_desfecho": _S, "efeito_observado": _S,
                "mcid_reportado": _B, "mcid_valor": _S, "mcid_fonte_metodo": _S,
                "para_desfecho_duro": _S,
                "efeito_excede_limiar": {"type": ["boolean", "null"]},
                "ic_sustenta_relevancia": {"type": ["boolean", "null"]},
                "classificacao": {"type": "string",
                                  "enum": ["robusto", "provavel", "incerto",
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


def extrair_fatos(pdf_path):
    """FATOS do artigo via SAÍDA ESTRUTURADA (tool use): a API obriga o modelo a devolver o objeto
    no formato do SCHEMA_FATOS. JSON malformado / campo faltando deixa de ser possível — é a correção
    ESTRUTURAL da causa que derrubou 74% do run de 25/07 (antes: pedia JSON em texto e torcia).
    Rede: se o tool use falhar (provedor sem suporte), cai no caminho de texto + parsing tolerante."""
    texto = "".join(p.get_text() for p in fitz.open(pdf_path))[:48000]
    import llm_client, modelos as M
    llm_client.contexto_uso(etapa="extracao")                  # p/ o log de uso
    prompt = PROMPT.replace("{article_text}", texto)
    try:
        return llm_client.gerar_json(M.EXTRACAO, prompt, SCHEMA_FATOS,
                                     max_tokens=8000, nome="extrair_fatos")
    except Exception as e:
        print(f"       ↻ saída estruturada indisponível ({type(e).__name__}); tentando modo texto…")
    ultimo = ""
    for tentativa in (1, 2):
        raw = llm_client.gerar(M.EXTRACAO, prompt, max_tokens=8000, temperatura=0).strip()
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
