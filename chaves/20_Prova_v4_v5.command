#!/bin/bash
# ═══ CHAVE 20 · PROVA v4 × v5 ═══
#
# Os dois prompts de classificação, o MESMO texto, o MESMO modelo, contra o gabarito de 111
# artigos que o Dr. Eduardo conferiu à mão em 31/Jul.
#
# POR QUE EXISTE: em 10/Ago ele abriu 13 PDFs e mostrou dois erros que o v3/v4 não tinha como
# evitar — "Gastroparesis: A Review" e "Alcohol-Related Liver Disease: A Review" (JAMA) foram
# para a pasta de META-ANÁLISE, com confiança ALTA, citando "We conducted a PubMed search"
# como prova. Palavras dele: *"não adianta remendar o v3 — sem peso e sem métrica, nós erramos
# ao construir o v3."*
#
# O v5 muda a ARQUITETURA: o LLM RELATA sinais, o CÓDIGO decide (a mesma ideia da LEI 0, onde
# o motor de rigor é determinístico sobre FATOS). Esta chave mede se isso vale.
#
# NÃO move arquivo. NÃO fala com o Supabase. NÃO escreve no plano de voo (silenciado).
# ═══════════════════════════════════════════════════════════════════════════
cd "$(dirname "$0")" && source ./config.sh && source "$CD_VENV/bin/activate"
cd "$CD_FULL"

clear
echo "═══════════════════════════════════════════════"
echo " CHAVE 20 · PROVA v4 × v5  (classificador)"
echo "═══════════════════════════════════════════════"
echo
python3 src/prova_v4_v5.py --dry-run
echo
echo "   ── OU só RECALCULAR o placar, de graça ──"
echo "   As 420 respostas do modelo já estão gravadas. Quando você julga um artigo de novo"
echo "   (planilha GABARITO_16_para_julgar), o placar se refaz contra a régua NOVA sem"
echo "   chamar modelo nenhum. Custo zero."
echo
echo "   O que vai ser medido:"
echo "     · ACURÁCIA de cada versão contra o gabarito"
echo "     · REPETIBILIDADE — a mesma pergunta 2×  (em 10/Ago o MESMO artigo saiu"
echo "       revisao_geral numa rodada e meta-análise na outra, as duas com confiança alta)"
echo "     · ERROS GRAVES — os que trocam o MOTOR e portanto a NOTA (LEI 8)"
echo "     · POR SINAL (só v5) — quando erra, QUAL sinal falhou"
echo
echo "   1) só RECALCULAR o placar com o gabarito atual   (US$ 0,00)"
echo "   2) RODAR a prova de novo                          (gasta o valor acima)"
echo
read -r -p "   Escolha [1-2, Enter = 1]: " E
echo
if [ "$E" = "2" ]; then
  python3 src/prova_v4_v5.py
else
  python3 src/prova_v4_v5.py --placar
fi
echo
echo "   Retoma de onde parou se a rede cair — é só clicar de novo."
echo "   Só o placar, sem gastar:  python3 src/prova_v4_v5.py --placar"
echo
read -p "Enter para fechar. "
