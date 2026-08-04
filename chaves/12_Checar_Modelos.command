#!/bin/bash
# ═══ CHAVE 12 · EXAME DAS CADEIAS ══════════════════════════════════════════
# Bate na porta de CADA modelo do modelos.py e diz quais respondem de verdade.
#
# POR QUE (04/Ago, 01h48): na primeira prova da extração o gemini-3.1-pro-preview falhou nos DOIS
# caminhos — estruturado e texto. Ele é o ÚLTIMO FALLBACK de quase toda cadeia. Se não responde,
# a LEI DA EQUIVALÊNCIA tem dois degraus, não três — e ninguém sabia, porque fallback só é
# exercitado quando o primário cai: no meio de um lote de 431 artigos, às 3 da manhã.
#
# Fallback que nunca foi testado não é fallback. É uma linha de código que faz o dono se sentir seguro.
#
# Custa centavos (~20 tokens por modelo). Não lê PDF, não move arquivo, não publica.
# ═══════════════════════════════════════════════════════════════════════════
cd "$(dirname "$0")" && source ./config.sh && source "$CD_VENV/bin/activate"
cd "$CD_FULL" || exit 1
python3 src/checar_modelos.py
echo
read -p "Enter para fechar. "
