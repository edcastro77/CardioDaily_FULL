#!/usr/bin/env python3
"""Depois de TODA edição de .py, confere a sintaxe na hora.

Erro de sintaxe não espera a Chave 8: o Claude recebe o erro de volta
imediatamente e conserta antes de seguir. Só checa sintaxe (compile),
não escreve bytecode nem executa nada.

Hook PostToolUse (matcher Edit|Write).
"""
import json
import sys


def main() -> None:
    dados = json.load(sys.stdin)
    fp = ((dados.get("tool_input") or {}).get("file_path")
          or (dados.get("tool_response") or {}).get("filePath") or "")
    if not fp.endswith(".py"):
        return
    try:
        with open(fp, encoding="utf-8") as f:
            compile(f.read(), fp, "exec")
    except SyntaxError as e:
        print(json.dumps({
            "decision": "block",
            "reason": f"SINTAXE REPROVADA em {fp}, linha {e.lineno}: {e.msg}. Conserte antes de seguir.",
        }, ensure_ascii=False))


try:
    main()
except Exception:
    pass
sys.exit(0)
