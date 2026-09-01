#!/bin/bash
# ═══ CHAVE 26 · TESTE DO ADMINISTRADOR ═════════════════════════════════════
# Sobe a tela da Chave 3 SEM navegador (AppTest do Streamlit) e prova:
#   · o painel abre do topo ao fim sem exceção
#   · o slider NAC abre em 6–10 e as datas começam vazias (decisões do dono)
#   · o número que a tela afirma ("X na tela · Y no banco") bate com o banco
#     MEDIDO POR FORA — foi este teste que pegou o artigo inaprovável em 01/Set
#     (tela 861 × lista 860: partes 1 e 2 com o mesmo rótulo colapsavam)
#   · apertar o filtro esconde E a tela avisa
# Precisa de .env e internet (o painel LÊ o Supabase ao abrir). Não escreve nada.
# ═══════════════════════════════════════════════════════════════════════════
cd "$(dirname "$0")" && source ./config.sh && source "$CD_VENV/bin/activate"
python -u "$CD_FULL/src/teste_administrador.py" 2>&1 | grep -v "ScriptRunContext"
echo
read -p "Enter para fechar. "
