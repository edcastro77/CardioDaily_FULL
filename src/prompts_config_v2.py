"""
prompts_config_v2.py — CASCA reconstruída (06/Jul/2026, branch lab/religar-prompts).

O arquivo original se perdeu com o Mac (é casca pura: lê os .md e os expõe). A interface
foi reconstruída FIELMENTE a partir do que article_analyzer.py espera (linhas 1380-1387):

    from prompts_config_v2 import PROMPTS, get_prompt, validate_prompts
      - PROMPTS: dict {tipo_canonico: texto_do_prompt}
      - get_prompt(tipo): resolve aliases e devolve o texto (None se não houver)
      - validate_prompts(): {tipo: {'exists': bool, 'length': int, 'file': str}}

MAPEAMENTO (decisão do Dr. Eduardo, 06/Jul/2026):
    artigo_original → v3 (RIGOROSO: TETO POR DESENHO + regra 0b + MCID) — o oficial.
    os outros 4     → v2 (ainda SEM o teto por desenho; é o furo do CABG, a tampar no elo 4).

Aliases espelham exatamente o dict prompt_key_aliases de article_analyzer.py.
"""
import os

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_PROMPTS_DIR = os.path.join(_THIS_DIR, "prompts")

# tipo canônico -> arquivo .md em src/prompts/
_PROMPT_FILES = {
    "artigo_original": "prompt_artigo_original_v3.md",              # v3 rigoroso (oficial)
    "revisao_sistematica_meta_analise": "prompt_meta_analise_v2.md",
    "revisao_geral": "prompt_revisao_geral_v2.md",
    "guideline": "prompt_guideline_v2.md",
    "ponto_de_vista": "prompt_ponto_de_vista_v2.md",
}

# alias -> tipo canônico
_ALIASES = {
    "original": "artigo_original",
    "artigo": "artigo_original",
    "artigo-original": "artigo_original",
    "metanalise": "revisao_sistematica_meta_analise",
    "meta_analise": "revisao_sistematica_meta_analise",
    "meta_analises": "revisao_sistematica_meta_analise",
    "meta-analise": "revisao_sistematica_meta_analise",
    "revisao_sistematica": "revisao_sistematica_meta_analise",
    "revisao_sistematica_metaanalise": "revisao_sistematica_meta_analise",
    "revisao": "revisao_geral",
    "review": "revisao_geral",
    "revisao_narrativa": "revisao_geral",
    "diretriz": "guideline",
    "guidelines": "guideline",
    "consenso": "guideline",
    "editorial": "ponto_de_vista",
    "perspectiva": "ponto_de_vista",
    "viewpoint": "ponto_de_vista",
}


def _load_one(filename):
    path = os.path.join(_PROMPTS_DIR, filename)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _build_prompts():
    prompts = {}
    for tipo, filename in _PROMPT_FILES.items():
        try:
            prompts[tipo] = _load_one(filename)
        except FileNotFoundError:
            prompts[tipo] = ""  # ausente: fica vazio; validate_prompts() sinaliza
    return prompts


PROMPTS = _build_prompts()


def _canonical(tipo):
    if tipo in PROMPTS:
        return tipo
    return _ALIASES.get(tipo, tipo)


def get_prompt(tipo):
    """Texto do prompt para o tipo (resolvendo aliases). None se não houver."""
    if not tipo:
        return None
    texto = PROMPTS.get(_canonical(tipo))
    return texto or None


def validate_prompts():
    """Status de cada prompt: {tipo: {'exists': bool, 'length': int, 'file': str}}."""
    status = {}
    for tipo, filename in _PROMPT_FILES.items():
        texto = PROMPTS.get(tipo, "")
        status[tipo] = {"exists": bool(texto), "length": len(texto), "file": filename}
    return status


if __name__ == "__main__":
    # smoke test (não chama nenhuma API): python src/prompts_config_v2.py
    st = validate_prompts()
    for tipo, s in st.items():
        marca = "OK " if s["exists"] and s["length"] > 1000 else "!! "
        print(f"  [{marca}] {tipo:38s} {s['length']:6d} chars  ({s['file']})")
    faltando = [t for t, s in st.items() if not s["exists"]]
    print(f"\nTotal: {len(PROMPTS)} prompts. artigo_original usa o V3 (rigoroso).")
    print("Faltando:" , faltando if faltando else "nenhum")
