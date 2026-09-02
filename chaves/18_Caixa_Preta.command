#!/bin/bash
# ═══ CHAVE 18 · CAIXA-PRETA ════════════════════════════════════════════════
# "Um avião que sai do Brasil para Paris não pode andar 2.000 km sem dizer
#  onde está. Se ele não se comunica com o próximo radar, AQUELE TRECHO vai
#  ser investigado — já se sabe qual região varrer."   — Dr. Eduardo, 09/Ago
#
# Lê o plano de voo e responde: o que rodou · quem não chegou · onde procurar.
# CUSTO ZERO: não chama modelo, não fala com banco, não escreve nada.
# ═══════════════════════════════════════════════════════════════════════════
cd "$(dirname "$0")" && source ./config.sh && source "$CD_VENV/bin/activate"
echo "═══════════════════════════════════════"
echo " CHAVE 18 · CAIXA-PRETA"
echo " o que aconteceu de verdade · custo zero"
echo "═══════════════════════════════════════"
echo
echo "   Enter = últimas 24h"
echo "   um número = quantas horas olhar (ex.: 72)"
echo "   uma palavra = filtrar pelo nome (ex.: radar, coffee)"
echo
read -r -p "   Período/filtro: " Q
echo
python -u "$CD_FULL/src/caixa_preta.py" $Q
echo
# ═══ 02/Set — O CONFERIDOR DE NOTAS ENTRA NA ROTINA (perícia das notas) ═══
# A nuvem NÃO consegue conferir fóssil: o recálculo do motor precisa dos fatos,
# que vivem SÓ neste disco. Então a vigilância mora aqui, na chave que você já
# abre para ver o estado do sistema. Só leitura; o resumo diz se alguma peça
# (ou a linha do Supabase) discorda do motor de hoje.
echo "───────────────────────────────────────"
echo " CONFERIDOR DE NOTAS (resumo · só leitura)"
set -a; source "$CD_FULL/.env" 2>/dev/null; set +a
python -u "$CD_FULL/src/conferir_notas.py" --supabase 2>&1 | tail -4
echo
read -p "Enter para fechar. "
