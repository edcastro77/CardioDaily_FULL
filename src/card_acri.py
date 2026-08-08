"""
card_acri.py — O CARD ACRI PARA REDES SOCIAIS (1080×1350).

═══════════════════════════════════════════════════════════════════════════════════════
POR QUE ESTE ARQUIVO EXISTE, E POR QUE ELE NÃO FERE A PROIBIÇÃO
═══════════════════════════════════════════════════════════════════════════════════════

O CLAUDE.md proíbe cards HTML→PNG desde 2025, e a proibição é justa. O motivo escrito lá:

    "Texto minúsculo: bullets curtos ficam com fonte pequena que não preenche o espaço"
    "Espaços vazios grandes: o layout expande os boxes mas o conteúdo não ocupa"
    "Resultado visual amador"

Mas a regra tem uma porta de saída, com todas as letras:

    "NÃO gerar cards HTML→PNG enquanto NÃO EXISTIR UM LAYOUT ADAPTATIVO QUE GARANTA
     DENSIDADE VISUAL REAL."

Em 06/Ago/2026 o Dr. Eduardo trouxe o layout (`card-acri.html`, desenhado por ele) e pediu a
peça para redes sociais. A condição foi cumprida — a proibição não está sendo furada, está
sendo FECHADA. E a densidade é garantida em DOIS pontos, não em um:

    1. NA ORIGEM — `card_acri_prompt.md` obriga cada frase a ter 90–140 caracteres. O texto
       nasce do tamanho do quadro, em vez de ser espremido nele depois.
    2. NO LAYOUT — o título muda de corpo em degraus (62 / 54 / 46 px) conforme o comprimento,
       e a bateria RECUSA card cujo texto estoure o limite.

O que reprovou os cards de 2025 foi exatamente a ausência dessas duas coisas.

═══════════════════════════════════════════════════════════════════════════════════════
O QUE ELE NÃO FAZ (de propósito)
═══════════════════════════════════════════════════════════════════════════════════════

· NÃO escreve no Supabase. LEI 5: quem escreve em `artigos` é o publicador e mais ninguém.
  O card fica no disco, ao lado do pacote, para o Dr. Eduardo baixar e postar.
· NÃO entra no carimbo (`versoes_atuais`). Se entrasse, criar este arquivo forçaria a
  reanálise dos ~380 artigos já prontos — US$ 114 para gerar uma imagem.
· NÃO toca no `_ACRI.txt`, que alimenta o site e o contrato. Este prompt é OUTRO, e o card
  é uma peça derivada — se ele falhar, nada mais quebra.
"""
import os
import re
import json
import glob

_HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.join(_HERE, "infographics", "templates", "card_acri_template.html")
PROMPT = os.path.join(_HERE, "card_acri_prompt.md")

# limites que o layout aguenta — a bateria confere, e o gerador recusa em vez de entregar feio
MIN_FRASE, MAX_FRASE = 60, 150
MAX_TITULO = 78


def classe_do_titulo(titulo):
    """O título muda de corpo em degraus. Sem isto, um título de 40 caracteres deixa uma
    faixa branca no meio do card e um de 70 estoura para a quarta linha."""
    n = len(titulo or "")
    if n <= 42:
        return ""
    return "medio" if n <= 58 else "longo"


def selo_conduta(muda_conduta):
    """O selo ao lado da nota. Os quatro tipos falam línguas diferentes (06/Ago) e o card
    tem de respeitar isso — escrever 'MUDA CONDUTA: NÃO' numa revisão é afirmação falsa."""
    v = (muda_conduta or "").strip()
    if v == "SIM":
        return "MUDA CONDUTA"
    if v == "NÃO":
        return ""                      # não se anuncia ausência; simplesmente não vem selo
    if v.upper().startswith("N/A"):
        return ""                      # revisão organiza conhecimento — a pergunta não cabe
    if v.startswith("RECOMENDADA COM"):
        return "COM RESSALVAS"
    if v.startswith("RECOMENDADA"):
        return "RECOMENDADA"
    if v.startswith("REFERÊNCIA"):
        return "REFERÊNCIA"
    if v.startswith("NÃO RECOMENDADA"):
        return "NÃO RECOMENDADA"
    return ""


def conferir(d):
    """Recusa o card ANTES de desenhar. Card feio publicado é pior que card não publicado —
    é a peça que circula sozinha, sem a perícia do lado para explicar."""
    problemas = []
    t = (d.get("titulo") or "").strip()
    if not t:
        problemas.append("título vazio")
    elif len(t) > MAX_TITULO:
        problemas.append(f"título com {len(t)} caracteres (máx. {MAX_TITULO})")
    for k in ("a", "c", "r", "i"):
        v = (d.get(k) or "").strip()
        if not v:
            problemas.append(f"{k.upper()} vazio")
        elif len(v) > MAX_FRASE:
            problemas.append(f"{k.upper()} com {len(v)} caracteres (máx. {MAX_FRASE}) — estoura o quadro")
        elif len(v) < MIN_FRASE:
            problemas.append(f"{k.upper()} com {len(v)} caracteres (mín. {MIN_FRASE}) — deixa buraco branco")
    return problemas


def _negrito_no_numero(texto):
    """Destaca o primeiro número com unidade no bloco R — é o que o olho procura em 2 segundos."""
    m = re.search(r"([+\-−]?\d+[\d.,]*\s*(?:pp|%|pontos|dias|meses|mg/dL|mmHg|vs\.?\s*\d+[\d.,]*\s*%))", texto)
    if not m:
        return texto
    return texto[:m.start()] + "<b>" + m.group(1) + "</b>" + texto[m.end():]


def dados_do_pacote(pasta):
    """Lê o que já existe no disco: canônico (identidade + notas) e ACRI (o texto longo)."""
    can = glob.glob(os.path.join(pasta, "*_CANONICO.md"))
    if not can:
        return None
    t = open(can[0], encoding="utf-8").read()

    def campo(c):
        m = re.search(rf'{c}:\s*"(.*?)"\s*$', t, re.M)
        return m.group(1).strip() if m else ""

    def num(c):
        m = re.search(rf"{c}:\s*(\d+)", t)
        return int(m.group(1)) if m else None

    acri = ""
    a = glob.glob(os.path.join(pasta, "*_ACRI.txt"))
    if a:
        acri = open(a[0], encoding="utf-8").read()
    fatos = {}
    f = glob.glob(os.path.join(pasta, "*_fatos.json"))
    if f:
        try:
            fatos = json.load(open(f[0]))
        except Exception:
            pass
    return {"titulo_orig": campo("titulo"), "revista": campo("revista"), "ano": campo("ano"),
            "nota": num("nota_aplicabilidade_clinica"), "rigor": num("nota_trabalho_estatistico"),
            "muda_conduta": campo("muda_conduta"), "acri": acri, "fatos": fatos,
            "tipo": (fatos.get("tipo_documento") or "")}


def montar_html(d, logo=""):
    """Renderiza o template com os campos já conferidos."""
    from jinja2 import Template
    tpl = Template(open(TEMPLATE, encoding="utf-8").read())
    return tpl.render(area=d.get("area") or "CARDIOLOGIA",
                      revista=d.get("revista", ""), ano=d.get("ano", ""),
                      nota=d.get("nota"), selo_conduta=selo_conduta(d.get("muda_conduta")),
                      titulo=d.get("titulo"), classe_titulo=classe_do_titulo(d.get("titulo")),
                      a=d.get("a"), c=d.get("c"), r=_negrito_no_numero(d.get("r") or ""),
                      i=d.get("i"), logo=logo)


def png(html, destino):
    """HTML → PNG 1080×1350 pelo Playwright, o mesmo motor do Visual Abstract."""
    from playwright.sync_api import sync_playwright
    tmp = destino + ".html"
    open(tmp, "w", encoding="utf-8").write(html)
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1080, "height": 1350}, device_scale_factor=2)
        pg.goto("file://" + os.path.abspath(tmp))
        pg.wait_for_timeout(1200)                    # a fonte Archivo precisa chegar
        pg.screenshot(path=destino, clip={"x": 0, "y": 0, "width": 1080, "height": 1350})
        b.close()
    os.remove(tmp)
    return destino


def gerar_um(pasta, force=False):
    """Gera o card de UM pacote do STAGING. Devolve (caminho_png, motivo_se_falhou).

    Custo: uma chamada curta de LLM (só condensa texto que já existe) + Playwright.
    NÃO chama o extrator, NÃO relê o PDF, NÃO toca no Supabase.
    """
    import llm_client
    import modelos as M

    d = dados_do_pacote(pasta)
    if not d:
        return None, "sem canônico"
    if d["nota"] is None:
        return None, "sem nota"
    base = os.path.basename(pasta.rstrip("/"))
    destino = os.path.join(pasta, f"{base}_card.png")
    if os.path.exists(destino) and not force:
        return destino, "já existia"
    if not d["acri"].strip():
        return None, "sem ACRI (nota <6 fica retido e não gera card)"

    ctx = (f"VEREDITO DO MOTOR — use estes números, não invente outros:\n"
           f"  nota de aplicabilidade: {d['nota']}/10\n"
           f"  nota de rigor: {d['rigor']}/10\n"
           f"  campo muda_conduta: {d['muda_conduta']}\n"
           f"  tipo do documento: {d['tipo']}\n\n"
           f"IDENTIDADE: {d['titulo_orig']} · {d['revista']} · {d['ano']}\n\n"
           f"ACRI COMPLETO (é o que você vai condensar):\n{d['acri']}\n\n"
           f"FATOS (todo número do card tem de estar AQUI):\n"
           f"{json.dumps(d['fatos'], ensure_ascii=False, indent=1)[:6000]}")

    bruto = llm_client.gerar(M.ESCRITA, open(PROMPT, encoding="utf-8").read(), contexto=ctx)
    txt = re.sub(r"^```(?:json)?|```$", "", (bruto or "").strip(), flags=re.M).strip()
    try:
        campos = json.loads(txt)
    except Exception as e:
        return None, f"JSON inválido do modelo: {str(e)[:60]}"

    problemas = conferir(campos)
    if problemas:
        return None, "recusado: " + " · ".join(problemas[:2])

    campos.update(revista=d["revista"], ano=d["ano"], nota=d["nota"],
                  muda_conduta=d["muda_conduta"])
    logo = os.path.join(_HERE, "infographics", "templates", "logo-heart.png")
    png(montar_html(campos, logo="file://" + logo if os.path.exists(logo) else ""), destino)
    return destino, ""


def gerar_lote(staging, nota_min=7, maximo=0, force=False):
    """Varre o STAGING e gera o card de todo pacote com nota ≥ nota_min (diretriz: sempre)."""
    feitos, pulados, falhas = [], 0, []
    for pasta in sorted(glob.glob(os.path.join(staging, "*"))):
        if not os.path.isdir(pasta):
            continue
        d = dados_do_pacote(pasta)
        if not d or d["nota"] is None:
            continue
        if d["nota"] < nota_min and d["tipo"] != "diretriz":
            continue
        base = os.path.basename(pasta)
        if os.path.exists(os.path.join(pasta, f"{base}_card.png")) and not force:
            pulados += 1
            continue
        try:
            p, motivo = gerar_um(pasta, force=force)
        except Exception as e:
            p, motivo = None, f"{type(e).__name__}: {str(e)[:60]}"
        if p:
            feitos.append(base)
            print(f"  ✅ {base[:60]}")
        else:
            falhas.append((base, motivo))
            print(f"  ⚠️  {base[:52]} — {motivo}")
        if maximo and len(feitos) >= maximo:
            break
    return feitos, pulados, falhas


if __name__ == "__main__":
    import sys
    stg = os.path.join(os.path.dirname(_HERE), "outputs", "STAGING")
    nmin = int(os.environ.get("CD_CARD_NOTA_MIN", "7"))
    mx = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 0
    print("═" * 72)
    print(f" CARD ACRI · 1080×1350 · nota ≥{nmin} (diretriz sempre)" + (f" · máximo {mx}" if mx else ""))
    print("═" * 72)
    f, p, x = gerar_lote(stg, nota_min=nmin, maximo=mx)
    print("═" * 72)
    print(f"  {len(f)} card(s) gerado(s) · {p} já existiam · {len(x)} falha(s)")
    if x:
        print("\n  as falhas (o card foi RECUSADO antes de sair feio):")
        for b, m in x[:10]:
            print(f"    · {b[:50]} — {m}")
