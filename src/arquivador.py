"""
arquivador.py — O APP ARQUIVADOR (bloco 5 do Full). Trabalho: ARQUIVAR, e ponto.
Roda DEPOIS do publicador. Move as pastas do STAGING pro ARQUIVO/AAAA-MM/ e limpa o staging.
Não decide nada (não é porteiro — o cuidado com prompt/nome/reanálise é do classificador e do analisador).
Nunca DELETA — só MOVE. Default --dry-run.

Uso:
  python arquivador.py <STAGING>               # dry-run: mostra o que arquivaria
  python arquivador.py <STAGING> --arquivar     # move tudo pra ARQUIVO/AAAA-MM/ e limpa o staging
"""
import os, sys, glob, shutil, argparse, datetime


def rodar(staging, executar=False, arquivo_dir=None):
    staging = os.path.abspath(os.path.expanduser(staging))
    if arquivo_dir is None:
        arquivo_dir = os.path.abspath(os.path.join(staging, "..", "ARQUIVO"))
    mes = datetime.date.today().strftime("%Y-%m")
    pastas = sorted(p for p in glob.glob(os.path.join(staging, "*")) if os.path.isdir(p))

    print(f"ARQUIVADOR — {len(pastas)} pasta(s) → {arquivo_dir}/{mes}/  ·  modo: {'ARQUIVAR' if executar else 'DRY-RUN'}\n")
    n = err = 0
    for pasta in pastas:
        base = os.path.basename(pasta)
        dst = os.path.join(arquivo_dir, mes, base)
        if executar:
            try:
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.move(pasta, dst)
            except Exception as e:
                print(f"  ⚠️  {base[:50]} — {type(e).__name__}: {e}")
                err += 1
                continue
        print(f"  arquiva  {base[:56]}")
        n += 1
    print(f"\n{n} arquivado(s)" + (f" · {err} erro(s)" if err else "")
          + ("" if executar else "   (dry-run — rode com --arquivar para mover)"))
    return n, err


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Arquivador (bloco 5) — move o STAGING pro ARQUIVO")
    ap.add_argument("staging", help="pasta STAGING")
    ap.add_argument("--arquivar", action="store_true", help="move de verdade (default: dry-run)")
    ap.add_argument("--arquivo", default=None, help="pasta de destino (default: ../ARQUIVO ao lado do staging)")
    a = ap.parse_args()
    rodar(a.staging, executar=a.arquivar, arquivo_dir=a.arquivo)
