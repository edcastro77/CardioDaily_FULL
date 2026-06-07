"""
Extrator de conteúdo de marketing via Claude.
Lê o analysis.md e retorna campos limpos prontos para as placas.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import anthropic
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

CLIENT = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

PROMPT = """Você é o diretor de marketing do CardioDaily — plataforma de inteligência médica em cardiologia do Dr. Eduardo Bringel Castro (CRM-ES 8062).

Leia a análise abaixo e extraia os campos para criação de conteúdo de redes sociais.

REGRAS ABSOLUTAS:
- Nunca criticar autores — comentar o tema e os dados
- Todo texto deve ser limpo, sem markdown (**texto**, ##, |, *, etc.)
- Português brasileiro, tom acadêmico e direto
- Frases icônicas: curtas, provocadoras, acionáveis
- Bullets: frases completas e independentes, sem truncar
- Legenda: começa com provocação, responde dilema clínico, explica dados relevantes

Retorne APENAS um JSON válido. IMPORTANTE: cada valor deve ser uma string em UMA ÚNICA LINHA — sem quebras de linha (\n) dentro dos valores. Use ponto e vírgula para separar itens dentro de um campo. Estrutura:
{
  "frase_iconica": "FRASE EM CAIXA ALTA DE 3-6 PALAVRAS QUE CAPTURA O DILEMA CLÍNICO",
  "s1_corpo": "2-3 frases em itálico que contextualizam a frase icônica. Por que este estudo importa agora.",
  "ancora": "DADO NUMÉRICO MAIS IMPACTANTE EM CAIXA ALTA (NNT, OR, %, redução absoluta)",
  "s2_corpo": "2-3 frases explicando o dado âncora em contexto clínico. Sem markdown.",
  "bullet1": "Frase completa sobre o que fazer na prática clínica",
  "bullet2": "Frase completa sobre para quem se aplica ou quando usar",
  "bullet3": "Frase completa sobre dose, contraindicação ou limitação importante",
  "s3_corpo": "1-2 frases de conclusão clínica. Sem markdown.",
  "legenda": "Legenda completa para Instagram (ver formato abaixo)",
  "script_gancho": "Frase de abertura do vídeo — dilema clínico real, 1-2 frases",
  "script_contexto": "Contexto do problema: por que este tema é mal resolvido na prática atual. 3-4 frases.",
  "script_estudo": "O que o estudo mostrou: tipo, achados principais com números. 4-6 frases.",
  "script_pratica": "Implicação prática: conduta objetiva, dose, indicação, contraindicação. 3-4 frases.",
  "fonte": "Autor principal et al., Revista, Ano. DOI se disponível."
}

FORMATO DA LEGENDA:
[FRASE ICÔNICA EM CAIXA ALTA]

[1-2 frases contextualizando o problema clínico]

O que os dados mostram:
→ [achado 1 com número]
→ [achado 2 com número]
→ [achado 3 com número]
→ [limitação relevante]

O que muda na prática:
[conduta prática objetiva]

📌 Fonte: [citação completa]

#CardioDaily #Cardiologia #MedicinaBaseadaEmEvidencias #OsFatosSemFirulas

---

ANÁLISE DO ARTIGO:
{analysis_md}
"""


def extrair_conteudo_marketing(analysis_md: str, artigo: dict) -> dict | None:
    """
    Usa Claude para extrair campos de marketing do analysis.md.
    Retorna dict com os campos ou None se falhar.
    """
    revista = (artigo.get("revista") or "").replace("_", " ")
    data    = (artigo.get("data_publicacao") or "")[:7]
    doenca  = (artigo.get("doenca_principal") or "")
    gancho  = (artigo.get("gancho_lista") or "")

    # Contexto adicional para o Claude
    contexto = f"\nContexto do artigo: Revista={revista}, Data={data}, Doença={doenca}, Gancho={gancho}\n\n"

    prompt = PROMPT.replace("{analysis_md}", contexto + analysis_md[:12000])

    try:
        resp = CLIENT.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )
        texto = resp.content[0].text.strip()

        # Extrair bloco JSON da resposta
        if "```json" in texto:
            texto = texto.split("```json")[1].split("```")[0].strip()
        elif "```" in texto:
            texto = texto.split("```")[1].split("```")[0].strip()
        else:
            # Pegar apenas o bloco entre { e }
            inicio = texto.find("{")
            fim = texto.rfind("}") + 1
            if inicio >= 0 and fim > inicio:
                texto = texto[inicio:fim]

        # Tentar parse direto
        try:
            dados = json.loads(texto)
            return dados
        except json.JSONDecodeError:
            # Fallback: usar ast.literal_eval ou tentar corrigir quebras de linha
            import re
            # Remover quebras de linha dentro de valores string
            texto_limpo = re.sub(r':\s*"(.*?)"(?=\s*[,}])',
                                  lambda m: ': "' + m.group(1).replace('\n', ' ').replace('"', "'") + '"',
                                  texto, flags=re.DOTALL)
            dados = json.loads(texto_limpo)
            return dados

    except Exception as e:
        print(f"Erro na extração IA: {e}")
        return None


def montar_defaults(dados: dict, artigo: dict) -> dict:
    """Converte o JSON do Claude nos campos do studio_app."""
    revista = (artigo.get("revista") or "").replace("_", " ")
    data    = (artigo.get("data_publicacao") or "")[:7]

    frase = dados.get("frase_iconica", "NOVO ESTUDO\nMUDA A PRÁTICA")
    # Quebrar frase icônica em linhas de ~20 chars
    palavras = frase.split()
    linhas, linha_atual = [], []
    for p in palavras:
        linha_atual.append(p)
        if len(" ".join(linha_atual)) > 20:
            linhas.append(" ".join(linha_atual[:-1]))
            linha_atual = [p]
    if linha_atual:
        linhas.append(" ".join(linha_atual))
    s1_titulo = "\n".join(linhas[:4]) if linhas else frase

    return {
        "s1_titulo": s1_titulo,
        "s1_corpo":  dados.get("s1_corpo", ""),
        "s2_titulo": "O DADO\nQUE IMPORTA",
        "s2_ancora": dados.get("ancora", ""),
        "s2_corpo":  dados.get("s2_corpo", ""),
        "s3_titulo": "O QUE MUDA\nNA PRÁTICA",
        "s3_b1":     dados.get("bullet1", ""),
        "s3_b2":     dados.get("bullet2", ""),
        "s3_b3":     dados.get("bullet3", ""),
        "s3_corpo":  dados.get("s3_corpo", ""),
        "p_titulo":  "",
        "p_ancora":  dados.get("ancora", ""),
        "p_b1":      dados.get("bullet1", ""),
        "p_b2":      dados.get("bullet2", ""),
        "p_b3":      dados.get("bullet3", ""),
        "p_b4":      dados.get("s3_corpo", ""),
        "p_corpo":   f"{revista} · {data}",
        "p_fonte":   dados.get("fonte", f"{revista}, {data}."),
        "legenda":   dados.get("legenda", ""),
        "script": f"""[GANCHO — 15s]
{dados.get('script_gancho', '')}

[CONTEXTO — 30s]
{dados.get('script_contexto', '')}

[O QUE O ESTUDO MOSTROU — 45s]
{dados.get('script_estudo', '')}

[IMPLICAÇÃO PRÁTICA — 30s]
{dados.get('script_pratica', '')}

[CALL TO ACTION — 15s]
O artigo completo está analisado no CardioDaily. Os fatos, sem fírulas. Link na bio.""",
    }
