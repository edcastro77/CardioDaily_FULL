"""
CardioDaily Radar v3 — Journal Issue Fetcher via PubMed
Dr. Eduardo Castro

Busca automaticamente o número mais recente de uma revista cardiológica no PubMed
e gera o script de podcast sem precisar de PDFs.

Uso:
    python3 src/radar/journal_issue_fetcher.py --journal "circulation"
    python3 src/radar/journal_issue_fetcher.py --journal "jacc" --audio
    python3 src/radar/journal_issue_fetcher.py --journal "nejm" --issue "396/1"
"""

import os
import sys
import json
import time
import argparse
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from xml.etree import ElementTree as ET

from Bio import Entrez, Medline

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from google import genai
from google.genai import types as genai_types
from dotenv import load_dotenv

load_dotenv()

from src.radar import radar_config, radar_prompts

# ==============================================================================
# MAPA DE REVISTAS CARDIOLÓGICAS → NOME OFICIAL NO PUBMED
# ==============================================================================
JOURNAL_MAP = {
    # Aliases → Nome exato no PubMed
    "circulation":              "Circulation",
    "circ":                     "Circulation",
    "jacc":                     "J Am Coll Cardiol",
    "journal of the american college of cardiology": "J Am Coll Cardiol",
    "nejm":                     "N Engl J Med",
    "new england journal":      "N Engl J Med",
    "jama":                     "JAMA",
    "lancet":                   "Lancet",
    "european heart journal":   "Eur Heart J",
    "eur heart j":              "Eur Heart J",
    "ehj":                      "Eur Heart J",
    "heart":                    "Heart",
    "jacc heart failure":       "JACC Heart Fail",
    "jacc hf":                  "JACC Heart Fail",
    "jacc heart fail":          "JACC Heart Fail",
    "jacc cardiovascular imaging":      "JACC Cardiovasc Imaging",
    "jacc imaging":             "JACC Cardiovasc Imaging",
    "jacc cardiovascular interventions":"JACC Cardiovasc Interv",
    "jacc interv":              "JACC Cardiovasc Interv",
    "jcin":                     "JACC Cardiovasc Interv",
    "jacc basic translational":         "JACC Basic Transl Sci",
    "jacc asia":                "JACC Asia",
    "circulation heart failure":        "Circ Heart Fail",
    "circ heart fail":          "Circ Heart Fail",
    "circulation arrhythmia":           "Circ Arrhythm Electrophysiol",
    "circ arrhythmia":          "Circ Arrhythm Electrophysiol",
    "circulation cardiovascular imaging": "Circ Cardiovasc Imaging",
    "circ imaging":             "Circ Cardiovasc Imaging",
    "circulation cardiovascular interventions": "Circ Cardiovasc Interv",
    "circ interventions":       "Circ Cardiovasc Interv",
    "circulation cardiovascular quality": "Circ Cardiovasc Qual Outcomes",
    "circ quality":             "Circ Cardiovasc Qual Outcomes",
    "atherosclerosis":          "Atherosclerosis",
    "hypertension":             "Hypertension",
    "heart rhythm":             "Heart Rhythm",
    "heart failure":            "ESC Heart Fail",
    "esc heart fail":           "ESC Heart Fail",
    "american heart journal":   "Am Heart J",
    "am heart j":               "Am Heart J",
    "american journal of cardiology": "Am J Cardiol",
    "am j cardiol":             "Am J Cardiol",
    "cardiovascular research":  "Cardiovasc Res",
    "stroke":                   "Stroke",
    "jaha":                     "J Am Heart Assoc",
    "journal of the american heart association": "J Am Heart Assoc",
}

# Tipos de artigo considerados clínicamente relevantes para o podcast
RELEVANT_TYPES = {
    "Journal Article",
    "Randomized Controlled Trial",
    "Clinical Trial",
    "Multicenter Study",
    "Meta-Analysis",
    "Systematic Review",
    "Review",
}

EDITORIAL_TYPES = {
    "Editorial",
    "Comment",
    "Letter",
}


class JournalIssueFetcher:
    """
    Busca o número mais recente de uma revista no PubMed e gera script de podcast.
    """

    def __init__(self, email: str = None):
        self.email = email or os.getenv("PUBMED_EMAIL", "cardiodaily@cardiopapers.com.br")
        Entrez.email = self.email
        self._setup_ai()

    def _setup_ai(self):
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY não encontrada no .env")

        self.genai_client = genai.Client(api_key=api_key)
        self.model_id = radar_config.GEMINI_MODEL_ID
        cfg = radar_config.GENERATION_CONFIG
        self.generation_config = genai_types.GenerateContentConfig(
            temperature=cfg.get("temperature", 0.2),
            top_p=cfg.get("top_p", 0.8),
            top_k=cfg.get("top_k", 40),
            max_output_tokens=cfg.get("max_output_tokens", 32768),
        )
        print(f"🤖 Usando modelo: {self.model_id}")

    # ------------------------------------------------------------------
    # RESOLUÇÃO DO NOME DA REVISTA
    # ------------------------------------------------------------------

    def resolve_journal(self, name: str) -> Optional[str]:
        """Converte alias coloquial para nome oficial no PubMed."""
        key = name.strip().lower()
        if key in JOURNAL_MAP:
            return JOURNAL_MAP[key]
        # Busca parcial
        for alias, official in JOURNAL_MAP.items():
            if key in alias or alias in key:
                return official
        return None

    # ------------------------------------------------------------------
    # BUSCA DO NÚMERO MAIS RECENTE
    # ------------------------------------------------------------------

    def get_latest_issue_info(self, pubmed_journal: str) -> Optional[Tuple[str, str]]:
        """
        Busca o número mais recente da revista que já tem volume/issue atribuído.
        Artigos epub-ahead-of-print (sem volume/issue) são ignorados.
        Retorna (volume, issue) ou None se não encontrar.
        """
        print(f"\n🔍 Buscando número mais recente de: {pubmed_journal}")

        query = f'"{pubmed_journal}"[Journal]'
        try:
            # Busca os 30 artigos mais recentes — alguns podem ser epub-ahead sem vol/issue
            handle = Entrez.esearch(
                db="pubmed",
                term=query,
                retmax=30,
                sort="pub date",
            )
            record = Entrez.read(handle)
            handle.close()

            if not record["IdList"]:
                print("  ⚠️  Nenhum artigo encontrado para esta revista.")
                return None

            pmid_list = record["IdList"]
            time.sleep(0.4)

            # Buscar metadados em XML para os 30 artigos
            handle = Entrez.efetch(
                db="pubmed", id=pmid_list, rettype="xml", retmode="xml"
            )
            xml_data = handle.read()
            handle.close()

            root = ET.fromstring(xml_data)

            # Varrer artigos até encontrar um com volume e issue preenchidos
            from collections import Counter
            issue_counts = Counter()

            for pub_art in root.findall(".//PubmedArticle"):
                try:
                    journal_el = pub_art.find(
                        "MedlineCitation/Article/Journal"
                    )
                    vol  = journal_el.findtext("JournalIssue/Volume") or ""
                    iss  = journal_el.findtext("JournalIssue/Issue") or ""
                    year = (
                        journal_el.findtext("JournalIssue/PubDate/Year")
                        or journal_el.findtext("JournalIssue/PubDate/MedlineDate")
                        or ""
                    )
                    if vol and iss:
                        issue_counts[(vol, iss, year)] += 1
                except Exception:
                    continue

            if not issue_counts:
                print("  ⚠️  Nenhum artigo com volume/issue atribuído nos 30 mais recentes.")
                print("      Todos podem ser epub-ahead-of-print.")
                return None

            # O número mais frequente entre os recentes é o último número publicado
            (volume, issue, year), count = issue_counts.most_common(1)[0]
            print(f"  📖 Número mais recente: Volume {volume}, Issue {issue} ({year})")
            print(f"     ({count} artigos identificados neste número)")
            return volume, issue

        except Exception as e:
            print(f"  ❌ Erro ao buscar número mais recente: {e}")
            import traceback
            traceback.print_exc()
            return None

    # ------------------------------------------------------------------
    # BUSCA DOS ARTIGOS DO NÚMERO
    # ------------------------------------------------------------------

    def fetch_issue_articles(
        self,
        pubmed_journal: str,
        volume: str,
        issue: str,
        max_results: int = 80,
    ) -> List[Dict]:
        """
        Busca todos os artigos de um volume/número específico.
        Retorna lista de dicts com metadados + abstract.
        """
        print(f"\n📥 Buscando artigos do Volume {volume}, Issue {issue}...")

        query = f'"{pubmed_journal}"[Journal] AND {volume}[Volume] AND {issue}[Issue]'

        try:
            handle = Entrez.esearch(db="pubmed", term=query, retmax=max_results)
            record = Entrez.read(handle)
            handle.close()

            pmid_list = record["IdList"]
            total = record["Count"]
            print(f"  📊 {total} artigos encontrados ({len(pmid_list)} carregados)")

            if not pmid_list:
                return []

            time.sleep(0.4)

            # Buscar registros completos em formato Medline
            handle = Entrez.efetch(
                db="pubmed",
                id=pmid_list,
                rettype="medline",
                retmode="text",
            )
            medline_text = handle.read()
            handle.close()

            # Parsear
            from io import StringIO
            records = list(Medline.parse(StringIO(medline_text)))

            articles = []
            for rec in records:
                article = self._parse_medline_record(rec)
                if article:
                    articles.append(article)

            print(f"  ✅ {len(articles)} artigos parseados")
            return articles

        except Exception as e:
            print(f"  ❌ Erro ao buscar artigos: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _parse_medline_record(self, rec: dict) -> Optional[Dict]:
        """Extrai campos relevantes de um registro Medline."""
        try:
            title    = rec.get("TI", "")
            abstract = rec.get("AB", "")
            authors  = rec.get("AU", [])
            pmid     = rec.get("PMID", "")
            doi      = rec.get("LID", "").replace(" [doi]", "").strip()
            pub_types = rec.get("PT", [])
            journal  = rec.get("JT", "")
            volume   = rec.get("VI", "")
            issue    = rec.get("IP", "")
            pages    = rec.get("PG", "")
            year     = rec.get("DP", "")
            mesh     = rec.get("MH", [])

            if not title:
                return None

            # Classificar tipo
            article_type = self._classify_type(pub_types)

            authors_str = ", ".join(authors[:3])
            if len(authors) > 3:
                authors_str += " et al."

            return {
                "pmid":         pmid,
                "doi":          doi,
                "title":        title,
                "abstract":     abstract,
                "authors":      authors_str,
                "pub_types":    pub_types,
                "article_type": article_type,
                "journal":      journal,
                "volume":       volume,
                "issue":        issue,
                "pages":        pages,
                "year":         year,
                "mesh":         mesh[:10],
                "has_abstract": bool(abstract),
            }
        except Exception:
            return None

    def _classify_type(self, pub_types: List[str]) -> str:
        """Classifica o artigo baseado nos pub_types do PubMed."""
        types_set = set(pub_types)

        if types_set & {"Randomized Controlled Trial", "Clinical Trial",
                        "Multicenter Study", "Controlled Clinical Trial"}:
            return "ORIGINAL"

        if types_set & {"Meta-Analysis", "Systematic Review"}:
            return "META-ANALYSIS"

        if types_set & {"Review"}:
            return "REVIEW"

        if types_set & {"Editorial"}:
            return "EDITORIAL"

        if types_set & {"Comment", "Letter"}:
            return "COMMENT"

        if "Journal Article" in types_set:
            return "ORIGINAL"

        return "OTHER"

    # ------------------------------------------------------------------
    # GERAÇÃO DO SCRIPT DE PODCAST
    # ------------------------------------------------------------------

    def generate_podcast_script(
        self,
        articles: List[Dict],
        journal_name: str,
        volume: str,
        issue: str,
    ) -> Optional[str]:
        """
        Envia os artigos ao Gemini e gera o script de podcast.
        """
        # Filtrar artigos relevantes (excluir cartas, errata, etc.)
        main_articles = [a for a in articles if a["article_type"] in
                         ("ORIGINAL", "META-ANALYSIS", "REVIEW") and a["has_abstract"]]

        editorials = [a for a in articles if a["article_type"] == "EDITORIAL"]

        print(f"\n🎯 Artigos principais: {len(main_articles)}")
        print(f"   Editoriais: {len(editorials)}")

        if not main_articles:
            print("  ⚠️  Nenhum artigo principal com abstract. Usando todos com abstract.")
            main_articles = [a for a in articles if a["has_abstract"]]

        if not main_articles:
            print("  ❌ Nenhum artigo com abstract para gerar o podcast.")
            return None

        # Montar contexto para o Gemini
        context_lines = [
            f"# {journal_name} — Volume {volume}, Issue {issue}",
            f"# Total de artigos neste número: {len(articles)}",
            f"# Artigos com abstract: {len(main_articles)}\n",
        ]

        for i, art in enumerate(main_articles, 1):
            context_lines.append(
                f"---\n"
                f"## Artigo {i} [{art['article_type']}]\n"
                f"**Título:** {art['title']}\n"
                f"**Autores:** {art['authors']}\n"
                f"**Ano:** {art['year']}\n"
                f"**DOI:** {art['doi']}\n"
                f"**PMID:** {art['pmid']}\n"
                f"**Abstract:**\n{art['abstract']}\n"
            )

        if editorials:
            context_lines.append("\n---\n## EDITORIAIS / COMENTÁRIOS\n")
            for ed in editorials[:5]:
                context_lines.append(
                    f"- **{ed['title']}** — {ed['authors']} (Editorial relacionado)\n"
                )

        context_text = "\n".join(context_lines)

        print(f"\n🧠 Contexto preparado: {len(context_text):,} caracteres")
        print(f"⏳ Gerando script com Gemini 2.5 Pro...")

        # Usar prompt do radar_prompts se preenchido, senão usar padrão
        podcast_prompt = radar_prompts.PROMPT_WEEKLY_PODCAST
        if "[PASTE" in podcast_prompt:
            podcast_prompt = self._default_podcast_prompt(journal_name, volume, issue)

        try:
            full_prompt = podcast_prompt + "\n\n" + context_text
            response = self.genai_client.models.generate_content(
                model=self.model_id,
                contents=full_prompt,
                config=self.generation_config,
            )
            script = response.text
            print(f"✅ Script gerado: {len(script):,} caracteres / ~{len(script.split()):,} palavras")
            return script

        except Exception as e:
            print(f"❌ Erro ao gerar script: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _default_podcast_prompt(self, journal: str, volume: str, issue: str) -> str:
        return f"""
Você é o Dr. CardioDaily, cardiologista e criador de conteúdo científico de alto nível.

Sua tarefa é criar um SCRIPT DE PODCAST em português brasileiro para o **Radar {journal}**,
cobrindo os artigos mais importantes do Volume {volume}, Issue {issue}.

---

## ESTRUTURA DO PODCAST

### ABERTURA (30 segundos)
- "Olá, aqui é o Dr. CardioDaily. Bem-vindos ao Radar {journal}."
- Diga o número total de artigos e quantos você vai cobrir com destaque.
- Uma frase contextualizando o que há de mais relevante nesta edição.

### CORPO — para cada artigo selecionado (3-5 artigos, os mais relevantes):
Para cada artigo siga EXATAMENTE esta ordem:
1. **Identificação:** Título, autores principais, tipo de estudo.
2. **Contexto:** Em 2-3 frases — qual problema clínico, o que já se sabia, o que faltava.
3. **Pergunta e Desenho:** Hipótese testada, tipo de estudo, N de pacientes, desfechos.
4. **Resultados:** SOMENTE os números que importam. Não despeje subgrupos — escolha os 2-3 achados centrais. Use HR, IC95%, NNT, p-valor quando disponíveis.
5. **Impacto clínico:** O que muda na prática? Seja específico — "pacientes com perfil X devem/não devem receber Y."
6. **Limitação principal:** A que compromete mais a validade ou generalização.

### EDITORIAL DO NÚMERO (se aplicável)
- Mencione brevemente o editorial mais relevante e o ponto de vista central.

### FECHAMENTO (20 segundos)
- Um takeaway acionável por artigo (lista rápida — 1 frase por artigo).
- "Até o próximo, aqui no CardioDaily."

---

## REGRAS INVIOLÁVEIS DE TOM

**PROIBIDO:**
- Aberturas sensacionalistas: "revolucionário", "divisor de águas", "prepare-se para", "você não vai acreditar"
- Clichês: "vamos mergulhar", "um tema que está dando o que falar", "fascinante"
- Hipérboles vazias sobre estudos incrementais
- Listar limitações por protocolo — mencione só as que realmente comprometem o estudo

**OBRIGATÓRIO:**
- Tom objetivo e direto, como um attending na visita ao fellow
- Frases curtas. Dados concretos. Conclusões específicas.
- Se o financiamento da indústria é relevante para interpretar o resultado, mencione.
- Se o estudo tem falha metodológica óbvia, diga claramente — sem eufemismos.

**FORMATO:**
- Escreva em formato de FALA, não de texto escrito
- Sem marcações técnicas ([PAUSA], [MÚSICA], etc.)
- Somente o texto que será falado
- Target: 1.500-2.500 palavras totais (podcasts de 10-15 minutos)

Agora gere o script completo:
"""

    # ------------------------------------------------------------------
    # GERAÇÃO DE ÁUDIO
    # ------------------------------------------------------------------

    def generate_audio(self, script: str, output_path: str) -> bool:
        """Gera o arquivo de áudio a partir do script via ElevenLabs TTS (PT-BR)."""
        try:
            from elevenlabs_audio_generator import ElevenLabsAudioGenerator
            generator = ElevenLabsAudioGenerator()
            return generator.generate_audio(text=script, output_path=output_path)
        except Exception as e:
            print(f"  ❌ Erro ao gerar áudio: {e}")
            return False

    # ------------------------------------------------------------------
    # PIPELINE PRINCIPAL
    # ------------------------------------------------------------------

    def run(
        self,
        journal_alias: str,
        issue_override: str = None,  # formato "volume/issue", ex: "151/3"
        generate_audio: bool = False,
        output_dir: str = None,
    ):
        """
        Pipeline completo:
        1. Resolve nome da revista
        2. Busca número mais recente (ou usa issue_override)
        3. Baixa artigos
        4. Gera script
        5. Salva script (e opcionalmente áudio)
        """
        print("\n" + "=" * 60)
        print(f"  📡 CARDIO DAILY RADAR v3 — {journal_alias.upper()}")
        print("=" * 60)

        # 1. Resolver revista
        pubmed_name = self.resolve_journal(journal_alias)
        if not pubmed_name:
            print(f"❌ Revista '{journal_alias}' não reconhecida.")
            print("   Revistas disponíveis:", list(JOURNAL_MAP.keys())[:10], "...")
            return

        print(f"📰 Revista: {pubmed_name}")

        # 2. Volume/Issue
        if issue_override:
            parts = issue_override.split("/")
            if len(parts) != 2:
                print("❌ Formato de issue inválido. Use: volume/issue (ex: 151/3)")
                return
            volume, issue = parts[0].strip(), parts[1].strip()
            print(f"   Usando issue especificado: Vol {volume}, Issue {issue}")
        else:
            result = self.get_latest_issue_info(pubmed_name)
            if not result:
                return
            volume, issue = result

        # 3. Buscar artigos
        articles = self.fetch_issue_articles(pubmed_name, volume, issue)
        if not articles:
            print("❌ Nenhum artigo encontrado para este número.")
            return

        # Resumo do que foi encontrado
        print(f"\n📋 Artigos por tipo:")
        from collections import Counter
        type_counts = Counter(a["article_type"] for a in articles)
        for atype, count in type_counts.most_common():
            print(f"   {atype}: {count}")

        # 4. Gerar script
        script = self.generate_podcast_script(articles, pubmed_name, volume, issue)
        if not script:
            return

        # 5. Salvar
        output_dir = output_dir or radar_config.OUTPUT_SCRIPT_DIR
        os.makedirs(output_dir, exist_ok=True)

        journal_slug = journal_alias.replace(" ", "_").upper()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        base_name = f"RADAR_{journal_slug}_vol{volume}_n{issue}_{timestamp}"

        # Salvar script
        script_path = os.path.join(output_dir, f"{base_name}_script.md")
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(f"# Radar {pubmed_name} — Vol. {volume}, n. {issue}\n")
            f.write(f"*Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')}*\n\n---\n\n")
            f.write(script)

        print(f"\n💾 Script salvo: {script_path}")

        # Salvar metadados dos artigos
        meta_path = os.path.join(output_dir, f"{base_name}_articles.json")
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(articles, f, ensure_ascii=False, indent=2)

        print(f"📊 Metadados: {meta_path}")

        # 6. Áudio (opcional)
        if generate_audio:
            audio_path = os.path.join(output_dir, f"{base_name}.mp3")
            print(f"\n🎙️  Gerando áudio...")
            success = self.generate_audio(script, audio_path)
            if success:
                print(f"🎧 Áudio salvo: {audio_path}")

        print(f"\n✅ Radar concluído!")
        print("=" * 60)


# ==============================================================================
# ENTRY POINT
# ==============================================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="CardioDaily Radar v3 — Busca automática via PubMed",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog="""
Exemplos:
  python3 src/radar/journal_issue_fetcher.py --journal "circulation"
  python3 src/radar/journal_issue_fetcher.py --journal "jacc" --audio
  python3 src/radar/journal_issue_fetcher.py --journal "nejm" --issue "393/5"
  python3 src/radar/journal_issue_fetcher.py --journal "eur heart j" --audio

Revistas suportadas:
  circulation, jacc, nejm, jama, lancet, eur heart j, heart,
  jacc heart failure, jacc imaging, jacc interv, circ heart fail,
  hypertension, atherosclerosis, stroke, jaha, e mais.
        """,
    )
    parser.add_argument(
        "--journal", "-j",
        required=True,
        help='Nome da revista (ex: "circulation", "jacc", "nejm")',
    )
    parser.add_argument(
        "--issue", "-i",
        default=None,
        help='Issue específico no formato volume/issue (ex: "151/3"). Padrão: último número.',
    )
    parser.add_argument(
        "--audio", "-a",
        action="store_true",
        help="Gera arquivo de áudio MP3 além do script",
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help=f"Pasta de saída. Padrão: {radar_config.OUTPUT_SCRIPT_DIR}",
    )

    args = parser.parse_args()

    fetcher = JournalIssueFetcher()
    fetcher.run(
        journal_alias=args.journal,
        issue_override=args.issue,
        generate_audio=args.audio,
        output_dir=args.output,
    )
