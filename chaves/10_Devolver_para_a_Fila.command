#!/bin/bash
# ═══ CHAVE 10 · DEVOLVER PARA A FILA ═══════════════════════════════════════
# Tira os PDFs das pastas de CLASSIFICADOS/ e devolve para a RAIZ de ARTIGOS/,
# que é a única coisa que a Chave 1 enxerga.
#
# POR QUE EXISTE: reclassificar exige que os PDFs voltem para a fila, e isso estava sendo feito
# à mão, por comando colado no Terminal — três vezes em 02/Ago, e uma delas não rodou (a Chave 1
# não achou nada e o Dr. Eduardo perdeu a volta).
#
# NÃO MEXE em _PUBLICADOS nem em _RECUSADOS sem você pedir: aqueles já foram ao Supabase ou
# foram recusados na curadoria, e trazê-los de volta é decisão editorial, não faxina.
# NÃO DELETA NADA. Só move.
# ═══════════════════════════════════════════════════════════════════════════
cd "$(dirname "$0")" && source ./config.sh
cd "$CD_INBOX" || exit 1

conta() { ls "$1"/*.pdf 2>/dev/null | wc -l | tr -d ' '; }

echo "═══════════════════════════════════════════════"
echo " CHAVE 10 · DEVOLVER PARA A FILA"
echo "═══════════════════════════════════════════════"
echo
echo "  Pasta: $CD_INBOX"
echo "  Na raiz agora (a Chave 1 só lê isto): $(conta .) PDF"
echo
echo "  ── na fila de trabalho ──"
VIVOS=0
for d in ARTIGOS_ORIGINAIS META_ANALISES GUIDELINES REVISOES MINIRREVISOES EDITORIAIS; do
  n=$(conta "CLASSIFICADOS/$d"); VIVOS=$((VIVOS+n))
  [ "$n" -gt 0 ] && printf "     %-20s %s\n" "$d" "$n"
done
NREV=$(conta "REVISAO_HUMANA"); VIVOS=$((VIVOS+NREV))
[ "$NREV" -gt 0 ] && printf "     %-20s %s\n" "REVISAO_HUMANA" "$NREV"
echo "     ────────────────────────────"
printf "     %-20s %s\n" "TOTAL" "$VIVOS"
echo
echo "  ── NÃO serão tocados (decisão editorial sua) ──"
printf "     %-20s %s\n" "_PUBLICADOS" "$(conta CLASSIFICADOS/_PUBLICADOS)"
printf "     %-20s %s\n" "_RECUSADOS" "$(conta CLASSIFICADOS/_RECUSADOS)"
printf "     %-20s %s\n" "DUPLICATAS" "$(conta DUPLICATAS)"
echo

if [ "$VIVOS" -eq 0 ]; then
  echo "  Nada para devolver — a fila já está na raiz."
  read -p "Enter para fechar. "; exit 0
fi

read -r -p "  Devolver estes $VIVOS PDF para a raiz? [s/N]: " OK
case "$OK" in s|S|sim|SIM) ;; *) echo "  Cancelado."; read -p "Enter. "; exit 0 ;; esac

for d in ARTIGOS_ORIGINAIS META_ANALISES GUIDELINES REVISOES MINIRREVISOES EDITORIAIS; do
  mv "CLASSIFICADOS/$d"/*.pdf . 2>/dev/null
done
mv REVISAO_HUMANA/*.pdf . 2>/dev/null

echo
echo "  ✔ Na raiz agora: $(conta .) PDF — prontos para a Chave 1."
echo
read -p "Enter para fechar. "
