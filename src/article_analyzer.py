"""
Sistema Principal de Análise de Artigos Médicos
Dr. Eduardo Castro - CardioDaily

Orquestra todo o fluxo:
1. Download de PDFs do Google Drive
2. Extração de DOI e verificação de duplicatas
3. Extração de texto do PDF
4. Classificação do tipo de artigo
5. Análise com IA (Claude Sonnet 4 para revisões, Gemini 2.5 Pro para meta-análises/originais)
11. Geração de áudio (ElevenLabs) para scores ≥7
12. Geração de imagem (DALL-E 3) para scores ≥7
13. Salvamento organizado em pastas locais
14. Atualização do banco de dados e relatório HTML

MODELOS POR TIPO DE ARTIGO (ATUALIZADO - DEZ 2025):
- Revisões (revisao_geral, guideline, ponto_de_vista) → Claude Sonnet 4
- Meta-análises + Artigos Originais → Gemini 2.5 Pro
"""

import os
import re
import json
import hashlib
import shutil
import requests as _requests
from datetime import datetime, timezone, timedelta
from pathlib import Path
import sys

# Adicionar src/ ao path para imports funcionarem
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

# Importar módulos do sistema (importação básica)
from doi_tracker import DOITracker
from pdf_extractor import PDFExtractor
from journal_utils import extract_journal

# Importar bibliotecas para análise
from openai import OpenAI
from dotenv import load_dotenv

# ── Notificação Telegram para beta testers ────────────────────────────────────
def _notify_telegram_beta(doc_id: str, titulo: str, revista: str, score: int,
                           resumo: str, podcast_url: str | None,
                           infographic_path: str | None) -> bool:
    """
    Envia notificação automática para os beta testers no Telegram.
    Ativado apenas para score >= CARDIODAILY_NOTIFY_SCORE_MIN (default 7).
    Lista de chat_ids em TELEGRAM_BETA_CHAT_IDS (separados por vírgula).
    """
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_ids_raw = os.getenv("TELEGRAM_BETA_CHAT_IDS", "")
    if not token or not chat_ids_raw:
        return False

    score_min = int(os.getenv("CARDIODAILY_NOTIFY_SCORE_MIN", "7"))
    if score < score_min:
        return False

    chat_ids = [c.strip() for c in chat_ids_raw.split(",") if c.strip()]
    if not chat_ids:
        return False

    # Limpar título
    titulo_limpo = titulo or "Novo artigo"
    titulo_limpo = re.sub(r'^ANÁLISE CRÍTICA:\s*', '', titulo_limpo, flags=re.IGNORECASE)
    titulo_limpo = re.sub(r'^Análise:\s*', '', titulo_limpo, flags=re.IGNORECASE)
    if len(titulo_limpo) > 100:
        titulo_limpo = titulo_limpo[:100] + "..."

    # Extrair pérola do resumo (primeira linha útil)
    perola = ""
    if resumo:
        for linha in resumo.split("\n"):
            linha = linha.strip().lstrip("#•|-| ")
            if len(linha) > 40:
                perola = linha[:200]
                break

    # Montar mensagem
    estrelas = "⭐" * min(score, 5) if score >= 8 else ""
    rev_clean = revista if (revista and not revista.isdigit() and len(revista) > 2) else "CardioDaily"

    msg = f"📡 NOVO ARTIGO — CardioDaily\n\n"
    msg += f"{titulo_limpo}\n"
    msg += f"📰 {rev_clean}  |  nota {score}/10 {estrelas}\n"
    if perola:
        msg += f"\n💡 {perola}\n"
    if podcast_url:
        msg += f"\n🎙 Podcast: {podcast_url}\n"
    msg += f"\n🔍 Ver no bot: /artigos {doc_id[:20]}"

    base_url = f"https://api.telegram.org/bot{token}"
    success = True

    for chat_id in chat_ids:
        try:
            # Enviar mensagem de texto
            r = _requests.post(f"{base_url}/sendMessage", json={
                "chat_id": chat_id,
                "text": msg,
            }, timeout=15)
            if not r.ok:
                print(f"   ⚠️  Telegram notify falhou para {chat_id}: {r.text[:100]}")
                success = False

            # Enviar infográfico se existir
            if infographic_path and Path(infographic_path).exists():
                with open(infographic_path, "rb") as f:
                    _requests.post(f"{base_url}/sendPhoto", data={
                        "chat_id": chat_id,
                        "caption": f"Infográfico: {titulo_limpo[:60]}",
                    }, files={"photo": f}, timeout=30)

        except Exception as e:
            print(f"   ⚠️  Erro ao notificar {chat_id}: {e}")
            success = False

    return success
# ──────────────────────────────────────────────────────────────────────────────

# ── Upload de podcast para Supabase Storage ───────────────────────────────────
def _upload_podcast_supabase(doc_id: str, mp3_path: str) -> str | None:
    """
    Faz upload do MP3 para Supabase Storage (bucket 'podcasts').
    Atualiza artigos.caminho_audio com a URL pública.
    Retorna a URL pública ou None em caso de falha.
    """
    sb_url = os.getenv("SUPABASE_URL", "").rstrip("/")
    sb_key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY", "")
    if not sb_url or not sb_key:
        return None

    bucket = "podcasts"
    objeto = f"{doc_id}.mp3"
    url_publica = f"{sb_url}/storage/v1/object/public/{bucket}/{objeto}"

    try:
        with open(mp3_path, "rb") as f:
            dados = f.read()
        h = {
            "apikey": sb_key,
            "Authorization": f"Bearer {sb_key}",
            "Content-Type": "audio/mpeg",
            "x-upsert": "true",
        }
        r = _requests.post(
            f"{sb_url}/storage/v1/object/{bucket}/{objeto}",
            headers=h, data=dados, timeout=120
        )
        if r.status_code not in (200, 201):
            print(f"   ⚠️  Storage upload falhou: {r.status_code} {r.text[:100]}")
            return None

        # Atualizar caminho_audio na tabela artigos
        h_db = {
            "apikey": sb_key,
            "Authorization": f"Bearer {sb_key}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        }
        _requests.patch(
            f"{sb_url}/rest/v1/artigos?doc_id=eq.{doc_id}",
            headers=h_db, json={"caminho_audio": url_publica}, timeout=15
        )
        return url_publica

    except Exception as e:
        print(f"   ⚠️  Erro no upload do podcast: {e}")
        return None
# ──────────────────────────────────────────────────────────────────────────────

# Importar SDK da Anthropic (Claude)
try:
    import anthropic
    ANTHROPIC_SDK_AVAILABLE = True
except ImportError:
    ANTHROPIC_SDK_AVAILABLE = False
    print("⚠️  anthropic não instalado. Execute: pip install anthropic")

# Importar SDK nativo do Google AI (NOVA VERSÃO)
try:
    from google import genai
    from google.genai import types
    GOOGLE_SDK_AVAILABLE = True
except ImportError:
    try:
        # Fallback para versão antiga (deprecated)
        import google.generativeai as genai
        GOOGLE_SDK_AVAILABLE = True
    except ImportError:
        GOOGLE_SDK_AVAILABLE = False
        print("⚠️  google-genai não instalado. Execute: pip install google-genai")

# Importar módulos de podcast
from podcast_script_generator import PodcastScriptGenerator

# Importar classificador robusto
try:
    from robust_classifier import RobustClassifier, classify_article, extract_pub_date_from_crossref
    ROBUST_CLASSIFIER_AVAILABLE = True
except ImportError:
    ROBUST_CLASSIFIER_AVAILABLE = False
    extract_pub_date_from_crossref = None
    print("⚠️  robust_classifier não encontrado. Usando classificador básico.")

# Importar gerador de áudio (unificado: OpenAI ou ElevenLabs)
try:
    from audio_generator import UnifiedAudioGenerator
    UNIFIED_AUDIO_AVAILABLE = True
except ImportError:
    UNIFIED_AUDIO_AVAILABLE = False
    try:
        from elevenlabs_audio_generator import ElevenLabsAudioGenerator
    except ImportError:
        ElevenLabsAudioGenerator = None

# Geração de imagens DALL-E removida (v9.1) — output sem valor clínico

# Importar gerador de infográfico portrait VisualMed (Playwright)
try:
    from infographics import InfographicPortrait
    PLAYWRIGHT_INFOGRAPHIC_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_INFOGRAPHIC_AVAILABLE = False

# Importar gerador de Visual Abstract (Claude Sonnet 4 + Playwright)
try:
    from infographics.visual_abstract_generator import VisualAbstractGenerator
    VISUAL_ABSTRACT_AVAILABLE = True
except ImportError:
    VISUAL_ABSTRACT_AVAILABLE = False

# Importar gerador de mapa mental visual (Playwright)
try:
    from infographics import MindmapGenerator as PlaywrightMindmapGenerator
    PLAYWRIGHT_MINDMAP_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_MINDMAP_AVAILABLE = False

# Carregar variáveis de ambiente da raiz do projeto
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)  # sobe de src/ para CardioDaily_FULL/
dotenv_path = os.path.join(project_root, '.env')
load_dotenv(dotenv_path=dotenv_path, override=True)
print(f"🔑 Carregando variáveis de ambiente de: {dotenv_path}")

# Importação condicional do Google Drive (apenas se necessário)
GoogleDriveManager = None

# Taxonomia e prompt de classificação de doença/tema (fonte única: taxonomy.py)
from taxonomy import TAXONOMY_CATEGORIES, TAXONOMY_SET as _TAXONOMY_SET, PROMPT_CLASSIFICATION, validate_category as _validate_category

# ============================================================================
# CONFIGURAÇÃO DE CLIENTES E MODELOS
# ============================================================================

# Modelos por tipo de artigo (ATUALIZADO DEZ/2025)
# - Revisões e Guidelines: Claude Sonnet 4 (análise profunda)
# - Artigos Originais e Meta-análises: Gemini 2.5 Pro (poder estatístico)
MODEL_CONFIG = {
    # Revisões e Guidelines - Claude Sonnet 4
    'revisao_geral': 'claude-sonnet-4-5-20250929',
    'guideline': 'claude-sonnet-4-5-20250929',
    'ponto_de_vista': 'claude-sonnet-4-5-20250929',
    # Meta-análises e originais -> Gemini 2.5 Pro
    'revisao_sistematica_meta_analise': 'gemini-2.5-pro',
    'artigo_original': 'gemini-2.5-pro',
}

# Fallback model (caso nenhuma API esteja configurada)
FALLBACK_MODEL = os.environ.get('OPENAI_MODEL', 'gemini-2.5-pro')

# Cliente OpenAI (fallback)
_openai_key = os.environ.get('OPENAI_API_KEY')
openai_client = OpenAI(api_key=_openai_key) if _openai_key else None

# Cliente Anthropic (Claude)
_anthropic_key = os.environ.get('ANTHROPIC_API_KEY')
if _anthropic_key and ANTHROPIC_SDK_AVAILABLE:
    anthropic_client = anthropic.Anthropic(api_key=_anthropic_key)
    print(f"✅ Cliente Claude (Anthropic) configurado com sucesso (chave com {len(_anthropic_key)} caracteres)")
else:
    anthropic_client = None
    if not _anthropic_key:
        print("⚠️  ANTHROPIC_API_KEY não encontrada no ambiente")
    elif not ANTHROPIC_SDK_AVAILABLE:
        print("⚠️  SDK Anthropic não disponível - execute: pip install anthropic")

# Configurar Google Gemini (SDK nativo - NOVA VERSÃO)
_google_key = os.environ.get('GOOGLE_API_KEY')
if _google_key and GOOGLE_SDK_AVAILABLE:
    try:
        # Tentar nova API google.genai
        client_genai = genai.Client(api_key=_google_key)
        gemini_client = client_genai
        print("✅ Cliente Gemini (google.genai - NOVA API) configurado com sucesso")
    except (AttributeError, TypeError):
        # Fallback para API antiga
        genai.configure(api_key=_google_key)
        gemini_client = True
        print("✅ Cliente Gemini (google.generativeai - API antiga) configurado com sucesso")
else:
    gemini_client = None
    if not _google_key:
        print("⚠️  GOOGLE_API_KEY não encontrada no .env")

# Cliente padrão (para compatibilidade com código existente)
client = openai_client


def sanitize_doi(doi: str) -> str | None:
    """Sanitiza DOI removendo caracteres de controle ASCII e espaços."""
    try:
        doi_str = str(doi)
    except Exception:
        return None

    # Remover caracteres de controle ASCII (0x00-0x1F e 0x7F)
    doi_str = re.sub(r"[\x00-\x1F\x7F]", "", doi_str)
    # Remover todos os espaços/brancos
    doi_str = re.sub(r"\s+", "", doi_str)
    doi_str = doi_str.strip()

    return doi_str or None


def sha256_file(path: str) -> str:
    """Calcula SHA-256 de um arquivo via streaming (chunks)."""
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def make_doc_id(doi_clean: str | None, pdf_sha256: str) -> str:
    """Gera um doc_id determinístico a partir do DOI sanitizado ou do hash do PDF."""
    if doi_clean:
        return "doi_" + hashlib.sha1(doi_clean.encode('utf-8')).hexdigest()[:16]
    return "pdf_" + hashlib.sha1(pdf_sha256.encode('utf-8')).hexdigest()[:16]


def now_iso_brt() -> str:
    """Retorna datetime ISO 8601 com timezone -03:00 (BRT)."""
    tz = timezone(timedelta(hours=-3))
    return datetime.now(tz=tz).isoformat(timespec='seconds')


def extract_pub_date_from_filename(filename: str) -> str:
    """Extrai data de publicação do nome do PDF.

    Formatos:
      2026-02-JAMA-Title.pdf        → '2026-02'
      2026-02-06-JACC-Title.pdf     → '2026-02-06'
      CIRC-2025-RV-Title.pdf        → '2025'
    """
    import re as _re
    name = filename.replace('.pdf', '').replace('.PDF', '')
    # YYYY-MM-DD
    m = _re.match(r'(\d{4}-\d{2}-\d{2})-', name)
    if m:
        return m.group(1)
    # YYYY-MM
    m = _re.match(r'(\d{4}-\d{2})-', name)
    if m:
        return m.group(1)
    # ABBREV-YYYY-
    m = _re.match(r'[A-Z]+-(\d{4})-', name)
    if m:
        return m.group(1)
    return ""


def canonical_type_for(article_type: str) -> str:
    """Mapeia subtype (label interno) para tipo canônico."""
    if article_type == 'artigo_original':
        return 'original'
    if article_type == 'revisao_sistematica_meta_analise':
        return 'metanalise'
    # guideline, revisao_geral, ponto_de_vista
    return 'revisao'


def extract_podcast_article_title(analysis_text: str, fallback_filename: str) -> str:
    """Extrai um título adequado para o podcast a partir do texto da análise.

    Prioriza o campo **Título** quando presente (ex.: em tabela Markdown) e
    cai para o nome do arquivo sem extensão como fallback.
    """
    fallback = os.path.splitext(os.path.basename(fallback_filename or ""))[0].strip()

    if analysis_text:
        patterns = [
            # Tabela Markdown: | **Título** | ... |
            r"^\|\s*\*\*T[ií]tulo\*\*\s*\|\s*(.+?)\s*\|\s*$",
            # Formatos comuns: **Título:** ... / **Título do artigo:** ...
            r"^\*\*T[ií]tulo(?:\s+do\s+artigo)?\*\*\s*:\s*(.+?)\s*$",
            r"^[Tt][ií]tulo\s*:\s*(.+?)\s*$",
            # Em alguns outputs pode vir em inglês
            r"^\|\s*\*\*Title\*\*\s*\|\s*(.+?)\s*\|\s*$",
            r"^\*\*Title\*\*\s*:\s*(.+?)\s*$",
        ]

        for pat in patterns:
            m = re.search(pat, analysis_text, flags=re.MULTILINE)
            if not m:
                continue
            title = (m.group(1) or "").strip()
            # Remover resíduos de Markdown e normalizar espaços
            title = re.sub(r"[`*_]+", "", title)
            title = re.sub(r"\s+", " ", title).strip()
            # Remover qualquer menção ao nome do arquivo/extension
            title = re.sub(r"\.pdf\b", "", title, flags=re.IGNORECASE).strip()
            if title:
                return title

    return re.sub(r"\.pdf\b", "", fallback, flags=re.IGNORECASE).strip() or "Artigo (título não informado)"


class ArticleAnalyzer:
    """
    Sistema principal de análise de artigos médicos.
    """
    
    def __init__(self, 
                 input_folder_id="19fWS3lEI6RIkoxbCdbxB4LB91bHX02LA",
                 input_local_dir=None,
                 output_base_dir="outputs"):
        """
        Inicializa o analisador de artigos.
        
        Args:
            input_folder_id: ID da pasta INPUT no Google Drive
            input_local_dir: Caminho local com PDFs para processar (se definido, ignora o Drive)
            output_base_dir: Diretório base para salvar outputs
        """
        self.input_folder_id = input_folder_id
        self.input_local_dir = os.path.expanduser(input_local_dir) if input_local_dir else None

        # Permitir sobrescrever diretório de output via env (útil para testes)
        env_output_dir = os.environ.get('CARDIODAILY_OUTPUT_DIR')
        if env_output_dir:
            output_base_dir = env_output_dir
        
        # Detectar se estamos rodando de src/ e ajustar caminhos para o projeto raiz
        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(script_dir) if os.path.basename(script_dir) == 'src' else script_dir
        
        # Usar caminho absoluto para outputs baseado na raiz do projeto
        self.output_base_dir = os.path.join(project_root, output_base_dir) if not os.path.isabs(output_base_dir) else output_base_dir

        # Corpus canônico para indexação/escala
        self.corpus_dir = os.path.join(self.output_base_dir, "corpus")
        
        # Criar estrutura de diretórios
        self.dirs = {
            'downloads': os.path.join(self.output_base_dir, 'downloads'),
            'markdown': os.path.join(self.output_base_dir, 'markdown'),
            'audio': os.path.join(self.output_base_dir, 'audio'),
            'images': os.path.join(self.output_base_dir, 'images'),
            # Subpastas de markdown por tipo
            'markdown_artigos_originais': os.path.join(self.output_base_dir, 'markdown', 'Artigos_Originais'),
            'markdown_meta_analises': os.path.join(self.output_base_dir, 'markdown', 'Meta_Analises'),
            'markdown_revisoes': os.path.join(self.output_base_dir, 'markdown', 'Revisoes'),
        }
        
        os.makedirs(self.corpus_dir, exist_ok=True)

        for dir_path in self.dirs.values():
            os.makedirs(dir_path, exist_ok=True)
        
        # Inicializar componentes
        print("\n" + "=" * 80)
        print("🚀 INICIALIZANDO SISTEMA DE ANÁLISE DE ARTIGOS")
        print("=" * 80)
        
        if self.input_local_dir:
            print("\n1️⃣ Modo LOCAL ativado — lerei PDFs em:")
            print(f"   📂 {self.input_local_dir}")
            self.drive_manager = None
        else:
            print("\n1️⃣ Conectando ao Google Drive...")
            # Importar apenas quando necessário
            from google_drive_manager_v2 import GoogleDriveManager
            # Resolver caminho de credenciais (prioridade: env > upload/ > credentials/)
            env_sa_path = os.environ.get('CARDIODAILY_SERVICE_ACCOUNT_PATH')
            candidates = [
                env_sa_path,
                'upload/pasted_file_CTs5mS_service_account.json',
                'credentials/service_account.json',
            ]
            service_account_path = next((p for p in candidates if p and os.path.exists(p)), None)
            if not service_account_path:
                # Manter caminho “padrão” para mensagens de erro consistentes no GoogleDriveManager
                service_account_path = candidates[-1]

            try:
                self.drive_manager = GoogleDriveManager(service_account_path=service_account_path)
            except FileNotFoundError as e:
                print(f"\n⚠️  Google Drive indisponível ({e}).")
                fallback_local_dir = os.environ.get('LOCAL_ARTICLES_DIR')
                if fallback_local_dir:
                    self.input_local_dir = os.path.expanduser(fallback_local_dir)
                else:
                    # Fallback automático para pastas comuns no projeto
                    project_candidates = [
                        os.path.join(project_root, 'ARTIGOS_HOJE'),
                        os.path.join(project_root, 'ARTIGOS'),
                        os.path.join(project_root, 'tmp_one_pdf'),
                    ]
                    self.input_local_dir = next((p for p in project_candidates if os.path.isdir(p)), None)

                if self.input_local_dir:
                    print("➡️  Alternando automaticamente para MODO LOCAL — lerei PDFs em:")
                    print(f"   📂 {self.input_local_dir}")
                    self.drive_manager = None
                else:
                    raise
        
        print("\n2️⃣ Carregando rastreador de DOIs...")
        # Permitir DB/HTML alternativos via env (útil para testes sem “sujar” o histórico oficial)
        db_path = os.environ.get('CARDIODAILY_DB_PATH', 'data/analyzed_articles.json')
        html_path = os.environ.get('CARDIODAILY_HTML_PATH', 'data/analyzed_articles.html')
        self.doi_tracker = DOITracker(database_path=db_path, html_path=html_path)
        
        print("\n3️⃣ Inicializando extrator de PDF...")
        self.pdf_extractor = PDFExtractor()
        
        print("\n4️⃣ Configurando Gemini AI...")
        self._setup_gemini()
        
        print("\n5️⃣ Carregando prompts personalizados...")
        self._load_prompts()
        
        print("\n6️⃣ Inicializando geradores de podcast...")
        self._setup_podcast_generators()

        print("\n7️⃣ Inicializando gerador de infográficos...")
        self._setup_infographic_generator()

        print("\n8️⃣ Inicializando gerador de mapa mental...")
        self._setup_mindmap_generator()

        print("\n" + "=" * 80)
        print("✅ SISTEMA PRONTO PARA ANÁLISE!")
        print("=" * 80 + "\n")
    
    def _setup_gemini(self):
        """Configura os modelos de IA por tipo de artigo."""
        # Configuração de modelos por tipo de artigo
        self.model_config = MODEL_CONFIG.copy()
        self.fallback_model = FALLBACK_MODEL
        
        # Verificar quais clientes estão disponíveis
        self.use_claude = anthropic_client is not None
        self.use_gemini = gemini_client is not None
        
        print("   📋 Configuração de Modelos:")
        if self.use_claude:
            print("      📚 Revisões/Guidelines → Claude Sonnet 4 (Anthropic)")
        if self.use_gemini:
            print("      📊 Meta-análises/Originais → Gemini 2.5 Pro (Google)")
        if not self.use_claude and not self.use_gemini:
            print(f"      ⚠️  Usando fallback: {self.fallback_model}")
            
        # Configurações de geração
        try:
            self.default_temperature = float(os.environ.get('OPENAI_TEMPERATURE', '0.3'))
        except ValueError:
            self.default_temperature = 0.3
        # Temperatura específica da classificação (mais conservadora)
        try:
            self.classify_temperature = float(os.environ.get('OPENAI_TEMPERATURE_CLASSIFY', '0.2'))
        except ValueError:
            self.classify_temperature = 0.2
        
        # Temperatura para análise (mais criativa)
        try:
            self.analysis_temperature = float(os.environ.get('OPENAI_TEMPERATURE_ANALYSIS', '0.3'))
        except ValueError:
            self.analysis_temperature = 0.3
        
        # Mensagem de sistema para orientar estilo/estrutura
        self.system_message = (
            "Você é um analista médico especializado em cardiologia. Responda sempre com máximo rigor,"
            " concisão e foco clínico. Siga estritamente a estrutura exigida pelo prompt do usuário."
            " Evite floreios; cite números e limitações. Gere uma nota de aplicabilidade clínica de 0 a 10"
            " obrigatoriamente no formato 'Nota de aplicabilidade clínica: X/10'."
        )
    
    def _get_model_for_type(self, article_type):
        """Retorna o modelo apropriado para o tipo de artigo."""
        return self.model_config.get(article_type, 'gemini-2.5-pro')
    
    def _is_claude_model(self, model_name):
        """Verifica se é um modelo Claude."""
        return 'claude' in model_name.lower()

    def _should_fallback_from_claude(self, error: Exception) -> bool:
        """Heurística: decide se deve fazer fallback do Claude para Gemini.

        A ideia é não travar o lote quando Claude estiver indisponível (quota/crédito/rate-limit),
        mas também ser tolerante a falhas transitórias.
        """
        msg = (str(error) or "").lower()
        keywords = (
            "quota",
            "credit",
            "billing",
            "payment",
            "insufficient",
            "rate limit",
            "rate_limit",
            "429",
            "too many requests",
            "overloaded",
            "temporarily",
            "timeout",
            "timed out",
            "service unavailable",
            "503",
            "connection",
            "network",
            "too long",
            "prompt is too long",
        )
        return any(k in msg for k in keywords)
    
    def _call_claude(self, model_name, prompt, system_message=None, temperature=0.3, max_tokens=16000):
        """
        Chama o modelo Claude usando SDK da Anthropic.
        
        Args:
            model_name: Nome do modelo (claude-sonnet-4-5-20250929, etc.)
            prompt: Prompt do usuário
            system_message: Mensagem de sistema
            temperature: Temperatura de geração
            max_tokens: Máximo de tokens na resposta
        
        Returns:
            Texto da resposta
        """
        if not anthropic_client:
            raise ValueError("Cliente Anthropic não está configurado")
        
        # Retry automático para falhas de rede/API (internet instável)
        delays = [15, 45, 120]  # 15s, 45s, 2min
        last_exc = None
        for attempt, delay in enumerate(delays + [0], 1):
            try:
                message = anthropic_client.messages.create(
                    model=model_name,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    system=system_message if system_message else "",
                    messages=[{"role": "user", "content": prompt}]
                )
                return message.content[0].text
            except Exception as e:
                last_exc = e
                if attempt <= len(delays):
                    print(f"   ⚠️  Claude tentativa {attempt} falhou ({type(e).__name__}). Aguardando {delay}s...")
                    time.sleep(delay)
                else:
                    raise last_exc
    
    def _call_gemini(self, model_name, prompt, system_message=None, temperature=0.3, max_tokens=16000):
        """
        Chama o modelo Gemini usando SDK nativo.
        
        Args:
            model_name: Nome do modelo (gemini-2.5-pro, claude-sonnet-4-5, etc.)
            prompt: Prompt do usuário
            system_message: Mensagem de sistema (será concatenada ao prompt)
            temperature: Temperatura de geração
            max_tokens: Máximo de tokens na resposta
        
        Returns:
            Texto da resposta
        """
        if not gemini_client:
            raise ValueError("Gemini não está configurado")
        
        try:
            # Tentar usar NOVA API (google.genai)
            if hasattr(gemini_client, 'models'):
                # Nova API do google.genai
                response = gemini_client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=temperature,
                        max_output_tokens=max_tokens,
                        system_instruction=system_message if system_message else None,
                    )
                )
                
                # Verificar se resposta foi cortada por MAX_TOKENS
                if response.candidates and len(response.candidates) > 0:
                    finish_reason = response.candidates[0].finish_reason
                    if finish_reason == 'MAX_TOKENS':
                        print(f"   ⚠️  Resposta cortada por MAX_TOKENS (usado: {max_tokens}). Considere aumentar max_tokens.")
                    
                    # Tentar extrair texto mesmo se resposta foi None
                    if response.text is None:
                        # Tentar extrair de candidates
                        if response.candidates[0].content and response.candidates[0].content.parts:
                            parts_text = []
                            for part in response.candidates[0].content.parts:
                                if hasattr(part, 'text') and part.text:
                                    parts_text.append(part.text)
                            if parts_text:
                                return ''.join(parts_text)
                        
                        print(f"   ⚠️  Gemini retornou resposta vazia (finish_reason: {finish_reason})")
                        return None
                
                return response.text
            else:
                # API antiga (google.generativeai) - DEPRECATED
                from google.generativeai.types import HarmCategory, HarmBlockThreshold
                
                # Configurar o modelo com safety settings mais permissivos para conteúdo médico
                generation_config = genai.GenerationConfig(
                    temperature=temperature,
                    max_output_tokens=max_tokens,
                )
                
                # Safety settings permissivos para conteúdo médico/científico
                safety_settings = {
                    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
                }
                
                model = genai.GenerativeModel(
                    model_name=model_name,
                    generation_config=generation_config,
                    system_instruction=system_message if system_message else None,
                    safety_settings=safety_settings
                )
                
                # Gerar resposta
                response = model.generate_content(prompt)
                return response.text
                
        except Exception as e:
            print(f"⚠️  Erro ao chamar Gemini: {e}")
            raise

    def _call_gemini_with_retry(self, model_name, prompt, system_message=None, temperature=0.3, max_tokens=16000):
        """Wrapper do _call_gemini com retry automático para falhas de rede."""
        delays = [15, 45, 120]
        last_exc = None
        for attempt, delay in enumerate(delays + [0], 1):
            try:
                return self._call_gemini(model_name, prompt, system_message, temperature, max_tokens)
            except Exception as e:
                last_exc = e
                msg = str(e).lower()
                # Só retentar em erros de rede/rate-limit — não em erros de conteúdo
                if any(k in msg for k in ("connection", "network", "timeout", "503", "502", "429", "rate", "overload", "temporarily")):
                    if attempt <= len(delays):
                        print(f"   ⚠️  Gemini tentativa {attempt} falhou ({type(e).__name__}). Aguardando {delay}s...")
                        time.sleep(delay)
                    else:
                        raise last_exc
                else:
                    raise  # Erros não-recuperáveis: falha imediata

    def _call_model(self, model_name, prompt, system_message=None, temperature=0.3, max_tokens=16000):
        """
        Chama o modelo apropriado baseado no nome.
        
        Esta é a função principal que roteia para Claude, Gemini ou OpenAI.
        """
        # Se é modelo Claude
        if self._is_claude_model(model_name):
            if self.use_claude:
                try:
                    return self._call_claude(model_name, prompt, system_message, temperature, max_tokens)
                except Exception as e:
                    # Não parar o lote por falha do Claude (ex.: quota/crédito/rate-limit)
                    if self.use_gemini and self._should_fallback_from_claude(e):
                        print(f"   ⚠️  Claude falhou ({type(e).__name__}: {e}); usando Gemini 2.5 Pro como fallback...")
                        return self._call_gemini('gemini-2.5-pro', prompt, system_message, temperature, max_tokens)
                    raise
            else:
                print("   ⚠️  Claude não disponível; usando Gemini 2.5 Pro como fallback...")
                return self._call_gemini('gemini-2.5-pro', prompt, system_message, temperature, max_tokens)
        
        # Se é modelo Gemini
        if 'gemini' in model_name.lower():
            if self.use_gemini:
                return self._call_gemini_with_retry(model_name, prompt, system_message, temperature, max_tokens)
            else:
                print(f"   ⚠️  Gemini não disponível, usando OpenAI como fallback...")
                return self._call_openai_fallback(self.fallback_model, prompt, system_message, temperature, max_tokens)
        
        # Fallback para OpenAI
        return self._call_openai_fallback(model_name, prompt, system_message, temperature, max_tokens)
    
    def _call_openai_fallback(self, model_name, prompt, system_message=None, temperature=0.3, max_tokens=8000):
        """Fallback para OpenAI quando Gemini não está disponível."""
        messages = []
        if system_message:
            messages.append({"role": "system", "content": system_message})
        messages.append({"role": "user", "content": prompt})
        
        response = openai_client.chat.completions.create(
            model=model_name,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens
        )
        return response.choices[0].message.content
    
    def _load_prompts(self):
        """Carrega os prompts personalizados (v2 com prompts completos)."""
        try:
            # Tentar carregar prompts v2 (completos) primeiro
            try:
                from prompts_config_v2 import PROMPTS, get_prompt, validate_prompts
                self.prompts = PROMPTS
                self._get_prompt = get_prompt
                
                # Validar prompts carregados
                status = validate_prompts()
                valid_count = sum(1 for s in status.values() if s.get('exists') and s.get('length', 0) > 1000)
                print(f"   ✅ {len(self.prompts)} prompts carregados de prompts_config_v2.py ({valid_count} completos)")
                
            except ImportError:
                # Fallback para versão antiga
                try:
                    from prompts_config_LIMPO import PROMPTS
                except ImportError:
                    import sys
                    sys.path.append(os.getcwd())
                    from prompts_config_LIMPO import PROMPTS
                
                self.prompts = PROMPTS
                self._get_prompt = lambda t: PROMPTS.get(t)
                print(f"   ⚠️  {len(self.prompts)} prompts carregados de prompts_config_LIMPO.py (fallback)")
            
        except Exception as e:
            print(f"   ❌ Erro ao carregar prompts: {e}")
            self.prompts = {}
            self._get_prompt = lambda t: None
    
    def _setup_podcast_generators(self):
        """Inicializa os geradores de podcast."""
        # Permite desabilitar geração de podcast/áudio (útil para rodadas focadas só em indexação)
        disable_podcast = os.environ.get('CARDIODAILY_DISABLE_PODCAST', '').strip().lower() in {
            '1', 'true', 'yes', 'y', 'on'
        }
        if disable_podcast:
            self.podcast_script_generator = None
            self.audio_generator = None
            self.audio_enabled = False
            print("   ⚠️  Podcast/áudio desabilitados (CARDIODAILY_DISABLE_PODCAST=1)")
            return

        try:
            self.podcast_script_generator = PodcastScriptGenerator()
            print("   ✅ Gerador de script de podcast inicializado")
            
            # Tentar inicializar gerador de áudio (unificado ou ElevenLabs)
            try:
                if UNIFIED_AUDIO_AVAILABLE:
                    # Usar sistema unificado (escolhe OpenAI ou ElevenLabs via env)
                    self.audio_generator = UnifiedAudioGenerator()
                    provider = os.environ.get('CARDIODAILY_AUDIO_PROVIDER', 'elevenlabs')
                    self.audio_enabled = True
                    print(f"   ✅ Gerador de áudio inicializado (provider: {provider})")
                elif ElevenLabsAudioGenerator:
                    # Fallback para ElevenLabs direto
                    self.audio_generator = ElevenLabsAudioGenerator()
                    self.audio_enabled = True
                    print("   ✅ Gerador de áudio ElevenLabs inicializado")
                else:
                    raise ValueError("Nenhum gerador de áudio disponível")
            except ValueError as e:
                self.audio_generator = None
                self.audio_enabled = False
                print(f"   ⚠️  Geração de áudio desabilitada: {e}")
                
        except Exception as e:
            print(f"   ⚠️  Erro ao inicializar geradores de podcast: {e}")
            self.podcast_script_generator = None
            self.audio_generator = None
            self.audio_enabled = False

        # Geração de imagens DALL-E removida (v9.1)

    def _setup_infographic_generator(self):
        """Inicializa VisualAbstractGenerator (template oficial 8 seções)."""
        # InfographicPortrait (VisualMed) DESATIVADO — substituído pelo Visual Abstract
        self.infographic_generator = None
        self.infographic_enabled = False

        if VISUAL_ABSTRACT_AVAILABLE:
            try:
                self.visual_abstract_generator = VisualAbstractGenerator()
                self.visual_abstract_enabled = True
                print("✅ VisualAbstractGenerator (Claude Sonnet 4 + Playwright) inicializado")
            except Exception as e:
                print(f"   ⚠️  VisualAbstractGenerator desabilitado: {e}")
                self.visual_abstract_generator = None
                self.visual_abstract_enabled = False
        else:
            self.visual_abstract_generator = None
            self.visual_abstract_enabled = False

    def _setup_mindmap_generator(self):
        """Mapa mental visual DESATIVADO — único artefato visual permitido é o Visual Abstract."""
        self.mindmap_generator = None
        self.mindmap_enabled = False

    def classify_article_type(self, text, file_path=None, filename=None, doi=None):
        """
        Classifica o tipo de artigo usando CLASSIFICADOR ROBUSTO.
        
        ESTRATÉGIA EM CAMADAS:
        1. Pasta do arquivo (100% certeza)
        2. CrossRef/PubMed via DOI (99% certeza)
        3. Regras determinísticas no texto (95% certeza)
        4. LLM com checklist estruturado (85% certeza)
        
        Args:
            text: Texto do artigo
            file_path: Caminho completo do arquivo
            filename: Nome do arquivo
            doi: DOI do artigo (se conhecido)
        
        Returns:
            Tipo do artigo (artigo_original, revisao_geral, etc.)
        """
        # Extrair filename do path se não fornecido
        if not filename and file_path:
            filename = os.path.basename(file_path)
        
        # ========== USAR CLASSIFICADOR ROBUSTO SE DISPONÍVEL ==========
        if ROBUST_CLASSIFIER_AVAILABLE:
            print("   🔬 Usando Classificador Robusto v1.0")
            
            # Criar função wrapper para chamar LLM
            def llm_call(prompt):
                try:
                    return self._call_model(
                        model_name='gemini-2.5-pro',
                        prompt=prompt,
                        temperature=0.1,
                        max_tokens=8000  # Gemini 2.5 Pro usa thinking tokens internos (~5k), mais ~3k para resposta
                    )
                except Exception as e:
                    print(f"      ⚠️ Erro ao chamar LLM: {e}")
                    return None
            
            # Inicializar classificador
            classifier = RobustClassifier(
                llm_call_function=llm_call,
                use_crossref=True,
                verbose=True
            )
            
            # Classificar
            tipo, confianca, motivo, camada = classifier.classify(
                text=text,
                file_path=file_path,
                filename=filename,
                doi=doi
            )
            
            print(f"   📊 Resultado: {tipo} [Confiança: {confianca:.0%}] [Camada: {camada}]")
            
            return tipo
        
        # ========== FALLBACK: CLASSIFICADOR BÁSICO ==========
        print("   ⚠️ Usando classificador básico (robust_classifier não disponível)")
        return self._classify_basic(text, file_path, filename)
    
    def _classify_basic(self, text, file_path=None, filename=None):
        """
        Classificador básico de fallback (versão simplificada).
        """
        import re
        
        if not filename and file_path:
            filename = os.path.basename(file_path)
        
        # Verificar pasta
        if file_path:
            path_lower = file_path.lower()
            if 'meta_analises' in path_lower or 'meta-analises' in path_lower:
                return 'revisao_sistematica_meta_analise'
            if 'revisoes' in path_lower or 'reviews' in path_lower:
                return 'revisao_geral'
            if 'guidelines' in path_lower or 'diretrizes' in path_lower:
                return 'guideline'
            if 'artigos_originais' in path_lower or 'originais' in path_lower:
                return 'artigo_original'
        
        # Verificar nome do arquivo
        if filename:
            filename_lower = filename.lower()
            if 'meta-analysis' in filename_lower or 'metanalise' in filename_lower:
                return 'revisao_sistematica_meta_analise'
            if 'systematic review' in filename_lower:
                return 'revisao_sistematica_meta_analise'
            if 'guideline' in filename_lower:
                return 'guideline'
        
        # Verificar texto
        text_lower = text.lower() if text else ""
        
        # Meta-análise
        meta_indicators = ['forest plot', 'funnel plot', 'prisma', 'prospero', 'pooled analysis']
        if sum(1 for ind in meta_indicators if ind in text_lower) >= 2:
            return 'revisao_sistematica_meta_analise'
        
        # Guideline
        if 'class i' in text_lower and 'level of evidence' in text_lower:
            return 'guideline'
        
        # Original
        original_indicators = ['we enrolled', 'we recruited', 'patients were randomized', 'primary endpoint']
        if sum(1 for ind in original_indicators if ind in text_lower) >= 2:
            return 'artigo_original'
        
        # Default
        return 'artigo_original'
    
    def classify_disease(self, text, filename=None):
        """
        Classifica a doença/tema principal do artigo usando a taxonomia em inglês (73 categorias).

        Usa LLM para determinar a categoria mais apropriada.
        O resultado é salvo no campo `doenca_principal` para compatibilidade com o banco.

        Args:
            text: Texto do artigo (ou primeiros ~5000 chars)
            filename: Nome do arquivo (usado como título fallback)

        Returns:
            Dicionário com doenca_principal, populacao e intervencao
        """
        # Extrair título do texto (primeira linha com #) ou usar filename
        title = filename or ""
        if text:
            title_match = re.search(r'^#\s+(.+)$', text, re.MULTILINE)
            if title_match:
                title = title_match.group(1).strip()

        # Limitar conteúdo enviado ao LLM
        content_snippet = text[:5000] if text else title

        prompt = PROMPT_CLASSIFICATION.format(
            categories=", ".join(TAXONOMY_CATEGORIES),
            title=title,
            content=content_snippet,
        )

        try:
            response_text = self._call_model(
                model_name='gemini-2.5-pro',
                prompt=prompt,
                temperature=0.1,
                max_tokens=8000,  # Gemini 2.5 Pro usa thinking tokens internos (~5k), mais ~3k para resposta
            )

            if not response_text:
                print("   ⚠️  LLM retornou vazio na classificação de doença")
                return {"doenca_principal": "Other", "populacao": [], "intervencao": []}

            # Limpar markdown fences
            clean = re.sub(r'```json\n?|```\n?', '', response_text).strip()
            tags = json.loads(clean)

            category = tags.get("category", "Outros")
            # validate_category faz migração automática de categorias antigas
            category = _validate_category(category)

            palavras_chave = tags.get("palavras_chave", [])
            if isinstance(palavras_chave, list):
                palavras_chave = [str(k).strip() for k in palavras_chave if k][:3]
            else:
                palavras_chave = []

            return {
                "doenca_principal": category,
                "palavras_chave": palavras_chave,
                "populacao": tags.get("population", []),
                "intervencao": tags.get("intervention", []),
            }

        except json.JSONDecodeError as e:
            print(f"   ⚠️  Erro ao parsear JSON de classificação: {e}")
            return {"doenca_principal": "Other", "populacao": [], "intervencao": []}
        except Exception as e:
            print(f"   ⚠️  Erro na classificação de doença: {e}")
            return {"doenca_principal": "Other", "populacao": [], "intervencao": []}

    def analyze_article(self, text, article_type):
        """
        Analisa o artigo usando o prompt apropriado.
        
        Args:
            text: Texto completo do artigo
            article_type: Tipo do artigo
        
        Returns:
            Dicionário com análise completa e score
        """
        try:
            # Obter prompt apropriado
            # Suporte a aliases para facilitar atualização/colagem de prompts
            prompt_key_aliases = {
                'artigo_original': ['original', 'artigo', 'artigo-original'],
                'revisao_sistematica_meta_analise': [
                    'metanalise', 'meta_analise', 'meta_analises', 'meta-analise',
                    'revisao_sistematica', 'revisao_sistematica_metaanalise'
                ],
                'revisao_geral': ['revisao', 'review', 'revisao_narrativa'],
                'guideline': ['diretriz', 'guidelines', 'consenso'],
                'ponto_de_vista': ['editorial', 'perspectiva', 'viewpoint'],
            }

            # Usar função _get_prompt se disponível (resolve aliases automaticamente)
            if hasattr(self, '_get_prompt') and callable(self._get_prompt):
                prompt_template = self._get_prompt(article_type)
            else:
                prompt_template = self.prompts.get(article_type)
                if not prompt_template:
                    for alias in prompt_key_aliases.get(article_type, []):
                        prompt_template = self.prompts.get(alias)
                        if prompt_template:
                            print(f"   ℹ️  Usando prompt alias '{alias}' para tipo '{article_type}'")
                            break
            
            if not prompt_template:
                print(f"   ⚠️  Prompt não encontrado para {article_type}")
                return None
            
            # Validar que o prompt tem tamanho mínimo (evitar prompts incompletos)
            if len(prompt_template) < 500:
                print(f"   ⚠️  Prompt muito curto para {article_type} ({len(prompt_template)} chars) - pode estar incompleto")
            else:
                print(f"   📋 Prompt carregado: {len(prompt_template):,} caracteres")
            
            # SELECIONAR MODELO BASEADO NO TIPO DE ARTIGO
            analysis_model = self._get_model_for_type(article_type)
            
            print(f"   🎯 Modelo selecionado: {analysis_model}")
            
            # Limitar tamanho do texto baseado no modelo/provider
            # Claude: ~200k tokens, Gemini: ~1M tokens, OpenAI: ~128k tokens
            is_claude = analysis_model.startswith('claude')
            MAX_CHARS = 400000 if is_claude else (800000 if self.use_gemini else 500000)
            
            if len(text) > MAX_CHARS:
                print(f"   ⚠️  Texto muito grande ({len(text):,} caracteres)")
                print(f"   ✂️  Truncando para {MAX_CHARS:,} caracteres...")
                text = text[:MAX_CHARS]
            
            # Preparar mensagens (onde o Prompt-Mestre entra pode mudar o resultado).
            # Para preservar compatibilidade, isso é configurável via env.
            prompt_mode = os.environ.get('CARDIODAILY_PROMPT_MODE', 'system_only').strip().lower()

            if prompt_mode == 'system_plus_base':
                system_msg = f"{self.system_message}\n\n{prompt_template}"
                user_prompt = f"POR FAVOR, ANALISE O SEGUINTE ARTIGO CIENTÍFICO:\n\n{text}"
            elif prompt_mode == 'user':
                system_msg = self.system_message
                user_prompt = f"{prompt_template}\n\nPOR FAVOR, ANALISE O SEGUINTE ARTIGO CIENTÍFICO:\n\n{text}"
            else:
                # Padrão: Prompt-Mestre no system (sem concatenar a mensagem base).
                # Isto tende a reproduzir melhor o comportamento do analisador legado.
                system_msg = prompt_template
                user_prompt = f"POR FAVOR, ANALISE O SEGUINTE ARTIGO CIENTÍFICO:\n\n{text}"
            
            # Identificar provider para logging
            if is_claude:
                provider_name = "Claude Sonnet 4"
            elif self.use_gemini:
                provider_name = "Gemini"
            else:
                provider_name = "OpenAI"
            
            estimated_tokens = (len(text) + len(system_msg or '')) // 4
            print(f"   🤖 Enviando para {provider_name} (modelo: {analysis_model})...")
            print(f"   🔑 Modo de prompt: {prompt_mode} (Prompt-Mestre {'no system' if prompt_mode != 'user' else 'no user'})")
            print(f"   📝 Tamanho do texto: {len(text):,} caracteres")
            print(f"   📊 Tokens estimados: ~{estimated_tokens:,}")
            
            # Configurar max_tokens baseado no provider
            try:
                env_max_tokens = int(os.environ.get('OPENAI_MAX_TOKENS', '16000'))
            except ValueError:
                env_max_tokens = 16000
            
            # Claude Sonnet suporta até 8192 output tokens, Gemini até 32k
            if is_claude:
                safe_max_tokens = max(256, min(env_max_tokens, 8000))
            elif self.use_gemini:
                safe_max_tokens = max(256, min(env_max_tokens, 32000))
            else:
                safe_max_tokens = max(256, min(env_max_tokens, 16000))

            # CHAMADA À API - Primeira passada
            draft = self._call_model(
                model_name=analysis_model,
                prompt=user_prompt,
                system_message=system_msg,
                temperature=self.analysis_temperature,
                max_tokens=safe_max_tokens
            )

            # Segunda passada (revisão, opcional) - DESLIGADA por padrão.
            # Motivo: o reviewer antigo adicionava exigências (MindNode, Pérolas etc.) que conflitam
            # com os novos Prompts-Mestre e pioram o resultado.
            enable_review = os.environ.get('OPENAI_ENABLE_REVIEW', '0') != '0'
            print(f"   🔁 Segunda passada (review): {'ON' if enable_review else 'OFF'}")
            if enable_review:
                reviewer_system = (
                    "Você é um revisor clínico extremamente rigoroso. Seu objetivo é melhorar CLAREZA,"
                    " COMPLETUDE e FIDELIDADE AO PROMPT-MESTRE.\n\n"
                    "REGRAS:\n"
                    "1) Preserve EXATAMENTE a estrutura/títulos/blocos exigidos no Prompt-Mestre.\n"
                    "2) Não invente dados, doses ou números ausentes do texto original.\n"
                    "3) Se faltar dado essencial, explicite como 'não informado'.\n"
                    "4) Mantenha foco em aplicabilidade clínica e números quando disponíveis.\n"
                    "5) Não adicione seções novas que NÃO estejam no Prompt-Mestre."
                )

                reviewer_prompt = (
                    "REESCREVA E MELHORE O RASCUNHO ABAIXO, SEGUINDO ESTRITAMENTE O PROMPT-MESTRE.\n\n"
                    "=== RASCUNHO ===\n"
                    f"{draft}"
                )

                # Usa _call_model para rotear automaticamente, mantendo o Prompt-Mestre como system.
                analysis_text = self._call_model(
                    model_name=analysis_model,
                    prompt=reviewer_prompt,
                    system_message=f"{system_msg}\n\n{reviewer_system}",
                    temperature=min(self.default_temperature, 0.25),
                    max_tokens=safe_max_tokens
                )
            else:
                analysis_text = draft
            
            print(f"   ✅ Análise gerada: {len(analysis_text):,} caracteres")
            
            # Extrair score da análise
            score = self._extract_score(analysis_text)
            
            return {
                'analysis': analysis_text,
                'score': score,
                'article_type': article_type,
                'model_used': analysis_model,
            }
            
        except Exception as e:
            print(f"   ❌ Erro na análise: {e}")
            return None

    def _write_failure_package(
        self,
        *,
        article_dir: str,
        filename: str,
        doc_id: str,
        pdf_sha256: str | None,
        doi_clean: str | None,
        article_type: str | None,
        stage: str,
        error_message: str,
    ) -> None:
        try:
            os.makedirs(article_dir, exist_ok=True)
            os.makedirs(os.path.join(article_dir, "assets"), exist_ok=True)

            analysis_dt = now_iso_brt()
            subtype = article_type or "unknown"
            canonical_type = canonical_type_for(subtype) if article_type else "unknown"
            doi_yaml = doi_clean if doi_clean else 'null'

            md_path = os.path.join(article_dir, "analysis.md")
            json_path = os.path.join(article_dir, "analysis.json")

            _pub_date = extract_pub_date_from_filename(filename)
            md = (
                "---\n"
                f"doc_id: \"{doc_id}\"\n"
                f"source_pdf: \"{filename}\"\n"
                f"doi: \"{doi_yaml}\"\n"
                f"pdf_sha256: \"{pdf_sha256 or 'null'}\"\n"
                f"type: \"{canonical_type}\"\n"
                f"subtype: \"{subtype}\"\n"
                f"data_publicacao: \"{_pub_date}\"\n"
                f"analysis_datetime: \"{analysis_dt}\"\n"
                "nota_aplicabilidade: null\n"
                "generator: \"CardioDaily ArticleAnalyzer\"\n"
                "generator_version: \"2026.01\"\n"
                "schema_version: 1\n"
                "language: \"pt-BR\"\n"
                "status: \"failed\"\n"
                f"failed_stage: \"{stage}\"\n"
                "---\n\n"
                f"# Análise (falha): {filename}\n\n"
                f"**doc_id:** {doc_id}\n\n"
                f"**DOI:** {doi_clean if doi_clean else 'Não encontrado'}\n\n"
                f"**Etapa:** {stage}\n\n"
                "O processamento deste PDF não concluiu a análise.\n\n"
                f"**Erro:** {error_message}\n"
            )

            tmp_md = md_path + ".tmp"
            with open(tmp_md, 'w', encoding='utf-8') as f:
                f.write(md)
            os.replace(tmp_md, md_path)

            analysis_json = {
                "schema_version": 1,
                "doc_id": doc_id,
                "source": {
                    "pdf_filename": filename,
                    "pdf_sha256": pdf_sha256,
                    "doi": doi_clean,
                    "journal": extract_journal(pdf_filename=filename),
                },
                "classification": {
                    "type": canonical_type,
                    "subtype": subtype,
                    "model_used": None,
                    "classifier": {
                        "final_label": subtype,
                    },
                },
                "analysis": {
                    "analysis_datetime": analysis_dt,
                    "language": "pt-BR",
                    "status": "failed",
                    "failed_stage": stage,
                    "error": error_message,
                    "scores": {
                        "aplicabilidade": None,
                    },
                },
                "media": {
                    "audio_status": None,
                    "image_status": None,
                },
                "artifacts": {
                    "article_dir": os.path.relpath(article_dir, self.output_base_dir),
                    "source_pdf": "source.pdf",
                    "analysis_md": "analysis.md",
                    "analysis_json": "analysis.json",
                    "assets_dir": "assets/",
                },
                "provenance": {
                    "generator": "CardioDaily ArticleAnalyzer",
                    "generator_version": "2026.01",
                },
            }

            tmp_json = json_path + ".tmp"
            with open(tmp_json, 'w', encoding='utf-8') as jf:
                json.dump(analysis_json, jf, ensure_ascii=False, indent=2)
            os.replace(tmp_json, json_path)
        except Exception:
            # Nunca deixar a exceção do salvamento mascarar a exceção raiz.
            return

    def _export_analysis_to_markdown_folder(self, *, article_type: str, doc_id: str, filename: str, md_path: str) -> None:
        try:
            base_name = os.path.splitext(os.path.basename(filename))[0]
            safe_base = re.sub(r"[^A-Za-z0-9._ -]+", "_", base_name).strip() or "artigo"

            if article_type == 'artigo_original':
                md_dir = self.dirs.get('markdown_artigos_originais', self.dirs.get('markdown'))
            elif article_type == 'revisao_sistematica_meta_analise':
                md_dir = self.dirs.get('markdown_meta_analises', self.dirs.get('markdown'))
            else:
                md_dir = self.dirs.get('markdown_revisoes', self.dirs.get('markdown'))

            if not md_dir:
                return

            os.makedirs(md_dir, exist_ok=True)
            dest = os.path.join(md_dir, f"{doc_id}__{safe_base}.md")

            if os.path.exists(dest):
                return

            try:
                os.symlink(os.path.relpath(md_path, md_dir), dest)
            except Exception:
                shutil.copy2(md_path, dest)
        except Exception:
            return
    
    def _extract_score(self, analysis_text):
        """
        Extrai a NOTA DE APLICABILIDADE CLÍNICA da análise (0–10).
        Suporta os formatos gerados pelo AI:
          - "Nota de aplicabilidade clínica: 8/10"
          - "| **Nota de aplicabilidade clínica** | **8**/10 |"  (tabela markdown)
          - "Nota de aplicabilidade clínica: X/10" no system_message
        """
        # Padrões em ordem de especificidade — param no primeiro match válido.
        # \*{0,2} captura markdown bold opcional ao redor do número.
        patterns = [
            r'Nota de aplicabilidade cl[ií]nica[^0-9]{0,40}\*{0,2}(\d+)\*{0,2}/10',
            r'Aplicabilidade cl[ií]nica[^0-9]{0,40}\*{0,2}(\d+)\*{0,2}/10',
            r'Nota de aplicabilidade[^0-9]{0,40}\*{0,2}(\d+)\*{0,2}/10',
        ]

        for pattern in patterns:
            match = re.search(pattern, analysis_text, re.IGNORECASE)
            if match:
                score = int(match.group(1))
                if 0 <= score <= 10:
                    return score

        print("   ⚠️  Nota de aplicabilidade clínica não encontrada na análise, usando 0")
        return 0
    
    def process_article(self, file_info):
        """
        Processa um único artigo completo.
        
        Args:
            file_info: Informações do arquivo do Google Drive
        
        Returns:
            True se processado com sucesso, False caso contrário
        """
        filename = file_info['name']
        base_name = os.path.splitext(filename)[0]
        is_local = file_info.get('local', False)
        file_id = file_info.get('id')
        
        print("\n" + "=" * 80)
        print(f"📄 PROCESSANDO: {filename}")
        print("=" * 80)
        
        try:
            stage = "start"
            article_type = None
            canonical_type = None
            # 1. Download do PDF
            if is_local:
                print("\n1️⃣ Usando PDF local...")
                pdf_path = file_info['path']
                if not os.path.isfile(pdf_path):
                    print("   ❌ Arquivo local não encontrado")
                    return False
            else:
                print("\n1️⃣ Baixando PDF...")
                pdf_path = os.path.join(self.dirs['downloads'], filename)
                
                if not self.drive_manager or not self.drive_manager.download_file(file_id, pdf_path):
                    print("   ❌ Falha no download")
                    return False

            # 1b. Hash do PDF para rastreabilidade
            print("\n1️⃣🔒 Calculando hash SHA-256 do PDF...")
            pdf_sha256 = sha256_file(pdf_path)
            print(f"   ✅ pdf_sha256: {pdf_sha256}")
            
            # ========== VERIFICAÇÃO PRECOCE DE DUPLICATAS ==========
            # Verificar SE JÁ FOI PROCESSADO antes de fazer qualquer trabalho pesado
            force_reanalyze = os.environ.get('CARDIODAILY_FORCE_REANALYZE', '0') == '1'
            
            if not force_reanalyze:
                # Gerar doc_id provisório baseado no hash (sem precisar extrair DOI)
                doc_id_by_hash = f"pdf_{pdf_sha256[:16]}"
                possible_article_dir = os.path.join(self.corpus_dir, doc_id_by_hash)
                possible_analysis_md = os.path.join(possible_article_dir, "analysis.md")
                possible_analysis_json = os.path.join(possible_article_dir, "analysis.json")
                
                if os.path.exists(possible_analysis_md) and os.path.exists(possible_analysis_json):
                    print(f"   ⏭️  JÁ PROCESSADO (hash match): {doc_id_by_hash}")
                    print(f"   💡 Use CARDIODAILY_FORCE_REANALYZE=1 para reprocessar")
                    return False
            
            # 2. Extrair DOI
            print("\n2️⃣ Extraindo DOI...")
            doi_raw = self.doi_tracker.extract_doi_from_pdf(pdf_path)
            doi_clean = sanitize_doi(doi_raw) if doi_raw else None
            
            # 2b. Criar doc_id determinístico e pasta canônica do artigo (sempre)
            doc_id = make_doc_id(doi_clean=doi_clean, pdf_sha256=pdf_sha256)
            article_dir = os.path.join(self.corpus_dir, doc_id)
            
            # ========== SEGUNDA VERIFICAÇÃO (com doc_id final) ==========
            if not force_reanalyze:
                analysis_md_path = os.path.join(article_dir, "analysis.md")
                analysis_json_path = os.path.join(article_dir, "analysis.json")
                
                if os.path.exists(analysis_md_path) and os.path.exists(analysis_json_path):
                    print(f"   ⏭️  JÁ PROCESSADO: {doc_id}")
                    print(f"   💡 Use CARDIODAILY_FORCE_REANALYZE=1 para reprocessar")
                    return False
            
            assets_dir = os.path.join(article_dir, "assets")
            os.makedirs(assets_dir, exist_ok=True)
            stage = "package_initialized"

            # Copiar PDF final para o pacote (sem sobrescrever se já existe)
            source_pdf_dst = os.path.join(article_dir, "source.pdf")
            if force_reanalyze or not os.path.exists(source_pdf_dst):
                shutil.copy2(pdf_path, source_pdf_dst)
            print(f"   📦 Pacote: {os.path.relpath(article_dir, self.output_base_dir)}")

            if doi_clean:
                print(f"   ✅ DOI encontrado: {doi_clean}")

                # Verificar se já foi analisado
                if self.doi_tracker.is_analyzed(doi_clean) and not force_reanalyze:
                    print(f"   ⚠️  Artigo já analisado anteriormente (DOI: {doi_clean})")
                    existing = None
                    try:
                        existing = self.doi_tracker.get_article(doi_clean)
                    except Exception:
                        existing = None

                    analysis_md_existing = os.path.join(article_dir, "analysis.md")
                    analysis_json_existing = os.path.join(article_dir, "analysis.json")

                    if existing and existing.get('summary_path'):
                        print(f"   📄 Resumo existente: {existing['summary_path']}")

                    # Se o pacote canônico já existe, não sobrescrever nada (idempotente)
                    if os.path.exists(analysis_md_existing) and os.path.exists(analysis_json_existing):
                        print("   ✅ Pacote canônico já existe; não sobrescrevendo")
                        print("   💡 Dica: defina CARDIODAILY_FORCE_REANALYZE=1 para reprocessar")
                        print("   ⏭️  Pulando para o próximo...")
                        return False

                    # Caso o pacote ainda não exista (ex.: rodadas antigas), criar stub apontando para o resumo existente
                    existing_article_type = (existing or {}).get('article_type') or "unknown"
                    existing_score = (existing or {}).get('score')
                    canonical_type = canonical_type_for(existing_article_type)
                    analysis_dt = now_iso_brt()

                    _pub_date = extract_pub_date_from_filename(filename)
                    md_stub = (
                        "---\n"
                        f"doc_id: \"{doc_id}\"\n"
                        f"source_pdf: \"{filename}\"\n"
                        f"doi: \"{doi_clean}\"\n"
                        f"pdf_sha256: \"{pdf_sha256}\"\n"
                        f"type: \"{canonical_type}\"\n"
                        f"subtype: \"{existing_article_type}\"\n"
                        f"data_publicacao: \"{_pub_date}\"\n"
                        f"analysis_datetime: \"{analysis_dt}\"\n"
                        f"nota_aplicabilidade: {existing_score if existing_score is not None else 'null'}\n"
                        "generator: \"CardioDaily ArticleAnalyzer\"\n"
                        "generator_version: \"2026.01\"\n"
                        "schema_version: 1\n"
                        "language: \"pt-BR\"\n"
                        "---\n\n"
                        f"# Análise (duplicata): {filename}\n\n"
                        f"**doc_id:** {doc_id}\n\n"
                        f"**DOI:** {doi_clean}\n\n"
                        "Este artigo já foi analisado anteriormente; esta execução não reprocessou o conteúdo.\n\n"
                    )

                    if existing and existing.get('summary_path'):
                        md_stub += f"Resumo existente: {existing['summary_path']}\n"

                    md_path = os.path.join(article_dir, "analysis.md")
                    with open(md_path, 'w', encoding='utf-8') as mf:
                        mf.write(md_stub)

                    json_path = os.path.join(article_dir, "analysis.json")
                    analysis_json = {
                        "schema_version": 1,
                        "doc_id": doc_id,
                        "source": {
                            "pdf_filename": filename,
                            "pdf_sha256": pdf_sha256,
                            "doi": doi_clean,
                            "journal": extract_journal(pdf_filename=filename),
                        },
                        "classification": {
                            "type": canonical_type,
                            "subtype": existing_article_type,
                            "model_used": None,
                            "classifier": {
                                "final_label": existing_article_type,
                            },
                        },
                        "analysis": {
                            "analysis_datetime": analysis_dt,
                            "language": "pt-BR",
                            "status": "skipped_duplicate",
                            "reference_summary_path": (existing or {}).get('summary_path'),
                            "scores": {
                                "aplicabilidade": int(existing_score) if isinstance(existing_score, (int, float)) else None,
                            },
                        },
                        "media": {
                            "audio_status": None,
                            "image_status": None,
                        },
                        "artifacts": {
                            "article_dir": os.path.relpath(article_dir, self.output_base_dir),
                            "source_pdf": "source.pdf",
                            "analysis_md": "analysis.md",
                            "analysis_json": "analysis.json",
                            "assets_dir": "assets/",
                        },
                        "provenance": {
                            "generator": "CardioDaily ArticleAnalyzer",
                            "generator_version": "2026.01",
                        },
                    }
                    with open(json_path, 'w', encoding='utf-8') as jf:
                        json.dump(analysis_json, jf, ensure_ascii=False, indent=2)

                    print("   ✅ Pacote canônico stub criado para duplicata")
                    print("   💡 Dica: defina CARDIODAILY_FORCE_REANALYZE=1 para reprocessar")
                    print("   ⏭️  Pulando para o próximo...")
                    return False

                if self.doi_tracker.is_analyzed(doi_clean) and force_reanalyze:
                    print(f"   🔁 Reprocessando artigo já analisado (DOI: {doi_clean}) por CARDIODAILY_FORCE_REANALYZE=1")
            else:
                print("   ⚠️  DOI não encontrado, continuando análise...")
            
            # 3. Extrair texto do PDF
            print("\n3️⃣ Extraindo texto do PDF...")
            stage = "extract_text"
            text = self.pdf_extractor.extract_text(pdf_path)
            
            if not text or len(text) < 500:
                print("   ❌ Texto extraído muito curto ou vazio")
                self._write_failure_package(
                    article_dir=article_dir,
                    filename=filename,
                    doc_id=doc_id,
                    pdf_sha256=pdf_sha256,
                    doi_clean=doi_clean,
                    article_type=None,
                    stage="extract_text",
                    error_message="Texto extraído muito curto ou vazio",
                )
                return False
            
            print(f"   ✅ Texto extraído: {len(text):,} caracteres")
            
            # 4. Classificar tipo de artigo
            print("\n4️⃣ Classificando tipo de artigo...")
            stage = "classify"
            # Usar classificador robusto com todas as informações disponíveis
            article_type = self.classify_article_type(
                text=text, 
                file_path=pdf_path, 
                filename=filename,
                doi=doi_clean  # Passa DOI para consulta CrossRef
            )
            print(f"   ✅ Tipo identificado: {article_type}")
            canonical_type = canonical_type_for(article_type)

            # 4b. Classificar doença/tema principal (taxonomia PT-BR, 25 categorias)
            print("\n4️⃣🏷️ Classificando doença/tema principal...")
            stage = "classify_disease"
            disease_tags = self.classify_disease(text=text, filename=filename)
            doenca_principal = disease_tags.get("doenca_principal", "Outros")
            populacao = disease_tags.get("populacao", [])
            intervencao = disease_tags.get("intervencao", [])
            palavras_chave = disease_tags.get("palavras_chave", [])
            print(f"   ✅ Doença principal: {doenca_principal}")

            # 5. Analisar artigo
            print("\n5️⃣ Analisando artigo com IA...")
            stage = "analyze"
            result = self.analyze_article(text, article_type)
            
            if not result:
                print("   ❌ Falha na análise")
                self._write_failure_package(
                    article_dir=article_dir,
                    filename=filename,
                    doc_id=doc_id,
                    pdf_sha256=pdf_sha256,
                    doi_clean=doi_clean,
                    article_type=article_type,
                    stage="analyze",
                    error_message="Falha na análise (modelo retornou vazio/erro)",
                )
                return False
            
            score = result['score']
            analysis = result['analysis']
            analysis_model = result.get('model_used')
            
            print(f"   ✅ Nota de aplicabilidade clínica: {score}/10")
            
            # 6. Salvar saída canônica (analysis.md + analysis.json)
            print("\n6️⃣ Salvando saída pronta para indexação...")
            stage = "write_outputs"

            analysis_dt = now_iso_brt()
            canonical_type = canonical_type_for(article_type)
            doi_yaml = doi_clean if doi_clean else 'null'

            md_path = os.path.join(article_dir, "analysis.md")
            json_path = os.path.join(article_dir, "analysis.json")

            # YAML front matter (formato exigido)
            _pub_date = extract_pub_date_from_filename(filename)
            # CrossRef como fonte primária da data (filosofia CardioDaily: data online exata)
            if doi_clean and extract_pub_date_from_crossref:
                _crossref_date = extract_pub_date_from_crossref(doi_clean)
                if _crossref_date:
                    _pub_date = _crossref_date
            # Extrair título real do artigo (do texto da análise ou do PDF)
            _titulo_real = extract_podcast_article_title(analysis, filename)
            with open(md_path, 'w', encoding='utf-8') as f:
                f.write("---\n")
                f.write(f"doc_id: \"{doc_id}\"\n")
                f.write(f"source_pdf: \"{filename}\"\n")
                f.write(f"doi: \"{doi_yaml}\"\n")
                f.write(f"pdf_sha256: \"{pdf_sha256}\"\n")
                f.write(f"type: \"{canonical_type}\"\n")
                f.write(f"subtype: \"{article_type}\"\n")
                f.write(f"doenca_principal: \"{doenca_principal}\"\n")
                f.write(f"data_publicacao: \"{_pub_date}\"\n")
                f.write(f"analysis_datetime: \"{analysis_dt}\"\n")
                f.write(f"nota_aplicabilidade: {int(score)}\n")
                f.write("generator: \"CardioDaily ArticleAnalyzer\"\n")
                f.write("generator_version: \"2026.01\"\n")
                f.write("schema_version: 1\n")
                f.write("language: \"pt-BR\"\n")
                f.write("---\n\n")

                f.write(f"# Análise: {filename}\n\n")
                f.write(f"**doc_id:** {doc_id}\n\n")
                f.write(f"**DOI:** {doi_clean if doi_clean else 'Não encontrado'}\n\n")
                f.write(f"**Tipo:** {canonical_type} ({article_type})\n\n")
                f.write(f"**Doença principal:** {doenca_principal}\n\n")
                f.write(f"**Data de Publicação:** {_pub_date}\n\n")
                f.write(f"**Data da Análise:** {analysis_dt}\n\n")
                f.write("---\n\n")
                f.write(analysis)

            # Export organizado por tipo (atalho para leitura humana)
            self._export_analysis_to_markdown_folder(
                article_type=article_type,
                doc_id=doc_id,
                filename=filename,
                md_path=md_path,
            )

            # Status de mídia (P1)
            audio_status = "not_implemented"
            
            # 7. Gerar áudio APENAS para artigos originais com nota_aplicabilidade_clinica >= 8
            audio_path = None

            # ========== VERIFICAÇÃO EXTRA PARA PODCAST ==========
            # Só gera podcast se:
            # 1. nota_aplicabilidade_clinica >= 8
            # 2. Tipo canônico == "original"
            # 3. NÃO é revisão/meta-análise disfarçada (verificar keywords no texto)
            
            should_generate_podcast = False
            skip_reason = None
            
            if score < 8:
                skip_reason = f"Nota de aplicabilidade insuficiente ({score}/10 — mínimo: 8)"
            elif canonical_type != "original":
                skip_reason = f"Tipo não é original ({canonical_type})"
            else:
                # Verificação extra: checar se NÃO é revisão/meta-análise disfarçada
                # NOTA: Muitos artigos originais citam/discutem meta-análises, então
                # o threshold precisa ser alto para evitar falsos positivos.
                # Verificamos apenas as primeiras 3000 chars (abstract/intro) para
                # evitar que referências no body ativem o filtro indevidamente.
                text_head = (text[:3000] if text else "").lower()

                # Red flags FORTES (só no abstract/intro) que indicam que o PRÓPRIO
                # artigo é uma revisão/meta-análise, não que ele apenas cita uma.
                meta_review_indicators = [
                    'systematic review and meta-analysis',
                    'prisma flow diagram', 'prisma checklist',
                    'forest plot', 'funnel plot',
                    'we searched medline', 'we searched pubmed',
                    'databases were searched', 'eligible studies',
                ]

                red_flag_count = sum(1 for indicator in meta_review_indicators if indicator in text_head)

                if red_flag_count >= 2:
                    skip_reason = f"Possível revisão/meta-análise disfarçada ({red_flag_count} indicadores no abstract)"
                    print(f"   ⚠️  ALERTA: Artigo classificado como original mas tem {red_flag_count} indicadores de revisão/meta-análise no abstract")
                else:
                    should_generate_podcast = True

            if should_generate_podcast:
                print(f"\n7️⃣ Original com score ≥ 8: Gerando podcast...")

                if self.podcast_script_generator and self.audio_enabled:
                    # Gerar script de podcast
                    print("   🎤 Gerando script de podcast...")
                    podcast_title = extract_podcast_article_title(analysis, filename)
                    podcast_script = self.podcast_script_generator.generate_podcast_script(
                        analysis_text=analysis,
                        article_title=podcast_title,
                        doi=doi_clean if doi_clean else "N/A",
                        score=score
                    )
                    
                    if podcast_script:
                        # Salvar script
                        script_filename = f"{base_name}_podcast_script.txt"
                        # Salvar o script no diretório por tipo (evita misturar)
                        if article_type == 'artigo_original':
                            script_dir = self.dirs.get('markdown_artigos_originais', self.dirs['markdown'])
                        elif article_type == 'revisao_sistematica_meta_analise':
                            script_dir = self.dirs.get('markdown_meta_analises', self.dirs['markdown'])
                        else:
                            script_dir = self.dirs.get('markdown_revisoes', self.dirs['markdown'])
                        script_path = os.path.join(script_dir, script_filename)
                        
                        with open(script_path, 'w', encoding='utf-8') as f:
                            f.write(podcast_script)
                        
                        print(f"   ✅ Script salvo: {script_filename}")
                        
                        # Gerar áudio
                        print("   🎵 Gerando áudio com ElevenLabs...")
                        audio_filename = f"{base_name}_podcast.mp3"
                        audio_path = os.path.join(self.dirs['audio'], audio_filename)
                        
                        success = self.audio_generator.generate_audio(
                            text=podcast_script,
                            output_path=audio_path
                        )
                        
                        if success:
                            print(f"   ✅ Podcast gerado: {audio_filename}")
                            audio_status = "generated"
                            # Upload automático para Supabase Storage
                            pub_url = _upload_podcast_supabase(doc_id, audio_path)
                            if pub_url:
                                print(f"   ☁️  Podcast publicado: {pub_url}")
                        else:
                            print(f"   ❌ Falha ao gerar áudio")
                            audio_path = None
                            audio_status = "failed"
                    else:
                        print(f"   ❌ Falha ao gerar script")
                        audio_status = "failed"
                else:
                    print("   ⚠️  Geração de podcast desabilitada (falta API key)")
                    audio_status = "disabled_no_api_key"
            else:
                # Não deve gerar podcast
                print(f"\n7️⃣ Pulando podcast: {skip_reason}")
                if skip_reason and "Nota de aplicabilidade insuficiente" in skip_reason:
                    audio_status = "skipped_low_score"
                elif skip_reason and "não é original" in skip_reason:
                    audio_status = "skipped_not_original"
                elif skip_reason and "disfarçada" in skip_reason:
                    audio_status = "skipped_misclassified_review"
                else:
                    audio_status = "skipped"
            
            # 7b. Extrair mapa mental do analysis.md
            mindmap_path_abs = None
            try:
                import re as _re
                mm_pattern = r'## 🗺️ SCRIPT PARA MAPA MENTAL.*?```(?:markdown)?\s*\n(.*?)\n```'
                mm_match = _re.search(mm_pattern, analysis, _re.DOTALL)
                if mm_match:
                    mindmap_content = mm_match.group(1).strip()
                    mindmap_file = os.path.join(article_dir, "mindmap.md")
                    with open(mindmap_file, 'w', encoding='utf-8') as f:
                        f.write(mindmap_content)
                    mindmap_path_abs = mindmap_file
                    print(f"   🗺️  Mapa mental extraído: mindmap.md")
            except Exception as e:
                print(f"   ⚠️  Erro ao extrair mapa mental: {e}")

            # 7b2. Gerar mapa mental visual (PNG) via Playwright
            mindmap_image_path = None
            mindmap_render_status = "not_generated"
            if mindmap_path_abs and self.mindmap_enabled:
                print(f"\n7️⃣🗺️ Gerando mapa mental visual (PNG)...")
                try:
                    mindmap_result = self.mindmap_generator.generate(article_dir)
                    if mindmap_result:
                        mindmap_image_path = mindmap_result
                        mindmap_render_status = "rendered"
                    else:
                        mindmap_render_status = "failed"
                except Exception as e:
                    print(f"   ⚠️  Erro ao gerar mapa mental visual: {e}")
                    mindmap_render_status = "failed"
            elif not mindmap_path_abs:
                mindmap_render_status = "no_mindmap_md"
            elif not self.mindmap_enabled:
                mindmap_render_status = "disabled"

            # 7c. InfographicPortrait DESATIVADO — Visual Abstract é o gerador oficial
            infographic_status = "disabled"
            infographic_path = None

            # 7d. Gerar Visual Abstract para todos os tipos com score >= 7
            # (originais, revisões, meta-análises, guidelines — prompt adaptativo)
            visual_abstract_status = "not_generated"
            if score >= 7 and canonical_type in ("original", "metanalise", "revisao") and self.visual_abstract_enabled:
                tipo_label = {"original": "Original", "metanalise": "Meta-análise", "revisao": "Revisão/Guideline"}.get(canonical_type, canonical_type)
                print(f"\n7️⃣📊 Gerando Visual Abstract [{tipo_label}] (nota {score}/10)...")
                try:
                    va_path = self.visual_abstract_generator.gerar_png(
                        Path(article_dir), canonical_type=canonical_type
                    )
                    if va_path and va_path.exists():
                        visual_abstract_status = "generated"
                        print(f"   ✅ Visual Abstract: {va_path.name} ({va_path.stat().st_size//1024} KB)")
                    else:
                        visual_abstract_status = "failed"
                except Exception as e:
                    print(f"   ⚠️  Erro ao gerar Visual Abstract: {e}")
                    visual_abstract_status = "failed"
            elif score < 7:
                visual_abstract_status = "skipped_low_score"

            # JSON canônico
            article_dir_rel_from_outputs = os.path.relpath(article_dir, self.output_base_dir)
            analysis_json = {
                "schema_version": 1,
                "doc_id": doc_id,
                "source": {
                    "pdf_filename": filename,
                    "pdf_sha256": pdf_sha256,
                    "doi": doi_clean,
                    "journal": extract_journal(pdf_filename=filename),
                    "titulo": _titulo_real,
                    "publication_date": _pub_date,
                },
                "classification": {
                    "type": canonical_type,
                    "subtype": article_type,
                    "doenca_principal": doenca_principal,
                    "palavras_chave": palavras_chave,
                    "populacao": populacao,
                    "intervencao": intervencao,
                    "model_used": analysis_model,
                    "classifier": {
                        "final_label": article_type,
                    },
                },
                "analysis": {
                    "analysis_datetime": analysis_dt,
                    "language": "pt-BR",
                    "scores": {
                        "aplicabilidade": int(score),
                    },
                },
                "media": {
                    "audio_status": audio_status,
                    "mindmap_status": mindmap_render_status if mindmap_render_status == "rendered" else ("extracted" if mindmap_path_abs else "not_found"),
                    "infographic_status": infographic_status,
                },
                "artifacts": {
                    "article_dir": article_dir_rel_from_outputs,
                    "source_pdf": "source.pdf",
                    "analysis_md": "analysis.md",
                    "analysis_json": "analysis.json",
                    "assets_dir": "assets/",
                },
                "provenance": {
                    "generator": "CardioDaily ArticleAnalyzer",
                    "generator_version": "2026.01",
                },
            }

            with open(json_path, 'w', encoding='utf-8') as jf:
                json.dump(analysis_json, jf, ensure_ascii=False, indent=2)

            print(f"   ✅ Pacote salvo: outputs/corpus/{doc_id}/")

            # 8. Registrar no banco de dados
            print("\n8️⃣ Registrando no banco de dados...")
            
            # Usar caminhos relativos para o HTML (novo pipeline canônico)
            summary_relative = f"outputs/corpus/{doc_id}/analysis.md"
            audio_relative = os.path.relpath(audio_path, os.path.dirname(self.output_base_dir)) if audio_path else None
            image_relative = None  # Geração de imagens DALL-E removida (v9.1)
            mindmap_relative = f"outputs/corpus/{doc_id}/mindmap.md" if mindmap_path_abs else None
            mindmap_image_relative = f"outputs/corpus/{doc_id}/assets/mindmap.png" if mindmap_image_path else None

            skip_db_write = os.environ.get('CARDIODAILY_SKIP_DB_WRITE', '0') == '1'
            if skip_db_write:
                print("   🧪 CARDIODAILY_SKIP_DB_WRITE=1: pulando escrita no banco/HTML")
            else:
                if doi_clean:
                    self.doi_tracker.add_article(
                        doi=doi_clean,
                        filename=filename,
                        article_type=article_type,
                        score=score,
                        summary_path=summary_relative,
                        audio_path=audio_relative,
                        image_path=image_relative,
                        mindmap_path=mindmap_relative,
                        mindmap_image_path=mindmap_image_relative
                    )
                else:
                    print("   ℹ️  DOI ausente após sanitização: não registrando no DOITracker (mas pacote foi salvo)")
            
            # 9. Notificar beta testers no Telegram
            _titulo_notif = _titulo_real if '_titulo_real' in dir() else filename
            _revista_notif = analysis_json.get("source", {}).get("journal", "") or ""
            _resumo_notif  = analysis_json.get("resumo_markdown", "") or ""
            _podcast_url   = None
            if audio_path and Path(audio_path).exists():
                _podcast_url = f"{os.getenv('SUPABASE_URL','').rstrip('/')}/storage/v1/object/public/podcasts/{doc_id}.mp3"
            _infographic   = str(Path(article_dir) / "assets" / "infografico_portrait.png")

            notified = _notify_telegram_beta(
                doc_id=doc_id,
                titulo=_titulo_notif,
                revista=_revista_notif,
                score=score,
                resumo=_resumo_notif,
                podcast_url=_podcast_url,
                infographic_path=_infographic,
            )
            if notified:
                print("   📲 Beta testers notificados no Telegram")

            print("\n" + "=" * 80)
            print(f"✅ ARTIGO PROCESSADO COM SUCESSO!")
            print("=" * 80)

            return True
            
        except Exception as e:
            print(f"\n❌ ERRO ao processar artigo: {e}")
            import traceback
            traceback.print_exc()
            try:
                # Se já criamos um pacote canônico, não deixar sem analysis.md
                if 'article_dir' in locals() and 'doc_id' in locals() and 'filename' in locals():
                    self._write_failure_package(
                        article_dir=article_dir,
                        filename=filename,
                        doc_id=doc_id,
                        pdf_sha256=locals().get('pdf_sha256'),
                        doi_clean=locals().get('doi_clean'),
                        article_type=locals().get('article_type'),
                        stage=locals().get('stage', 'unknown'),
                        error_message=str(e),
                    )
            except Exception:
                pass
            return False
    
    def process_all_articles(self, max_articles=None, skip_first: int = 0):
        """
        Processa todos os artigos da pasta INPUT.
        
        Args:
            max_articles: Número máximo de artigos a processar (None = todos)
        
        Returns:
            Estatísticas do processamento
        """
        print("\n" + "=" * 80)
        if self.input_local_dir:
            print("🔍 BUSCANDO ARTIGOS NA PASTA LOCAL")
        else:
            print("🔍 BUSCANDO ARTIGOS NO GOOGLE DRIVE")
        print("=" * 80)
        
        # Listar arquivos
        if self.input_local_dir:
            local_dir = Path(self.input_local_dir)
            if not local_dir.exists() or not local_dir.is_dir():
                print(f"\n⚠️  Pasta local não existe ou não é diretório: {local_dir}")
                files = []
            else:
                pdf_lower = list(local_dir.rglob("*.pdf"))
                pdf_upper = list(local_dir.rglob("*.PDF"))
                # Filtrar arquivos de metadata do macOS (._*)
                pdf_paths = sorted(set(
                    p for p in (pdf_lower + pdf_upper)
                    if not p.name.startswith('._')
                ))
                print(f"\n📂 Pasta local: {local_dir}")
                print(f"🔎 PDFs encontrados: {len(pdf_paths)}")
                files = [
                    {
                        'name': p.name,
                        'path': str(p),
                        'local': True,
                    }
                    for p in pdf_paths
                ]
        else:
            files = self.drive_manager.list_files(self.input_folder_id)
        
        if not files:
            print("\n⚠️  Nenhum arquivo encontrado na pasta INPUT")
            return
        
        total_files = len(files)

        # Pular primeiros N arquivos (útil para retomar do ponto onde parou)
        if skip_first:
            try:
                skip_first_int = int(skip_first)
            except Exception:
                skip_first_int = 0

            if skip_first_int < 0:
                skip_first_int = 0

            if skip_first_int >= total_files:
                print(f"\n⚠️  skip_first={skip_first_int} ≥ total={total_files}: nada para processar")
                return

            files = files[skip_first_int:]
            print(f"\n⏭️  Retomando: pulando os primeiros {skip_first_int} PDFs")
            total_files = len(files)
        else:
            skip_first_int = 0

        if max_articles:
            files = files[:max_articles]
            print(f"\n📊 Processando {len(files)} de {total_files} artigos")
        else:
            print(f"\n📊 Processando todos os {total_files} artigos")
        
        # Estatísticas
        stats = {
            'total': len(files),
            'processed': 0,
            'skipped': 0,
            'failed': 0
        }

        # Progresso (a cada N artigos)
        try:
            progress_every = int(os.environ.get('CARDIODAILY_PROGRESS_EVERY', '100'))
        except Exception:
            progress_every = 100
        if progress_every <= 0:
            progress_every = 100
        
        # Processar cada artigo
        for i, file_info in enumerate(files, 1):
            global_index = skip_first_int + i
            global_total = skip_first_int + len(files)
            print(f"\n\n{'='*80}")
            print(f"ARTIGO {global_index}/{global_total}")
            print(f"{'='*80}")
            
            result = self.process_article(file_info)
            
            if result:
                stats['processed'] += 1
            elif result is False:
                stats['skipped'] += 1
            else:
                stats['failed'] += 1

            if (i % progress_every == 0) or (i == len(files)):
                print(
                    f"\n📈 Progresso: {global_index}/{global_total} | ✅ {stats['processed']} | ⏭️ {stats['skipped']} | ❌ {stats['failed']}",
                    flush=True,
                )
        
        # Relatório final
        print("\n\n" + "=" * 80)
        print("📊 RELATÓRIO FINAL")
        print("=" * 80)
        print(f"\n✅ Processados com sucesso: {stats['processed']}")
        print(f"⏭️  Pulados (duplicatas): {stats['skipped']}")
        print(f"❌ Falhas: {stats['failed']}")
        print(f"📁 Total: {stats['total']}")
        
        # Estatísticas do banco de dados
        db_stats = self.doi_tracker.get_statistics()
        print(f"\n📚 Total no banco de dados: {db_stats['total']}")
        print(f"⭐ Artigos com nota aplicabilidade ≥ 7: {db_stats['high_score']}")
        print(f"\n🎧 Com podcast: {db_stats['with_audio']}")
        print(f"🖼️  Com imagem: {db_stats['with_image']}")
        print(f"\n🎯 Elegíveis para podcast (nota aplicabilidade ≥ 8, tipo original): {sum(1 for s in db_stats.get('scores', []) if s >= 8) if db_stats.get('scores') else 'N/A'}")
        print(f"\n📊 Relatório HTML: {self.doi_tracker.html_path}")
        print("\n" + "=" * 80)
        print("✅ PROCESSAMENTO CONCLUÍDO!")
        print("=" * 80 + "\n")
        
        return stats


# Função principal
if __name__ == "__main__":
    import sys
    
    import argparse

    print("\n" + "=" * 80)
    print("🚀 SISTEMA DE ANÁLISE DE ARTIGOS - CardioDaily")
    print("=" * 80)

    parser = argparse.ArgumentParser(
        prog="article_analyzer.py",
        description="Analisa PDFs (Google Drive ou pasta local) e gera outputs do CardioDaily.",
    )
    parser.add_argument(
        "n",
        nargs="?",
        type=int,
        help="Quantidade máxima de artigos (ex: 5).",
    )
    parser.add_argument(
        "--limit",
        "-l",
        "--max",
        dest="limit",
        type=int,
        help="Quantidade máxima de artigos (ex: --limit 5).",
    )
    parser.add_argument(
        "--local-dir",
        dest="local_dir",
        help="Caminho de uma pasta local para ler PDFs (ativa modo local).",
    )
    parser.add_argument(
        "--skip-first",
        dest="skip_first",
        type=int,
        default=None,
        help="Pula os primeiros N PDFs (para retomar um processamento). Alternativa: env CARDIODAILY_SKIP_FIRST.",
    )
    parser.add_argument(
        "--drive",
        action="store_true",
        help="Força uso do Google Drive (mesmo se --local-dir estiver presente).",
    )
    args = parser.parse_args()

    # Detectar pasta local via CLI ou variável de ambiente (opcional)
    local_dir = args.local_dir or os.environ.get("LOCAL_ARTICLES_DIR")

    # Determinar limite
    max_articles = args.limit if args.limit is not None else args.n

    # Retomar (pular primeiros N)
    skip_first = args.skip_first
    if skip_first is None:
        try:
            skip_first = int(os.environ.get("CARDIODAILY_SKIP_FIRST", "0"))
        except Exception:
            skip_first = 0

    # Criar analisador
    if local_dir and not args.drive:
        print(f"\n📂 Usando pasta local para PDFs: {local_dir}")
        analyzer = ArticleAnalyzer(input_local_dir=local_dir)
    else:
        analyzer = ArticleAnalyzer()

    if max_articles is not None:
        print(f"\n🎯 Processando até {max_articles} artigos...")
    else:
        print("\n🎯 Processando TODOS os artigos...")
        print("💡 Dica: Use 'python article_analyzer.py 5' ou '--limit 5' para processar apenas 5 artigos")
    
    # Processar artigos
    stats = analyzer.process_all_articles(max_articles=max_articles, skip_first=skip_first)
    
    print("\n✅ Processamento concluído!")

