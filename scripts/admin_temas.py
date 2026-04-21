#!/usr/bin/env python3
"""
CardioDaily — Admin de temas por assinante.

Permite definir os temas de interesse de cada assinante interativamente
ou via arquivo de configuração.

Uso:
  python3 scripts/admin_temas.py               # modo interativo
  python3 scripts/admin_temas.py --listar      # mostra configuração atual
  python3 scripts/admin_temas.py --arquivo temas.json  # aplica de arquivo JSON
"""

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv
load_dotenv(ROOT / ".env")
from supabase import create_client

TEMAS_VALIDOS = [
    "coronaria",
    "cardiometabolico",
    "miocardiopatias",
    "valvulopatias",
    "arritmia",
    "uti",
    "imagem",
    "prevencao",
    "genomica",
    "obstetrica",
    "oncologia",
]

TEMAS_DESCRICAO = {
    "coronaria":       "Coronariopatia aguda/crônica, ICP, stent",
    "cardiometabolico":"Dislipidemia, diabetes, obesidade, HAS, GLP-1",
    "miocardiopatias": "Miocardiopatias, IC, amiloidose, dLVAD",
    "valvulopatias":   "Valvulopatias, TAVI, cirurgia valvar",
    "arritmia":        "FA, arritmias, marcapasso, ablação, stroke",
    "uti":             "Emergências, choque, UTI, PCR",
    "imagem":          "Eco, TC, RM, cintilografia, imagem CV",
    "prevencao":       "Prevenção CV, reabilitação, estilo de vida",
    "genomica":        "Genética, cardiomiopatia hereditária, congênitas",
    "obstetrica":      "Cardio-obstetrícia, gravidez e coração",
    "oncologia":       "Cardio-oncologia, toxicidade CV de quimioterapia",
}


def conectar():
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_KEY", "")
    return create_client(url, key)


def listar_assinantes(sb):
    result = sb.table("whatsapp_users").select(
        "id, nome, phone, temas, ativo"
    ).order("nome").execute()
    return result.data


def exibir_tabela(assinantes):
    print(f"\n{'#':<3} {'Nome':<25} {'Temas'}")
    print("─" * 80)
    for i, a in enumerate(assinantes, 1):
        temas = a.get("temas") or []
        ativo = "✅" if a.get("ativo") else "⏸️"
        print(f"{i:<3} {ativo} {a['nome']:<22} {', '.join(temas) if temas else '(todos)'}")


def exibir_menu_temas(selecionados):
    print("\nTemas disponíveis:")
    for i, tema in enumerate(TEMAS_VALIDOS, 1):
        marca = "✅" if tema in selecionados else "  "
        print(f"  {marca} {i:>2}. {tema:<20} {TEMAS_DESCRICAO[tema]}")
    print("\n  0. Confirmar e salvar")
    print("  T. Selecionar TODOS")
    print("  N. Limpar todos")


def editar_temas_interativo(nome, temas_atuais):
    selecionados = list(temas_atuais or TEMAS_VALIDOS)
    while True:
        print(f"\n── {nome} ──")
        exibir_menu_temas(selecionados)
        escolha = input("Número para toggle (ou 0 para salvar): ").strip().upper()
        if escolha == "0":
            break
        elif escolha == "T":
            selecionados = list(TEMAS_VALIDOS)
        elif escolha == "N":
            selecionados = []
        else:
            try:
                n = int(escolha)
                if 1 <= n <= len(TEMAS_VALIDOS):
                    tema = TEMAS_VALIDOS[n - 1]
                    if tema in selecionados:
                        selecionados.remove(tema)
                    else:
                        selecionados.append(tema)
            except ValueError:
                print("Opção inválida.")
    return selecionados


def salvar_temas(sb, assinante_id, temas):
    sb.table("whatsapp_users").update({"temas": temas}).eq("id", assinante_id).execute()


def modo_interativo(sb):
    assinantes = listar_assinantes(sb)
    exibir_tabela(assinantes)

    print("\nDigite o número do assinante para editar (ou 0 para sair):")
    while True:
        escolha = input("\n> ").strip()
        if escolha == "0":
            break
        try:
            idx = int(escolha) - 1
            if 0 <= idx < len(assinantes):
                a = assinantes[idx]
                novos = editar_temas_interativo(a["nome"], a.get("temas") or [])
                salvar_temas(sb, a["id"], novos)
                print(f"✅ {a['nome']} → {', '.join(novos)}")
                # Atualizar lista local
                assinantes[idx]["temas"] = novos
                exibir_tabela(assinantes)
            else:
                print("Número fora do intervalo.")
        except ValueError:
            print("Inválido.")


def modo_arquivo(sb, caminho):
    """
    Arquivo JSON no formato:
    {
      "Carol": ["coronaria", "miocardiopatias"],
      "Lapa":  ["coronaria", "arritmia", "valvulopatias"]
    }
    """
    with open(caminho) as f:
        config = json.load(f)

    assinantes = listar_assinantes(sb)
    nome_para_id = {a["nome"]: a["id"] for a in assinantes}

    ok, erro = 0, 0
    for nome, temas in config.items():
        temas_invalidos = [t for t in temas if t not in TEMAS_VALIDOS]
        if temas_invalidos:
            print(f"❌ {nome}: temas inválidos {temas_invalidos}")
            erro += 1
            continue
        if nome not in nome_para_id:
            print(f"❌ {nome}: assinante não encontrado")
            erro += 1
            continue
        salvar_temas(sb, nome_para_id[nome], temas)
        print(f"✅ {nome} → {', '.join(temas)}")
        ok += 1

    print(f"\n{ok} atualizados, {erro} erros.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--listar", action="store_true")
    parser.add_argument("--arquivo", type=str)
    args = parser.parse_args()

    sb = conectar()

    if args.listar:
        exibir_tabela(listar_assinantes(sb))
    elif args.arquivo:
        modo_arquivo(sb, args.arquivo)
    else:
        modo_interativo(sb)


if __name__ == "__main__":
    main()
