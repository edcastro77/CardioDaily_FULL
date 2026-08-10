"""
classificador_prompt_v5.py — O LLM EXTRAI SINAIS. O CÓDIGO DECIDE.

═══════════════════════════════════════════════════════════════════════════════════════
POR QUE O v3/v4 PRECISOU SER JOGADO FORA (10/Ago/2026)
═══════════════════════════════════════════════════════════════════════════════════════

Palavras do Dr. Eduardo: *"não adianta remendar o v3 — de alguma forma, nós dois, SEM PESO E
SEM MÉTRICA, nós erramos ao construir o v3."*

Ele tem razão, e os dois erros são estruturais:

ERRO 1 — A REGRA 1 DIZIA QUE O RÓTULO DE SEÇÃO MANDA ACIMA DE TUDO.
    "ORIGINAL RESEARCH ARTICLE · ORIGINAL ARTICLE · ORIGINAL INVESTIGATION → artigo_original"
    Medido nos 13 papers que ele abriu em 10/Ago: o rótulo MENTIU em 2.
      · "Cardiovascular Disease Screening in LMICs"  — carimbo ORIGINAL RESEARCH,
        e é "A Systematic Review", com PROSPERO CRD420251241426 e PRISMA
      · "Effects of Omega-3 on Risk for AF"          — carimbo ORIGINAL ARTICLE,
        e é "An Updated Meta-Analysis of 35 Trials including 114.592 Individuals"
    "ORIGINAL RESEARCH" é o nome da SEÇÃO da revista, não o desenho do estudo. E no mesmo dia
    eu tinha tirado essa camada da CASCATA e deixado a regra viva AQUI — LEI 9 na minha cara.

ERRO 2 — A "TRAVA DA REVISÃO SISTEMÁTICA" ERA UM **OU** ENTRE SINAIS DE FORÇAS DIFERENTES.
    "responda meta se declarar PELO MENOS UM: busca nomeando bases; critérios de elegibilidade;
     número de estudos; PRISMA; pooled ou I²"
    "We conducted a PubMed search" valia o mesmo que "I² = 94,8 %". E TODA revisão narrativa da
    JAMA tem a primeira frase — é o parágrafo padrão da seção Clinical Review & Education.
    Resultado medido: "Gastroparesis: A Review" e "Alcohol-Related Liver Disease: A Review"
    foram para a pasta de META-ANÁLISE, com confiança ALTA, citando essa frase como prova.
    O motor da Escada ia cobrar PROSPERO, I² e Trim-and-Fill de uma revisão do Camilleri.
    O modelo não errou: obedeceu uma regra que confunde PROCURAR com SOMAR.

═══════════════════════════════════════════════════════════════════════════════════════
A ARQUITETURA NOVA — A MESMA DA LEI 0
═══════════════════════════════════════════════════════════════════════════════════════

O `notas_prototipo.py` não pergunta a nota ao modelo: ele recebe FATOS e aplica `min(tetos)` em
código determinístico. É por isso que a nota é reprodutível e auditável. O classificador era o
único bloco da casa que ainda pedia OPINIÃO — e opinião não repete: em 10/Ago o mesmo
"Alcohol-Related Liver Disease" foi classificado DUAS vezes pelo mesmo modelo, uma como
`revisao_geral` e outra como `revisao_sistematica_meta_analise`, as duas com confiança ALTA.

Agora: **o LLM olha e RELATA o que viu. O código DECIDE.**
Sinal é fato — ou o `PROSPERO` está no texto ou não está. Fato repete.

E dá para medir cada sinal separado: quando errar, a gente sabe QUAL sinal falhou, em vez de
saber só que "o classificador errou".

═══════════════════════════════════════════════════════════════════════════════════════
A ESPINHA — DECISÃO DO DR. EDUARDO, 10/Ago
═══════════════════════════════════════════════════════════════════════════════════════

*"ARTIGO ORIGINAL SEMPRE USA IMRD — onde, ao invés de pesquisar por artigos na internet, ele
coloca o contexto; em MÉTODOS ele explica como fez a seleção de PACIENTES (não de artigos), e
mesmo que seja coorte, análise retrospectiva etc. É totalmente diferente de meta-análise — e
diferente das revisões, que eu nunca vi usar IMRD."*

A pergunta que separa os três não é "o que o artigo é". É:

        ┌──────────────────────────────────────────────┐
        │  A seção MÉTODOS descreve a seleção de QUÊ?  │
        └──────────────────────────────────────────────┘
             PACIENTES  →  artigo original
             ESTUDOS    →  revisão sistemática / meta-análise
             (não há)   →  revisão narrativa / diretriz

Conferido nos 13 papers de 10/Ago:
  · as 11 metas: Métodos = "Search strategy", "Study selection", "Data extraction", "Eligibility"
  · o Gastroparesis (JAMA Review): nem tem Métodos como espinha — tem "Physiology of Normal
    Gastric Motor Function", "Pathophysiology", "Risk Factors". Estrutura TEMÁTICA. O Camilleri
    não selecionou nada: ele ORGANIZOU um tema.
"""
import re

import fitz

PROMPT_VERSAO = "v5"

# ═══════════════════════════════════════════════════════════════════════════════════════
# O PROMPT — o modelo RELATA. Não julga.
# ═══════════════════════════════════════════════════════════════════════════════════════
PROMPT = """Você é um leitor técnico. Sua tarefa NÃO é dizer que tipo de artigo é este — é
RELATAR, com fidelidade, o que você vê nas páginas abaixo. Quem decide o tipo é outro programa.

Responda EXATAMENTE neste formato, uma linha por campo, nada mais:

ESTRUTURA: IMRD | TEMATICA | RECOMENDACOES | INDEFINIDA
METODOS_SELECIONA: PACIENTES | ESTUDOS | NADA
REGISTRO_REVISAO: <trecho literal com PROSPERO/CRD/PRISMA, ou NAO>
SINTESE_QUANTITATIVA: <trecho literal com estimativa agrupada, I², modelo de efeitos aleatórios
   ou forest plot, ou NAO>
ABSTRACT_CABECALHOS: <os cabeçalhos do resumo, na ordem, separados por barra, ou NAO>
TITULO: <o título literal do artigo>
LINHA_DE_TIPO: <a linha em que a revista declara o formato, ex.: "JAMA | Review", "Seminar",
   "ORIGINAL RESEARCH", ou NAO>
RECOMENDACOES_FORMAIS: <trecho com classe de recomendação / nível de evidência / writing
   committee, ou NAO>
UM_PACIENTE: <trecho mostrando que o texto descreve UM caso único, ou NAO>
PROVA: <o trecho que você considera mais decisivo, até 25 palavras>
CONFIANCA: alta | media | baixa

═══ COMO PREENCHER CADA CAMPO ═══

ESTRUTURA — o esqueleto do artigo, pelos títulos das seções:
  IMRD          Introdução → Métodos → Resultados → Discussão (com esses nomes ou equivalentes:
                Background/Methods/Results/Discussion). É o formato de quem PRODUZIU um resultado.
  TEMATICA      as seções são ASSUNTOS, não etapas: "Epidemiologia", "Fisiopatologia",
                "Diagnóstico", "Tratamento", "Physiology of Normal Gastric Motor Function".
                É o formato de quem ORGANIZA conhecimento.
  RECOMENDACOES o corpo é uma sequência de recomendações numeradas, com classe e nível.
  INDEFINIDA    o texto abaixo não mostra as seções (só capa, só cabeçalho).
  ⚠️ Um artigo pode ter um parágrafo chamado "Methods" e ainda assim ser TEMATICA — o que
  decide é o ESQUELETO INTEIRO, não a presença de uma palavra.

METODOS_SELECIONA — o campo mais importante. Se existe seção de métodos, ela explica como
foram escolhidos:
  PACIENTES  pessoas, participantes, prontuários, exames, animais, amostras. Sinais: "we
             enrolled", "consecutive patients", "inclusion criteria: age ≥ 18", "we
             retrospectively reviewed the records of", número de registro NCT, aprovação de
             comitê de ética, consentimento informado.
  ESTUDOS    artigos, ensaios, publicações em bases de dados. Sinais: "we searched MEDLINE /
             Embase / Cochrane / Scopus / Web of Science", "studies were eligible if",
             "N studies (n = X patients) were included", fluxograma de seleção de estudos.
  NADA       não há seleção formal de nada — ou não há métodos, ou o parágrafo apenas conta
             que os autores leram a literatura, sem critérios de elegibilidade nem contagem.
  ⚠️ ATENÇÃO, É AQUI QUE O CLASSIFICADOR ANTIGO ERRAVA: a frase "We conducted a PubMed search
  for English-language articles" aparece em QUASE TODA revisão narrativa de revista grande.
  Ela sozinha NÃO é seleção de estudos. Só marque ESTUDOS se houver critérios de elegibilidade
  OU contagem de estudos incluídos OU fluxograma de seleção.

REGISTRO_REVISAO — copie o trecho literal se aparecer PROSPERO, um número CRD, ou a palavra
  PRISMA. Estes só existem em revisão sistemática: ninguém registra revisão narrativa.

SINTESE_QUANTITATIVA — copie o trecho literal se houver estimativa AGRUPADA de vários estudos:
  "pooled HR/RR/OR", "random-effects model", "I² = ", "forest plot", "meta-regression".
  ⚠️ NÃO confunda com os resultados do próprio estudo: um ensaio clínico também reporta HR e
  IC95%. O que conta aqui é o agrupamento DE ESTUDOS.

ABSTRACT_CABECALHOS — copie os cabeçalhos do resumo na ordem em que aparecem, ex.:
  "IMPORTANCE / OBSERVATIONS / CONCLUSIONS AND RELEVANCE"
  "BACKGROUND / METHODS / RESULTS / CONCLUSIONS"
  "IMPORTANCE / OBJECTIVE / DATA SOURCES / STUDY SELECTION / DATA EXTRACTION AND SYNTHESIS"
  Se o resumo for um parágrafo corrido sem cabeçalhos, responda NAO.

LINHA_DE_TIPO — a linha em que a PRÓPRIA REVISTA declara o formato do artigo. Copie literal.
  ⚠️ Copie mesmo que ela contradiga tudo o mais. Quem pesa isso é o programa, não você.

UM_PACIENTE — só marque se o texto descreve UM caso individual como objeto do artigo. Uma
  discussão de caso com fim EDUCACIONAL ("case-based review", "an illustrative case") NÃO é
  isso: nela o caso é pretexto para ensinar.

REGRAS GERAIS
  · COPIE trechos literais. Não resuma, não interprete, não traduza.
  · Se um campo não existir no texto, escreva NAO. Não invente e não deduza.
  · CITAR não é SER: um artigo que MENCIONA "meta-analysis" nas referências ou na discussão não
    tem síntese quantitativa. Só conta o que o PRÓPRIO artigo faz.
  · Se as páginas abaixo forem só capa, sem resumo e sem seções, marque ESTRUTURA: INDEFINIDA
    e CONFIANCA: baixa.

TEXTO (páginas 1 a 3):
{texto}
"""

# ═══════════════════════════════════════════════════════════════════════════════════════
# A DECISÃO — CÓDIGO, NÃO OPINIÃO
# ═══════════════════════════════════════════════════════════════════════════════════════
#
# A ordem abaixo É a hierarquia de peso. Cada degrau só é consultado se o de cima calar.
# Os pesos vêm da medição de 10/Ago (13 papers abertos pelo Dr. Eduardo + 111 do gabarito):
#
#   DECISIVO   PROSPERO/PRISMA · síntese quantitativa · cabeçalhos DATA SOURCES/STUDY SELECTION
#              · cabeçalho OBSERVATIONS · METODOS_SELECIONA
#   FORTE      título declarando o formato · linha de tipo da revista
#   ZERO       "we conducted a PubMed search" (toda revisão narrativa tem)
#   CONFERE    rótulo de seção (ORIGINAL RESEARCH) — mentiu em 2 de 13, nunca decide
_T_META = re.compile(r"meta[-\s]?analy|systematic\s+review|pooled\s+analys|individual[-\s]patient[-\s]data|IPDMA|revis[ãa]o\s+sistem[áa]tica", re.I)
_T_REVIEW = re.compile(r":\s*(a|an)\s+[a-z\-]*\s*review\s*\.?\s*$|^review\b", re.I)
_ABS_SISTEMATICA = re.compile(r"data\s+sources|study\s+selection|data\s+extraction", re.I)
_ABS_NARRATIVA = re.compile(r"\bobservations\b", re.I)
_TIPO_REVISAO = re.compile(r"\breview\b|\bseminar\b|state[-\s]of[-\s]the[-\s]art", re.I)
_TIPO_DIRETRIZ = re.compile(r"guideline|scientific\s+statement|consensus|position\s+paper", re.I)
_TIPO_BREVE = re.compile(r"brief\s+(report|communication)|short\s+(report|communication)|research\s+brief|heart\s+of\s+the\s+matter", re.I)
_TIPO_OPINIAO = re.compile(r"editorial|viewpoint|perspective|comment\b", re.I)


def _tem(v):
    """O campo foi preenchido com conteúdo de verdade (não NAO/vazio)?"""
    s = (v or "").strip()
    return bool(s) and s.upper() not in ("NAO", "NÃO", "NO", "NONE", "-", "N/A")


def decidir(s):
    """Recebe os SINAIS relatados pelo modelo. Devolve (tipo, porque).

    Função pura: mesmos sinais, mesma resposta, sempre. É isto que o v3 não tinha — lá o mesmo
    artigo saiu `revisao_geral` numa rodada e `revisao_sistematica_meta_analise` na seguinte,
    as duas com confiança alta.
    """
    estrutura = (s.get("estrutura") or "").upper()
    seleciona = (s.get("metodos_seleciona") or "").upper()
    titulo = s.get("titulo") or ""
    linha = s.get("linha_de_tipo") or ""
    abst = s.get("abstract_cabecalhos") or ""

    # ── 1. DIRETRIZ — recomendações formais é o que nenhum outro tipo tem ──
    if _tem(s.get("recomendacoes_formais")) or estrutura == "RECOMENDACOES" \
            or _TIPO_DIRETRIZ.search(linha):
        return "guideline", "recomendações formais (classe/nível) ou linha de tipo de diretriz"

    # ── 2. RELATO DE CASO — um paciente é o objeto ──
    if _tem(s.get("um_paciente")):
        return "relato_de_caso", "o artigo descreve UM caso como objeto"

    # ── 3. SISTEMÁTICA / META — os três sinais decisivos, qualquer um basta ──
    # PROSPERO e PRISMA não existem fora de revisão sistemática. Síntese quantitativa é somar
    # estudos. Os cabeçalhos DATA SOURCES/STUDY SELECTION são o formato de resumo que a JAMA
    # reserva para revisão sistemática.
    if _tem(s.get("registro_revisao")):
        return "revisao_sistematica_meta_analise", "registro PROSPERO/PRISMA declarado"
    if _tem(s.get("sintese_quantitativa")):
        return "revisao_sistematica_meta_analise", "síntese quantitativa (agrupamento de estudos)"
    if _ABS_SISTEMATICA.search(abst):
        return "revisao_sistematica_meta_analise", "resumo com DATA SOURCES / STUDY SELECTION"

    # ── 4. A ESPINHA (Dr. Eduardo, 10/Ago): o que os MÉTODOS selecionam ──
    if seleciona == "ESTUDOS":
        return "revisao_sistematica_meta_analise", "os métodos selecionam ESTUDOS"
    if seleciona == "PACIENTES":
        # ⚠️ o formato BREVE é decisão dele (31/Jul): brief report não sustenta a perícia de um
        # original, mesmo trazendo dado primário.
        if _TIPO_BREVE.search(linha):
            return "minirevisao", "dado primário, mas formato BREVE declarado pela revista"
        return "artigo_original", "os métodos selecionam PACIENTES (IMRD)"

    # ── 5. NÃO SELECIONA NADA → é revisão. Qual? ──
    # Aqui o TÍTULO e a LINHA DE TIPO valem, porque são declaração de formato — e é o único
    # ponto em que sinal FORTE decide, depois de todos os DECISIVOS calarem.
    if _ABS_NARRATIVA.search(abst):
        return "revisao_geral", "resumo com OBSERVATIONS (formato de revisão narrativa)"
    if _T_META.search(titulo):
        return "revisao_sistematica_meta_analise", "o título declara revisão sistemática/meta"
    if _TIPO_BREVE.search(linha):
        return "minirevisao", "formato breve declarado pela revista"
    if _TIPO_OPINIAO.search(linha):
        return "ponto_de_vista", "linha de tipo de editorial/viewpoint"
    if _TIPO_REVISAO.search(linha) or _T_REVIEW.search(titulo) or estrutura == "TEMATICA":
        return "revisao_geral", "estrutura temática / a revista declara revisão"

    return "incerto", "nenhum sinal decisivo e nenhuma declaração de formato"


# ═══════════════════════════════════════════════════════════════════════════════════════
# LEITURA DA RESPOSTA
# ═══════════════════════════════════════════════════════════════════════════════════════
_CAMPOS = ("ESTRUTURA", "METODOS_SELECIONA", "REGISTRO_REVISAO", "SINTESE_QUANTITATIVA",
           "ABSTRACT_CABECALHOS", "TITULO", "LINHA_DE_TIPO", "RECOMENDACOES_FORMAIS",
           "UM_PACIENTE", "PROVA", "CONFIANCA")
_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
TETO_CHARS = 20_000


def paginas_1a3(caminho):
    doc = fitz.open(caminho)
    return _CTRL.sub("", "".join(doc[i].get_text() for i in range(min(3, len(doc)))))


def montar(texto):
    return PROMPT.format(texto=(texto or "")[:TETO_CHARS])


def ler_sinais(saida):
    """Extrai os 11 campos. Campo ausente vira "" — e "" nunca é tomado por sinal presente."""
    out = {}
    txt = saida or ""
    for i, c in enumerate(_CAMPOS):
        prox = "|".join(_CAMPOS[i + 1:]) or "\\Z"
        m = re.search(rf"^{c}:\s*(.*?)(?=^(?:{prox}):|\Z)", txt, re.M | re.S)
        out[c.lower()] = _CTRL.sub("", (m.group(1) if m else "")).strip().replace("\n", " ")[:300]
    return out


def classificar(saida):
    """(tipo, confianca, prova, porque, sinais) — tudo o que a rodada precisa registrar."""
    s = ler_sinais(saida)
    tipo, porque = decidir(s)
    conf = (s.get("confianca") or "").lower().replace("é", "e")
    conf = conf if conf in ("alta", "media", "baixa") else ""
    return tipo, conf, s.get("prova", ""), porque, s
