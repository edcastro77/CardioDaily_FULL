"""
checar_modelos.py — O EXAME DE SANIDADE DAS CADEIAS (04/Ago/2026).

═══ POR QUE EXISTE ═══

Na primeira prova da extração (04/Ago, 01h48) o `gemini-3.1-pro-preview` falhou nos DOIS caminhos —
saída estruturada e texto. E o `gpt-5.6-terra` falhou na saída estruturada e caiu para texto.

Isso não é detalhe de laboratório. O gemini é o ÚLTIMO FALLBACK de praticamente toda cadeia do
`modelos.py`. Se ele não responde na conta do Dr. Eduardo, então:

  • a "LEI DA EQUIVALÊNCIA" (Claude → GPT → Gemini) tem só DOIS degraus de verdade, não três;
  • e ninguém sabia disso, porque o fallback só é exercitado quando o primário cai — ou seja,
    justamente na hora ruim, no meio de um lote de 431 artigos, às 3 da manhã.

Fallback que nunca foi testado não é fallback: é uma linha de código que faz o dono se sentir seguro.

═══ O QUE FAZ ═══

Bate na porta de CADA modelo declarado no `modelos.py` com um prompt minúsculo, e diz:

  TEXTO   — o modelo responde em modo texto?           (é o piso de todo fallback)
  JSON    — o modelo aceita SAÍDA ESTRUTURADA?         (tool use / function calling / responseSchema)

Custa centavos: são ~20 tokens de entrada e ~20 de saída por modelo. Não lê PDF, não move arquivo,
não publica, não fala com o Supabase.

Uso:
    python src/checar_modelos.py             (todos os modelos de todas as cadeias)
    python src/checar_modelos.py --so=texto  (pula o teste de JSON)
"""
import os
import sys
import time
import argparse

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

# schema mínimo, mas com o `["boolean","null"]` que os FATOS usam de verdade — se um provedor
# engasgar com o tipo nulo, é AQUI que tem de aparecer, não no meio de um lote de 431 artigos.
SCHEMA_TESTE = {
    "type": "object",
    "properties": {
        "ok": {"type": "boolean"},
        "reportado": {"type": ["boolean", "null"]},
        "n": {"type": ["integer", "null"]},
    },
    "required": ["ok"],
}


def _cadeias():
    import modelos as M
    saida = {}
    for nome in dir(M):
        v = getattr(M, nome)
        if nome.isupper() and isinstance(v, list) and v and all(isinstance(x, str) for x in v):
            saida[nome] = v
    return saida


def main():
    ap = argparse.ArgumentParser(description="Bate na porta de cada modelo das cadeias do modelos.py")
    ap.add_argument("--so", choices=("texto", "json"), default=None)
    # 04/Ago: o Dr. Eduardo renovou a chave do Gemini DEPOIS de o tirarmos das cadeias. Testar um
    # modelo que NÃO está em cadeia nenhuma dá o dado sem comprometer produção — decide-se com
    # número, não com a lembrança do 429 de ontem.
    ap.add_argument("--extras", default="gemini-3.1-pro-preview,gemini-3.6-flash",
                    help="modelos FORA das cadeias, só para ver se respondem (vazio p/ pular)")
    a = ap.parse_args()

    # o .env, pelo mesmo caminho que a produção usa
    try:
        import publicador as P
        P._carregar_env()
    except Exception:
        pass

    import modelos as M
    import llm_client as L

    cadeias = _cadeias()
    modelos, onde = [], {}
    for e in [x.strip() for x in (a.extras or "").split(",") if x.strip()]:
        modelos.append(e); onde[e] = ["(fora das cadeias)"]
    for nome, lista in sorted(cadeias.items()):
        for i, m in enumerate(lista):
            if m not in onde:
                modelos.append(m)
                onde[m] = []
            onde[m].append(f"{nome}[{i}]" + ("*" if i == 0 else ""))

    print(f"\n{'='*86}")
    print(f" EXAME DAS CADEIAS · {len(modelos)} modelo(s) distinto(s) em {len(cadeias)} cadeia(s)")
    print(f" (* = é o PRIMÁRIO daquela cadeia)")
    print(f" Custa centavos: ~20 tokens por teste. Não lê PDF, não publica, não move nada.")
    print(f"{'='*86}\n")
    print(f" {'modelo':26} {'TEXTO':>22}  {'JSON (estruturado)':>26}")
    print(" " + "─"*84)

    problemas = []
    for m in modelos:
        # ── TEXTO ──
        t_txt, e_txt = "—", ""
        if a.so != "json":
            t0 = time.time()
            try:
                L.gerar([m], "Responda apenas: ok", max_tokens=20, temperatura=0)
                t_txt = f"✅ {time.time()-t0:>4.1f}s"
            except Exception as e:
                t_txt = "❌"
                e_txt = f"{type(e).__name__}: {str(e)[:400]}"

        # ── JSON ESTRUTURADO ──
        t_js, e_js = "—", ""
        if a.so != "texto":
            t0 = time.time()
            try:
                L._ULTIMO_MODO[0] = None
                L.gerar_json([m], "Devolva ok=true, reportado=null, n=7.", SCHEMA_TESTE,
                             max_tokens=200, nome="teste")
                t_js = f"✅ {L._ULTIMO_MODO[0] or '?'} {time.time()-t0:.1f}s"
            except Exception as e:
                t_js = "❌"
                e_js = f"{type(e).__name__}: {str(e)[:400]}"

        print(f" {m:26} {t_txt:>22}  {t_js:>26}")
        print(f" {'':26} {','.join(onde[m])}")
        if e_txt or e_js:
            problemas.append((m, onde[m], e_txt, e_js))

    if problemas:
        print(f"\n{'='*86}")
        print(" O QUE FALHOU, E POR QUÊ (mensagem completa)")
        print(f"{'='*86}")
        for m, ond, e_txt, e_js in problemas:
            print(f"\n ▸ {m}   ({', '.join(ond)})")
            if e_txt:
                print(f"     TEXTO ❌  {e_txt}")
            if e_js:
                print(f"     JSON  ❌  {e_js}")

    # ── o veredito que importa: alguma cadeia ficou sem fallback de verdade? ──
    mortos = {m for m, _, e_txt, _ in problemas if e_txt}
    print(f"\n{'='*86}")
    print(" SAÚDE DAS CADEIAS (a LEI DA EQUIVALÊNCIA, medida em vez de suposta)")
    print(f"{'='*86}")
    for nome, lista in sorted(cadeias.items()):
        vivos = [m for m in lista if m not in mortos]
        marca = "✅" if len(vivos) >= 2 else ("⚠️ " if len(vivos) == 1 else "🔴")
        obs = ("" if len(vivos) >= 2 else
               "  ← SEM FALLBACK: se o primário cair, a corrente PARA" if len(vivos) == 1 else
               "  ← NENHUM MODELO RESPONDE")
        print(f" {marca} {nome:18} {len(vivos)} de {len(lista)} respondem{obs}")
        for m in lista:
            print(f"      {'✓' if m not in mortos else '✗'} {m}")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
