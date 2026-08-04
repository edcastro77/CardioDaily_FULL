#!/bin/bash
# ═══ CHAVE 11 · PROVA DA EXTRAÇÃO ══════════════════════════════════════════
# Mede a ETAPA QUE DECIDE TUDO e que nunca tinha sido medida.
#
# Em 01/Ago você mediu o REDATOR — 5 documentos, 4 modelos, tabelas, lacunas, tokens. O terra ganhou.
# Mas o redator ESCREVE. Quem JULGA é a EXTRAÇÃO, e ela nunca foi comparada com ninguém.
#
#     PDF ──[extração]──> FATOS ──[motor]──> NOTA ──> publica? visual? áudio?
#                                              └────> entra DENTRO do prompt do redator
#
# Se a extração lê errado, artigo bom leva 5 e some sem ninguém ver. Na sua última rodada:
# 122 analisados, 75 recusados. Isso pode ser o sistema funcionando — ou não. Ninguém mediu.
#
# COMO: o mesmo PDF é lido por 3 modelos; cada leitura passa pelo MESMO motor determinístico.
# O motor é a régua comum. Se as três notas batem, a extração é robusta. Se divergem, a decisão
# do CardioDaily depende de qual servidor atendeu.
#
# NÃO move arquivo · NÃO publica · NÃO fala com o Supabase.
# ═══════════════════════════════════════════════════════════════════════════
cd "$(dirname "$0")" && source ./config.sh && source "$CD_VENV/bin/activate"
cd "$CD_FULL" || exit 1

echo "═══════════════════════════════════════════════"
echo " CHAVE 11 · PROVA DA EXTRAÇÃO"
echo "═══════════════════════════════════════════════"
echo
echo "  Escolha os artigos: um de cada TIPO, e que você conheça bem."
echo "  (o tipo vem da pasta do classificador — arraste de dentro de CLASSIFICADOS/)"
echo
echo "  Arraste os PDFs para esta janela, separados por espaço, e tecle Enter."
echo "  Ou tecle Enter vazio para escolher da lista."
echo
read -r -p "  PDFs: " ALVOS

if [ -z "$ALVOS" ]; then
  echo
  echo "── PDFs classificados ──"
  IFS=$'\n' read -r -d '' -a LISTA < <(find "$CD_CLASSIFICADOS" -maxdepth 2 -name "*.pdf" \
      ! -name "._*" ! -path "*_PUBLICADOS*" ! -path "*_RECUSADOS*" | sort && printf '\0')
  if [ ${#LISTA[@]} -eq 0 ]; then echo "  (nenhum PDF)"; read -p "Enter. "; exit 1; fi
  i=1
  for f in "${LISTA[@]}"; do
    printf "  %3d) %-18s %s\n" "$i" "$(basename "$(dirname "$f")")" "$(basename "$f" | cut -c1-56)"
    i=$((i+1))
  done
  echo
  echo "  Digite os NÚMEROS separados por espaço (ex.: 4 19 88 140)"
  read -r -p "  Números: " NUMS
  ALVOS=""
  for n in $NUMS; do
    case "$n" in ''|*[!0-9]*) echo "  '$n' não é número — ignorado."; continue ;; esac
    f="${LISTA[$((n-1))]}"
    [ -n "$f" ] && ALVOS="$ALVOS \"$f\""
  done
fi

[ -z "$ALVOS" ] && { echo "  Nada escolhido."; read -p "Enter. "; exit 1; }

# conta quantos e estima o custo antes de gastar
N=$(eval "for f in $ALVOS; do echo \$f; done" | grep -c '\.pdf$')
echo
echo "  $N artigo(s) × 3 modelos (sonnet-5 · gpt-5.6-terra · gemini-3.1-pro) = $((N*3)) chamadas"
echo "  Custo aproximado: US\$ $(awk "BEGIN{printf \"%.2f\", $N*0.30}")"
echo "  (só a LEITURA do PDF — não gera perícia, não gera áudio, não gera visual)"
echo
read -r -p "  Rodar? [s/N]: " OK
case "$OK" in s|S|sim|SIM) ;; *) echo "  Cancelado. Nada foi gasto."; read -p "Enter. "; exit 0 ;; esac
echo

eval "python3 src/prova_extracao.py $ALVOS"

echo
echo "  O relatório em outputs/PROVA/ tem uma coluna vazia — 'quem acertou?'."
echo "  Só você pode preencher: quem sabe qual fato está no PDF é o cardiologista."
echo
read -p "Enter para fechar. "
