#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CardioDaily — Ingestão Automática de Artigos em PDF
Processa PDFs novos → extrai texto → analisa com GPT-4o → gera assets → insere Supabase.

Fluxo por artigo:
  PDF → extração texto → análise GPT-4o (NAC + estrutura) → insere artigos
      → [NAC ≥ 7] gera visual abstract PNG + PDF resumo + MP3 → atualiza artigos

Pastas:
  inputs/artigos_pdf/      ← coloque aqui os PDFs novos
  inputs/artigos_pdf/done/ ← PDFs processados são movidos aqui
  inputs/artigos_pdf/erro/ ← PDFs com falha ficam aqui

Uso:
  python scripts/ingerir_artigos.py              # processa todos os PDFs na fila
  python scripts/ingerir_artigos.py --dry-run    # só lista, não processa
  python scripts/ingerir_artigos.py --limite 3   # máximo 3 arquivos
  python scripts/ingerir_artigos.py --arquivo caminho.pdf  # arquivo específico
  python scripts/ingerir_artigos.py --sem-assets # insere no banco mas não gera PNG/MP3/PDF
"""

import argparse
import base64
import hashlib
import json
import os
import re
import shutil
import sys
import time
import requests
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime, date

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "src"))

try:
    from dotenv import load_dotenv
    load_dotenv(_ROOT / ".env")
except ImportError:
    pass

# ─── Config ───────────────────────────────────────────────────────────────────
SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY", "")
OPENAI_KEY   = os.getenv("OPENAI_API_KEY", "")

INPUT_DIR = _ROOT / "inputs" / "artigos_pdf"
DONE_DIR  = INPUT_DIR / "done"
ERRO_DIR  = INPUT_DIR / "erro"

# Revistas aceitas (palavras-chave no nome do arquivo ou metadados)
REVISTAS_ACEITAS = (
    "circulation", "jaha", "atvbaha", "circ", "heartfailure", "heartrhythm",
    "eurheartj", "ehj", "ehaf", "ehjcvi", "ehjqcco",
    "jacc", "jaccasi", "jaccrn",
    "jama", "jamacard",
    "nejm", "nejmoa",
    "lancet", "lanc",
    "bmj",
)

# ─── Supabase ─────────────────────────────────────────────────────────────────

def _sb_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }


def doc_id_de_doi(doi: str) -> str:
    """Gera doc_id determinístico a partir do DOI."""
    return "doi_" + hashlib.sha256(doi.encode()).hexdigest()[:16]


def doc_id_de_titulo(titulo: str) -> str:
    """Fallback: doc_id a partir do título quando DOI não está disponível."""
    return "titulo_" + hashlib.sha256(titulo.encode()).hexdigest()[:16]


def artigo_ja_existe(doc_id: str) -> bool:
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/artigos",
        headers=_sb_headers(),
        params={"select": "doc_id", "doc_id": f"eq.{doc_id}"},
        timeout=15,
    )
    return r.status_code == 200 and bool(r.json())


def inserir_artigo(payload: dict) -> bool:
    r = requests.post(
        f"{SUPABASE_URL}/rest/v1/artigos",
        headers={**_sb_headers(), "Prefer": "return=minimal,resolution=merge-duplicates"},
        json=payload,
        params={"on_conflict": "doc_id"},
        timeout=30,
    )
    return r.status_code in (200, 201, 204)


def atualizar_artigo(doc_id: str, campos: dict) -> bool:
    r = requests.patch(
        f"{SUPABASE_URL}/rest/v1/artigos?doc_id=eq.{doc_id}",
        headers={**_sb_headers(), "Prefer": "return=minimal"},
        json=campos,
        timeout=15,
    )
    return r.status_code in (200, 204)

# ─── Extração de texto PDF ────────────────────────────────────────────────────

def extrair_texto_pdf(pdf_path: Path) -> tuple[str, dict]:
    """
    Extrai texto e metadados do PDF.
    Retorna (texto_completo, meta_dict).
    meta_dict: {titulo, doi, revista, ano}
    """
    try:
        import fitz
    except ImportError:
        raise RuntimeError("PyMuPDF não instalado. Execute: pip install pymupdf")

    doc = fitz.open(str(pdf_path))
    meta_raw = doc.metadata or {}

    # Extrair texto de todas as páginas (max 20 pág para artigos longos)
    partes = []
    for i in range(min(20, len(doc))):
        partes.append(doc[i].get_text())
    texto = "\n".join(partes)

    # Renderizar primeiras páginas como imagem para visão (captura fluxogramas/gráficos)
    imagens_b64: list[str] = []
    for i in range(min(6, len(doc))):
        pix = doc[i].get_pixmap(dpi=100)
        imagens_b64.append(base64.b64encode(pix.tobytes("png")).decode())

    doc.close()

    # Tentar extrair DOI do texto (padrão: 10.XXXX/...)
    doi = ""
    doi_match = re.search(r'\b(10\.\d{4,}/[^\s"<>{}\[\]|\\^`]+)', texto)
    if doi_match:
        doi = doi_match.group(1).rstrip(".,;)")

    # Título dos metadados ou primeira linha significativa
    titulo = meta_raw.get("title", "").strip()
    if not titulo:
        # Tenta pegar a primeira linha longa do texto
        for linha in texto.splitlines():
            linha = linha.strip()
            if len(linha) > 30 and not linha.startswith("http") and not re.match(r'^\d', linha):
                titulo = linha[:200]
                break

    # Revista: inferir do DOI, nome do arquivo ou primeiras linhas do texto
    nome_arquivo = pdf_path.stem.lower()
    doi_lower = doi.lower()
    revista = ""

    # 1. DOI (mais confiável)
    if any(x in doi_lower for x in ("eurheartj", "ehaf", "ehjcvi", "ehjqcco")):
        revista = "European Heart Journal"
    elif any(x in doi_lower for x in ("circulationaha", "circresaha", "circep",
                                       "circimaging", "atvbaha", "heartfailureaha")):
        revista = "Circulation"
    elif any(x in doi_lower for x in ("jacc", "jacasi", "jaccrn", "jaccas")):
        revista = "JACC"
    elif "jamacard" in doi_lower:
        revista = "JAMA Cardiology"
    elif "jama" in doi_lower:
        revista = "JAMA"
    elif any(x in doi_lower for x in ("nejmoa", "nejmc", "nejm")):
        revista = "N Engl J Med"
    elif "lancet" in doi_lower:
        revista = "Lancet"
    elif "bmj" in doi_lower:
        revista = "BMJ"

    # 2. Nome do arquivo
    if not revista:
        for pat, nome in [
            ("ehaf", "European Heart Journal"), ("eurheartj", "European Heart Journal"),
            ("circ", "Circulation"), ("jacc", "JACC"), ("jama", "JAMA"),
            ("nejm", "N Engl J Med"), ("lancet", "Lancet"),
        ]:
            if pat in nome_arquivo:
                revista = nome
                break

    # 3. Primeiras linhas do texto
    if not revista:
        for linha in texto.splitlines()[:15]:
            for rev in ["European Heart Journal", "Circulation", "JACC",
                        "JAMA", "N Engl J Med", "Lancet", "Heart Rhythm"]:
                if rev in linha:
                    revista = rev
                    break
            if revista:
                break

    # Ano
    ano = ""
    ano_match = re.search(r'\b(202[0-9])\b', texto[:2000])
    if ano_match:
        ano = ano_match.group(1)

    return texto, {
        "titulo": titulo,
        "doi": doi,
        "revista": revista or "Revista Cardiológica",
        "ano": ano or str(date.today().year),
        "_imagens_b64": imagens_b64,   # páginas renderizadas para GPT-4o vision
    }

# ─── Análise GPT-4o ──────────────────────────────────────────────────────────

PROMPT_ANALISE = """Você é o Dr. Eduardo Castro, cardiologista sênior. Analise o artigo e retorne SOMENTE um JSON válido.
TODOS os valores em PORTUGUÊS BRASILEIRO.

MISSÃO: extrair aptidões para aplicabilidade clínica imediata. O médico vai usar isso amanhã no ambulatório.

Para ESTUDOS ORIGINAIS: foque em quem se beneficia, o resultado com números absolutos/relativos, e como aplicar.
Para REVISÕES e DIRETRIZES: foque no fluxo diagnóstico-terapêutico e nas recomendações práticas (Classe I/IIa).
Se houver fluxogramas ou gráficos nas imagens, use-os — eles frequentemente contêm a recomendação mais importante.

{
  "titulo": "Título direto e impactante (max 12 palavras)",
  "tagline": "Achado principal com número se possível (max 18 palavras)",
  "tipo_estudo": "original | revisao | metanalise | diretriz | caso_clinico | editorial",
  "especialidade": "Subespecialidade cardiológica",
  "doenca_principal": "Uma das: Coronariopatia Aguda | Coronariopatia Crônica | Insuficiencia Cardiaca | Arritmias | Valvulopatias | Miocardiopatias | Hipertensão Arterial Sistêmica | Dislipidemias | Cardio-Oncologia | Cardio-Obstetricia | Genética | Imagem Cardiovascular | Emergências/UTI | Aortopatias | Stroke | Cardiopatia Congênita | Prevenção Cardiovascular | Farmacologia | Outros",
  "nota_aplicabilidade": 0,
  "nota_metodologia": 0,
  "nota_geral": 0,
  "populacao": "Perfil do paciente: idade, FE, classificação funcional, comorbidades",
  "intervencao": "Fármaco/procedimento/estratégia específica com dose se disponível",
  "tipo_endpoint": "primário hard | primário surrogate | segurança | diagnóstico | prognóstico",
  "revista_ano": "Ex: European Heart Journal 2026",
  "pergunta_clinica": ["O que o estudo quis responder na prática clínica"],
  "metodos": ["Tipo de estudo e N de pacientes", "Seguimento", "Intervenção vs controle", "Desfecho primário com resultado"],
  "populacao_bullets": ["Critério de inclusão que define quem se beneficia", "Características demográficas-chave", "Comorbidades relevantes"],
  "resultados": ["Resultado primário: número relativo E número absoluto ou NNT", "Resultado secundário relevante", "Achado de segurança"],
  "vieses": ["Limitação que restringe a aplicabilidade ao seu paciente", "Outro ponto de atenção"],
  "pontos_fortes": ["Por que dá para confiar no resultado", "Força do desenho", "Relevância do desfecho"],
  "pontos_fracos": ["Por que pode não se aplicar", "Limitação prática importante"],
  "discussao": ["O que muda na prática a partir de agora", "Em quem NÃO aplicar", "Lacuna que ainda precisa ser respondida"],
  "conclusao": ["O que fazer diferente na próxima consulta", "Impacto esperado no desfecho do paciente"],
  "o_que_usar": "Nome específico do fármaco/procedimento + dose se relevante (ex: dapagliflozina 10mg/dia)",
  "em_quem": "Perfil exato: FE, classe NYHA, escore, comorbidade que define a indicação",
  "o_que_paciente_ganha": "Benefício concreto com número (ex: redução de 22% em hospitalização por IC)",
  "cuidados": "Contraindicação ou condição que modifica a conduta",
  "perola": "Frase de ouro que começa com verbo de ação, para usar no ambulatório amanhã (max 18 palavras)",
  "palavras_chave": ["kw1", "kw2", "kw3", "kw4", "kw5"]
}

CRITÉRIOS DE NOTA (1-10):
- nota_aplicabilidade: impacto prático imediato no dia a dia do cardiologista
- nota_metodologia: rigor científico, N amostral, endpoints relevantes
- nota_geral: combinação

REGRAS:
- Listas: 2-4 itens, max 15 palavras cada
- perola DEVE começar com verbo (ex: "Prescreva", "Inclua", "Considere", "Evite")
- o_que_usar NUNCA genérico — nome do fármaco ou procedimento específico
- Sem markdown, asteriscos ou emojis no JSON
- Retorne APENAS o JSON
"""


def analisar_com_gpt4o(texto: str, meta: dict) -> dict | None:
    from openai import OpenAI
    client = OpenAI(api_key=OPENAI_KEY)

    entrada_texto = (
        f"REVISTA: {meta.get('revista','')}\n"
        f"ANO: {meta.get('ano','')}\n"
        f"DOI: {meta.get('doi','')}\n\n"
        f"TEXTO DO ARTIGO (primeiras páginas):\n{texto[:8000]}"
    )

    # Monta conteúdo multimodal: imagens das páginas + texto
    # As imagens permitem capturar fluxogramas e gráficos de revisões/diretrizes
    imagens_b64 = meta.get("_imagens_b64", [])
    content: list[dict] = []
    for img in imagens_b64[:5]:   # max 5 páginas, detail=low → ~85 tokens cada
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{img}", "detail": "low"},
        })
    content.append({"type": "text", "text": entrada_texto})

    try:
        resp = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": PROMPT_ANALISE},
                {"role": "user",   "content": content},
            ],
            temperature=0.2,
            max_tokens=3000,
            response_format={"type": "json_object"},
        )
        return json.loads(resp.choices[0].message.content)
    except Exception as e:
        print(f"   ❌ GPT-4o: {e}")
        return None

# ─── Geração de assets ────────────────────────────────────────────────────────

PROMPT_PODCAST_ORIGINAL = """Você é o Dr. Eduardo Castro, cardiologista. Crie um SCRIPT DE PODCAST de exatamente 90 segundos (≈ 220 palavras).

REGRA ABSOLUTA: vá direto à conduta. Zero contexto histórico, zero explicação de por que o estudo foi feito.
O médico tem 90 segundos. Cada palavra tem que valer.

ESTRUTURA OBRIGATÓRIA:
1. ABERTURA (10s): "Saiu [tipo de estudo] em [revista] sobre [assunto]." — só isso, sem rodeios.
2. PACIENTE-ALVO (15s): Quem se beneficia? Perfil exato: FE, classe funcional, escore, comorbidades.
3. RESULTADO-CHAVE (20s): [Intervenção] reduziu/aumentou [desfecho] em [número concreto]. NNT se disponível.
4. COMO USAR (35s): Na sua consulta: [ação 1]. Se [condição] → [ação 2]. Dose ou estratégia específica.
5. PÉROLA (10s): Uma frase que o médico vai lembrar no ambulatório amanhã.

PROIBIDO: abrir com contexto histórico, mencionar limitações antes dos resultados, gastar tempo explicando por que o estudo foi conduzido, qualquer frase que não leve à ação.
Tom: colega cardiologista passando informação no corredor.
Sem markdown. Máximo 220 palavras."""

PROMPT_PODCAST_REVISAO = """Você é o Dr. Eduardo Castro, cardiologista. Crie um SCRIPT DE PODCAST de exatamente 90 segundos (≈ 220 palavras).

ESTE É UM ARTIGO DE REVISÃO OU DIRETRIZ. O objetivo é extrair aptidões para aplicabilidade prática, da introdução à conclusão.
Cada linha do artigo foi escrita para guiar conduta — é isso que você vai entregar.

ESTRUTURA OBRIGATÓRIA:
1. ABERTURA (10s): "Nova [diretriz/revisão] de [tema] — o que você precisa aplicar agora."
2. QUEM TRATAR (20s): Critério de seleção do paciente. Classificação, escore, achado clínico que define quem entra.
3. COMO INVESTIGAR (20s): Fluxo em 2-3 passos. Se [achado] → [próxima ação]. Exame que define a decisão.
4. COMO TRATAR (30s): Primeira linha. Quando escalar. O que vigiar. Dose se relevante.
5. PÉROLA (10s): Uma recomendação Classe I que o médico vai aplicar na próxima consulta.

PROIBIDO: contexto histórico, discussão sobre metodologia da revisão, comparação com diretrizes anteriores, qualquer frase que não resulte em ação clínica.
Tom: colega cardiologista passando informação no corredor.
Sem markdown. Máximo 220 palavras."""


def gerar_script_podcast(analise: dict, texto_pdf: str) -> str:
    """Gera script de podcast 90s focado em conduta clínica prática."""
    from openai import OpenAI
    client = OpenAI(api_key=OPENAI_KEY)

    tipo = (analise.get("tipo_estudo") or "original").lower()
    é_revisao = tipo in ("revisao", "diretriz", "guideline", "revisao_geral", "revisão")
    prompt_sistema = PROMPT_PODCAST_REVISAO if é_revisao else PROMPT_PODCAST_ORIGINAL

    # Alimenta o modelo com os campos práticos — não com metodologia
    campos = {
        "titulo":               analise.get("titulo"),
        "tipo_estudo":          analise.get("tipo_estudo"),
        "doenca_principal":     analise.get("doenca_principal"),
        "revista_ano":          analise.get("revista_ano"),
        "em_quem":              analise.get("em_quem"),
        "o_que_usar":           analise.get("o_que_usar"),
        "o_que_paciente_ganha": analise.get("o_que_paciente_ganha"),
        "cuidados":             analise.get("cuidados"),
        "perola":               analise.get("perola"),
        "resultados":           analise.get("resultados"),
        "conclusao":            analise.get("conclusao"),
        "populacao_bullets":    analise.get("populacao_bullets"),
        "discussao":            analise.get("discussao"),
    }
    entrada = json.dumps(campos, ensure_ascii=False, indent=2)

    resp = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": prompt_sistema},
            {"role": "user",   "content": entrada},
        ],
        temperature=0.3,
        max_tokens=500,
    )
    return resp.choices[0].message.content


def gerar_mp3(script: str, mp3_path: Path) -> bool:
    """TTS via OpenAI."""
    headers = {
        "Authorization": f"Bearer {OPENAI_KEY}",
        "Content-Type": "application/json",
    }
    max_chars = 4000
    chunks = []
    if len(script) <= max_chars:
        chunks = [script]
    else:
        paragrafos = script.split("\n\n")
        atual = ""
        for p in paragrafos:
            p = p.strip()
            if not p:
                continue
            if len(atual) + len(p) + 2 <= max_chars:
                atual = (atual + "\n\n" + p).strip()
            else:
                if atual:
                    chunks.append(atual)
                atual = p
        if atual:
            chunks.append(atual)

    all_bytes = []
    for chunk in chunks:
        r = requests.post(
            "https://api.openai.com/v1/audio/speech",
            headers=headers,
            json={"model": "tts-1-hd", "input": chunk, "voice": "onyx",
                  "response_format": "mp3", "speed": 1.0},
            timeout=300,
        )
        if r.status_code != 200:
            print(f"   ❌ TTS: HTTP {r.status_code}")
            return False
        all_bytes.append(r.content)

    mp3_path.parent.mkdir(parents=True, exist_ok=True)
    with open(mp3_path, "wb") as f:
        for b in all_bytes:
            f.write(b)
    return True


def upload_arquivo(doc_id: str, file_path: Path, bucket: str, content_type: str) -> str | None:
    ext = file_path.suffix
    objeto = f"{doc_id}{ext}"
    url_upload  = f"{SUPABASE_URL}/storage/v1/object/{bucket}/{objeto}"
    url_publica = f"{SUPABASE_URL}/storage/v1/object/public/{bucket}/{objeto}"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": content_type,
        "x-upsert": "true",
    }
    with open(file_path, "rb") as f:
        r = requests.post(url_upload, headers=headers, data=f, timeout=180)
    return url_publica if r.status_code in (200, 201) else None


def gerar_visual_abstract_png(analise: dict, doc_id: str, nota: int, png_path: Path) -> bool:
    """Reutiliza lógica do gerar_imagens_lote."""
    try:
        # Import das funções do outro script
        sys.path.insert(0, str(_ROOT / "scripts"))
        from gerar_imagens_lote import montar_html, gerar_png
        html = montar_html(analise, nota)
        return gerar_png(html, png_path)
    except Exception as e:
        print(f"   ❌ Visual abstract: {e}")
        return False


def gerar_pdf_resumo(analise: dict, doc_id: str, nota: int, pdf_path: Path) -> bool:
    """Reutiliza lógica do gerar_pdfs_lote."""
    try:
        sys.path.insert(0, str(_ROOT / "scripts"))
        from gerar_pdfs_lote import conteudo_para_html, gerar_pdf_playwright
        titulo = analise.get("titulo", doc_id)
        data   = str(date.today())
        script_txt = (
            analise.get("perola", "") + "\n\n" +
            "\n".join(analise.get("resultados", [])) + "\n\n" +
            "\n".join(analise.get("discussao", [])) + "\n\n" +
            "\n".join(analise.get("conclusao", []))
        )
        return gerar_pdf_playwright(doc_id, pdf_path, script_txt, titulo, nota, data)
    except Exception as e:
        print(f"   ❌ PDF resumo: {e}")
        return False

# ─── Processador principal ────────────────────────────────────────────────────

def processar_pdf(pdf_path: Path, dry_run: bool, gerar_assets: bool) -> str:
    """
    Processa um PDF completo.
    Retorna: 'ok' | 'duplicado' | 'erro_extracao' | 'erro_analise' | 'erro_supabase'
    """
    print(f"\n{'─'*60}")
    print(f"📄 {pdf_path.name}")

    # ── 1. Extrair texto ──────────────────────────────────────────────
    print("   📑 Extraindo texto do PDF…")
    try:
        texto, meta = extrair_texto_pdf(pdf_path)
    except Exception as e:
        print(f"   ❌ Extração falhou: {e}")
        return "erro_extracao"

    if len(texto) < 500:
        print(f"   ⚠️  PDF com conteúdo insuficiente ({len(texto)} chars) — pulando")
        return "erro_extracao"

    doi    = meta["doi"]
    titulo = meta["titulo"]
    print(f"   📌 DOI: {doi or '(não encontrado)'}")
    print(f"   📌 Título: {titulo[:70]}")
    print(f"   📌 Revista: {meta['revista']} {meta['ano']}")
    print(f"   📑 Texto: {len(texto):,} chars em {min(20, len(texto)//800)} páginas")

    # ── 2. doc_id ─────────────────────────────────────────────────────
    doc_id = doc_id_de_doi(doi) if doi else doc_id_de_titulo(titulo)
    print(f"   🔑 doc_id: {doc_id}")

    if dry_run:
        print("   [dry-run] — parando aqui")
        return "dry_run"

    # ── 3. Verificar duplicata ────────────────────────────────────────
    if artigo_ja_existe(doc_id):
        print(f"   ♻️  Já existe no Supabase — pulando")
        return "duplicado"

    # ── 4. Análise GPT-4o ─────────────────────────────────────────────
    print("   🤖 Analisando com GPT-4o…")
    analise = analisar_com_gpt4o(texto, meta)
    if not analise:
        return "erro_analise"

    nota = analise.get("nota_aplicabilidade") or 0
    print(f"   ✅ NAC: {nota}/10 | Tipo: {analise.get('tipo_estudo')} | Doença: {analise.get('doenca_principal')}")
    print(f"   📌 Pérola: {analise.get('perola','')[:80]}")

    # ── 5. Inserir no Supabase ────────────────────────────────────────
    payload = {
        "doc_id":              doc_id,
        "doi":                 doi or None,
        "titulo":              analise.get("titulo") or titulo,
        "revista":             meta["revista"],
        "data_publicacao":     f"{meta['ano']}-01-01",
        "tipo_estudo":         analise.get("tipo_estudo", "original"),
        "doenca_principal":    analise.get("doenca_principal", "Outros"),
        "nota_metodologia":    analise.get("nota_metodologia"),
        "nota_aplicabilidade": nota,
        "nota_geral":          analise.get("nota_geral"),
        "generator":           "ingerir_artigos.py",
        "generator_version":   "1.0",
        "analysis_datetime":   datetime.now().isoformat(),
    }

    print("   💾 Inserindo no Supabase…")
    if not inserir_artigo(payload):
        print("   ❌ Falha ao inserir no Supabase")
        return "erro_supabase"
    print("   ✅ Artigo inserido")

    # ── 6. Salvar análise local ───────────────────────────────────────
    corpus_dir = _ROOT / "outputs" / "corpus" / doc_id
    corpus_dir.mkdir(parents=True, exist_ok=True)
    (corpus_dir / "analise_estruturada.json").write_text(
        json.dumps(analise, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # ── 7. Gerar assets (se NAC ≥ 7 e não --sem-assets) ──────────────
    if gerar_assets and nota >= 7:
        print(f"\n   🎨 NAC={nota} ≥ 7 — gerando assets…")
        campos_update = {}

        # Visual abstract
        print("   🖼️  Visual abstract…")
        png_path = _ROOT / "outputs" / "imagens_lote" / f"{doc_id}.png"
        # Garante que listas são listas (GPT às vezes retorna string)
        def _to_list(v):
            if isinstance(v, list): return v
            if isinstance(v, str) and v.strip(): return [v]
            return []
        analise_img = {**analise,
                       "populacao_bullets": _to_list(analise.get("populacao_bullets") or analise.get("populacao")),
                       "metodos": _to_list(analise.get("metodos")),
                       "resultados": _to_list(analise.get("resultados")),
                       "vieses": _to_list(analise.get("vieses")),
                       "pontos_fortes": _to_list(analise.get("pontos_fortes")),
                       "pontos_fracos": _to_list(analise.get("pontos_fracos")),
                       "discussao": _to_list(analise.get("discussao")),
                       "conclusao": _to_list(analise.get("conclusao")),
                       "pergunta_clinica": _to_list(analise.get("pergunta_clinica")),}
        if gerar_visual_abstract_png(analise_img, doc_id, nota, png_path):
            url_img = upload_arquivo(doc_id, png_path, "visual_abstracts", "image/png")
            if url_img:
                campos_update["caminho_visual_abstract"] = url_img
                print(f"   ✅ VA: {url_img.split('/')[-1]}")

        # Script + MP3
        print("   🎙️  Gerando script + MP3…")
        try:
            script = gerar_script_podcast(analise, texto)
            script_path = _ROOT / "outputs" / "audio_lote" / f"{doc_id}_script.txt"
            script_path.parent.mkdir(parents=True, exist_ok=True)
            script_path.write_text(script, encoding="utf-8")

            mp3_path = _ROOT / "outputs" / "audio_lote" / f"{doc_id}.mp3"
            if gerar_mp3(script, mp3_path):
                url_mp3 = upload_arquivo(doc_id, mp3_path, "podcasts", "audio/mpeg")
                if url_mp3:
                    campos_update["caminho_audio"] = url_mp3
                    print(f"   ✅ MP3: {mp3_path.stat().st_size // 1024} KB")
        except Exception as e:
            print(f"   ⚠️  MP3: {e}")

        # PDF resumo
        print("   📄 PDF resumo…")
        pdf_resumo_path = _ROOT / "outputs" / "pdfs_lote" / f"{doc_id}.pdf"
        if gerar_pdf_resumo(analise, doc_id, nota, pdf_resumo_path):
            url_pdf = upload_arquivo(doc_id, pdf_resumo_path, "resumos_pdf", "application/pdf")
            if url_pdf:
                campos_update["caminho_pdf"] = url_pdf
                print(f"   ✅ PDF: {pdf_resumo_path.stat().st_size // 1024} KB")

        # Atualiza Supabase com todos os caminhos
        if campos_update:
            atualizar_artigo(doc_id, campos_update)
            print(f"   🗄️  {len(campos_update)} asset(s) atualizados no Supabase")

    elif nota < 7:
        print(f"   ℹ️  NAC={nota} < 7 — assets não gerados (abaixo do limiar)")

    return "ok"

# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="CardioDaily — Ingestão de Artigos em PDF")
    parser.add_argument("--dry-run",    action="store_true", help="Só lista, não processa")
    parser.add_argument("--limite",     type=int, default=50)
    parser.add_argument("--arquivo",    type=str, default=None, help="PDF específico")
    parser.add_argument("--sem-assets", action="store_true",
                        help="Insere no banco mas não gera visual/MP3/PDF")
    args = parser.parse_args()

    gerar_assets = not args.sem_assets

    if not SUPABASE_URL or not SUPABASE_KEY:
        print("❌ SUPABASE_URL / SUPABASE_SERVICE_KEY não configurados")
        sys.exit(1)
    if not OPENAI_KEY:
        print("❌ OPENAI_API_KEY não configurada")
        sys.exit(1)

    print(f"\n{'='*60}")
    print(f"📥 CardioDaily — Ingestão Automática de Artigos")
    print(f"   📅 {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    print(f"   {'[DRY-RUN]' if args.dry_run else 'MODO REAL'}")
    print(f"   Assets: {'SIM (NAC ≥ 7)' if gerar_assets else 'NÃO (--sem-assets)'}")
    print(f"{'='*60}\n")

    # Resolver lista de PDFs
    if args.arquivo:
        pdfs = [Path(args.arquivo)]
        if not pdfs[0].exists():
            print(f"❌ Arquivo não encontrado: {args.arquivo}")
            sys.exit(1)
    else:
        INPUT_DIR.mkdir(parents=True, exist_ok=True)
        DONE_DIR.mkdir(parents=True, exist_ok=True)
        ERRO_DIR.mkdir(parents=True, exist_ok=True)
        pdfs = sorted(INPUT_DIR.glob("*.pdf"))[:args.limite]

    if not pdfs:
        print(f"✅ Nenhum PDF em {INPUT_DIR}")
        print(f"   Coloque PDFs em: {INPUT_DIR}")
        return

    print(f"📂 PDFs encontrados: {len(pdfs)}")
    for p in pdfs:
        print(f"   • {p.name}")
    print()

    stats = {"ok": 0, "duplicado": 0, "dry_run": 0,
             "erro_extracao": 0, "erro_analise": 0, "erro_supabase": 0}

    for i, pdf in enumerate(pdfs, 1):
        print(f"\n[{i}/{len(pdfs)}]")
        status = processar_pdf(pdf, dry_run=args.dry_run, gerar_assets=gerar_assets)
        stats[status] = stats.get(status, 0) + 1

        # Mover arquivo após processamento
        if not args.dry_run and args.arquivo is None:
            if status == "ok":
                shutil.move(str(pdf), str(DONE_DIR / pdf.name))
                print(f"   📁 Movido → done/")
            elif status not in ("duplicado",):
                shutil.move(str(pdf), str(ERRO_DIR / pdf.name))
                print(f"   📁 Movido → erro/")

        if i < len(pdfs):
            time.sleep(2)  # evitar rate limit

    print(f"\n\n{'='*60}")
    print(f"✅ INGESTÃO CONCLUÍDA")
    print(f"   ✅ Novos artigos processados: {stats['ok']}")
    print(f"   ♻️  Duplicatas ignoradas:     {stats['duplicado']}")
    print(f"   ❌ Erro extração PDF:         {stats['erro_extracao']}")
    print(f"   ❌ Erro análise GPT-4o:       {stats['erro_analise']}")
    print(f"   ❌ Erro Supabase:             {stats['erro_supabase']}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
