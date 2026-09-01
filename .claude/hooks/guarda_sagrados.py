#!/usr/bin/env python3
"""Trava dos arquivos sagrados — editar o motor exige confirmação; .env nunca.

`notas_prototipo.py` é a LEI 0 em código; `contrato.py`/`publicador.py` são o
portão da LEI 5; `classificador_ouro.py` é a LEI 8; `teste_motor.py` são as
travas da casa — mexer na trava é tão grave quanto mexer no motor.
`.env` guarda segredo (a service_role já vazou uma vez): o Claude não edita.

Hook PreToolUse (matcher Edit|Write).
"""
import json
import os
import sys

SAGRADOS = {
    "notas_prototipo.py": "LEI 0 — o motor de rigor",
    "contrato.py": "LEI 5 — o portão do Supabase",
    "publicador.py": "LEI 5 — o único escritor de `artigos`",
    "classificador_ouro.py": "LEI 8 — o classificador é a decisão",
    "teste_motor.py": "as travas da casa",
}


def responder(decisao: str, motivo: str) -> None:
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": decisao,
        "permissionDecisionReason": motivo,
    }}, ensure_ascii=False))
    sys.exit(0)


def main() -> None:
    dados = json.load(sys.stdin)
    fp = (dados.get("tool_input") or {}).get("file_path") or ""
    base = os.path.basename(fp)

    if base == ".env" or base.startswith(".env"):
        responder("deny", "O Claude não edita .env (segredos; já houve vazamento de chave). "
                          "Quem edita é o Dr. Eduardo — chave 13_Abrir_o_env.")

    if base in SAGRADOS:
        responder("ask", f"Arquivo SAGRADO ({SAGRADOS[base]}). Antes de editar: a LEI 9 foi "
                         "varrida (todos os blocos onde a regra mora)? A mudança é decisão do dono?")


try:
    main()
except Exception:
    pass
sys.exit(0)
