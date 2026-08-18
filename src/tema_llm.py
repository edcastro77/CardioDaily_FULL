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
from temas import TEMAS, SEM_TEMA

SCHEMA = {
    "type": "object",
    "properties": {
        "tema": {"type": "string", "enum": TEMAS + [SEM_TEMA]},
        "tema_secundario": {"type": "string", "enum": TEMAS + ["nenhum"]},
        "porque": {"type": "string"},
    },
    "required": ["tema", "tema_secundario", "porque"],
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

REGRAS QUE IMPORTAM:
· O tema é sobre O QUE O ARTIGO INVESTIGA, não sobre o que ele menciona de passagem.
  Um RCT de dapagliflozina na ICFER é Insuficiência Cardíaca, não Cardiometabólica.
· TAVR e TEER: se o assunto é a DOENÇA da valva → Valvulopatias. Se é a TÉCNICA, o
  dispositivo ou o acesso → Intervenção/Hemodinâmica.
· Eco/RM/TC: se o artigo é sobre o DESEMPENHO do método (acurácia, reprodutibilidade,
  novo parâmetro) → Imagem Cardiovascular. Se o método é só a ferramenta para estudar
  outra doença → o tema da doença.
· Insuficiência mitral SECUNDÁRIA é doença de ventrículo: principal Insuficiência
  Cardíaca, secundário Valvulopatias.
· Cardio-Oncologia exige que o EFEITO CARDIOVASCULAR DO TRATAMENTO oncológico seja o
  assunto. Paciente que só POR ACASO tem câncer não conta.
· Prevenção primária, risco cardiovascular, escore de risco → Cardiometabólica.

O SECUNDÁRIO só existe se o artigo for de verdade sobre os dois. Na dúvida, "nenhum" —
inventar um segundo tema faz o assinante receber coisa que não pediu.

Se o texto não permitir decidir, devolva tema="{sem}". Não chute: um artigo sem tema vai
para a revisão humana, o que é barato. Um artigo no tema errado chega no celular de alguém.

Responda APENAS o JSON."""


def classificar(titulo, texto, revista=""):
    """(tema, secundario, porque). Devolve (None, None, motivo) se o modelo falhar."""
    ctx = f"REVISTA: {revista}\nTÍTULO: {titulo}\n\nTEXTO:\n{(texto or '')[:9000]}"
    try:
        r = llm_client.gerar_json(
            M.CLASSIFICACAO,
            INSTRUCAO.replace("{sem}", SEM_TEMA),
            SCHEMA, contexto=ctx, max_tokens=400, nome="tema")
    except Exception as e:
        return None, None, f"{type(e).__name__}: {e}"

    if isinstance(r, str):
        try:
            r = json.loads(r)
        except Exception as e:
            return None, None, f"JSON inválido: {e}"

    tema = (r or {}).get("tema")
    sec = (r or {}).get("tema_secundario")
    # ⚠️ O schema já restringe o enum, mas conferir aqui é barato e fecha o caso do
    # fallback para um provedor que ignore o enum. Rótulo fora da lista vira None — nunca
    # um tema fantasma que ninguém recebe.
    if tema not in TEMAS:
        return (SEM_TEMA if tema == SEM_TEMA else None), None, (r or {}).get("porque", "")
    if sec not in TEMAS or sec == tema:
        sec = None
    return tema, sec, (r or {}).get("porque", "")
