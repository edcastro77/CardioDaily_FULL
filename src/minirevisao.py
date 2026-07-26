"""
minirevisao.py — TRILHA DA MINIRREVISÃO / OPINIÃO DE ESPECIALISTA.

Minirevisão NÃO passa pelo motor de rigor (LEI 0 é para ESTUDO original — desenho, randomização,
estatística). Aqui o valor é outro, e é o método do Dr. Eduardo (o "caderno do especialista"):

  1) BASELINE — o que já se sabe: a diretriz VIGENTE do tema (GuidelineLibrary do PESQUISADOR,
     sempre a mais recente). É a "página do caderno" escrita ANTES de ler a revisão.
  2) DELTA — o que a revisão ACRESCENTA além da diretriz: números, valores de corte específicos,
     delimitação do papel de cada opção e, sobretudo, uma ESTRATÉGIA de abordagem aplicável no Brasil.
  3) FAIXA — a "nota" da minirevisão (não é rigor):
       0 = vaselina (só repete recomendação, nada prático novo) → NÃO SOBE
       1 = consolida + acrescenta útil (números, cortes, delimita papel)
       2 = grande interesse (traz um modelo prático de abordagem aplicável, ainda que sem certeza)
  4) ENTREGÁVEL (faixa ≥1) — condutas práticas + FLUXOGRAMA Mermaid da estratégia de abordagem.

Uso:  python minirevisao.py <ARTIGO.pdf> [pasta_saida]
"""
import os, sys, json, subprocess, shutil, tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

# Ponte para a KB de diretrizes do PESQUISADOR (reuso, não reinventa).
_PESQ = "/Users/eduardocastro/projetos/PESQUISADOR/pesquisador_cardiodaily/pesquisador"


def _carregar_env():
    from dotenv import load_dotenv
    d = _HERE
    for _ in range(8):
        cand = os.path.join(d, "CardioDaily_FULL", ".env")
        if os.path.exists(cand):
            load_dotenv(cand, override=True); return
        d = os.path.dirname(d)
    load_dotenv(override=True)


def _texto_pdf(pdf, limite=48000):
    import fitz
    return "".join(p.get_text() for p in fitz.open(pdf))[:limite]


# ─────────────────────────── BASELINE (o que já se sabe) ───────────────────────────

def baseline_do_tema(tema, termos):
    """Diretriz vigente do tema, via GuidelineLibrary do PESQUISADOR. Devolve (texto, fontes)."""
    import modelos as M
    try:
        if _PESQ not in sys.path:
            sys.path.insert(0, _PESQ)
        from guideline_library import GuidelineLibrary
    except Exception as e:
        print(f"       ⚠️  GuidelineLibrary indisponível ({type(e).__name__}: {e}) — segue sem baseline")
        return "", []
    config = {
        "anthropic": {"api_key": os.getenv("ANTHROPIC_API_KEY", ""), "model": M.RAPIDO[0]},
        "guidelines": {"enabled": True, "max_docs": 2, "max_chars_per_doc": 12000},
    }
    try:
        lib = GuidelineLibrary(config)
        texto, usadas = lib.build_context(tema, intencao="conduta prática", terms=termos)
        return texto, [f"{u.get('year','?')} {u.get('society','')} — {u.get('topic','')}" for u in usadas]
    except Exception as e:
        print(f"       ⚠️  baseline falhou ({type(e).__name__}: {e})")
        return "", []


# ─────────────────────────── EXTRAÇÃO (tema + delta + faixa + condutas + Mermaid) ───────────────────────────

_SCHEMA_TEMA = {
    "type": "object",
    "properties": {
        "titulo": {"type": "string"},
        "tema": {"type": "string", "description": "tema clínico curto p/ buscar a diretriz (ex.: 'coarctação de aorta')"},
        "termos": {"type": "array", "items": {"type": "string"},
                   "description": "3-6 termos específicos do tema p/ localizar a seção na diretriz"},
    },
    "required": ["titulo", "tema", "termos"],
}

# LIÇÃO (26/07/2026): o tool-use NÃO força tipo array — o modelo devolve string onde se pede lista e a
# API deixa passar. Então os campos de lista são STRING "uma por linha" (o modelo cumpre bem) e o código
# quebra em lista (`_linhas`). Joga a favor do modelo, não contra. Mais confiável que array de objeto/string.
_SCHEMA_MINIREV = {
    "type": "object",
    "properties": {
        "titulo": {"type": "string"},
        "tema": {"type": "string"},
        "faixa": {"type": "integer", "enum": [0, 1, 2]},
        "faixa_justificativa": {"type": "string",
            "description": "por que 0/1/2: o que a revisão ACRESCENTA (ou não) além da diretriz vigente"},
        "condutas": {"type": "string",
            "description": "condutas práticas acionáveis — UMA POR LINHA, cada linha começando com '- ', "
                           "no imperativo; se útil embuta 'aplicar quando… / evitar quando…' na frase."},
        "delta": {"type": "string",
            "description": "o que a revisão acrescenta ao baseline (números, cortes, papel) — UMA POR LINHA, com '- '"},
        "incertezas": {"type": "string",
            "description": "o que fica em aberto (o 'o que não sei') — UMA POR LINHA, com '- '"},
        "aplicabilidade_brasil": {"type": "string",
            "description": "como implementar aqui / no consultório (SUS, disponibilidade, custo)"},
        "fluxograma_mermaid": {"type": "string",
            "description": "corpo Mermaid 'flowchart TD ...' da ESTRATÉGIA DE ABORDAGEM (não do tratamento). "
                           "Decisões marcadas com :::dec e condutas terminais com :::term. Sem cabeçalho de tema/init."},
    },
    "required": ["titulo", "tema", "faixa", "faixa_justificativa", "condutas", "incertezas", "fluxograma_mermaid"],
}


def _linhas(v):
    """Normaliza um campo (string 'uma por linha' OU lista) numa lista de itens limpos."""
    if isinstance(v, list):
        itens = [str(x) for x in v]
    else:
        itens = str(v or "").splitlines()
    out = []
    for s in itens:
        s = s.strip().lstrip("-•*·").strip()
        s = s.strip()
        if len(s) >= 3:
            out.append(s)
    return out

_PROMPT = """Você é um cardiologista crítico avaliando uma MINIRREVISÃO / opinião de especialista para o CardioDaily.

MÉTODO (o "caderno do especialista"): antes de valorizar a revisão, considere o BASELINE — o que a
DIRETRIZ VIGENTE já recomenda. A revisão só tem valor pelo que ACRESCENTA a isso.

BASELINE (diretriz vigente do tema — pode estar vazio se não houver):
{baseline}

TEXTO DA MINIRREVISÃO:
{texto}

Faça:
1) DELTA — liste o que a revisão acrescenta ALÉM do baseline: números, valores de corte específicos,
   delimitação do papel de cada opção de tratamento/estratégia. Se não acrescenta nada prático, diga.
2) FAIXA — classifique:
   • 0 = "vaselina": só repete a recomendação, sem nada prático novo ("se adulto, o stent é tão bom
     quanto a cirurgia"). NÃO interessa ao CardioDaily.
   • 1 = consolida o conhecimento E acrescenta útil: números, cortes, delimita bem o papel das opções.
   • 2 = grande interesse: traz um MODELO PRÁTICO de abordagem, aplicável no Brasil/consultório, que
     bate o martelo mesmo quando a evidência é fraca ("a evidência é fraca, MAS a estratégia é ESTA").
3) CONDUTAS — extraia as condutas práticas acionáveis (cada uma com quando aplicar / quando não).
4) INCERTEZAS — o que fica em aberto (as dúvidas honestas do especialista).
5) APLICABILIDADE BRASIL — como implementar aqui (SUS, disponibilidade, custo).
6) FLUXOGRAMA (Mermaid) — desenhe a ESTRATÉGIA DE ABORDAGEM do tema (não o tratamento em si) como
   'flowchart TD'. Use rótulos curtos com <b>título</b><br/>detalhe. Marque nós de DECISÃO com :::dec
   e condutas TERMINAIS com :::term. NÃO inclua cabeçalho de tema nem bloco %%{init}%% (eu adiciono o tema).
   Mantenha português, siglas do dia a dia (PA, HAS, TC), e fidelidade ao que a revisão + baseline dizem.

Não invente número que não esteja na revisão ou no baseline. Se a faixa for 0, o fluxograma pode ser mínimo.

IMPORTANTE: preencha CADA campo separadamente. Em `condutas`, `delta` e `incertezas`, escreva UMA POR LINHA,
cada linha começando com '- ' (não use XML, não numere, não escreva um parágrafo corrido). Ao menos 2 condutas
se faixa ≥1. `aplicabilidade_brasil` é um parágrafo curto. `fluxograma_mermaid` é só o corpo 'flowchart TD ...'.
"""

# tema init validado + classes (o layout/tema é NOSSO, não do LLM → consistência garantida)
_MERMAID_TEMA = (
    "%%{init: {'theme':'base','themeVariables':{'fontFamily':'Helvetica, Arial, sans-serif',"
    "'fontSize':'17px','primaryColor':'#eef3fb','primaryTextColor':'#132743',"
    "'primaryBorderColor':'#0B3D91','lineColor':'#2b57ad','clusterBkg':'#f4f7fc'}}}%%\n"
)
_MERMAID_CLASSDEF = (
    "\nclassDef dec fill:#fdeceb,stroke:#C00000,stroke-width:2px,color:#8a0000;"
    "\nclassDef term fill:#ffffff,stroke:#C00000,stroke-width:2.5px,color:#8a0000;\n"
)


def _tema_e_termos(texto):
    import llm_client, modelos as M
    p = ("Extraia o tema clínico e termos p/ localizar a diretriz desta minirevisão.\n\nTEXTO:\n" + texto[:12000])
    return llm_client.gerar_json(M.RAPIDO, p, _SCHEMA_TEMA, max_tokens=500, nome="tema_minirev")


def montar_mermaid(corpo):
    """Embrulha o corpo do LLM com o TEMA CardioDaily + classDefs. O motor garante o layout."""
    corpo = (corpo or "").strip()
    # tira cerca ```mermaid e um possível %%{init}%% que o modelo tenha posto mesmo assim
    if corpo.startswith("```"):
        corpo = corpo.strip("`")
        corpo = corpo.split("\n", 1)[1] if "\n" in corpo else corpo
    import re
    corpo = re.sub(r"%%\{init[^\n]*\}%%\s*", "", corpo).strip()
    if not corpo.lower().startswith("flowchart"):
        corpo = "flowchart TD\n" + corpo
    return _MERMAID_TEMA + corpo + _MERMAID_CLASSDEF


def analisar(pdf):
    """Roda a trilha inteira sobre 1 PDF de minirevisão. Devolve o dict do resultado."""
    _carregar_env()
    import llm_client, modelos as M
    texto = _texto_pdf(pdf)
    tt = _tema_e_termos(texto)
    tema, termos = tt.get("tema", ""), tt.get("termos", [])
    print(f"       tema: {tema} · termos: {', '.join(termos)}")
    baseline, fontes = baseline_do_tema(tema, termos or [tema])
    print(f"       baseline: {'—' if not baseline else str(len(baseline)) + ' chars'} · fontes: {', '.join(fontes) or 'nenhuma'}")
    prompt = _PROMPT.replace("{baseline}", baseline or "(sem diretriz localizada — avalie só pela revisão)").replace("{texto}", texto)
    r = llm_client.gerar_json(M.ESCRITA, prompt, _SCHEMA_MINIREV, max_tokens=8000, nome="minirevisao")
    # guarda de conteúdo: faixa ≥1 SEM condutas = extração capenga → 1 retry reforçado
    if int(r.get("faixa", 0)) >= 1 and not _linhas(r.get("condutas")):
        reforco = prompt + ("\n\nATENÇÃO: a resposta anterior veio sem `condutas`. Liste as condutas no campo "
                            "`condutas`, UMA POR LINHA começando com '- ' (mínimo 2). Não use XML.")
        r = llm_client.gerar_json(M.ESCRITA, reforco, _SCHEMA_MINIREV, max_tokens=8000, nome="minirevisao")
    r["tema"] = r.get("tema") or tema
    r["fontes_baseline"] = fontes
    r["condutas"] = _linhas(r.get("condutas"))          # string 'uma por linha' → lista limpa
    r["delta"] = _linhas(r.get("delta"))
    r["incertezas"] = _linhas(r.get("incertezas"))
    r["fluxograma_mermaid"] = montar_mermaid(r.get("fluxograma_mermaid", ""))
    r["sobe"] = int(r.get("faixa", 0)) >= 1
    return r


def render_mermaid(codigo, out_png):
    """Render offline via mmdc (mermaid-cli). Usa o Chromium do Playwright como browser do puppeteer.
    Best-effort: sempre grava o .mmd (fonte); devolve o caminho do PNG se renderizou, senão None."""
    mmd = os.path.splitext(out_png)[0] + ".mmd"
    open(mmd, "w", encoding="utf-8").write(codigo)
    env = os.environ.copy()
    try:                                            # aponta o puppeteer p/ o chromium do Playwright
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            env["PUPPETEER_EXECUTABLE_PATH"] = p.chromium.executable_path
    except Exception:
        pass
    cfg = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
    cfg.write('{"args":["--no-sandbox"]}'); cfg.close()
    try:
        subprocess.run(
            ["npx", "-y", "@mermaid-js/mermaid-cli", "-i", mmd, "-o", out_png,
             "-b", "white", "-p", cfg.name],
            check=True, env=env, capture_output=True, timeout=180)
        return out_png if os.path.exists(out_png) else None
    except Exception as e:
        msg = getattr(e, "stderr", b"")
        print(f"       ⚠️  mmdc não renderizou ({type(e).__name__}); .mmd salvo em {os.path.basename(mmd)}. "
              f"{(msg[-200:].decode('utf-8','ignore') if msg else '')}")
        return None


if __name__ == "__main__":
    pdf = os.path.expanduser(sys.argv[1])
    saida = os.path.expanduser(sys.argv[2]) if len(sys.argv) > 2 else os.path.dirname(pdf)
    os.makedirs(saida, exist_ok=True)
    base = os.path.splitext(os.path.basename(pdf))[0]
    print(f"MINIRREVISÃO — {base[:60]}")
    r = analisar(pdf)
    print(f"\n=== FAIXA {r['faixa']} — {'SOBE' if r['sobe'] else 'RETIDO (vaselina)'} ===")
    print(f"  {r['faixa_justificativa']}")
    print(f"\n  Condutas ({len(r.get('condutas') or [])}):")
    for c in (r.get("condutas") or []):
        print(f"   • {c}")
    if r.get("incertezas"):
        print(f"\n  Incertezas: " + " · ".join(r["incertezas"]))
    json.dump(r, open(os.path.join(saida, base + "_minirev.json"), "w"), ensure_ascii=False, indent=2)
    if r["sobe"]:
        png = render_mermaid(r["fluxograma_mermaid"], os.path.join(saida, base + "_fluxograma.png"))
        print(f"\n  Fluxograma: {'PNG ' + os.path.basename(png) if png else '.mmd salvo (render pendente)'}")
    print(f"\n  JSON: {base}_minirev.json")
