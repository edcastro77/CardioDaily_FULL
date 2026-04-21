#!/usr/bin/env python3
"""
CardioDaily — Servidor de Webhook WhatsApp (Z-API)

Recebe mensagens inbound do Z-API e processa via webhook_handler.
O Z-API faz POST para: http://SEU_DOMINIO/webhook

Uso:
  python3 scripts/webhook_server.py          # porta 5055
  python3 scripts/webhook_server.py --port 8080

Para expor publicamente no beta (Mac):
  ngrok http 5055
  → Copie a URL https e configure em app.z-api.io → Instâncias → Webhook
"""

import argparse
import logging
import sys
from pathlib import Path

from flask import Flask, request, jsonify

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from whatsapp.webhook_handler import handle_webhook

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(ROOT / "logs" / "webhook.log"),
    ],
)
log = logging.getLogger("webhook")

app = Flask(__name__)


@app.route("/webhook", methods=["POST"])
def webhook():
    payload = request.get_json(silent=True) or {}
    log.info(f"POST /webhook — phone={payload.get('phone')} type={payload.get('type')} body={repr(payload.get('body', ''))[:80]}")
    try:
        result = handle_webhook(payload)
        log.info(f"  → action={result.get('action')}")
        return jsonify({"ok": True, **result}), 200
    except Exception as e:
        log.exception(f"Erro ao processar webhook: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=5055)
    parser.add_argument("--host", default="0.0.0.0")
    args = parser.parse_args()

    import os
    os.makedirs(ROOT / "logs", exist_ok=True)

    log.info(f"CardioDaily Webhook Server — {args.host}:{args.port}")
    log.info("Configure o Z-API: app.z-api.io → Instâncias → Webhook → POST /webhook")
    app.run(host=args.host, port=args.port, debug=False)
