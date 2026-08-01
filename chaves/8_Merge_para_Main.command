#!/bin/bash
# ═══ CHAVE 8 · LEVAR O TRABALHO PARA A MAIN ═════════════════════════════════
# A main é de onde o GitHub Actions roda (Radar 07:30 BRT, artigos-diários 07:00 BRT).
# Por isso NÃO se mexe direto nela.
#
# ORDEM SEGURA (a produção nunca fica quebrada no meio):
#   1) traz a main PARA DENTRO da lab  → conflito, se houver, acontece onde é seguro
#   2) roda a prova do motor + compila tudo → PORTÃO: se falhar, para aqui
#   3) só então a main recebe a lab — e aí já é avanço direto, sem conflito
#   4) o push fica por sua conta, depois de você olhar
#
# OS 4 CONFLITOS ESPERADOS E POR QUE A LAB VENCE OS QUATRO (conferido em 01/Ago):
#   CLAUDE.md                 → lab é a v3.0 auditada, e JÁ CONTÉM a LEI 4 que a main trouxe
#   src/article_analyzer.py   → na lab o analisador antigo está APOSENTADO (25/Jul > 24/Jul da main)
#   src/radar/radar_pubmed.py → main ainda diz modelo='gemini-2.5-pro' (MODELO MORTO);
#                               lab diz 'claude-sonnet-5'
#   src/llm_client.py         → conflito ADD/ADD (as duas branches criaram o arquivo do zero).
#                               A 1ª versão desta chave NÃO previa este e ABORTOU — o portão
#                               funcionou. Conferido função a função em 01/Ago:
#                                 main = 86 linhas, 5 funções
#                                 lab  = 189 linhas, 9 funções — SUPERCONJUNTO ESTRITO
#                                 (a lab tem tudo da main + gerar_json/tool use, log de uso,
#                                  retry em erro transitório)
#                               `gerar()` — a função que o RADAR chama — tem assinatura IDÊNTICA
#                               nas duas; a da lab só acrescenta retry. Nada que a main tenha
#                               falta na lab. Por isso é seguro ficar com a lab.
# ═══════════════════════════════════════════════════════════════════════════
set -u
cd "$(dirname "$0")" && source ./config.sh
cd "$CD_FULL" || exit 1
LAB="lab/religar-prompts"

echo "═══════════════════════════════════════════════"
echo " CHAVE 8 · MERGE PARA A MAIN"
echo "═══════════════════════════════════════════════"
echo
[ -f .git/index.lock ] && rm -f .git/index.lock && echo "(trava antiga do git removida)"

if [ -n "$(git status --porcelain)" ]; then
  echo "⛔ Há alterações não commitadas. Rode a Chave 7 (Commit) primeiro."
  git status --short; echo; read -p "Enter para fechar. "; exit 1
fi

echo "PASSO 1/4 · trazendo a main para dentro da $LAB"
git checkout "$LAB" -q || { echo "⛔ não consegui entrar na $LAB"; read -p "Enter. "; exit 1; }

if git merge main --no-edit -q 2>/dev/null; then
  echo "  ✅ sem conflito"
else
  echo "  ⚠️  conflitos — resolvendo com a versão da LAB nos 3 arquivos previstos:"
  ESPERADOS="CLAUDE.md src/article_analyzer.py src/radar/radar_pubmed.py src/llm_client.py"
  INESPERADO=""
  for f in $(git diff --name-only --diff-filter=U); do
    case " $ESPERADOS " in
      *" $f "*) git checkout --ours -- "$f" && git add "$f" && echo "      · $f → versão da LAB" ;;
      *) INESPERADO="$INESPERADO $f" ;;
    esac
  done
  if [ -n "$INESPERADO" ]; then
    echo
    echo "  ⛔ CONFLITO NÃO PREVISTO em:$INESPERADO"
    echo "     Não vou adivinhar. Abortando — nada foi alterado."
    git merge --abort; echo; read -p "Enter para fechar. "; exit 1
  fi
  git commit --no-edit -q && echo "  ✅ merge da main resolvido dentro da lab"
fi

echo
echo "PASSO 2/4 · PORTÃO — a prova do motor e a compilação de tudo"
if ! python3 src/teste_motor.py; then
  echo; echo "⛔ O MOTOR REPROVOU. A main NÃO vai receber nada."
  echo "   A lab ficou com o merge feito — conserte e rode a Chave 8 de novo."
  read -p "Enter para fechar. "; exit 1
fi
ERRO=0
for f in src/*.py; do python3 -m py_compile "$f" 2>/dev/null || { echo "  ❌ não compila: $f"; ERRO=1; }; done
if [ "$ERRO" != "0" ]; then
  echo; echo "⛔ Há arquivo que não compila. A main NÃO vai receber nada."
  read -p "Enter para fechar. "; exit 1
fi
echo "  ✅ motor aprovado · todos os .py compilam"

echo
echo "PASSO 3/4 · o que a MAIN vai receber"
git log --oneline main.."$LAB" | head -40
echo "  ($(git log --oneline main.."$LAB" | wc -l | tr -d ' ') commit(s))"
echo
echo "  ⚠️  A main é de onde o Actions roda. Isto MEXE EM PRODUÇÃO."
read -p "  Confirma levar para a main? [s/N]: " OK
if [ "$OK" != "s" ] && [ "$OK" != "S" ]; then
  echo "  Cancelado. A lab ficou atualizada; a main, intacta."
  read -p "Enter para fechar. "; exit 0
fi

echo
echo "PASSO 4/4 · main ← $LAB"
git checkout main -q && git merge "$LAB" --ff-only -q \
  && echo "  ✅ main atualizada (avanço direto, sem merge commit)" \
  || { echo "  ⛔ não foi avanço direto — algo mudou na main no meio do caminho."; \
       git checkout "$LAB" -q; read -p "Enter. "; exit 1; }

echo
git log --oneline -3
echo
echo "── FALTA O PUSH (de propósito: olhe antes) ──"
echo "   git push origin main"
echo
read -p "Enter para fechar. "
