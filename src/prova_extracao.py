"""
prova_extracao.py — A PROVA DA ETAPA QUE DECIDE TUDO (03/Ago/2026).

═══ POR QUE EXISTE ═══

Em 01/Ago o Dr. Eduardo mediu o REDATOR com rigor: 5 documentos, 3–4 modelos, contagem de tabelas,
de lacunas admitidas, de tokens e de tempo. O gpt-5.6-terra ganhou e virou a cadeia PERICIA.

Mas o redator é a etapa que ESCREVE. A que JULGA nunca foi medida.

A corrente é esta:

    PDF ──[extração]──> FATOS ──[motor determinístico]──> NOTA ──> publica? visual? áudio?
                                                            └────> entra DENTRO do prompt do redator

A NOTA sai dos FATOS. Os FATOS saem de UMA chamada de LLM que nunca foi comparada com ninguém.
Se a extração lê errado, a nota erra — e aí:
  • artigo bom leva 5 e é descartado sem ninguém ver (na última rodada: 122 analisados, 75 recusados);
  • artigo fraco leva 8, ganha áudio e visual, e vai pro site;
  • e o redator recebe a nota errada no prompt — medido: trocar 6 por 9 muda 86% dos parágrafos.

O motor é código, é determinístico e está APROVADO na bateria. Ele não erra. Ele obedece aos fatos.
Quem pode estar errando é quem entrega os fatos — e é isso que este programa mede.

═══ COMO MEDE ═══

Por artigo, para cada modelo:

    PDF → modelo extrai FATOS → MESMO motor determinístico → Nota / Rigor

O motor vira a RÉGUA COMUM. Não se compara JSON campo a campo (chato e não responde nada); compara-se
a DECISÃO que cada extração produz. Se os três modelos dão a mesma nota, a extração é robusta e o
problema está noutro lugar — e a gente para de gastar aqui. Se dão 5, 7 e 8, então a nota do
CardioDaily depende de qual servidor atendeu naquele segundo.

Depois, e SÓ depois, ele mostra os campos que DIVERGIRAM — porque campo em que os três concordam não
merece o tempo do Dr. Eduardo.

LUTA JUSTA (03/Ago): até hoje o `gerar_json` só fazia saída estruturada para a Anthropic; os outros
caíam para "peça JSON em prosa e torça". Comparar assim seria luta arranjada — o sonnet ganharia por
construção. Foi implementado function calling (OpenAI) e responseSchema (Google) antes desta medição.
A coluna `modo` mostra qual caminho cada modelo usou. Se algum cair para modo texto, está na tela.

NÃO MOVE ARQUIVO · NÃO PUBLICA · NÃO FALA COM O SUPABASE. Só lê PDF, chama LLM e escreve relatório.

Uso:
    python src/prova_extracao.py <pdf1> <pdf2> ...
    python src/prova_extracao.py <pasta>                        (todos os PDFs da pasta)
    python src/prova_extracao.py <pdf> --tipo=diretriz          (PDF fora das pastas do classificador)
    python src/prova_extracao.py <pasta> --modelos=claude-sonnet-5,gpt-5.6-terra
"""
import os
import sys
import json
import time
import glob
import argparse
import datetime

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

MODELOS_PADRAO = ["claude-sonnet-5", "gpt-5.6-terra", "gemini-3.1-pro-preview"]

# US$ por 1M de tokens (entrada, saída) — para a coluna de custo. Aproximado e declarado como tal.
_PRECO = {
    "claude-sonnet-5":        (3.00, 15.00),
    "claude-opus-5":          (15.00, 75.00),
    "claude-haiku-4-5-20251001": (1.00, 5.00),
    "gpt-5.6-terra":          (1.25, 10.00),
    "gpt-5.6-sol":            (1.25, 10.00),
    "gpt-5.6-luna":           (0.20, 1.20),
    "gemini-3.1-pro-preview": (1.25, 10.00),
}

TIPOS = ("original", "meta", "diretriz", "revisao_narrativa")


def _custo(modelo, ent, sai):
    p = _PRECO.get(modelo)
    if not p or ent is None or sai is None:
        return None
    return (ent * p[0] + sai * p[1]) / 1_000_000


def _achatar(d, prefixo=""):
    """{'agree': {'busca': True}} → {'agree.busca': True} — para comparar campo a campo sem aninhamento."""
    out = {}
    for k, v in (d or {}).items():
        chave = f"{prefixo}{k}"
        if isinstance(v, dict):
            out.update(_achatar(v, chave + "."))
        else:
            out[chave] = v
    return out


def medir_um(pdf, tipo, modelos):
    """Roda a extração de UM artigo com cada modelo e pontua cada resultado no MESMO motor."""
    import analise as A
    import notas_prototipo as N
    import llm_client

    linhas = []
    for mod in modelos:
        llm_client._ULTIMO_MODO[0] = None
        llm_client._ULTIMO_USO.clear()
        llm_client.contexto_uso(etapa="prova_extracao", artigo=os.path.basename(pdf))
        t0 = time.time()
        try:
            fatos = A.extrair_fatos(pdf, tipo=tipo, cadeia=[mod])   # UM modelo, sem fallback: é uma prova
            erro = ""
        except Exception as e:
            linhas.append({"modelo": mod, "erro": f"{type(e).__name__}: {str(e)[:90]}",
                           "aplic": None, "rigor": None, "motor": "—", "modo": "FALHOU",
                           "seg": round(time.time() - t0, 1), "fatos": {}})
            print(f"      ❌ {mod:24} {type(e).__name__}: {str(e)[:60]}")
            continue
        seg = round(time.time() - t0, 1)

        fatos["tipo_documento"] = tipo          # LEI 8: a pasta manda, igual à produção
        r = N.score(fatos)
        uso = dict(llm_client._ULTIMO_USO)
        ent, sai = uso.get("input"), uso.get("output")
        linhas.append({
            "modelo": mod, "erro": "",
            "aplic": r["aplic"], "rigor": r["trabalho"], "motor": r["motor"],
            "muda_conduta": r.get("muda_conduta"), "rota": r.get("rota"),
            "modo": llm_client._ULTIMO_MODO[0] or "texto",
            "seg": seg, "entrada": ent, "saida": sai, "custo": _custo(mod, ent, sai),
            "stop": uso.get("stop_reason"), "fatos": fatos,
        })
        c = _custo(mod, ent, sai)
        print(f"      ✔ {mod:24} Nota {str(r['aplic']):>4}/10 · Rigor {str(r['trabalho']):>4}/10 · "
              f"{r['motor']:8} · {linhas[-1]['modo']:16} {seg:>6.1f}s"
              + (f" · US$ {c:.3f}" if c else ""))
    return linhas


def _divergencias(linhas):
    """Só os campos em que os modelos NÃO concordaram. Campo unânime não toma o tempo do Dr. Eduardo."""
    vivos = [l for l in linhas if not l["erro"]]
    if len(vivos) < 2:
        return {}
    planos = {l["modelo"]: _achatar(l["fatos"]) for l in vivos}
    chaves = set()
    for p in planos.values():
        chaves |= set(p)
    div = {}
    for k in sorted(chaves):
        if k == "tipo_documento":
            continue
        vals = {m: p.get(k, "<ausente>") for m, p in planos.items()}
        if len({json.dumps(v, sort_keys=True, ensure_ascii=False) for v in vals.values()}) > 1:
            div[k] = vals
    return div


def main():
    ap = argparse.ArgumentParser(description="Mede a EXTRAÇÃO: mesma régua (o motor), extratores diferentes")
    ap.add_argument("alvos", nargs="+", help="PDFs ou uma pasta")
    ap.add_argument("--tipo", choices=TIPOS, default=None,
                    help="se o PDF estiver FORA das pastas do classificador (senão a pasta manda)")
    ap.add_argument("--modelos", default=",".join(MODELOS_PADRAO))
    a = ap.parse_args()

    from analisador import tipo_do_documento, _TIPO_POR_PASTA
    modelos = [m.strip() for m in a.modelos.split(",") if m.strip()]

    pdfs = []
    for alvo in a.alvos:
        alvo = os.path.expanduser(alvo)
        if os.path.isdir(alvo):
            pdfs += sorted(f for f in glob.glob(os.path.join(alvo, "**", "*.pdf"), recursive=True)
                           if not os.path.basename(f).startswith("._"))
        elif alvo.lower().endswith(".pdf"):
            pdfs.append(alvo)
    pdfs = [p for p in pdfs if os.path.isfile(p)]
    if not pdfs:
        print("Nenhum PDF encontrado."); return 1

    # o tipo, com a mesma regra da produção (LEI 8) — e sem adivinhar quando não dá
    tarefas = []
    for p in pdfs:
        t = a.tipo or (tipo_do_documento(p)
                       if os.path.basename(os.path.dirname(p)) in _TIPO_POR_PASTA else None)
        if t is None:
            print(f"⛔ {os.path.basename(p)[:60]}\n   está FORA das pastas do classificador e você não "
                  f"passou --tipo. Não vou adivinhar (LEI 8).")
            return 1
        tarefas.append((p, t))

    print(f"\n{'='*80}")
    print(f" PROVA DA EXTRAÇÃO · {len(tarefas)} artigo(s) × {len(modelos)} modelo(s) = "
          f"{len(tarefas)*len(modelos)} chamadas")
    print(f" A régua é a MESMA para todos: o motor determinístico (notas_prototipo).")
    print(f" Nada é movido, nada é publicado.")
    print(f"{'='*80}")

    resultado = []
    for i, (pdf, tipo) in enumerate(tarefas, 1):
        print(f"\n[{i}/{len(tarefas)}] {os.path.basename(pdf)[:66]}")
        print(f"      tipo: {tipo}")
        linhas = medir_um(pdf, tipo, modelos)
        notas = {l["aplic"] for l in linhas if not l["erro"]}
        if len(notas) > 1:
            print(f"      ⚠️  AS NOTAS DIVERGEM: {sorted(n for n in notas if n is not None)} — "
                  f"a decisão deste artigo depende de qual modelo atendeu")
        elif notas:
            print(f"      ✅ os modelos concordam na nota ({notas.pop()}/10)")
        resultado.append({"pdf": pdf, "tipo": tipo, "linhas": linhas,
                          "divergencias": _divergencias(linhas)})

    saida = os.path.abspath(os.path.join(_HERE, "..", "outputs", "PROVA"))
    os.makedirs(saida, exist_ok=True)
    carimbo = datetime.datetime.now().strftime("%Y%m%d-%H%M")
    md = os.path.join(saida, f"prova_extracao_{carimbo}.md")
    _escrever_relatorio(md, resultado, modelos)

    # ── o placar ──
    div = sum(1 for r in resultado if len({l["aplic"] for l in r["linhas"] if not l["erro"]}) > 1)
    custo = sum(l.get("custo") or 0 for r in resultado for l in r["linhas"])
    print(f"\n{'='*80}")
    print(f" PLACAR · {len(resultado)} artigo(s)")
    print(f"{'='*80}")
    print(f"   artigos em que a NOTA divergiu entre modelos: {div} de {len(resultado)}")
    print(f"   custo total desta prova: US$ {custo:.2f}")
    print(f"\n📋 relatório para você marcar quem leu certo:\n   {md}\n")
    return 0


def _escrever_relatorio(caminho, resultado, modelos):
    L = []
    L.append("# Prova da EXTRAÇÃO — CardioDaily\n")
    L.append(f"_{datetime.datetime.now():%d/%m/%Y %H:%M}_\n")
    L.append("A régua é a mesma para todos: o **motor determinístico**. O que muda é só quem leu o PDF.\n")
    L.append("Se as notas batem, a extração é robusta. Se divergem, a decisão do CardioDaily "
             "depende de qual modelo atendeu.\n")

    for r in resultado:
        L.append(f"\n---\n\n## {os.path.basename(r['pdf'])}\n")
        L.append(f"**tipo:** `{r['tipo']}`\n")
        L.append("\n| modelo | Nota | Rigor | motor | muda conduta | modo | tempo | entrada | saída | US$ |")
        L.append("|---|---|---|---|---|---|---|---|---|---|")
        for l in r["linhas"]:
            if l["erro"]:
                L.append(f"| `{l['modelo']}` | — | — | — | — | **FALHOU** | {l['seg']}s | | | "
                         f"| {l['erro']} |")
                continue
            c = f"{l['custo']:.3f}" if l.get("custo") else ""
            L.append(f"| `{l['modelo']}` | **{l['aplic']}/10** | {l['rigor']}/10 | {l['motor']} | "
                     f"{l.get('muda_conduta','')} | {l['modo']} | {l['seg']}s | "
                     f"{l.get('entrada','')} | {l.get('saida','')} | {c} |")

        notas = {l["aplic"] for l in r["linhas"] if not l["erro"]}
        if len(notas) > 1:
            L.append(f"\n> ⚠️ **AS NOTAS DIVERGEM.** Este artigo publicaria ou não dependendo do "
                     f"modelo que o leu.\n")
        elif notas:
            L.append(f"\n> ✅ Os modelos concordam na nota.\n")

        div = r["divergencias"]
        if not div:
            L.append("\nNenhum campo divergiu — os modelos leram o artigo do mesmo jeito.\n")
        else:
            L.append(f"\n### Campos em que discordaram ({len(div)}) — marque quem leu certo\n")
            L.append("| campo | " + " | ".join(f"`{m}`" for m in modelos) + " | quem acertou? |")
            L.append("|---" * (len(modelos) + 2) + "|")
            for k, vals in div.items():
                cel = " | ".join(f"`{json.dumps(vals.get(m, '—'), ensure_ascii=False)}`" for m in modelos)
                L.append(f"| **{k}** | {cel} |  |")
            L.append("")

    L.append("\n---\n\n## Como ler isto\n")
    L.append("- **Nota divergente** é o achado que importa: significa que publicar ou descartar o "
             "artigo depende de sorte.\n")
    L.append("- **modo** diz como o JSON foi obtido. `tool_use` / `function_calling` / `responseSchema` "
             "são saída estruturada de verdade (a API obriga o formato). `texto` ou "
             "`json_mode(sem schema)` é caminho degradado — se aparecer, o modelo lutou em desvantagem "
             "e a comparação com ele não é justa.\n")
    L.append("- **Campos divergentes**: preencha a última coluna. É o único gabarito possível — "
             "quem sabe qual fato está no PDF é você.\n")
    open(caminho, "w", encoding="utf-8").write("\n".join(L))


if __name__ == "__main__":
    sys.exit(main())
