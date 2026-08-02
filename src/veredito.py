"""
veredito.py — O VEREDITO REAL DE UM PDF, para colar no painel (02/Ago/2026).

POR QUE EXISTE
--------------
O Dr. Eduardo está INVENTANDO as duas notas para conseguir rodar o comparativo — porque a trava
do veredito (criada em 01/Ago) impede rodar com o campo vazio, e ele não tinha como obter a nota
verdadeira fora da corrente.

Isso tem um risco que não dá para ignorar: **a nota ANCORA o texto**. Um veredito "8/10" faz o
modelo escrever como quem já sabe que o estudo é bom. A perícia inteira pode ficar mais branda —
ou mais dura — por causa de um número que ninguém calculou.

Este programa fecha esse buraco: dá o veredito DE VERDADE, do mesmo motor que roda em produção.
  PDF → extrai os FATOS (1 chamada de LLM, ~US$ 0,02) → motor determinístico → linha do veredito.

Uso:
  python src/veredito.py <ARTIGO.pdf>              # imprime a linha p/ colar
  python src/veredito.py <ARTIGO.pdf> --fatos      # mostra também os fatos extraídos
  python src/veredito.py <PASTA> --lote            # todos os PDFs da pasta, em CSV
"""
import os
import sys
import json
import glob

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)


def veredito_de(pdf, tipo=None):
    """Devolve (linha_do_veredito, fatos, resultado_do_motor). Mesma corrente da produção.

    `tipo` — LEI 8: o tipo decide TUDO (extrator, motor, prompt). Em produção quem decide é o
    CLASSIFICADOR, e a pasta é o registro dessa decisão. Aqui, num PDF solto arrastado de qualquer
    lugar do disco, NÃO EXISTE decisão de classificador para obedecer — então quem decide é o
    Dr. Eduardo, explicitamente. O programa NÃO adivinha: adivinhar criaria uma terceira fonte de
    verdade, que é exatamente o que a LEI 8 proíbe.
    (02/Ago: uma diretriz da SBC arrastada da pasta Downloads caiu no extrator de artigo original e
     saiu 'SEM NOTA — desenho nao_classificavel'. O motor não errou; ele nunca chegou a rodar.)"""
    import analise as A
    import notas_prototipo as N
    fatos = A.extrair_fatos(pdf, tipo=tipo)
    r = N.score(fatos)
    # UMA fonte só: é EXATAMENTE o bloco que o analisador injeta no contexto do redator em produção.
    # Se a Chave 9 montasse a própria linha, ela mostraria uma coisa e a produção usaria outra.
    return N.veredito_completo(r), fatos, r


def _um(pdf, mostrar_fatos=False, tipo=None):
    print(f"\n{os.path.basename(pdf)[:70]}")
    print("─" * 72)
    linha, fatos, r = veredito_de(pdf, tipo=tipo)
    diretriz, revisao = r.get("motor") == "DIRETRIZ", r.get("motor") == "REVISAO"
    if mostrar_fatos:
        print("FATOS (o que o extrator leu):")
        if revisao:
            q = fatos.get("qualidade_revisao") or {}
            for k in ("titulo", "revista", "ano"):
                print(f"   {k:30} {fatos.get(k)}")
            print("   ── rigor ──")
            for k in ("afirmacoes_sem_citacao", "atribui_nivel_evidencia",
                      "apresenta_contra_evidencia", "tom_promocional", "metodo_busca_declarado",
                      "n_referencias", "ano_referencia_mais_recente", "conflitos_declarados",
                      "financiamento_industria", "limitacoes_reconhecidas"):
                print(f"   {k:30} {q.get(k)}")
            print("   ── utilidade prática ──")
            for k in ("n_condutas_acionaveis", "traz_valores_corte_ou_doses",
                      "traz_magnitude_efeito", "traz_custo_acesso", "traz_seguranca",
                      "traz_em_quem_nao_usar", "tem_tabela_comparativa"):
                print(f"   {k:30} {q.get(k)}")
        elif diretriz:
            g, ag = fatos.get("recomendacoes") or {}, fatos.get("agree") or {}
            for k in ("titulo", "revista", "ano", "sociedade", "tipo_documento_norm",
                      "aplicavel_brasil", "idade_anos"):
                print(f"   {k:26} {fatos.get(k)}")
            print(f"   {'sistema_graduacao':26} {g.get('sistema_graduacao')}")
            print(f"   {'classe I/IIa/IIb/III':26} {g.get('n_classe_I')}/{g.get('n_classe_IIa')}"
                  f"/{g.get('n_classe_IIb')}/{g.get('n_classe_III')}")
            print(f"   {'nível A/B/C':26} {g.get('n_nivel_A')}/{g.get('n_nivel_B')}/{g.get('n_nivel_C')}")
            print(f"   {'Classe I em nível C':26} {g.get('n_classe_I_nivel_C')}")
            for k in ("busca_sistematica_declarada", "vinculo_recomendacao_evidencia",
                      "revisao_externa", "conflitos_declarados", "politica_gestao_conflitos",
                      "plano_atualizacao"):
                print(f"   {k:26} {ag.get(k)}")
        else:
            for k in ("titulo", "revista", "ano", "pergunta", "desenho", "retrospectivo",
                      "open_label", "poder_ok", "desfecho_duro", "extrapolavel", "eventos_min_grupo"):
                print(f"   {k:26} {fatos.get(k)}")
            rc = (fatos.get("relevancia_clinica") or {}).get("classificacao")
            print(f"   {'relevancia_clinica':26} {rc}")
        print(f"   {'falhas_fatais':26} {r.get('falhas_fatais') or '—'}")
        print()
    print("VEREDITO — cole ISTO INTEIRO no campo do painel "
          "(é o mesmo bloco que a produção entrega ao redator):\n")
    print(linha + "\n")
    # LEI 8 — o tipo é UM só: o motor e o prompt leem a MESMA decisão (a pasta do classificador).
    # Antes daqui saía "desenho=nao_classificavel → usaria o prompt ORIGINAL": duas fontes de verdade.
    from analisador import tipo_do_documento, _PROMPT_POR_TIPO_DOC
    t = tipo or tipo_do_documento(pdf)
    origem = "você informou" if tipo else \
             ("pasta do classificador" if os.path.basename(os.path.dirname(pdf)) in
              __import__("analisador")._TIPO_POR_PASTA else "⚠️ PDF fora das pastas — assumido")
    print(f"   (tipo={t} [{origem}] → motor {r.get('motor')} · prompt {_PROMPT_POR_TIPO_DOC.get(t, '?')})")
    return linha


TIPOS_VALIDOS = ("original", "meta", "diretriz", "revisao_narrativa")


def main(args):
    if not args:
        print(__doc__); return 1
    alvo = os.path.expanduser(args[0])
    lote = "--lote" in args
    tipo = next((a.split("=", 1)[1] for a in args if a.startswith("--tipo=")), None)
    if tipo and tipo not in TIPOS_VALIDOS:
        print(f"Tipo inválido: {tipo}. Use um de: {', '.join(TIPOS_VALIDOS)}"); return 1

    if lote or os.path.isdir(alvo):
        pdfs = sorted(f for f in glob.glob(os.path.join(alvo, "*.pdf"))
                      if not os.path.basename(f).startswith("._"))
        if not pdfs:
            print(f"Nenhum PDF em {alvo}"); return 1
        import csv
        saida = os.path.join(os.path.dirname(_HERE), "outputs", "PROVA_PROMPTS", "vereditos.csv")
        os.makedirs(os.path.dirname(saida), exist_ok=True)
        linhas = []
        for p in pdfs:
            try:
                linha, fatos, _ = veredito_de(p, tipo=tipo)
                linhas.append({"arquivo": os.path.basename(p), "desenho": fatos.get("desenho"),
                               "pergunta": fatos.get("pergunta"), "veredito": linha})
                print(f"  ✅ {os.path.basename(p)[:46]:48} {linha[:56]}")
            except Exception as e:
                linhas.append({"arquivo": os.path.basename(p), "desenho": "", "pergunta": "",
                               "veredito": f"ERRO: {type(e).__name__}: {e}"})
                print(f"  ❌ {os.path.basename(p)[:46]:48} {type(e).__name__}: {str(e)[:44]}")
        with open(saida, "w", newline="", encoding="utf-8-sig") as fh:
            w = csv.DictWriter(fh, fieldnames=list(linhas[0].keys()))
            w.writeheader(); w.writerows(linhas)
        print(f"\n→ {saida}")
        return 0

    if not os.path.isfile(alvo):
        print(f"Não achei: {alvo}"); return 1
    _um(alvo, "--fatos" in args, tipo=tipo)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
