#!/bin/bash
# ═══ CHAVE 21 · ENVIAR AGORA ═══  (fora do horário automático das 07:00)
#
# ═══════════════════════════════════════════════════════════════════════════
# 14/Ago/2026 — ESTA CHAVE MUDOU DE PAPEL
#
# Ela nasceu em 10/Ago porque o envio NÃO podia rodar na nuvem: a agenda morava em
# `saidas/agenda_envio.csv`, no Mac dele, e o runner do GitHub não enxerga esse disco.
# Ele aprovaria no painel, clicaria "Run workflow", e o log diria "nada aprovado para hoje"
# — a mensagem CERTA para o motivo ERRADO.
#
# Em 14/Ago ele perguntou: *"por que o sistema não usa o mesmo do radar, que envia todos os
# dias independente de como meu computador estiver ligado ou não?"* A agenda foi para o
# Supabase, e o obstáculo — que era um arquivo — deixou de existir. O envio agora roda às
# 07:00 pela nuvem, como o Radar.
#
# ENTÃO PARA QUE ELA SERVE AGORA: para enviar FORA DE HORA. Ele aprova algo às 15h e não
# quer esperar amanhã. Não é mais "o jeito de enviar" — é o atalho.
#
# O QUE ELA MANDA: só o que está na fila da Chave 3 para HOJE **e ainda não saiu**. Se o
# cron das 07:00 já mandou, a consulta devolve vazio e nada é repetido.
# ═══════════════════════════════════════════════════════════════════════════
cd "$(dirname "$0")" && source ./config.sh && source "$CD_VENV/bin/activate"
cd "$CD_FULL"

# ═══ 14/Ago/2026 — A AGENDA SAIU DO DISCO E FOI PARA O SUPABASE ═══
#
# Esta chave lia `saidas/agenda_envio.csv` para mostrar a fila antes de enviar. O arquivo
# não é mais a fonte: a Chave 3 grava na tabela `agenda_envio`, e o cron das 07:00 lê de lá.
# Ler o CSV aqui seria uma SEGUNDA agenda — o defeito que custou os dias 09, 10 e 11.
#
# E o papel desta chave mudou: o envio agora acontece SOZINHO às 07:00, pela nuvem. Ela
# deixou de ser "o jeito de enviar" e virou "enviar AGORA, fora do horário" — quando ele
# aprova algo no meio do dia e não quer esperar amanhã.
#
# Quem mostra a fila é o próprio distribuidor, em ENSAIO: uma fonte só, a mesma que envia.
HOJE=$(date +%Y-%m-%d)

clear
echo "═══════════════════════════════════════════════"
echo " CHAVE 21 · ENVIAR AGORA"
echo " O automático já roda às 07:00 — isto é fora de hora"
echo " $HOJE"
echo "═══════════════════════════════════════════════"
echo
echo "   A fila vive no Supabase (tabela agenda_envio), gravada pela Chave 3."
echo "   O que já saiu hoje NÃO sai de novo — a coluna enviado_em segura."
echo

# ── ENSAIO PRIMEIRO: mostra a mensagem sem mandar ──
echo "   1) VER A FILA — mostra o que sairia agora, SEM enviar"
echo "   2) ENVIAR   — manda de verdade no WhatsApp"
echo "   3) ENVIAR sem verificar a Z-API"
echo "      (use se a verificação der timeout mas você SABE que está conectado —"
echo "       por exemplo, o Radar chegou hoje. Em 11/Ago um timeout de 10s abortou"
echo "       um envio com a instância perfeitamente conectada.)"
echo "   4) DIAGNOSTICAR — por que a mensagem não chegou (não envia nada)"
echo
read -r -p "   Escolha [1-4, Enter = 1]: " E
echo
if [ "$E" = "2" ] || [ "$E" = "3" ]; then
  echo "   ⚠️  Vai enviar de verdade. Confirma? [s/N]"
  read -r -p "   > " OK
  case "$OK" in s|S|sim|SIM) ;; *) echo "   Cancelado. Nada foi enviado."; read -p "Enter. "; exit 0 ;; esac
  echo
  if [ "$E" = "3" ]; then
    CD_PULAR_CHECK_ZAPI=1 python3 distribuidor.py artigos
  else
    python3 distribuidor.py artigos
  fi
elif [ "$E" = "4" ]; then
  python3 src/testar_zapi.py
else
  python3 distribuidor.py artigos --dry-run
fi

echo
echo "   O que saiu daqui fica no plano de voo. Chave 18 mostra."
echo
read -p "Enter para fechar. "
