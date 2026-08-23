#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════════
# CHAVE 25 — ENCHER O MeSH DAS LINHAS QUE SUBIRAM VAZIAS (22/Ago/2026)
#
# MEDIDO em 22/Ago: 208 de 704 linhas com `mesh_terms` vazio — e `mesh_terms` é
# por onde o PESQUISADOR acha material. Vazio, o artigo existe no banco e é
# invisível para quem procura.
#
# E não adianta esperar: numa amostra de 25 com DOI real, perguntando ao PubMed
# naquele instante, 0/25 já tinham MeSH. O indexador HUMANO da NLM leva de
# semanas a meses, e a fila enche justamente dos artigos MAIS NOVOS.
#
# Esta chave NÃO escreve no Supabase (LEI 5). Ela gera `saidas/MESH_LLM.sql`,
# e quem roda o SQL é você.
#
# CUSTO: ~US$ 0,0006 por artigo → os 208 saem por ~US$ 0,13.
# ═══════════════════════════════════════════════════════════════════════════════
cd "$(dirname "$0")" && source ./config.sh && source "$CD_VENV/bin/activate"
clear
cd "$CD_FULL"

echo "═══════════════════════════════════════════════════════════════════════════"
echo " CHAVE 25 · MeSH DOS VAZIOS"
echo " o modelo propõe, a NLM confere, o que não é descritor é DESCARTADO"
echo "═══════════════════════════════════════════════════════════════════════════"
echo
echo "   Enter    = rodar TODOS os vazios"
echo "   um número = rodar só os N primeiros (para conferir antes de gastar)"
echo "   c        = só CONFERIR o banco (grátis, não chama modelo, não escreve)"
echo
read -p "   Quantos? " N

# ═══ 22/Ago — A CONFERÊNCIA VIROU BOTÃO ═══
# Eu havia deixado a conferência como a última consulta do MESH_LLM.sql, contando que ele a
# lesse no SQL Editor. Ele perguntou: "esta última conferência que não sei como fazer?" — e a
# pergunta é justa. Conferência que depende do dono saber ler saída de SQL não é conferência:
# é mais uma coisa que fica sem ser feita. Foi assim que 208 linhas ficaram vazias sem ninguém
# ver. Agora é uma tecla, e responde em português.
if [ "$(echo "$N" | tr '[:upper:]' '[:lower:]' | tr -d '[:space:]')" = "c" ]; then
  echo
  python -u scripts/mesh_backfill.py --conferir
  echo
  read -p "Enter para fechar. "; exit 0
fi

# ⚠️ 22/Ago — A ENTRADA QUE NÃO É NÚMERO **PARA**, não segue.
# A primeira versão desta linha era `if é número; então limite; SENÃO roda tudo`. Ou seja:
# digitar "dez", ou "10 " com espaço sobrando, ou esbarrar numa tecla, mandava rodar os 208
# e gastar — quando a intenção era justamente a prova pequena. É o defeito da Chave 24 de
# 19/Ago com outra roupa: a interface lendo o engano como se fosse ordem, e calada.
# Enter é uma escolha explícita; qualquer outra coisa que não seja número é engano.
N_LIMPO=$(echo "$N" | tr -d '[:space:]')
if [ -z "$N_LIMPO" ]; then
  ARGS=""
  echo
  echo "   → TODOS os vazios. Leva ~40 min para 208 (a NLM é consultada termo a"
  echo "     termo, 3 por segundo, e o cache faz as rodadas seguintes acelerarem)."
elif [ "$N_LIMPO" -eq "$N_LIMPO" ] 2>/dev/null && [ "$N_LIMPO" -gt 0 ]; then
  ARGS="--limite $N_LIMPO"
  echo
  echo "   → prova com $N_LIMPO artigos."
else
  echo
  echo "⛔ CANCELADO — você digitou \"$N\", e eu esperava um NÚMERO ou Enter."
  echo "   Nada rodou e nada foi gasto. Abra a chave de novo."
  read -p "Enter para fechar. "; exit 0
fi
echo

# ⚠️ `python -u` (SEM BUFFER) — a mesma razão da Chave 2: sem isso a tela fica
# muda por minutos e parece travada, e quem está olhando aborta uma rodada que
# estava andando. Rodada abortada no meio é dinheiro pago sem SQL gerado.
#
# A RETOMADA é automática: o programa lê o próprio MESH_LLM.sql e pula quem já
# está lá. Isto existe porque em 20/Ago 49 artigos foram cobrados DUAS VEZES —
# o banco só muda quando você aplica o SQL, então uma segunda rodada encontrava
# exatamente os mesmos vazios e pagava tudo de novo.
python -u scripts/mesh_backfill.py $ARGS
RC=$?

echo
echo "───────────────────────────────────────────────────────────────────────────"
if [ "$RC" -ne 0 ]; then
  echo "⛔ PAROU. Leia a mensagem acima. Nada foi escrito no Supabase de qualquer forma."
  read -p "Enter para fechar. "; exit 1
fi

echo "PRÓXIMOS PASSOS — nesta ordem:"
echo
echo "  1) Abra o arquivo e confira alguns descritores:"
echo "       $CD_FULL/saidas/MESH_LLM.sql"
echo
echo "  2) Cole o arquivo INTEIRO no SQL Editor do Supabase e rode."
echo "     A primeira linha dele é o ALTER TABLE da coluna `mesh_origem` —"
echo "     ela é NOVA, e sem ela a CHAVE 2 se recusa a publicar (de propósito:"
echo "     coluna que só existe no código faria toda linha levar 400 mudo)."
echo
echo "  3) A última consulta do arquivo é a CONFERÊNCIA. `vazios` tem que dar ZERO."
echo
echo "  Depois disso, a CHAVE 2 volta ao normal."
read -p "Enter para fechar. "
