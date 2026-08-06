#!/bin/bash
# ═══ CHAVE 16 · CONFERIDOR DE NOTAS ════════════════════════════════════════
# "visual abstract aparece uma nota e no texto outra" — Dr. Eduardo, 06/Ago.
# Varre TODAS as peças de TODOS os pacotes e diz onde a nota diverge do motor.
# Custo ZERO: não chama LLM, não escreve nada. Só lê e conta.
# Inclui a LINHA DO SUPABASE — que é o que o site mostra, e é onde eu não
# consigo olhar do meu lado.
# ═══════════════════════════════════════════════════════════════════════════
cd "$(dirname "$0")" && source ./config.sh && source "$CD_VENV/bin/activate"
python -u "$CD_FULL/src/conferir_notas.py" --supabase 2>&1 | tee "$CD_FULL/outputs/LOGS/notas_$(date +%Y%m%d-%H%M).log"
echo
read -p "Enter para fechar. "
