#!/bin/bash
# ═══ CHAVE 21 · ENVIAR ═══  (manda o que VOCÊ aprovou na Chave 3)
#
# ═══════════════════════════════════════════════════════════════════════════
# POR QUE ESTA CHAVE EXISTE, E POR QUE ELA RODA AQUI E NÃO NO GITHUB
# ═══════════════════════════════════════════════════════════════════════════
#
# Pergunta do Dr. Eduardo em 10/Ago: *"Então como eu posso enviar os artigos?"*
# A resposta era: não podia. Existia o workflow `artigos-diarios.yml`, disparo manual pelo
# site do GitHub — mas ele roda numa máquina da NUVEM, que só enxerga o que está COMMITADO.
#
# A Chave 3 grava `saidas/agenda_envio.csv` NO MAC DELE, e esse arquivo NÃO está rastreado
# no git (conferido: `git ls-files saidas/agenda_envio.csv` devolve zero). Ele aprovaria no
# painel, clicaria "Run workflow", e o runner leria um arquivo que não existe lá. Nada sairia,
# e o log diria "nada aprovado para hoje" — que é a mensagem CERTA para o motivo ERRADO.
#
# Por isso o envio roda na máquina dele, onde a agenda mora e o .env tem as credenciais.
# O venv da casa já tem `supabase` e `httpx` — conferido em 10/Ago.
#
# O QUE ELA MANDA: só o que está na fila da Chave 3 com a data de HOJE. Nada mais.
# Se a fila estiver vazia, ela não envia e diz por quê. (Decisão dele: "SÓ o que eu aprovei".)
# ═══════════════════════════════════════════════════════════════════════════
cd "$(dirname "$0")" && source ./config.sh && source "$CD_VENV/bin/activate"
cd "$CD_FULL"

AGENDA="$CD_FULL/saidas/agenda_envio.csv"
HOJE=$(date +%Y-%m-%d)

clear
echo "═══════════════════════════════════════════════"
echo " CHAVE 21 · ENVIAR"
echo " Só o que você aprovou na Chave 3 · $HOJE"
echo "═══════════════════════════════════════════════"
echo

if [ ! -f "$AGENDA" ]; then
  echo "   ⏸️  A agenda ainda não existe: ${AGENDA/#$HOME/~}"
  echo
  echo "   Abra a CHAVE 3 (Administrador), aprove os artigos e marque a data."
  echo "   É a aprovação que alimenta este envio — nada sai sem ela."
  echo
  read -p "Enter para fechar. "; exit 0
fi

# ── o que está marcado para HOJE ──
N=$(awk -F',' -v d="$HOJE" 'NR>1 && $1 ~ d && $4 != "" {n++} END{print n+0}' "$AGENDA")
echo "   ── FILA DE HOJE ($HOJE) ──"
if [ "$N" -eq 0 ]; then
  echo "   ⏸️  NADA aprovado para hoje."
  echo
  echo "   Datas que existem na agenda:"
  awk -F',' 'NR>1 && $1 != "" {print "      " $1}' "$AGENDA" | sort -u | tail -5
  echo
  echo "   Abra a Chave 3 e marque a data de hoje nos artigos que quer enviar."
  echo
  read -p "Enter para fechar. "; exit 0
fi
awk -F',' -v d="$HOJE" 'NR>1 && $1 ~ d && $4 != "" {printf "      • %s  (%s)\n", $2, $3}' "$AGENDA"
echo
echo "   $N artigo(s) · destino: o número do EDUARDO_PHONE no .env"
echo

# ── ENSAIO PRIMEIRO: mostra a mensagem sem mandar ──
echo "   1) ENSAIO   — monta a mensagem e mostra na tela, SEM enviar"
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
