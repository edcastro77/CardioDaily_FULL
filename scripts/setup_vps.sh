#!/bin/bash
# CardioDaily — Setup VPS (Ubuntu 22.04)
# Uso: bash setup_vps.sh
# Executar como root no servidor recém-criado

set -e
echo "========================================"
echo " CardioDaily VPS Setup"
echo "========================================"

# ── 1. Sistema base ────────────────────────────────────────────────────────────
apt-get update -qq && apt-get upgrade -y -qq
apt-get install -y -qq git python3 python3-pip python3-venv curl wget \
    build-essential libssl-dev libffi-dev python3-dev nginx certbot python3-certbot-nginx

# ── 2. Usuário cardiodaily ─────────────────────────────────────────────────────
if ! id -u cardiodaily &>/dev/null; then
    useradd -m -s /bin/bash cardiodaily
    echo "Usuário cardiodaily criado"
fi

# ── 3. Clonar repositório ──────────────────────────────────────────────────────
REPO_DIR="/opt/cardiodaily"
if [ ! -d "$REPO_DIR" ]; then
    git clone https://github.com/edcastro77/CardioDaily_FULL.git "$REPO_DIR"
else
    cd "$REPO_DIR" && git pull origin main
fi
chown -R cardiodaily:cardiodaily "$REPO_DIR"

# ── 4. Virtualenv + dependências ──────────────────────────────────────────────
cd "$REPO_DIR"
sudo -u cardiodaily python3 -m venv venv
sudo -u cardiodaily venv/bin/pip install --quiet --upgrade pip
sudo -u cardiodaily venv/bin/pip install --quiet -r requirements.txt

# ── 5. Diretórios de log ───────────────────────────────────────────────────────
sudo -u cardiodaily mkdir -p "$REPO_DIR/logs"

# ── 6. Arquivo .env ────────────────────────────────────────────────────────────
if [ ! -f "$REPO_DIR/.env" ]; then
    cat > "$REPO_DIR/.env" << 'ENVEOF'
SUPABASE_URL=https://hzqtogcpwdzhjfroxtfz.supabase.co
SUPABASE_SERVICE_KEY=PREENCHER
ANTHROPIC_API_KEY=PREENCHER
GEMINI_API_KEY=PREENCHER
OPENAI_API_KEY=PREENCHER
ZAPI_BASE=https://api.z-api.io/instances/3F0C22040662826CFF327E97F8598275/token
ZAPI_CLIENT_TOKEN=PREENCHER
TELEGRAM_BOT_TOKEN=PREENCHER
TELEGRAM_CHAT_ID=PREENCHER
ENVEOF
    chown cardiodaily:cardiodaily "$REPO_DIR/.env"
    echo ""
    echo "⚠️  PREENCHA o arquivo .env antes de continuar:"
    echo "   nano $REPO_DIR/.env"
fi

# ── 7. Serviço systemd: webhook_server ────────────────────────────────────────
cat > /etc/systemd/system/cardiodaily-webhook.service << EOF
[Unit]
Description=CardioDaily WhatsApp Webhook Server
After=network.target

[Service]
Type=simple
User=cardiodaily
WorkingDirectory=$REPO_DIR
ExecStart=$REPO_DIR/venv/bin/python3 scripts/webhook_server.py --port 5055
Restart=always
RestartSec=10
StandardOutput=append:$REPO_DIR/logs/webhook.log
StandardError=append:$REPO_DIR/logs/webhook.log

[Install]
WantedBy=multi-user.target
EOF

# ── 8. Serviço systemd: distribuidor (artigos 7h + radar 8h via cron) ─────────
cat > /etc/systemd/system/cardiodaily-distribuidor.service << EOF
[Unit]
Description=CardioDaily Distribuidor Diário
After=network.target

[Service]
Type=oneshot
User=cardiodaily
WorkingDirectory=$REPO_DIR
ExecStart=$REPO_DIR/venv/bin/python3 distribuidor.py artigos
StandardOutput=append:$REPO_DIR/logs/distribuidor.log
StandardError=append:$REPO_DIR/logs/distribuidor.log
EOF

cat > /etc/systemd/system/cardiodaily-radar.service << EOF
[Unit]
Description=CardioDaily Radar Diário
After=network.target

[Service]
Type=oneshot
User=cardiodaily
WorkingDirectory=$REPO_DIR
ExecStart=$REPO_DIR/venv/bin/python3 distribuidor.py radar
StandardOutput=append:$REPO_DIR/logs/distribuidor.log
StandardError=append:$REPO_DIR/logs/distribuidor.log
EOF

cat > /etc/systemd/system/cardiodaily-watchdog.service << EOF
[Unit]
Description=CardioDaily Watchdog
After=network.target

[Service]
Type=oneshot
User=cardiodaily
WorkingDirectory=$REPO_DIR
ExecStart=$REPO_DIR/venv/bin/python3 scripts/watchdog_envio.py
StandardOutput=append:$REPO_DIR/logs/watchdog.log
StandardError=append:$REPO_DIR/logs/watchdog.log
EOF

# ── 9. Timers systemd (substitui crontab — mais robusto) ──────────────────────
cat > /etc/systemd/system/cardiodaily-distribuidor.timer << EOF
[Unit]
Description=CardioDaily Distribuidor 7h (Horário de Brasília = UTC-3)

[Timer]
OnCalendar=*-*-* 10:00:00 UTC
Persistent=true

[Install]
WantedBy=timers.target
EOF

cat > /etc/systemd/system/cardiodaily-radar.timer << EOF
[Unit]
Description=CardioDaily Radar 8h (UTC-3)

[Timer]
OnCalendar=*-*-* 11:00:00 UTC
Persistent=true

[Install]
WantedBy=timers.target
EOF

cat > /etc/systemd/system/cardiodaily-watchdog.timer << EOF
[Unit]
Description=CardioDaily Watchdog 7h15 (UTC-3)

[Timer]
OnCalendar=*-*-* 10:15:00 UTC
Persistent=true

[Install]
WantedBy=timers.target
EOF

# ── 10. Nginx reverse proxy ────────────────────────────────────────────────────
cat > /etc/nginx/sites-available/cardiodaily << 'EOF'
server {
    listen 80;
    server_name _;

    location /webhook {
        proxy_pass http://127.0.0.1:5055;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /health {
        proxy_pass http://127.0.0.1:5055;
    }
}
EOF
ln -sf /etc/nginx/sites-available/cardiodaily /etc/nginx/sites-enabled/cardiodaily
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx

# ── 11. Ativar tudo ────────────────────────────────────────────────────────────
systemctl daemon-reload
systemctl enable --now cardiodaily-webhook
systemctl enable cardiodaily-distribuidor.timer
systemctl enable cardiodaily-radar.timer
systemctl enable cardiodaily-watchdog.timer
systemctl start cardiodaily-distribuidor.timer
systemctl start cardiodaily-radar.timer
systemctl start cardiodaily-watchdog.timer

echo ""
echo "========================================"
echo " Setup concluído!"
echo "========================================"
echo ""
echo "Próximos passos:"
echo "  1. Preencha o .env:  nano $REPO_DIR/.env"
echo "  2. Reinicie webhook: systemctl restart cardiodaily-webhook"
echo "  3. Configure Z-API webhook URL: http://$(curl -s ifconfig.me)/webhook"
echo "  4. Verifique logs:   journalctl -u cardiodaily-webhook -f"
echo ""
echo "Timers ativos (horário Brasília):"
echo "  07:00 → distribuidor artigos"
echo "  07:15 → watchdog"
echo "  08:00 → radar"
echo ""
