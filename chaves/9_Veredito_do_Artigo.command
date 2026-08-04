#!/bin/bash
# ═══ CHAVE 9 · VEREDITO DO ARTIGO ══════════════════════════════════════════
# Dá a nota REAL de um PDF — a do motor determinístico, a mesma que roda em produção —
# para colar no comparativo em vez de inventar.
#
# Existe porque a trava do veredito (01/Ago) impede rodar com o campo vazio, e inventar
# a nota tem um risco: ela pode ANCORAR o tom da perícia. Nota inventada não fica só no
# número — pode deixar a crítica mais branda ou mais dura sem ninguém perceber.
#
# Custa ~US$ 0,02 por artigo (1 chamada de extração). Não move arquivo, não publica nada.
# ═══════════════════════════════════════════════════════════════════════════
cd "$(dirname "$0")" && source ./config.sh && source "$CD_VENV/bin/activate"
cd "$CD_FULL" || exit 1

echo "═══════════════════════════════════════════════"
echo " CHAVE 9 · VEREDITO DO ARTIGO"
echo "═══════════════════════════════════════════════"
echo
echo "  Arraste o PDF para esta janela e tecle Enter."
echo "  (ou tecle Enter vazio para escolher da lista)"
echo
read -r -p "  PDF: " ALVO

# limpa o que o Finder cola junto: aspas, barra invertida de escape, espaços nas pontas
ALVO="${ALVO%\"}"; ALVO="${ALVO#\"}"; ALVO="${ALVO%\'}"; ALVO="${ALVO#\'}"
ALVO="$(echo "$ALVO" | sed 's/\\ / /g' | sed 's/[[:space:]]*$//;s/^[[:space:]]*//')"

if [ -z "$ALVO" ]; then
  echo
  echo "── PDFs classificados ──"
  IFS=$'\n' read -r -d '' -a LISTA < <(find "$CD_CLASSIFICADOS" -maxdepth 2 -name "*.pdf" \
      ! -name "._*" ! -path "*_PUBLICADOS*" ! -path "*_RECUSADOS*" | sort && printf '\0')
  if [ ${#LISTA[@]} -eq 0 ]; then echo "  (nenhum PDF)"; read -p "Enter. "; exit 1; fi
  i=1
  for f in "${LISTA[@]}"; do
    printf "  %3d) %-22s %s\n" "$i" "$(basename "$(dirname "$f")")" "$(basename "$f" | cut -c1-58)"
    i=$((i+1))
  done
  echo
  read -r -p "  Número: " N
  case "$N" in ''|*[!0-9]*) echo "Número inválido."; read -p "Enter. "; exit 1 ;; esac
  ALVO="${LISTA[$((N-1))]}"
  [ -z "$ALVO" ] && { echo "Fora da lista."; read -p "Enter. "; exit 1; }
fi

if [ ! -f "$ALVO" ]; then
  echo; echo "⛔ Não achei o arquivo:"; echo "   $ALVO"
  read -p "Enter para fechar. "; exit 1
fi

# ─── O TIPO (LEI 8) ───
# O tipo decide TUDO: extrator, motor e prompt. Em produção quem decide é o CLASSIFICADOR, e a pasta
# é o registro dessa decisão. Num PDF arrastado de qualquer lugar do disco NÃO EXISTE essa decisão —
# então quem decide é o Dr. Eduardo. O programa não adivinha: adivinhar seria uma TERCEIRA fonte de
# verdade, que é o que a LEI 8 proíbe. (02/Ago: uma diretriz da SBC vinda de Downloads caiu no
# extrator de artigo original e saiu "SEM NOTA". O motor não errou — nunca chegou a rodar.)
PASTA_ALVO="$(basename "$(dirname "$ALVO")")"
case "$PASTA_ALVO" in
  ARTIGOS_ORIGINAIS|META_ANALISES|GUIDELINES|REVISOES|EDITORIAIS|MINIRREVISOES)
    TIPO_ARG=""
    echo "  Pasta: $PASTA_ALVO — o tipo vem do classificador."
    ;;
  *)
    echo
    echo "  ⚠️  Este PDF está FORA das pastas do classificador."
    echo "      Sem a decisão dele, o tipo é seu — e o tipo decide o motor e o prompt."
    echo
    echo "      1) artigo original   2) meta-análise   3) diretriz   4) revisão narrativa"
    echo
    read -r -p "  Tipo [1-4]: " T
    case "$T" in
      1) TIPO_ARG="--tipo=original" ;;
      2) TIPO_ARG="--tipo=meta" ;;
      3) TIPO_ARG="--tipo=diretriz" ;;
      4) TIPO_ARG="--tipo=revisao_narrativa" ;;
      *) echo "  Opção inválida."; read -p "Enter para fechar. "; exit 1 ;;
    esac
    ;;
esac

echo
python3 -u src/veredito.py "$ALVO" --fatos $TIPO_ARG
echo
read -p "Enter para fechar. "
