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
CENT=$((N * 2))                      # sem awk — ver o comentário na Chave 11 (travou o Terminal em 04/Ago)
printf "   Custo aproximado: US\$ %d.%02d\n" $((CENT/100)) $((CENT%100))
echo "   (o modelo só é chamado quando as camadas determinísticas não decidem sozinhas)"
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
