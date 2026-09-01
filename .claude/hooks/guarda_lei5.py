#!/usr/bin/env python3
"""Trava executável da LEI 5 — só o publicador.py escreve na tabela `artigos`.

Vale para o Claude também: bloqueia SQL de escrita em `artigos` (via Bash ou
via MCP Supabase execute_sql/apply_migration) e REST cru de escrita em
/rest/v1/artigos. Quem precisa publicar chama o portão
(src/rodar_em_blocos.py → publicador), nunca por fora. SELECT é livre.

Hook PreToolUse (matchers: Bash e mcp__*upabase*__execute_sql|apply_migration).
"""
import json
import re
import sys

SQL_ESCRITA = re.compile(
    r"\b(INSERT\s+INTO|UPDATE|DELETE\s+FROM|TRUNCATE(\s+TABLE)?|DROP\s+TABLE|ALTER\s+TABLE)\s+"
    r'("?public"?\.)?"?artigos"?\b',
    re.IGNORECASE)

MOTIVO = ("LEI 5: só o publicador.py escreve na tabela `artigos`. Para publicar ou "
          "atualizar artigo, rode o portão (src/rodar_em_blocos.py). SELECT é livre.")


def responder(decisao: str, motivo: str) -> None:
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": decisao,
        "permissionDecisionReason": motivo,
    }}, ensure_ascii=False))
    sys.exit(0)


def main() -> None:
    dados = json.load(sys.stdin)
    nome = dados.get("tool_name") or ""
    ti = dados.get("tool_input") or {}

    if nome == "Bash":
        cmd = ti.get("command") or ""
        if SQL_ESCRITA.search(cmd):
            responder("deny", MOTIVO)
        if re.search(r"/rest/v1/artigos", cmd) and re.search(
                r"(-X\s*(POST|PATCH|PUT|DELETE)\b|--request\s+(POST|PATCH|PUT|DELETE)\b|--data\b|\s-d\s)",
                cmd, re.IGNORECASE):
            responder("deny", MOTIVO + " (REST cru de escrita em /rest/v1/artigos detectado)")
        return

    if "execute_sql" in nome or "apply_migration" in nome:
        q = str(ti.get("query") or ti.get("sql") or "")
        if "apply_migration" in nome:
            # migração é o caminho legítimo para schema — mas em `artigos` é decisão do dono
            if re.search(r"\bartigos\b", q, re.IGNORECASE):
                responder("ask", "Migração tocando na tabela `artigos`: mudança de schema exige "
                                 "migração explícita decidida pelo dono. Confirme antes.")
            return
        if SQL_ESCRITA.search(q):
            responder("deny", MOTIVO)


try:
    main()
except Exception:
    pass
sys.exit(0)
