#!/usr/bin/env python3
"""TESTE DO ADMINISTRADOR (Chave 3) — a tela de curadoria provada SEM navegador.

01/Set/2026. O `teste_motor.py` prova o administrador por AST e por exec de funções
puras (`passa()`, `midia()`) — prova a LÓGICA, não a TELA. Esta suíte sobe o painel
de verdade com o AppTest do Streamlit (`streamlit.testing.v1`): o script inteiro
roda, os widgets existem como objetos, e dá para mexer neles e reexecutar — sem
navegador, sem Playwright, sem porta 8501.

O que ela NÃO é: prova de pixel. Layout, player de áudio tocando, botão de download
— isso só o navegador mostra (Chave 3 de verdade, ou Playwright). O que ela É: a
prova de que a tela abre, os filtros abrem como o dono decidiu, e os números que a
tela afirma batem com o banco DE VERDADE — medido por fora, não pela própria tela.

LEI 7 — o que esta prova exige para rodar: `.env` com SUPABASE_URL/chave e internet
(o painel LÊ a tabela `artigos` ao abrir). Sem isso ela reprova por credencial, não
por defeito — o relatório diz qual dos dois foi.

Uso:  .venv/bin/python -u src/teste_administrador.py
"""
import os
import re
import sys

falhas = []


def checa(nome, condicao, detalhe=""):
    if condicao:
        print(f"  ✅ {nome}")
    else:
        print(f"  ❌ {nome} — {detalhe}")
        falhas.append(nome)


AQUI = os.path.dirname(os.path.abspath(__file__))

# ── a sessão é UMA e compartilhada: subir o painel custa rede + varredura de
#    ~1.000 pacotes no disco; cada teste mexe nela em vez de abrir outra ──
_AT = None


def _painel():
    global _AT
    if _AT is None:
        from streamlit.testing.v1 import AppTest
        _AT = AppTest.from_file(os.path.join(AQUI, "administrador.py"),
                                default_timeout=180)
        _AT.run()
    return _AT


def _textos(at):
    """Todo texto que a tela afirmou, num saco só (markdown/caption/warning...)."""
    pedacos = []
    for tipo in ("markdown", "caption", "warning", "error", "info", "title",
                 "subheader", "header", "text"):
        for el in getattr(at, tipo, []):
            pedacos.append(str(getattr(el, "value", el)))
    return "\n".join(pedacos)


def _conta_banco_por_fora():
    """Contagem INDEPENDENTE da tabela `artigos` — a régua contra a qual a tela
    tem que bater. Mesmo desenho do header de contagem exata do PostgREST."""
    import requests
    from dotenv import load_dotenv
    load_dotenv(os.path.join(AQUI, "..", ".env"))
    url = os.environ.get("SUPABASE_URL", "")
    key = (os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
           or os.environ.get("SUPABASE_SERVICE_KEY")
           or os.environ.get("SUPABASE_KEY") or "")
    r = requests.get(f"{url}/rest/v1/artigos", params={"select": "doc_id"},
                     headers={"apikey": key, "Authorization": f"Bearer {key}",
                              "Prefer": "count=exact", "Range": "0-0"},
                     timeout=30)
    r.raise_for_status()
    return int(r.headers["Content-Range"].split("/")[1])


def teste_o_painel_abre_sem_excecao():
    at = _painel()
    checa("o painel roda do topo ao fim sem exceção", not at.exception,
          "; ".join(str(e.value) for e in at.exception) if at.exception else "")


def teste_a_tela_diz_o_banco_inteiro_e_nao_mente():
    """O caption afirma '{X} artigo(s) na tela · {Y} no banco'. O Y tem que ser o
    banco DE VERDADE — contado por fora, com o header de contagem exata. Foi para
    isso que o buscar() ganhou paginação em 01/Set: sem ela, no artigo 1001 o Y
    da tela viraria mentira silenciosa."""
    at = _painel()
    txt = _textos(at)
    m = re.search(r"(\d+)\**\s*no banco", txt)
    checa("a tela declara quantos há NO BANCO", m is not None,
          "o caption '{X} na tela · {Y} no banco' sumiu")
    if not m:
        return
    y_tela = int(m.group(1))
    y_banco = _conta_banco_por_fora()
    checa(f"o número da tela bate com o banco ({y_tela} = {y_banco})",
          y_tela == y_banco,
          f"tela diz {y_tela}, banco tem {y_banco} — alguém está cortando em silêncio")


def teste_o_slider_nac_abre_em_6_a_10():
    """Decisão do dono (22/Ago): abrir em 8–10 escondia 27 de 39. Abre em 6–10 —
    6 é a porta da LEI 10, não gosto."""
    at = _painel()
    sliders = list(at.sidebar.slider)
    checa("existe o slider NAC na sidebar", bool(sliders), "sumiu o filtro de nota")
    if sliders:
        checa("o slider abre em (6, 10)", tuple(sliders[0].value) == (6, 10),
              f"abriu em {sliders[0].value} — o padrão é decisão do dono, não default novo")


def teste_os_filtros_de_data_comecam_vazios():
    """Decisão do dono (padrão registrado no fonte): vazio mostra TUDO. Nada é
    escondido sem ele mandar."""
    at = _painel()
    datas = [t for t in at.sidebar.text_input
             if "AAAA-MM-DD" in (t.label or "")]
    checa("os dois campos de data existem", len(datas) == 2,
          f"achei {len(datas)} campo(s) com máscara AAAA-MM-DD")
    for t in datas:
        checa(f"  '{t.label}' começa vazio", (t.value or "") == "",
              f"começou com {t.value!r} — vazio-mostra-tudo é decisão do dono")


def teste_a_lista_de_aprovacao_acompanha_a_tela():
    """O selectbox 'Escolha o artigo' é a porta da aprovação. Ele tem que oferecer
    exatamente o que a tela diz que está na tela — nem mais, nem menos."""
    at = _painel()
    caixas = [s for s in at.selectbox if "artigo" in (s.label or "").lower()]
    checa("o selectbox de aprovação existe", bool(caixas), "sem ele não há curadoria")
    if not caixas:
        return
    m = re.search(r"(\d+)\**\s*artigo\(s\) na tela", _textos(at))
    if m:
        na_tela = int(m.group(1))
        n_opcoes = len(caixas[0].options)
        checa(f"a lista oferece o que a tela mostra ({n_opcoes} = {na_tela})",
              n_opcoes == na_tela,
              f"selectbox {n_opcoes} × tela {na_tela} — duas verdades na mesma página")


def teste_apertar_o_filtro_esconde_e_a_tela_AVISA():
    """A regra de 22/Ago: nada some em silêncio. Aperto o slider para (9,10) e a
    tela tem que (a) mostrar menos e (b) DIZER que escondeu."""
    at = _painel()
    antes = re.search(r"(\d+)\**\s*artigo\(s\) na tela", _textos(at))
    sliders = list(at.sidebar.slider)
    if not (antes and sliders):
        checa("pré-condição do teste de filtro", False, "sem caption ou sem slider")
        return
    sliders[0].set_value((9, 10)).run()
    txt2 = _textos(at)
    depois = re.search(r"(\d+)\**\s*artigo\(s\) na tela", txt2)
    checa("a tela reagiu ao slider", depois is not None, "caption sumiu após rerun")
    if depois:
        a, d = int(antes.group(1)), int(depois.group(1))
        checa(f"o filtro 9–10 mostra menos ({d} ≤ {a})", d <= a,
              "apertar o filtro AUMENTOU a tela?")
        if d < a:
            checa("a tela AVISA que escondeu", "escondido" in txt2,
                  "sumiu gente da tela e ninguém disse — é o defeito de 22/Ago de volta")
    # ⚠️ NÃO devolver o slider ao padrão aqui: o segundo rerun do AppTest tropeça no
    # session_state do checkbox com key (KeyError $$ID-…) — quirk do harness, não do
    # painel. Este teste MEXE na sessão compartilhada; por isso ele é o ÚLTIMO da
    # lista fixa. Teste novo que precise da tela limpa: abra outro AppTest.


if __name__ == "__main__":
    print("═" * 70)
    print("TESTE DO ADMINISTRADOR · AppTest (a tela de verdade, sem navegador)")
    print("═" * 70)

    # mesmo desenho do teste_motor: a lista fixa ordena o relatório, e a varredura
    # recolhe qualquer teste_* esquecido — aprovar por ausência é proibido.
    testes = [teste_o_painel_abre_sem_excecao,
              teste_a_tela_diz_o_banco_inteiro_e_nao_mente,
              teste_o_slider_nac_abre_em_6_a_10,
              teste_os_filtros_de_data_comecam_vazios,
              teste_a_lista_de_aprovacao_acompanha_a_tela,
              teste_apertar_o_filtro_esconde_e_a_tela_AVISA]
    _vistos = {f.__name__ for f in testes}
    _mod = sys.modules[__name__]
    for _nome in sorted(vars(_mod)):
        if _nome.startswith("teste_") and _nome not in _vistos and callable(getattr(_mod, _nome)):
            testes.append(getattr(_mod, _nome))

    for t in testes:
        print(f"\n▶ {t.__name__}")
        try:
            t()
        except Exception as e:
            print(f"  ❌ ESTOUROU: {type(e).__name__}: {e}")
            falhas.append(t.__name__)

    print("\n" + "═" * 70)
    if falhas:
        print(f"REPROVADO · {len(falhas)} falha(s): {', '.join(falhas)}")
        sys.exit(1)
    print("APROVADO · a tela da Chave 3 abre, filtra como o dono decidiu, e os "
          "números que ela afirma batem com o banco medido por fora.")
    sys.exit(0)
