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

# ═══ 10/Ago/2026 — A LINHA QUE FALTAVA, E QUE CUSTOU 10 ARTIGOS ═══
# Em 09/Ago instrumentei este arquivo com o plano de voo: 8 chamadas a `_VOO.marcar(...)`
# em P2_CONTRATO, P3_MIDIA e P4_BANCO. E não escrevi o import. O `ficha_site.py` tinha,
# o `analisador.py` tinha, o `rodar_em_blocos.py` tinha — este não.
#
# POR QUE NADA PEGOU: `NameError` não existe em tempo de compilação. `python3 -c "import
# publicador"` passa, `ast.parse` passa, a bateria passa (ela não toca no publicador, que
# precisa de Supabase). O nome só falta no instante em que a linha roda — e a linha só roda
# quando um artigo REAL termina a análise e vai publicar. Eu escrevi "testei aqui" e a
# palavra estava certa pela LEI 7; o que faltou foi dizer que o publicador não estava no
# "aqui" de teste nenhum.
#
# O ESTRAGO: 10 artigos analisados e pagos, publicação recusada em todos, "fica na fila p/
# refazer". O dinheiro da análise não se perdeu (o pacote fica no STAGING com _OK e é
# reaproveitado), mas o Dr. Eduardo clicou uma chave que ia gastar US$ 30 e viu 10 falhas
# seguidas logo no primeiro bloco.
#
# A IRONIA: o defeito estava DENTRO do sistema de vigilância que existe para achar defeitos.
# O instrumento derrubou o voo. Por isso a `voo.marcar` foi escrita para NUNCA levantar
# exceção — e essa proteção não vale nada se o próprio NOME do módulo não existe.
import voo as _VOO


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
    """Upsert idempotente na tabela artigos. A tabela tem DUAS únicas: UNIQUE(doi) e UNIQUE(doc_id).
    Sem `on_conflict` o PostgREST resolve pela PK (id) — e o DOI existente bate na única → 409 (linha antiga
    do sistema velho tinha doc_id='doi_<hash>' e o DOI real na coluna doi). Então resolvemos NO conflito certo:
    tem DOI → on_conflict=doi (atualiza a linha existente, mesmo com doc_id antigo diferente); sem DOI → doc_id.
    Service role via .env — NUNCA hardcoded."""
    import requests
    url = os.getenv("SUPABASE_URL", "").rstrip("/")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY ausentes no .env")
    hdr = {"apikey": key, "Authorization": f"Bearer {key}"}
    conflito = "doi" if payload.get("doi") else "doc_id"   # DOI é a identidade forte; sem DOI cai no doc_id
    # PRESERVA o doc_id EXISTENTE: a linha antiga (sistema velho) tem doc_id='doi_<hash>' e pode estar
    # referenciada na tabela `entregas` (FK). Trocar o doc_id no update quebra a FK (23503). Então, se o
    # artigo já existe (por doi), reusa o doc_id que já está lá — o conteúdo atualiza, a entrega não órfãoza.
    if payload.get("doi"):
        try:
            g = requests.get(f"{url}/rest/v1/artigos", headers=hdr, timeout=15,
                             params={"doi": f"eq.{payload['doi']}", "select": "doc_id"})
            rows = g.json() if g.status_code == 200 else []
            if rows and rows[0].get("doc_id"):
                payload = {**payload, "doc_id": rows[0]["doc_id"]}
        except Exception:
            pass
    r = requests.post(
        f"{url}/rest/v1/artigos?on_conflict={conflito}",
        headers={**hdr, "Content-Type": "application/json",
                 "Prefer": "resolution=merge-duplicates,return=minimal"},
        json=payload, timeout=30)
    if r.status_code >= 400:                              # mostra a mensagem REAL do Supabase (coluna/constraint)
        raise RuntimeError(f"Supabase {r.status_code}: {r.text[:400]}")
    return r.status_code


# Schema REAL da tabela artigos (Supabase) — fonte da verdade p/ o preflight. Atualizar se a tabela mudar.
SCHEMA_ARTIGOS = {
    "id": "uuid", "doi": "text", "doc_id": "text", "titulo": "text", "revista": "text",
    "data_publicacao": "date", "tipo_estudo": "text", "doenca_principal": "text", "nota_aplicabilidade": "integer",
    "resumo_markdown": "text",
    "caminho_pdf": "text", "caminho_audio": "text",
    "created_at": "timestamp", "updated_at": "timestamp",
    "caminho_visual_abstract": "text", "keywords": "ARRAY", "contexto_tema": "text",
    "aplicabilidade_pratica": "text", "impacto_conduta": "text", "bullets_praticos": "jsonb", "gancho_lista": "text",
    "gancho_abertura": "text", "publicar_no_site": "boolean", "nota_trabalho_estatistico": "integer",
    "mcid_avaliacao": "text", "muda_conduta": "text",
    "motor": "text", "tipo_documento": "text", "veredito_dominios": "jsonb",
}


def _retirar_do_supabase(doi, doc_id, publicar=False):
    """RETRATAÇÃO — apaga a linha de um artigo que a régua ATUAL reprova.

    ═══ 04/Ago/2026, 22h30 — O PORTÃO PUBLICAVA MAS NUNCA RETRATAVA ═══

    Depois de a Escada entrar, o Dr. Eduardo rodou as 24 metas de novo. O placar da tela disse
    "11 publicados · 13 recusados". Mas o banco tinha 23 LINHAS — 11 da rodada e 12 FANTASMAS,
    de rodadas anteriores, com as notas da régua velha.

    O efeito era o inverso exato da LEI 10: um artigo reprovado de 8 para 5 saía para _RECUSADOS
    no disco e CONTINUAVA no banco valendo 8, pronto para ele mandar ao ar na Chave 5. E foi assim
    que a contradição `nota 9 · muda_conduta NÃO` reapareceu no banco depois de a gente matá-la:
    era uma linha velha do Ticagrelor, que nesta rodada tirou 5.

    Decisão dele (opção A, 04/Ago): **apagar a linha.** O banco reflete só o que a régua atual
    aprova. Coerente com "o site não recebe buraco" — e com o produto ser um FILTRO.

    LEI 5: quem apaga é o publicador, o mesmo e único portão que escreve. Ninguém mais.
    """
    import requests
    url = os.getenv("SUPABASE_URL", "").rstrip("/")
    key = (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_KEY")
           or os.getenv("SUPABASE_KEY", ""))
    if not url or not key:
        return None
    # a chave certa: a tabela tem UNIQUE(doi) e UNIQUE(doc_id) — usa o que existir
    if doi and doi != "n/a":
        alvo, valor = "doi", doi
    elif doc_id:
        alvo, valor = "doc_id", doc_id
    else:
        return None
    h = {"apikey": key, "Authorization": f"Bearer {key}", "Prefer": "return=representation"}
    try:
        # 1) existe linha? (no dry-run só OLHA — não apaga nada)
        g = requests.get(f"{url}/rest/v1/artigos", headers=h,
                         params={alvo: f"eq.{valor}", "select": "id,nota_aplicabilidade"}, timeout=30)
        linhas = g.json() if g.status_code == 200 else []
        if not linhas:
            return None
        if not publicar:
            return f"ENSAIO: existe linha (nota {linhas[0].get('nota_aplicabilidade')}) — seria APAGADA"
        r = requests.delete(f"{url}/rest/v1/artigos", headers=h,
                            params={alvo: f"eq.{valor}"}, timeout=30)
        if r.status_code in (200, 204):
            return f"RETRATADO: linha antiga (nota {linhas[0].get('nota_aplicabilidade')}) apagada"
        return f"⚠️  retratação falhou: {r.status_code} {r.text[:120]}"
    except Exception as e:
        return f"⚠️  retratação falhou: {type(e).__name__}: {str(e)[:100]}"


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
        # ═══ 09/Ago — ERA UM `return None` MUDO, E O ESTRAGO É PIOR DO QUE PARECE ═══
        # Quem chama faz `if u:` — se vier None, o campo FICA COM O CAMINHO LOCAL DO MAC,
        # e a linha sobe assim para o Supabase. O site renderiza um link para
        # `/Users/eduardocastro/...`, que não existe para ninguém no mundo.
        # As três causas são bem diferentes e agora aparecem separadas.
        _VOO.marcar("P3_MIDIA", ok=False, artigo=os.path.basename(str(local_path or "")),
                    bucket=bucket,
                    erro=("credencial do Supabase ausente" if not (url and key)
                          else f"arquivo local não existe: {local_path}"))
        print(f"  ⚠️  Storage {bucket}: NÃO subiu — " +
              ("credencial ausente" if not (url and key) else f"arquivo não existe ({os.path.basename(str(local_path or ''))})"))
        print(f"      ⚠️ o campo vai para o banco com o CAMINHO LOCAL, que não abre fora deste Mac.")
        return None
    url_publica = f"{url}/storage/v1/object/public/{bucket}/{objeto}"
    with open(local_path, "rb") as f:
        dados = f.read()
    hdr = {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": content_type, "x-upsert": "true"}

    # ═══ 06/Ago — RETRY DE REDE NO UPLOAD (a falha que mais custou clique) ═══
    #
    # Havia tratamento para erro de STATUS (400/404 = bucket não existe) e NENHUM para EXCEÇÃO de
    # rede. Um `BrokenPipeError` no meio do envio subia e derrubava o artigo inteiro, que voltava
    # para a fila. Medido em 06/Ago, em duas rodadas seguidas:
    #
    #     GUIDELINES ... 6 de 31 falharam  (ConnectionError · SSLError · timeout)
    #     REVISOES ..... 5 de 89 falharam  (BrokenPipe · RemoteDisconnected, TODAS seguidas)
    #
    # ~5%. Nos 236 artigos originais isso seriam ~12 artigos caindo — e caindo de MADRUGADA, com
    # o Dr. Eduardo dormindo depois de um plantão. Ele reclicaria de manhã, de graça (reusa o
    # staging), mas é uma hora de rodada perdida por um problema de 20 linhas.
    #
    # POR QUE ACONTECE AQUI e não nas outras chamadas: este é o único ponto que empurra ARQUIVO —
    # PNG de ~500 KB, áudio de ~4 MB. Conexão doméstica instável derruba upload longo muito antes
    # de derrubar um POST de JSON. As 5 falhas vieram em sequência: foi UMA janela ruim de rede,
    # e três tentativas com espera crescente atravessariam a janela inteira.
    def _post(u, **kw):
        """POST com 3 tentativas e espera crescente (2s · 6s · 18s). Só reenvia em erro de REDE —
        erro de status é decidido pelo chamador, que sabe o que 400 e 404 significam aqui."""
        import time
        ultimo = None
        for i in range(3):
            try:
                return requests.post(u, **kw)
            except requests.exceptions.RequestException as e:
                ultimo = e
                if i < 2:
                    espera = 2 * (3 ** i)
                    print(f"  ↻ rede caiu no upload ({type(e).__name__}) — tentativa {i + 2}/3 "
                          f"em {espera}s")
                    time.sleep(espera)
        raise ultimo

    r = _post(f"{url}/storage/v1/object/{bucket}/{objeto}", headers=hdr, data=dados, timeout=120)
    if r.status_code in (200, 201):
        _VOO.marcar("P3_MIDIA", artigo=objeto, bucket=bucket, kb=len(dados) // 1024)
        return url_publica
    if r.status_code in (400, 404):                      # bucket pode não existir → cria e re-tenta
        _post(f"{url}/storage/v1/bucket",
              headers={"apikey": key, "Authorization": f"Bearer {key}"},
              json={"id": bucket, "name": bucket, "public": True}, timeout=15)
        r = _post(f"{url}/storage/v1/object/{bucket}/{objeto}", headers=hdr, data=dados, timeout=120)
        if r.status_code in (200, 201):
            return url_publica
    _VOO.marcar("P3_MIDIA", ok=False, artigo=objeto, bucket=bucket,
                erro=f"HTTP {r.status_code}: {r.text[:200]}")
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
        # RETRATAÇÃO (04/Ago): se este artigo já estava no banco de uma régua anterior, sai.
        msg = _retirar_do_supabase(ficha.get("doi"), ficha.get("doc_id"), publicar)
        if msg:
            print(f"  ↩️  {msg}")
        # ═══ WAYPOINT P2 — "o contrato validou (ou recusou)" ═══
        # RECUSA NÃO É FALHA: nota <6 é a LEI 10 funcionando. O que se registra é a CAUSA,
        # para que a pergunta "por que este artigo não subiu?" nunca mais dependa de eu ir
        # ler um arquivo de motivo de uma rodada de duas semanas atrás — que foi exatamente
        # o erro que cometi em 09/Ago, contando 90 artigos publicados como retidos.
        _VOO.marcar("P2_CONTRATO", ok=False, artigo=base,
                    nota=ficha.get("nota_aplicabilidade"),
                    tipo_documento=ficha.get("tipo_documento"),
                    violacoes=len(violacoes),
                    erro=" · ".join(violacoes[:3])[:380])
        return ("RECUSADO", ficha.get("nota_aplicabilidade"), violacoes)

    _VOO.marcar("P2_CONTRATO", artigo=base, nota=ficha.get("nota_aplicabilidade"),
                tipo_documento=ficha.get("tipo_documento"), violacoes=0)

    # passou no portão do CONTRATO → agora o PREFLIGHT de SCHEMA (roda até no dry-run: pega o erro antes)
    prob = _preflight(_payload_site(ficha))
    if prob:
        open(os.path.join(pasta, "_REVISAR_publicacao.txt"), "w", encoding="utf-8").write(
            "RECUSADO NO PREFLIGHT DE SCHEMA — tipo/coluna não bate com a tabela artigos:\n\n"
            + "\n".join(f"  • {p}" for p in prob) + "\n")
        msg = _retirar_do_supabase(ficha.get("doi"), ficha.get("doc_id"), publicar)
        if msg:
            print(f"  ↩️  {msg}")
        _VOO.marcar("P4_BANCO", ok=False, artigo=base,
                    erro="preflight de schema: " + " · ".join(prob[:3])[:340])
        return ("RECUSADO(schema)", ficha.get("nota_aplicabilidade"), prob)
    if publicar:
        ficha = _subir_midia(ficha)              # payload validado → sobe PNG/áudio/PDF, troca por URLs
    open(os.path.join(pasta, "_SITE.json"), "w", encoding="utf-8").write(
        json.dumps(_payload_site(ficha), ensure_ascii=False, indent=2))
    if publicar:
        # ═══ WAYPOINT P4 — "a linha entrou na tabela artigos" ═══
        # É o último waypoint do voo do artigo. Se ele existe, o artigo chegou. Se o P3
        # passou e este não veio, o trecho a investigar é P3→P4, e a zona de busca é
        # coluna NOT NULL, chave única duplicada, credencial, rede.
        try:
            code = _upsert_supabase(_payload_site(ficha))
        except Exception as e:
            _VOO.marcar("P4_BANCO", ok=False, artigo=base, erro=f"{type(e).__name__}: {e}")
            raise
        _VOO.marcar("P4_BANCO", artigo=base, http=code,
                    nota=ficha.get("nota_aplicabilidade"), doi=ficha.get("doi"))
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
