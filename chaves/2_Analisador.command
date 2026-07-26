#!/bin/bash
# ═══ CHAVE 2 · ANALISADOR ═══  (analisa → notas → perícia/áudio → PUBLICA SOZINHO como rascunho)
cd "$(dirname "$0")" && source ./config.sh && source "$CD_VENV/bin/activate"
echo "═══════════════════════════════════════"
echo " CHAVE 2 · ANALISADOR"
echo " Lendo classificados de: $CD_CLASSIFICADOS"
echo " Analisa E publica em BLOCOS DE 20 — cada bloco vai pro Supabase antes do próximo."
echo " Se a net cair, os blocos publicados ficam SALVOS; clique a Chave 2 de novo e ela CONTINUA."
echo "═══════════════════════════════════════"
python "$CD_FULL/src/rodar_em_blocos.py" "$CD_CLASSIFICADOS" 20
echo
echo "═══════════════════════════════════════"
echo " TRILHA MINIRREVISÃO / OPINIÃO DE ESPECIALISTA"
echo " Condutas práticas + fluxograma. NÃO sobe no Supabase (é standalone, como o Pesquisador)."
echo " Saída em: $CD_FULL/outputs/MINIRREVISOES/  ·  faixa 0 (vaselina) fica retida."
echo "═══════════════════════════════════════"
python "$CD_FULL/src/minirevisao.py" "$CD_CLASSIFICADOS/MINIRREVISOES"
echo
echo "✔ Publicado em blocos, como rascunho. Sobrou algo na fila (queda de rede)? Clique a Chave 2 de novo."
echo "  Minirevisões: condutas + fluxograma em outputs/MINIRREVISOES/ (não vão pro site)."
echo "  Curadoria (ver · ouvir · aprovar) → Chave 3 · Administrador."
read -p "Enter para fechar. "
