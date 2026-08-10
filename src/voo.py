"""
voo.py — O PLANO DE VOO DO CARDIODAILY.

═══════════════════════════════════════════════════════════════════════════════════════
A IDEIA, NAS PALAVRAS DO DR. EDUARDO (09/Ago/2026)
═══════════════════════════════════════════════════════════════════════════════════════

    "Os aviões, quando decolam, a cada 250 quilômetros têm que se comunicar com um radar
     específico — 'olha, eu tô aqui'. Um avião que sai do Brasil para Paris não pode andar
     2.000 quilômetros sem dizer onde está. Se ele não se comunica com o próximo radar,
     AQUELE TRECHO em que ele deveria se comunicar e não se comunicou vai ser investigado.
     Se for no meio do oceano, já se sabe qual região varrer, que marés passam por ali,
     onde procurar destroços."

E o diagnóstico dele, que é o que este arquivo existe para resolver:

    "Enquanto a gente não atacar o problema certo, vai fazer programas fantásticos que não
     resolvem nada. Enquanto não atacarmos o problema certo, não saímos do lugar."

Ele tinha razão, e a prova apareceu no mesmo dia: eu auditei 269 artigos "rejeitados" lendo
arquivos de motivo de rodadas ANTIGAS, sem perguntar se aquela versão ainda era a que valia.
90 daqueles artigos já estavam publicados. Não errei por falta de capacidade — errei porque
**não havia waypoint**: nada no sistema dizia "este trecho é o atual".

═══════════════════════════════════════════════════════════════════════════════════════
O QUE MUDA
═══════════════════════════════════════════════════════════════════════════════════════

Hoje o CardioDaily tem 22 pontos onde falha em silêncio (mapeados em 09/Ago). O padrão é
sempre o mesmo: a etapa não consegue, devolve vazio, e o programa segue como se nada tivesse
acontecido. O pior deles é um `except Exception: pass` em volta do CÁLCULO DA NOTA
(`ficha_site.py:230`), que desliga de uma vez a exceção da diretriz e a trava de inversão
de fração de ejeção.

A partir daqui, cada etapa crítica **marca posição**. Se a marca não existe, não se pergunta
"será que deu certo?" — sabe-se EM QUE TRECHO procurar, e cada trecho tem a sua zona de busca.

    de:   "o Radar não veio hoje. Por quê? Falha do GitHub? Não pagou? O que aconteceu?"
    para: "o Radar de 09/Ago passou por E1 e não chegou em E2.
           Zona de busca do trecho E1→E2: crédito acabado · credencial · TTS · rede."

E foi exatamente isso: em 09/Ago o Radar não chegou porque **a assinatura do fornecedor
tinha esgotado os créditos**, e ele renovaria no dia seguinte. Uma causa banal, que hoje
custa uma investigação e amanhã custa uma consulta.

═══════════════════════════════════════════════════════════════════════════════════════
TRÊS REGRAS QUE ESTE ARQUIVO NUNCA QUEBRA
═══════════════════════════════════════════════════════════════════════════════════════

1. **NUNCA levanta exceção.** O registro não pode derrubar a corrida. Um avião não cai
   porque o rádio quebrou. Todo `marcar()` está dentro de try/except que engole tudo.
2. **NUNCA chama rede nem banco.** É um append num arquivo local. Se a rede é o problema,
   o registro tem de funcionar mesmo assim — senão ele some justo quando é necessário.
3. **APPEND-ONLY.** Nada é reescrito. O `voo.jsonl` é a caixa-preta: só cresce, e a
   verdade de ontem continua lá quando a de hoje mudar. Foi a falta disso que me fez ler
   o passado achando que era o presente.
"""
import os
import json
import time
import datetime

_HERE = os.path.dirname(os.path.abspath(__file__))
VOO = os.path.join(os.path.dirname(_HERE), "outputs", "voo.jsonl")

# ═══════════════════════════════════════════════════════════════════════════════════════
# OS WAYPOINTS — o plano de voo de cada bloco, em ordem
# ═══════════════════════════════════════════════════════════════════════════════════════
#
# A ordem importa: é ela que define o TRECHO. Se o último waypoint marcado foi o C3 e o
# plano previa C4, o trecho investigado é C3→C4 — e não o voo inteiro.
#
# Cada linha: (código, o que significa, o que a etapa tem de registrar quando dá certo)

PLANO = {
    "CLASSIFICADOR": [
        ("C1_TEXTO",   "o texto foi extraído do PDF",            "n_chars"),
        ("C2_DOI",     "o DOI foi encontrado no texto",          "doi"),
        ("C3_PUBMED",  "o PubMed respondeu sobre este DOI",      "pubtypes"),
        ("C4_DECIDIU", "uma camada da cascata decidiu o tipo",   "camada, tipo"),
        ("C5_MOVEU",   "o PDF foi para a pasta do tipo",         "destino"),
        ("C6_DIARIO",  "o CSV da rodada foi gravado",            "linhas"),
    ],
    "ANALISADOR": [
        ("A1_FATOS",   "os FATOS foram extraídos do PDF",        "tipo_documento, n_campos"),
        ("A2_NOTA",    "o motor calculou a nota",                "nota, motor"),
        ("A3_PECAS",   "as peças da porta foram geradas",        "pecas"),
        ("A4_OK",      "o pacote passou na conferência (_OK)",   "—"),
    ],
    "PUBLICADOR": [
        ("P1_FICHA",   "a ficha foi montada a partir do disco",  "doc_id"),
        ("P2_CONTRATO","o contrato validou (ou recusou)",        "violacoes"),
        ("P3_MIDIA",   "a mídia subiu para o Storage",           "quais"),
        ("P4_BANCO",   "a linha entrou na tabela artigos",       "http"),
    ],
    "ENTREGA": [
        ("E1_RADAR",   "o Radar do dia foi gerado",              "tema, n_artigos"),
        ("E2_AUDIO",   "o áudio subiu para o bucket",            "url"),
        ("E3_REGISTRO","a linha entrou na tabela radar",         "http"),
        ("E4_LISTA",   "a lista de envio foi montada",           "n_artigos, n_destinos"),
        ("E5_ENVIOU",  "a mensagem saiu para os destinatários",  "n_ok, n_falha"),
    ],
}

# ═══════════════════════════════════════════════════════════════════════════════════════
# A ZONA DE BUSCA — as causas conhecidas de CADA trecho
# ═══════════════════════════════════════════════════════════════════════════════════════
#
# É a parte mais importante do arquivo, e a mais parecida com a analogia dele: quando um
# avião some entre dois waypoints, não se procura no oceano inteiro. Sabe-se a região, as
# correntes, o que esperar.
#
# Cada entrada responde: "o voo parou AQUI. Onde eu procuro, e o que eu espero encontrar?"
# A lista é ORDENADA por probabilidade — a causa mais comum primeiro.

ZONA_DE_BUSCA = {
    "C1_TEXTO": [
        "PDF é imagem escaneada, sem camada de texto (precisa de OCR)",
        "PDF protegido por senha ou corrompido no download",
        "arquivo com extensão .pdf que não é PDF",
    ],
    "C2_DOI": [
        "artigo antigo, anterior ao DOI (Framingham 1962, NEJM dos anos 90)",
        "documento de sociedade que não usa DOI (NICE, KDIGO, diretriz brasileira)",
        "o DOI está só na primeira página e o texto veio truncado",
    ],
    "C3_PUBMED": [
        "rede caiu ou o NCBI está fora (429 / 5xx / timeout)",
        "DOI válido mas não indexado no PubMed (preprint, revista local)",
        "DOI 'emprestado' — o texto trouxe o DOI de uma referência, não o do artigo",
    ],
    "C4_DECIDIU": [
        "SEM CRÉDITO no fornecedor do modelo — o juiz LLM não respondeu",
        "chave de API ausente ou expirada no .env",
        "as páginas 1-3 vieram vazias (ver C1)",
        "o modelo respondeu fora do formato e o parse não reconheceu",
    ],
    "C5_MOVEU": [
        "permissão de escrita na pasta de destino",
        "disco cheio",
        "arquivo aberto em outro programa (Preview, Adobe)",
    ],
    "C6_DIARIO": [
        "a rodada abortou ANTES do fim — o CSV só é escrito no final",
        "permissão de escrita na pasta ARTIGOS",
    ],
    "A1_FATOS": [
        "SEM CRÉDITO no fornecedor do modelo",
        "PDF grande demais: o texto foi truncado em 600.000 caracteres",
        "a saída estruturada (tool use) caiu e o modo texto não devolveu JSON válido",
        "o tipo do documento não casou com nenhum schema",
    ],
    "A2_NOTA": [
        "os FATOS vieram sem campo obrigatório (o motor levanta)",
        "tipo_documento desconhecido — caiu no motor errado",
    ],
    "A3_PECAS": [
        "SEM CRÉDITO no fornecedor do modelo",
        "TTS falhou (áudio) — chave da OpenAI ou limite de caracteres",
        "WeasyPrint quebrou no PDF (fonte ausente, HTML malformado)",
        "Playwright não subiu (Visual Abstract)",
        "a peça saiu curta demais e o piso de tamanho reprovou",
    ],
    "A4_OK": [
        "uma peça da porta não existe ou ficou abaixo do tamanho mínimo",
    ],
    "P1_FICHA": [
        "o canônico não existe ou está sem o frontmatter",
        "o nome da pasta não segue AAAA-MM-Revista-Titulo (capa vazia)",
    ],
    "P2_CONTRATO": [
        "nota <6 — retenção por regra (LEI 10), não é defeito",
        "campo do ACRI vazio (contexto_tema, impacto_conduta, gancho_lista)",
        "inversão de fração de ejeção: o texto trocou ICFEr por ICFEp",
        "tema fora da lista do site",
    ],
    "P3_MIDIA": [
        "rede caiu no meio do upload (BrokenPipe, SSLError) — o arquivo é grande",
        "credencial do Supabase ausente",
        "o arquivo local não existe (a peça não foi gerada)",
        "bucket não existe ou mudou de nome",
    ],
    "P4_BANCO": [
        "coluna NOT NULL sem valor (23502) — ex.: documento sem DOI",
        "violação de chave única (doi ou doc_id duplicado)",
        "credencial do Supabase expirada",
        "rede",
    ],
    "E1_RADAR": [
        "SEM CRÉDITO no fornecedor do modelo — a causa de 09/Ago/2026",
        "chave de API ausente no GitHub Secrets",
        "o PubMed não devolveu artigos para o tema do dia",
        "o workflow não disparou (cron do GitHub atrasa ou pula)",
    ],
    "E2_AUDIO": [
        "SEM CRÉDITO no fornecedor de TTS",
        "bucket com nome diferente entre quem grava e quem lê",
        "credencial do Storage ausente",
    ],
    "E3_REGISTRO": [
        "credencial do Supabase ausente",
        "a coluna caminho_podcast ficou vazia porque o upload falhou (ver E2)",
    ],
    "E4_LISTA": [
        "os temas do filtro não existem no banco (vocabulários diferentes)",
        "nenhum artigo novo com nota acima do corte no período",
        "o Supabase respondeu erro e a lista veio vazia sem avisar",
    ],
    "E5_ENVIOU": [
        "Z-API sem crédito ou instância desconectada",
        "BETA_PAUSADO=1 — envia só para o número do dono (default do sistema)",
        "a lista de assinantes veio vazia porque o banco não respondeu",
    ],
}


def _corrida():
    """Um identificador por EXECUÇÃO, para agrupar os waypoints de uma mesma rodada.
    Herdado por variável de ambiente quando um programa chama outro (a Chave 2 chama o
    publicador), para que o voo inteiro fique costurado numa linha só."""
    c = os.environ.get("CD_CORRIDA")
    if not c:
        c = f"{datetime.datetime.now():%Y%m%d-%H%M%S}-{os.getpid()}"
        os.environ["CD_CORRIDA"] = c
    return c


# ═══════════════════════════════════════════════════════════════════════════════════════
# MODO ENSAIO — SIMULAÇÃO NÃO ESCREVE NO PLANO DE VOO (10/Ago/2026)
# ═══════════════════════════════════════════════════════════════════════════════════════
#
# O `ensaio_seco.py` existe para responder "o que aconteceria SE eu rodasse", de graça e sem
# efeito nenhum. Para simular, ele chama `ficha_site.montar()` — que marca `P1_FICHA`.
# Ou seja: toda vez que eu rodava o ensaio, o registro ganhava uma marca de PRODUÇÃO que
# nunca aconteceu.
#
# Medido na rodada de 10/Ago: P1_FICHA com **222 marcas para 119 artigos**. Um artigo cuja
# história real era `A1→A2→A3→A4→P1→P2 (recusado, nota 4)` aparecia na caixa-preta com onze
# marcas de P1 DEPOIS do P2 — e, como ela olha a ÚLTIMA marca, era relatado como "parado no
# P1_FICHA", com zona de busca e tudo. O artigo tinha chegado ao P2 às 23:49; as marcas
# posteriores eram minhas, do ensaio.
#
# É a versão mais traiçoeira do problema: o OBSERVADOR alterando o observado. O ensaio é a
# ferramenta que eu uso justamente para não fazer o Dr. Eduardo gastar — e ela estava
# adulterando a única prova de onde os artigos param.
#
# Quem simula chama `voo.silenciar()` no começo. Nada mais muda: as mesmas funções, os mesmos
# caminhos de código, só que a escrita vira no-op.
_SILENCIO = [False]


def silenciar(sim=True):
    """Desliga a gravação. Para SIMULAÇÃO (ensaio_seco, testes) — nunca para produção."""
    _SILENCIO[0] = bool(sim)


def silenciado():
    return _SILENCIO[0]


def marcar(wp, ok=True, artigo=None, erro=None, **dados):
    """Marca posição. É a única função que os programas do CardioDaily chamam.

    NUNCA levanta exceção e NUNCA fala com a rede — um avião não cai porque o rádio quebrou.

        marcar("C1_TEXTO", n_chars=48213, artigo="2026-07-JAMA-Coffee")
        marcar("C3_PUBMED", ok=False, erro="HTTP 429", artigo=base)

    `erro` é o que se procura depois: guarde a mensagem REAL, não um resumo. Foi um corte
    de 60 caracteres numa mensagem de erro que transformou um diagnóstico de dez segundos
    em 232 linhas idênticas na tela (07/Ago).
    """
    if _SILENCIO[0]:
        return                      # simulação: não sujar o registro de voo (ver acima)
    try:
        linha = {
            "t": datetime.datetime.now().isoformat(timespec="seconds"),
            "corrida": _corrida(),
            "wp": wp,
            "ok": bool(ok),
        }
        if artigo:
            linha["artigo"] = str(artigo)[:120]
        if erro:
            linha["erro"] = str(erro)[:400]
        for k, v in dados.items():
            if isinstance(v, (str, int, float, bool)) or v is None:
                linha[k] = v if not isinstance(v, str) else v[:200]
            else:
                linha[k] = str(v)[:200]
        os.makedirs(os.path.dirname(VOO), exist_ok=True)
        with open(VOO, "a", encoding="utf-8") as f:
            f.write(json.dumps(linha, ensure_ascii=False) + "\n")
    except Exception:
        pass          # o registro jamais derruba a corrida. É a regra 1.


def ler(desde_horas=None, corrida=None):
    """Lê o voo.jsonl. `desde_horas=24` traz só o último dia."""
    linhas = []
    try:
        if not os.path.exists(VOO):
            return []
        corte = None
        if desde_horas:
            corte = datetime.datetime.now() - datetime.timedelta(hours=desde_horas)
        with open(VOO, encoding="utf-8") as f:
            for l in f:
                l = l.strip()
                if not l:
                    continue
                try:
                    d = json.loads(l)
                except Exception:
                    continue
                if corrida and d.get("corrida") != corrida:
                    continue
                if corte:
                    try:
                        if datetime.datetime.fromisoformat(d["t"]) < corte:
                            continue
                    except Exception:
                        pass
                linhas.append(d)
    except Exception:
        pass
    return linhas


def bloco_do_waypoint(wp):
    """A qual bloco este waypoint pertence."""
    for bloco, wps in PLANO.items():
        if any(w[0] == wp for w in wps):
            return bloco
    return None


def proximo_waypoint(wp):
    """O waypoint seguinte no plano — o destino que não foi alcançado."""
    for wps in PLANO.values():
        codigos = [w[0] for w in wps]
        if wp in codigos:
            i = codigos.index(wp)
            return codigos[i + 1] if i + 1 < len(codigos) else None
    return None


def zona_de_busca(wp_ultimo, ok_ultimo=True, wp_esperado=None):
    """As causas conhecidas. É a 'região do oceano' da analogia — e há DOIS casos.

    ═══ 09/Ago — O DEFEITO QUE APARECEU NO PRIMEIRO TESTE ═══
    A primeira versão sempre procurava o waypoint SEGUINTE. Simulando o Radar de 09/Ago
    (`E1_RADAR` com `ok=False` e a mensagem "429 quota exceeded"), a resposta veio com a
    zona do E2 — "bucket com nome diferente", "credencial do Storage". Tudo irrelevante:
    o avião não sumiu depois do waypoint, ele **reportou emergência NO waypoint**.

    Na aviação são situações distintas, e a busca é distinta:

        SILÊNCIO   — o último contato foi no C3 e o C4 nunca veio.
                     Procura-se no trecho C3→C4, com as causas do C4.
        EMERGÊNCIA — o C3 reportou falha, com mensagem.
                     Procura-se NO C3, com as causas do C3 — e a mensagem já é a pista.

    Devolve (descrição do trecho, [causas ordenadas por probabilidade]).
    """
    if not ok_ultimo:
        return (f"falha reportada em {wp_ultimo}", ZONA_DE_BUSCA.get(wp_ultimo, []))
    alvo = wp_esperado or proximo_waypoint(wp_ultimo)
    if not alvo:
        return (f"{wp_ultimo} → fim do plano", [])
    return (f"silêncio entre {wp_ultimo} e {alvo}", ZONA_DE_BUSCA.get(alvo, []))


def descricao(wp):
    """O que este waypoint significa, em português."""
    for wps in PLANO.values():
        for codigo, texto, _ in wps:
            if codigo == wp:
                return texto
    return wp


if __name__ == "__main__":
    print("═" * 78)
    print(" PLANO DE VOO DO CARDIODAILY")
    print("═" * 78)
    for bloco, wps in PLANO.items():
        print(f"\n   {bloco}")
        for codigo, texto, registra in wps:
            print(f"      {codigo:14s} {texto}")
            if registra != "—":
                print(f"      {'':14s}   registra: {registra}")
    print()
    print("═" * 78)
    n = len(ler())
    print(f"   voo.jsonl: {n} marca(s) registrada(s)   ·   {VOO}")
