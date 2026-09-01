#!/usr/bin/env python3
"""Trava executável da LEI 12 — nada destrutivo sem conferir antes.

Intercepta comandos Bash com rm/cp/mv sobre as pastas FORA DO GIT
(saidas/, outputs/, ARTIGOS/ — ali não existe desfazer) e aplica o checklist
da lei: origem com 0 bytes não é dado; destino existente não se sobrescreve
sem olhar. Na dúvida (glob, comando composto), PEDE — não decide sozinho.

Hook PreToolUse (matcher Bash). Sem saída = fluxo normal de permissão.
"""
import json
import os
import re
import shlex
import sys

PROTEGIDAS = ("saidas", "outputs", "ARTIGOS")


def responder(decisao: str, motivo: str) -> None:
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": decisao,
        "permissionDecisionReason": motivo,
    }}, ensure_ascii=False))
    sys.exit(0)


def protegido(token: str) -> bool:
    t = token.strip("'\"").rstrip("/")
    for p in PROTEGIDAS:
        if t == p or t.startswith(p + "/") or f"/{p}/" in t + "/" or t.endswith("/" + p):
            return True
    return False


def main() -> None:
    dados = json.load(sys.stdin)
    cmd = (dados.get("tool_input") or {}).get("command") or ""
    if not re.search(r"\b(rm|cp|mv)\b", cmd):
        return
    cwd = dados.get("cwd") or os.getcwd()

    for parte in re.split(r"(?:&&|\|\||[;|])", cmd):
        try:
            tokens = shlex.split(parte.strip())
        except ValueError:
            tokens = parte.split()
        if not tokens:
            continue
        prog = os.path.basename(tokens[0])
        if prog not in ("rm", "cp", "mv"):
            continue
        args = [t for t in tokens[1:] if not t.startswith("-")]
        if not any(protegido(t) for t in args):
            continue

        if prog == "rm":
            responder("ask", "LEI 12: rm em pasta FORA DO GIT (saidas/outputs/ARTIGOS) — "
                             "ali não existe desfazer. O que será perdido é reconstruível? "
                             "Se só o Dr. Eduardo refaz, não encoste.")

        if len(args) < 2 or any("*" in a or "?" in a for a in args):
            responder("ask", f"LEI 12: {prog} com glob/forma que não consigo conferir sozinho, "
                             "sobre pasta fora do git. Confira origem (tamanho > 0) e destino antes.")

        destino = args[-1] if os.path.isabs(args[-1]) else os.path.join(cwd, args[-1])
        for origem in args[:-1]:
            o = origem if os.path.isabs(origem) else os.path.join(cwd, origem)
            if os.path.isfile(o) and os.path.getsize(o) == 0:
                responder("deny", f"LEI 12: a origem '{origem}' tem 0 BYTES — upload incompleto "
                                  "não é dado. Foi assim que o gabarito marcado se perdeu em 20/Ago.")

        alvo = destino
        if os.path.isdir(destino):
            alvo = os.path.join(destino, os.path.basename(args[0].strip("'\"").rstrip("/")))
        if os.path.exists(alvo) and protegido(args[-1]):
            responder("ask", f"LEI 12: o destino '{args[-1]}' já existe e será SOBRESCRITO, "
                             "em pasta sem git. Olhou o que há lá? É reconstruível por você?")


try:
    main()
except Exception:
    # a trava não pode derrubar a sessão; sem decisão = permissão normal
    pass
sys.exit(0)
