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
import os, sys, shutil, glob, json

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
import analisador as A          # carrega o .env no import
import publicador as P
P._carregar_env()

# ═══════════ RAMPA DE CONFIANÇA — 04/Ago/2026 ═══════════
# Ideia do Dr. Eduardo: *"vamos rodar com blocos de 10 em 10; depois de 30 consecutivos bons,
# passamos para 3 blocos de 20/20; 3 blocos bons, passamos para 30 em 30"*.
#
# POR QUE É BOM: bloco pequeno = pouca coisa refeita quando cai, e o erro aparece cedo, quando ainda
# custa 10 artigos em vez de 400. Mas bloco pequeno também é mais lento (mais idas ao Supabase).
# A rampa resolve os dois: começa cauteloso e ACELERA à medida que o sistema prova que está bom.
#
# O QUE É "BLOCO BOM": ZERO falhas de análise E ZERO falhas de publicação.
# Artigo RECUSADO por nota baixa NÃO é falha — é o sistema funcionando e dizendo não.
#
# E O QUE ACONTECE SE UM BLOCO FALHA: volta ao degrau 1 (10) e o contador zera. Conservador de
# propósito: subir é opcional, mas voltar a errar 400 de uma vez não pode acontecer duas vezes.
RAMPA = [(10, 3), (20, 3), (30, None)]   # (tamanho do bloco, blocos bons para subir; None = topo)

FILA_FORA = ("_PUBLICADOS", "_RECUSADOS", "MINIRREVISOES")   # NÃO são fila do publicador
# (MINIRREVISOES é a trilha da minirevisão/opinião: condutas+fluxograma via minirevisao.py, não sobe no Supabase)


_CHAVE_DO_TIPO = {"diretriz": "agree", "revisao_narrativa": "qualidade_revisao",
                  "meta": "qualidade_meta"}   # 04/Ago: a meta ganhou schema próprio


def _staging_serve(pasta, pdf):
    """O `_OK` autoriza REUSAR o staging. Esta função decide se ele ainda vale.

    ═══ O ERRO FATÍDICO DE 03/Ago — por que esta função voltou a existir ═══

    Palavras do Dr. Eduardo: *"consertei manualmente os artigos nas pastas e na primeira análise
    ele me lê uma REVISÃO com PROMPT DE ARTIGO ORIGINAL."*

    A causa não estava no analisador — estava AQUI. O laço de blocos fazia só isto:

        if os.path.exists(pasta + "/_OK"): reusa; continue   # nunca chama processar()

    E a pasta do staging é indexada pelo NOME DO ARQUIVO, não pela pasta de origem. Quando ele
    movia o PDF de META_ANALISES para REVISOES, o staging era o mesmo, tinha `_OK`, e era
    REPUBLICADO com a análise velha. A correção manual dele ia para o lixo num `continue`.

    Pior: TODAS as travas que existem para isso moram DENTRO de `processar()` — a checagem de
    tipo no cache de fatos, o apagamento dos derivados velhos, e a LEI 8 ("a pasta manda").
    O `continue` passava por cima das três. Elas eram INALCANÇÁVEIS.

    E havia uma segunda camada do mesmo buraco: a `_staging_atual()`, escrita em 27/Jul contra
    exatamente isto (*"254 de 268 _OK eram de schema velho e furavam os consertos por reuso"*),
    estava DEFINIDA E NUNCA ERA CHAMADA. Código morto. Aquele conserto nunca chegou a rodar.

    REGRA AGORA — só reusa se as DUAS forem verdade:
      1. os fatos do staging foram extraídos para o MESMO tipo que a pasta de hoje diz (LEI 8);
      2. o schema daquele tipo está presente nos fatos (a `_staging_atual` de julho, viva).

    Staging sem o campo `tipo_documento` = feito antes de 03/Ago = feito pela corrente quebrada.
    Não serve. Re-analisa. Isso é de propósito e custa dinheiro uma vez só.
    """
    if not os.path.exists(os.path.join(pasta, "_OK")):
        return False, "sem _OK"
    fj = glob.glob(os.path.join(pasta, "*_fatos.json"))
    if not fj:
        return False, "sem fatos.json"
    try:
        fatos = json.load(open(fj[0], encoding="utf-8"))
    except Exception:
        return False, "fatos.json ilegível"

    # ═══ TERRA ARRASADA (04/Ago) — o carimbo do prompt é o PRIMEIRO portão ═══
    # *"se não tem certeza que foi com ESTE prompt, tem que apagar TUDO deste artigo e começar do
    #   zero"* — Dr. Eduardo. Sem `_versoes.json`, ou com um hash diferente, o pacote NÃO serve.
    # O `processar()` apaga a pasta inteira quando pega o caso; aqui a gente só recusa o reuso.
    try:
        vnow, vold = A.versoes_atuais(pdf), A.versoes_gravadas(pasta)
    except Exception:
        vnow, vold = {}, {}
    if vnow and vold != vnow:
        difs = [k for k, x in vnow.items() if vold.get(k) != x]
        return False, ("sem carimbo de prompt (staging anterior a 04/Ago)" if not vold
                       else f"prompt mudou: {', '.join(difs)}")

    tipo_hoje = A.tipo_do_documento(pdf)                    # ← a PASTA de agora
    tipo_staging = fatos.get("tipo_documento")
    if tipo_staging != tipo_hoje:
        return False, (f"staging é de '{tipo_staging or 'antes de 03/Ago'}', "
                       f"a pasta hoje diz '{tipo_hoje}'")
    chave = _CHAVE_DO_TIPO.get(tipo_hoje, "fracao_ejecao")  # schema do tipo (conserto de 27/Jul)
    if chave not in fatos:
        return False, f"fatos sem o schema de '{tipo_hoje}' (falta '{chave}')"
    return True, ""


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
    """Todos os PDFs ainda por fazer (ignora o que já saiu p/ _PUBLICADOS / _RECUSADOS).

    03/Ago — LEI 8: PDF FORA de uma pasta de tipo NÃO ENTRA. Depois que a pasta virou a fonte
    única do tipo, um PDF solto na raiz de CLASSIFICADOS é um PDF SEM TIPO — e o
    `tipo_do_documento` devolvia 'original' calado, escolhendo motor e prompt no chute. Adivinhar
    aqui é criar a segunda fonte de verdade que a LEI 8 proíbe. Devolve (fila, sem_pasta).
    """
    fila, sem_pasta = [], []
    for root, dirs, files in os.walk(classificados):
        dirs[:] = [d for d in dirs if d not in FILA_FORA]   # não desce nas pastas de concluídos
        conhecida = os.path.basename(root) in A._TIPO_POR_PASTA
        for f in sorted(files):
            if f.lower().endswith(".pdf") and not f.startswith("._"):
                (fila if conhecida else sem_pasta).append(os.path.join(root, f))
    return sorted(fila), sorted(sem_pasta)


def _tirar_da_fila(pdf, classificados, subpasta):
    """Move o PDF fonte p/ CLASSIFICADOS/_PUBLICADOS (ou _RECUSADOS) — sai da fila de vez."""
    dest = os.path.join(classificados, subpasta)
    os.makedirs(dest, exist_ok=True)
    try:
        shutil.move(pdf, os.path.join(dest, os.path.basename(pdf)))
    except Exception as e:
        print(f"      (aviso: não moveu {os.path.basename(pdf)}: {e})")


def main(classificados, tam_bloco=20, maximo=0, rampa=False, so_pasta="", so_artigo=""):
    staging = os.path.abspath(os.path.join(_HERE, "..", "outputs", "STAGING"))
    os.makedirs(staging, exist_ok=True)
    fila, sem_pasta = _pdfs_na_fila(classificados)
    # ═══ 05/Ago — `--artigo=<pedaço do nome>`: rodar UM artigo escolhido ═══
    # O Dr. Eduardo pediu uma amostra de 1 artigo original e 1 revisão antes de gastar nos 431.
    # Com `--max=1` puro sairia o PRIMEIRO da ordem alfabética — e na REVISOES o primeiro é um
    # `2014_07_.pdf`, sem título nem revista no nome. A amostra sairia ruim por motivo errado.
    # Este filtro deixa ESCOLHER: casa por substring, sem acento, em qualquer parte do nome.
    if so_artigo:
        import unicodedata as _u
        def _norm(s):
            s = _u.normalize("NFD", (s or "").lower())
            return "".join(c for c in s if _u.category(c) != "Mn")
        alvo = _norm(so_artigo)
        antes = len(fila)
        fila = [p for p in fila if alvo in _norm(os.path.basename(p))]
        print(f"SÓ O ARTIGO que casa com '{so_artigo}': {len(fila)} de {antes}\n")
        if not fila:
            print(f"Nenhum PDF casa com '{so_artigo}'. Confira o pedaço do nome.")
            return 1
    if so_pasta:
        antes = len(fila)
        fila = [p for p in fila if os.path.basename(os.path.dirname(p)) == so_pasta]
        print(f"SÓ A PASTA {so_pasta}: {len(fila)} de {antes} artigos "
              f"(as outras pastas ficam intactas na fila)\n")
        if not fila:
            print(f"Nenhum PDF em {so_pasta}. Pastas disponíveis: "
                  + ", ".join(sorted(A._TIPO_POR_PASTA))); return 1
    if sem_pasta:
        print(f"⛔ {len(sem_pasta)} PDF FORA de pasta de tipo — NÃO entram (LEI 8: sem pasta, sem tipo):")
        for p in sem_pasta[:10]:
            print(f"     · {os.path.relpath(p, classificados)}")
        if len(sem_pasta) > 10:
            print(f"     · (+{len(sem_pasta)-10})")
        print("   Mova-os para a pasta certa, ou devolva à fila (Chave 10) e rode a Chave 1.\n")
    if maximo:                                          # teste de confiança: só os primeiros N
        fila = fila[:maximo]
    total = len(fila)
    if total == 0:
        print("Fila vazia — nada a fazer (tudo já concluído, ou pasta sem PDF).")
        return
    pub_ok = pub_rec = 0
    falhou = []                      # 03/Ago: as falhas rolavam a tela e sumiam. Agora viram lista no fim.

    # ── a fila é consumida em blocos de tamanho VARIÁVEL (a rampa) ──
    degrau = 0 if rampa else None
    bons_seguidos = 0
    i, nb = 0, 0
    if rampa:
        print(f"RAMPA DE CONFIANÇA: {' → '.join(str(t) for t, _ in RAMPA)} "
              f"(sobe após {RAMPA[0][1]} blocos sem falha; qualquer falha volta ao {RAMPA[0][0]})\n")
    while i < total:
        tam = RAMPA[degrau][0] if rampa else tam_bloco
        # ═══ 04/Ago — O BLOCO NÃO ATRAVESSA A DIVISA ENTRE PASTAS ═══
        # Pergunta do Dr. Eduardo: *"não combinamos que o sistema ia ler pasta por pasta, para
        # aplicar o prompt aos artigos daquela pasta?"* — e ia, e vai: cada PDF carrega o caminho
        # dele, e é a pasta que decide prompt e motor (LEI 8). Mas 3 dos 18 blocos CAÍAM em cima da
        # divisa, misturando ARTIGOS_ORIGINAIS com GUIDELINES no mesmo bloco. Não quebrava nada —
        # estragava o DIAGNÓSTICO: um problema no prompt de diretriz aparecia num bloco que era
        # metade artigo original, e a rampa não sabia de quem era a culpa.
        pasta_do_bloco = os.path.basename(os.path.dirname(fila[i]))
        bloco = []
        for p in fila[i:i + tam]:
            if os.path.basename(os.path.dirname(p)) != pasta_do_bloco:
                break                                   # fecha o bloco na divisa
            bloco.append(p)
        nb += 1
        etiqueta = (f" · degrau {degrau+1}/{len(RAMPA)} (até {tam}) · "
                    f"{bons_seguidos} bom(ns) seguido(s)" if rampa else "")
        print(f"═══ BLOCO {nb} · {pasta_do_bloco} · artigos {i+1}–{i+len(bloco)} de {total}"
              f"{etiqueta} ═══")
        falhas_no_bloco = 0

        # 1) analisa o bloco (local, no staging). RETOMÁVEL: staging que SERVE é reaproveitado.
        analisados = []
        for pdf in bloco:
            base = os.path.splitext(os.path.basename(pdf))[0]
            pasta = os.path.join(staging, base)
            serve, porque = _staging_serve(pasta, pdf)
            if serve:
                analisados.append((pdf, pasta))
                print(f"   reusado    {base[:42]:42} (staging pronto)")
                continue
            if os.path.exists(os.path.join(pasta, "_OK")):
                print(f"   ↻ REANALISA {base[:42]:42} — {porque}")
            try:
                base, nota, mc, ents, sobe = A.processar(pdf, staging)
                analisados.append((pdf, os.path.join(staging, base)))
                print(f"   analisado  {base[:42]:42} nota {nota}")
            except Exception as e:
                print(f"   ⚠️  análise falhou (fica na fila p/ refazer): "
                      f"{os.path.basename(pdf)[:42]} — {type(e).__name__}: {e}")
                falhou.append((os.path.basename(pdf), f"análise · {type(e).__name__}: {str(e)[:50]}"))
                falhas_no_bloco += 1

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
                falhou.append((os.path.basename(pasta), f"publicação · {type(e).__name__}: {str(e)[:50]}"))
                falhas_no_bloco += 1

        # ── a rampa decide o tamanho do PRÓXIMO bloco ──
        if rampa:
            if falhas_no_bloco == 0:
                bons_seguidos += 1
                alvo = RAMPA[degrau][1]
                if alvo is not None and bons_seguidos >= alvo and degrau + 1 < len(RAMPA):
                    degrau += 1; bons_seguidos = 0
                    print(f"   ⬆️  {alvo} blocos sem falha — SUBINDO para blocos de {RAMPA[degrau][0]}")
            else:
                if degrau != 0:
                    print(f"   ⬇️  {falhas_no_bloco} falha(s) neste bloco — VOLTANDO para blocos de "
                          f"{RAMPA[0][0]} (o contador zera)")
                degrau = 0; bons_seguidos = 0
        print(f"═══ BLOCO {nb} fechado · publicados {pub_ok} · recusados {pub_rec} · "
              f"falhas neste bloco {falhas_no_bloco} ═══\n")
        i += len(bloco)

    print(f"FIM · {pub_ok} publicado(s) no Supabase (rascunho) · {pub_rec} recusado(s) (em _RECUSADOS).")
    if falhou:
        print(f"\n⚠️  {len(falhou)} artigo(s) FALHARAM e ficaram na fila para refazer:")
        for nome, motivo in falhou[:15]:
            print(f"     · {nome[:44]:44} {motivo}")
        if len(falhou) > 15:
            print(f"     · (+{len(falhou)-15} — veja o diário completo)")
    print("Se sobrou algo na fila (falha de rede), é só clicar a Chave 2 de novo — ela continua.")
    return 1 if falhou else 0


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--max")]
    mx = next((int(a.split("=")[1]) for a in sys.argv[1:] if a.startswith("--max=")), 0)
    rampa = "--rampa" in sys.argv[1:]
    so_pasta = next((a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--pasta=")), "")
    so_artigo = next((a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--artigo=")), "")
    args = [a for a in args if a != "--rampa" and not a.startswith("--pasta=")
            and not a.startswith("--artigo=")]
    cl = os.path.expanduser(args[0]) if args else ""
    tb = int(args[1]) if len(args) > 1 else 20
    if not cl or not os.path.isdir(cl):
        print("uso: python rodar_em_blocos.py <pasta_CLASSIFICADOS> [tam_bloco=20] [--max=N] [--rampa] [--pasta=META_ANALISES]"); sys.exit(1)
    # 03/Ago — o código de saída passa a VALER: a Chave 2 lê ele e só chama o minirevisao se for 0.
    # Antes, um Ctrl+C aqui caía direto na trilha da minirevisão (mais 81 artigos pagos): o
    # "eu interrompi e ele não para" do Dr. Eduardo.
    try:
        sys.exit(main(cl, tb, mx, rampa, so_pasta, so_artigo) or 0)
    except KeyboardInterrupt:
        print("\n\n⛔ INTERROMPIDO POR VOCÊ (Ctrl+C). O que já publicou está salvo no Supabase;"
              "\n   o resto continua na fila. Clique a Chave 2 de novo quando quiser continuar.")
        sys.exit(130)
