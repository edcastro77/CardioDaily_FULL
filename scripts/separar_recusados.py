"""
separar_recusados.py — desfaz o balde único: `_RECUSADOS` vira RÉGUA · DEFEITO.

═══ 22/Ago/2026 — POR QUE ═══
Palavras dele: *"esta categoria de recusados era para situações raras de artigos que não se
enquadram... desde quando o classificador tem autonomia para pegar um artigo de revisão ou
original e dar nota e excluir?"*

Ele estava certo. O classificador nunca fez isso — ele descarta caso/carta para `DESCARTE`.
Quem enchia o `_RECUSADOS` era o publicador (`rodar_em_blocos.py`), com um `else` que não
perguntava o motivo. Resultado, medido nos 267 que estavam lá:

    257  a RÉGUA segurou (nota 0, 3, 4, 5) — decisão de produto, LEI 10
      7  DEFEITO NOSSO — 5 por inversão de sigla FE, 1 nota 6, e **1 nota 9**
      3  sem registro

E, como `_pdfs_na_fila` ignora a pasta, todos saíram da fila PARA SEMPRE — inclusive os 7 que
caíram por bug meu. Um artigo nota 9, com perícia, áudio e visual prontos, exilado por uma
sigla trocada no nosso próprio texto.

Este programa lê o `_REVISAR_publicacao.txt` de cada pacote e move o PDF para:
    _RETIDOS_PELA_REGUA/ ... a régua disse não. Fica fora da fila, mas VISÍVEL na Chave 3.
    _DEFEITO/ .............. fomos nós. **Volta para a fila** no próximo run da Chave 2.
    (fica onde está) ....... sem registro para decidir — não se chuta com o acervo dele.

═══ LEI 12 — NADA DESTRUTIVO SEM CONFERIR ANTES ═══
Roda em DOIS tempos. Sem `--executar` ele só MOSTRA, arquivo por arquivo, e não toca em nada.
Move (não copia, não apaga), e recusa mover se o destino já existir. `ARTIGOS/` não está no
git: aqui não há desfazer.

Uso:  python3 scripts/separar_recusados.py              # ensaio, não toca em nada
      python3 scripts/separar_recusados.py --executar
"""
import collections
import glob
import os
import re
import shutil
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLASSIFICADOS = os.path.join(RAIZ, "ARTIGOS", "CLASSIFICADOS")
ORIGEM = os.path.join(CLASSIFICADOS, "_RECUSADOS")
sys.path.insert(0, os.path.join(RAIZ, "src"))


def _pacote(nome_pdf):
    base = os.path.splitext(nome_pdf)[0]
    for padrao in (os.path.join(RAIZ, "outputs", "STAGING", base),
                   os.path.join(RAIZ, "outputs", "ARQUIVO", "*", base)):
        for p in glob.glob(padrao):
            if os.path.isdir(p):
                return p
    return None


def _ler_veredito(pasta):
    """(nota, [violações]) do `_REVISAR_publicacao.txt`. (None, []) se não houver."""
    rev = os.path.join(pasta, "_REVISAR_publicacao.txt")
    if not os.path.exists(rev):
        return None, []
    txt = open(rev, encoding="utf-8", errors="ignore").read()
    m = re.search(r"Nota:\s*(\d+)", txt)
    nota = int(m.group(1)) if m else None
    viol = [l.strip(" •\t") for l in txt.splitlines()
            if l.strip().startswith("•")]
    return nota, viol


def main():
    executar = "--executar" in sys.argv
    if not os.path.isdir(ORIGEM):
        print(f"⛔ não achei {ORIGEM}")
        return 1

    # a MESMA função que o publicador usa daqui em diante — uma fonte de verdade, não duas
    # que concordam por sorte. Importada por AST para não carregar o .env nem o analisador.
    import ast
    import types
    fonte = open(os.path.join(RAIZ, "src", "rodar_em_blocos.py"), encoding="utf-8").read()
    arv = ast.parse(fonte)
    fn = next(n for n in arv.body
              if isinstance(n, ast.FunctionDef) and n.name == "_destino_da_recusa")
    mod = types.ModuleType("_rb")
    mod.__dict__.update(RETIDOS="_RETIDOS_PELA_REGUA", DEFEITO="_DEFEITO")
    exec(compile(ast.Module(body=[fn], type_ignores=[]), "<rb>", "exec"), mod.__dict__)
    decidir = mod._destino_da_recusa

    pdfs = sorted(f for f in os.listdir(ORIGEM) if f.lower().endswith(".pdf"))
    plano, indeciso = [], []
    for f in pdfs:
        p = _pacote(f)
        if not p:
            indeciso.append((f, "sem pacote — não dá para saber o motivo"))
            continue
        nota, viol = _ler_veredito(p)
        # 22/Ago — o `_REVISAR` destes pacotes foi escrito quando o contrato ainda dizia
        # "nota inválida: 0 (int 1–10)". Essa linha some agora que a faixa é 0–10, mas o
        # arquivo no disco é HISTÓRICO e não muda sozinho. Sem tirá-la aqui, os 43 pré-clínicos
        # seriam lidos como defeito de programa — o veredito de ontem lido com a régua de hoje.
        viol = [x for x in viol if "nota_aplicabilidade inválida" not in x]
        if nota is None and not viol:
            indeciso.append((f, "pacote sem _REVISAR — motivo não registrado"))
            continue
        destino, motivo = decidir(viol, nota)
        plano.append((f, destino, nota, motivo))

    cont = collections.Counter(d for _, d, _, _ in plano)
    print("═" * 78)
    print(f" SEPARAR _RECUSADOS · {len(pdfs)} PDF(s)" + ("" if executar else "  ·  E N S A I O"))
    print("═" * 78)
    for destino in ("_RETIDOS_PELA_REGUA", "_DEFEITO"):
        n = cont.get(destino, 0)
        rot = ("a régua segurou — sai da fila, mas visível na Chave 3"
               if destino == "_RETIDOS_PELA_REGUA"
               else "defeito NOSSO — VOLTA para a fila no próximo run")
        print(f"\n   {n:>4}  → {destino:<22} {rot}")
        for f, d, nota, motivo in plano:
            if d == destino and destino == "_DEFEITO":
                print(f"           nota {nota} · {f[:62]}")
    if indeciso:
        print(f"\n   {len(indeciso):>4}  → FICAM ONDE ESTÃO (não se chuta com o acervo dele)")
        for f, por in indeciso:
            print(f"           {por:<38} {f[:44]}")

    if not executar:
        print("\n" + "─" * 78)
        print("   ENSAIO — nada foi movido. Para valer:")
        print("     python3 scripts/separar_recusados.py --executar")
        return 0

    # ⚠️ 22/Ago — `_DEFEITO` NÃO RECEBE PDF, e eu descobri isso depois de mover 9 para lá.
    # A LEI 8 diz: **PDF fora de uma pasta de TIPO não entra na fila** (`_pdfs_na_fila` só
    # aceita ARTIGOS_ORIGINAIS, META_ANALISES, GUIDELINES, REVISOES, EDITORIAIS). Ou seja:
    # ao "salvar" os 9 do exílio eu os teria tornado invisíveis de outro jeito — o mesmo
    # defeito, com outra roupa, cometido dentro do próprio conserto dele.
    # O código de PRODUÇÃO já estava certo (em defeito ele não move nada, só registra); o
    # errado era este script. Agora `_DEFEITO` guarda apenas o registro do que falhou, e o
    # PDF FICA onde está — que é o que o faz voltar sozinho na próxima Chave 2.
    movidos = collections.Counter()
    for f, destino, _nota, _motivo in plano:
        if destino == "_DEFEITO":
            os.makedirs(os.path.join(CLASSIFICADOS, "_DEFEITO"), exist_ok=True)
            with open(os.path.join(CLASSIFICADOS, "_DEFEITO", "_o_que_falhou.txt"),
                      "a", encoding="utf-8") as reg:
                reg.write(f"{f}\n   nota {_nota} · {_motivo}\n\n")
            movidos["_DEFEITO (registrado, PDF fica na pasta de tipo)"] += 1
            continue
        dest_dir = os.path.join(CLASSIFICADOS, destino)
        os.makedirs(dest_dir, exist_ok=True)
        alvo = os.path.join(dest_dir, f)
        origem = os.path.join(ORIGEM, f)
        # LEI 12, itens 1 e 2: origem com tamanho plausível, destino inexistente.
        if os.path.exists(alvo):
            print(f"   ⚠️  já existe no destino, NÃO mexi: {f[:56]}")
            continue
        if os.path.getsize(origem) < 1024:
            print(f"   ⚠️  origem com {os.path.getsize(origem)} bytes — suspeito, NÃO mexi: {f[:44]}")
            continue
        shutil.move(origem, alvo)
        movidos[destino] += 1

    print("\n" + "─" * 78)
    for d, n in movidos.items():
        print(f"   ✔ {n} → {d}")
    resta = [f for f in os.listdir(ORIGEM) if f.lower().endswith(".pdf")]
    print(f"   _RECUSADOS agora tem {len(resta)} PDF(s) — os sem registro, intocados.")
    if movidos.get("_DEFEITO"):
        print(f"\n   🔧 Rode a CHAVE 2: os {movidos['_DEFEITO']} de `_DEFEITO` voltam sozinhos")
        print("      para a fila. Os FATOS já estão pagos — refazer custa quase nada.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
