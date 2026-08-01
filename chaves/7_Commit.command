#!/bin/bash
# ═══ CHAVE 7 · COMMIT ═══════════════════════════════════════════════════════
# Grava no git o trabalho aprovado. Existe porque o ambiente do Claude não tem
# permissão para apagar arquivos na sua pasta — e o git precisa disso (index.lock).
# Mostra o que vai entrar ANTES de gravar, e pede confirmação.
# ═══════════════════════════════════════════════════════════════════════════
cd "$(dirname "$0")" && source ./config.sh
cd "$CD_FULL" || exit 1

echo "═══════════════════════════════════════════════"
echo " CHAVE 7 · COMMIT"
echo " Pasta:  $CD_FULL"
echo " Branch: $(git branch --show-current)"
echo "═══════════════════════════════════════════════"
echo

# trava esquecida por processo interrompido — o motivo de existir esta chave
[ -f .git/index.lock ] && rm -f .git/index.lock && echo "(trava antiga do git removida)" && echo

echo "── ARQUIVOS QUE VÃO ENTRAR ──"
git add -A
git status --short
echo
echo "── MENSAGEM (primeiras linhas) ──"
head -3 COMMIT_MSG.txt
echo "   [...] (mensagem completa em COMMIT_MSG.txt)"
echo
read -p "Confirma o commit? [s/N]: " OK
echo
if [ "$OK" != "s" ] && [ "$OK" != "S" ]; then
  echo "Cancelado. Nada foi gravado (os arquivos ficam preparados)."
  read -p "Enter para fechar. "; exit 0
fi

git commit -F COMMIT_MSG.txt && echo && git log --oneline -1
echo
echo "Para enviar ao GitHub:  git push"
echo "(o cron do Actions roda do main — se este trabalho tem que ir pra produção, precisa ir pro main)"
echo
read -p "Enter para fechar. "
