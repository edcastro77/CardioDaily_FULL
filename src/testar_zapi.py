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
    if tem_instancia:
        try:
            inst = partes[partes.index("instances") + 1]
            print(f"   instância: {inst[:8]}…{inst[-4:]}  ({len(inst)} caracteres)")
            print("   ⚠️  CONFIRA ESTE ID contra o painel em app.z-api.io — o CLAUDE.md e o")
            print("       alerta do distribuidor citam IDs que DIFEREM num dígito (…2284… × …2204…).")
        except Exception:
            pass

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
            print(f"   🔴 A instância NÃO está pareada. Motivo: {d.get('error') or d}")
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
