#!/bin/bash
# ═══ CHAVE 6 · PROVA DO CLASSIFICADOR ═══════════════════════════════════════
# Roda o EXPERIMENTO: cada artigo julgado por vários modelos, várias vezes,
# e o placar contra o gabarito do Dr. Eduardo.
#
# NÃO move arquivo · NÃO renomeia · NÃO fala com o Supabase. Só lê PDF e grava CSV.
# É retomável: se cair, clica de novo — o que já foi pago não é refeito.
# ═══════════════════════════════════════════════════════════════════════════
cd "$(dirname "$0")" && source ./config.sh && source "$CD_VENV/bin/activate"
cd "$CD_FULL" || exit 1

echo "═══════════════════════════════════════════════"
echo " CHAVE 6 · PROVA DO CLASSIFICADOR"
echo "═══════════════════════════════════════════════"

# o venv não tinha openpyxl (31/07): o placar já cai no gabarito.csv sozinho, mas com a
# biblioteca ele lê o .xlsx direto — instala em silêncio na primeira vez e nunca mais.
python3 -c "import openpyxl" 2>/dev/null || pip install -q openpyxl 2>/dev/null
echo
echo "  1) SÓ O LUNA, 1 rodada — todos os artigos   (~US\$ 0,09, uns 3 min)   ← o teste do prompt"
echo "  2) PILOTO — 12 artigos, 3 modelos, 3 rodadas (~US\$ 0,20)"
echo "  3) COMPLETA — todos, 3 modelos, 3 rodadas    (~US\$ 6,00, uns 25 min)"
echo "  4) SÓ O PLACAR — não gasta nada, relê o que já foi rodado"
echo
read -p "  Escolha [1/2/3/4]: " ESCOLHA
echo

case "$ESCOLHA" in
  1) python3 -u src/prova_classificador.py --modelos gpt-5.6-luna --rodadas 1 ;;
  2) python3 -u src/prova_classificador.py --max 12 --rodadas 3 ;;
  3) python3 -u src/prova_classificador.py --rodadas 3 ;;
  4) echo "(pulando a rodada — só o placar)" ;;
  *) echo "Opção inválida. Nada foi feito."; read -p "Enter para fechar. "; exit 1 ;;
esac

echo
python3 -u src/placar.py
echo
read -p "Enter para fechar. "
