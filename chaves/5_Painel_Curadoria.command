#!/bin/bash
# ═══ CHAVE 5 · PAINEL DE CURADORIA ═══  (VOCÊ escolhe o que sai — nada publica sozinho, só o Radar)
cd "$(dirname "$0")" && source ./config.sh && source "$CD_VENV/bin/activate"
echo "═══════════════════════════════════════"
echo " CHAVE 5 · PAINEL DE CURADORIA"
echo " Filtre por nota, revista, data, MCID e tema — e escolha o que publica no site,"
echo " envia no grupo (WhatsApp/Telegram) ou vira post do Instagram. Um a um, na sua mão."
echo " O sistema NÃO publica nem envia nada sozinho (só o Radar continua diário)."
echo " Abrindo no navegador: http://localhost:8501"
echo "═══════════════════════════════════════"
streamlit run "$CD_FULL/src/painel_curadoria.py"
