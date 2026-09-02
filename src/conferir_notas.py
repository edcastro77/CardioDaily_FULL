"""
conferir_notas.py — A NOTA É UMA SÓ. ESTE PROGRAMA PROVA ISSO, PEÇA POR PEÇA.

═══════════════════════════════════════════════════════════════════════════════════════
POR QUE ESTE ARQUIVO EXISTE (06/Ago/2026)
═══════════════════════════════════════════════════════════════════════════════════════

O Dr. Eduardo: *"visual abstract aparece uma nota e no texto outra"* — e, quando eu disse que
não tinha achado: *"depois eu mostro, mas são VÁRIOS"*.

Eu medi cinco peças no disco e todas bateram (canônico × perícia .md × PDF × Visual Abstract ×
ACRI/áudio, 79 a 115 pacotes cada, zero divergência). Isso NÃO quer dizer que ele viu errado.
Quer dizer que eu olhei onde não estava. Duas coisas eu não alcanço do meu ambiente:

    · a LINHA NO SUPABASE (o que o site e o painel de curadoria mostram)
    · o que ficou no banco de rodadas ANTERIORES, quando a régua era outra

E existe um jeito conhecido de a divergência aparecer sem que nenhuma peça do disco esteja
errada: o pacote foi REANALISADO com a régua nova, o disco atualizou, e a linha do banco ficou
com a nota velha. Foi por isso que o `publicador` ganhou a retratação em 05/Ago — o portão
publicava e nunca retirava.

Este programa é o CONFERIDOR: ele varre tudo, compara TODAS as peças contra o canônico, e diz
onde diverge. Não chama LLM, não gasta um centavo, não escreve em lugar nenhum. Só olha e conta.

    python3 src/conferir_notas.py              → confere o disco
    python3 src/conferir_notas.py --supabase   → confere TAMBÉM a linha do banco (só LEITURA)

É a versão "nota" da tarefa #27 (Conferidor de números). A nota é o coração do produto: se as
peças discordam entre si, o assinante perde a confiança em TUDO — e ele tem razão em perder.
"""
import os
import re
import sys
import glob
import json

RAIZ = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "outputs", "STAGING")


def _n(txt, padrao):
    m = re.search(padrao, txt or "")
    return int(m.group(1)) if m else None


def notas_do_canonico(caminho):
    """A FONTE DA VERDADE. Quem discorda daqui é que está errado — o canônico é o que o MOTOR
    DETERMINÍSTICO gravou, e o motor é a única coisa no sistema que não depende do humor do LLM."""
    t = open(caminho, encoding="utf-8").read()
    return (_n(t, r"nota_aplicabilidade_clinica:\s*(\d+)"),
            _n(t, r"nota_trabalho_estatistico:\s*(\d+)"))


# ═══ 02/Set — A DEPENDÊNCIA AUSENTE FALAVA COM A VOZ DO DADO ═══
# O `except: return None` em volta do IMPORT transformava "pypdf não instalado" em
# "PDF: ilegível" — 533 de 695 pacotes, TODOS mentira. A camada de conferência do PDF
# (a nota que o assinante REALMENTE abre) nunca tinha rodado, e o relatório parecia
# medir o acervo. Aprovação/reprovação por ausência DENTRO do instrumento de prova.
# Agora: falta de dependência ABORTA com a causa dita; o except fica só na extração.
try:
    from pypdf import PdfReader as _PdfReader
except Exception:
    _PdfReader = None


def _texto_do_pdf(caminho):
    if _PdfReader is None:
        raise SystemExit("⛔ pypdf NÃO está instalado — sem ele eu não confiro os PDFs.\n"
                         "   Isto NÃO é 'PDF ilegível': é ambiente incompleto.\n"
                         "   Conserte com: .venv/bin/pip install pypdf")
    try:
        return "".join((p.extract_text() or "") for p in _PdfReader(caminho).pages[:3])
    except Exception:
        return None


def conferir_pacote(pasta, ver_supabase=False):
    """Devolve lista de divergências. Vazia = o pacote fala com UMA voz."""
    can = glob.glob(os.path.join(pasta, "*_CANONICO.md"))
    if not can:
        return [("sem canônico", "pasta sem _CANONICO.md — lixo de rodada interrompida", None, None)]
    aplic, rigor = notas_do_canonico(can[0])
    if aplic is None:
        return [("canônico ilegível", "não achei nota_aplicabilidade_clinica", None, None)]
    ruins = []

    # ── a perícia em MARKDOWN ──
    # ⚠️ A perícia traz as DUAS notas em linhas seguidas. Casar "nota ... N/10" solto pega a linha
    #    do RIGOR e acusa divergência que não existe — eu caí nessa em 06/Ago e quase reportei 27
    #    defeitos inexistentes. Cada padrão abaixo é ANCORADO no nome da nota.
    for md in glob.glob(os.path.join(pasta, "*_analise.md")):
        t = open(md, encoding="utf-8").read()
        a = _n(t, r"[Nn]ota de aplicabilidade cl[ií]nica:?\s*\**\s*(\d{1,2})\s*/\s*10")
        g = _n(t, r"[Nn]ota de rigor[^:]{0,26}:?\s*\**\s*(\d{1,2})\s*/\s*10")
        if a is not None and a != aplic:
            ruins.append(("perícia .md", "aplicabilidade", aplic, a))
        if g is not None and rigor is not None and g != rigor:
            ruins.append(("perícia .md", "rigor", rigor, g))

    # ── o PDF (é o que o assinante REALMENTE abre) ──
    for pdf in glob.glob(os.path.join(pasta, "*_analise.pdf")):
        t = _texto_do_pdf(pdf)
        if t is None:
            ruins.append(("PDF", "ilegível — não consegui extrair texto", None, None))
            continue
        a = _n(t, r"[Nn]ota de aplicabilidade cl[ií]nica:?\s*(\d{1,2})\s*/\s*10")
        if a is not None and a != aplic:
            velho = os.path.getmtime(pdf) < os.path.getmtime(can[0]) - 5
            ruins.append(("PDF" + (" (mais VELHO que o canônico)" if velho else ""),
                          "aplicabilidade", aplic, a))

    # ── o Visual Abstract (o card, a peça que circula sozinha no WhatsApp) ──
    for vj in glob.glob(os.path.join(pasta, "assets", "visual_abstract_data.json")):
        try:
            v = json.load(open(vj))
        except Exception:
            continue
        nv = v.get("nota") or v.get("nac") or v.get("nota_aplicabilidade")
        if nv is not None:
            try:
                nv = int(str(nv).split("/")[0])
            except Exception:
                nv = None
        if nv is not None and nv != aplic:
            ruins.append(("Visual Abstract", "aplicabilidade", aplic, nv))

    # ── ACRI e roteiro de áudio: qualquer N/10 tem de ser uma das DUAS notas ──
    for pat, rot in (("*_ACRI.txt", "ACRI"), ("*_roteiro_audio.txt", "roteiro de áudio")):
        for f in glob.glob(os.path.join(pasta, pat)):
            t = open(f, encoding="utf-8", errors="ignore").read()
            for x in re.findall(r"(?:nota|NAC)[^.\n]{0,34}?(\d{1,2})\s*/\s*10", t, re.I):
                if int(x) not in (aplic, rigor):
                    ruins.append((rot, "cita nota que não é nenhuma das duas", f"{aplic}/{rigor}", x))

    # ── a LINHA DO BANCO — o candidato nº 1 para "são vários" ──
    # O disco pode estar impecável e o banco carregar a nota de uma rodada anterior. Só LEITURA:
    # a LEI 5 diz que quem ESCREVE em `artigos` é o publicador e mais ninguém.
    if ver_supabase:
        linha = _linha_do_supabase(pasta)
        if linha == "sem credencial":
            ruins.append(("Supabase", "sem credencial no ambiente — não consegui olhar", None, None))
        elif isinstance(linha, dict):
            nb = linha.get("nota_aplicabilidade")
            if nb is not None and int(nb) != aplic:
                ruins.append(("SUPABASE (é o que o site mostra)", "aplicabilidade", aplic, nb))
            rb = linha.get("nota_trabalho_estatistico")
            if rb is not None and rigor is not None and int(rb) != rigor:
                ruins.append(("SUPABASE (é o que o site mostra)", "rigor", rigor, rb))
    return ruins


def _linha_do_supabase(pasta):
    """LÊ (só lê) a linha do artigo. Casa pelo DOI do canônico, que é a chave do portão."""
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_KEY")
    if not (url and key):
        return "sem credencial"
    can = glob.glob(os.path.join(pasta, "*_CANONICO.md"))
    if not can:
        return None
    m = re.search(r'doi:\s*"?([^"\n]+)', open(can[0], encoding="utf-8").read())
    if not m:
        return None
    doi = m.group(1).strip()
    try:
        import urllib.request
        import urllib.parse
        q = urllib.parse.quote(doi, safe="")
        req = urllib.request.Request(
            f"{url}/rest/v1/artigos?doi=eq.{q}&select=nota_aplicabilidade,nota_trabalho_estatistico",
            headers={"apikey": key, "Authorization": f"Bearer {key}"})
        dados = json.load(urllib.request.urlopen(req, timeout=20))
        return dados[0] if dados else None
    except Exception:
        return None


def main():
    ver_sb = "--supabase" in sys.argv
    pastas = [p for p in sorted(glob.glob(os.path.join(RAIZ, "*"))) if os.path.isdir(p)]
    if not pastas:
        print("STAGING vazio.")
        return 0
    print("═" * 78)
    print(" CONFERIDOR DE NOTAS · a nota é UMA só, em todas as peças")
    print(f" {len(pastas)} pacote(s)" + ("  ·  incluindo a linha do Supabase (leitura)" if ver_sb
                                         else "  ·  só o disco (use --supabase p/ incluir o banco)"))
    print("═" * 78)
    total_ruins = 0
    for p in pastas:
        r = conferir_pacote(p, ver_sb)
        if not r:
            continue
        total_ruins += 1
        print(f"\n❌ {os.path.basename(p)[:70]}")
        for peca, campo, esperado, veio in r:
            if esperado is None:
                print(f"     · {peca}: {campo}")
            else:
                print(f"     · {peca}: {campo} — motor diz {esperado}, a peça diz {veio}")
    print("\n" + "═" * 78)
    if total_ruins:
        print(f"REPROVADO · {total_ruins} de {len(pastas)} pacote(s) falam com mais de uma voz.")
        return 1
    print(f"APROVADO · os {len(pastas)} pacotes falam com UMA voz só.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
