#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════════
# CHAVE 24 — DEVOLVER À FILA O QUE A RÉGUA VELHA REPROVOU (19/Ago/2026)
#
# Roda em DOIS tempos: primeiro o ENSAIO (mostra tudo, não toca em nada), e só
# executa se você digitar SIM. Nenhuma chamada de LLM, nenhuma linha no Supabase.
# Depois desta chave, rode a CHAVE 2 — é ela que analisa e publica (LEI 5).
# ═══════════════════════════════════════════════════════════════════════════════
cd "$(dirname "$0")" && source ./config.sh && source "$CD_VENV/bin/activate"
clear
cd "$CD_FULL"

python3 scripts/reavaliar_regua_19ago.py
RC=$?
if [ "$RC" -ne 0 ]; then
  echo
  echo "⛔ O ENSAIO PAROU. Nada foi tocado. Leia a mensagem acima antes de seguir."
  read -p "Enter para fechar. "; exit 1
fi

echo
echo "───────────────────────────────────────────────────────────────────────────"
read -p "Executar de verdade? [s/N]: " R
# ⚠️ 19/Ago — AQUI EU PEDIA "SIM" EM MAIÚSCULO, COM COMPARAÇÃO EXATA.
# Todas as outras chaves do projeto perguntam `[s/N]`. O Dr. Eduardo digitou o que digita
# sempre, a chave leu como CANCELAR, e não disse por quê — ele foi direto para a Chave 2 e
# encontrou a fila vazia, sem nenhuma pista de que o passo anterior não tinha rodado.
# É a Chave 2 de 06/Ago outra vez (a contagem numa ordem e o menu em outra): a interface
# fazendo a ação CERTA parecer a errada, e o silêncio escondendo qual foi.
# Agora aceita o que qualquer um digitaria, em qualquer caixa — e, se cancelar, DIZ que
# cancelou e o que ele digitou.
R_LIMPO=$(echo "$R" | tr '[:upper:]' '[:lower:]' | tr -d '[:space:]')
case "$R_LIMPO" in
  s|si|sim|y|yes|ok) ;;
  *)
    echo
    echo "⛔ CANCELADO — você digitou \"$R\", e eu esperava sim / s."
    echo "   NADA foi tocado: os PDFs continuam em _RECUSADOS e a fila da Chave 2 segue vazia."
    read -p "Enter para fechar. "; exit 0 ;;
esac

echo
python3 scripts/reavaliar_regua_19ago.py --executar
echo
echo "───────────────────────────────────────────────────────────────────────────"
echo "PRÓXIMO PASSO: CHAVE 2 (Analisador)."
echo "  · os FATOS são reaproveitados — só os 5 da lista re-extraem"
echo "  · perícia, ACRI, Visual Abstract e áudio são refeitos com a nota NOVA"
read -p "Enter para fechar. "
