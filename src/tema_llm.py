"""
tema_llm.py — O PLANO B DO TEMA: quando o PubMed ainda não indexou.

═══ 18/Ago/2026 — POR QUE ESTE ARQUIVO EXISTE ═══

O tema vem do MeSH, o vocabulário controlado que indexadores HUMANOS da National Library
of Medicine atribuem depois de ler o artigo inteiro. É de graça, é determinístico, e
resolveu 313 dos 520 artigos do acervo.

Mas a indexação DEMORA. Artigo publicado esta semana entra no PubMed sem MeSH e só recebe
os descritores algumas semanas depois. Medido em 18/Ago: **194 dos 520 sem MeSH**, e são
justamente os MAIS NOVOS — ou seja, exatamente os que o Dr. Eduardo mais quer entregar.

Decisão dele: *"llm e já pode implementar que quando não tiver indexação por mesh — que
deve automaticamente rodar a llm"*. O plano B deixa de ser uma tarefa manual e vira parte
da esteira: sem MeSH → chama o modelo → grava com `tema_origem='llm'`.

⚠️ POR QUE `tema_origem` IMPORTA MAIS AQUI DO QUE EM QUALQUER OUTRO LUGAR
O MeSH é humano e auditável; o LLM é palpite barato. Guardar a procedência permite:
  · auditar SÓ os do LLM quando um tema parecer errado (dezenas, não 520);
  · **re-rodar o MeSH depois** — quando a NLM indexar, o descritor humano SUBSTITUI o
    palpite. `tema_origem='llm'` é o que marca quem ainda pode melhorar de graça.
Sem essa coluna, o palpite viraria permanente sem ninguém perceber.

═══ CUSTO MEDIDO ═══
    ~2.700 tokens de entrada por artigo (título + resumo + as 2 primeiras páginas)
    gpt-5.6-luna .... US$ 0,00057/artigo  →  194 artigos = US$ 0,11
    claude-haiku .... US$ 0,00282/artigo  →  194 artigos = US$ 0,55
Usa a cadeia CLASSIFICACAO (luna primeiro), a mesma que classifica o TIPO do documento e
que acertou 210/210 na prova de 11/Ago.
"""
import json
import os
import sys

_AQUI = os.path.dirname(os.path.abspath(__file__))
if _AQUI not in sys.path:
    sys.path.insert(0, _AQUI)

import llm_client
import modelos as M
# 20/Ago — `SEM_TEMA` saiu do import de propósito. Decisão do Dr. Eduardo:
# *"inadmissível não ter tema — então não é cardiologia e medicina, estamos falando do cosmo."*
# Todo artigo de cardiologia tem onde, o quê e quem. Quando o tripé não fecha, a resposta é
# `fora_do_escopo` (o artigo não pertence ao acervo), nunca um tema vazio.
from temas import TEMAS

# ═══════════ 20/Ago/2026 — O TRIPÉ (arquitetura de decisão do Dr. Eduardo) ═══════════
#
# Medido no gabarito cego de 40: o LLM levava o artigo ao leitor certo em 85 %, o MeSH em 65 %.
# Decisão dele: **LLM decide, MeSH vira 2º tema e desempate.** Mas trocar a ordem sem trocar o
# raciocínio só troca quem erra. O que ele ditou foi COMO decidir:
#
#   *"o sistema deve ler com um tripé na sua arquitetura de decisão — a ordem aqui não importa,
#    o que interessa é se eles conseguem COMBINAR DE FORMA PLAUSÍVEL:
#      · onde aplico este conhecimento (no ambulatório, na UTI, na sala de hemodinâmica?)
#      · este conhecimento diz respeito a mecanismos de doença, métodos de avaliação,
#        implicações prognósticas ou a uma intervenção?
#      · e por último e não menos importante — QUEM VAI LER: cardio clínico, cardio pediatra,
#        o cara que atende miocardiopatias, recém-formado que dá muito plantão na UCO,
#        plantonista do PS, médico da hemodinâmica, médico do transplante, ou o diretor?"*
#
# Por isso os três eixos são CAMPOS OBRIGATÓRIOS do schema, preenchidos ANTES do tema: o modelo
# tem de se comprometer com onde/o quê/quem, e só então escolher — e o tema precisa combinar
# com os três. É a mesma ideia do VEREDITO ABERTO de 02/Ago: obrigar a mostrar a conta impede
# a resposta bonita e vazia. Aqui também dá auditoria: quando um tema sair errado, os três
# eixos dizem ONDE o raciocínio torceu.
#
# ⚠️ E FOI ISTO QUE MATOU O `Sem tema`. Eu tinha proposto um `nao_classificavel` para quando o
# sistema não decidisse. Resposta dele: *"inadmissível não ter tema — então não é cardiologia e
# medicina, estamos falando do cosmo."* Ele está certo: todo artigo de cardiologia tem onde,
# o quê e quem. Se o tripé NÃO fecha, o problema não é "faltou tema" — é que **o artigo não
# pertence ao acervo**. Isso é `fora_do_escopo`, que é uma resposta, não um buraco (LEI 11).
LOCAIS = ["ambulatório", "enfermaria", "UTI/UCO", "pronto-socorro",
          "sala de hemodinâmica", "centro cirúrgico", "laboratório de imagem",
          "consultório/prevenção", "pesquisa/bancada"]
NATUREZAS = ["mecanismo de doença", "método de avaliação", "implicação prognóstica",
             "intervenção terapêutica", "organização do cuidado"]
LEITORES = ["cardiologista clínico", "cardiopediatra", "especialista em miocardiopatias",
            "plantonista de UCO/UTI", "plantonista do pronto-socorro", "hemodinamicista",
            "eletrofisiologista", "especialista em imagem", "médico do transplante",
            "cirurgião cardíaco", "cardio-oncologista", "cardio-obstetra",
            "gestor/diretor de clínica"]

SCHEMA = {
    "type": "object",
    "properties": {
        # ── o TRIPÉ, respondido ANTES do tema ──
        "onde_se_aplica": {"type": "string", "enum": LOCAIS},
        "natureza": {"type": "string", "enum": NATUREZAS},
        "quem_le": {"type": "string", "enum": LEITORES},
        "os_tres_combinam": {"type": "boolean"},
        # ── e só então o tema ──
        "tema": {"type": "string", "enum": TEMAS + ["fora_do_escopo"]},
        "tema_secundario": {"type": "string", "enum": TEMAS + ["nenhum"]},
        "porque": {"type": "string"},
    },
    "required": ["onde_se_aplica", "natureza", "quem_le", "os_tres_combinam",
                 "tema", "tema_secundario", "porque"],
    "additionalProperties": False,
}

INSTRUCAO = """Você classifica artigos de cardiologia no vocabulário do CardioDaily.

Devolva o TEMA PRINCIPAL e, se o artigo pertencer legitimamente a dois, o SECUNDÁRIO.

OS 13 TEMAS:
 1  Coronária/DAC — doença coronária, SCA, IAM, angina, aterosclerose coronária
 2  Insuficiência Cardíaca — IC com FE reduzida/preservada, congestão, transplante
 3  Arritmias/Anticoagulantes — FA, flutter, TV, ablação, marca-passo, CDI, anticoagulação
 4  Cardiometabólica — diabetes, obesidade, lipídios, GLP-1, iSGLT2, prevenção primária
 5  Valvulopatias — valva aórtica/mitral/tricúspide, prótese, endocardite, TAVR/TEER
 6  Miocardiopatias — hipertrófica, dilatada, amiloidose, miocardite, Chagas, Takotsubo
 7  UTI Cardiológica — choque cardiogênico, ECMO, dispositivo de assistência, PCR, vasoativo
 8  Intervenção/Hemodinâmica — ICP, stent, cateterismo, FFR (o PROCEDIMENTO como assunto)
 9  Imagem Cardiovascular — eco, RM, TC, cintilografia, strain (o MÉTODO como assunto)
10  Aorta/Congênitas/Genética — aneurisma/dissecção de aorta, cardiopatia congênita, genética
11  Cardio-Oncologia — cardiotoxicidade de quimio/radio, antracíclico, anti-HER2, checkpoint
12  Hipertensão/HAS — hipertensão arterial, anti-hipertensivo, MAPA, HAS resistente
13  Cardio-Obstetrícia — gestação, pré-eclâmpsia, periparto, cardiopatia na gravidez

═══ COMO DECIDIR — O TRIPÉ ═══
Responda os TRÊS eixos ANTES de escolher o tema. A ordem entre eles não importa; o que
importa é se COMBINAM de forma plausível.

 1 ONDE se aplica este conhecimento? (ambulatório · UTI/UCO · sala de hemodinâmica · …)
 2 QUE NATUREZA tem? (mecanismo de doença · método de avaliação · implicação prognóstica ·
   intervenção terapêutica · organização do cuidado)
 3 QUEM VAI LER? (cardiologista clínico · cardiopediatra · o especialista em miocardiopatias ·
   plantonista de UCO · plantonista do PS · hemodinamicista · eletrofisiologista ·
   especialista em imagem · médico do transplante · cirurgião · gestor)

O TEMA É QUEM LÊ. Se os três eixos combinam, o tema sai deles. Um exemplo real: "reserva de
fluxo subendocárdica em perfusão normal" — ONDE: sala de hemodinâmica · NATUREZA: método de
avaliação · QUEM: hemodinamicista → tema Intervenção/Hemodinâmica, e NÃO Imagem, porque a
medida se faz dentro do laboratório e é o hemodinamicista que a usa.

⚠️ REGRA DURA — SE O TRIPÉ FECHA, HÁ TEMA. SEMPRE.
"fora_do_escopo" só é permitido quando os_tres_combinam=false. Se você conseguiu nomear um
LEITOR CARDIOLÓGICO plausível, o artigo PERTENCE ao acervo — e você é obrigado a escolher um
dos 13 temas, por mais que o assunto pareça de outra especialidade.

Isto foi medido: o modelo marcou "fora do escopo" para poluição/saúde cerebral (dizendo
"ambulatório · prognóstico · cardiologista clínico") e para distúrbios anti-PF4 ("ambulatório ·
mecanismo de doença · cardiologista clínico") — nos dois casos o tripé FECHOU e ele descartou
mesmo assim. Os dois pertencem: poluição gera aterosclerose (regra A) e anti-PF4 é trombose
com repercussão vascular. Errar o tema custa um artigo no lugar errado; jogar fora um artigo
que o cardiologista queria ler custa o assinante.

Hematologia, reumatologia, nefrologia, oncologia, pneumologia e saúde ambiental ENTRAM sempre
que houver leitor cardiológico. "Fora do escopo" é para o que não tem leitor nenhum na
cardiologia — ergonomia ocupacional, gestão hospitalar genérica, ciência básica sem alvo
cardiovascular.

═══ TRÊS TEMAS SÃO DE MÉTODO, UM É DE CENÁRIO ═══
· Imagem Cardiovascular — aquisição/interpretação NÃO invasiva. Teste: **um radiologista
  poderia fazer?** Se sim, é Imagem.
· Intervenção/Hemodinâmica — a medida ou o gesto acontece DENTRO da sala de hemodinâmica.
  IVUS, OCT, FFR, reserva de fluxo invasiva, cateterismo. Mesmo quando a doença é coronária.
· Arritmias/Anticoagulantes — a ferramenta é o ECG/eletrofisiologia, OU o assunto é o
  USO CLÍNICO de anticoagulante (mesmo sem arritmia nenhuma).
· UTI Cardiológica — cuidado à beira do leito crítico: choque, PCR, ECMO, suporte mecânico,
  AVC agudo, pós-parada. Quem lê é o intensivista, não o clínico de consultório.

MÉTODO OU DOENÇA? Avaliar o PACIENTE (quem tem indicação, qual o risco) → tema da doença.
Avaliar ou executar o MÉTODO em si → tema do método.

═══ REGRAS DE CONTEÚDO (ditadas pelo Dr. Eduardo) ═══
A · ATEROSCLEROSE É UM CONTÍNUO. "Coronária/DAC" significa aterosclerose CLÍNICA em qualquer
    leito — coronário, cerebral, carotídeo, periférico. Carga/fator metabólico que LEVA à
    placa → Cardiometabólica 1º, Coronária/DAC 2º. Placa ou doença estabelecida →
    Coronária/DAC 1º. (Poluição e saúde cerebral → Cardiometabólica + Coronária/DAC.)
B · TODA hipertensão pulmonar → Miocardiopatias, de qualquer grupo (1, tromboembólica, do VE,
    portopulmonar), mesmo quando avaliada por hemodinâmica invasiva. O que adoece é o VD.
C · MIOCARDIOPATIAS É MAIOR DO QUE A PALAVRA "CARDIOMYOPATHY". Não espere o título dizer.
    Três mecanismos levam a este tema, e são eles que decidem:
      (1) VENTRÍCULO DIREITO — qualquer doença que sobrecarregue ou faça falhar o VD.
          **TODA hipertensão pulmonar entra aqui**, de qualquer grupo (1, tromboembólica,
          do VE, portopulmonar), e mesmo quando medida por cateterismo direito: o que
          adoece é o VD, e com ele vêm congestão hepática, renal, venosa e infarto venoso.
      (2) MIOCÁRDIO OU PERICÁRDIO INFILTRADO/INFLAMADO — miocardite (inclusive por COVID),
          pericardiopatia, derrame pericárdico, restritiva, e doença sistêmica que os cause:
          **reumatológica** (pericardite, miocardite, vasculite), sarcoidose, amiloidose.
      (3) O AMBULATÓRIO — a lista que o especialista atende: Chagas, amiloidose, sarcoidose,
          doença de Danon, PKP2, doença de Kawasaki, hipertrófica, dilatada, Takotsubo.
    E ainda: cardio-oncologia é acompanhada PELO grupo de miocardiopatias (2º tema frequente);
    congênita do adulto cursa com miocardiopatia via VD e hipertensão pulmonar.
    Teste rápido: **o especialista em miocardiopatias leria isto?** Se sim, o tema está aí —
    como principal ou como secundário.
D · ANTICOAGULANTE: mecanismo (hemostasia, ativação plaquetária, parede vascular) →
    Cardiometabólica. USO CLÍNICO do anticoagulante → Arritmias/Anticoagulantes.
E · CONTEXTO CLÍNICO GANHA DE ÓRGÃO. Gravidez → Cardio-Obstetrícia 1º. Pediátrico →
    Aorta/Congênitas/Genética como 2º. AVC agudo e pós-parada → UTI Cardiológica 1º.
F · SOBREVIVENTE DE CÂNCER é Cardio-Oncologia mesmo anos depois — antracíclico e quimio dão
    eventos 5 a 10 anos após o fim do tratamento.

Além dessas: o tema é O QUE O ARTIGO INVESTIGA, não o que menciona de passagem (um RCT de
dapagliflozina na ICFER é Insuficiência Cardíaca). Insuficiência mitral SECUNDÁRIA é doença
de ventrículo: IC 1º, Valvulopatias 2º.

═══ O SECUNDÁRIO ═══
Existe se o artigo pertence de verdade aos dois — e vale muito: o assinante de QUALQUER das
duas categorias recebe o artigo. Na dúvida entre dois temas plausíveis, use os dois em vez de
escolher um. Só "nenhum" quando o segundo seria invenção.

Responda APENAS o JSON."""


def classificar(titulo, texto, revista=""):
    """(tema, secundario, porque). `tema` pode ser 'fora_do_escopo'.

    Devolve (None, None, motivo) SÓ quando o modelo falha de verdade (rede, JSON, enum
    quebrado) — e aí quem chama tem de tratar como falha, não como "sem tema".
    """
    ctx = f"REVISTA: {revista}\nTÍTULO: {titulo}\n\nTEXTO:\n{(texto or '')[:9000]}"
    try:
        r = llm_client.gerar_json(
            M.CLASSIFICACAO, INSTRUCAO, SCHEMA,
            contexto=ctx, max_tokens=600, nome="tema")
    except Exception as e:
        return None, None, f"{type(e).__name__}: {e}"

    if isinstance(r, str):
        try:
            r = json.loads(r)
        except Exception as e:
            return None, None, f"JSON inválido: {e}"
    r = r or {}

    tema = r.get("tema")
    sec = r.get("tema_secundario")
    # o tripé vai junto do motivo: é o que permite auditar ONDE o raciocínio torceu quando
    # um tema sair errado, em vez de só ver o rótulo final e adivinhar.
    tripe = (f"[onde: {r.get('onde_se_aplica')} · natureza: {r.get('natureza')} · "
             f"lê: {r.get('quem_le')}] ")
    porque = tripe + (r.get("porque") or "")

    if tema == "fora_do_escopo":
        return "fora_do_escopo", None, porque
    # ⚠️ O schema restringe o enum, mas conferir aqui é barato e fecha o caso do fallback
    # para um provedor que ignore o enum. Rótulo fora da lista é FALHA, não "sem tema":
    # os dois viravam a mesma coisa antes, e era impossível saber se o modelo tinha
    # respondido "não sei" ou se a chamada tinha quebrado.
    if tema not in TEMAS:
        return None, None, f"tema fora do enum ({tema!r}) · {porque}"
    if sec not in TEMAS or sec == tema:
        sec = None
    return tema, sec, porque
