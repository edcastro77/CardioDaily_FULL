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

# ═══════════════════════════════════════════════════════════════════════════
# PORTÃO DE SEGREDO — 10/Ago/2026
# ═══════════════════════════════════════════════════════════════════════════
# Em 04/Ago um backup do .env chamado `.env.backup-20260804-0315` entrou no commit d1b6226 e
# ficou 23 commits versionado. O .gitignore cobria `.env` e não cobria o sufixo. Dentro dele:
# ANTHROPIC, OPENAI, GOOGLE, GEMINI, SUPABASE_SERVICE_KEY (a que escreve em QUALQUER tabela),
# ELEVENLABS, ZAPI, TELEGRAM, NCBI e o telefone do Dr. Eduardo.
#
# Só não virou incidente porque o repositório estava 25 commits atrás do GitHub e o push nunca
# tinha sido dado. Foi achado à mão, conferindo o que ia subir. Sorte não é processo.
#
# Esta trava olha DUAS coisas, porque o .gitignore sozinho não basta:
#   1. o NOME do arquivo (o que o .gitignore já pega — e pegou tarde)
#   2. o CONTEÚDO: qualquer linha com cara de chave de API dentro de arquivo staged. É isto que
#      pega o caso que o nome não denuncia — a chave colada dentro de um .py, de um .md, de um
#      COMMIT_MSG.txt. Nome a gente acerta; conteúdo escapa.
# Ela RECUSA — não avisa e segue. Segredo commitado não se desfaz apagando depois: fica no
# histórico, e bot varre o GitHub por chave em segundos.
SUSPEITOS=$(git diff --cached --name-only | grep -iE '(^|/)\.env($|\.)|\.pem$|\.p12$|_secrets|service_account' || true)

VAZANDO=""
for f in $(git diff --cached --name-only --diff-filter=ACM); do
  [ -f "$f" ] || continue
  case "$f" in *.png|*.jpg|*.pdf|*.mp3|*.xlsx) continue ;; esac
  # sk-… (OpenAI) · sk-ant-… (Anthropic) · AIza… (Google) · JWT de 3 partes (Supabase) · xai-…
  #
  # ⚠️ O JWT ME PEGOU NA PRIMEIRA SABOTAGEM. Eu tinha escrito `eyJ[A-Za-z0-9_-]{40,}` — e o
  # cabeçalho padrão de TODO JWT é `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9`: 33 caracteres depois
  # do `eyJ`, e o PONTO que vem a seguir não está na classe. A trava exigia 40 e nunca chegaria
  # lá. Ou seja: ela teria recusado chave nenhuma do Supabase — justamente a mais perigosa, a
  # que ignora as políticas e escreve em qualquer tabela. Passava dando "✓ portão ok".
  # Agora casa a ESTRUTURA de três partes separadas por ponto, que é o que define um JWT.
  if grep -qE '(sk-ant-[A-Za-z0-9_-]{20,}|sk-[A-Za-z0-9_-]{20,}|AIza[A-Za-z0-9_-]{30,}|xai-[A-Za-z0-9_-]{20,}|eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{10,})' "$f" 2>/dev/null; then
    VAZANDO="$VAZANDO $f"
  fi
done

if [ -n "$SUSPEITOS" ] || [ -n "$VAZANDO" ]; then
  echo "🔴🔴🔴  COMMIT RECUSADO — SEGREDO NA FILA  🔴🔴🔴"
  echo
  [ -n "$SUSPEITOS" ] && { echo "   arquivo com NOME de segredo:"; for f in $SUSPEITOS; do echo "      · $f"; done; echo; }
  [ -n "$VAZANDO" ]   && { echo "   arquivo com CHAVE DENTRO (sk-… / AIza… / eyJ…):"; for f in $VAZANDO; do echo "      · $f"; done; echo; }
  echo "   Nada foi commitado. Para tirar da fila sem apagar do disco:"
  for f in $SUSPEITOS $VAZANDO; do echo "      git rm --cached \"$f\""; done
  echo
  echo "   Depois acrescente o padrão ao .gitignore e rode a Chave 7 de novo."
  echo "   Se a chave já foi commitada antes, apagar agora NÃO basta: ela fica no histórico."
  echo
  git reset -q
  read -p "Enter para fechar. "; exit 1
fi
echo "   ✓ portão de segredo: nenhum arquivo com nome nem conteúdo de chave"
echo
# ═══ 11/Ago/2026 — A MENSAGEM ESTAVA VELHA E NINGUÉM VIU ═══
#
# O Dr. Eduardo rodou a Chave 7 duas vezes hoje. Os dois commits saíram com o título
# "A VARREDURA DOS 4 SCHEMAS — 05/Ago/2026" — uma mensagem escrita em 09/Ago, sobre trabalho
# de 05/Ago. O que foi commitado hoje era outra coisa inteira: o telefone do distribuidor, o
# ACRI do painel, o filtro de data, o bloqueio de protocolo, o teto do desenho.
#
# O histórico do git passou a MENTIR — e o histórico é o que sobra quando ninguém lembra.
# Daqui a um mês, procurando "quando foi que o protocolo passou a ser bloqueado", a resposta
# vai ser um commit chamado "varredura dos 4 schemas".
#
# A chave imprimia só as 3 primeiras linhas, ele lia "A VARREDURA DOS 4 SCHEMAS" e confirmava.
# É a mesma família do dia: a tela mostra algo plausível e o estado é outro.
#
# Agora a chave COMPARA a idade do COMMIT_MSG.txt com a do arquivo mais novo da fila. Se a
# mensagem for mais velha que o trabalho, ela PARA.
NOVO=$(git diff --cached --name-only | while read -r f; do [ -f "$f" ] && stat -f %m "$f" 2>/dev/null || stat -c %Y "$f" 2>/dev/null; done | sort -rn | head -1)
MSG=$(stat -f %m COMMIT_MSG.txt 2>/dev/null || stat -c %Y COMMIT_MSG.txt 2>/dev/null)
echo "── MENSAGEM ──"
if [ -n "$NOVO" ] && [ -n "$MSG" ] && [ "$MSG" -lt "$NOVO" ]; then
  echo
  echo "   🔴 A MENSAGEM É MAIS VELHA QUE O TRABALHO — COMMIT RECUSADO"
  echo
  echo "      COMMIT_MSG.txt escrito em : $(date -r $MSG '+%d/%b %H:%M' 2>/dev/null)"
  echo "      arquivo mais novo da fila : $(date -r $NOVO '+%d/%b %H:%M' 2>/dev/null)"
  echo
  echo "      Primeira linha da mensagem: \"$(head -1 COMMIT_MSG.txt)\""
  echo
  echo "   Em 11/Ago dois commits saíram com a mensagem de 05/Ago, e o histórico passou a"
  echo "   mentir sobre o que foi feito. Reescreva o COMMIT_MSG.txt e rode a chave de novo."
  echo
  git reset -q
  read -p "Enter para fechar. "; exit 1
fi
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

# ═══ 11/Ago — E O PUSH NUNCA ACONTECIA ═══
# A chave imprimia "Para enviar ao GitHub: git push" e fechava. Ele rodou a Chave 7 duas
# vezes hoje achando que o trabalho estava salvo — e estavam **10 commits** só no Mac dele.
# Uma instrução impressa não é uma ação executada. A chave passa a OFERECER o push, e a
# dizer com todas as letras quando NÃO enviou.
FALTAM=$(git log --oneline @{u}..HEAD 2>/dev/null | wc -l | tr -d ' ')
echo "══════════════════════════════════════════════════════════"
if [ "${FALTAM:-0}" -eq 0 ]; then
  echo "   ✅ O GitHub está em dia."
else
  echo "   ⚠️  $FALTAM commit(s) existem SÓ NESTE MAC."
  echo "      Se o disco morrer agora, morre com ele."
  echo
  read -p "   Enviar ao GitHub agora? [s/N]: " P
  echo
  case "$P" in
    s|S|sim|SIM)
      if git push; then
        echo; echo "   ✅ ENVIADO. Agora existe em outro lugar além deste Mac."
      else
        echo; echo "   🔴 O PUSH FALHOU (veja o erro acima). O trabalho continua só aqui."
      fi ;;
    *)
      echo "   🔴 NÃO ENVIADO — os $FALTAM commit(s) continuam só neste Mac." ;;
  esac
fi
echo "══════════════════════════════════════════════════════════"
echo "(o cron do Actions roda do main — se este trabalho tem que ir pra produção, precisa ir pro main)"
echo
read -p "Enter para fechar. "
