"""
mesh_backfill.py — enche o `mesh_terms` das linhas que já estão no banco vazias.

═══ 22/Ago/2026 — O QUE ESTE PROGRAMA CONSERTA ═══

Medido no acervo de 704: **208 linhas com `mesh_terms` vazio.** E `mesh_terms` não é enfeite —
é por ele que o **Pesquisador** acha material. Vazio, o artigo existe no banco e é invisível
para quem procura.

As três causas, medidas (não supostas):

    38  anteriores à era do DOI — doc_id "Sintetico_": CONSENSUS 1987, CIBIS-II, RALES,
        MERIT-HF, COPERNICUS, FAME. O DOI só virou universal nos anos 2000.
     1  DOI truncado ("10.2174", só o prefixo Bentham) — defeito, nunca vai resolver
   169  DOI real, 157 deles de 2026 — o indexador HUMANO da NLM ainda não chegou

E a medida que decidiu tudo — 25 sorteados do grupo dos 169, perguntando ao PubMed naquele
instante: **0/25 já tinham MeSH.** 21 estavam no PubMed sem descritor; 4 nem no PubMed
(diretrizes SBC). Ou seja: rodar `mesh_faltantes.py` de novo não conserta uma única linha hoje.

Por isso o `src/mesh_llm.py`: o modelo PROPÕE e a amarra RESOLVE contra o vocabulário oficial
da NLM, descartando o que não é descritor de verdade. Descritor inventado seria pior que
descritor faltando — entra na busca e nunca casa com nada.

═══ LEI 5 — ESTE PROGRAMA NÃO ESCREVE NO SUPABASE ═══
Ele **gera SQL** em `saidas/MESH_LLM.sql`, e quem roda é o Dr. Eduardo, no SQL Editor. Quem
escreve linha de artigo é o `publicador.py`, e só ele. Este aqui é conserto de retaguarda de
linhas que já subiram — não é portão, e não vira portão.

═══ CUSTO ═══
~US$ 0,0006 por artigo · 208 artigos ≈ **US$ 0,13**. Ele já recusou uma proposta de US$ 19
para tapar buraco, e tinha razão: *"não tem cabimento pagar 19 dólares, 100 reais, para
consertar os buracos"*. Reanálise custa caro porque re-extrai tudo; isto só olha título e
resumo, que o banco já tem.

Uso:  python3 scripts/mesh_backfill.py            # roda tudo, grava o SQL
      python3 scripts/mesh_backfill.py --limite 10   # prova com 10, para conferir antes
      python3 scripts/mesh_backfill.py --reconferir  # limpa os "não existe" do cache e refaz
"""
import json
import os
import sys
import urllib.parse
import urllib.request

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "src"))
SAIDA = os.path.join(RAIZ, "saidas", "MESH_LLM.sql")


def _env():
    for l in open(os.path.join(RAIZ, ".env"), encoding="utf-8", errors="ignore"):
        l = l.strip()
        if "=" in l and not l.startswith("#"):
            k, v = l.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    key = (os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_SERVICE_KEY")
           or os.environ.get("SUPABASE_KEY", ""))
    return url, key


def _vazios(url, key):
    p = {"select": "doc_id,doi,titulo,revista,resumo_markdown,contexto_tema,keywords,mesh_terms",
         "limit": "3000"}
    r = urllib.request.Request(f"{url}/rest/v1/artigos?{urllib.parse.urlencode(p)}",
                               headers={"apikey": key, "Authorization": f"Bearer {key}"})
    linhas = json.load(urllib.request.urlopen(r, timeout=60))
    def vazio(v):
        return v is None or (isinstance(v, list) and not v) or str(v).strip() in ("", "[]", "{}")
    return [x for x in linhas if vazio(x.get("mesh_terms"))], len(linhas)


def esc(s):
    return str(s or "").replace("'", "''")


def conferir(url, key):
    """A conferência DEPOIS de aplicar o SQL — sem LLM, sem custo, sem escrever nada.

    ═══ 22/Ago — POR QUE ISTO É UM BOTÃO E NÃO UMA CONSULTA ═══
    Eu havia deixado a conferência como a última linha do `MESH_LLM.sql`, contando que ele
    lesse o resultado no SQL Editor. Ele respondeu: *"esta última conferência que não sei como
    fazer?"* — e a pergunta é justa. **Conferência que depende de o dono saber ler saída de SQL
    não é conferência: é mais uma coisa que fica sem ser feita.** Foi assim que 208 linhas
    ficaram vazias sem ninguém ver.
    """
    p = {"select": "doc_id,mesh_terms,mesh_origem,titulo", "limit": "3000"}
    r = urllib.request.Request(f"{url}/rest/v1/artigos?{urllib.parse.urlencode(p)}",
                               headers={"apikey": key, "Authorization": f"Bearer {key}"})
    try:
        linhas = json.load(urllib.request.urlopen(r, timeout=60))
    except Exception as e:
        # ⚠️ a coluna `mesh_origem` pode não existir ainda — e aí o PostgREST devolve 400.
        # Dizer "erro" seria inútil; o que ele precisa é saber que falta o ALTER TABLE.
        print(f"⛔ não consegui ler o banco: {type(e).__name__}")
        print("   Se a mensagem fala em 'mesh_origem', é porque o ALTER TABLE ainda não rodou.")
        print("   Ele é a PRIMEIRA linha do saidas/MESH_LLM.sql.")
        return 1

    def vazio(v):
        return v is None or (isinstance(v, list) and not v) or str(v).strip() in ("", "[]", "{}")

    vazios = [x for x in linhas if vazio(x.get("mesh_terms"))]
    por_origem = {}
    for x in linhas:
        por_origem[x.get("mesh_origem") or "(sem origem)"] = \
            por_origem.get(x.get("mesh_origem") or "(sem origem)", 0) + 1

    print("═" * 70)
    print(" CONFERÊNCIA DO MeSH · o que está no Supabase agora")
    print("═" * 70)
    print(f"\n   {len(linhas)} artigos no banco\n")
    for o, n in sorted(por_origem.items(), key=lambda x: -x[1]):
        rot = {"pubmed": "descritor HUMANO da NLM (a verdade)",
               "mesh_llm": "proposto pelo modelo, conferido contra o oficial",
               "(sem origem)": "⚠️  linha antiga, ainda sem procedência"}.get(o, o)
        print(f"      {n:>5}  {o:<14} {rot}")

    print()
    if not vazios:
        print("   ✅ ZERO vazios. Todo artigo do acervo é achável pelo Pesquisador.")
        return 0
    print(f"   ⚠️  {len(vazios)} AINDA VAZIOS — invisíveis para quem procura:")
    for x in vazios[:10]:
        print(f"        · {str(x.get('titulo'))[:60]}")
    if len(vazios) > 10:
        print(f"        … e mais {len(vazios) - 10}")
    print("\n   Rode a CHAVE 25 de novo (ela pula quem já está no SQL e refaz só estes).")
    return 0


def main():
    if "--conferir" in sys.argv:
        url, key = _env()
        return conferir(url, key)
    limite = None
    if "--limite" in sys.argv:
        limite = int(sys.argv[sys.argv.index("--limite") + 1])

    url, key = _env()
    if not url or not key:
        print("⛔ SUPABASE_URL/KEY não encontrados no .env")
        return 1

    import mesh_llm as ML
    if "--reconferir" in sys.argv:
        # os `null` do cache são "a NLM disse que não existe" OU "a rede caiu" — e o
        # `_perguntar_a_nlm` não distingue os dois. Limpar só os null refaz as perguntas
        # duvidosas sem perder o que já resolveu.
        c, _ = ML._indices()
        mortos = [k for k, v in c.items() if v is None]
        for k in mortos:
            del c[k]
        ML._gravar_cache()
        print(f"   ↻ {len(mortos)} termos não resolvidos saíram do cache\n")

    alvo, total = _vazios(url, key)
    if limite:
        alvo = alvo[:limite]
    print(f"{total} linhas no banco · {len(alvo)} com mesh_terms vazio"
          f"{f' · rodando {limite}' if limite else ''}\n")
    if not alvo:
        print("✔ nada a fazer.")
        return 0

    # ═══ RETOMADA — porque rodar de novo PAGA DE NOVO ═══
    # O banco só muda quando o Dr. Eduardo aplica o SQL. Entre gerar e aplicar, qualquer segunda
    # rodada acha exatamente os mesmos vazios e paga tudo outra vez. Foi assim que em 20/Ago
    # 49 artigos foram cobrados duas vezes — 99 linhas para 50 artigos — porque o arquivo era
    # escrito com `;` e relido sem, e a retomada não achava nada.
    # Aqui a retomada lê o PRÓPRIO SQL já gerado e pula quem já está lá.
    ja = set()
    if os.path.exists(SAIDA) and "--zero" not in sys.argv:
        import re as _re
        for l in open(SAIDA, encoding="utf-8"):
            m = _re.search(r"WHERE doc_id='(.+?)';", l)
            if m:
                ja.add(m.group(1).replace("''", "'"))
    if ja:
        antes = len(alvo)
        alvo = [a for a in alvo if a.get("doc_id") not in ja]
        print(f"   ↻ {len(ja)} já estão no SQL de antes — pulando ({antes} → {len(alvo)})")
        print(f"     (use --zero para refazer tudo do começo)\n")
    if not alvo:
        print(f"✔ todos já estão em {SAIDA}. Aplique-o no Supabase.")
        return 0

    os.makedirs(os.path.dirname(SAIDA), exist_ok=True)
    feitos, falhos = 0, []
    modo = "w" if ("--zero" in sys.argv or not ja) else "a"
    with open(SAIDA, modo, encoding="utf-8") as f:
        if modo == "w":
            f.write("-- MESH_LLM.sql · gerado por scripts/mesh_backfill.py\n")
            f.write("-- Descritores propostos pelo modelo e RESOLVIDOS contra o vocabulário\n")
            f.write("-- oficial da NLM. A varredura semanal os SUBSTITUI pelo MeSH humano\n")
            f.write("-- assim que a NLM indexar — é para isso que serve `mesh_origem`.\n\n")
            f.write("ALTER TABLE artigos ADD COLUMN IF NOT EXISTS mesh_origem text;\n\n")
            # quem JÁ tem descritor veio do PubMed: nomeia a procedência antes de mexer no resto
            f.write("UPDATE artigos SET mesh_origem='pubmed'\n"
                        " WHERE mesh_origem IS NULL AND cardinality(mesh_terms) > 0;\n\n")

        for i, a in enumerate(alvo, 1):
            texto = " ".join(str(a.get(c) or "") for c in
                             ("titulo", "contexto_tema", "resumo_markdown"))[:9000]
            termos, origem, det = ML.descritores(a.get("titulo") or "", texto,
                                                 a.get("revista") or "")
            marca = "✓" if termos else "✗"
            print(f"   {i:>3}/{len(alvo)} {marca} {str(a.get('titulo'))[:46]:<46} "
                  f"{len(termos)} · {det[:44]}", flush=True)
            if not termos:
                falhos.append((a.get("doc_id"), det))
                continue
            arr = "ARRAY[" + ",".join(f"'{esc(t)}'" for t in termos) + "]::text[]"
            f.write(f"UPDATE artigos SET mesh_terms={arr}, mesh_origem='{origem}'\n"
                    f" WHERE doc_id='{esc(a.get('doc_id'))}';\n")
            f.flush()               # grava a cada linha: se cair, não se perde o que foi pago
            feitos += 1

        f.write("\n-- conferência: rode e confira que `vazios` deu ZERO\n")
        f.write("SELECT count(*) FILTER (WHERE mesh_terms IS NULL "
                "OR cardinality(mesh_terms)=0) AS vazios,\n")
        f.write("       count(*) FILTER (WHERE mesh_origem='pubmed')   AS do_pubmed,\n")
        f.write("       count(*) FILTER (WHERE mesh_origem='mesh_llm') AS do_modelo,\n")
        f.write("       count(*) AS total\n  FROM artigos;\n")

    print(f"\n✔ {SAIDA}")
    print(f"  {feitos} linhas de UPDATE · {len(falhos)} não resolveram")
    for d, m in falhos[:8]:
        print(f"     ✗ {str(d)[:40]:<40} {m[:60]}")
    if falhos:
        print("\n  Os que não resolveram NÃO viram linha no SQL — ficam vazios e visíveis,")
        print("  em vez de subir com descritor inventado. Rode de novo para tentar outra vez.")
    print("\n  Abra o SQL Editor do Supabase, cole o arquivo e rode.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
