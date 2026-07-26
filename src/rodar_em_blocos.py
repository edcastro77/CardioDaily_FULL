"""
rodar_em_blocos.py — a Chave 2 (Analisador) chama isto. Roda a corrente do FULL em BLOCOS de N (default 20).

POR QUE BLOCOS (exigência do Dr. Eduardo, plantão com internet instável):
  numa rodada de horas, cair NÃO pode estragar tudo. Cada bloco é ANALISADO e PUBLICADO no Supabase
  antes do próximo. Se cair no meio:
    • os blocos já publicados estão SEGUROS no Supabase (upsert idempotente por doc_id) — não se perdem;
    • cada PDF concluído SAI da fila fisicamente (vai p/ CLASSIFICADOS/_PUBLICADOS ou /_RECUSADOS);
    • só o bloco em andamento (≤N) é refeito ao reiniciar (clicar a Chave 2 de novo).

NÃO usa "pular por marcador" (que sempre dá problema). O estado é FÍSICO: o que está na fila ainda
falta; o que saiu da fila, acabou. Reiniciar = continuar de onde parou, sem confiar em flag nenhuma.

Uso (o botão faz):  python rodar_em_blocos.py <pasta_CLASSIFICADOS> [tam_bloco=20]
"""
import os, sys, shutil

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
import analisador as A          # carrega o .env no import
import publicador as P
P._carregar_env()

FILA_FORA = ("_PUBLICADOS", "_RECUSADOS")   # subpastas que NÃO são fila (já processados)


def analisar_e_publicar_um(pdf, staging=None, publicar=True):
    """Adaptador de 1 artigo para a CORRENTE NOVA — o ponto único que aposenta o article_analyzer.
    Analisa (analisador) → publica pelo portão (publicador: contrato + preflight) → devolve o doc_id.
    Usado pelo webhook do WhatsApp (on-demand). Devolve (doc_id | None, status, nota).
    nota <6 fica RETIDO (não publica, sem doc_id)."""
    from analisador import processar
    import publicador as P
    import ficha_site as F
    P._carregar_env()
    if staging is None:
        staging = os.path.abspath(os.path.join(_HERE, "..", "outputs", "STAGING"))
    os.makedirs(staging, exist_ok=True)
    base, nota, _mc, _ents, sobe = processar(pdf, staging)
    if not sobe:                                    # ≤5: retido por regra, não vai pro site
        return None, "RETIDO(<6)", nota
    pasta = os.path.join(staging, base)
    status, nota, _viol = P.processar_pasta(pasta, publicar=publicar)
    doc_id = F.montar(pasta).get("doc_id") if str(status).startswith(("PUBLICADO", "APROVADO")) else None
    return doc_id, status, nota


def _pdfs_na_fila(classificados):
    """Todos os PDFs ainda por fazer (ignora o que já saiu p/ _PUBLICADOS / _RECUSADOS)."""
    fila = []
    for root, dirs, files in os.walk(classificados):
        dirs[:] = [d for d in dirs if d not in FILA_FORA]   # não desce nas pastas de concluídos
        for f in sorted(files):
            if f.lower().endswith(".pdf") and not f.startswith("._"):
                fila.append(os.path.join(root, f))
    return sorted(fila)


def _tirar_da_fila(pdf, classificados, subpasta):
    """Move o PDF fonte p/ CLASSIFICADOS/_PUBLICADOS (ou _RECUSADOS) — sai da fila de vez."""
    dest = os.path.join(classificados, subpasta)
    os.makedirs(dest, exist_ok=True)
    try:
        shutil.move(pdf, os.path.join(dest, os.path.basename(pdf)))
    except Exception as e:
        print(f"      (aviso: não moveu {os.path.basename(pdf)}: {e})")


def main(classificados, tam_bloco=20):
    staging = os.path.abspath(os.path.join(_HERE, "..", "outputs", "STAGING"))
    os.makedirs(staging, exist_ok=True)
    fila = _pdfs_na_fila(classificados)
    total = len(fila)
    if total == 0:
        print("Fila vazia — nada a fazer (tudo já concluído, ou pasta sem PDF).")
        return
    n_blocos = (total + tam_bloco - 1) // tam_bloco
    print(f"EM BLOCOS DE {tam_bloco}  ·  {total} artigo(s) na fila  ·  {n_blocos} bloco(s)  →  {staging}\n")
    pub_ok = pub_rec = 0
    for i in range(0, total, tam_bloco):
        bloco = fila[i:i + tam_bloco]
        nb = i // tam_bloco + 1
        print(f"═══ BLOCO {nb}/{n_blocos} · artigos {i+1}–{i+len(bloco)} de {total} ═══")
        # 1) analisa o bloco (local, no staging)
        analisados = []
        for pdf in bloco:
            try:
                base, nota, mc, ents, sobe = A.processar(pdf, staging)
                analisados.append((pdf, os.path.join(staging, base)))
                print(f"   analisado  {base[:42]:42} nota {nota}")
            except Exception as e:
                print(f"   ⚠️  análise falhou (fica na fila p/ refazer): "
                      f"{os.path.basename(pdf)[:42]} — {type(e).__name__}: {e}")
        # 2) publica o bloco no Supabase; só o que SUBIU sai da fila
        for pdf, pasta in analisados:
            try:
                status, nota, viol = P.processar_pasta(pasta, publicar=True)
                print(f"   {status:16} {os.path.basename(pasta)[:40]}")
                if str(status).startswith("PUBLICADO"):
                    _tirar_da_fila(pdf, classificados, "_PUBLICADOS"); pub_ok += 1
                else:                                            # RECUSADO pelo portão/preflight
                    _tirar_da_fila(pdf, classificados, "_RECUSADOS"); pub_rec += 1
            except Exception as e:
                print(f"   ⚠️  publicação falhou (fica na fila p/ refazer): "
                      f"{os.path.basename(pasta)[:40]} — {type(e).__name__}: {e}")
        print(f"═══ BLOCO {nb}/{n_blocos} fechado · publicados até agora {pub_ok} · recusados {pub_rec} · "
              f"se cair agora, só este bloco refaz ═══\n")
    print(f"FIM · {pub_ok} publicado(s) no Supabase (rascunho) · {pub_rec} recusado(s) (em _RECUSADOS).")
    print("Se sobrou algo na fila (falha de rede), é só clicar a Chave 2 de novo — ela continua.")


if __name__ == "__main__":
    cl = os.path.expanduser(sys.argv[1]) if len(sys.argv) > 1 else ""
    tb = int(sys.argv[2]) if len(sys.argv) > 2 else 20
    if not cl or not os.path.isdir(cl):
        print("uso: python rodar_em_blocos.py <pasta_CLASSIFICADOS> [tam_bloco=20]"); sys.exit(1)
    main(cl, tb)
