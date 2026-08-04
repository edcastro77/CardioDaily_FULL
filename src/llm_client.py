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

# ═══ TIMEOUT — 03/Ago/2026 ═══
# NÃO HAVIA NENHUM. Cada SDK usava o padrão da casa (Anthropic: 600 s com 2 retentativas INTERNAS =
# 30 min numa chamada só; e o nosso laço tenta mais 3 vezes por cima = quase 2 h pendurado).
# Foi assim que a prova do PLATO — 13 páginas, 58 mil chars, ~14,5 mil tokens, que deveria levar
# 30 s — passou de 30 minutos sem uma linha na tela. E é o MESMO risco na Chave 2: uma conexão
# pendurada num lote de 431 artigos congela a noite inteira sem ninguém saber.
# Quem tem de decidir quando desistir é o CardioDaily, não o padrão de fábrica de cada fornecedor.
TIMEOUT_S = float(os.getenv("CD_TIMEOUT_S", "180"))   # 3 min por tentativa — folga de 6× sobre o normal
_RETRIES_SDK = 0        # as retentativas são NOSSAS (visíveis, com espera crescente), não do SDK

_ULTIMO_MODELO = [None]   # observabilidade: quem respondeu por último
_ULTIMO_USO = {}          # observabilidade: tokens/stop_reason da última chamada (o lab lê daqui)
_USO_CTX = {"etapa": "?", "artigo": "?"}   # quem chamou seta isto antes de gerar (p/ o log saber a etapa/artigo)


def contexto_uso(etapa=None, artigo=None):
    """Marca a etapa/artigo da próxima chamada — só p/ o log de uso saber de onde veio."""
    if etapa is not None:
        _USO_CTX["etapa"] = etapa
    if artigo is not None:
        _USO_CTX["artigo"] = artigo


def _registrar_uso(r, modelo):
    """Uma linha JSONL por chamada LLM em outputs/uso.jsonl. É isto que transforma 'acho que' em NÚMERO:
    custo, cache hit, tokens de thinking e — crucial — stop_reason (o detector de truncamento).
    Best-effort ABSOLUTO: se qualquer coisa falhar aqui, NÃO derruba a análise."""
    try:
        import json, datetime
        u = getattr(r, "usage", None) or getattr(r, "usage_metadata", None)   # Anthropic/OpenAI vs Gemini
        def g(*nomes):                                        # pega o 1º nome que existir (nomes diferem por provedor)
            for n in nomes:
                v = getattr(u, n, None) if u is not None else None
                if v is not None:
                    return v
            return None
        stop = getattr(r, "stop_reason", None)                # Anthropic
        if stop is None:
            try: stop = r.choices[0].finish_reason            # OpenAI
            except Exception:
                try: stop = str(getattr(r.candidates[0], "finish_reason", None))  # Gemini
                except Exception: stop = None
        d = getattr(u, "output_tokens_details", None)
        linha = {
            "ts": datetime.datetime.now().isoformat(timespec="seconds"),
            "artigo": _USO_CTX.get("artigo"), "etapa": _USO_CTX.get("etapa"), "modelo": modelo,
            "input": g("input_tokens", "prompt_tokens", "prompt_token_count"),
            "output": g("output_tokens", "completion_tokens", "candidates_token_count"),
            "cache_write": g("cache_creation_input_tokens") or 0,
            "cache_read": g("cache_read_input_tokens", "cached_content_token_count") or 0,
            "thinking": getattr(d, "thinking_tokens", None) if d else None,
            "stop_reason": stop,                              # "max_tokens" (Anthropic) / "length" (OpenAI) = truncou
        }
        _ULTIMO_USO.clear(); _ULTIMO_USO.update(linha)   # o lab de prova lê os tokens daqui
        caminho = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "outputs", "uso.jsonl")
        with open(caminho, "a", encoding="utf-8") as f:
            f.write(json.dumps(linha, ensure_ascii=False) + "\n")
    except Exception:
        pass


def _erro_de_sampling(e):
    s = str(e).lower()
    return "temperature" in s or "sampling" in s or "top_p" in s or "unsupported" in s


def gerar(chain, instrucao, contexto=None, max_tokens=2000, temperatura=0.4):
    """Tenta cada modelo da cadeia (cross-provider) até um responder. Levanta só se TODOS falharem."""
    erros = []
    for mod in chain:
        prov = M.provedor(mod)
        fn = {"anthropic": _anthropic, "openai": _openai,
              "google": _gemini, "xai": _xai}.get(prov)
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
                erros.append(f"{mod}: {type(e).__name__}: {str(e)[:600]}")
                break
    raise RuntimeError("Todos os modelos da cadeia falharam:\n  " + "\n  ".join(erros))


def _transitorio(e):
    """Erro de rede/carga que vale re-tentar (não é erro de lógica)."""
    s = str(e).lower()
    return any(k in s for k in ("timeout", "timed out", "connection", "network", "overloaded",
                                "rate limit", "429", "500", "502", "503", "504", "temporarily"))


_ULTIMO_MODO = [None]   # observabilidade: COMO o último JSON foi obtido (tool_use / function / responseSchema)


def _schema_para_gemini(s):
    """O `responseSchema` do Google é OpenAPI, não JSON Schema puro: ele NÃO aceita `type` como lista.
    Nossos schemas usam `{"type": ["number", "null"]}` para distinguir os TRÊS estados do NHLBI
    (true=fez · false=não fez · null=NÃO REPORTA) — e essa distinção é o coração do rigor, não pode
    ser perdida na conversão. Aqui a lista vira `type` + `nullable`, recursivamente."""
    if isinstance(s, list):
        return [_schema_para_gemini(x) for x in s]
    if not isinstance(s, dict):
        return s
    out = {}
    for k, v in s.items():
        if k == "type" and isinstance(v, list):
            reais = [t for t in v if t != "null"]
            out["type"] = reais[0] if reais else "string"
            if "null" in v:
                out["nullable"] = True
        elif k in ("properties", "items"):
            out[k] = _schema_para_gemini(v)
        elif k == "additionalProperties":
            continue                                   # o Google rejeita
        else:
            out[k] = _schema_para_gemini(v) if isinstance(v, (dict, list)) else v
    return out


def _json_anthropic(mod, instrucao, schema, contexto, max_tokens, nome):
    import anthropic
    cli = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY", ""),
                              timeout=TIMEOUT_S, max_retries=_RETRIES_SDK)
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
    _registrar_uso(r, mod)
    for b in r.content:
        if getattr(b, "type", "") == "tool_use":
            _ULTIMO_MODO[0] = "tool_use"
            return b.input                            # já é dict validado pelo schema
    raise RuntimeError("modelo não devolveu tool_use")


def _json_openai(mod, instrucao, schema, contexto, max_tokens, nome):
    """OpenAI chama de FUNCTION CALLING — é a mesma coisa que o tool use da Anthropic, com outro nome.
    Escolhido em vez do `response_format: json_schema` porque o modo `strict` exige que TODA propriedade
    esteja em `required` e `additionalProperties: false` em todo objeto; nossos schemas de FATOS não são
    assim (campo que o artigo não reporta fica de fora de propósito), e o strict recusaria o schema."""
    import json
    from openai import OpenAI
    cli = OpenAI(api_key=os.getenv("OPENAI_API_KEY", ""),
                 timeout=TIMEOUT_S, max_retries=_RETRIES_SDK)
    texto = (contexto + "\n\n" + instrucao) if contexto else instrucao
    r = cli.chat.completions.create(
        model=mod, max_completion_tokens=max_tokens,
        messages=[{"role": "user", "content": texto}],
        tools=[{"type": "function",
                "function": {"name": nome, "description": "Devolve os dados estruturados pedidos.",
                             "parameters": schema}}],
        tool_choice={"type": "function", "function": {"name": nome}})   # OBRIGA
    _registrar_uso(r, mod)
    for tc in (r.choices[0].message.tool_calls or []):
        _ULTIMO_MODO[0] = "function_calling"
        return json.loads(tc.function.arguments)
    raise RuntimeError("modelo não devolveu function_call")


def _json_gemini(mod, instrucao, schema, contexto, max_tokens, nome):
    """Google chama de responseSchema + response_mime_type. Se o schema for recusado (o dialeto é mais
    estreito), cai para JSON MODE sem schema — que ainda garante JSON sintaticamente válido, e é
    incomparavelmente melhor que pedir JSON em prosa e torcer."""
    import json
    from google import genai
    from google.genai import types
    cli = genai.Client(api_key=os.getenv("GEMINI_API_KEY", "") or os.getenv("GOOGLE_API_KEY", ""),
                       http_options=types.HttpOptions(timeout=int(TIMEOUT_S * 1000)))   # ms
    texto = (contexto + "\n\n" + instrucao) if contexto else instrucao
    for cfg, modo in ((types.GenerateContentConfig(max_output_tokens=max_tokens,
                                                   response_mime_type="application/json",
                                                   response_schema=_schema_para_gemini(schema)),
                       "responseSchema"),
                      (types.GenerateContentConfig(max_output_tokens=max_tokens,
                                                   response_mime_type="application/json"),
                       "json_mode(sem schema)")):
        try:
            r = cli.models.generate_content(model=mod, contents=texto, config=cfg)
            _registrar_uso(r, mod)
            _ULTIMO_MODO[0] = modo
            return json.loads(r.text)
        except Exception as e:
            if modo.startswith("responseSchema") and not _transitorio(e):
                continue                               # schema recusado → tenta json mode puro
            raise


def _json_por_provedor(prov):
    """Resolvido na HORA DA CHAMADA, não na importação — o `_json_xai` mora mais abaixo no arquivo
    (junto do `_xai`, para o par ficar lado a lado) e um dicionário no topo quebrava com NameError."""
    return {"anthropic": _json_anthropic, "openai": _json_openai,
            "google": _json_gemini, "xai": _json_xai}.get(prov)


def gerar_json(chain, instrucao, schema, contexto=None, max_tokens=8000, nome="extrair"):
    """Devolve DICT — não texto. SAÍDA ESTRUTURADA: a API OBRIGA o modelo a entregar o objeto no
    formato do schema. JSON malformado (vírgula sobrando, caractere de controle, preâmbulo, comentário)
    deixa de ser POSSÍVEL — não é reparo, é impossibilidade. Mata a classe inteira de falha.

    ═══ 03/Ago/2026 — O FALLBACK ERA MAIS FRACO QUE O PRIMÁRIO, E ISSO NÃO ESTAVA ESCRITO ═══

    Até hoje esta função tinha `if M.provedor(mod) != "anthropic": continue`. O terra e o gemini eram
    PULADOS. Na prática: quando a Anthropic caía, a extração desabava para o modo texto — pedir JSON
    em prosa e torcer, que é EXATAMENTE o mecanismo que derrubou 74% da rodada de 25/07 e que a saída
    estruturada veio matar. A cadeia dizia ter fallback cross-provider; para a extração, não tinha.

    E impedia a medição: comparar o sonnet (com schema imposto pela API) contra o terra (sem) é uma
    luta arranjada — o sonnet ganharia por construção, e o número pareceria medição sendo armadilha.

    As três casas fazem a mesma coisa com nome diferente:
        Anthropic → tool use          (input_schema + tool_choice forçado)
        OpenAI    → function calling  (parameters + tool_choice forçado)
        Google    → responseSchema    (+ response_mime_type=application/json)

    Agora os três têm saída estruturada de verdade, e `_ULTIMO_MODO` registra qual caminho foi usado —
    porque "o gemini caiu para json mode sem schema" é um fato que o instrumento tem de contar.
    """
    erros = []
    for mod in chain:
        fn = _json_por_provedor(M.provedor(mod))
        if fn is None:
            erros.append(f"{mod}: provedor desconhecido")
            continue
        for tentativa in (1, 2, 3):                  # retry com espera crescente (rede/429/sobrecarga)
            try:
                _ULTIMO_MODELO[0] = mod
                return fn(mod, instrucao, schema, contexto, max_tokens, nome)
            except Exception as e:
                if _transitorio(e) and tentativa < 3:
                    import time; time.sleep(5 * tentativa); continue
                erros.append(f"{mod}: {type(e).__name__}: {str(e)[:600]}")
                break
    raise RuntimeError("gerar_json falhou em toda a cadeia:\n  " + "\n  ".join(erros or ["cadeia vazia"]))


def _anthropic(mod, instrucao, contexto, max_tokens, temperatura):
    import anthropic
    cli = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY", ""),
                              timeout=TIMEOUT_S, max_retries=_RETRIES_SDK)
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
            _registrar_uso(r, mod)
            return "".join(b.text for b in r.content if getattr(b, "type", "") == "text")
        except Exception as e:
            if kw and _erro_de_sampling(e):
                continue
            raise


def _openai(mod, instrucao, contexto, max_tokens, temperatura):
    from openai import OpenAI
    cli = OpenAI(api_key=os.getenv("OPENAI_API_KEY", ""),
                 timeout=TIMEOUT_S, max_retries=_RETRIES_SDK)
    texto = (contexto + "\n\n" + instrucao) if contexto else instrucao   # OpenAI cacheia prefixo automático
    for kw in (M.temp_kwargs(mod, temperatura), {}):
        try:
            r = cli.chat.completions.create(model=mod, max_completion_tokens=max_tokens,
                                            messages=[{"role": "user", "content": texto}], **kw)
            _registrar_uso(r, mod)                        # fallback OpenAI também é visível ao instrumento
            return r.choices[0].message.content or ""
        except Exception as e:
            if kw and _erro_de_sampling(e):
                continue
            raise


def _xai(mod, instrucao, contexto, max_tokens, temperatura):
    """xAI (grok) — 04/Ago/2026, entrou no lugar do gemini como 3º degrau.
    A API da xAI é COMPATÍVEL COM A DA OPENAI: mesmo SDK, só muda o endereço e a chave. Por isso
    não há cliente novo aqui — é o `openai` apontando para api.x.ai."""
    from openai import OpenAI
    cli = OpenAI(api_key=os.getenv("XAI_API_KEY", ""), base_url="https://api.x.ai/v1",
                 timeout=TIMEOUT_S, max_retries=_RETRIES_SDK)
    texto = (contexto + "\n\n" + instrucao) if contexto else instrucao
    for kw in (M.temp_kwargs(mod, temperatura), {}):
        try:
            r = cli.chat.completions.create(model=mod, max_completion_tokens=max_tokens,
                                            messages=[{"role": "user", "content": texto}], **kw)
            _registrar_uso(r, mod)
            return r.choices[0].message.content or ""
        except Exception as e:
            if kw and _erro_de_sampling(e):
                continue
            raise


def _json_xai(mod, instrucao, schema, contexto, max_tokens, nome):
    """Saída estruturada no grok — function calling, igual à OpenAI (a API é compatível)."""
    import json
    from openai import OpenAI
    cli = OpenAI(api_key=os.getenv("XAI_API_KEY", ""), base_url="https://api.x.ai/v1",
                 timeout=TIMEOUT_S, max_retries=_RETRIES_SDK)
    texto = (contexto + "\n\n" + instrucao) if contexto else instrucao
    r = cli.chat.completions.create(
        model=mod, max_completion_tokens=max_tokens,
        messages=[{"role": "user", "content": texto}],
        tools=[{"type": "function",
                "function": {"name": nome, "description": "Devolve os dados estruturados pedidos.",
                             "parameters": schema}}],
        tool_choice={"type": "function", "function": {"name": nome}})
    _registrar_uso(r, mod)
    for tc in (r.choices[0].message.tool_calls or []):
        _ULTIMO_MODO[0] = "function_calling(xai)"
        return json.loads(tc.function.arguments)
    raise RuntimeError("grok não devolveu function_call")


def _gemini(mod, instrucao, contexto, max_tokens, temperatura):
    from google import genai
    from google.genai import types
    cli = genai.Client(api_key=os.getenv("GEMINI_API_KEY", "") or os.getenv("GOOGLE_API_KEY", ""),
                       http_options=types.HttpOptions(timeout=int(TIMEOUT_S * 1000)))   # ms
    texto = (contexto + "\n\n" + instrucao) if contexto else instrucao
    cfg = types.GenerateContentConfig(max_output_tokens=max_tokens,
                                      **M.temp_kwargs(mod, temperatura))   # Gemini aceita temperature
    r = cli.models.generate_content(model=mod, contents=texto, config=cfg)
    _registrar_uso(r, mod)                                # fallback Gemini também é visível ao instrumento
    return r.text
