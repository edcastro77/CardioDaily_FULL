#!/bin/bash
# ═══ CHAVE 2 · ANALISADOR ═══  (analisa → notas → perícia/áudio → PUBLICA SOZINHO como rascunho)
#
# CONSERTOS DE 03/Ago (os três que o Dr. Eduardo mandou depois da auditoria das chaves):
#   · TRAVA DE SAÍDA — o minirevisao.py só roda se o analisador terminar BEM. Antes não havia
#     `set -e` nem checagem de código de saída: um Ctrl+C no analisador caía DIRETO na trilha da
#     minirevisão (mais 81 artigos pagos, sem perguntar). Era o "eu interrompi e ele não para".
#   · CONFIRMAÇÃO — mostra a fila e o custo estimado e pede [s/N] ANTES de gastar. As Chaves 7, 8
#     e 10 já perguntavam; as duas que gastam dinheiro de verdade (1 e 2) eram as que não.
#   · DIÁRIO — grava tudo em outputs/LOGS/. A Chave 1 já deixava CSV; esta só imprimia na janela,
#     e quando a janela fechava a prova do que aconteceu ia junto.
# ═══════════════════════════════════════════════════════════════════════════
cd "$(dirname "$0")" && source ./config.sh && source "$CD_VENV/bin/activate"

LOGDIR="$CD_FULL/outputs/LOGS"; mkdir -p "$LOGDIR"
DIARIO="$LOGDIR/chave2_$(date +%Y%m%d-%H%M).log"

echo "═══════════════════════════════════════"
echo " CHAVE 2 · ANALISADOR"
echo " Lendo classificados de: $CD_CLASSIFICADOS"
echo "═══════════════════════════════════════"
echo

# ── o que vai ser feito, e quanto custa, ANTES de gastar ──
N_TOT=0
for d in ARTIGOS_ORIGINAIS META_ANALISES GUIDELINES REVISOES EDITORIAIS; do
  n=$(ls "$CD_CLASSIFICADOS/$d"/*.pdf 2>/dev/null | wc -l | tr -d ' ')
  [ "$n" -gt 0 ] && printf "   %-20s %4s\n" "$d" "$n"
  N_TOT=$((N_TOT+n))
done
N_MINI=$(ls "$CD_CLASSIFICADOS/MINIRREVISOES"/*.pdf 2>/dev/null | wc -l | tr -d ' ')
echo "   ────────────────────────────"
printf "   %-20s %4s   → analisa e PUBLICA no Supabase (rascunho)\n" "fila do analisador" "$N_TOT"
printf "   %-20s %4s   → condutas + fluxograma, NÃO sobe no Supabase\n" "minirevisões" "$N_MINI"
echo
if [ "$N_TOT" -eq 0 ] && [ "$N_MINI" -eq 0 ]; then
  echo "   Fila vazia — nada a fazer. Rode a Chave 1 primeiro."
  read -p "Enter para fechar. "; exit 0
fi
echo "   Custo aproximado: US\$ $(awk "BEGIN{printf \"%.2f\", ($N_TOT*0.30)+($N_MINI*0.15)}")"
echo "   (blocos de 20: cada bloco vai pro Supabase antes do próximo — se a net cair, só o bloco refaz)"
echo "   Diário desta rodada: ${DIARIO/#$HOME/~}"
echo
read -r -p "   Começar? [s/N]: " OK
case "$OK" in s|S|sim|SIM) ;; *) echo "   Cancelado. Nada foi gasto."; read -p "Enter. "; exit 0 ;; esac
echo

# ── 1) o analisador, com o diário ligado ──
set -o pipefail
python "$CD_FULL/src/rodar_em_blocos.py" "$CD_CLASSIFICADOS" 20 2>&1 | tee -a "$DIARIO"
RC=${PIPESTATUS[0]}

# ── TRAVA DE SAÍDA: só continua se o analisador terminou bem ──
if [ "$RC" -eq 130 ]; then
  echo | tee -a "$DIARIO"
  echo "⛔ VOCÊ INTERROMPEU. A trilha da minirevisão NÃO vai rodar." | tee -a "$DIARIO"
  echo "   O que já publicou está salvo; o resto continua na fila. Clique a Chave 2 quando quiser." | tee -a "$DIARIO"
  echo "   Diário: $DIARIO"
  read -p "Enter para fechar. "; exit 130
fi
if [ "$RC" -ne 0 ]; then
  echo | tee -a "$DIARIO"
  echo "⛔ O ANALISADOR TERMINOU COM FALHA (código $RC)." | tee -a "$DIARIO"
  echo "   A trilha da minirevisão NÃO vai rodar — não faz sentido gastar mais com o lote quebrado." | tee -a "$DIARIO"
  echo "   Os artigos que falharam continuam na fila. A lista está no fim do diário:"
  echo "   $DIARIO"
  read -p "Enter para fechar. "; exit "$RC"
fi

# ── 2) trilha da minirevisão (só se a de cima passou) ──
if [ "$N_MINI" -gt 0 ]; then
  echo | tee -a "$DIARIO"
  echo "═══════════════════════════════════════" | tee -a "$DIARIO"
  echo " TRILHA MINIRREVISÃO / OPINIÃO DE ESPECIALISTA" | tee -a "$DIARIO"
  echo " Condutas práticas + fluxograma. NÃO sobe no Supabase (é standalone, como o Pesquisador)." | tee -a "$DIARIO"
  echo " Saída em: $CD_FULL/outputs/MINIRREVISOES/  ·  faixa 0 (vaselina) fica retida." | tee -a "$DIARIO"
  echo "═══════════════════════════════════════" | tee -a "$DIARIO"
  python "$CD_FULL/src/minirevisao.py" "$CD_CLASSIFICADOS/MINIRREVISOES" 2>&1 | tee -a "$DIARIO"
fi

echo
echo "✔ Publicado em blocos, como rascunho. Sobrou algo na fila (queda de rede)? Clique a Chave 2 de novo."
echo "  Minirevisões: condutas + fluxograma em outputs/MINIRREVISOES/ (não vão pro site)."
echo "  Curadoria (ver · ouvir · aprovar) → Chave 3 · Administrador."
echo "  Diário desta rodada: $DIARIO"
read -p "Enter para fechar. "
