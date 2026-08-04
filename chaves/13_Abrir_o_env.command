#!/bin/bash
# ═══ CHAVE 13 · ABRIR O .env ═══════════════════════════════════════════════
# O .env é OCULTO — o Finder não mostra e não dá para abrir com dois cliques.
# É onde moram as chaves de API e os ajustes que NÃO ficam no código (nem no git).
#
# Esta chave NÃO lê e NÃO mostra o conteúdo na tela: ela só abre o arquivo no TextEdit,
# faz uma cópia de segurança antes, e diz quais chaves existem (só os NOMES, nunca os valores).
# ═══════════════════════════════════════════════════════════════════════════
cd "$(dirname "$0")" && source ./config.sh
ENV="$CD_FULL/.env"

echo "═══════════════════════════════════════════════"
echo " CHAVE 13 · ABRIR O .env"
echo "═══════════════════════════════════════════════"
echo

if [ ! -f "$ENV" ]; then
  echo "  ⛔ Não existe .env em $CD_FULL"
  read -p "Enter para fechar. "; exit 1
fi

# cópia de segurança — mexer em chave de API sem rede de proteção não vale a pena
BKP="$ENV.backup-$(date +%Y%m%d-%H%M)"
cp "$ENV" "$BKP"
echo "  Cópia de segurança: $(basename "$BKP")"
echo

echo "  ── chaves que JÁ existem (só os nomes) ──"
grep -oE "^[A-Z_]+=" "$ENV" | sed 's/=$//' | sort | sed 's/^/     /'
echo

echo "  ── o que falta para o grok (04/Ago) ──"
grep -q "^XAI_API_KEY=" "$ENV" && echo "     ✔ XAI_API_KEY já está lá" || cat <<'FIM'
     Cole estas DUAS linhas no fim do arquivo:

       XAI_API_KEY=xai-...sua chave aqui...
       CD_M_GROK=grok-4.5

     A segunda existe porque o nome do modelo é um PALPITE. Se a Chave 12
     devolver erro 404 nele, troque só esta linha — sem mexer em código.
FIM
echo
echo "  Abrindo no TextEdit… salve com ⌘S e feche a janela."
echo "  Depois: Chave 12 (exame das cadeias) para provar que a chave funciona."
open -e "$ENV"
echo
read -p "Enter para fechar. "
