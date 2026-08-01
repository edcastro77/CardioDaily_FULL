"""
prova_classificador.py — PROVA·2 · o EXPERIMENTO (31/Jul/2026).

DESENHO (proposto pelo Dr. Eduardo: "rodar os artigos em ocasiões repetidas para ver o que ocorre"):
  cada artigo é lido por VÁRIOS MODELOS, VÁRIAS VEZES cada. Isso separa três coisas que estavam
  misturadas e por isso ninguém conseguia consertar nada:

    • REPETIBILIDADE  — mesmo modelo, mesmo artigo, N vezes → ele é ESTÁVEL?
    • CONCORDÂNCIA    — modelos diferentes, mesmo artigo    → eles veem a MESMA coisa?
    • ACURÁCIA        — contra o gabarito do Dr. Eduardo    → está CERTO?

  Confiabilidade não é validade: um modelo pode ser perfeitamente reprodutível e perfeitamente
  errado. Por isso as três medidas andam juntas, e por isso o gabarito.py não é opcional.

O QUE MUDA EM RELAÇÃO AO CLASSIFICADOR DE HOJE (as duas causas medidas dos 11 erros):
  1. Lê PÁGINAS 1–3, não a página 1. Medido em 158 PDFs: no ESC o rótulo sobe de 23 % → 92 %,
     porque a página 1 do Oxford Academic é CAPA (177–470 caracteres).
  2. Exige FRASE DE PROVA: o modelo precisa citar o trecho do artigo que sustenta a resposta.
     Resposta sem prova é descartada. Mata o "achismo" silencioso.

GARANTIA DE ISOLAMENTO: não importa publicador, não move PDF, não renomeia, não fala com o
Supabase. Só lê PDF, chama LLM e escreve CSV em outputs/PROVA/.

RETOMÁVEL (sem marcador, como manda a casa): o CSV é a memória. Ao reiniciar, o que já está
gravado não é refeito. Se a net cair, clica de novo.

Uso:
  python src/prova_classificador.py --max 10                    # piloto barato
  python src/prova_classificador.py --rodadas 3                 # a prova inteira
  python src/prova_classificador.py --modelos gpt-5.6-luna,claude-haiku-4-5-20251001
"""
import os
import re
import csv
import sys
import glob
import time
import argparse
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import fitz
from dotenv import load_dotenv

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
sys.path.insert(0, _HERE)
load_dotenv(os.path.join(_ROOT, ".env"), override=True)

import modelos as M  # noqa: E402

BASE = os.path.join(_ROOT, "ARTIGOS", "CLASSIFICADOS")
SAIDA = os.path.join(_ROOT, "outputs", "PROVA")
CSV_BRUTO = os.path.join(SAIDA, "prova_bruta.csv")

PASTA_TIPO = {
    "ARTIGOS_ORIGINAIS": "artigo_original",
    "META_ANALISES": "revisao_sistematica_meta_analise",
    "REVISOES": "revisao_geral",
    "GUIDELINES": "guideline",
    "EDITORIAIS": "ponto_de_vista",
    "MINIRREVISOES": "minirevisao",
}

# Os 3 juízes. Preço/M tokens de entrada em 31/07/2026: Luna 0,20 · Haiku 1,00 · Sonnet 2,00.
MODELOS_PADRAO = ["gpt-5.6-luna", "claude-haiku-4-5-20251001", "claude-sonnet-5"]
PRECO_ENTRADA = {"gpt-5.6-luna": 0.20, "gpt-5.6-terra": 2.00, "gpt-5.6-sol": 5.00,
                 "claude-haiku-4-5-20251001": 1.00, "claude-sonnet-5": 2.00, "claude-opus-5": 15.00}
PRECO_SAIDA = {"gpt-5.6-luna": 1.20, "gpt-5.6-terra": 12.00, "gpt-5.6-sol": 25.00,
               "claude-haiku-4-5-20251001": 5.00, "claude-sonnet-5": 10.00, "claude-opus-5": 75.00}

# ─────────────────────────── O PROMPT ───────────────────────────
# VERSÃO DO PROMPT — entra na chave de retomada. Sem isto, mudar o prompt e rodar de novo NÃO
# refaz nada (o CSV acha que já foi feito) e a comparação entre versões fica impossível.
#   v1 (31/07, 1ª prova, 999 julgamentos): Luna 91,9 % · Sonnet 90,1 % · Haiku 89,2 %
#       (com opiniao≡minirevisao). Erros residuais: case-based virando relato_de_caso (5),
#       narrativa virando sistemática (2).
#   v2 (31/07): case-based educacional = minirevisao · TRAVA da revisão sistemática.
#       Luna 110/111 = 99,1 %. Consertou os 5 "Protected PCI", o Agentic AI e o JAMA Dyslipidemia.
#       (2 dos 3 "erros" eram do GABARITO: os artigos DECLARAVAM PRISMA — corrigido no gabarito.)
#       Único erro restante = REGRESSÃO minha: "JACC STATE-OF-THE-ART REVIEW" virou minirevisao,
#       porque eu ampliei minirevisao sem dizer que o RÓTULO IMPRESSO tem precedência.
#   v3 (31/07): rótulo impresso de seção vence a impressão de "parece opinião".
PROMPT_VERSAO = "v3"
# DECISÃO D-01 do Dr. Eduardo (31/07): revisão sistemática = meta-análise, mesma trilha.
# O prompt ANTIGO mandava o contrário ("se parecer revisão sistemática, escolha revisao_geral").
PROMPT = """Você classifica o TIPO de um artigo científico de cardiologia. Abaixo estão as
primeiras páginas do PDF, como saíram do arquivo (pode vir capa, cabeçalho e texto misturado).

Responda EXATAMENTE em três linhas, nada mais:
TIPO: <uma palavra da lista>
CONFIANCA: alta | media | baixa
PROVA: <trecho LITERAL do texto abaixo que sustenta sua resposta, até 20 palavras>

LISTA DE TIPOS:
- artigo_original — coleta dados primários em sujeitos. Inclui RCT, coorte, caso-controle,
  transversal, registro, e também estudos de modelagem/custo-efetividade construídos sobre dados.
  Sinais: "we enrolled/recruited N patients", "randomly assigned", regressão, Cox, HR, NCT.
- revisao_sistematica_meta_analise — revisão SISTEMÁTICA (com ou sem meta-análise) e meta-análise.
  Sinais: busca em bases declarada, PRISMA, fluxograma de seleção, estimativa agrupada, I².
- revisao_geral — revisão NARRATIVA / state-of-the-art / educacional. Sem busca sistemática.
- guideline — diretriz, consenso, position paper, scientific statement de sociedade
  (AHA/ACC/ESC/SBC). Sinais: classe de recomendação, nível de evidência, "writing committee".
- ponto_de_vista — editorial, comentário editorial, viewpoint, perspectiva.
- minirevisao — texto CURTO de especialista atualizando um tema ou comentando um estudo, típico de
  suplemento de congresso (European Heart Journal Supplements, "The Heart of the Matter") ou de
  seção editorial de revista. **INCLUI as discussões de caso com FIM EDUCACIONAL** — "case-based
  review", "a clinical case-based discussion", "an illustrative case highlighting patient selection".
  Nessas, o caso é PRETEXTO para ensinar conduta: isso é minirevisao, NÃO relato_de_caso.
- relato_de_caso — relato de UM caso publicado como "Case Report" da revista, com o objetivo de
  descrever o caso em si (achado raro, complicação inédita, técnica nova em um paciente).
- carta_de_pesquisa — research letter / carta ao editor (formato breve).
- incerto — se o texto abaixo NÃO permitir decidir com segurança.

REGRAS QUE VALEM MAIS QUE A SUA IMPRESSÃO:
1. O RÓTULO DE SEÇÃO IMPRESSO PELA REVISTA MANDA, e manda acima de tudo. Se ele aparecer no texto,
   ele DECIDE — mesmo que o artigo "pareça" outra coisa, mesmo que seja curto, opinativo ou
   assinado por poucos autores. Correspondência obrigatória:
     ORIGINAL RESEARCH ARTICLE · ORIGINAL ARTICLE · ORIGINAL INVESTIGATION · CLINICAL RESEARCH
        → artigo_original
     STATE-OF-THE-ART REVIEW · REVIEW ARTICLE · JACC REVIEW TOPIC OF THE WEEK · IN DEPTH · FRONTIERS
        → revisao_geral   (NUNCA minirevisao — por mais que o texto pareça ensaio de opinião)
     AHA SCIENTIFIC STATEMENT · SCIENTIFIC STATEMENT · CLINICAL PRACTICE GUIDELINE · CONSENSUS
     DOCUMENT · POSITION PAPER  → guideline
     THE HEART OF THE MATTER  → minirevisao
     EDITORIAL · EDITORIAL COMMENT · VIEWPOINT  → ponto_de_vista
   Só use o julgamento dos itens 2 a 5 quando NÃO houver rótulo impresso.
2. Se não houver rótulo, o juiz é o METHODS: quem COLETA dado de paciente é artigo_original;
   quem BUSCA estudos em base é revisao_sistematica_meta_analise; quem não faz nem um nem outro
   é revisao_geral ou guideline.
3. CITAR não é SER. Um artigo que MENCIONA "meta-analysis" ou "guideline" no texto não vira
   meta-análise nem diretriz. Só o que o artigo É conta.
4. TRAVA DA REVISÃO SISTEMÁTICA — só responda revisao_sistematica_meta_analise se o artigo
   DECLARAR pelo menos um destes: busca nomeando bases (PubMed, Embase, Cochrane, Web of Science);
   critérios de elegibilidade/inclusão e exclusão; número de estudos incluídos; fluxograma PRISMA;
   estimativa agrupada (pooled) ou I². **Se nada disso aparecer, é revisao_geral** — por mais
   completa, longa ou "abrangente" que a revisão pareça. Revisão narrativa boa continua narrativa.
5. Se o texto abaixo for só capa (título, autores, "Downloaded from…") sem abstract nem methods,
   responda incerto — NÃO adivinhe.

TEXTO (páginas 1 a 3):
{texto}
"""

_RE_TIPO = re.compile(r"TIPO:\s*([a-z_]+)", re.I)
_RE_CONF = re.compile(r"CONFIANCA:\s*(alta|m[eé]dia|media|baixa)", re.I)
_RE_PROVA = re.compile(r"PROVA:\s*(.+)", re.I | re.S)
_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_TIPOS = {"artigo_original", "revisao_sistematica_meta_analise", "revisao_geral", "guideline",
          "ponto_de_vista", "minirevisao", "relato_de_caso", "carta_de_pesquisa", "incerto"}

_lock = threading.Lock()
_uso = {}


def paginas_1a3(caminho):
    doc = fitz.open(caminho)
    return _CTRL.sub("", "".join(doc[i].get_text() for i in range(min(3, len(doc)))))


# ─────────────────────────── as chamadas ───────────────────────────
def _anthropic(modelo, prompt):
    import anthropic
    cli = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY", ""))
    kw = M.temp_kwargs(modelo, 0)          # temperature 0 onde o modelo aceita (Haiku aceita; Sonnet 5 não)
    r = cli.messages.create(model=modelo, max_tokens=700,
                            messages=[{"role": "user", "content": prompt}], **kw)
    txt = "".join(b.text for b in r.content if getattr(b, "type", "") == "text")
    return txt, r.usage.input_tokens, r.usage.output_tokens


def _openai(modelo, prompt):
    from openai import OpenAI
    cli = OpenAI(api_key=os.getenv("OPENAI_API_KEY", ""))
    kw = M.temp_kwargs(modelo, 0)
    r = cli.chat.completions.create(model=modelo, max_completion_tokens=700,
                                    messages=[{"role": "user", "content": prompt}], **kw)
    u = r.usage
    return (r.choices[0].message.content or ""), u.prompt_tokens, u.completion_tokens


def chamar(modelo, prompt):
    """Uma tentativa por modelo, com retry em erro transitório. SEM cadeia de fallback:
    a prova compara MODELOS — deixar outro responder no lugar falsearia o experimento."""
    fn = {"anthropic": _anthropic, "openai": _openai}.get(M.provedor(modelo))
    if fn is None:
        raise RuntimeError(f"provedor não suportado na prova: {modelo}")
    ultimo = None
    for tentativa in (1, 2, 3):
        try:
            return fn(modelo, prompt)
        except Exception as e:
            ultimo = e
            s = str(e).lower()
            if any(k in s for k in ("429", "rate", "overload", "timeout", "connection", "503", "500")):
                time.sleep(4 * tentativa)
                continue
            raise
    raise ultimo


def julgar(modelo, texto):
    saida, tin, tout = chamar(modelo, PROMPT.format(texto=texto[:20000]))
    with _lock:
        d = _uso.setdefault(modelo, [0, 0])
        d[0] += tin
        d[1] += tout
    mt = _RE_TIPO.search(saida)
    tipo = (mt.group(1).lower() if mt else "")
    if tipo not in _TIPOS:                                  # rede de segurança: varre a resposta
        tipo = next((t for t in _TIPOS if t in saida.lower()), "PARSE_FALHOU")
    mc = _RE_CONF.search(saida)
    mp = _RE_PROVA.search(saida)
    prova = _CTRL.sub("", (mp.group(1) if mp else "")).strip().replace("\n", " ")[:160]
    return {
        "tipo": tipo,
        "confianca": (mc.group(1).lower().replace("é", "e") if mc else ""),
        "prova": prova,
        "tem_prova": "sim" if len(prova) >= 12 else "NAO",   # resposta sem prova não vale
        "tokens_in": tin, "tokens_out": tout,
    }


# ─────────────────────────── o laço ───────────────────────────
CAMPOS = ["arquivo", "pasta_hoje", "classificador_disse", "modelo", "rodada", "prompt",
          "tipo", "confianca", "tem_prova", "prova", "tokens_in", "tokens_out", "erro"]


def _migrar_cabecalho():
    """BUG real de 31/07, que custou uma rodada paga: acrescentei a coluna 'prompt' ao CAMPOS,
    mas o CSV em disco tinha o cabeçalho ANTIGO. O DictWriter passou a gravar 13 valores num
    arquivo cujo cabeçalho declarava 12 → toda linha nova ficou DESLOCADA (o 'v2' caiu na coluna
    'tipo'). Nada se perdeu, mas o placar leu lixo.
    Agora: se o cabeçalho do disco não bate com o CAMPOS de hoje, o arquivo é MIGRADO antes de
    escrever qualquer coisa. Regra geral: nunca append em CSV sem conferir o cabeçalho."""
    if not (os.path.exists(CSV_BRUTO) and os.path.getsize(CSV_BRUTO)):
        return
    with open(CSV_BRUTO, encoding="utf-8-sig", newline="") as fh:
        linhas = list(csv.reader(fh))
    if not linhas or linhas[0] == CAMPOS:
        return
    velho = linhas[0]
    dados = []
    for r in linhas[1:]:
        d = dict(zip(velho, r))
        d.setdefault("prompt", "v1")                 # o que foi rodado antes da coluna existir
        dados.append([d.get(c, "") for c in CAMPOS])
    with open(CSV_BRUTO, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(CAMPOS)
        w.writerows(dados)
    print(f"  (cabeçalho do CSV migrado: {len(velho)} → {len(CAMPOS)} colunas · "
          f"{len(dados)} linhas preservadas)")


def _ja_feito():
    """A memória do experimento é o próprio CSV (estado FÍSICO, sem marcador).
    A VERSÃO DO PROMPT entra na chave: prompt novo = trabalho novo, e as duas versões
    convivem no mesmo arquivo para poder comparar v1 × v2."""
    _migrar_cabecalho()
    feitos = set()
    if os.path.exists(CSV_BRUTO) and os.path.getsize(CSV_BRUTO):
        with open(CSV_BRUTO, encoding="utf-8-sig") as fh:
            for l in csv.DictReader(fh):
                feitos.add((l["arquivo"], l["modelo"], l["rodada"], l.get("prompt") or "v1"))
    return feitos


def _pdfs(max_n=0):
    fs = []
    for pasta in PASTA_TIPO:
        for f in sorted(glob.glob(os.path.join(BASE, pasta, "*.pdf"))):
            if not os.path.basename(f).startswith("._"):
                fs.append((pasta, f))
    if max_n:
        passo = max(1, len(fs) // max_n)          # amostra ESPALHADA nas pastas, não só as primeiras
        fs = fs[::passo][:max_n]
    return fs


def main():
    ap = argparse.ArgumentParser(description="PROVA do classificador: N modelos × N rodadas")
    ap.add_argument("--modelos", default=",".join(MODELOS_PADRAO))
    ap.add_argument("--rodadas", type=int, default=3)
    ap.add_argument("--max", type=int, default=0, help="amostra de N artigos (piloto)")
    ap.add_argument("--paralelo", type=int, default=6)
    a = ap.parse_args()

    modelos = [m.strip() for m in a.modelos.split(",") if m.strip()]
    os.makedirs(SAIDA, exist_ok=True)
    pdfs = _pdfs(a.max)
    if not pdfs:
        print(f"Nenhum PDF em {BASE}"); return 1

    feitos = _ja_feito()
    tarefas = [(p, f, m, r) for (p, f) in pdfs for m in modelos for r in range(1, a.rodadas + 1)
               if (os.path.basename(f), m, str(r), PROMPT_VERSAO) not in feitos]

    total = len(pdfs) * len(modelos) * a.rodadas
    print(f"\nPROVA DO CLASSIFICADOR · somente leitura (não move arquivo, não toca no Supabase)")
    print(f"  prompt {PROMPT_VERSAO}")
    print(f"  {len(pdfs)} artigo(s) × {len(modelos)} modelo(s) × {a.rodadas} rodada(s) = {total} julgamentos")
    print(f"  já gravados: {total - len(tarefas)} · a fazer: {len(tarefas)}")
    print(f"  modelos: {' · '.join(modelos)}\n")
    if not tarefas:
        print("Nada a fazer — a prova já está completa. Rode o placar.py."); return 0

    cache = {}
    # BUG corrigido 31/07: era `not os.path.exists(...)`. Arquivo ZERADO (0 byte) existe, então o
    # cabeçalho não era escrito e o placar quebrava com KeyError. O critério é TAMANHO, não existência.
    novo = (not os.path.exists(CSV_BRUTO)) or os.path.getsize(CSV_BRUTO) == 0
    fh = open(CSV_BRUTO, "a", newline="", encoding="utf-8-sig")
    w = csv.DictWriter(fh, fieldnames=CAMPOS)
    if novo:
        w.writeheader()

    def tarefa(t):
        pasta, caminho, modelo, rodada = t
        nome = os.path.basename(caminho)
        with _lock:
            texto = cache.get(caminho)
        if texto is None:
            texto = paginas_1a3(caminho)
            with _lock:
                cache[caminho] = texto
        linha = {"arquivo": nome, "pasta_hoje": pasta, "classificador_disse": PASTA_TIPO[pasta],
                 "modelo": modelo, "rodada": rodada, "prompt": PROMPT_VERSAO, "erro": ""}
        try:
            linha.update(julgar(modelo, texto))
        except Exception as e:
            linha.update({"tipo": "ERRO", "erro": f"{type(e).__name__}: {str(e)[:120]}"})
        return linha

    feito = 0
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=a.paralelo) as ex:
        futs = {ex.submit(tarefa, t): t for t in tarefas}
        for fu in as_completed(futs):
            linha = fu.result()
            with _lock:
                w.writerow(linha)
                fh.flush()                       # grava JÁ: se cair, não se perde o que foi pago
            feito += 1
            marca = "❌" if linha["tipo"] in ("ERRO", "PARSE_FALHOU") else \
                    ("⚠️" if linha.get("tem_prova") == "NAO" else "✅")
            if feito % 10 == 0 or marca != "✅":
                print(f"  [{feito}/{len(tarefas)}] {marca} {linha['modelo'][:22]:23} "
                      f"r{linha['rodada']} {linha['tipo'][:28]:29} {linha['arquivo'][:40]}"
                      + (f"  {linha['erro']}" if linha["erro"] else ""))
    fh.close()

    print(f"\n{'─' * 70}\nCUSTO REAL desta rodada ({time.time() - t0:.0f}s):")
    tot = 0.0
    for mod, (ti, to) in sorted(_uso.items()):
        c = ti / 1e6 * PRECO_ENTRADA.get(mod, 0) + to / 1e6 * PRECO_SAIDA.get(mod, 0)
        tot += c
        print(f"  {mod:28} entrada {ti:>9,} · saída {to:>7,} → US$ {c:.4f}")
    print(f"  {'TOTAL':28} {'':>30} → US$ {tot:.4f}")
    print(f"\n→ {CSV_BRUTO}\nAgora: python src/placar.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
