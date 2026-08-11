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
# ═══════════════════════════════════════════════════════════════════════════════════════
# v6 — 10/Ago/2026 · SEIS REGRAS, TODAS DITADAS PELO DR. EDUARDO SOBRE ERRO MEDIDO
# ═══════════════════════════════════════════════════════════════════════════════════════
#
# ⚠️ O NÚMERO 5 FOI PULADO DE PROPÓSITO. O `classificador_prompt_v5.py` é OUTRA arquitetura
# (o LLM relata sinais, o código decide) que foi construída, medida e REPROVADA em 10/Ago:
# 61,9 % contra 90,5 % do v4, com 29 regressões. Ele fica no disco como registro do que não
# funcionou — reusar o número criaria duas coisas chamadas v5.
#
# O v6 NÃO é redesenho. É o v4 com seis regras trocadas, cada uma nascida de um artigo que
# ele abriu e julgou à mão, com o motivo escrito na planilha `GABARITO_16_para_julgar.xlsx`.
# Medição de partida (105 artigos, gabarito v2): v4 = 90,5 %, 11 erros, 4 deles GRAVES.
#
#  A · TRIBUTO NÃO É ARTIGO — 6 dos 11 erros
#      Os tributos póstumos ao Braunwald (JACC, julho/2026) vinham como `ponto_de_vista`.
#      Ele: *"são um tributo pós-morte... prestando homenagem ao homem que transformou a
#      cardiologia no século 20"* → DESCARTAR. Categoria que não existia no prompt.
#      ⚠️ Esta regra vive TAMBÉM no `classificador_ouro.eh_descartavel` — lá ela é
#      determinística e nem chama o modelo. LEI 9: as duas foram mexidas juntas.
#
#  B · GUIDELINE É GRADUAÇÃO, NÃO É NOME — 2 erros GRAVES, em sentidos opostos
#      KDIGO (dizia revisão): *"se ler as primeiras páginas fica fácil entender que isso aqui
#      tem recomendações graduadas — logo é um guideline"*
#      ACC Expert Consensus (dizia guideline): *"você não vê ele determinar a graduação de
#      recomendações"*
#      Mesmo teste nas duas direções. E o motivo de fundo é o MOTOR, não a taxonomia:
#      *"nosso prompt vai tentar explorar qual percentual de recomendações se baseiam em
#      padrão de evidência A, B ou C"* — documento sem graduação quebra o motor AGREE.
#
#  C · BUSCA SOZINHA VALE ZERO — 1 erro GRAVE
#      Galen Medical Journal, "Intravascular Imaging-Guided PCI". Única evidência no texto:
#      "A structured literature search was conducted using PubMed, Embase, and Cochrane".
#      Conferido nas 3 páginas: SEM "systematic review", SEM PRISMA, SEM PROSPERO, SEM
#      critérios de elegibilidade, SEM I²/pooled. E ainda MENCIONA meta-análises (como as
#      fontes que revisou) — a regra "CITAR não é SER" sendo violada pelo próprio prompt.
#      Ele: *"se ele leu o resumo e não tem métodos com 'A systematic review was conducted
#      according to PRISMA'... então não pode ser meta-análise!"*
#      Comparação que fixa a regra — os dois que ELE classificou como meta têm o oposto:
#        Arquivos Bras.: "A Systematic Review" no título · PRISMA · PROSPERO CRD420251044229
#        J Clin Med   : "systematic review conducted according to PRISMA" · random-effects
#
#  D · BRIEF REPORT DE ENSAIO CONTINUA SENDO ORIGINAL — 1 erro
#      Corrige a regra dele de 31/Jul ("BRIEF REPORT é minirevisão"). O caso: JAMA Cardiology
#      Brief Report que é *"A Randomized Clinical Trial"*. Ele: *"no resumo ele segue a
#      cartilha IMRD — define o problema, testa uma hipótese (OBJECTIVE To test the
#      hypothesis...), estabelece os métodos (DESIGN, SETTING, AND PARTICIPANTS...), diz qual
#      intervenção será testada (INTERVENTION...)"*. O formato breve sozinho não basta.
#
#  E · PÁGINA SEPARA REVISÃO DE PONTO DE VISTA — 1 erro
#      Ele: *"em praticamente todos os pontos de vista que vi tem menos de 3 páginas — se tem
#      mais de 5 páginas, fica como revisão"*, e depois: *"estou diferenciando apenas revisão
#      de ponto de vista — isto não se aplica a artigo original, que no caso seria obrigatório
#      o IMRD."*
#      MEDIDO no gabarito de 105: ponto de vista = 2 páginas · tributos = 2,2,2,3,3,3 ·
#      minirevisão mediana 6 · revisão narrativa MÍNIMO 8 · original mínimo 5.
#      Abaixo de 3 páginas não existe original, revisão, meta nem minirrevisão. Corte limpo.
#      O caso: "Cardiovascular Health Across the Life Course" tem VIEWPOINT impresso e ele
#      classificou revisão — *"delimitou um tema e diz que seu objetivo é revisar como as
#      terapias modernas podem impactar"*. Contra "The Next Phase of Cardio-Oncology", que É
#      ponto de vista — *"não tem IMRD, não tem recomendação formal, não avança sobre uma
#      doença específica"*.
#
#  F · ARTIGO ORIGINAL É IMRD, E O IMRD SELECIONA PACIENTES
#      Ele: *"ARTIGO ORIGINAL SEMPRE USA IMRD — onde, ao invés de pesquisar por artigos na
#      internet, em MÉTODOS ele explica como fez a seleção de PACIENTES (não de artigos)...
#      As revisões eu nunca vi usar IMRD."*
#      É a única regra que sobreviveu inteira da arquitetura reprovada do v5 — lá ela era o
#      campo `METODOS_SELECIONA`, e nos 13 papers que ele abriu acertou 11 de 11.
PROMPT_VERSAO = "v6"

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
- tributo — homenagem, obituário, memorial ou perfil biográfico de um médico ou pesquisador.
  Rótulos: TRIBUTE · IN MEMORIAM · OBITUARY · EDITOR'S PAGE quando o texto é homenagem ·
  "An Appreciation" · "My Relationship With…". Não ensina conduta, não tem tema clínico
  delimitado: fala de uma PESSOA.
- incerto — se o texto abaixo NÃO permitir decidir com segurança.

═══ AS SEIS REGRAS QUE DECIDEM · leia todas ANTES de responder ═══

R1 · ARTIGO ORIGINAL É IMRD, E O IMRD SELECIONA PACIENTES.
   Um artigo original tem Introdução → Métodos → Resultados → Discussão, e na seção de MÉTODOS
   ele explica como escolheu PACIENTES — não como escolheu artigos.
     seleciona PACIENTES  → artigo_original   ("we enrolled", "consecutive patients",
        "inclusion criteria: age ≥18", "we retrospectively reviewed the records of", NCT,
        aprovação de comitê de ética, consentimento informado, DESIGN/SETTING/PARTICIPANTS)
     seleciona ESTUDOS    → revisao_sistematica_meta_analise (ver R2)
     não seleciona nada   → revisão, diretriz, minirevisão ou ponto de vista
   Revisão narrativa NÃO usa IMRD: as seções dela são ASSUNTOS (Epidemiologia, Fisiopatologia,
   Diagnóstico, Tratamento), não etapas.

R2 · BUSCA SOZINHA NÃO FAZ META-ANÁLISE. Frases como "a structured literature search was
   conducted using PubMed, Embase and Cochrane" ou "a busca foi realizada nas bases…" aparecem
   em QUASE TODA revisão narrativa séria — procurar não é sintetizar.
   Para responder revisao_sistematica_meta_analise o artigo tem de trazer PELO MENOS UM destes:
     · "systematic review" / "revisão sistemática" DECLARADO (no título, no tipo do artigo, ou
       em "a systematic review was conducted according to PRISMA")
     · PRISMA · PROSPERO / número CRD
     · critérios de elegibilidade (inclusão E exclusão) declarados
     · número de estudos incluídos a partir de uma triagem
     · estimativa agrupada: pooled, random-effects, I², forest plot, meta-regressão
   Se o artigo SÓ diz que buscou, é revisao_geral.
   ⚠️ E ATENÇÃO À R6: um artigo que CITA meta-análises entre as fontes que revisou não é uma.

R3 · GUIDELINE É GRADUAÇÃO DE RECOMENDAÇÃO, NÃO É O NOME NO TÍTULO.
   Responda guideline quando o documento GRADUA o que recomenda — Classe I / IIa / IIb / III,
   Nível de Evidência A / B / C, GRADE forte/fraco, tabelas de recomendação, writing committee.
     · "Consensus Document", "Expert Consensus Decision Pathway", "Position Paper" SEM
       graduação → é revisao_geral. O nome não basta.
     · Documento COM graduação → é guideline mesmo que a palavra "guideline" não apareça
       (ex.: um documento do KDIGO com recomendações graduadas).
   POR QUÊ ISTO IMPORTA: a análise da diretriz mede o percentual de recomendações apoiadas em
   evidência A, B ou C. Um documento sem graduação não tem o que medir.

R4 · PÁGINAS SEPARAM REVISÃO DE PONTO DE VISTA — E NADA MAIS.
   O total de páginas do PDF está declarado logo abaixo. Ele serve para UMA decisão, e só uma:
   quando você já concluiu que o texto é revisao_geral OU ponto_de_vista e está em dúvida entre
   os dois.
     menos de 3 páginas → ponto_de_vista
     mais de 5 páginas  → revisao_geral, AINDA QUE a revista tenha impresso VIEWPOINT no topo
   ⛔ NÃO use o número de páginas para NENHUMA outra decisão. Não para separar artigo original,
   meta-análise, diretriz, minirrevisão, tributo ou relato de caso — nesses, quem manda é a R1
   (IMRD/pacientes), a R2 (síntese) e a R3 (graduação). Um artigo original de 4 páginas continua
   sendo artigo original; uma diretriz de 2 páginas continua sendo diretriz.
   O teste que confirma a escolha: um ponto de vista opina sobre o CAMPO e não delimita tema
   ("não avança sobre uma doença específica"); uma revisão DELIMITA um tema e se propõe a
   revisá-lo, mesmo trazendo o olhar próprio do autor.

R5 · TRIBUTO É TRIBUTO. Homenagem, obituário ou perfil de uma pessoa → tributo. Rótulos:
   TRIBUTE, IN MEMORIAM, OBITUARY, "An Appreciation", EDITOR'S PAGE quando o conteúdo é
   homenagem. Não force para ponto_de_vista: um tributo não opina sobre um tema clínico,
   ele fala de alguém.

R6 · CITAR NÃO É SER. Um artigo que MENCIONA "meta-analysis", "guideline" ou "PRISMA" no texto
   ou nas referências não vira meta-análise nem diretriz. Só conta o que o PRÓPRIO artigo FAZ.

═══ O RÓTULO IMPRESSO — FORTE, MAS PERDE PARA AS SEIS REGRAS ACIMA ═══
7. O rótulo de seção impresso pela revista é a pista mais rápida, e na maioria das vezes está
   certo. Use-o quando as regras R1–R6 não decidirem. MAS ele é o nome da SEÇÃO da revista, não
   o desenho do estudo — revista carimba meta-análise como "ORIGINAL RESEARCH" e revisão como
   "VIEWPOINT" o tempo todo. Correspondência:
     ORIGINAL RESEARCH ARTICLE · ORIGINAL ARTICLE · ORIGINAL INVESTIGATION · CLINICAL RESEARCH
        → artigo_original
     STATE-OF-THE-ART REVIEW · REVIEW ARTICLE · JACC REVIEW TOPIC OF THE WEEK · IN DEPTH · FRONTIERS
     SEMINAR (é como o Lancet chama suas revisões) · CLINICAL UPDATE · THERAPY IN PRACTICE
        → revisao_geral   (NUNCA minirevisao — por mais que o texto pareça ensaio de opinião)
     AHA SCIENTIFIC STATEMENT · SCIENTIFIC STATEMENT · CLINICAL PRACTICE GUIDELINE · CONSENSUS
     DOCUMENT · POSITION PAPER  → guideline
     THE HEART OF THE MATTER · BRIEF REPORT · BRIEF COMMUNICATION · SHORT REPORT
     RESEARCH BRIEF · SHORT COMMUNICATION  → minirevisao
        ⚠️ EXCEÇÃO (10/Ago): BRIEF REPORT que traz ENSAIO ou desenho declarado é
        artigo_original. Se o resumo segue a cartilha IMRD — testa uma hipótese (OBJECTIVE To
        test the hypothesis…), declara o desenho (DESIGN, SETTING, AND PARTICIPANTS / "A
        Randomized Clinical Trial"), nomeia a intervenção (INTERVENTION…) — então o formato
        breve é só o tamanho do texto, e vale a R1.
     TRIBUTE · IN MEMORIAM · OBITUARY · AN APPRECIATION  → tributo
     EDITORIAL · EDITORIAL COMMENT · VIEWPOINT  → ponto_de_vista
        ⚠️ mas confira a R4 antes: VIEWPOINT com mais de 5 páginas que delimita um tema é
        revisao_geral.

8. Se o texto abaixo for só capa (título, autores, "Downloaded from…") sem resumo nem seções,
   responda incerto — NÃO adivinhe.

═══ O DOCUMENTO ═══
Total de páginas do PDF: {paginas}     (use SOMENTE como manda a R4)

TEXTO (páginas 1 a 3):
{texto}
"""

_RE_TIPO = re.compile(r"TIPO:\s*([a-z_]+)", re.I)
_RE_CONF = re.compile(r"CONFIANCA:\s*(alta|m[eé]dia|media|baixa)", re.I)
_RE_PROVA = re.compile(r"PROVA:\s*(.+)", re.I | re.S)
_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

TIPOS = {"artigo_original", "revisao_sistematica_meta_analise", "revisao_geral", "guideline",
         "ponto_de_vista", "minirevisao", "relato_de_caso", "carta_de_pesquisa",
         "tributo", "incerto"}

TETO_CHARS = 20_000     # o que a prova mediu; mudar isto invalida o 99,1 %

# ═══ 10/Ago — O NÚMERO DE PÁGINAS PASSA A ENTRAR NO PROMPT (regra R4) ═══
# Ele não estava lá, e o modelo não tem como contar páginas lendo texto extraído.
# MEDIDO no gabarito de 105 artigos julgados por ele:
#     ponto de vista .... 2 páginas          tributos ......... 2,2,2,3,3,3
#     minirevisão ....... mediana 6          revisão narrativa  MÍNIMO 8
#     artigo original ... mínimo 5           meta ............. mínimo 7
# Abaixo de 3 páginas não existe original, revisão, meta nem minirrevisão.
_PAGINAS_CACHE = {}


def total_paginas(caminho):
    """Quantas páginas o PDF tem. Best-effort: se não abrir, devolve 0 e a R4 fica muda —
    melhor um sinal ausente que um número inventado."""
    try:
        if caminho not in _PAGINAS_CACHE:
            _PAGINAS_CACHE[caminho] = len(fitz.open(caminho))
        return _PAGINAS_CACHE[caminho]
    except Exception:
        return 0


def paginas_1a3(caminho):
    """As 3 PRIMEIRAS páginas do PDF. A produção lia 5.000 caracteres do começo — e o rótulo
    impresso da seção ('ORIGINAL INVESTIGATION', 'STATE-OF-THE-ART REVIEW'), que é a REGRA 1 deste
    prompt, muitas vezes está na página 2 ou 3. Foi o que levou o acerto de 54 % para 87 %."""
    doc = fitz.open(caminho)
    _PAGINAS_CACHE[caminho] = len(doc)          # aproveita a abertura: a R4 precisa do total
    return _CTRL.sub("", "".join(doc[i].get_text() for i in range(min(3, len(doc)))))


def montar(texto, paginas=0):
    """`paginas` = total de páginas do PDF (regra R4). Zero significa 'não sei' — e o prompt
    diz isso ao modelo em vez de mentir um número."""
    return PROMPT.format(texto=(texto or "")[:TETO_CHARS],
                         paginas=(paginas if paginas else "não informado"))


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
