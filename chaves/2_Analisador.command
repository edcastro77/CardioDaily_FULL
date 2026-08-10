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
# ── 06/Ago: A TELA MOSTRAVA DUAS ORDENS DIFERENTES ──
# A contagem do topo listava ARTIGOS_ORIGINAIS·META·GUIDELINES·REVISOES; o menu logo abaixo
# numerava 1)META 2)GUIDELINES 3)REVISOES 4)ARTIGOS_ORIGINAIS. O Dr. Eduardo leu a contagem,
# contou até REVISOES, digitou 4 — e o 4 era ARTIGOS_ORIGINAIS: 255 artigos, US$ 76,50.
# Duas ordens na mesma tela é a versão de interface do "duas fontes de verdade" da LEI 9.
# Agora existe UMA lista, com UM número por pasta — o mesmo que se digita.
N_TOT=0
for d in ARTIGOS_ORIGINAIS META_ANALISES GUIDELINES REVISOES EDITORIAIS; do
  n=$(ls "$CD_CLASSIFICADOS/$d"/*.pdf 2>/dev/null | wc -l | tr -d ' ')
  N_TOT=$((N_TOT+n))
done
N_MINI=$(ls "$CD_CLASSIFICADOS/MINIRREVISOES"/*.pdf 2>/dev/null | wc -l | tr -d ' ')
if [ "$N_TOT" -eq 0 ] && [ "$N_MINI" -eq 0 ]; then
  echo "   Fila vazia — nada a fazer. Rode a Chave 1 primeiro."
  read -p "Enter para fechar. "; exit 0
fi
# ── QUAL PASTA (04/Ago) ──
# Pergunta do Dr. Eduardo: "não combinamos que ia ler pasta por pasta?". Ia, e vai — cada PDF carrega
# o caminho dele e é a pasta que decide prompt e motor (LEI 8). Mas rodar TUDO de uma vez significa
# gastar ~US$ 77 nos 256 artigos originais ANTES de o código mais novo (o da meta, escrito hoje) ser
# tocado uma única vez. O risco novo tem de ser testado primeiro, e ele é o mais barato de testar.
n_meta=$(ls "$CD_CLASSIFICADOS/META_ANALISES"/*.pdf     2>/dev/null|wc -l|tr -d ' ')
n_guia=$(ls "$CD_CLASSIFICADOS/GUIDELINES"/*.pdf        2>/dev/null|wc -l|tr -d ' ')
n_revi=$(ls "$CD_CLASSIFICADOS/REVISOES"/*.pdf          2>/dev/null|wc -l|tr -d ' ')
n_orig=$(ls "$CD_CLASSIFICADOS/ARTIGOS_ORIGINAIS"/*.pdf 2>/dev/null|wc -l|tr -d ' ')
# ═══ O CUSTO POR ARTIGO SAI DO REGISTRO, NÃO DO MEU CHUTE (09/Ago/2026) ═══
# Esta tela dizia US$ 0,30 por artigo desde que foi escrita — um número que eu inventei e
# chumbei aqui. Em 09/Ago li o `outputs/uso.jsonl` pela primeira vez (3.767 chamadas gravadas
# desde 27/Jul, nunca lidas) e o real, na configuração de hoje, é US$ 0,199. A tela mentia
# 55 % PARA CIMA — e é com ela que o Dr. Eduardo decide se roda a fila ou se espera.
# Agora o número vem de `custo.py --por-artigo`, que lê os últimos 7 dias medidos.
# Se o registro estiver vazio ou o python falhar, cai nos 30 centavos antigos: uma tela que
# não abre é pior que uma tela conservadora.
CENT_ART=$(cd "$CD_FULL" && python3 src/custo.py --por-artigo 2>/dev/null \
           | awk '{printf "%d", $1*100}')
case "$CENT_ART" in ''|*[!0-9]*) CENT_ART=30; FONTE_CUSTO="estimado (registro vazio)";; \
                    *) FONTE_CUSTO="MEDIDO nos últimos 7 dias";; esac
[ "$CENT_ART" -lt 1 ] && { CENT_ART=30; FONTE_CUSTO="estimado (registro vazio)"; }

echo "   ── A FILA · digite o número da linha ──"
printf "     1) META_ANALISES     %4s   US\$ %d   motor da Escada\n"           "$n_meta" $((n_meta*CENT_ART/100))
printf "     2) GUIDELINES        %4s   US\$ %d   motor AGREE (sobe em qualquer nota)\n" "$n_guia" $((n_guia*CENT_ART/100))
printf "     3) REVISOES          %4s   US\$ %d   motor da revisão narrativa\n" "$n_revi" $((n_revi*CENT_ART/100))
printf "     4) ARTIGOS_ORIGINAIS %4s   US\$ %d   o mais caro\n"               "$n_orig" $((n_orig*CENT_ART/100))
printf "     5) TUDO              %4s   US\$ %d   nesta ordem\n"               "$N_TOT"  $((N_TOT*CENT_ART/100))
echo
printf "     (custo/artigo: US\$ 0,%02d — %s · Chave 19 mostra a conta)\n" "$CENT_ART" "$FONTE_CUSTO"
echo
printf "     (minirevisões: %s — condutas + fluxograma, NÃO sobem no Supabase)\n" "$N_MINI"
echo
read -r -p "   Escolha [1-5]: " ESCOLHA
case "$ESCOLHA" in
  1) PASTA="--pasta=META_ANALISES";     NP=$(ls "$CD_CLASSIFICADOS/META_ANALISES"/*.pdf 2>/dev/null|wc -l|tr -d ' ') ;;
  2) PASTA="--pasta=GUIDELINES";        NP=$(ls "$CD_CLASSIFICADOS/GUIDELINES"/*.pdf 2>/dev/null|wc -l|tr -d ' ') ;;
  3) PASTA="--pasta=REVISOES";          NP=$(ls "$CD_CLASSIFICADOS/REVISOES"/*.pdf 2>/dev/null|wc -l|tr -d ' ') ;;
  4) PASTA="--pasta=ARTIGOS_ORIGINAIS"; NP=$(ls "$CD_CLASSIFICADOS/ARTIGOS_ORIGINAIS"/*.pdf 2>/dev/null|wc -l|tr -d ' ') ;;
  5) PASTA="";                          NP=$N_TOT ;;
  *) echo "   Opção inválida. Nada foi feito."; read -p "Enter. "; exit 1 ;;
esac
echo
CENT=$((NP * CENT_ART))
printf "   %s artigo(s) · custo aproximado US\$ %d.%02d   (%s)\n" \
       "$NP" $((CENT/100)) $((CENT%100)) "$FONTE_CUSTO"
echo "   RAMPA DE CONFIANÇA: começa em blocos de 10 · 3 blocos sem falha → 20 · mais 3 → 30"
echo "   (qualquer falha volta para 10 e o contador zera · o bloco nunca atravessa a divisa entre pastas)"
echo "   Diário desta rodada: ${DIARIO/#$HOME/~}"
echo
read -r -p "   Começar? [s/N]: " OK
case "$OK" in s|S|sim|SIM) ;; *) echo "   Cancelado. Nada foi gasto."; read -p "Enter. "; exit 0 ;; esac
echo

# ── 1) o analisador, com o diário ligado ──
set -o pipefail
# ⚠️ `python -u` (SEM BUFFER) — 04/Ago/2026, e a razão está escrita porque eu errei três vezes:
#    Quando o Python vê que a saída vai para um CANO (o `tee` do diário) e não para a tela, ele muda
#    de "solta linha por linha" para "acumula 4–8 KB e solta de uma vez". O Dr. Eduardo ficou olhando
#    uma janela PARADA enquanto o sistema analisava meta-análises normalmente, e o diário ficou com
#    0 bytes. Na Chave 11 eu já tinha resolvido isso com flush=True e NÃO varri as outras — o mesmo
#    erro da LEI 9, cometido por mim, contra mim. O `-u` resolve para todas de uma vez.
python -u "$CD_FULL/src/rodar_em_blocos.py" "$CD_CLASSIFICADOS" --rampa $PASTA 2>&1 | tee -a "$DIARIO"
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
if [ "$N_MINI" -gt 0 ] && [ -z "$PASTA" ]; then   # só na opção TUDO
  echo | tee -a "$DIARIO"
  echo "═══════════════════════════════════════" | tee -a "$DIARIO"
  echo " TRILHA MINIRREVISÃO / OPINIÃO DE ESPECIALISTA" | tee -a "$DIARIO"
  echo " Condutas práticas + fluxograma. NÃO sobe no Supabase (é standalone, como o Pesquisador)." | tee -a "$DIARIO"
  echo " Saída em: $CD_FULL/outputs/MINIRREVISOES/  ·  faixa 0 (vaselina) fica retida." | tee -a "$DIARIO"
  echo "═══════════════════════════════════════" | tee -a "$DIARIO"
  python -u "$CD_FULL/src/minirevisao.py" "$CD_CLASSIFICADOS/MINIRREVISOES" 2>&1 | tee -a "$DIARIO"
fi

echo
# ⚠️ 04/Ago — ESTA LINHA MENTIA. Dizia "✔ Publicado em blocos" SEMPRE, mesmo quando o placar
# real da rodada era `publicados 0 · recusados 10`. O Dr. Eduardo leu o ✔ verde numa rodada em
# que NADA subiu ao Supabase — e só descobriu quando mandou eu conferir o banco.
# Um ✔ que aparece independentemente do resultado não é informação: é decoração que engana.
# Agora quem fala é o placar do próprio analisador (impresso acima, e no diário).
echo "── FIM DA RODADA ──"
echo "  O placar verdadeiro está logo acima e no diário: publicados · retidos · falharam."
echo "  RETIDO não é erro: é o portão recusando linha incompleta (o site não recebe buraco)."
echo "  O motivo de cada retenção está no _REVISAR_publicacao.txt dentro da pasta do artigo."
echo "  Sobrou algo na fila (queda de rede)? Clique a Chave 2 de novo — ela reaproveita o pronto."
echo "  Minirevisões: condutas + fluxograma em outputs/MINIRREVISOES/ (não vão pro site)."
echo "  Curadoria (ver · ouvir · aprovar) → Chave 3 · Administrador."
echo "  Diário desta rodada: $DIARIO"
read -p "Enter para fechar. "
