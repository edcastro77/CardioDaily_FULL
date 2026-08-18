#!/bin/bash
# ═══ CHAVE 23 · CONFERIR A CHAVE DO SUPABASE ═══
#
# 14/Ago/2026 — a SUPABASE_SERVICE_ROLE_KEY foi encontrada em texto puro num arquivo colado
# num chat externo (o briefing do site, em julho). Ela ignora todas as permissões: lê e apaga
# o banco inteiro. A troca não é "rotacionar" — rotacionar derruba a chave `anon` junto e o
# site para. É CRIAR uma chave nova (`sb_secret_…`) e aposentar a velha.
#
# Esta chave existe para você conferir, ANTES e DEPOIS da troca, se está tudo de pé.
# Ela NÃO muda nada: só lê o .env e pergunta ao Supabase.
cd "$(dirname "$0")" && source ./config.sh && source "$CD_VENV/bin/activate"
cd "$CD_FULL"

clear
echo "═══════════════════════════════════════════════"
echo " CHAVE 23 · CONFERIR A CHAVE DO SUPABASE"
echo " (não muda nada — só olha e testa)"
echo "═══════════════════════════════════════════════"
echo

python3 - <<'PY'
import os, sys, json, urllib.request, urllib.error
sys.path.insert(0, "src")
from dotenv import load_dotenv
load_dotenv(".env", override=True)
from supabase_chaves import cabecalhos, descrever, eh_chave_nova

url = (os.getenv("SUPABASE_URL") or "").rstrip("/")
print(f"   projeto: {url or '(SUPABASE_URL vazio!)'}")
print()

CHAVES = [("SUPABASE_SERVICE_ROLE_KEY", "escreve tudo — é a que vazou"),
          ("SUPABASE_SERVICE_KEY",      "o mesmo, com outro nome"),
          ("SUPABASE_ANON_KEY",         "leitura pública — o site usa esta"),
          ("SUPABASE_KEY",              "genérica")]

print("   ── O QUE ESTÁ NO .env ──")
achou = {}
for nome, papel in CHAVES:
    v = os.getenv(nome)
    if v:
        achou[nome] = v
        print(f"   {nome:28} {descrever(v)}")
        print(f"   {'':28} └ {papel}")
if not achou:
    print("   🔴 nenhuma chave do Supabase no .env")
print()

print("   ── FUNCIONA? (uma leitura de 1 linha, sem escrever nada) ──")
for nome, v in achou.items():
    try:
        req = urllib.request.Request(f"{url}/rest/v1/artigos?select=doc_id&limit=1",
                                     headers=cabecalhos(v))
        r = urllib.request.urlopen(req, timeout=20)
        print(f"   ✅ HTTP {r.status}  {nome}")
    except urllib.error.HTTPError as e:
        corpo = e.read()[:120].decode("utf-8", "replace")
        print(f"   🔴 HTTP {e.code}  {nome} — {corpo}")
    except Exception as e:
        print(f"   ⚠️  {nome}: não consegui testar ({type(e).__name__})")
print()

# ── o veredito, em português ──
svc = achou.get("SUPABASE_SERVICE_ROLE_KEY") or achou.get("SUPABASE_SERVICE_KEY")
print("   ── VEREDITO ──")
if not svc:
    print("   ⚠️  não achei chave de serviço no .env")
elif eh_chave_nova(svc):
    print("   ✅ A chave de serviço JÁ É A NOVA (sb_secret_…).")
    print("      Falta só desativar a `service_role` legada no painel do Supabase,")
    print("      em Settings > API Keys. Isso é reversível.")
else:
    print("   🔴 A chave de serviço ainda é a LEGADA (JWT) — a que vazou.")
    print("      Crie a nova em: Supabase > Settings > API Keys > Create new API keys")
    print("      Depois troque nos 5 lugares (veja docs/TROCA_DA_CHAVE.md).")
print()

# ── backups de .env com chave dentro ──
import glob
velhos = [f for f in glob.glob(".env.*") if not f.endswith(".example")]
if velhos:
    print(f"   ⚠️  {len(velhos)} arquivo(s) .env.* no disco, com a chave ANTIGA dentro:")
    for f in velhos:
        print(f"        {f}")
    print("      Depois da troca eles ficam inúteis — e continuam sendo cópia de segredo")
    print("      espalhada. A Chave 23 não apaga nada; apague você quando terminar.")
PY

echo
read -p "Enter para fechar. "
