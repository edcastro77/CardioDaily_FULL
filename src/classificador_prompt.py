"""
classificador_prompt.py — O PROMPT DA CLASSIFICAÇÃO, EM UM LUGAR SÓ (02/Ago/2026).

POR QUE EXISTE (LEI 8). Até hoje havia DOIS prompts de classificação:
  • o da PROVA (`prova_classificador.py`), versão v3, medido em 110/111 = 99,1 % com gpt-5.6-luna
  • o da PRODUÇÃO (`classificador_ouro.py`), antigo — e que **contradizia a DECISÃO D-01
    do Dr. Eduardo** ("revisão sistemática É meta-análise"), porque mandava literalmente:
        "(Meta-análise NÃO é opção aqui). Se o artigo parecer meta/revisão sistemática,
         escolha revisao_geral."
    Além disso lia só 5.000 caracteres e não conhecia `minirevisao`.

Enquanto os dois textos viveram em arquivos diferentes, o 99,1 % media UMA COISA e a produção
fazia OUTRA. Medir um e rodar o outro não é medição — é ilusão de medição.
Agora existe UM prompt. A prova e a produção importam DAQUI. Se alguém mexer no texto, o número
da prova e o comportamento da Chave 1 mudam JUNTOS — que é o único jeito de o número significar algo.

HISTÓRICO DAS VERSÕES (medido em 31/07/2026, 111 artigos do gabarito do Dr. Eduardo):
  v1 — Luna 91,9 % · Sonnet 90,1 % · Haiku 89,2 % (com opiniao ≡ minirevisao).
       Erros residuais: case-based virando relato_de_caso (5), narrativa virando sistemática (2).
  v2 — case-based educacional = minirevisao · TRAVA da revisão sistemática.
       Luna 110/111 = 99,1 %. (2 dos 3 "erros" eram do GABARITO: os artigos DECLARAVAM PRISMA.)
       Erro restante: "JACC STATE-OF-THE-ART REVIEW" virou minirevisao.
  v3 — o RÓTULO IMPRESSO de seção vence a impressão de "parece opinião".
  v4 (02/Ago) — BRIEF REPORT/SHORT REPORT → minirevisao (F-02, aberta desde 31/Jul) e SEMINAR
       (rótulo do Lancet) → revisao_geral. ⚠️ O texto MUDOU: os 99,1 % foram medidos no v3 e
       NÃO valem para o v4 até a Chave 6 rodar de novo. ← EM USO
"""
import re

import fitz

# VERSÃO DO PROMPT — entra na chave de retomada da prova. Sem isto, mudar o prompt e rodar de novo
# NÃO refaz nada (o CSV acha que já foi feito) e a comparação entre versões fica impossível.
PROMPT_VERSAO = "v4"

# DECISÃO D-01 do Dr. Eduardo (31/07): revisão sistemática = meta-análise, mesma trilha.
PROMPT = """Você classifica o TIPO de um artigo científico de cardiologia. Abaixo estão as
primeiras páginas do PDF, como saíram do arquivo (pode vir capa, cabeçalho e texto misturado).

Responda EXATAMENTE em três linhas, nada mais:
TIPO: <uma palavra da lista>
CONFIANCA: alta | media | baixa
PROVA: <trecho LITERAL do texto abaixo que sustenta sua resposta, até 20 palavras>

LISTA DE TIPOS:
- artigo_original — coleta dados primários em sujeitos. Inclui RCT, coorte, caso-controle,
  transversal, registro, e também estudos de modelagem/custo-efetividade construídos sobre dados.
  Sinais: "we enrolled/recruited N patients", "randomly assigned", regressão, Cox, HR, NCT.
- revisao_sistematica_meta_analise — revisão SISTEMÁTICA (com ou sem meta-análise) e meta-análise.
  Sinais: busca em bases declarada, PRISMA, fluxograma de seleção, estimativa agrupada, I².
- revisao_geral — revisão NARRATIVA / state-of-the-art / educacional. Sem busca sistemática.
- guideline — diretriz, consenso, position paper, scientific statement de sociedade
  (AHA/ACC/ESC/SBC). Sinais: classe de recomendação, nível de evidência, "writing committee".
- ponto_de_vista — editorial, comentário editorial, viewpoint, perspectiva.
- minirevisao — texto CURTO de especialista atualizando um tema ou comentando um estudo, típico de
  suplemento de congresso (European Heart Journal Supplements, "The Heart of the Matter") ou de
  seção editorial de revista. **INCLUI as discussões de caso com FIM EDUCACIONAL** — "case-based
  review", "a clinical case-based discussion", "an illustrative case highlighting patient selection".
  Nessas, o caso é PRETEXTO para ensinar conduta: isso é minirevisao, NÃO relato_de_caso.
- relato_de_caso — relato de UM caso publicado como "Case Report" da revista, com o objetivo de
  descrever o caso em si (achado raro, complicação inédita, técnica nova em um paciente).
- carta_de_pesquisa — research letter / carta ao editor (formato breve).
- incerto — se o texto abaixo NÃO permitir decidir com segurança.

REGRAS QUE VALEM MAIS QUE A SUA IMPRESSÃO:
1. O RÓTULO DE SEÇÃO IMPRESSO PELA REVISTA MANDA, e manda acima de tudo. Se ele aparecer no texto,
   ele DECIDE — mesmo que o artigo "pareça" outra coisa, mesmo que seja curto, opinativo ou
   assinado por poucos autores. Correspondência obrigatória:
     ORIGINAL RESEARCH ARTICLE · ORIGINAL ARTICLE · ORIGINAL INVESTIGATION · CLINICAL RESEARCH
        → artigo_original
     STATE-OF-THE-ART REVIEW · REVIEW ARTICLE · JACC REVIEW TOPIC OF THE WEEK · IN DEPTH · FRONTIERS
     SEMINAR (é como o Lancet chama suas revisões) · CLINICAL UPDATE · THERAPY IN PRACTICE
        → revisao_geral   (NUNCA minirevisao — por mais que o texto pareça ensaio de opinião)
     AHA SCIENTIFIC STATEMENT · SCIENTIFIC STATEMENT · CLINICAL PRACTICE GUIDELINE · CONSENSUS
     DOCUMENT · POSITION PAPER  → guideline
     THE HEART OF THE MATTER · BRIEF REPORT · BRIEF COMMUNICATION · SHORT REPORT
     RESEARCH BRIEF · SHORT COMMUNICATION  → minirevisao
        (decisão do Dr. Eduardo: BRIEF REPORT é minirevisão, NÃO artigo original — mesmo quando
         traz dado primário. O formato breve não sustenta a perícia de um original.)
     EDITORIAL · EDITORIAL COMMENT · VIEWPOINT  → ponto_de_vista
   Só use o julgamento dos itens 2 a 5 quando NÃO houver rótulo impresso.
2. Se não houver rótulo, o juiz é o METHODS: quem COLETA dado de paciente é artigo_original;
   quem BUSCA estudos em base é revisao_sistematica_meta_analise; quem não faz nem um nem outro
   é revisao_geral ou guideline.
3. CITAR não é SER. Um artigo que MENCIONA "meta-analysis" ou "guideline" no texto não vira
   meta-análise nem diretriz. Só o que o artigo É conta.
4. TRAVA DA REVISÃO SISTEMÁTICA — só responda revisao_sistematica_meta_analise se o artigo
   DECLARAR pelo menos um destes: busca nomeando bases (PubMed, Embase, Cochrane, Web of Science);
   critérios de elegibilidade/inclusão e exclusão; número de estudos incluídos; fluxograma PRISMA;
   estimativa agrupada (pooled) ou I². **Se nada disso aparecer, é revisao_geral** — por mais
   completa, longa ou "abrangente" que a revisão pareça. Revisão narrativa boa continua narrativa.
5. Se o texto abaixo for só capa (título, autores, "Downloaded from…") sem abstract nem methods,
   responda incerto — NÃO adivinhe.

TEXTO (páginas 1 a 3):
{texto}
"""

_RE_TIPO = re.compile(r"TIPO:\s*([a-z_]+)", re.I)
_RE_CONF = re.compile(r"CONFIANCA:\s*(alta|m[eé]dia|media|baixa)", re.I)
_RE_PROVA = re.compile(r"PROVA:\s*(.+)", re.I | re.S)
_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

TIPOS = {"artigo_original", "revisao_sistematica_meta_analise", "revisao_geral", "guideline",
         "ponto_de_vista", "minirevisao", "relato_de_caso", "carta_de_pesquisa", "incerto"}

TETO_CHARS = 20_000     # o que a prova mediu; mudar isto invalida o 99,1 %


def paginas_1a3(caminho):
    """As 3 PRIMEIRAS páginas do PDF. A produção lia 5.000 caracteres do começo — e o rótulo
    impresso da seção ('ORIGINAL INVESTIGATION', 'STATE-OF-THE-ART REVIEW'), que é a REGRA 1 deste
    prompt, muitas vezes está na página 2 ou 3. Foi o que levou o acerto de 54 % para 87 %."""
    doc = fitz.open(caminho)
    return _CTRL.sub("", "".join(doc[i].get_text() for i in range(min(3, len(doc)))))


def montar(texto):
    return PROMPT.format(texto=(texto or "")[:TETO_CHARS])


def ler_resposta(saida):
    """Devolve (tipo, confianca, prova). Mesmo parser da prova — para o que foi medido lá ser
    exatamente o que acontece aqui."""
    mt = _RE_TIPO.search(saida or "")
    tipo = (mt.group(1).lower() if mt else "")
    if tipo not in TIPOS:                                # rede de segurança: varre a resposta
        tipo = next((t for t in TIPOS if t in (saida or "").lower()), "")
    mc = _RE_CONF.search(saida or "")
    mp = _RE_PROVA.search(saida or "")
    prova = _CTRL.sub("", (mp.group(1) if mp else "")).strip().replace("\n", " ")[:160]
    conf = (mc.group(1).lower().replace("é", "e") if mc else "")
    return tipo, conf, prova
