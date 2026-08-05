"""
backfill_datas_crossref_2026.py — CONSERTA a data_publicacao pela FONTE REAL (CrossRef, pelo DOI).

Por que existe (27/Jul/2026): a extração guardava só o ANO em muitos artigos (virava AAAA-01-01), e o
painel chegou a FABRICAR data (usar a data de análise). Fabricar data é mentira. A data real está no
CrossRef, indexada pelo DOI. Este script busca a data verdadeira e corrige SÓ a coluna data_publicacao.

Alvo: artigos com data_publicacao = AAAA-01-01 (só-ano) E com DOI. Só atualiza se o CrossRef tiver
uma data MAIS PRECISA (com mês). Nunca inventa: se o CrossRef também só tem o ano, deixa como está.
"""
import os, sys, time, requests
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
U = os.getenv("SUPABASE_URL", "").rstrip("/")
K = os.getenv("SUPABASE_SERVICE_KEY")
H = {"apikey": K, "Authorization": f"Bearer {K}"}
UA = {"User-Agent": "CardioDaily/1.0 (mailto:edcastro77@gmail.com)"}


def crossref_data(doi):
    """Data mais precisa que o CrossRef tiver (published-online > published > issued). None se só-ano."""
    try:
        m = requests.get(f"https://api.crossref.org/works/{doi}", headers=UA, timeout=25).json()["message"]
    except Exception:
        return None
    for campo in ("published-online", "published", "issued", "published-print"):
        parts = (m.get(campo) or {}).get("date-parts", [[None]])[0]
        if parts and len(parts) >= 2 and parts[0]:                 # precisa ter pelo menos ANO-MÊS
            y = parts[0]; mo = parts[1]; d = parts[2] if len(parts) >= 3 else 1
            return f"{y:04d}-{mo:02d}-{d:02d}"
    return None


def alvo():
    """Traz doc_id + doi dos artigos com data só-ano (AAAA-01-01) e com DOI."""
    out, passo = [], 1000
    for off in range(0, 20000, passo):
        r = requests.get(f"{U}/rest/v1/artigos", headers=H, params={
            "select": "doc_id,doi,data_publicacao",
            "doi": "not.is.null", "limit": str(passo), "offset": str(off)}, timeout=40).json()
        out += [a for a in r if (a.get("data_publicacao") or "").endswith("-01-01")]
        if len(r) < passo:
            break
    return out


def main():
    arts = alvo()
    print(f"alvo: {len(arts)} artigos com data só-ano (AAAA-01-01) e DOI")
    fixos = igual = semdoi = mesmo_ano = 0
    for i, a in enumerate(arts, 1):
        real = crossref_data(a["doi"])
        time.sleep(0.12)                                          # educado com o CrossRef
        if not real:
            igual += 1
        elif real == a["data_publicacao"]:
            igual += 1
        else:
            # só grava se ganhou precisão (mês diferente de 01, ou dia): não sobrescreve por nada
            r = requests.patch(f"{U}/rest/v1/artigos", headers={**H, "Prefer": "return=minimal"},
                               params={"doc_id": f"eq.{a['doc_id']}"},
                               json={"data_publicacao": real}, timeout=30)
            if r.status_code in (200, 204):
                fixos += 1
                if fixos <= 12:
                    print(f"  {a['data_publicacao']} → {real}  ({a['doi']})")
        if i % 50 == 0:
            print(f"  ...{i}/{len(arts)} · corrigidos {fixos}")
    print(f"\nFIM · corrigidos {fixos} · sem melhora {igual} · total {len(arts)}")


if __name__ == "__main__":
    main()
