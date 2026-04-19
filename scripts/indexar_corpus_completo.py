#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os, sys, json, re, requests
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from tqdm import tqdm
import anthropic

# Adicionar src/ ao path para importar taxonomy.py
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))
from taxonomy import (TAXONOMY_CATEGORIES, TAXONOMY_SET as _TAXONOMY_SET, PROMPT_CLASSIFICATION,
                        migrate_legacy_category as _migrate_legacy_category,
                        validate_category as _validate_category)

load_dotenv("/Users/edcastro77/CardioDaily_FULL/.env")
CORPUS_DIR = "/Users/edcastro77/CardioDaily_FULL/outputs/corpus"
LOG_FILE = "/Users/edcastro77/CardioDaily_FULL/logs/indexacao.log"
CHECKPOINT_FILE = "/Users/edcastro77/CardioDaily_FULL/data/checkpoint.txt"
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY")

if not all([SUPABASE_URL, SUPABASE_KEY, ANTHROPIC_KEY]):
    print("❌ Credenciais faltando")
    exit(1)

claude = anthropic.Anthropic(api_key=ANTHROPIC_KEY)

def log(msg):
    timestamp = datetime.now().strftime("%H:%M:%S")
    full_msg = f"[{timestamp}] {msg}"
    print(full_msg)
    Path(LOG_FILE).parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(full_msg + "\n")

def load_checkpoint():
    if Path(CHECKPOINT_FILE).exists():
        with open(CHECKPOINT_FILE, "r") as f:
            return set(line.strip() for line in f)
    return set()

def save_checkpoint(doc_id):
    Path(CHECKPOINT_FILE).parent.mkdir(parents=True, exist_ok=True)
    with open(CHECKPOINT_FILE, "a") as f:
        f.write(f"{doc_id}\n")

def _parse_date_from_filename(pdf_filename):
    """Extrai ano, revista e data de um filename no padrão YYYY-MM-JOURNAL-Title.
    Retorna (revista, data_pub) ou (None, None) se o formato não for válido."""
    parts = pdf_filename.split("-")
    year  = parts[0] if len(parts) >= 1 and parts[0].isdigit() and len(parts[0]) == 4 else None
    month = parts[1] if len(parts) >= 2 and parts[1].isdigit() and 1 <= int(parts[1]) <= 12 else None
    revista  = parts[2] if len(parts) >= 3 and year and month else None
    data_pub = f"{year}-{month.zfill(2)}-01" if year and month else None
    return revista, data_pub


def _extract_journal_date_from_md(md_content: str) -> tuple[str | None, str | None]:
    """
    Extrai revista e ano da referência Vancouver no analysis.md.
    Fallback para PDFs com nomes genéricos (sem padrão YYYY-MM-JOURNAL no filename).

    Padrão Vancouver: Authors. Title. JournalName. YYYY;Vol(Issue):Pages.
    Ex: "Kang J, et al. ... Lancet. 2026;407(10539):1439-1447."
    """
    # Procura padrão: <Algo>. <YYYY>;<volume>
    # O grupo antes do ano é o nome da revista
    m = re.search(
        r'\.\s+([A-Z][A-Za-z\s\(\)&/\-]+?)\.\s+(\d{4});\d+',
        md_content
    )
    if m:
        journal_raw = m.group(1).strip()
        year = m.group(2)
        # Normalizar usando o mapa existente (importado via journal_utils)
        import sys, os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
        try:
            from journal_utils import JOURNAL_NORMALIZE
            journal = JOURNAL_NORMALIZE.get(journal_raw, journal_raw)
        except ImportError:
            journal = journal_raw
        return journal, f"{year}-01-01"
    return None, None


def _titulo_parece_filename(titulo: str, pdf_filename: str) -> bool:
    """Retorna True se o título é não-vazio mas parece ser o nome do arquivo."""
    if not titulo:
        return False  # vazio já é tratado pelo fallback normal (or _extract_titulo)
    stem = re.sub(r'\.pdf$', '', pdf_filename, flags=re.IGNORECASE).lower()
    # É exatamente o nome do arquivo (ex: "host-exam" para "host-exam.pdf")
    if titulo.lower() == stem:
        return True
    # Sem espaços e curto — claramente não é um título real (ex: "host-exam", "NEJM2026")
    if ' ' not in titulo and len(titulo) < 40 and titulo.lower() != titulo.upper():
        return True
    return False

def _normalize_date(d) -> str | None:
    """Normaliza qualquer formato de data para YYYY-MM-DD (exigido pelo Supabase).
    '2026-03'   → '2026-03-01'
    '2026'      → '2026-01-01'
    '2026-03-05'→ '2026-03-05' (inalterado)
    """
    if not d:
        return None
    d = str(d).strip()
    if re.match(r'^\d{4}-\d{2}-\d{2}$', d):
        return d
    if re.match(r'^\d{4}-\d{2}$', d):
        return d + "-01"
    if re.match(r'^\d{4}$', d):
        return d + "-01-01"
    return None

_SKIP_HEADING = re.compile(
    r'^(Análise|Analysis|Contextualiz|Descrição|Principais|Interpretação|'
    r'Discussão|Conclusão|Take.Home|ETAPA|Resumo|BLOCO|Ficha|Seção|'
    r'Introdução|Background|Methods|Results|Contribuição|Limitaç|'
    r'Pontos|Perspectiv|Implicaç|Script|Pérola|Dados|Study|Clinical|'
    r'Nota\s+de\s+Aplicabilidade|Classificação|Endpoint|Justificativa|'
    r'Material\s+de|Observaç|Valor(es)?\s+de\s+Ref|A\d+\s*[—–-])',
    re.IGNORECASE)


def _extract_titulo_from_md(md_content: str) -> str | None:
    """
    Extrai o título real do artigo no analysis.md.
    Prioridade 1: tabela Markdown  | **Título** | ... |
    Prioridade 2: heading # logo após frontmatter (formato antigo)
    """
    # 1. Tabela Markdown (formato novo): | **Título** | Título real |
    for pattern in [
        r'\|\s*\*\*Título(?:\s+do\s+artigo)?\*\*\s*\|\s*(.+?)\s*\|',
        r'\|\s*Título(?:\s+do\s+artigo)?\s*\|\s*(.+?)\s*\|',
    ]:
        m = re.search(pattern, md_content, re.IGNORECASE)
        if m:
            t = m.group(1).strip()
            # Descartar se for placeholder ou muito curto
            if len(t) > 10 and len(t.split()) >= 3 and not re.match(r'^[\-\?]+$', t):
                return t[:300]

    # 2. Heading # real (formato antigo): título aparece como heading H1 antes das seções
    _ANALISE_PREFIX = re.compile(
        r'^ANÁLISE\s+CRÍTICA(?:\s+DE\s+[\w\s]+?)?\s*[:\-–—]\s*',
        re.IGNORECASE
    )
    for match in re.finditer(r'^#+\s+(.+)$', md_content, re.MULTILINE):
        c = match.group(1).strip()
        c = re.sub(r'^[^\w\s]*\s*', '', c).strip()
        c = re.sub(r'^(Análise|Analysis)\s*:\s*', '', c, flags=re.IGNORECASE).strip()
        c = re.sub(r'\.pdf\s*$', '', c, flags=re.IGNORECASE).strip()

        # Formato legado: "ANÁLISE CRÍTICA: Título real" — extrai a parte após o prefixo
        m_pref = _ANALISE_PREFIX.match(c)
        if m_pref:
            c = c[m_pref.end():].strip()

        if not c or _SKIP_HEADING.match(c):
            continue
        if re.match(r'^\d{4}-\d{2}', c):
            continue
        if '_' in c and '-' in c:
            continue
        if c.endswith(':'):
            continue
        # Descartar ALL-CAPS puro (seções de análise)
        alpha = [ch for ch in c if ch.isalpha()]
        if alpha and sum(ch.isupper() for ch in alpha) / len(alpha) > 0.75:
            continue
        if len(c.split()) >= 3:
            return c[:300]

    return None


def _extract_titulo(md_content, pdf_filename):
    """Extrai título do MD ou cai no filename como último recurso."""
    t = _extract_titulo_from_md(md_content)
    if t:
        return t
    # Fallback: extrair do filename (palavras após journal)
    parts = pdf_filename.replace(".pdf", "").split("-")
    if len(parts) >= 4:
        return " ".join(parts[3:]).replace("_", " ")[:300]
    return None

def extract_metadata(folder):
    json_path = folder / "analysis.json"
    md_path   = folder / "analysis.md"
    if not json_path.exists() or not md_path.exists():
        return None
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Nota de aplicabilidade — pré-requisito mínimo
        scores    = data.get("analysis", {}).get("scores", {})
        nota_geral = scores.get("aplicabilidade") or scores.get("overall")
        if nota_geral is None or nota_geral < 5:
            return None

        with open(md_path, "r", encoding="utf-8") as f:
            md_content = f.read()

        pdf_filename          = data.get("source", {}).get("pdf_filename", "")
        revista, data_pub_fn  = _parse_date_from_filename(pdf_filename)

        # Fallback: extrair revista e ano da referência Vancouver no MD
        # (para PDFs com nomes genéricos sem padrão YYYY-MM-JOURNAL)
        if not revista or not data_pub_fn:
            revista_md, data_pub_md = _extract_journal_date_from_md(md_content)
            revista    = revista    or revista_md
            data_pub_fn = data_pub_fn or data_pub_md

        # Preferir publication_date do analysis.json; fallback ao filename/MD
        data_pub = _normalize_date(
            data.get("source", {}).get("publication_date") or data_pub_fn
        )

        # Título: se o JSON tiver um filename stem (sem espaços), preferir o MD
        titulo_json = data.get("source", {}).get("titulo") or ""
        if _titulo_parece_filename(titulo_json, pdf_filename):
            titulo = _extract_titulo(md_content, pdf_filename) or titulo_json
        else:
            titulo = titulo_json

        classificacao    = data.get("classification", {})

        # Ler doenca_principal / palavras_chave / populacao / intervencao do JSON
        doenca_principal = classificacao.get("doenca_principal")
        palavras_chave   = classificacao.get("palavras_chave") or []
        populacao        = classificacao.get("populacao") or []
        intervencao      = classificacao.get("intervencao") or []

        # Migrar categoria legada (73 inglês → 25 PT-BR) sem chamar Claude
        if doenca_principal:
            doenca_principal = _migrate_legacy_category(doenca_principal) or doenca_principal

        # Validar contra a taxonomia nova
        if doenca_principal and doenca_principal not in _TAXONOMY_SET:
            doenca_principal = None  # forçar fallback Claude abaixo

        # Visual abstract: construir URL pública se o PNG existir localmente
        supabase_url = os.environ.get("SUPABASE_URL", "").rstrip("/")
        doc_id_val = data.get("doc_id", "")
        va_png = folder / "assets" / "visual_abstract.png"
        caminho_va = None
        if va_png.exists() and supabase_url and doc_id_val:
            caminho_va = f"{supabase_url}/storage/v1/object/public/visual_abstracts/{doc_id_val}.png"

        return {
            "doc_id":                   data.get("doc_id"),
            "doi":                      data.get("source", {}).get("doi"),
            "titulo":                   titulo,
            "revista":                  revista,
            "data_publicacao":          data_pub,
            "tipo_estudo":              classificacao.get("type"),
            "nota_geral":               nota_geral,
            "doenca_principal":         doenca_principal,
            "palavras_chave":           palavras_chave,
            "populacao":                populacao,
            "intervencao":              intervencao,
            "caminho_visual_abstract":  caminho_va,
            # resumo_md só enviado ao Claude se doenca_principal estiver faltando
            "_resumo_md":               md_content[:2500] if not doenca_principal else None,
            "caminho_pasta":            str(folder),
        }
    except Exception as e:
        log(f"❌ {folder.name}: {str(e)}")
        return None

def extrair_tags_claude(resumo_md, doc_id):
    """Chamado APENAS como fallback quando doenca_principal não está no analysis.json."""
    categories_str = ", ".join(TAXONOMY_CATEGORIES)
    prompt = f"""Você é um cardiologista especialista classificando literatura médica para
estudo de prova de título de especialista em Cardiologia (SBC/AMB).

TAREFA:
Analise o artigo e retorne:
1. A categoria principal (1 das 25 abaixo)
2. Até 3 palavras-chave clínicas específicas (termos técnicos precisos)

CATEGORIAS VÁLIDAS:
{categories_str}

REGRAS DE CLASSIFICAÇÃO:
- Stroke / AVC / oclusão de artéria basilar / trombectomia mecânica → "Stroke"
- Insuficiência cardíaca (HFrEF, HFpEF, HFmrEF, IC avançada) → "Insuficiencia Cardiaca"
- FA, flutter, TSV, TV, morte súbita → "Arritmias"
- IAM, STEMI, NSTEMI, SCA → "Coronariopatia Aguda"
- DAC estável, angina crônica → "Coronariopatia Crônica"
- TAVI, TEER, MitraClip, PCI, CABG, intervenção periférica → "Intervenção Vascular"
- Estenose aórtica, regurgitação mitral/tricúspide, endocardite, prótese → "Valvulopatias"
- Aneurisma de aorta, dissecção aórtica → "Aortopatias"
- CMH, MCD, amiloidose, miocardite, sarcoidose → "Miocardiopatias"
- Estatinas, PCSK9, LDL → "Dislipidemias"
- SGLT2, GLP-1, anticoagulantes, antiplaquetários → "Farmacologia"
- Gestação, periparto, SCAD, pré-eclâmpsia → "Cardio-Obstetricia"
- Cardiotoxicidade, imunoterapia, quimioterapia → "Cardio-Oncologia"
- ECO, RM cardíaca, TC cardíaca → "Imagem Cardiovascular"
- Marcapasso, CDI, CRT → "Marcapasso"
- Pericardite, tamponamento → "Pericardiopatias"
- HAS, hipertensão resistente → "Hipertensão Arterial Sistêmica"
- CHIP, PKP2, LMNA, canalopatias, Fabry → "Genética"
- Cardiopatia congênita → "Cardiopatia Congênita"
- Choque cardiogênico, ECMO, Impella → "Choque"
- PCR, ressuscitação cardiopulmonar → "Parada Cardiorespiratória"
- Avaliação pré-operatória, cirurgia cardíaca, pós-operatório → "Pré-Operatório"
- Diabetes, lúpus, amiloidose, Chagas, HIV cardíaco → "Manifestações Cardiovasculares de Doenças Sistêmicas"
- Use "Outros" APENAS para temas não cardiovasculares

ARTIGO:
Título: {doc_id}
Conteúdo: {resumo_md[:5000]}

Responda APENAS com JSON (sem markdown):
{{"category": "categoria exata da lista", "palavras_chave": ["termo1", "termo2", "termo3"], "population": ["lista"], "intervention": ["lista"]}}"""
    try:
        response = claude.messages.create(model="claude-sonnet-4-20250514", max_tokens=500, messages=[{"role": "user", "content": prompt}])
        raw = response.content[0].text.strip()
        json_match = re.search(r'\{.*\}', raw, re.DOTALL)
        if not json_match:
            raise ValueError("Nenhum objeto JSON encontrado na resposta")
        tags = json.loads(re.sub(r'```json\n?|```\n?', '', json_match.group(0)).strip())
        category = _validate_category(tags.get("category", "Outros"))
        palavras_chave = tags.get("palavras_chave", [])
        if isinstance(palavras_chave, list):
            palavras_chave = [str(k).strip() for k in palavras_chave if k][:3]
        else:
            palavras_chave = []
        return {
            "doenca_principal": category,
            "palavras_chave":   palavras_chave,
            "populacao":        tags.get("population", []),
            "intervencao":      tags.get("intervention", []),
        }
    except Exception as e:
        log(f"❌ tags {doc_id}: {str(e)}")
        return {"doenca_principal": "Outros", "palavras_chave": [], "populacao": [], "intervencao": []}

def verificar_e_limpar_incompletos(processados: set) -> int:
    """
    Consulta Supabase por artigos com nota_aplicabilidade NULL.
    - Remove do checkpoint os que têm corpus local → serão re-indexados no próximo loop.
    - Deleta do Supabase os que NÃO têm corpus local (fantasmas sem análise).
    Retorna o número de entradas liberadas para re-indexação.
    """
    try:
        headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/artigos",
            headers=headers,
            params={"nota_aplicabilidade": "is.null", "select": "doc_id", "limit": "2000"},
        )
        if r.status_code != 200:
            log(f"⚠️ verificar_incompletos: HTTP {r.status_code}")
            return 0
        incompletos = [row["doc_id"] for row in r.json() if row.get("doc_id")]
        if not incompletos:
            return 0

        log(f"⚠️ {len(incompletos)} artigos no Supabase com nota_aplicabilidade NULL")
        corpus_path = Path(CORPUS_DIR)
        para_reindexar, sem_corpus = [], []

        for doc_id in incompletos:
            folder = corpus_path / doc_id
            if folder.exists() and (folder / "analysis.json").exists():
                para_reindexar.append(doc_id)
            else:
                sem_corpus.append(doc_id)

        # Reescrever checkpoint removendo os que têm corpus (serão re-processados)
        if para_reindexar:
            ids_set = set(para_reindexar)
            processados.difference_update(ids_set)
            checkpoint_path = Path(CHECKPOINT_FILE)
            if checkpoint_path.exists():
                linhas = [l.strip() for l in checkpoint_path.read_text().splitlines() if l.strip()]
                checkpoint_path.write_text(
                    "\n".join(l for l in linhas if l not in ids_set) + "\n"
                )
            log(f"♻️ {len(para_reindexar)} artigos removidos do checkpoint → serão re-indexados")

        # Deletar do Supabase os fantasmas sem corpus local
        if sem_corpus:
            del_headers = {**headers, "Content-Type": "application/json"}
            for doc_id in sem_corpus:
                requests.delete(
                    f"{SUPABASE_URL}/rest/v1/artigos?doc_id=eq.{doc_id}",
                    headers=del_headers,
                )
            log(f"🗑️ {len(sem_corpus)} artigos fantasmas (sem corpus local) deletados do Supabase")

        return len(para_reindexar)
    except Exception as e:
        log(f"⚠️ verificar_incompletos: {str(e)}")
        return 0


def importar_supabase(metadata):
    try:
        # on_conflict=doc_id → upsert: usa doc_id como chave de conflito (não a PK serial)
        url = f"{SUPABASE_URL}/rest/v1/artigos?on_conflict=doc_id"
        headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json", "Prefer": "return=minimal,resolution=merge-duplicates"}
        data = {
            "doc_id":             metadata["doc_id"],
            "doi":                metadata["doi"],
            "titulo":             metadata["titulo"],
            "revista":            metadata["revista"],
            "data_publicacao":    metadata["data_publicacao"],
            "tipo_estudo":        metadata["tipo_estudo"],
            "nota_aplicabilidade": metadata["nota_geral"],
            "doenca_principal":   metadata["doenca_principal"],
            "palavras_chave":     metadata.get("palavras_chave", []),
            "populacao":          metadata.get("populacao", []),
            "intervencao":        metadata.get("intervencao", []),
            "caminho_pasta":      metadata["caminho_pasta"],
        }
        # Incluir URL do visual abstract se existir localmente
        if metadata.get("caminho_visual_abstract"):
            data["caminho_visual_abstract"] = metadata["caminho_visual_abstract"]
        response = requests.post(url, headers=headers, json=data)
        if response.status_code not in [200, 201, 204]:
            log(f"❌ importar {metadata['doc_id']}: HTTP {response.status_code} — {response.text[:300]}")
            return False
        return True
    except Exception as e:
        log(f"❌ importar {metadata['doc_id']}: {str(e)}")
        return False

def main():
    log("="*60)
    log("🚀 CARDIODAILY - INDEXAÇÃO")
    log("="*60)
    corpus_path = Path(CORPUS_DIR)
    if not corpus_path.exists():
        log("❌ Corpus não encontrado")
        return
    folders = [f for f in corpus_path.iterdir() if f.is_dir() and f.name.startswith("doi_")]
    log(f"📊 Total: {len(folders)}")
    processados = load_checkpoint()
    verificar_e_limpar_incompletos(processados)
    folders = [f for f in folders if f.name not in processados]
    log(f"⏭️ Restantes: {len(folders)}")
    if len(folders) == 0:
        log("✅ Todos processados!")
        return
    sucesso, filtrados, erros, claude_calls = 0, 0, 0, 0
    for folder in tqdm(folders, desc="Processando"):
        metadata = extract_metadata(folder)
        if not metadata:
            filtrados += 1
            save_checkpoint(folder.name)
            continue
        # Chamar Claude APENAS se doenca_principal não veio do analysis.json
        if not metadata.get("doenca_principal"):
            resumo_md = metadata.pop("_resumo_md", "") or ""
            tags = extrair_tags_claude(resumo_md, metadata["doc_id"])
            metadata.update(tags)
            claude_calls += 1
            # Write-back: salvar no analysis.json para evitar nova chamada Claude no futuro
            try:
                json_path = folder / "analysis.json"
                aj = json.load(open(json_path, "r", encoding="utf-8"))
                aj.setdefault("classification", {})
                aj["classification"]["doenca_principal"] = tags["doenca_principal"]
                aj["classification"]["palavras_chave"]   = tags.get("palavras_chave", [])
                aj["classification"]["populacao"]        = tags["populacao"]
                aj["classification"]["intervencao"]      = tags["intervencao"]
                tmp = str(json_path) + ".tmp"
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump(aj, f, ensure_ascii=False, indent=2)
                Path(tmp).replace(json_path)
            except Exception:
                pass  # write-back é melhor esforço, não bloqueia a indexação
        else:
            metadata.pop("_resumo_md", None)  # limpar campo interno
        if importar_supabase(metadata):
            sucesso += 1
            save_checkpoint(folder.name)
        else:
            erros += 1
    log("\n"+"="*60)
    log(f"✅ Sucesso: {sucesso} | ⊘ Filtrados: {filtrados} | ❌ Erros: {erros} | 🤖 Claude calls: {claude_calls}")

if __name__ == "__main__":
    main()
