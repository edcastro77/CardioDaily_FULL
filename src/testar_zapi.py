"""
testar_zapi.py — POR QUE A MENSAGEM NÃO CHEGOU. Custo zero, não envia nada.

═══════════════════════════════════════════════════════════════════════════════════════
POR QUE ESTE ARQUIVO EXISTE
═══════════════════════════════════════════════════════════════════════════════════════

11/Ago/2026. O Dr. Eduardo aprovou 2 artigos, clicou ENVIAR, e:
    · opção 2 → "Z-API desconectada" (era timeout, não desconexão — já consertado)
    · opção 3 → "CONCLUÍDO — 2 artigos enviados"  … e nada chegou no WhatsApp.

Dizer "enviei" e não ter enviado é o pior estado possível: ele confia, fecha a janela, e
descobre pela ausência. Este programa existe para responder ONDE a corrente arrebenta, sem
mandar mensagem nenhuma e sem gastar nada.

O QUE ELE OLHA, em ordem — cada degrau só faz sentido se o de cima passou:
    1. as variáveis existem no .env?           (ZAPI_BASE, ZAPI_CLIENT_TOKEN, EDUARDO_PHONE)
    2. a URL tem o formato que a Z-API espera?
    3. a máquina alcança o servidor?           (DNS + rota + TLS)
    4. o endpoint /status responde?            (token válido?)
    5. o WhatsApp está pareado?                (`connected: true`)

NUNCA imprime o valor de um token — só se existe e quantos caracteres tem. O .env é dele.

    python3 src/testar_zapi.py
"""
import os
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
sys.path.insert(0, _HERE)

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(_ROOT, ".env"), override=True)
except ImportError:
    pass

import httpx


def _mascara(v):
    """Mostra que existe e o tamanho, nunca o valor."""
    if not v:
        return "❌ VAZIO"
    return f"✅ {len(v)} caracteres · começa com {v[:6]}…"


def main():
    print("═" * 78)
    print(" DIAGNÓSTICO DA Z-API — não envia nada, não gasta nada")
    print("═" * 78)

    base = os.getenv("ZAPI_BASE", "").rstrip("/")
    token = os.getenv("ZAPI_CLIENT_TOKEN", "")
    phone = os.getenv("EDUARDO_PHONE", "")

    # ── 1. as variáveis ──
    print("\n   ── 1. O QUE ESTÁ NO .env ──")
    print(f"   ZAPI_BASE         {_mascara(base)}")
    print(f"   ZAPI_CLIENT_TOKEN {_mascara(token)}")
    print(f"   EDUARDO_PHONE     {_mascara(phone)}")
    if not base:
        print("\n   🔴 PAROU AQUI: sem ZAPI_BASE não há para onde mandar.")
        print("      Abra a Chave 13 e confira a linha ZAPI_BASE.")
        return 1
    if not phone:
        print("\n   🔴 PAROU AQUI: sem EDUARDO_PHONE o distribuidor não tem destinatário —")
        print("      e ele devolve uma lista VAZIA de assinantes sem reclamar (linha 223).")
        return 1

    # ── 2. o formato da URL ──
    print("\n   ── 2. O FORMATO DA URL ──")
    # a Z-API usa https://api.z-api.io/instances/<ID>/token/<TOKEN>
    partes = base.split("/")
    tem_instancia = "instances" in partes
    tem_token = "token" in partes
    print(f"   {'✅' if base.startswith('http')  else '🔴'} começa com http")
    print(f"   {'✅' if tem_instancia else '🔴'} tem /instances/ no caminho")
    print(f"   {'✅' if tem_token     else '🔴'} tem /token/ no caminho")
    # ═══ 11/Ago — SÃO DOIS TOKENS DIFERENTES, E EU SÓ MOSTRAVA UM ═══
    # O Dr. Eduardo abriu o painel e conferiu: o ID da instância do .env está CERTO
    # (3F0C2204…, igual ao painel — quem estava errado era o CLAUDE.md, documentação velha),
    # e o ZAPI_CLIENT_TOKEN também (Fef…, igual à tela de Segurança).
    # Mesmo assim: NOT_FOUND. Porque existe um TERCEIRO segredo que eu não estava imprimindo:
    #
    #     https://api.z-api.io/instances/<ID>/token/<TOKEN_DA_INSTANCIA>
    #                                             └── este, da coluna TOKEN do painel
    #     header Client-Token: <TOKEN_DA_CONTA>   └── este, da tela Segurança
    #
    # A Z-API devolve NOT_FOUND quando o PAR instância+token da URL não bate — não só quando o
    # ID não existe. Um diagnóstico que mostra o ID e esconde o token da URL manda o dono
    # conferir metade do problema. Agora mostra os dois, sempre mascarados.
    if tem_instancia:
        try:
            inst = partes[partes.index("instances") + 1]
            print(f"   ID da instância   : {inst[:16]}…{inst[-4:]}  ({len(inst)} caracteres)")
            print("      → compare com a coluna ID em Instâncias Web")
        except Exception:
            pass
    if tem_token:
        try:
            tk = partes[partes.index("token") + 1]
            print(f"   TOKEN na URL      : {tk[:18]}…{tk[-4:]}  ({len(tk)} caracteres)")
            print("      → compare com a coluna TOKEN em Instâncias Web (NÃO é o Client-Token)")
        except Exception:
            pass
    print(f"   Client-Token      : {token[:6]}…  (tela Segurança → Token de segurança da conta)")
    print()
    print("   ⚠️  SÃO TRÊS SEGREDOS DIFERENTES. O NOT_FOUND aparece se o ID OU o TOKEN DA URL")
    print("       estiverem errados — o Client-Token só é testado depois que esses dois passam.")

    # ── 3. a máquina alcança o servidor? ──
    print("\n   ── 3. A SUA MÁQUINA ALCANÇA A Z-API? ──")
    host = "/".join(base.split("/")[:3])
    t0 = time.time()
    try:
        r = httpx.get(host, timeout=15, follow_redirects=True)
        print(f"   ✅ {host} respondeu em {time.time() - t0:.1f}s (HTTP {r.status_code})")
    except Exception as e:
        print(f"   🔴 {host} NÃO respondeu em {time.time() - t0:.1f}s — {type(e).__name__}: {e}")
        print()
        print("   PAROU AQUI. O problema é de REDE, não do CardioDaily:")
        print("     · a sua internet, o DNS, um firewall ou VPN")
        print("     · o Radar de hoje saiu do GITHUB, não deste Mac — por isso ele chegou")
        print("       e este envio não. São caminhos de rede diferentes.")
        return 1

    # ── 4 e 5. o endpoint e o pareamento ──
    print("\n   ── 4. O ENDPOINT /status ──")
    for tent in (1, 2, 3):
        t0 = time.time()
        try:
            r = httpx.get(f"{base}/status",
                          headers={"Client-Token": token} if token else {}, timeout=20)
            print(f"   HTTP {r.status_code} em {time.time() - t0:.1f}s")
            if r.status_code == 401 or r.status_code == 403:
                print("   🔴 TOKEN RECUSADO. O ZAPI_CLIENT_TOKEN do .env não vale para esta instância.")
                return 1
            if r.status_code >= 400:
                print(f"   🔴 resposta: {r.text[:200]}")
                return 1
            d = r.json()
            print("\n   ── 5. O WHATSAPP ESTÁ PAREADO? ──")
            con = d.get("connected")
            print(f"   connected = {con}")
            if con:
                print("\n   ✅ TUDO CERTO. A Z-API está conectada e alcançável daqui.")
                print("      Se a mensagem não chegou mesmo assim, o problema é no ENVIO —")
                print("      rode a Chave 21 e me mande as linhas que começam com 'Erro WhatsApp'.")
                return 0
            motivo = str(d.get("error") or d)

            # ═══ 11/Ago — NOT_FOUND NÃO É "DESCONECTADA" ═══
            # Esta mensagem dizia "a instância NÃO está pareada — escaneie o QR code", e para
            # NOT_FOUND isso está errado: o Dr. Eduardo iria ao painel escanear um QR code de
            # uma instância que EXISTE e está boa, enquanto o problema é o ID no .env.
            # É o terceiro diagnóstico errado do mesmo dia (o "Z-API desconectada" que era
            # timeout, o "CONCLUÍDO" que não enviou, e este). Mandar o dono resolver o problema
            # errado é pior que não dizer nada.
            if "NOT_FOUND" in motivo.upper() or "NOT FOUND" in motivo.upper():
                print(f"   🔴 O SERVIDOR NÃO CONHECE ESTA INSTÂNCIA. Resposta: {motivo}")
                print()
                print("   ISTO NÃO É DESCONEXÃO — não adianta escanear QR code. O ID que está")
                print("   no seu .env não existe na Z-API. Ou ele foi digitado errado, ou a")
                print("   instância foi recriada e o .env ficou com o número velho.")
                print()
                print("   O CASO REAL DE 11/Ago: o .env tinha 3F0C22[04]… e o ID certo era")
                print("   3F0C22[84]… — UM dígito. O Radar chegava porque sai do GitHub Actions,")
                print("   que usa o secret ZAPI_BASE (correto); o envio da máquina usava o .env.")
                print()
                print("   O QUE FAZER:")
                print("     1. app.z-api.io → copie o ID da instância e o token")
                print("     2. Chave 13 (Abrir o .env) → corrija a linha ZAPI_BASE")
                print("     3. rode este diagnóstico de novo")
                print("     4. confira também o secret do GitHub, se quiser os dois iguais")
                return 1

            print(f"   🔴 A instância existe, mas NÃO está pareada. Motivo: {motivo}")
            print("      Vá em app.z-api.io → sua instância → Conectar → escaneie o QR code.")
            return 1
        except Exception as e:
            print(f"   tentativa {tent}/3: {type(e).__name__}: {e}")
            if tent < 3:
                time.sleep(2 * tent)
    print("\n   🔴 O servidor da Z-API responde, mas o /status desta instância não.")
    print("      Confira o ID da instância no painel: se ele mudou, o .env está velho.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
