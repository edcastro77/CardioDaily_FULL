"""
llm_client.py — CLIENTE UNIFICADO. Executa a cadeia de fallback CROSS-PROVIDER definida no modelos.py.
É AQUI que a LEI DA EQUIVALÊNCIA roda de verdade: tenta cada modelo da cadeia (ex.: Claude 5 → GPT-5.6 → Gemini 3.x Pro)
até um responder. Se um provedor cai (crédito/cota/API), pula pro próximo — que é de OUTRO dono e do MESMO tier.

Recursos:
  • Prompt caching (bloco 'contexto' reaproveitável) no caminho Anthropic — leitura a 10% do input.
  • Remove `temperature` onde o modelo de raciocínio rejeita (proativo via modelos.py + reativo por erro).
  • Um SDK por provedor, escolhido pelo prefixo do model_id.

Uso:
    import llm_client, modelos as M
    txt = llm_client.gerar(M.ESCRITA, instrucao, contexto=texto_do_artigo, max_tokens=3200)
"""
import os
import modelos as M

_ULTIMO_MODELO = [None]   # observabilidade: quem respondeu por último


def _erro_de_sampling(e):
    s = str(e).lower()
    return "temperature" in s or "sampling" in s or "top_p" in s or "unsupported" in s


def gerar(chain, instrucao, contexto=None, max_tokens=2000, temperatura=0.4):
    """Tenta cada modelo da cadeia (cross-provider) até um responder. Levanta só se TODOS falharem."""
    erros = []
    for mod in chain:
        prov = M.provedor(mod)
        fn = {"anthropic": _anthropic, "openai": _openai, "google": _gemini}.get(prov)
        if fn is None:
            erros.append(f"{mod}: provedor desconhecido"); continue
        for tentativa in (1, 2, 3):                   # retry com espera crescente antes de trocar de modelo
            try:
                txt = fn(mod, instrucao, contexto, max_tokens, temperatura)
                _ULTIMO_MODELO[0] = mod
                return txt
            except Exception as e:
                if _transitorio(e) and tentativa < 3:  # rede/429/sobrecarga → espera e tenta o MESMO modelo
                    import time; time.sleep(5 * tentativa); continue
                erros.append(f"{mod}: {type(e).__name__}: {str(e)[:140]}")
                break
    raise RuntimeError("Todos os modelos da cadeia falharam:\n  " + "\n  ".join(erros))


def _transitorio(e):
    """Erro de rede/carga que vale re-tentar (não é erro de lógica)."""
    s = str(e).lower()
    return any(k in s for k in ("timeout", "timed out", "connection", "network", "overloaded",
                                "rate limit", "429", "500", "502", "503", "504", "temporarily"))


def gerar_json(chain, instrucao, schema, contexto=None, max_tokens=8000, nome="extrair"):
    """Devolve DICT — não texto. Usa TOOL USE (saída estruturada): a API OBRIGA o modelo a entregar
    o objeto no formato do schema. JSON malformado (vírgula sobrando, caractere de controle, preâmbulo,
    comentário) deixa de ser POSSÍVEL — não é reparo, é impossibilidade. Mata a classe inteira de falha.

    Fallback: se um provedor não suportar tool use, cai no caminho de texto + parsing tolerante.
    """
    erros = []
    for mod in chain:
        if M.provedor(mod) != "anthropic":          # tool use implementado p/ Anthropic; outros → texto
            continue
        for tentativa in (1, 2, 3):                  # retry com espera crescente (rede/429/sobrecarga)
            try:
                import anthropic
                cli = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY", ""))
                if contexto:
                    content = [{"type": "text", "text": contexto, "cache_control": {"type": "ephemeral"}},
                               {"type": "text", "text": instrucao}]
                else:
                    content = instrucao
                r = cli.messages.create(
                    model=mod, max_tokens=max_tokens,
                    tools=[{"name": nome, "description": "Devolve os dados estruturados pedidos.",
                            "input_schema": schema}],
                    tool_choice={"type": "tool", "name": nome},   # OBRIGA o uso da ferramenta
                    messages=[{"role": "user", "content": content}])
                for b in r.content:
                    if getattr(b, "type", "") == "tool_use":
                        _ULTIMO_MODELO[0] = mod
                        return b.input                            # já é dict validado pelo schema
                raise RuntimeError("modelo não devolveu tool_use")
            except Exception as e:
                if _transitorio(e) and tentativa < 3:
                    import time; time.sleep(5 * tentativa); continue
                erros.append(f"{mod}: {type(e).__name__}: {str(e)[:120]}")
                break
    raise RuntimeError("gerar_json falhou em toda a cadeia:\n  " + "\n  ".join(erros or ["sem modelo Anthropic na cadeia"]))


def _anthropic(mod, instrucao, contexto, max_tokens, temperatura):
    import anthropic
    cli = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY", ""))
    if contexto:                                   # contexto reaproveitável → cacheado (10% na leitura)
        content = [{"type": "text", "text": contexto, "cache_control": {"type": "ephemeral"}},
                   {"type": "text", "text": instrucao}]
    else:
        content = instrucao
    # NOTA (medido 27/07): o claude-sonnet-5 aqui NÃO faz extended thinking (default ~0 tokens de thinking;
    # e 'thinking.type.enabled' é rejeitado por este modelo). O "ACRI vazio" NÃO era thinking comendo tokens
    # (a saída usa ~560 tokens num teto de 8000) — era retorno vazio pontual. Quem conserta é o RETRY em
    # analisador._gerar, não mexer em thinking. Então não passamos parâmetro de thinking — comportamento nativo.
    for kw in (M.temp_kwargs(mod, temperatura), {}):     # com temp; refaz sem se o modelo rejeitar sampling
        try:
            r = cli.messages.create(model=mod, max_tokens=max_tokens,
                                    messages=[{"role": "user", "content": content}], **kw)
            return "".join(b.text for b in r.content if getattr(b, "type", "") == "text")
        except Exception as e:
            if kw and _erro_de_sampling(e):
                continue
            raise


def _openai(mod, instrucao, contexto, max_tokens, temperatura):
    from openai import OpenAI
    cli = OpenAI(api_key=os.getenv("OPENAI_API_KEY", ""))
    texto = (contexto + "\n\n" + instrucao) if contexto else instrucao   # OpenAI cacheia prefixo automático
    for kw in (M.temp_kwargs(mod, temperatura), {}):
        try:
            r = cli.chat.completions.create(model=mod, max_completion_tokens=max_tokens,
                                            messages=[{"role": "user", "content": texto}], **kw)
            return r.choices[0].message.content or ""
        except Exception as e:
            if kw and _erro_de_sampling(e):
                continue
            raise


def _gemini(mod, instrucao, contexto, max_tokens, temperatura):
    from google import genai
    from google.genai import types
    cli = genai.Client(api_key=os.getenv("GEMINI_API_KEY", "") or os.getenv("GOOGLE_API_KEY", ""))
    texto = (contexto + "\n\n" + instrucao) if contexto else instrucao
    cfg = types.GenerateContentConfig(max_output_tokens=max_tokens,
                                      **M.temp_kwargs(mod, temperatura))   # Gemini aceita temperature
    r = cli.models.generate_content(model=mod, contents=texto, config=cfg)
    return r.text
