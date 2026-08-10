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
