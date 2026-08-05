#!/bin/bash
# ═══ CHAVE 15 · AMOSTRA — VER 1 ARTIGO PRONTO ANTES DO LOTE ════════════════
#
# POR QUE ESTA CHAVE EXISTE (05/Ago/2026)
#
# O Dr. Eduardo pediu, antes de rodar os 431: *"rode uma avaliação de artigo original e 1 avaliação
# de revisão e me mostre o resultado — inclusive PDF / áudio / visual abstract"*.
#
# Ele está certo, e é o oposto do que a gente fez o dia todo: a régua foi reescrita cinco vezes
# (Escada, escala de aplicabilidade, MCID conferido, limiar da casa, independência editorial) e
# NADA disso rodou com dado real. Tudo o que eu disse hoje é "testei aqui" — função pura, com fatos
# de mentira. Gastar US$ 122 nos 431 sem ver UM artigo pronto é apostar, não medir.
#
# A Chave 2 só roda pasta inteira. Esta roda O ARTIGO QUE VOCÊ ESCOLHER, pelo mesmo caminho de
# produção — mesmo extrator, mesmo motor, mesmo redator, mesmo portão. O que sair aqui sai lá.
#
# Custo: ~US$ 0,35 por artigo.
# ═══════════════════════════════════════════════════════════════════════════
cd "$(dirname "$0")" && source ./config.sh && source "$CD_VENV/bin/activate"

echo "═══════════════════════════════════════"
echo " CHAVE 15 · AMOSTRA"
echo " Prova a régua nova em dado REAL, antes de gastar no lote."
echo "═══════════════════════════════════════"
echo

echo "   ── DE QUAL PASTA? ──"
echo "     1) ARTIGOS_ORIGINAIS  ($(ls "$CD_CLASSIFICADOS/ARTIGOS_ORIGINAIS"/*.pdf 2>/dev/null|wc -l|tr -d ' '))"
echo "     2) REVISOES           ($(ls "$CD_CLASSIFICADOS/REVISOES"/*.pdf 2>/dev/null|wc -l|tr -d ' '))"
echo "     3) META_ANALISES      ($(ls "$CD_CLASSIFICADOS/META_ANALISES"/*.pdf 2>/dev/null|wc -l|tr -d ' '))"
echo "     4) GUIDELINES         ($(ls "$CD_CLASSIFICADOS/GUIDELINES"/*.pdf 2>/dev/null|wc -l|tr -d ' '))"
echo
read -r -p "   Escolha [1-4]: " Q
case "$Q" in
  1) PASTA="ARTIGOS_ORIGINAIS" ;;
  2) PASTA="REVISOES" ;;
  3) PASTA="META_ANALISES" ;;
  4) PASTA="GUIDELINES" ;;
  *) echo "   Opção inválida."; read -p "Enter. "; exit 1 ;;
esac

# ── a LISTA, para escolher em vez de pegar o primeiro da ordem alfabética ──
# (na REVISOES o primeiro é um '2014_07_.pdf', sem título nem revista no nome — a amostra
#  sairia ruim por motivo errado, não por causa da régua)
echo
echo "   ── QUAL ARTIGO? ──  (os mais recentes primeiro)"
IFS=$'\n' read -r -d '' -a LISTA < <(ls -1 "$CD_CLASSIFICADOS/$PASTA"/*.pdf 2>/dev/null | sort -r && printf '\0')
if [ ${#LISTA[@]} -eq 0 ]; then echo "   Pasta vazia."; read -p "Enter. "; exit 1; fi
i=1
for f in "${LISTA[@]:0:20}"; do
  printf "   %3d) %s\n" "$i" "$(basename "$f" .pdf | cut -c1-74)"
  i=$((i+1))
done
[ ${#LISTA[@]} -gt 20 ] && echo "        ... (+$(( ${#LISTA[@]} - 20 )) outros — digite 0 para pegar o 1º da fila)"
echo
read -r -p "   Número: " NUM
case "$NUM" in ''|*[!0-9]*) echo "   '$NUM' não é número."; read -p "Enter. "; exit 1 ;; esac

if [ "$NUM" -eq 0 ]; then
  FILTRO=""
  ALVO="(o primeiro da fila)"
else
  ARQ="${LISTA[$((NUM-1))]}"
  [ -z "$ARQ" ] && { echo "   Número fora da lista."; read -p "Enter. "; exit 1; }
  # um pedaço do nome que seja único: os 40 primeiros caracteres bastam
  FILTRO="--artigo=$(basename "$ARQ" .pdf | cut -c1-40)"
  ALVO="$(basename "$ARQ" .pdf | cut -c1-64)"
fi

echo
echo "   $ALVO"
echo "   Custo aproximado: US\$ 0.35"
echo "   Vai gerar: FATOS · perícia · PDF · ACRI · Visual Abstract · áudio"
echo "   (o que a porta da nota permitir — diretriz leva tudo; os outros dependem da nota)"
echo
read -r -p "   Rodar? [s/N]: " OK
case "$OK" in s|S|sim|SIM) ;; *) echo "   Cancelado. Nada foi gasto."; read -p "Enter. "; exit 0 ;; esac
echo

LOGDIR="$CD_FULL/outputs/LOGS"; mkdir -p "$LOGDIR"
DIARIO="$LOGDIR/chave15_$(date +%Y%m%d-%H%M).log"
set -o pipefail
python -u "$CD_FULL/src/rodar_em_blocos.py" "$CD_CLASSIFICADOS" 1 --max=1 \
       "--pasta=$PASTA" $FILTRO 2>&1 | tee "$DIARIO"
RC=${PIPESTATUS[0]}

echo | tee -a "$DIARIO"
if [ "$RC" -ne 0 ]; then
  echo "⛔ Terminou com falha (código $RC). O motivo está no fim do diário."
else
  echo "── O QUE CONFERIR AGORA ──"
  echo "  Abra outputs/STAGING/<nome do artigo>/ e olhe, nesta ordem:"
  echo
  echo "   _CANONICO.md   a NOTA, os domínios medidos e o motivo de cada teto."
  echo "                  Procure a linha do MCID: se o artigo não declarou limiar, tem de"
  echo "                  aparecer 'limiar CardioDaily' com o número que a casa aplicou."
  echo "   _analise.pdf   a perícia. Tabelas em estilo de revista, título dentro da tabela,"
  echo "                  coluna vazia podada COM a nota explicando o que saiu."
  echo "   _visual.png    o card. A NOTA NELE TEM DE SER A MESMA do canônico — era aqui que"
  echo "                  o modelo dava um número e o banco outro (consertado em 04/Ago)."
  echo "   _audio.mp3     o áudio (nota ≥8; diretriz sempre)."
  echo "   _ACRI.txt      as palavras-chave têm de estar EM PORTUGUÊS."
fi
echo
echo "  Diário: $DIARIO"
read -p "Enter para fechar. "
