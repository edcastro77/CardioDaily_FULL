#!/usr/bin/env python3
"""
CardioDaily — Auditor de Integridade do Supabase v2.1

Gera relatório semanal das tabelas `artigos` e `radar`:
- Campos nulos obrigatórios
- Artigos elegíveis sem áudio (nota ≥ 8)
- Artigos sem PDF
- Artigos sem keywords
- Artigos sem resumo_markdown
- Cobertura do Radar (temas sem episódio nos últimos 14 dias)
- Discrepância corpus local vs. Supabase

Envia resultado via Telegram ao Dr. Eduardo.
Salva relatório em outputs/auditorias/

Uso:
    python3 scripts/auditoria_supabase.py           # relatório completo + envia Telegram
    python3 scripts/auditoria_supabase.py --dry-run # só exibe, não envia
    python3 scripts/auditoria_supabase.py --quick   # só contadores, sem amostras
"""

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "src"))

try:
    from dotenv import load_dotenv
    load_dotenv(_ROOT / ".env")
except ImportError:
    pass

SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY", "")
CORPUS_DIR   = _ROOT / "outputs" / "corpus"
OUTPUT_DIR   = _ROOT / "outputs" / "auditorias"

# ── títulos genéricos/inválidos ─────────────────────────────────────────────
# Padrões que indicam que o título não foi preenchido corretamente.
# Qualquer título que contenha um desses fragmentos (case-insensitive) é genérico.
TITULOS_GENERICOS_FRAGMENT = [
    "o que tem esta paciente",
    "o que tem este paciente",
    "análise do artigo",
    "analise do artigo",
    "estudo clínico recente",
    "estudo clinico recente",
    "artigo em análise",
    "artigo em analise",
    "título não disponível",
    "titulo nao disponivel",
    "sem título",
    "sem titulo",
    "untitled",
    "resumo do estudo",
    "resumo do artigo",
    "novo artigo",
    "artigo recente",
    "estudo recente",
    "publicação recente",
    "publicacao recente",
]

# Títulos muito curtos (≤ 10 chars) também são suspeitos
TITULO_MIN_CHARS = 10

HDRS = lambda: {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
}


# ── helpers ─────────────────────────────────────────────────────────────────

def _count(table: str, params: dict) -> int:
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/{table}",
        headers={**HDRS(), "Prefer": "count=exact", "Range": "0-0"},
        params={"select": "doc_id" if table == "artigos" else "id", **params},
        timeout=30,
    )
    try:
        return int(r.headers.get("Content-Range", "0/0").split("/")[1])
    except Exception:
        return 0


def _fetch(table: str, params: dict, limit: int = 10) -> list[dict]:
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/{table}",
        headers=HDRS(),
        params={**params, "limit": str(limit)},
        timeout=30,
    )
    return r.json() if r.status_code == 200 and isinstance(r.json(), list) else []


def _semaforo(valor: int, amarelo: int, vermelho: int) -> str:
    if valor >= vermelho:
        return "🔴"
    if valor >= amarelo:
        return "🟡"
    return "✅"


def _pct(parte: int, total: int) -> str:
    if not total:
        return "0%"
    return f"{parte / total * 100:.1f}%"


# ── detecção de títulos genéricos ───────────────────────────────────────────

def _detectar_titulos_genericos(quick: bool = False) -> list[dict]:
    """
    Busca artigos com títulos genéricos/inválidos.
    Faz paginação em lotes de 1000 para varrer todo o banco.
    Retorna lista de dicts com doc_id, titulo, nota_aplicabilidade.
    """
    encontrados = []
    offset = 0
    batch  = 1000

    while True:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/artigos",
            headers=HDRS(),
            params={
                "select": "doc_id,titulo,nota_aplicabilidade",
                "titulo": "not.is.null",   # só os que TÊM título (os nulos já são capturados acima)
                "order":  "nota_aplicabilidade.desc",
                "offset": str(offset),
                "limit":  str(batch),
            },
            timeout=60,
        )
        if r.status_code != 200:
            break
        dados = r.json()
        if not isinstance(dados, list) or not dados:
            break

        for a in dados:
            titulo = (a.get("titulo") or "").strip()
            if not titulo:
                continue
            # Muito curto
            if len(titulo) <= TITULO_MIN_CHARS:
                encontrados.append(a)
                continue
            # Fragmento genérico
            titulo_lower = titulo.lower()
            if any(frag in titulo_lower for frag in TITULOS_GENERICOS_FRAGMENT):
                encontrados.append(a)

        if len(dados) < batch:
            break

        # Em modo quick, basta checar os primeiros 2000
        if quick and offset >= 2000:
            break

        offset += batch

    # Ordena por nota desc para mostrar os mais críticos primeiro
    encontrados.sort(key=lambda x: -(x.get("nota_aplicabilidade") or 0))
    return encontrados


# ── checks individuais ───────────────────────────────────────────────────────

def check_artigos(quick: bool) -> tuple[str, list[str]]:
    """Retorna (bloco_texto, lista_comandos_correcao)."""
    linhas = ["📚 TABELA artigos"]
    comandos = []

    total = _count("artigos", {})
    linhas.append(f"   Total: {total:,} artigos")

    # Sem PDF
    sem_pdf = _count("artigos", {"caminho_pdf": "is.null"})
    s = _semaforo(sem_pdf, 100, 500)
    linhas.append(f"   {s} Sem caminho_pdf:      {sem_pdf:,} ({_pct(sem_pdf, total)})")
    if sem_pdf > 0:
        comandos.append(f"PDFs faltando ({sem_pdf:,}): python3 scripts/upload_pdfs_supabase.py --since 2020-01-01")

    # Sem áudio
    sem_audio = _count("artigos", {"caminho_audio": "is.null"})
    s = _semaforo(sem_audio, 200, 1000)
    linhas.append(f"   {s} Sem caminho_audio:    {sem_audio:,} ({_pct(sem_audio, total)})")

    # Elegíveis sem áudio (nota ≥ 8, qualquer ano)
    eleg_sem_audio = _count("artigos", {"caminho_audio": "is.null", "nota_aplicabilidade": "gte.8"})
    s = _semaforo(eleg_sem_audio, 10, 30)
    linhas.append(f"   {s} Nota≥8 sem áudio:     {eleg_sem_audio:,}")
    if eleg_sem_audio > 0:
        comandos.append(f"Áudios nota≥8 ({eleg_sem_audio:,}): python3 scripts/gerar_audios_lote.py")

    # Sem resumo_markdown
    sem_resumo = _count("artigos", {"resumo_markdown": "is.null"})
    s = _semaforo(sem_resumo, 50, 200)
    linhas.append(f"   {s} Sem resumo_markdown:  {sem_resumo:,} ({_pct(sem_resumo, total)})")

    # Sem keywords
    sem_kw = _count("artigos", {"keywords": "is.null"})
    s = _semaforo(sem_kw, 50, 200)
    linhas.append(f"   {s} Sem keywords:         {sem_kw:,} ({_pct(sem_kw, total)})")

    # Sem titulo (null ou string vazia)
    sem_titulo_null  = _count("artigos", {"titulo": "is.null"})
    sem_titulo_vazio = _count("artigos", {"titulo": "eq."})
    sem_titulo = sem_titulo_null + sem_titulo_vazio
    s = _semaforo(sem_titulo, 5, 50)
    linhas.append(f"   {s} Sem titulo:           {sem_titulo:,} (null={sem_titulo_null}, vazio={sem_titulo_vazio})")
    if sem_titulo > 0:
        linhas.append(f"   ⚠️  ATENÇÃO: {sem_titulo} artigo(s) com título ausente — com portão de validação "
                      f"ativo, deveriam ter sido barrados na ingestão e gravados em artigos_rejeitados. "
                      f"Reparo pontual se necessário (NÃO usar backfill aposentado em archive/).")

    # Títulos genéricos — busca em lotes, avalia localmente
    genericos = _detectar_titulos_genericos(quick=quick)
    n_gen = len(genericos)
    s = _semaforo(n_gen, 1, 5)
    linhas.append(f"   {s} Títulos genéricos:    {n_gen:,}")
    if n_gen > 0:
        linhas.append("   ⚠️  ATENÇÃO: Estes artigos têm títulos inválidos e NÃO devem ser enviados:")
        for g in genericos[:10]:
            doc_id = (g.get("doc_id") or "?")[:22]
            titulo = (g.get("titulo") or "?")[:70]
            nota   = g.get("nota_aplicabilidade", "?")
            linhas.append(f"      🚫 [{nota}] {doc_id} — \"{titulo}\"")
        if n_gen > 10:
            linhas.append(f"      ... e mais {n_gen - 10} artigos com título genérico")
        comandos.append(
            f"Títulos genéricos ({n_gen}): python3 scripts/backfill_sem_resumo.py --apenas-sem-titulo"
        )

    # Sem doenca_principal
    sem_doenca = _count("artigos", {"doenca_principal": "is.null"})
    s = _semaforo(sem_doenca, 10, 50)
    linhas.append(f"   {s} Sem doenca_principal: {sem_doenca:,}")

    # Últimos 7 dias
    since_7d = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    novos_7d = _count("artigos", {"created_at": f"gte.{since_7d}"})
    linhas.append(f"   📈 Indexados últimos 7 dias: {novos_7d:,}")

    # Amostra nota≥8 sem áudio (se não quick)
    if not quick and eleg_sem_audio > 0:
        sample = _fetch("artigos", {
            "select": "doc_id,titulo,nota_aplicabilidade,tipo_estudo,data_publicacao",
            "caminho_audio": "is.null",
            "nota_aplicabilidade": "gte.8",
            "order": "nota_aplicabilidade.desc",
        }, limit=5)
        if sample:
            linhas.append("   ── Amostra nota≥8 sem áudio (top 5) ──")
            for a in sample:
                titulo = (a.get("titulo") or "sem título")[:55]
                nota = a.get("nota_aplicabilidade", "?")
                tipo = (a.get("tipo_estudo") or "?")[:12]
                linhas.append(f"   • [{nota}] {tipo:<12} {titulo}")

    return "\n".join(linhas), comandos


def check_radar(quick: bool) -> tuple[str, list[str]]:
    """Verifica cobertura da tabela radar nos últimos 14 dias."""
    linhas = ["📡 TABELA radar"]
    comandos = []

    total_radar = _count("radar", {})
    linhas.append(f"   Total de episódios: {total_radar:,}")

    # Episódios últimos 14 dias
    since_14d = (datetime.now(timezone.utc) - timedelta(days=14)).isoformat()
    recentes = _fetch("radar", {
        "select": "tema,data_varredura,artigos_analisados,caminho_podcast",
        "created_at": f"gte.{since_14d}",
        "order": "data_varredura.desc",
    }, limit=50)

    temas_cobertos = {r["tema"] for r in recentes}
    temas_todos = {
        "doenca_coronariana", "cardio_metabolica", "arritmias",
        "insuficiencia_cardiaca", "valvulopatias", "miocardiopatias",
        "intervencao_hemodinamica", "cardio_oncologia", "cardiobstetrica",
        "cardio_genomica", "uti_cardiologica", "aorta_congenitas",
        "imagem_cardiovascular",
    }
    temas_ausentes = temas_todos - temas_cobertos

    s = _semaforo(len(temas_ausentes), 3, 7)
    linhas.append(f"   {s} Temas cobertos (14d): {len(temas_cobertos)}/13")

    if temas_ausentes:
        linhas.append(f"   ⚠️  Temas sem episódio nos últimos 14 dias:")
        for t in sorted(temas_ausentes):
            linhas.append(f"      • {t}")

    # Episódios sem áudio (caminho_podcast nulo ou vazio)
    sem_podcast = [r for r in recentes if not r.get("caminho_podcast")]
    if sem_podcast:
        s2 = _semaforo(len(sem_podcast), 2, 5)
        linhas.append(f"   {s2} Episódios recentes sem podcast: {len(sem_podcast)}")
        for r in sem_podcast[:3]:
            linhas.append(f"      • {r['tema']} — {r.get('data_varredura','?')}")
        comandos.append(f"Radar sem podcast ({len(sem_podcast)}): verificar logs do GitHub Actions")

    # Últimos 3 episódios gerados
    if not quick and recentes:
        linhas.append("   ── Últimos 3 episódios ──")
        for r in recentes[:3]:
            n = r.get("artigos_analisados", "?")
            d = r.get("data_varredura", "?")
            t = r.get("tema", "?")
            tem_audio = "🎙️" if r.get("caminho_podcast") else "❌"
            linhas.append(f"   {tem_audio} {d} — {t} ({n} artigos)")

    return "\n".join(linhas), comandos


def check_corpus_local() -> str:
    """Compara corpus local com Supabase."""
    linhas = ["💾 CORPUS LOCAL"]

    if not CORPUS_DIR.exists():
        linhas.append("   ⚠️  Diretório outputs/corpus não encontrado")
        return "\n".join(linhas)

    pastas = [d for d in CORPUS_DIR.iterdir() if d.is_dir()]
    n_local = len(pastas)
    total_sb = _count("artigos", {})

    delta = n_local - total_sb
    s = _semaforo(abs(delta), 50, 200)
    linhas.append(f"   {s} Local: {n_local:,} | Supabase: {total_sb:,} | Delta: {delta:+d}")

    sem_analysis = sum(1 for d in pastas if not (d / "analysis.json").exists() and not (d / "analysis.md").exists())
    s2 = _semaforo(sem_analysis, 10, 50)
    linhas.append(f"   {s2} Pastas sem analysis.json/md: {sem_analysis:,}")

    sem_pdf_local = sum(1 for d in pastas if not (d / "assets" / "resumo.pdf").exists() and (d / "analysis.md").exists())
    s3 = _semaforo(sem_pdf_local, 100, 500)
    linhas.append(f"   {s3} Pastas com analysis mas sem PDF local: {sem_pdf_local:,}")

    return "\n".join(linhas)


# ── relatório final ──────────────────────────────────────────────────────────

def gerar_relatorio(quick: bool = False) -> str:
    agora = datetime.now().strftime("%d/%m/%Y %H:%M")

    bloco_artigos, cmds_artigos = check_artigos(quick)
    bloco_radar,   cmds_radar   = check_radar(quick)
    bloco_local                  = check_corpus_local()

    todos_cmds = cmds_artigos + cmds_radar

    linhas = [
        f"{'='*55}",
        f"CardioDaily — Auditoria de Integridade",
        f"📅 {agora}",
        f"{'='*55}",
        "",
        bloco_artigos,
        "",
        bloco_radar,
        "",
        bloco_local,
        "",
        f"{'─'*55}",
    ]

    if todos_cmds:
        linhas.append("🔧 AÇÕES NECESSÁRIAS:")
        for i, cmd in enumerate(todos_cmds, 1):
            linhas.append(f"   {i}. {cmd}")
    else:
        linhas.append("✅ Nenhuma ação necessária — tudo em dia!")

    linhas.append(f"{'='*55}")
    return "\n".join(linhas)


def _enviar_telegram(texto: str):
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat  = os.getenv("TELEGRAM_CHAT_ID", "")
    if not token or not chat:
        print("   ⚠️  Telegram não configurado — relatório não enviado.")
        return
    msg = f"```\n{texto[:4000]}\n```"  # Telegram limita 4096 chars por msg
    r = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat, "text": msg, "parse_mode": "Markdown"},
        timeout=30,
    )
    if r.status_code == 200:
        print("   📨 Relatório enviado ao Telegram.")
    else:
        print(f"   ⚠️  Telegram falhou: {r.status_code} {r.text[:100]}")

    # Se relatório for longo, enviar o arquivo completo também
    if len(texto) > 3800:
        data_str = datetime.now().strftime("%Y%m%d_%H%M")
        fname = f"auditoria_{data_str}.txt"
        requests.post(
            f"https://api.telegram.org/bot{token}/sendDocument",
            data={"chat_id": chat, "caption": f"📋 Auditoria completa — {datetime.now().strftime('%d/%m/%Y')}"},
            files={"document": (fname, texto.encode(), "text/plain")},
            timeout=30,
        )


def main():
    parser = argparse.ArgumentParser(description="CardioDaily — Auditoria Supabase")
    parser.add_argument("--dry-run", action="store_true", help="Só exibe, não envia Telegram")
    parser.add_argument("--quick",   action="store_true", help="Só contadores, sem amostras")
    args = parser.parse_args()

    if not SUPABASE_URL or not SUPABASE_KEY:
        print("❌ SUPABASE_URL / SUPABASE_SERVICE_KEY não configurados")
        sys.exit(1)

    relatorio = gerar_relatorio(quick=args.quick)
    print(relatorio)

    # Salvar em disco
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    data_str = datetime.now().strftime("%Y%m%d_%H%M")
    out_path = OUTPUT_DIR / f"auditoria_{data_str}.txt"
    out_path.write_text(relatorio, encoding="utf-8")
    print(f"\n💾 Salvo em: {out_path}")

    if not args.dry_run:
        _enviar_telegram(relatorio)


if __name__ == "__main__":
    main()
