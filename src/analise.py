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

# SCHEMA DOS FATOS — contrato de saída estruturada (tool use). A API OBRIGA o modelo a devolver
# exatamente estes campos com estes tipos. JSON malformado ou campo faltando deixa de ser possível.
SCHEMA_FATOS = {
    "type": "object",
    "properties": {
        "titulo": _S, "revista": _S, "ano": _S,
        "pergunta": {"type": "string", "enum": ["intervencao", "etiologia", "prognostico", "diagnostico"]},
        "desenho": {"type": "string", "enum": ["rct", "meta", "coorte", "registro",
                                               "observacional_ajustado", "transversal", "caso_controle"]},
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
    },
    # obrigatórios: o que o motor de rigor e o canônico NÃO podem receber vazio
    "required": ["titulo", "revista", "ano", "pergunta", "desenho", "retrospectivo", "fracao_ejecao", "open_label", "poder_ok",
                 "desfecho_duro", "extrapolavel", "conclusao_nao_bate_desenho", "itt_falso",
                 "qualidade_entrada", "achados_principais", "keywords", "relevancia_clinica",
                 "aplicabilidade"],
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
