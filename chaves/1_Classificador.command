#!/bin/bash
# ═══ CHAVE 1 · CLASSIFICADOR ═══  (classifica e nomeia os PDFs baixados → CLASSIFICADOS/<tipo>/)
cd "$(dirname "$0")" && source ./config.sh && source "$CD_VENV/bin/activate"
echo "═══════════════════════════════════════"
echo " CHAVE 1 · CLASSIFICADOR"
echo " Lendo PDFs de: $CD_INBOX"
echo "═══════════════════════════════════════"
python "$CD_FULL/src/classificador_ouro.py" "$CD_INBOX"
echo
echo "✔ Classificados em: $CD_CLASSIFICADOS"
read -p "Enter para fechar. "
