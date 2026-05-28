#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CardioDaily — Extração de campos clínicos a partir do analysis.md existente

Lê o analysis.md já gerado e usa um LLM barato (Gemini 2.0 Flash ou 2.5 Flash)
para extrair os campos que faltam no Supabase — SEM reanalisar o PDF.

Modo teste: gera um JSON de comparação lado a lado para validação manual.
Modo produção: atualiza o Supabase diretamente (apenas campos vazios).

USO:
    # Teste com 11 artigos específicos (validação manual)
    python3 scripts/extrai_campos_llm.py --teste

    # Produção: todos os nota>=7 sem contexto_tema
    python3 scripts/extrai_campos_llm.py --nota-min 7 --workers 5

    # Dry-run (mostra o que faria sem salvar)
    python3 scripts/extrai_campos_llm.py --nota-min 7 --dry-run
"""

import argparse
import json
import os
import sys
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")
except ImportError:
    pass

ROOT         = Path(__file__).parent.parent
CORPUS_DIR   = ROOT / "outputs" / "corpus"
SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY", "")
GEMINI_KEY   = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY", "")

# Artigos do teste de validação (5 originais + 3 revisões + 3 meta-análises)
ARTIGOS_TESTE = [
    # originais
    "doi_6e4e60bb372de0fc",
    "doi_6dd0dd7a0a2524c0",
    "doi_885f3b9ac62714df",
    "doi_c5521a29458f6b6c",
    "doi_7afaaefa6d4f2363",
    # revisões
    "doi_3877eb89e8930c19",
    "doi_ac8ef8f8e3c0d021",
    "doi_4ccdb5458141d1ca",
    # meta-análises
    "doi_3b4a024fe088d817",
    "doi_1e16a32d3f1289dc",
    "doi_b06376a098656fd7",
]

PROMPT_EXTRACAO = """Você é um assistente especializado em cardiologia clínica prática.

Abaixo está a análise completa de um artigo científico já realizada por um especialista.
Sua tarefa é EXTRAIR — não reescrever — as informações já presentes nesta análise
e estruturá-las nos campos abaixo.

NÃO invente informações. Se um campo não puder ser extraído diretamente da análise,
deixe como null.

ANÁLISE DO ARTIGO:
{analysis_text}

---

Retorne APENAS um JSON válido com esta estrutura (sem markdown, sem explicação):

{{
  "keywords": ["termo EN 1", "termo EN 2", "termo EN 3", "termo EN 4", "termo EN 5"],
  "contexto_tema": "2-3 frases: qual o tema e o que já se sabe sobre ele hoje",
  "aplicabilidade_pratica": "1-2 frases: como aplicar na prática clínica",
  "impacto_conduta": "1-2 frases: o que muda na conduta após este estudo",
  "tamanho_beneficio": "números concretos: HR, RR, NNT, p-valor, IC95%",
  "conclusao_geral": "1-2 frases: síntese da conclusão do estudo",
  "bullets_praticos": [
    "bullet prático 1",
    "bullet prático 2",
    "bullet prático 3"
  ]
}}

Regras gerais:
- keywords: 5-10 termos clínicos específicos em INGLÊS (ex: "heart failure", "SGLT2 inhibitors")
- Todos os outros campos em PORTUGUÊS
- tamanho_beneficio: apenas números reais do estudo, não estimativas
- bullets_praticos: máximo 5 bullets, cada um com 1 frase acionável

REGRA CRÍTICA para bullets_praticos — PRESCRIÇÃO CONCRETA:
Cada bullet deve ser específico o suficiente para o médico agir imediatamente.
Quando o estudo permitir, inclua obrigatoriamente:
  • Nome do fármaco/dispositivo/procedimento (nome genérico + comercial se relevante)
  • Dose, via e frequência (ex: "dapagliflozina 10 mg VO 1x/dia")
  • Critério de seleção do paciente (ex: "em pacientes com ICFEr FEVE<40%, já em uso de betabloqueador + IECA/BRA")
  • O que NÃO fazer, quando aplicável (ex: "não usar se TFGe < 25 mL/min/1,73m²")

Exemplos de bullet RUIM vs BOM:
  ✗ RUIM: "Considere SGLT2i em pacientes com insuficiência cardíaca"
  ✓ BOM: "Iniciar dapagliflozina 10 mg/dia em pacientes com ICFEr (FEVE ≤40%), mesmo sem DM2, independente do uso de diurético"

  ✗ RUIM: "Use estatina de alta potência após SCA"
  ✓ BOM: "Prescrever atorvastatina 80 mg/dia (ou rosuvastatina 40 mg/dia) na alta hospitalar pós-SCA, independente do LDL basal"

  ✗ RUIM: "Anticoagular pacientes com FA e risco elevado"
  ✓ BOM: "Iniciar apixabana 5 mg 2x/dia (ou 2,5 mg 2x/dia se ≥2 critérios de redução de dose) em FA não valvar com CHA₂DS₂-VASc ≥2 em homens ou ≥3 em mulheres"

Se o estudo não fornece dados suficientes para prescrição concreta (ex: artigo diagnóstico, epidemiológico, fisiopatológico), o bullet deve ser acionável na conduta, não na prescrição.
"""


def _chamar_gemini_flash(text: str) -> dict | None:
    """Chama Gemini 2.0 Flash para extrair campos do analysis.md."""
    if not GEMINI_KEY:
        print("❌ GEMINI_API_KEY não configurada")
        return None

    prompt = PROMPT_EXTRACAO.format(analysis_text=text[:15000])  # limite seguro

    try:
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=GEMINI_KEY)
        resp = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0.1, max_output_tokens=8000),
        )
        raw = resp.text.strip()
        # Remover markdown se presente
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw.strip())
    except Exception as e:
        print(f"   ❌ Gemini Flash erro: {e}")
        return None


def _processar_artigo(doc_id: str, dry_run: bool = False, salvar_supabase: bool = True) -> dict:
    """
    Lê analysis.md, extrai campos via LLM, retorna resultado.
    """
    md_path = CORPUS_DIR / doc_id / "analysis.md"
    if not md_path.exists():
        return {"doc_id": doc_id, "status": "sem_analysis_md"}

    analysis_text = md_path.read_text(errors="ignore")
    if len(analysis_text) < 1000:
        return {"doc_id": doc_id, "status": "analysis_md_vazio"}

    campos = _chamar_gemini_flash(analysis_text)
    if not campos:
        return {"doc_id": doc_id, "status": "erro_llm"}

    # Filtrar campos vazios/nulos
    campos_validos = {k: v for k, v in campos.items()
                      if v and (isinstance(v, list) and v or isinstance(v, str) and len(v.strip()) > 5)}

    resultado = {
        "doc_id": doc_id,
        "status": "ok",
        "campos_extraidos": list(campos_validos.keys()),
        "dados": campos_validos,
    }

    if not dry_run and salvar_supabase and campos_validos:
        ok = _patch_supabase(doc_id, campos_validos)
        resultado["supabase"] = "ok" if ok else "erro"

    return resultado


def _patch_supabase(doc_id: str, campos: dict) -> bool:
    r = requests.patch(
        f"{SUPABASE_URL}/rest/v1/artigos",
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        },
        params={"doc_id": f"eq.{doc_id}"},
        json=campos,
        timeout=20,
    )
    return r.status_code in (200, 204)


def _buscar_sem_contexto(nota_min: int, limit: int = 2000) -> list[str]:
    """Busca doc_ids com contexto_tema NULL e nota >= nota_min."""
    todos = []
    offset = 0
    while True:
        r = requests.get(f"{SUPABASE_URL}/rest/v1/artigos",
            headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"},
            params={
                "select": "doc_id",
                "nota_aplicabilidade": f"gte.{nota_min}",
                "contexto_tema": "is.null",
                "order": "nota_aplicabilidade.desc",
                "limit": "1000",
                "offset": str(offset),
            }, timeout=30)
        batch = r.json() if r.status_code == 200 else []
        if not batch: break
        todos.extend(a["doc_id"] for a in batch)
        offset += len(batch)
        if len(batch) < 1000 or len(todos) >= limit: break
    return [d for d in todos if (CORPUS_DIR / d / "analysis.md").exists()]


def _buscar_todos_com_md(nota_min: int, limit: int = 5000) -> list[str]:
    """Busca TODOS os doc_ids com nota >= nota_min que têm analysis.md local."""
    todos = []
    offset = 0
    while True:
        r = requests.get(f"{SUPABASE_URL}/rest/v1/artigos",
            headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"},
            params={
                "select": "doc_id",
                "nota_aplicabilidade": f"gte.{nota_min}",
                "order": "nota_aplicabilidade.desc",
                "limit": "1000",
                "offset": str(offset),
            }, timeout=30)
        batch = r.json() if r.status_code == 200 else []
        if not batch: break
        todos.extend(a["doc_id"] for a in batch)
        offset += len(batch)
        if len(batch) < 1000 or len(todos) >= limit: break
    return [d for d in todos if (CORPUS_DIR / d / "analysis.md").exists()]


def modo_teste():
    """
    Roda nos 11 artigos de teste e salva resultado para comparação manual.
    NÃO salva no Supabase — apenas gera arquivo de comparação.
    """
    print(f"\n{'='*60}")
    print("MODO TESTE — Extração de campos via Gemini 2.0 Flash")
    print("Artigos: 5 originais + 3 revisões + 3 meta-análises")
    print("Resultado: scripts/teste_extracao_resultado.json")
    print(f"{'='*60}\n")

    resultados = []
    for i, doc_id in enumerate(ARTIGOS_TESTE, 1):
        md_path = CORPUS_DIR / doc_id / "analysis.md"
        existe = md_path.exists()
        tamanho = md_path.stat().st_size // 1024 if existe else 0
        print(f"[{i:02d}/11] {doc_id} ({tamanho}KB)...")

        if not existe:
            print(f"       ⚠️  analysis.md não encontrado")
            resultados.append({"doc_id": doc_id, "status": "sem_analysis_md"})
            continue

        resultado = _processar_artigo(doc_id, dry_run=True, salvar_supabase=False)
        status = resultado.get("status")
        campos = resultado.get("campos_extraidos", [])
        print(f"       {'✅' if status == 'ok' else '❌'} {status} | campos: {campos}")
        resultados.append(resultado)
        time.sleep(0.5)  # respeitar rate limit

    # Salvar para comparação manual
    output = ROOT / "scripts" / "teste_extracao_resultado.json"
    output.write_text(json.dumps(resultados, ensure_ascii=False, indent=2), encoding="utf-8")

    ok = sum(1 for r in resultados if r.get("status") == "ok")
    print(f"\n{'='*60}")
    print(f"✅ {ok}/11 artigos extraídos com sucesso")
    print(f"📄 Resultado salvo em: scripts/teste_extracao_resultado.json")
    print(f"\nPróximo passo: revisar o JSON e comparar com sua avaliação manual.")
    print(f"{'='*60}\n")


def modo_producao(nota_min: int, dry_run: bool, workers: int, limite: int, force_bullets: bool = False):
    """Processa artigos nota>=nota_min sem contexto_tema (ou todos, se --force-bullets)."""
    print(f"\n{'='*60}")
    modo_label = "FORCE-BULLETS (reescrever todos)" if force_bullets else "Extração campos"
    print(f"PRODUÇÃO — {modo_label} | nota >= {nota_min} | {'DRY-RUN' if dry_run else 'REAL'}")
    print(f"Modelo: Gemini 2.5 Flash | Workers: {workers}")
    print(f"{'='*60}\n")

    if force_bullets:
        print("🔍 Buscando todos os artigos com analysis.md (--force-bullets)...")
        doc_ids = _buscar_todos_com_md(nota_min, limit=limite)
    else:
        print("🔍 Buscando artigos sem contexto_tema...")
        doc_ids = _buscar_sem_contexto(nota_min, limit=limite)
    print(f"   → {len(doc_ids)} artigos com analysis.md local\n")

    if not doc_ids:
        print("✅ Nenhum artigo pendente.")
        return

    ok = erros = sem_md = 0
    lock = threading.Lock()
    done = [0]
    t0 = time.time()

    def processar(doc_id):
        resultado = _processar_artigo(doc_id, dry_run=dry_run, salvar_supabase=not dry_run)
        # No modo force-bullets, filtrar payload para só atualizar bullets_praticos
        if force_bullets and resultado.get("status") == "ok" and not dry_run:
            bullets = resultado.get("dados", {}).get("bullets_praticos")
            if bullets:
                ok_patch = _patch_supabase(doc_id, {"bullets_praticos": bullets})
                resultado["supabase"] = "ok" if ok_patch else "erro"
            else:
                resultado["status"] = "sem_bullets"
        return resultado

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(processar, d): d for d in doc_ids}
        for fut in as_completed(futures):
            r = fut.result()
            with lock:
                done[0] += 1
                n = done[0]
                if r["status"] == "ok":
                    ok += 1
                elif r["status"] == "sem_analysis_md":
                    sem_md += 1
                else:
                    erros += 1
            if n % 50 == 0:
                elapsed = time.time() - t0
                print(f"  [{n}/{len(doc_ids)}] {ok} ok | {erros} erros | {elapsed/60:.1f}min")

    elapsed = time.time() - t0
    print(f"\n{'='*60}")
    print(f"✅ {ok} atualizados | {erros} erros | {sem_md} sem analysis.md")
    print(f"   Tempo: {elapsed:.0f}s | Custo estimado: ~US${ok*0.0001:.2f} (Gemini Flash)")
    print(f"{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(description="CardioDaily — Extração campos via LLM")
    parser.add_argument("--teste", action="store_true", help="Modo teste (11 artigos, sem salvar)")
    parser.add_argument("--nota-min", type=int, default=7)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--force-bullets", action="store_true",
                        help="Reescrever bullets_praticos de TODOS os artigos com novo prompt")
    parser.add_argument("--limite", type=int, default=2000)
    args = parser.parse_args()

    if not SUPABASE_URL or not SUPABASE_KEY:
        print("❌ SUPABASE_URL/SUPABASE_SERVICE_KEY não configurados")
        sys.exit(1)
    if not GEMINI_KEY:
        print("❌ GEMINI_API_KEY não configurada")
        sys.exit(1)

    if args.teste:
        modo_teste()
    else:
        modo_producao(args.nota_min, args.dry_run, args.workers, args.limite,
                      force_bullets=args.force_bullets)


if __name__ == "__main__":
    main()
