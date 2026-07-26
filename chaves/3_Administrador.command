#!/bin/bash
# ═══ CHAVE 3 · ADMINISTRADOR ═══  (painel que mostra o publicado, com filtros — abre no navegador)
cd "$(dirname "$0")" && source ./config.sh && source "$CD_VENV/bin/activate"
echo "═══════════════════════════════════════"
echo " CHAVE 3 · ADMINISTRADOR"
echo " Abrindo o painel no navegador (localhost:8501)…"
echo " Feche esta janela ou Ctrl+C para parar."
echo "═══════════════════════════════════════"
streamlit run "$CD_FULL/src/administrador.py"
