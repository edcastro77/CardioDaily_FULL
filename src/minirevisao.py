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
import os, sys, json, subprocess, shutil, tempfile, base64, glob, html as _html

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
   ENVOLVA todo rótulo entre ASPAS DUPLAS — ex.: A["texto (com parênteses) ok"]:::term e B{"Lp(a) ≥ 50?"}:::dec
   — senão parêntese/%/: quebram o Mermaid.
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


def _aspar_rotulos(corpo):
    """Aspa TODO rótulo de nó [..] e {..} não-aspeado. Sem isso, parêntese no texto (Lp(a), (~50 mg/dL),
    (>40%)) quebra o parser do Mermaid — foi o que derrubou 4 renders no batch de 45. Já-aspeados: ignora."""
    import re
    def q(m):
        return m.group(0)[0] + '"' + m.group(1).strip() + '"' + m.group(0)[-1]
    corpo = re.sub(r'\[([^\[\]"\n]+?)\]', q, corpo)   # retângulos / terminais
    corpo = re.sub(r'\{([^{}"\n]+?)\}', q, corpo)     # decisões (losango)
    # rótulos de ARESTA também quebram com parêntese/vírgula: -->|texto| e -- texto -->
    corpo = re.sub(r'\|([^|"\n]+?)\|', lambda m: '|"' + m.group(1).strip() + '"|', corpo)
    corpo = re.sub(r'--\s+([^"|>\n][^\n]*?)\s+-->', lambda m: '-- "' + m.group(1).strip() + '" -->', corpo)
    return corpo


def montar_mermaid(corpo):
    """Embrulha o corpo do LLM com o TEMA CardioDaily + classDefs. IDEMPOTENTE: tira init/classDef que
    já existam (dá pra reprocessar um mermaid já montado). O motor garante o layout."""
    import re
    corpo = (corpo or "").strip()
    if corpo.startswith("```"):                        # tira cerca ```mermaid
        corpo = corpo.strip("`")
        corpo = corpo.split("\n", 1)[1] if "\n" in corpo else corpo
    corpo = re.sub(r"%%\{init[^\n]*\}%%\s*", "", corpo)          # tira init (meu, se reprocessando)
    corpo = re.sub(r"(?m)^\s*classDef\s+.*$", "", corpo)         # tira classDef (meu)
    corpo = "\n".join(l for l in corpo.splitlines() if l.strip()).strip()
    if not corpo.lower().startswith("flowchart"):
        corpo = "flowchart TD\n" + corpo
    corpo = _aspar_rotulos(corpo)                       # blindagem contra parêntese/% em rótulo
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
    # mmdc instalado (global) é rápido; senão npx baixa na hora (lento, mas funciona)
    cmd = (["mmdc"] if shutil.which("mmdc") else ["npx", "-y", "@mermaid-js/mermaid-cli"])
    try:
        subprocess.run(cmd + ["-i", mmd, "-o", out_png, "-b", "white", "-p", cfg.name],
                       check=True, env=env, capture_output=True, timeout=180)
        return out_png if os.path.exists(out_png) else None
    except Exception as e:
        msg = getattr(e, "stderr", b"")
        print(f"       ⚠️  mmdc não renderizou ({type(e).__name__}); .mmd salvo em {os.path.basename(mmd)}. "
              f"{(msg[-200:].decode('utf-8','ignore') if msg else '')}")
        return None


_FAIXA_ROTULO = {0: "0 · vaselina (retido)", 1: "1 · consolida + acrescenta útil", 2: "2 · grande interesse (modelo prático)"}


def montar_card(dst, base, r):
    """Escreve o ENTREGÁVEL LEGÍVEL da minirevisão: card em Markdown + HTML (fluxograma embutido).
    É o que o Dr. lê — não o JSON cru. Gera só p/ faixa ≥1 (faixa 0 é vaselina/retido)."""
    faixa = int(r.get("faixa", 0))
    rot = _FAIXA_ROTULO.get(faixa, str(faixa))
    cond = r.get("condutas") or []
    inc = r.get("incertezas") or []
    dlt = r.get("delta") or []
    fontes = " · ".join(r.get("fontes_baseline") or []) or "—"
    png = glob.glob(os.path.join(dst, base + "_fluxograma.png"))

    # ---------- Markdown (portável, git-friendly) ----------
    md = [f"# {r.get('titulo','(sem título)')}",
          f"\n**Tema:** {r.get('tema','')}  \n**Faixa:** {rot}",
          f"\n> {r.get('faixa_justificativa','')}",
          "\n## Condutas práticas"]
    md += [f"- {c}" for c in cond] or ["- (nenhuma)"]
    if png:
        md.append(f"\n## Fluxograma da estratégia de abordagem\n\n![fluxograma]({os.path.basename(png[0])})")
    if inc:
        md.append("\n## Incertezas (o que fica em aberto)"); md += [f"- {x}" for x in inc]
    if r.get("aplicabilidade_brasil"):
        md.append(f"\n## Aplicabilidade no Brasil\n\n{r['aplicabilidade_brasil']}")
    if dlt:
        md.append("\n## O que a revisão acrescenta à diretriz (delta)"); md += [f"- {x}" for x in dlt]
    md.append(f"\n---\n_Baseline (diretriz vigente): {fontes}. Trilha minirevisão CardioDaily — não sobe no Supabase. "
              f"Conteúdo educativo; não substitui julgamento clínico._")
    open(os.path.join(dst, base + "_card.md"), "w", encoding="utf-8").write("\n".join(md))

    # ---------- HTML (bonito, autocontido, fluxograma embutido) ----------
    def esc(s): return _html.escape(str(s or ""))
    img = ""
    if png:
        b64 = base64.b64encode(open(png[0], "rb").read()).decode()
        img = (f'<h2>Fluxograma da estratégia de abordagem</h2>'
               f'<div class="flow"><img alt="fluxograma" src="data:image/png;base64,{b64}"></div>')
    li_cond = "".join(f"<li>{esc(c)}</li>" for c in cond)
    li_inc = "".join(f"<li>{esc(x)}</li>" for x in inc)
    li_del = "".join(f"<li>{esc(x)}</li>" for x in dlt)
    aplic = f'<div class="aplic"><b>Aplicabilidade no Brasil.</b> {esc(r.get("aplicabilidade_brasil"))}</div>' if r.get("aplicabilidade_brasil") else ""
    html_doc = f"""<!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(r.get('titulo'))} — Minirevisão CardioDaily</title><style>
:root{{--azul:#0B3D91;--verm:#C00000;--ink:#16233a;--muted:#5a6b85;--bg:#fff;--surf:#f4f7fc;--bd:#d6dfef}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:16px/1.55 Helvetica,Arial,sans-serif}}
.wrap{{max-width:860px;margin:0 auto;padding:28px 20px 64px}}
.kick{{font-size:12px;letter-spacing:.14em;text-transform:uppercase;color:var(--verm);font-weight:700}}
h1{{color:var(--azul);font-size:26px;margin:6px 0 4px;line-height:1.18}}
.tema{{color:var(--muted);font-size:14px}}
.badge{{display:inline-block;margin-top:10px;border:1px solid var(--azul);color:var(--azul);border-radius:999px;padding:4px 13px;font-weight:700;font-size:13px}}
.just{{background:var(--surf);border-left:4px solid var(--azul);border-radius:10px;padding:12px 15px;margin:16px 0;font-size:14px}}
h2{{color:var(--azul);font-size:17px;margin:26px 0 8px}}
ul.cond{{list-style:none;padding:0;margin:0;display:flex;flex-direction:column;gap:8px}}
ul.cond li{{background:var(--surf);border:1px solid var(--bd);border-left:3px solid var(--verm);border-radius:9px;padding:10px 13px;font-size:14px}}
ul.mini{{padding-left:18px;color:var(--muted);font-size:13.5px}}ul.mini li{{margin-bottom:5px}}
.aplic{{background:#eaf0fa;border:1px solid var(--bd);border-radius:10px;padding:12px 14px;font-size:13.5px;margin-top:10px}}.aplic b{{color:var(--azul)}}
.flow{{background:#fff;border:1px solid var(--bd);border-radius:12px;padding:12px;overflow-x:auto;text-align:center}}
.flow img{{max-width:100%;height:auto}}
.foot{{margin-top:26px;font-size:12px;color:var(--muted);border-top:1px solid var(--bd);padding-top:12px}}
</style></head><body><div class="wrap">
<div class="kick">CardioDaily · minirevisão · opinião de especialista</div>
<h1>{esc(r.get('titulo'))}</h1><div class="tema">Tema: {esc(r.get('tema'))}</div>
<div class="badge">Faixa {esc(rot)}</div>
<div class="just">{esc(r.get('faixa_justificativa'))}</div>
<h2>Condutas práticas</h2><ul class="cond">{li_cond}</ul>
{img}
{'<h2>Incertezas (o que fica em aberto)</h2><ul class="mini">'+li_inc+'</ul>' if li_inc else ''}
{aplic}
{'<h2>O que a revisão acrescenta à diretriz</h2><ul class="mini">'+li_del+'</ul>' if li_del else ''}
<div class="foot">Baseline (diretriz vigente): {esc(fontes)}. Trilha minirevisão CardioDaily — não sobe no Supabase. Conteúdo educativo; não substitui julgamento clínico.</div>
</div></body></html>"""
    open(os.path.join(dst, base + "_card.html"), "w", encoding="utf-8").write(html_doc)
    return os.path.join(dst, base + "_card.html")


def processar_pdf(pdf, saida_base):
    """Processa 1 PDF de minirevisão → pasta própria em saida_base. Faixa 0 fica retido (sem fluxograma).
    NÃO sobe no Supabase (é ferramenta standalone, como o Pesquisador). Devolve (faixa, sobe)."""
    base = os.path.splitext(os.path.basename(pdf))[0]
    dst = os.path.join(saida_base, base); os.makedirs(dst, exist_ok=True)
    if os.path.exists(os.path.join(dst, "_OK")):        # retomável: pula os já feitos
        print(f"  ⏭️  {base[:54]} já processado"); return None, None
    print(f"\n▶ {base[:60]}")
    r = analisar(pdf)
    json.dump(r, open(os.path.join(dst, base + "_minirev.json"), "w"), ensure_ascii=False, indent=2)
    faixa = r.get("faixa"); sobe = r.get("sobe")
    print(f"  FAIXA {faixa} — {'SOBE (condutas+fluxograma)' if sobe else 'RETIDO (vaselina, sem valor prático novo)'}")
    for c in (r.get("condutas") or [])[:8]:
        print(f"    • {c[:110]}")
    if sobe:
        png = render_mermaid(r["fluxograma_mermaid"], os.path.join(dst, base + "_fluxograma.png"))
        print(f"    fluxograma: {os.path.basename(png) if png else '.mmd (render pendente)'}")
        card = montar_card(dst, base, r)             # ENTREGÁVEL LEGÍVEL (md + html) — o que se lê
        print(f"    card: {os.path.basename(card)}")
    open(os.path.join(dst, "_OK"), "w").write("")
    return faixa, sobe


def refazer_cards(saida):
    """Pós-passo: (re)gera os cards legíveis a partir dos *_minirev.json já produzidos (sem re-analisar)."""
    jsons = glob.glob(os.path.join(saida, "*", "*_minirev.json"))
    n = 0
    for j in jsons:
        r = json.load(open(j, encoding="utf-8"))
        if int(r.get("faixa", 0)) < 1:              # faixa 0 é retido, sem card
            continue
        dst = os.path.dirname(j)
        base = os.path.basename(j).replace("_minirev.json", "")
        montar_card(dst, base, r); n += 1
    print(f"cards (re)gerados: {n} · em {saida}")
    return n


def _pdfs(caminho):
    if os.path.isfile(caminho):
        return [caminho]
    achados = []
    for root, _, files in os.walk(caminho):
        for f in sorted(files):
            if f.lower().endswith(".pdf") and not f.startswith("._"):
                achados.append(os.path.join(root, f))
    return sorted(achados)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("uso: python minirevisao.py <PDF|pasta> [saida]  |  --cards <saida>"); sys.exit(1)
    if sys.argv[1] == "--cards":                     # pós-passo: regenera cards dos JSONs existentes
        saida = os.path.expanduser(sys.argv[2]) if len(sys.argv) > 2 else \
            os.path.abspath(os.path.join(_HERE, "..", "outputs", "MINIRREVISOES"))
        refazer_cards(saida); sys.exit(0)
    entrada = os.path.expanduser(sys.argv[1])
    saida = os.path.expanduser(sys.argv[2]) if len(sys.argv) > 2 else \
        os.path.abspath(os.path.join(_HERE, "..", "outputs", "MINIRREVISOES"))
    os.makedirs(saida, exist_ok=True)
    pdfs = _pdfs(entrada)
    print(f"TRILHA MINIRREVISÃO — {len(pdfs)} artigo(s)  →  {saida}\n(condutas + fluxograma · NÃO sobe no Supabase)")
    sobem = retidos = 0
    for pdf in pdfs:
        try:
            faixa, sobe = processar_pdf(pdf, saida)
            if sobe is True: sobem += 1
            elif sobe is False: retidos += 1
        except Exception as e:
            print(f"  ⚠️  {os.path.basename(pdf)[:54]} ERRO: {type(e).__name__}: {e}")
    print(f"\nFIM · {sobem} com valor prático (faixa ≥1) · {retidos} retidos (vaselina). Saída em {saida}")
