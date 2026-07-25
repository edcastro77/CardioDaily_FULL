"""
publicador.py — O APP PUBLICADOR (Elo 3), autocontido e modular.
Lê o STAGING (o que o Analisador aprovou) → por artigo: monta a FICHA → passa pelo CONTRATO (portão) →
  ✅ passou  → grava _SITE.json (dry-run)  |  sobe pro Supabase (--publicar)  [upsert idempotente por doc_id]
  ❌ furou   → NÃO sobe. Grava _REVISAR_publicacao.txt dizendo QUAL campo furou. Fica retido.

Modularidade: só PUBLICA. Não analisa (é do analisador), não limpa (é do arquivador).
LEI DO CLONE: default é --dry-run (nada vai pro ar). Só sobe de verdade com --publicar.

Uso:
  python publicador.py <STAGING>                 # dry-run: monta ficha + valida + escreve _SITE.json / _REVISAR
  python publicador.py <STAGING> --publicar       # sobe os aprovados pro Supabase (upsert por doc_id)
"""
import os, sys, json, glob, argparse

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
import contrato as C
import ficha_site as F


def _carregar_env():
    from dotenv import load_dotenv
    d = _HERE
    for _ in range(8):
        cand = os.path.join(d, "CardioDaily_FULL", ".env")
        if os.path.exists(cand):
            load_dotenv(cand, override=True); return
        d = os.path.dirname(d)
    load_dotenv(override=True)


def _payload_site(ficha):
    """Só os 16 campos do contrato (tira metadados auxiliares que começam com _)."""
    return {k: v for k, v in ficha.items() if not k.startswith("_")}


def _upsert_supabase(payload):
    """Upsert idempotente na tabela artigos (merge por doc_id). Service role via .env — NUNCA hardcoded."""
    import requests
    url = os.getenv("SUPABASE_URL", "").rstrip("/")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY ausentes no .env")
    r = requests.post(
        f"{url}/rest/v1/artigos",
        headers={"apikey": key, "Authorization": f"Bearer {key}",
                 "Content-Type": "application/json",
                 "Prefer": "resolution=merge-duplicates,return=minimal"},
        json=payload, timeout=30)
    if r.status_code >= 400:                              # mostra a mensagem REAL do Supabase (coluna/constraint)
        raise RuntimeError(f"Supabase {r.status_code}: {r.text[:400]}")
    return r.status_code


# Schema REAL da tabela artigos (Supabase) — fonte da verdade p/ o preflight. Atualizar se a tabela mudar.
SCHEMA_ARTIGOS = {
    "id": "uuid", "doi": "text", "doc_id": "text", "titulo": "text", "revista": "text",
    "data_publicacao": "date", "tipo_estudo": "text", "doenca_principal": "text",
    "populacao": "ARRAY", "intervencao": "ARRAY", "nota_aplicabilidade": "integer",
    "nota_geral": "integer", "resumo_markdown": "text", "caminho_pasta": "text",
    "caminho_pdf": "text", "caminho_audio": "text", "analysis_datetime": "timestamp",
    "created_at": "timestamp", "updated_at": "timestamp", "palavras_chave": "ARRAY",
    "caminho_visual_abstract": "text", "keywords": "ARRAY", "contexto_tema": "text",
    "aplicabilidade_pratica": "text", "impacto_conduta": "text", "tamanho_beneficio": "text",
    "conclusao_geral": "text", "bullets_praticos": "jsonb", "gancho_lista": "text",
    "gancho_abertura": "text", "publicar_no_site": "boolean", "nota_trabalho_estatistico": "integer",
    "mcid_avaliacao": "text", "muda_conduta": "text", "por_que_importa": "text",
    "principais_recomendacoes": "text", "nota_metodologica": "numeric", "embedding": "USER-DEFINED",
    "descartado": "boolean",
}


def _preflight(payload):
    """Confere o payload contra o SCHEMA REAL antes de subir. Devolve lista de problemas (vazia = ok).
    Mata o 400 mudo do Supabase: mismatch de tipo/coluna vira erro LOCAL e falado, na hora."""
    import re
    probs = []
    for campo, v in payload.items():
        if campo not in SCHEMA_ARTIGOS:
            probs.append(f"coluna '{campo}' não existe na tabela artigos"); continue
        if v is None:
            continue
        t = SCHEMA_ARTIGOS[campo]
        if t == "date" and not (isinstance(v, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", v)):
            probs.append(f"{campo}: DATE exige AAAA-MM-DD, veio {v!r}")
        elif t == "timestamp" and not (isinstance(v, str) and re.match(r"\d{4}-\d{2}-\d{2}", v)):
            probs.append(f"{campo}: TIMESTAMP inválido: {v!r}")
        elif t == "integer" and (not isinstance(v, int) or isinstance(v, bool)):
            probs.append(f"{campo}: INTEGER exige int, veio {type(v).__name__}")
        elif t == "numeric" and (not isinstance(v, (int, float)) or isinstance(v, bool)):
            probs.append(f"{campo}: NUMERIC exige número, veio {type(v).__name__}")
        elif t == "boolean" and not isinstance(v, bool):
            probs.append(f"{campo}: BOOLEAN exige true/false, veio {type(v).__name__}")
        elif t in ("ARRAY", "jsonb") and not isinstance(v, (list, dict)):
            probs.append(f"{campo}: {t} exige lista, veio {type(v).__name__}")
        elif t == "text" and not isinstance(v, str):
            probs.append(f"{campo}: TEXT exige string, veio {type(v).__name__}")
    return probs


def _upload_storage(bucket, local_path, objeto, content_type):
    """Sobe UM arquivo pro Storage (bucket público) com a service_role e devolve a URL pública.
    x-upsert idempotente; cria o bucket se não existir. Devolve None se falhar (não derruba a linha)."""
    import requests
    url = os.getenv("SUPABASE_URL", "").rstrip("/")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY", "")
    if not url or not key or not local_path or not os.path.exists(local_path):
        return None
    url_publica = f"{url}/storage/v1/object/public/{bucket}/{objeto}"
    with open(local_path, "rb") as f:
        dados = f.read()
    hdr = {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": content_type, "x-upsert": "true"}
    r = requests.post(f"{url}/storage/v1/object/{bucket}/{objeto}", headers=hdr, data=dados, timeout=120)
    if r.status_code in (200, 201):
        return url_publica
    if r.status_code in (400, 404):                      # bucket pode não existir → cria e re-tenta
        requests.post(f"{url}/storage/v1/bucket",
                      headers={"apikey": key, "Authorization": f"Bearer {key}"},
                      json={"id": bucket, "name": bucket, "public": True}, timeout=15)
        r = requests.post(f"{url}/storage/v1/object/{bucket}/{objeto}", headers=hdr, data=dados, timeout=120)
        if r.status_code in (200, 201):
            return url_publica
    print(f"  ⚠️  Storage {bucket}: {r.status_code} {r.text[:120]}")
    return None


def _subir_midia(ficha):
    """Sobe PNG/áudio/PDF pro Storage e troca os caminho_* LOCAIS pelas URLs públicas (o que o site usa).
    Sem arquivo local → deixa o campo como está. Buckets: visual_abstracts / podcasts / resumos_pdf."""
    doc = ficha.get("doc_id") or "artigo"
    mapa = [("caminho_visual_abstract", "visual_abstracts", f"{doc}.png", "image/png"),
            ("caminho_audio",           "podcasts",         f"{doc}.mp3", "audio/mpeg"),
            ("caminho_pdf",             "resumos_pdf",      f"{doc}.pdf", "application/pdf")]
    for campo, bucket, objeto, ctype in mapa:
        local = ficha.get(campo, "")
        if local and os.path.exists(local):
            u = _upload_storage(bucket, local, objeto, ctype)
            if u:
                ficha[campo] = u                          # caminho local → URL pública
    return ficha


def processar_pasta(pasta, publicar=False):
    ficha = F.montar(pasta)
    violacoes = C.validar(ficha, checar_arquivos=True)
    base = os.path.basename(pasta.rstrip("/"))

    if violacoes:
        rep = os.path.join(pasta, "_REVISAR_publicacao.txt")
        open(rep, "w", encoding="utf-8").write(
            "RECUSADO PELO CONTRATO DE PUBLICAÇÃO — o site não recebe buraco.\n\n"
            + f"Artigo: {ficha.get('titulo') or base}\nNota: {ficha.get('nota_aplicabilidade')}\n\n"
            + "Campos que furaram:\n" + "\n".join(f"  • {v}" for v in violacoes) + "\n")
        return ("RECUSADO", ficha.get("nota_aplicabilidade"), violacoes)

    # passou no portão do CONTRATO → agora o PREFLIGHT de SCHEMA (roda até no dry-run: pega o erro antes)
    prob = _preflight(_payload_site(ficha))
    if prob:
        open(os.path.join(pasta, "_REVISAR_publicacao.txt"), "w", encoding="utf-8").write(
            "RECUSADO NO PREFLIGHT DE SCHEMA — tipo/coluna não bate com a tabela artigos:\n\n"
            + "\n".join(f"  • {p}" for p in prob) + "\n")
        return ("RECUSADO(schema)", ficha.get("nota_aplicabilidade"), prob)
    if publicar:
        ficha = _subir_midia(ficha)              # payload validado → sobe PNG/áudio/PDF, troca por URLs
    open(os.path.join(pasta, "_SITE.json"), "w", encoding="utf-8").write(
        json.dumps(_payload_site(ficha), ensure_ascii=False, indent=2))
    if publicar:
        code = _upsert_supabase(_payload_site(ficha))
        return (f"PUBLICADO({code})", ficha.get("nota_aplicabilidade"), [])
    return ("APROVADO(dry-run)", ficha.get("nota_aplicabilidade"), [])


def main():
    ap = argparse.ArgumentParser(description="Publicador (Elo 3) — STAGING → contrato → Supabase")
    ap.add_argument("staging", help="pasta STAGING (com uma subpasta por artigo)")
    ap.add_argument("--publicar", action="store_true", help="sobe de verdade pro Supabase (default: dry-run)")
    a = ap.parse_args()
    if a.publicar:
        _carregar_env()

    pastas = sorted(p for p in glob.glob(os.path.join(os.path.expanduser(a.staging), "*")) if os.path.isdir(p))
    print(f"PUBLICADOR — {len(pastas)} artigo(s) no staging  ·  modo: {'PUBLICAR' if a.publicar else 'DRY-RUN'}\n")
    ok = rec = 0
    for pasta in pastas:
        try:
            status, nota, viol = processar_pasta(pasta, a.publicar)
        except Exception as e:
            status, nota, viol = (f"ERRO: {type(e).__name__}: {e}", None, [])
        base = os.path.basename(pasta)[:44]
        print(f"  {base:44} nota {str(nota):>4} · {status}")
        if viol:
            for v in viol[:6]:
                print(f"         ↳ {v}")
        if status.startswith(("APROVADO", "PUBLICADO")):
            ok += 1
        elif status.startswith("RECUSADO"):
            rec += 1
    print(f"\n{ok} aprovado(s)/publicado(s) · {rec} recusado(s) (retidos em _REVISAR_publicacao.txt)")


if __name__ == "__main__":
    main()
