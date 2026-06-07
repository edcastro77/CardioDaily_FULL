#!/usr/bin/env python3
"""
CardioDaily — Tunnel Manager
Inicia cloudflared quicktunnel, captura a URL pública e atualiza o Z-API.
Reinicia automaticamente se o túnel cair.
"""
import os
import re
import subprocess
import sys
import time
import signal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

import requests

ZAPI_INSTANCE  = os.getenv("ZAPI_INSTANCE_ID", "")
ZAPI_TOKEN     = os.getenv("ZAPI_TOKEN", "")
ZAPI_CLIENT    = os.getenv("ZAPI_CLIENT_TOKEN", "")
WEBHOOK_PATH   = "/webhook"
TUNNEL_URL_FILE = ROOT / ".tunnel_url"

proc = None


def atualizar_zapi(url: str) -> bool:
    """Atualiza o webhook do Z-API com a nova URL."""
    webhook_url = url.rstrip("/") + WEBHOOK_PATH
    try:
        r = requests.put(
            f"https://api.z-api.io/instances/{ZAPI_INSTANCE}/token/{ZAPI_TOKEN}/update-webhook-received",
            json={"value": webhook_url},
            headers={"Client-Token": ZAPI_CLIENT},
            timeout=10,
        )
        if r.status_code == 200:
            print(f"✅ Z-API atualizado: {webhook_url}")
            TUNNEL_URL_FILE.write_text(webhook_url)
            return True
        else:
            print(f"❌ Z-API erro {r.status_code}: {r.text[:100]}")
            return False
    except Exception as e:
        print(f"❌ Erro ao atualizar Z-API: {e}")
        return False


def iniciar_tunel():
    """Inicia cloudflared e captura a URL pública."""
    global proc
    print("🚇 Iniciando túnel cloudflared...")
    proc = subprocess.Popen(
        ["cloudflared", "tunnel", "--url", "http://localhost:5055", "--no-autoupdate"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    url = None
    deadline = time.time() + 30
    for line in proc.stdout:
        print(f"  [cf] {line.rstrip()}")
        m = re.search(r"https://[a-z0-9-]+\.trycloudflare\.com", line)
        if m:
            url = m.group(0)
            print(f"\n🌐 URL pública: {url}")
            atualizar_zapi(url)
            break
        if time.time() > deadline:
            print("❌ Timeout aguardando URL do túnel")
            break

    return url


def monitorar():
    """Drena stdout do processo para detectar quedas."""
    global proc
    if proc:
        for line in proc.stdout:
            if "ERR" in line or "error" in line.lower():
                print(f"  [cf] {line.rstrip()}")


def sair(sig, frame):
    global proc
    print("\n⏹ Encerrando túnel...")
    if proc:
        proc.terminate()
    sys.exit(0)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, sair)
    signal.signal(signal.SIGTERM, sair)

    tentativas = 0
    while True:
        tentativas += 1
        print(f"\n{'='*50}")
        print(f"Tentativa {tentativas} — {time.strftime('%H:%M:%S')}")

        url = iniciar_tunel()

        if url:
            print(f"\n✅ Túnel ativo. Monitorando...")
            # Aguarda o processo terminar
            proc.wait()
            print(f"⚠️  Túnel encerrado (código {proc.returncode}). Reiniciando em 5s...")
        else:
            print("⚠️  Falha ao obter URL. Tentando novamente em 10s...")
            if proc:
                proc.terminate()
            time.sleep(10)
            continue

        time.sleep(5)
