#!/usr/bin/env python3
"""
Visual Abstract Generator — CardioDaily

Gera Visual Abstracts de 1 página a partir de analysis.md/analysis.json.
Extração via Claude Sonnet 4 → Jinja2 HTML → Playwright PNG.

Uso:
    # Gerar para um artigo específico
    python3 src/infographics/visual_abstract_generator.py outputs/corpus/doi_XXXXX

    # Gerar pendentes (score >= 7)
    python3 src/infographics/visual_abstract_generator.py --batch

    # Gerar pendentes com score mínimo diferente
    python3 src/infographics/visual_abstract_generator.py --batch --score-min 8

    # Forçar regeneração (ignorar cache)
    python3 src/infographics/visual_abstract_generator.py --batch --force

    # Testar com N artigos
    python3 src/infographics/visual_abstract_generator.py --test --test-n 3
"""

import json
import os
import re
import sys
import time
from pathlib import Path
import requests
import anthropic as _anthropic_module

# Carregar .env do root do projeto
_ROOT = Path(__file__).resolve().parent.parent.parent
_env_file = _ROOT / ".env"
if _env_file.exists():
    from dotenv import load_dotenv
    load_dotenv(_env_file)

# ============================================================
# SUPABASE UPLOAD
# ============================================================

BUCKET = "visual_abstracts"


def upload_visual_abstract_supabase(doc_id: str, png_path: Path) -> str | None:
    """
    Faz upload do PNG para Supabase Storage (bucket 'visual_abstracts').
    Retorna a URL pública ou None em caso de erro.
    """
    supabase_url = os.getenv("SUPABASE_URL", "").rstrip("/")
    svc_key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY", "")

    if not supabase_url or not svc_key:
        print("  ⚠️  SUPABASE_URL ou SUPABASE_SERVICE_KEY não configurados")
        return None

    objeto = f"{doc_id}.png"
    url_publica = f"{supabase_url}/storage/v1/object/public/{BUCKET}/{objeto}"

    # Verificar se já existe (não-fatal se timeout)
    try:
        if requests.head(url_publica, timeout=5).status_code == 200:
            return url_publica
    except Exception:
        pass  # Prosseguir com upload mesmo sem confirmar existência

    # Upload
    with open(png_path, "rb") as f:
        dados = f.read()

    r = requests.post(
        f"{supabase_url}/storage/v1/object/{BUCKET}/{objeto}",
        headers={
            "apikey": svc_key,
            "Authorization": f"Bearer {svc_key}",
            "Content-Type": "image/png",
            "x-upsert": "true",
        },
        data=dados,
        timeout=60,
    )

    if r.status_code in (200, 201):
        return url_publica

    # Tentar criar bucket se não existir
    if r.status_code in (400, 404):
        requests.post(
            f"{supabase_url}/storage/v1/bucket",
            headers={"apikey": svc_key, "Authorization": f"Bearer {svc_key}"},
            json={"id": BUCKET, "name": BUCKET, "public": True},
            timeout=15,
        )
        # Re-tentar upload
        r2 = requests.post(
            f"{supabase_url}/storage/v1/object/{BUCKET}/{objeto}",
            headers={
                "apikey": svc_key,
                "Authorization": f"Bearer {svc_key}",
                "Content-Type": "image/png",
                "x-upsert": "true",
            },
            data=dados,
            timeout=60,
        )
        if r2.status_code in (200, 201):
            return url_publica

    print(f"  ⚠️  Upload falhou: {r.status_code} {r.text[:100]}")
    return None


def atualizar_campo_supabase(doc_id: str, campo: str, valor: str) -> bool:
    """Atualiza um campo na tabela artigos do Supabase."""
    supabase_url = os.getenv("SUPABASE_URL", "").rstrip("/")
    svc_key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY", "")

    if not supabase_url or not svc_key:
        return False

    r = requests.patch(
        f"{supabase_url}/rest/v1/artigos?doc_id=eq.{doc_id}",
        headers={
            "apikey": svc_key,
            "Authorization": f"Bearer {svc_key}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        },
        json={campo: valor},
        timeout=15,
    )
    return r.status_code in (200, 204)


# ============================================================
# PROMPTS
# ============================================================

SYSTEM_PROMPT = """Você é um cardiologista sênior brasileiro, pragmático e rigoroso.
Sua tarefa: extrair de uma análise de artigo científico um JSON estruturado
para gerar um Visual Abstract de 1 página.

REGRAS ABSOLUTAS:
- Bullets curtos (máx 15 palavras cada)
- Português brasileiro, sem erros de ortografia
- Números sempre com unidade e IC95 quando disponível
- Se o dado não existe na análise, use null (nunca invente)
- Seção 8 (aplicabilidade) deve ser escrita como se fosse uma anotação
  rápida que você faria antes de entrar no ambulatório
- Responda APENAS com o JSON, sem texto antes ou depois, sem markdown"""

# Prompt para ARTIGOS ORIGINAIS (RCT, coorte, caso-controle, etc.)
USER_PROMPT_TEMPLATE = """Analise o artigo abaixo e extraia um JSON com EXATAMENTE esta estrutura.
Responda APENAS com o JSON válido, sem markdown, sem ```json, sem texto adicional.

--- INÍCIO DA ANÁLISE ---
{content}
--- FIM DA ANÁLISE ---

Retorne o JSON no formato:

{{
  "tema_central": {{
    "titulo": "string — título em português, máx 20 palavras, estilo manchete",
    "categoria": "string — ex: Amiloidose Cardíaca, Insuficiência Cardíaca, FA, DAC, HAS...",
    "revista": "string — nome da revista",
    "ano": "string — ano de publicação"
  }},
  "tipo_artigo": "original",
  "pergunta_clinica": [
    "string — A pergunta que o estudo tenta responder, 1-2 bullets"
  ],
  "metodos": [
    "string — Tipo de estudo",
    "string — Desenho",
    "string — Seguimento",
    "string — Comparação: Intervenção vs Controle"
  ],
  "populacao": [
    "string — N total e braços",
    "string — Critérios de inclusão (1 bullet)",
    "string — Características basais (idade, comorbidades)"
  ],
  "resultados": [
    "string — Desfecho primário com número, IC95 e p-valor",
    "string — Desfechos secundários relevantes",
    "string — NNT/NNH se calculável",
    "string — Segurança: eventos adversos"
  ],
  "limitacoes": {{
    "vieses": ["string — viéses identificados"],
    "pontos_fortes": ["string — o que o estudo faz bem"],
    "pontos_fracos": ["string — o que compromete a validade"]
  }},
  "discussao": [
    "string — Contextualização (máx 3 bullets)",
    "string — Comparação com evidência prévia",
    "string — O que falta responder"
  ],
  "conclusao": [
    "string — Conclusão em 1-2 bullets diretos"
  ],
  "aplicabilidade_clinica": {{
    "o_que_usar": "string — Medicamento, dose, via, frequência",
    "em_quem": "string — População que se beneficia",
    "beneficio_paciente": "string — O que o paciente ganha",
    "cuidados": "string — Ressalvas, quando NÃO usar",
    "perola": "string — A frase-resumo pro post-it do consultório"
  }},
  "nota_aplicabilidade": 7,
  "cor_destaque": "string — verde (benefício claro), amarelo (evidência moderada), vermelho (risco/cautela)"
}}"""

# Prompt para REVISÕES, META-ANÁLISES, GUIDELINES e EDITORIAIS
# Foco: recomendações práticas, NÃO detalhes metodológicos
USER_PROMPT_REVIEW_TEMPLATE = """Analise abaixo uma REVISÃO / META-ANÁLISE / GUIDELINE / EDITORIAL.
Responda APENAS com o JSON válido, sem markdown, sem ```json, sem texto adicional.

ATENÇÃO — este NÃO é um artigo original. Siga estas prioridades:
1. "metodos": MÁXIMO 2 bullets. Apenas tipo da revisão e período coberto. NADA MAIS.
2. "populacao": Quem é o paciente-alvo + escopo da revisão (N estudos/pacientes se meta-análise).
3. "resultados": AQUI MORA O VALOR. Escreva como POST-ITS de consultório:
   "Use X em pacientes com Y → reduz Z em W%"
   "Dose recomendada: X mg/dia. Alvo: Y."
   "Não usar quando: [condição]"
   Se há números pooled (RR/OR/HR/NNT) inclua o mais importante.
4. "aplicabilidade_clinica": Guia prático completo — segunda-feira de manhã,
   paciente entra, o que você faz diferente por causa desta revisão?

--- INÍCIO DA ANÁLISE ---
{content}
--- FIM DA ANÁLISE ---

Retorne o JSON no formato:

{{
  "tema_central": {{
    "titulo": "string — título em português, máx 20 palavras, estilo manchete",
    "categoria": "string — ex: Amiloidose Cardíaca, IC, FA, DAC, HAS...",
    "revista": "string — nome da revista",
    "ano": "string — ano de publicação"
  }},
  "tipo_artigo": "revisao",
  "pergunta_clinica": [
    "string — A questão clínica central desta revisão em 1-2 bullets diretos"
  ],
  "metodos": [
    "string — Tipo: Revisão sistemática / Meta-análise / Guideline / Narrativa / Editorial",
    "string — Cobertura: [período]. [N estudos + N pacientes se meta-análise]"
  ],
  "populacao": [
    "string — Paciente-alvo: perfil clínico de quem se beneficia do conhecimento",
    "string — Questão PICO adaptada em 1 frase",
    "string — Abrangência: sociedades consultadas, bases de dados, nível de evidência"
  ],
  "resultados": [
    "string — Recomendação 1: O QUE fazer + em quem + benefício esperado",
    "string — Recomendação 2: dose / estratégia específica / alvo terapêutico",
    "string — Recomendação 3: quando NÃO usar / contraindicações / red flags",
    "string — Dado numérico: resultado pooled mais relevante com IC95% (se existir)"
  ],
  "limitacoes": {{
    "vieses": ["string — principal limitação metodológica desta revisão"],
    "pontos_fortes": ["string — por que confiar nesta revisão"],
    "pontos_fracos": ["string — o que esta revisão NÃO responde"]
  }},
  "discussao": [
    "string — Onde isso muda a prática clínica atual",
    "string — O que as diretrizes dizem hoje vs o que esta revisão acrescenta",
    "string — Próximo passo: o que falta para consolidar a recomendação"
  ],
  "conclusao": [
    "string — A mensagem mais importante em 1 frase direta",
    "string — Grau de confiança: alto / moderado / baixo — e por quê em 5 palavras"
  ],
  "aplicabilidade_clinica": {{
    "o_que_usar": "string — Intervenção concreta: medicamento/estratégia + dose + via + frequência",
    "em_quem": "string — Perfil exato do paciente: diagnóstico, gravidade, comorbidades",
    "beneficio_paciente": "string — O que o paciente ganha em termos concretos e mensuráveis",
    "cuidados": "string — Quando NÃO aplicar, monitorização necessária, interações",
    "perola": "string — 'Quando ver [situação], [ação concreta]. Resultado: [benefício]'"
  }},
  "nota_aplicabilidade": 7,
  "cor_destaque": "string — verde (recomendação clara/aplicável), amarelo (evidência moderada), vermelho (cautela/risco)"
}}"""

# Tipos de artigo que usam o prompt de revisão
_REVIEW_SUBTYPES = {
    "revisao_sistematica_meta_analise",
    "revisao_geral",
    "guideline",
    "ponto_de_vista",
    "revisao",
    "review",
    "meta_analise",
    "metanalise",
    "editorial",
    "diretriz",
    "consenso",
}


# ============================================================
# CLASSE PRINCIPAL
# ============================================================

class VisualAbstractGenerator:
    """Gera Visual Abstracts: Claude Sonnet 4 extração → Jinja2 → Playwright PNG."""

    TEMPLATE_NAME = "visual_abstract_template.html"
    CACHE_FILENAME = "visual_abstract_data.json"
    OUTPUT_FILENAME = "visual_abstract.png"
    MAX_CONTENT_CHARS = 12000

    def __init__(self):
        self.template_dir = Path(__file__).parent / "templates"
        self.template_path = self.template_dir / self.TEMPLATE_NAME
        self._anthropic_client = None
        self._jinja_env = None

    # ------ Lazy inits ------

    @property
    def anthropic_client(self):
        if self._anthropic_client is None:
            import anthropic
            self._anthropic_client = anthropic.Anthropic()
        return self._anthropic_client

    @property
    def jinja_env(self):
        if self._jinja_env is None:
            from jinja2 import Environment, FileSystemLoader
            self._jinja_env = Environment(
                loader=FileSystemLoader(str(self.template_dir)),
                autoescape=False,
            )
        return self._jinja_env

    # ------ Extração via Claude ------

    def _detectar_tipo_artigo(self, analysis_json_path: Path) -> str:
        """Detecta se o artigo é original ou revisão lendo classification.subtype."""
        if not analysis_json_path.exists():
            return "original"
        try:
            data = json.loads(analysis_json_path.read_text(encoding="utf-8"))
            clf = data.get("classification", {})
            subtype = (
                clf.get("subtype")
                or clf.get("type")
                or data.get("article_type")
                or ""
            ).lower().strip()
            if subtype in _REVIEW_SUBTYPES:
                return "revisao"
            # Se o type é "original" ou "artigo_original", é original
            return "original"
        except (json.JSONDecodeError, AttributeError):
            return "original"

    def extrair_dados(self, article_dir: Path, force: bool = False,
                      canonical_type: str | None = None) -> dict:
        """
        Extrai dados estruturados do analysis.md via Claude Sonnet 4.
        Usa cache em assets/visual_abstract_data.json se disponível.

        canonical_type: quando passado pelo article_analyzer ("original",
        "metanalise", "revisao"), evita depender do analysis.json que pode
        ainda não ter sido escrito no momento da geração.
        """
        assets_dir = article_dir / "assets"
        assets_dir.mkdir(exist_ok=True)
        cache_path = assets_dir / self.CACHE_FILENAME

        # Usar cache se existir e não forçar
        if cache_path.exists() and not force:
            try:
                data = json.loads(cache_path.read_text(encoding="utf-8"))
                if data and "tema_central" in data:
                    return data
            except (json.JSONDecodeError, KeyError):
                pass  # Cache inválido, re-extrair

        # Carregar analysis.md (fonte primária)
        analysis_md_path = article_dir / "analysis.md"
        analysis_json_path = article_dir / "analysis.json"

        content = None
        if analysis_md_path.exists():
            content = analysis_md_path.read_text(encoding="utf-8")
        elif analysis_json_path.exists():
            # Fallback: usar analysis.json como fonte
            raw = json.loads(analysis_json_path.read_text(encoding="utf-8"))
            content = json.dumps(raw, ensure_ascii=False, indent=2)

        if not content:
            raise FileNotFoundError(
                f"Nem analysis.md nem analysis.json encontrados em {article_dir}"
            )

        # Limitar tamanho
        if len(content) > self.MAX_CONTENT_CHARS:
            content = content[: self.MAX_CONTENT_CHARS]

        # Determinar tipo: canonical_type tem precedência (evita timing issue),
        # fallback para leitura do analysis.json
        if canonical_type in ("metanalise", "revisao"):
            tipo_artigo = "revisao"
        elif canonical_type == "original":
            tipo_artigo = "original"
        else:
            tipo_artigo = self._detectar_tipo_artigo(analysis_json_path)
        is_review = (tipo_artigo == "revisao")

        # Ler nota_aplicabilidade do JSON existente (mais confiável que re-gerar)
        nota_existente = self._ler_nota_existente(analysis_json_path)

        # Ler revista do JSON existente
        revista_existente = self._ler_revista_existente(analysis_json_path)

        # Selecionar prompt conforme tipo
        template = USER_PROMPT_REVIEW_TEMPLATE if is_review else USER_PROMPT_TEMPLATE
        prompt_label = "revisão/meta-análise" if is_review else "artigo original"
        print(f"  📋 Tipo detectado: {prompt_label}")

        # Chamar Claude Sonnet 4 (com retry para timeouts)
        prompt = template.format(content=content)

        response = None
        last_exc = None
        for attempt in range(1, 4):  # até 3 tentativas
            try:
                response = self.anthropic_client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=2500,
                    system=SYSTEM_PROMPT,
                    messages=[{"role": "user", "content": prompt}],
                )
                break
            except (_anthropic_module.APIStatusError, _anthropic_module.APIConnectionError,
                    _anthropic_module.APITimeoutError) as e:
                last_exc = e
                if attempt < 3:
                    wait = 10 * attempt  # 10s, 20s
                    print(f"  ⚠️  Tentativa {attempt} falhou ({type(e).__name__}), aguardando {wait}s...")
                    time.sleep(wait)
        if response is None:
            raise last_exc

        raw_response = response.content[0].text

        # Extrair JSON da resposta (robusto contra texto extra)
        match = re.search(r"\{.*\}", raw_response, re.DOTALL)
        if not match:
            raise ValueError(f"Claude não retornou JSON válido: {raw_response[:200]}")

        data = json.loads(match.group())

        # Sobrescrever nota com a do pipeline (mais confiável)
        if nota_existente and nota_existente > 0:
            data["nota_aplicabilidade"] = nota_existente

        # Sobrescrever revista se disponível
        if revista_existente and (
            not data.get("tema_central", {}).get("revista")
            or data["tema_central"]["revista"] in ("", "NR", "Não informado")
        ):
            data["tema_central"]["revista"] = revista_existente

        # Validar cor_destaque
        if data.get("cor_destaque") not in ("verde", "amarelo", "vermelho"):
            data["cor_destaque"] = "amarelo"

        # Limpar listas com None
        data = self._limpar_nulos(data)

        # Salvar cache
        cache_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        return data

    # ------ Renderização ------

    def renderizar_html(self, data: dict) -> str:
        """Renderiza o template Jinja2 com os dados extraídos."""
        template = self.jinja_env.get_template(self.TEMPLATE_NAME)
        return template.render(data=data)

    def gerar_png(self, article_dir: Path, force: bool = False, open_file: bool = False,
                  canonical_type: str | None = None) -> Path:
        """
        Pipeline completo: extração → HTML → PNG.
        Retorna o path do PNG gerado.

        canonical_type: "original" | "metanalise" | "revisao" — passado pelo
        article_analyzer para seleção correta do prompt sem depender do timing
        de escrita do analysis.json.
        """
        assets_dir = article_dir / "assets"
        assets_dir.mkdir(exist_ok=True)
        output_path = assets_dir / self.OUTPUT_FILENAME

        # Skip se já existe e não forçar
        if output_path.exists() and not force:
            print(f"  ⏭️  Visual Abstract já existe: {output_path.name}")
            return output_path

        # 1. Extrair dados
        print(f"  🔍 Extraindo dados via Claude Sonnet 4...")
        data = self.extrair_dados(article_dir, force=force, canonical_type=canonical_type)

        # 2. Renderizar HTML
        print(f"  🎨 Renderizando HTML...")
        html = self.renderizar_html(data)

        # 3. Playwright → PNG
        print(f"  📸 Capturando PNG...")
        self._html_to_png(html, output_path)

        if not output_path.exists() or output_path.stat().st_size < 1024:
            raise RuntimeError(
                f"Playwright falhou: {output_path.name} não criado ou muito pequeno "
                f"({output_path.stat().st_size if output_path.exists() else 0} bytes)"
            )

        size_kb = output_path.stat().st_size / 1024
        print(f"  ✅ Visual Abstract gerado: {output_path.name} ({size_kb:.0f} KB)")

        titulo = data.get("tema_central", {}).get("titulo", "?")
        nota = data.get("nota_aplicabilidade", "?")
        cor = data.get("cor_destaque", "?")
        print(f"     Título: {titulo}")
        print(f"     NAC: {nota}/10 | Cor: {cor}")

        # Upload automático para Supabase Storage
        try:
            doc_id = article_dir.name
            public_url = upload_visual_abstract_supabase(doc_id, output_path)
            if public_url:
                ok = atualizar_campo_supabase(doc_id, "caminho_visual_abstract", public_url)
                if ok:
                    print(f"  ☁️  Publicado e Supabase atualizado: {public_url}")
                else:
                    print(f"  ⚠️  Upload OK mas Supabase NÃO atualizado (PATCH retornou erro)")
            else:
                print(f"  ⚠️  Upload para Storage falhou (URL não retornada)")
        except Exception as e:
            print(f"  ⚠️  Upload Supabase falhou (não-fatal): {e}")

        if open_file:
            import subprocess
            subprocess.run(["open", str(output_path)], check=False)

        return output_path

    # ------ Playwright ------

    def _html_to_png(self, html: str, output_path: Path):
        """Renderiza HTML para PNG via Playwright."""
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(
                viewport={"width": 1080, "height": 800},
                device_scale_factor=2,
            )
            page.set_content(html, wait_until="networkidle")

            # Esperar fontes carregarem
            page.wait_for_timeout(1500)

            # Capturar elemento .container (altura dinâmica)
            container = page.query_selector(".container")
            if container:
                container.screenshot(path=str(output_path))
            else:
                page.screenshot(path=str(output_path), full_page=True)

            browser.close()

    # ------ Helpers ------

    def _ler_nota_existente(self, json_path: Path) -> int:
        """Lê nota_aplicabilidade do analysis.json com fallback."""
        if not json_path.exists():
            return 0
        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
            scores = (
                data.get("analysis", {}).get("scores")
                or data.get("scores")
                or {}
            )
            return int(
                scores.get("aplicabilidade")
                or scores.get("overall")
                or 0
            )
        except (json.JSONDecodeError, ValueError, TypeError):
            return 0

    def _ler_revista_existente(self, json_path: Path) -> str:
        """Lê revista do analysis.json."""
        if not json_path.exists():
            return ""
        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
            return data.get("source", {}).get("journal", "") or ""
        except (json.JSONDecodeError, KeyError):
            return ""

    def _limpar_nulos(self, data: dict) -> dict:
        """Remove itens None de listas no JSON."""
        for key, value in data.items():
            if isinstance(value, list):
                data[key] = [v for v in value if v is not None]
            elif isinstance(value, dict):
                data[key] = self._limpar_nulos(value)
        return data


# ============================================================
# CLI
# ============================================================

def find_eligible_articles(corpus_dir: Path, score_min: int = 7) -> list:
    """Encontra artigos elegíveis para Visual Abstract."""
    eligible = []
    for doc_dir in sorted(corpus_dir.iterdir()):
        if not doc_dir.is_dir():
            continue

        json_path = doc_dir / "analysis.json"
        if not json_path.exists():
            continue

        # Precisa ter analysis.md OU analysis.json
        has_source = (doc_dir / "analysis.md").exists() or json_path.exists()
        if not has_source:
            continue

        # Verificar nota
        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
            scores = (
                data.get("analysis", {}).get("scores")
                or data.get("scores")
                or {}
            )
            nota = int(scores.get("aplicabilidade") or scores.get("overall") or 0)
        except (json.JSONDecodeError, ValueError):
            continue

        if nota >= score_min:
            eligible.append((doc_dir, nota))

    return eligible


def main():
    import argparse

    parser = argparse.ArgumentParser(description="CardioDaily Visual Abstract Generator")
    parser.add_argument("article_dir", nargs="?", help="Diretório do artigo")
    parser.add_argument("--batch", action="store_true", help="Gerar para todos os pendentes")
    parser.add_argument("--test", action="store_true", help="Modo teste")
    parser.add_argument("--test-n", type=int, default=3, help="Número de artigos para teste")
    parser.add_argument("--score-min", type=int, default=7, help="Score mínimo (default: 7)")
    parser.add_argument("--force", action="store_true", help="Forçar regeneração")
    parser.add_argument("--open", action="store_true", help="Abrir PNG após gerar")
    args = parser.parse_args()

    gen = VisualAbstractGenerator()

    # Modo: artigo único
    if args.article_dir:
        article_dir = Path(args.article_dir)
        if not article_dir.exists():
            print(f"❌ Diretório não encontrado: {article_dir}")
            sys.exit(1)
        gen.gerar_png(article_dir, force=args.force, open_file=args.open)
        return

    # Modo: batch ou teste
    corpus_dir = Path("outputs/corpus")
    if not corpus_dir.exists():
        print("❌ Diretório outputs/corpus/ não encontrado")
        sys.exit(1)

    eligible = find_eligible_articles(corpus_dir, args.score_min)
    print(f"\n📊 Artigos elegíveis (NAC ≥ {args.score_min}): {len(eligible)}")

    # Filtrar já processados (a menos que --force)
    if not args.force:
        pending = [
            (d, n) for d, n in eligible
            if not (d / "assets" / gen.OUTPUT_FILENAME).exists()
        ]
    else:
        pending = eligible

    if args.test:
        pending = pending[: args.test_n]

    print(f"🔄 A processar: {len(pending)} artigos\n")

    success = 0
    errors = 0

    for i, (doc_dir, nota) in enumerate(pending, 1):
        doc_id = doc_dir.name
        print(f"\n[{i}/{len(pending)}] {doc_id} (NAC: {nota})")

        try:
            gen.gerar_png(doc_dir, force=args.force, open_file=args.open)
            success += 1
        except Exception as e:
            print(f"  ❌ Erro: {e}")
            errors += 1

        # Rate limiting (respeitar API)
        if i < len(pending):
            time.sleep(3)

    print(f"\n{'='*50}")
    print(f"✅ Sucesso: {success} | ❌ Erros: {errors} | Total: {len(pending)}")


if __name__ == "__main__":
    main()
