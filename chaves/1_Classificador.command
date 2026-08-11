#!/bin/bash
# ═══ CHAVE 1 · CLASSIFICADOR ═══  (classifica e nomeia os PDFs baixados → CLASSIFICADOS/<tipo>/)
#
# 03/Ago: passou a MOSTRAR o que vai fazer e PEDIR [s/N] antes de gastar. Junto com a Chave 2,
# eram as duas únicas que gastavam dinheiro e moviam arquivo sem perguntar nada — enquanto a 7,
# a 8 e a 10, que fazem bem menos estrago, todas perguntavam.
# ═══════════════════════════════════════════════════════════════════════════
cd "$(dirname "$0")" && source ./config.sh && source "$CD_VENV/bin/activate"

echo "═══════════════════════════════════════"
echo " CHAVE 1 · CLASSIFICADOR"
echo " Lendo PDFs de: $CD_INBOX"
echo "═══════════════════════════════════════"
echo

N=$(ls "$CD_INBOX"/*.pdf 2>/dev/null | grep -cv '/\._')
[ -z "$N" ] && N=0
if [ "$N" -eq 0 ]; then
  echo "   Nenhum PDF na RAIZ de ARTIGOS/ — é só daí que esta chave lê."
  echo "   Se os PDFs já estão nas pastas de CLASSIFICADOS e você quer reclassificar,"
  echo "   rode a Chave 10 (Devolver para a Fila) primeiro."
  echo
  read -p "Enter para fechar. "; exit 0
fi

echo "   $N PDF na fila  ·  vão ser LIDOS, RENOMEADOS e MOVIDOS para CLASSIFICADOS/<tipo>/"
# ═══ 10/Ago — A TELA MENTIA EM DOIS PONTOS ═══
# Dizia "(o modelo só é chamado quando as camadas determinísticas não decidem sozinhas)" —
# verdade até ontem, quando 6 camadas decidiam antes dele e só 22 % chegavam ao juiz.
# Hoje é o CONTRÁRIO: decidem antes só o mapa de revista e o filtro de lixo; o LLM lê e decide
# todo o resto. Foi a decisão do Dr. Eduardo depois de medir o preço da leitura.
# E o custo estava em 2 centavos por artigo — 20× acima do medido (736 leituras reais no
# uso.jsonl: mediana de 4.482 tokens de entrada, US$ 0,001 por artigo).
# Mesmo defeito dos US$ 0,30 da Chave 2: número chumbado que o dono lê como se fosse medida.
CENT_MIL=$((N * 1))                  # 0,1 centavo por artigo — MEDIDO, não chutado
printf "   Custo aproximado: US\$ %d.%02d   (medido: ~US\$ 0,001 por artigo)\n" \
       $((CENT_MIL/1000)) $(((CENT_MIL%1000)/10))
echo "   O LLM lê as páginas 1-3 de PRATICAMENTE TODO artigo e decide o tipo."
echo "   Só o mapa de revista (Clinics, EHJ Supplements) e o filtro de lixo decidem antes dele."
echo
read -r -p "   Começar? [s/N]: " OK
case "$OK" in s|S|sim|SIM) ;; *) echo "   Cancelado. Nada foi gasto e nada foi movido."; read -p "Enter. "; exit 0 ;; esac
echo

# ═══ 09/Ago — O "✔" DECORATIVO ═══
# Esta chave imprimia "✔ Classificados em:" SEM ler o código de saída — exatamente o defeito
# que a Chave 2 documenta e corrigiu em 06/Ago e que aqui continuava vivo. Uma rodada que
# abortava no meio terminava com o mesmo visto verde de uma rodada perfeita.
LOGDIR="$CD_FULL/outputs/LOGS"; mkdir -p "$LOGDIR"
DIARIO="$LOGDIR/chave1_$(date +%Y%m%d-%H%M).log"
set -o pipefail
python -u "$CD_FULL/src/classificador_ouro.py" "$CD_INBOX" 2>&1 | tee "$DIARIO"
RC=${PIPESTATUS[0]}
echo
if [ "$RC" -ne 0 ]; then
  echo "⛔ O CLASSIFICADOR TERMINOU COM FALHA (código $RC)."
  echo "   Os PDFs que não foram movidos continuam na fila, intactos."
  echo "   O motivo está no fim do diário — e o percurso de cada artigo está no plano de voo:"
  echo "      python3 src/caixa_preta.py          (custo zero)"
else
  echo "✔ Classificados em: $CD_CLASSIFICADOS"
  echo "  Diário desta rodada: o _CLASSIFICACAO_*.csv em ARTIGOS/ — confira ANTES de rodar a Chave 2."
fi
echo "  Log: ${DIARIO/#$HOME/~}"
read -p "Enter para fechar. "
