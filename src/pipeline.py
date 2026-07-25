"""
pipeline.py — a ESTEIRA do coração (orquestrador fino).
PDF → analise (fatos + keywords + aplicabilidade + mcid) → notas (nota) → REGISTRO CANÔNICO.
Formato do registro (desenho do Dr. Eduardo): YAML dos DADOS CANÔNICOS em cima, a ANÁLISE embaixo.
É a "linha do banco" — a verdade forjada UMA vez, da qual tudo deriva (Plantonista, sábado, áudio).
Uso: python pipeline.py <ARTIGO.pdf>  → grava <nome>_CANONICO.md
"""
import os, sys, json, re, fitz
import analise as A, notas_prototipo as N

_HERE = os.path.dirname(os.path.abspath(__file__))
_DOI = re.compile(r"10\.\d{4,9}/[-._;()/:A-Za-z0-9]+")

_TIPO = {"rct": "artigo_original", "coorte": "artigo_original", "registro": "artigo_original",
         "transversal": "artigo_original", "caso_controle": "artigo_original",
         "observacional_ajustado": "artigo_original", "meta": "revisao_sistematica_meta_analise"}


def yaml_list(xs):
    return "[" + ", ".join(f'"{x}"' for x in xs) + "]"


def registro_canonico(pdf):
    base = os.path.splitext(os.path.basename(pdf))[0]
    cache = os.path.join(_HERE, base + "_fatos.json")
    fatos = json.load(open(cache)) if (os.path.exists(cache) and "keywords" in json.load(open(cache))) \
        else A.extrair_fatos(pdf)
    json.dump(fatos, open(cache, "w"), ensure_ascii=False)
    r = N.score(fatos)
    texto = "".join(p.get_text() for p in fitz.open(pdf))
    m = _DOI.search(texto); doi = re.sub(r"/\d{6,}$", "", m.group(0).rstrip(".")) if m else "n/a"

    y = []
    y.append("---")
    y.append("# REGISTRO CANÔNICO — CardioDaily · dados e fatos, sem firulas")
    y.append("identidade:")
    y.append(f'  titulo: "{fatos.get("titulo","")}"')
    y.append(f'  revista: "{fatos.get("revista","")}"')
    y.append(f'  ano: "{fatos.get("ano","")}"')
    y.append(f'  doi: "{doi}"')
    y.append(f'  tipo: "{_TIPO.get(fatos.get("desenho"), "artigo_original")}"')
    y.append(f'  pergunta: "{fatos.get("pergunta","")}"')
    y.append(f'  desenho: "{fatos.get("desenho","")}"')
    y.append("veredito:   # do MOTOR DE RIGOR (código), não do LLM")
    y.append(f'  nota_aplicabilidade_clinica: {r["aplic"]}')
    y.append(f'  nota_trabalho_estatistico: {r["trabalho"]}')
    y.append(f'  muda_conduta: "{r["muda_conduta"]}"')
    y.append(f'  teto_desenho: {r["teto_desenho"]}')
    y.append(f'  teto_validade_externa: {r["teto_externa"]}')
    y.append(f"  delatores: {yaml_list(r['flags']) if r['flags'] else '[]'}")
    # N-SID — a 2ª dimensão da nota: o filtro de tradução clínica (MCID/MID; ARD/NNT/GRADE p/ desfecho duro)
    rc = fatos.get("relevancia_clinica") or {}
    y.append("relevancia_clinica:   # N-SID — relevância clínica do efeito (não confundir com p<0,05)")
    if isinstance(rc, dict) and rc:
        for k in ("desfecho_primario", "tipo_desfecho", "efeito_observado", "mcid_reportado",
                  "mcid_valor", "mcid_fonte_metodo", "para_desfecho_duro", "efeito_excede_limiar",
                  "ic_sustenta_relevancia", "classificacao", "frase_chave"):
            v = rc.get(k, "")
            if isinstance(v, bool) or v is None:
                y.append(f"  {k}: {json.dumps(v)}")
            else:
                y.append(f'  {k}: "{str(v).replace(chr(34), "")}"')
    else:                                    # compat: extração antiga (mcid_nota como string)
        y.append('  classificacao: "n/a"')
        y.append(f'  frase_chave: "{str(fatos.get("mcid_nota", "")).replace(chr(34), "")}"')
    y.append("reaproveitamento:   # keywords + aplicabilidade (a relevância virou seção própria)")
    y.append(f"  keywords: {yaml_list(fatos.get('keywords', []))}")
    y.append(f'  aplicabilidade: "{fatos.get("aplicabilidade","").replace(chr(34), "")}"')
    y.append(f'achados: "{fatos.get("achados_principais","").replace(chr(34), "")}"')
    y.append("derivados:")
    y.append(f'  texto_analise: "{base}_analise.md"')
    y.append(f'  roteiro_audio: "{base}_roteiro_audio.txt"')
    y.append("---\n")

    # a ANÁLISE embaixo (texto do redator, se já gerado)
    an = os.path.join(_HERE, base + "_analise.md")
    corpo = open(an).read() if os.path.exists(an) else f"# {fatos.get('titulo','')}\n\n_(análise do redator — gerar com redator.py)_"
    out = os.path.join(_HERE, base + "_CANONICO.md")
    open(out, "w").write("\n".join(y) + corpo)
    return out


if __name__ == "__main__":
    print("REGISTRO CANÔNICO salvo em:", registro_canonico(sys.argv[1]))
