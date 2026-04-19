#!/bin/bash
# ============================================================
# RE-ANALISAR FALHAS - CardioDaily
# Detecta artigos com status=failed, limpa os stubs e re-processa.
# Uso: bash scripts/reanalisar_falhas.sh
# ============================================================

cd "$(dirname "$0")/.."
source venv/bin/activate

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "============================================="
echo "  RE-ANALISAR FALHAS - CardioDaily"
echo "  $(date '+%d/%m/%Y %H:%M')"
echo "============================================="
echo ""

# ── 1. Encontrar artigos com status=failed ─────────────────
echo "🔍 Buscando artigos com falha..."

FAILED_DIRS=$(python3 -c "
import json
from pathlib import Path

corpus = Path('outputs/corpus')
falhas = []
for d in corpus.iterdir():
    if not d.is_dir(): continue
    md = d / 'analysis.md'
    js = d / 'analysis.json'
    if not md.exists() or not js.exists(): continue

    # Checar status=failed no md
    try:
        content = md.read_text(encoding='utf-8')
        if 'status: \"failed\"' in content or 'status: failed' in content:
            falhas.append(str(d))
            continue
    except: pass

    # Checar nota=0 E md muito curto (< 2000b = análise incompleta)
    try:
        data = json.loads(js.read_text())
        scores = data.get('analysis',{}).get('scores') or data.get('scores') or {}
        nota = int(scores.get('aplicabilidade') or scores.get('overall') or 0)
        if nota == 0 and md.stat().st_size < 2000:
            falhas.append(str(d))
    except: pass

for f in falhas:
    print(f)
" 2>/dev/null)

N_FALHAS=$(echo "$FAILED_DIRS" | grep -c "doi_\|pdf_" 2>/dev/null || echo 0)

if [ "$N_FALHAS" -eq 0 ]; then
    echo "✅ Nenhuma falha encontrada! Todos os artigos foram analisados com sucesso."
    echo ""
    echo "Pressione ENTER para fechar..."
    read -r
    exit 0
fi

echo "⚠️  Artigos com falha encontrados: $N_FALHAS"
echo ""

# ── 2. Listar PDFs que ainda estão nas pastas ──────────────
N_ORIG=$(find "$PROJECT_ROOT/ARTIGOS/ARTIGOS_ORIGINAIS" -maxdepth 1 -name "*.pdf" 2>/dev/null | wc -l | tr -d ' ')
N_GUIDE=$(find "$PROJECT_ROOT/ARTIGOS/GUIDELINES" -maxdepth 1 -name "*.pdf" 2>/dev/null | wc -l | tr -d ' ')
N_REV=$(find "$PROJECT_ROOT/ARTIGOS/REVISOES" -maxdepth 1 -name "*.pdf" 2>/dev/null | wc -l | tr -d ' ')
N_META=$(find "$PROJECT_ROOT/ARTIGOS/META_ANALISES" -maxdepth 1 -name "*.pdf" 2>/dev/null | wc -l | tr -d ' ')
N_PDFS=$((N_ORIG + N_GUIDE + N_REV + N_META))

echo "  PDFs disponíveis para re-análise:"
echo "  Artigos Originais : $N_ORIG"
echo "  Guidelines        : $N_GUIDE"
echo "  Revisões          : $N_REV"
echo "  Meta-análises     : $N_META"
echo "  Total             : $N_PDFS PDFs"
echo ""

if [ "$N_PDFS" -eq 0 ]; then
    echo "⚠️  Nenhum PDF nas pastas ARTIGOS. Os PDFs podem ter sido arquivados."
    echo "   Execute o Arquivar Artigos e depois o Classificar Artigos com os PDFs originais."
    echo ""
    echo "Pressione ENTER para fechar..."
    read -r
    exit 1
fi

# ── 3. Confirmação ─────────────────────────────────────────
echo "Deseja limpar os stubs e re-analisar os $N_FALHAS artigos com falha?"
echo "(Os $((N_PDFS - N_FALHAS > 0 ? N_PDFS - N_FALHAS : 0)) já analisados com sucesso serão pulados)"
echo ""
read -p "Digite sim para continuar: " CONFIRMA

if [[ "${CONFIRMA,,}" != "sim" ]]; then
    echo "Operação cancelada."
    exit 0
fi

# ── 4. Limpar stubs dos artigos com falha ─────────────────
echo ""
echo "🗑️  Limpando stubs de análise com falha..."

LIMPOS=0
while IFS= read -r dir; do
    [ -z "$dir" ] && continue
    if [ -d "$dir" ]; then
        rm -f "$dir/analysis.md" "$dir/analysis.json"
        LIMPOS=$((LIMPOS + 1))
    fi
done <<< "$FAILED_DIRS"

echo "   ✅ $LIMPOS stubs removidos."
echo ""

# ── 5. Re-analisar ─────────────────────────────────────────
echo "▶ Re-analisando artigos..."
echo ""

INICIO=$(date +%s)
ERROS=0

if [ "$N_ORIG" -gt 0 ]; then
    echo "── Artigos Originais ($N_ORIG PDFs) ──"
    export LOCAL_ARTICLES_DIR="$PROJECT_ROOT/ARTIGOS/ARTIGOS_ORIGINAIS"
    python3 src/article_analyzer.py || ERROS=$((ERROS + 1))
    echo ""
fi

if [ "$N_GUIDE" -gt 0 ]; then
    echo "── Guidelines ($N_GUIDE PDFs) ──"
    export LOCAL_ARTICLES_DIR="$PROJECT_ROOT/ARTIGOS/GUIDELINES"
    python3 src/article_analyzer.py || ERROS=$((ERROS + 1))
    echo ""
fi

if [ "$N_REV" -gt 0 ]; then
    echo "── Revisões ($N_REV PDFs) ──"
    export LOCAL_ARTICLES_DIR="$PROJECT_ROOT/ARTIGOS/REVISOES"
    python3 src/article_analyzer.py || ERROS=$((ERROS + 1))
    echo ""
fi

if [ "$N_META" -gt 0 ]; then
    echo "── Meta-análises ($N_META PDFs) ──"
    export LOCAL_ARTICLES_DIR="$PROJECT_ROOT/ARTIGOS/META_ANALISES"
    python3 src/article_analyzer.py || ERROS=$((ERROS + 1))
    echo ""
fi

# ── 6. Sync Supabase ───────────────────────────────────────
echo "── Sync Supabase ──"
python3 scripts/indexar_corpus_completo.py && echo "  ✅ Supabase sincronizado." || echo "  ⚠️  Sync Supabase falhou."

# ── 7. Resumo ──────────────────────────────────────────────
FIM=$(date +%s)
DURACAO=$(( (FIM - INICIO) / 60 ))

# Contar quantos ainda falhos
AINDA_FALHOS=$(python3 -c "
from pathlib import Path
n = 0
for d in Path('outputs/corpus').iterdir():
    md = d / 'analysis.md'
    if md.exists() and ('status: \"failed\"' in md.read_text(encoding='utf-8', errors='ignore') or md.stat().st_size < 2000):
        n += 1
print(n)
" 2>/dev/null || echo "?")

echo ""
echo "============================================="
echo "  RE-ANÁLISE CONCLUÍDA"
echo "  Tempo: ${DURACAO} min | Erros: $ERROS"
echo "  Ainda com falha: $AINDA_FALHOS artigos"
echo "============================================="

if [ "$AINDA_FALHOS" != "0" ] && [ "$AINDA_FALHOS" != "?" ]; then
    echo ""
    echo "  Se ainda há falhas, pode ser instabilidade de API."
    echo "  Execute este script novamente quando a internet estiver estável."
fi

osascript -e "display notification \"Re-análise concluída. Falhas restantes: $AINDA_FALHOS\" with title \"CardioDaily\" subtitle \"Re-analisar Falhas\" sound name \"Glass\"" 2>/dev/null

echo ""
echo "Pressione ENTER para fechar..."
read -r
