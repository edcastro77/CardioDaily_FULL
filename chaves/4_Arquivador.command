#!/bin/bash
# ═══ CHAVE 4 · ARQUIVADOR ═══  (move o staging publicado pro ARQUIVO e limpa)
cd "$(dirname "$0")" && source ./config.sh && source "$CD_VENV/bin/activate"
echo "═══════════════════════════════════════"
echo " CHAVE 4 · ARQUIVADOR"
echo " Staging: $CD_STAGING"
echo "═══════════════════════════════════════"
python "$CD_FULL/src/arquivador.py" "$CD_STAGING"            # dry-run: mostra o que arquivaria
echo
read -p "Enter para ARQUIVAR de verdade · Ctrl+C para cancelar. "
python "$CD_FULL/src/arquivador.py" "$CD_STAGING" --arquivar
echo
read -p "✔ Arquivado. Enter para fechar. "
