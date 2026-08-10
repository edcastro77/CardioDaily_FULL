#!/bin/bash
# ═══ CHAVE 19 · CUSTO ═══  (para onde o dinheiro foi — custo ZERO para rodar)
#
# Lê o `outputs/uso.jsonl`, que o `llm_client.py` grava desde 27/Jul: uma linha por chamada de
# LLM, com tokens de entrada, saída, cache, etapa e artigo. Em 09/Ago havia 3.767 chamadas ali
# e NINGUÉM NUNCA TINHA ABERTO O ARQUIVO — enquanto a Chave 2 decidia por um chute de US$ 0,30
# que estava 55 % acima do real.
#
# Não chama modelo. Não fala com o Supabase. Não escreve nada além da tela.
# ═══════════════════════════════════════════════════════════════════════════
cd "$(dirname "$0")" && source ./config.sh && source "$CD_VENV/bin/activate"
cd "$CD_FULL"

clear
echo "═══════════════════════════════════════"
echo " CHAVE 19 · PARA ONDE O DINHEIRO FOI"
echo "═══════════════════════════════════════"
echo
echo "   1) últimos 7 dias   (a máquina de HOJE — é este o número que vale)"
echo "   2) últimos 30 dias"
echo "   3) o histórico inteiro"
echo
read -r -p "   Escolha [1-3, Enter = 1]: " E
case "$E" in
  2) ARG="30" ;;
  3) ARG="--tudo" ;;
  *) ARG="7" ;;
esac
echo
python3 src/custo.py $ARG
echo
echo "   A tabela de preços é src/precos.py. Se você conferir a sua FATURA e corrigir os"
echo "   valores lá, é só rodar esta chave de novo: o histórico inteiro se recalcula, sem"
echo "   gastar um centavo e sem reanalisar um artigo. Token é medido; dinheiro é derivado."
echo
read -p "Enter para fechar. "
