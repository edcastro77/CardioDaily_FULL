"""
ocr_pdf.py — quando o PDF é IMAGEM, o texto vem do OCR.

═══ 19/Ago/2026 — O CASO QUE ORIGINOU ISTO ═══

O Dr. Eduardo baixou os 100 artigos originais que mudaram a história da IC. Cinco foram
para revisão humana. Um deles, o V-HeFT I (Cohn, NEJM 1986), é um **scan do arquivo
histórico do NEJM**: não tem camada de texto, só a imagem da página.

⚠️ E ELE NÃO ERA UM PDF VAZIO — ERA PIOR. Tinha exatamente 257 caracteres por página,
idênticos em todas:

    "The New England Journal of Medicine — Downloaded from nejm.org at BOSTON UNIVERSITY
     on September 6, 2013. For personal use only… From the NEJM Archive."

É o carimbo de download. O classificador testava `if texto.strip()` — e 257 caracteres
passam nesse teste. Ou seja: **o PDF parecia legível e não era**. A cascata inteira
decidia em cima de um carimbo, e o waypoint C1 registrava sucesso.

O detector antigo pegava só o caso do PDF 100% vazio. O caso real é este: texto
suficiente para enganar a checagem, insuficiente para dizer qualquer coisa.

═══ O QUE ESTE MÓDULO FAZ ═══
1. `texto_e_util()` — decide se o que saiu do PDF serve, olhando DENSIDADE e REPETIÇÃO.
2. `ocr()` — roda o Tesseract nas páginas, a 300 dpi.

MEDIDO no V-HeFT: 4,7 s por página · 15.929 caracteres em 2 páginas · título, autores,
resumo e desenho legíveis. Os nomes saem com erro ("Coun" por Cohn), o que não afeta nem
a classificação nem a extração — o que importa é "randomly assigned 642 men".

CUSTO: zero. É software livre rodando na máquina.

⚠️ DEPENDE DO TESSERACT ESTAR INSTALADO. Se não estiver, este módulo diz isso em voz alta
em vez de devolver string vazia em silêncio — que seria trocar um buraco mudo por outro.
No Mac:  brew install tesseract
"""
import os
import re
import shutil

DPI = 300           # abaixo de 300 o Tesseract erra número, e número é o que mais importa aqui
MIN_CHARS_PAGINA = 400    # página de artigo científico tem 2.000–4.000. 400 já é generoso.


class TextoIlegivel(RuntimeError):
    """O PDF não entregou texto que sirva — e o OCR também não resolveu.

    19/Ago — Antes disto, o SAVE Trial (NEJM 1992) foi ANALISADO em cima de 1.557 caracteres
    de carimbo de download: extração, motor, nota 0, perícia. Gastou LLM para não produzir
    nada. É a mesma família do 'Editorial/Comment entra na fila e vira perícia' que o
    CLAUDE.md já marca como 🔴 BUG — QUEIMA DINHEIRO.

    Não é decisão nova: a LEI 10 diz que o CardioDaily reprova mais, e o dono já disse
    *"não tenho dinheiro para você ficar rasgando"*. Texto ilegível não vira análise —
    para antes de pagar, e vai para revisão humana COM O MOTIVO ESCRITO.
    """


def tesseract_existe():
    """(bool, mensagem). Nunca falha em silêncio."""
    if shutil.which("tesseract"):
        return True, ""
    return False, ("Tesseract não está instalado — sem ele não dá para ler PDF que é "
                   "imagem. No Mac:  brew install tesseract")


def texto_e_util(texto, n_paginas=1):
    """(bool, motivo) — este texto serve para classificar/extrair?

    Duas perguntas, e a segunda é a que pegou o V-HeFT:
      · DENSIDADE — tem caractere suficiente por página?
      · REPETIÇÃO — as páginas são todas iguais? Então é carimbo, não conteúdo.
    """
    t = (texto or "").strip()
    if not t:
        return False, "PDF sem nenhuma camada de texto"

    por_pagina = len(t) / max(n_paginas, 1)
    if por_pagina < MIN_CHARS_PAGINA:
        return False, (f"só {int(por_pagina)} caracteres por página — artigo científico tem "
                       f"milhares. É imagem com carimbo por cima.")

    # ⚠️ O TESTE QUE FALTAVA. O carimbo do NEJM se repete IDÊNTICO em toda página; o
    # conteúdo, não. Se as linhas longas quase todas se repetem, o que temos é moldura.
    linhas = [l.strip() for l in t.splitlines() if len(l.strip()) > 40]
    if linhas:
        unicas = len(set(linhas))
        if unicas / len(linhas) < 0.35:
            return False, (f"as linhas se repetem ({unicas} distintas em {len(linhas)}) — "
                           f"é carimbo de download, não texto do artigo")
    return True, ""


def ocr(caminho, max_paginas=None, dpi=DPI):
    """Texto das páginas via Tesseract. Levanta RuntimeError se o Tesseract faltar."""
    ok, msg = tesseract_existe()
    if not ok:
        raise RuntimeError(msg)
    import io
    import fitz
    import pytesseract
    from PIL import Image

    doc = fitz.open(caminho)
    n = len(doc) if max_paginas is None else min(max_paginas, len(doc))
    partes = []
    for i in range(n):
        pix = doc[i].get_pixmap(dpi=dpi)
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        # `eng` porque o acervo é de revista internacional. Se um dia entrar artigo em
        # português escaneado, acrescentar "eng+por" — mas isso DOBRA o tempo, então não
        # se faz "por via das dúvidas".
        partes.append(pytesseract.image_to_string(img, lang="eng"))
    doc.close()
    return "\n".join(partes)


def extrair(caminho, texto_ja_extraido=None, max_paginas=None):
    """(texto, origem, aviso) — o ponto de entrada.

    origem: 'pdf' (a camada de texto serviu) · 'ocr' · 'pdf_ruim' (não serviu e não deu
    para fazer OCR — e aí quem chama PRECISA saber, para não decidir em cima de carimbo).
    """
    import fitz
    try:
        doc = fitz.open(caminho)
        n_pag = len(doc)
        if texto_ja_extraido is None:
            texto_ja_extraido = "".join(p.get_text() for p in doc)
        doc.close()
    except Exception as e:
        return "", "pdf_ruim", f"não consegui abrir o PDF: {type(e).__name__}: {e}"

    serve, motivo = texto_e_util(texto_ja_extraido, n_pag)
    if serve:
        return texto_ja_extraido, "pdf", ""

    ok, msg = tesseract_existe()
    if not ok:
        return texto_ja_extraido, "pdf_ruim", f"{motivo} · {msg}"

    try:
        t = ocr(caminho, max_paginas=max_paginas)
    except Exception as e:
        return texto_ja_extraido, "pdf_ruim", f"{motivo} · OCR falhou: {type(e).__name__}: {e}"

    serve2, motivo2 = texto_e_util(t, n_pag)
    if not serve2:
        return t, "pdf_ruim", f"{motivo} · e o OCR também não rendeu: {motivo2}"
    return t, "ocr", f"OCR aplicado ({motivo})"
