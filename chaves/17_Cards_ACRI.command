#!/bin/bash
# ═══ CHAVE 17 · CARD ACRI PARA REDES SOCIAIS ═══════════════════════════════
# 1080×1350 (4:5, feed do Instagram), no layout do Dr. Eduardo.
# Gera para todo artigo com nota ≥7 que ainda não tem card (diretriz: sempre).
# NÃO reanalisa nada: usa o ACRI que já está no disco. ~US$ 0,01 por card.
# ═══════════════════════════════════════════════════════════════════════════
cd "$(dirname "$0")" && source ./config.sh && source "$CD_VENV/bin/activate"
echo "═══════════════════════════════════════"
echo " CHAVE 17 · CARD ACRI (rede social)"
echo "═══════════════════════════════════════"
echo
N=$(ls -d "$CD_FULL/outputs/STAGING"/*/ 2>/dev/null | wc -l | tr -d ' ')
echo "   $N pacote(s) no STAGING · gera só os de nota ≥7 sem card"
echo "   custo: ~US\$ 0,01 por card (só condensa texto que já existe)"
echo
read -r -p "   Quantos? (Enter = todos · um número = só esse tanto, p/ ver antes): " Q
echo
python -u "$CD_FULL/src/card_acri.py" $Q 2>&1 | tee "$CD_FULL/outputs/LOGS/cards_$(date +%Y%m%d-%H%M).log"
echo
echo "   Os cards estão em outputs/STAGING/<artigo>/<artigo>_card.png"
read -p "Enter para fechar. "
