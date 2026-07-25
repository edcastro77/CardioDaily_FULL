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


def extrair_fatos(pdf_path):
    texto = "".join(p.get_text() for p in fitz.open(pdf_path))[:48000]
    import llm_client, modelos as M                       # cliente unificado: cadeia EXTRACAO cross-provider
    # teto folgado: o Sonnet 5 tem thinking ligado (consome tokens antes do texto) — 2200 sufocava a saída
    raw = llm_client.gerar(M.EXTRACAO, PROMPT.replace("{article_text}", texto),
                           max_tokens=8000, temperatura=0).strip()
    # robusto: pega o primeiro objeto {...} mesmo se vier com cerca ```json ou preâmbulo ("aqui está o JSON:")
    m = re.search(r"\{.*\}", raw, re.S)
    if not m:
        raise ValueError(f"extração não retornou JSON (modelo={llm_client._ULTIMO_MODELO[0]}, "
                         f"len={len(raw)}): {raw[:200]!r}")
    return json.loads(m.group(0))


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
