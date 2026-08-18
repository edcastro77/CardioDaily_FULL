"""
supabase_chaves.py — UM lugar só para montar o cabeçalho do Supabase.

═══ 14/Ago/2026 — POR QUE ISTO EXISTE ═══

A `SUPABASE_SERVICE_ROLE_KEY` foi encontrada em texto puro num arquivo colado num chat
externo (`outputs/site_operacional/pasted_content_2.txt`, do briefing do site em julho).
Ela dá poder TOTAL no banco: ignora Row Level Security, lê e apaga tudo.

O conserto NÃO é "rotacionar a chave". A `service_role` e a `anon` são as duas assinadas
pelo mesmo JWT secret, e a documentação da Supabase é explícita:

    "anon and service_role must be rotated simultaneously"
    "Currently active users get immediately signed out"
    "it is no longer possible to rotate the legacy anon, service and JWT secrets"

Rotacionar derrubaria o site junto. O caminho documentado para exatamente este caso:

    "If the JWT secret is secure, substitute the service_role JWT-based key with a new
     secret key which you can create in Settings > API Keys. This prevents downtime."

Ou seja: **cria-se uma chave nova do sistema novo (`sb_secret_…`) e aposenta-se a velha.**
As duas valem ao mesmo tempo, então a troca é sem pressa e sem interrupção.

═══ E POR QUE ESTE ARQUIVO, EM VEZ DE TROCAR A STRING E PRONTO ═══

As chaves novas NÃO são JWT. A documentação avisa:

    "You cannot send a publishable or secret key in the Authorization: Bearer header,
     except if the value exactly equals the apikey header."

⚠️ **MEDIDO EM 14/Ago, E O RESULTADO ME DESMENTIU:** testei os dois formatos contra o
projeto real com a chave publishable — `apikey` sozinho e `apikey` + `Authorization:
Bearer` — e os DOIS devolveram **HTTP 200**. Eu tinha previsto 401 lendo a documentação;
o gateway tolera hoje.

Então este módulo não conserta uma quebra: ele **tira a dependência de um comportamento
tolerado mas não documentado**. Se a Supabase apertar essa regra, o CardioDaily não
descobre no dia em que o painel parar de abrir.

Regra: chave JWT (legada) → manda os dois headers, como sempre.
       chave `sb_…` (nova) → manda SÓ o `apikey`, como a documentação pede.
"""

def eh_chave_nova(chave):
    """True para `sb_secret_…` / `sb_publishable_…`; False para as JWT legadas (`eyJ…`)."""
    return str(chave or "").startswith("sb_")


def cabecalhos(chave, extra=None):
    """O cabeçalho certo para ESTA chave. Use em toda chamada REST ao Supabase.

    >>> cabecalhos("eyJhbGciOi...")["Authorization"]      # legada: os dois headers
    'Bearer eyJhbGciOi...'
    >>> "Authorization" in cabecalhos("sb_secret_abc")     # nova: só o apikey
    False
    """
    h = {"apikey": chave}
    if not eh_chave_nova(chave):
        # A chave legada É um JWT válido, e o PostgREST usa o `Authorization` para ler o
        # `role` de dentro dele. Tirar este header numa chave legada QUEBRA de verdade —
        # o oposto do caso novo. Por isso a decisão é pelo TIPO da chave, não por gosto.
        h["Authorization"] = f"Bearer {chave}"
    if extra:
        h.update(extra)
    return h


def descrever(chave):
    """Como a chave aparece num log, sem vazar o valor. Para o diagnóstico da Chave 13."""
    c = str(chave or "")
    if not c:
        return "(vazia)"
    tipo = ("secret NOVA" if c.startswith("sb_secret_") else
            "publishable NOVA" if c.startswith("sb_publishable_") else
            "JWT LEGADA" if c.startswith("eyJ") else "formato desconhecido")
    return f"{tipo} · {c[:12]}…{c[-4:]} ({len(c)} caracteres)"
