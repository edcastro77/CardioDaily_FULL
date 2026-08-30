"""
devolver_para_futilidade.py — devolve à fila os artigos que podem ter parado por FUTILIDADE.

═══ 29/Ago/2026 — POR QUE ═══
O LIBREXIA-ACS (NEJM, 29/Ago) saiu com nota 6 e `muda_conduta: NÃO` sobre um ensaio de 14.194
pacientes que o DSMB mandou parar por futilidade em análise interina pré-especificada. Parar
por futilidade produz, MECANICAMENTE, os dois campos que o motor lia como "ficou pelo caminho":

    poder_ok               False
    eventos_nao_alcancados True     (749 dos 875 previstos = 85,6%)

A exceção do BENEFÍCIO existia no `teto_desenho` desde sempre; a simétrica nunca existiu.
Regra nova (decisão do Dr. Eduardo, 29/Ago — *"confirmo o 9"*): futilidade neutraliza o poder,
não desconta rigor pelos eventos, e abre a Rota 2. Medido: aplic 6 → 9, muda_conduta → SIM.

═══ POR QUE SÃO 3, E NÃO 27 ═══
Candidatos brutos no acervo (`poder_ok=False` + `eventos_nao_alcancados` + não parou por
benefício): 27 de 274 RCTs de intervenção. Re-extrair os 27 custaria US$ 5,71 (mediana medida
no `uso.jsonl`: US$ 0,212/artigo).

Em vez disso o PDF de cada um foi LIDO (`pdftotext`) e varrido por `futility|futilidade|
conditional power`. É evidência mais forte que o palpite: lê o ARTIGO, não o que o extrator
resolveu escrever no campo livre. Resultado:

     3  a palavra está no artigo  → estes aqui       (US$ 0,64)
    24  não aparece no PDF inteiro → insuficiência de verdade, ficam como estão

O 24º merece nota, porque eu errei duas vezes sobre ele antes de ir ler. O CARRESS-HF
(Ultrafiltration/NEJM 2012) foi por mim chamado de "PDF sem texto extraível" e depois de "o PDF
não está mais em ARTIGOS/". As duas erradas: extrai 41.417 caracteres, e o arquivo existe (o
Dr. Eduardo o subiu em 19/Ago; eu tinha varrido só ARTIGOS/). Lido inteiro: futility 0,
conditional power 0, interim analysis 0 — as duas ocorrências de "stopped" falam da
ultrafiltração interrompida em PACIENTES, não do ensaio. Insuficiência de verdade.

⚠️ A palavra aparecer NÃO prova que o ensaio parou por futilidade — pode ser frase de métodos
("uma análise interina de futilidade estava prevista"). Quem decide é a re-extração. O grep
serve só para não pagar pelos 23 que certamente não mudam.

═══ O QUE ACONTECE DEPOIS ═══
O PDF volta para `ARTIGOS_ORIGINAIS/`. Na próxima Chave 2 o analisador vê que o carimbo
`extrator` mudou (o prompt de extração mudou de verdade) e faz TERRA ARRASADA no pacote —
re-extrai do zero, com o campo `parado_por_futilidade` já no schema. O publicador reescreve a
linha pelo `doc_id` (upsert idempotente, LEI 5): não cria duplicata.

═══ LEI 12 — NADA DESTRUTIVO SEM CONFERIR ANTES ═══
Roda em DOIS tempos. Sem `--executar` só MOSTRA. Move (não copia, não apaga), confere tamanho
da origem, e RECUSA mover se já existir algo no destino. `ARTIGOS/` não está no git.

Uso:  python3 scripts/devolver_para_futilidade.py              # ensaio, não toca em nada
      python3 scripts/devolver_para_futilidade.py --executar
"""
import os
import shutil
import subprocess
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLASSIFICADOS = os.path.join(RAIZ, "ARTIGOS", "CLASSIFICADOS")
ORIGEM = os.path.join(CLASSIFICADOS, "_PUBLICADOS")
DESTINO = os.path.join(CLASSIFICADOS, "ARTIGOS_ORIGINAIS")

# Os 3 achados pela varredura dos PDFs em 29/Ago. Prefixo, porque os nomes são longos.
ALVOS = [
    ("NEJMoa2608717",
     "LIBREXIA-ACS · milvexian após SCA · 8 ocorrências de futility/conditional power"),
    ("2026-06-Journal_of_the_American_-Vagal_Nerve_Stimulation",
     "Vagal Nerve Stimulation na IC · 2 ocorrências de 'for futility'"),
    ("2026-08-JAMA-Cardiovascular_Magnetic_Resonance_to_Guide_Defibrillator",
     "CMR para guiar CDI · 1 ocorrência de 'futility' (pode ser só métodos)"),
]


def _acha(prefixo):
    if not os.path.isdir(ORIGEM):
        return None
    for f in sorted(os.listdir(ORIGEM)):
        if f.lower().endswith(".pdf") and f.startswith(prefixo):
            return f
    return None


def main():
    executar = "--executar" in sys.argv
    plano, faltando = [], []
    for prefixo, porque in ALVOS:
        f = _acha(prefixo)
        (plano.append((f, porque)) if f else faltando.append((prefixo, porque)))

    print("═" * 78)
    print(" DEVOLVER À FILA — candidatos a PARADA POR FUTILIDADE"
          + ("" if executar else "   ·   E N S A I O"))
    print("═" * 78)
    for f, porque in plano:
        kb = os.path.getsize(os.path.join(ORIGEM, f)) / 1024
        print(f"\n   {f[:70]}")
        print(f"      {porque}")
        print(f"      {kb:.0f} KB  ·  _PUBLICADOS/ → ARTIGOS_ORIGINAIS/")
    for prefixo, porque in faltando:
        print(f"\n   ⚠️  NÃO ACHEI em _PUBLICADOS: {prefixo[:56]}")
        print(f"      {porque}")

    print("\n" + "─" * 78)
    print(f"   {len(plano)} artigo(s) · custo estimado da Chave 2: "
          f"US$ {0.212 * len(plano):.2f}  (mediana medida em 1.120 artigos)")

    if not executar:
        print("\n   ENSAIO — nada foi movido. Para valer:")
        print("     python3 scripts/devolver_para_futilidade.py --executar")
        return 0

    os.makedirs(DESTINO, exist_ok=True)
    movidos = 0
    for f, _porque in plano:
        origem, alvo = os.path.join(ORIGEM, f), os.path.join(DESTINO, f)
        if os.path.exists(alvo):                       # LEI 12, item 2
            print(f"   ⚠️  já existe no destino, NÃO mexi: {f[:56]}")
            continue
        if os.path.getsize(origem) < 1024:             # LEI 12, item 1
            print(f"   ⚠️  origem com {os.path.getsize(origem)} bytes — NÃO mexi: {f[:44]}")
            continue
        shutil.move(origem, alvo)
        movidos += 1
        print(f"   ✅ {f[:66]}")

    print("\n" + "─" * 78)
    print(f"   {movidos} PDF(s) de volta na fila. Agora rode a CHAVE 2 (opção "
          f"ARTIGOS_ORIGINAIS).")
    print("   O analisador vai fazer TERRA ARRASADA nesses pacotes (o carimbo do extrator")
    print("   mudou) e re-extrair com o campo `parado_por_futilidade`.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
