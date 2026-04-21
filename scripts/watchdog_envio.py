#!/usr/bin/env python3
"""
CardioDaily — Watchdog de envio diário.

Roda às 07:15. Verifica se o distribuidor.py rodou com sucesso hoje às 07:00.
Se não encontrar entrada de hoje no log, envia alerta no Telegram.

Crontab:
  15 7 * * * cd /Users/edcastro77/CardioDaily_FULL && /opt/homebrew/bin/python3 scripts/watchdog_envio.py >> logs/watchdog.log 2>&1
"""

import os
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

import httpx

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID", "237863636")
LOG_FILE           = ROOT / "logs" / "distribuidor.log"

HOJE = datetime.now().strftime("%Y-%m-%d 07:")  # qualquer linha das 07h de hoje


def enviar_alerta(msg: str):
    if not TELEGRAM_BOT_TOKEN:
        print(f"[watchdog] SEM TOKEN — alerta não enviado: {msg}")
        return
    try:
        httpx.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": msg},
            timeout=10,
        )
        print(f"[watchdog] Alerta enviado: {msg}")
    except Exception as e:
        print(f"[watchdog] Erro ao enviar alerta: {e}")


def main():
    agora = datetime.now().strftime("%Y-%m-%d %H:%M")
    print(f"[watchdog] {agora} — verificando envio de hoje...")

    if not LOG_FILE.exists():
        enviar_alerta(
            "⚠️ CardioDaily — LOG NÃO ENCONTRADO\n"
            f"Arquivo {LOG_FILE} não existe.\n"
            "Verifique se o distribuidor está configurado corretamente."
        )
        return

    # Ler as últimas 200 linhas (evita ler o arquivo inteiro)
    linhas = LOG_FILE.read_text(encoding="utf-8", errors="ignore").splitlines()
    recentes = linhas[-200:]

    enviou_hoje = any(HOJE in linha for linha in recentes)

    if enviou_hoje:
        # Contar artigos enviados hoje
        enviados = sum(1 for l in recentes if HOJE in l and "Enviando para" in l)
        print(f"[watchdog] ✅ Envio de hoje detectado ({enviados} envios registrados)")
    else:
        enviar_alerta(
            "🚨 CardioDaily — ENVIO DAS 07:00 NÃO OCORREU\n\n"
            f"Nenhuma entrada de hoje ({datetime.now().strftime('%d/%m/%Y')}) "
            "encontrada no log do distribuidor.\n\n"
            "Verifique o crontab ou rode manualmente:\n"
            "cd ~/CardioDaily_FULL && python3 distribuidor.py artigos"
        )


if __name__ == "__main__":
    main()
