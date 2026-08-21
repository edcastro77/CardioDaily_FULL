"""
tema_mesh.py — decide o TEMA de um artigo a partir dos descritores MeSH.

═══ 14/Ago/2026 — POR QUE ISTO EXISTE, E POR QUE NÃO É "ORGANIZAÇÃO" ═══

Palavras do Dr. Eduardo: *"o tema MeSH diz respeito à minha capacidade de disponibilizar
o material correto para quem quer receber mensagens de imagem cardiovascular ou síndrome
metabólica. Então isso não pode esperar."*

Ele está certo e eu tinha posto isto em quarto lugar. O tema NÃO é etiqueta de arquivo:
é a chave de entrega. Sem ele, o assinante que marcou "Imagem Cardiovascular" não recebe
imagem cardiovascular — recebe o que o `ficha_site.KW_TEMA` chutar.

═══ O QUE ISTO SUBSTITUI ═══

`ficha_site._tema()`: 7 grupos de palavras em inglês, testados NA ORDEM em que foram
escritos — o PRIMEIRO grupo que casar vence. Um artigo de obesidade com desfecho coronário
pegava o tema pela posição na lista, não pelo peso. E o último recurso era "Outros".

MEDIDO: a categoria de cardio-obstetrícia do Radar tem 19 termos e pegou **1 artigo em
705**, enquanto 44 artigos falam de gestação. As frases eram compostas ("preeclampsia
cardiovascular") — feitas para o PubMed, que expande com MeSH, e inúteis contra texto.

═══ A REGRA: ESPECIFICIDADE, NÃO CONTAGEM ═══

Um artigo tem ~14 descritores, e vários apontam para temas diferentes. Contar quantos
batem (a ideia inicial do Dr. Eduardo) é melhor que "o primeiro vence", mas ainda erra:
`Cardiovascular Diseases` aparece em 48 artigos e não diz tema nenhum, enquanto
`Cardiomyopathy, Hypertrophic` aparece em 4 e diz tudo.

Então o peso de cada descritor é o INVERSO da frequência dele no acervo — a mesma ideia
do IDF. Descritor raro pesa mais porque é mais específico. É a intuição dele
("quanto mais keywords, mais forte") corrigida pelo que a palavra realmente informa.

⚠️ E o motor DECLARA a margem. Se o primeiro e o segundo tema empatam, ele diz `indeciso`
em vez de escolher pela ordem do dicionário — que foi exatamente o defeito do KW_TEMA.
"""
import json
import math
import os

_AQUI = os.path.dirname(os.path.abspath(__file__))

# ⚠️ ESTE ARQUIVO NÃO TEM LISTA DE TEMAS. Ele importa de `temas.py`.
#
# 17/Ago — eu tinha escrito os 13 aqui TAMBÉM, e a normalização convertia "Valvulopatias"
# (o nome canônico) para "Valvopatias" (o nome velho). Resultado medido: o tema Valvulopatias
# ficou com ZERO artigos, enquanto 35 artigos tinham descritor de valva — eles saíam com um
# rótulo que não existe na lista oficial.
#
# Dois arquivos com a mesma lista, discordando: é LITERALMENTE o defeito que este trabalho
# veio matar, cometido dentro do conserto. Agora existe UM lugar com os temas, e este módulo
# se recusa a devolver rótulo que não esteja lá.
from temas import TEMAS, SEM_TEMA

# só variação de digitação da planilha → o nome canônico. Nada mais mora aqui.
_SINONIMOS = {
    "valvopatias": "Valvulopatias",
    "arritmias": "Arritmias/Anticoagulantes",
    "hipertensão": "Hipertensão/HAS",
    "aorta/congênitas": "Aorta/Congênitas/Genética",
    "cardio-obstétrica": "Cardio-Obstetrícia",
    "cardio metabolica / prevencao": "Cardiometabólica",
}


def normalizar(rotulo):
    """Rótulo da planilha → nome canônico dos 13. Devolve "" se não for um tema válido.

    Devolver "" em vez do texto cru é de propósito: rótulo desconhecido some do placar em
    vez de virar um tema fantasma que ninguém recebe.
    """
    r = (rotulo or "").strip()
    r = _SINONIMOS.get(r.lower(), r)
    return r if r in TEMAS else ""


_ARVORE = _RAMOS = _EXCECOES = None


def _carregar_arvore():
    """Carrega, uma vez, a árvore oficial da NLM e os dois mapas.

    ═══ 21/Ago/2026 — A ÁRVORE DA NLM SUBSTITUI O MAPA À MÃO ═══
    Até aqui o tema saía de `mesh_para_tema.json`: 303 descritores que EU mapeei um a um em
    17/Ago. Media 80 % e errava do jeito que só mapa manual erra — "Prevention of Work-Related
    Musculoskeletal Disorders" caiu em Coronária/DAC porque algum descritor genérico bateu.

    A NLM já tem essa informação, oficial e completa: **a árvore MeSH**, em
    `https://id.nlm.nih.gov/mesh/sparql` (pública, sem chave). Cada descritor sabe onde mora, e
    a posição diz o que ele é. Ergonomia ocupacional não está sob C14; o mapa estrutural não
    comete esse erro.

    Decisão do Dr. Eduardo: *"vale trocar o mapa à mão pela árvore oficial? SIM — faça isso,
    mesmo que custe."*

    TRÊS CAMADAS, e a ordem importa:
      1. EXCEÇÃO por descritor  — a régua CLÍNICA dele, manda mais que tudo
      2. RAMO da árvore         — estrutura oficial da NLM
      3. mapa antigo            — rede, para descritor que ainda não está na árvore baixada
    """
    global _ARVORE, _RAMOS, _EXCECOES
    if _ARVORE is not None:
        return
    d = os.path.join(_AQUI, "dados")

    def _ler(nome):
        # ⚠️ NUNCA em silêncio. Um `except: return {}` mudo aqui faria a árvore inteira sumir
        # sem uma linha de aviso, e o motor cairia no mapa antigo achando que estava tudo bem —
        # a mesma família de defeito do `mesh_de_doi` inventado (20/Ago), que só não custou caro
        # porque foi pego antes de rodar.
        caminho = os.path.join(d, nome)
        try:
            x = json.load(open(caminho, encoding="utf-8"))
            x.pop("_leia", None)
            return x
        except FileNotFoundError:
            print(f"       ⚠️  {nome} não existe — rode scripts/puxar_arvore_mesh.py")
            return {}
        except Exception as e:
            print(f"       ⚠️  {nome} ilegível: {type(e).__name__}: {e}")
            return {}
    _ARVORE = _ler("mesh_arvore.json")
    _RAMOS = _ler("arvore_para_tema.json")
    _EXCECOES = _ler("descritor_para_tema.json")


def tema_do_descritor(descritor, mapa_antigo=None):
    """O tema de UM descritor MeSH, pelas três camadas. '' = genérico, sem tema.

    Devolver '' para `Humans`, `Middle Aged` e `Risk Factors` é o comportamento CERTO e é o
    que o mapa manual não fazia: medido em 21/Ago, só **65 de 695** descritores do acervo são
    cardiovasculares (C14). Os outros 630 apareciam em tudo e puxavam o tema para qualquer lado.
    """
    _carregar_arvore()

    # ═══════════ 21/Ago — MEDIDO: A ÁRVORE SOZINHA PIOROU. ORDEM INVERTIDA. ═══════════
    # Eu construí as três camadas achando que a árvore oficial da NLM ganharia do mapa manual.
    # Ele autorizou sem hesitar — *"SIM, faça isso, mesmo que custe"*. Medi contra o gabarito
    # cego de 40 que ele marcou a mão, nos 20 que têm MeSH:
    #
    #       mapa MANUAL ..... 14/20  (70 %)
    #       ÁRVORE da NLM ... 12/20  (60 %)
    #
    # **Piorou.** E dá para ver por quê nos casos: "Microaxial Flow Pumps in Cardiogenic Shock"
    # virou Insuficiência Cardíaca em vez de UTI; "Heart Failure With Mildly Reduced EF" virou
    # Coronária/DAC. A árvore da NLM organiza por ANATOMIA — ela não sabe que choque cardiogênico
    # é do intensivista. O mapa manual, feito olhando artigos reais do acervo, sabe.
    #
    # A árvore continua valendo em DUAS coisas, e são as que ela provou:
    #   · dizer que um descritor NÃO é cardiovascular (Humans, Air Pollution → sem tema)
    #   · achar quem o mapa manual não conhece (Hyperaldosteronism, Thyroid Neoplasms)
    # Por isso ela virou a camada 3, não a 1. Ordem: exceção clínica → mapa manual → árvore.
    #
    # ⚠️ LIÇÃO, e é a mais cara do dia: **fonte oficial não é o mesmo que fonte melhor.** Eu
    # argumentei a favor da árvore por autoridade (é da NLM, é completa, é estrutural) e não por
    # medição. Ele aprovou confiando no argumento. O número desmentiu os dois.

    # ── 1 · EXCEÇÃO CLÍNICA — manda mais que tudo ──
    # A NLM organiza por ANATOMIA; ele organiza por QUEM LÊ. Exemplo medido: a NLM põe
    # `Cardiomyopathy, Hypertrophic` em TRÊS lugares, e dois são Heart Valve Diseases (via
    # obstrução de via de saída). Sem esta camada, a hipertrófica viraria valvopatia.
    if descritor in _EXCECOES:
        return normalizar(_EXCECOES[descritor])

    # ── 2 · MAPA MANUAL — feito olhando artigos REAIS do acervo. Mede 70 %. ──
    do_mapa = normalizar((mapa_antigo or {}).get(descritor, ""))
    if do_mapa:
        return do_mapa

    # ── 3 · A ÁRVORE ESTÁ DESLIGADA DA DECISÃO. Medido, duas vezes. ──
    #
    #   árvore como camada 1 (decisora) .... 12/20  (60 %)
    #   mapa manual sozinho ................ 14/20  (70 %)
    #   manual + árvore como REDE .......... 13/20  (65 %)   ← ganhou 1, perdeu 2
    #
    # Nem decidindo nem como rede ela ajuda. O ganho existe e é real (Portopulmonary Hypertension
    # passou a sair como Miocardiopatias, que é a regra dele), mas o saldo é negativo: a árvore
    # atribui tema a descritores genéricos-de-borda que o mapa manual sabiamente ignora.
    #
    # ONDE A ÁRVORE VALE, E ISSO FOI MEDIDO TAMBÉM: na BUSCA do Pesquisador. Expandir
    # "tempestade elétrica" para os descritores certos + sinônimos da NLM levou o resultado de
    # **1.114 para 5.947 artigos** — e o RCT que responde a pergunta clínica estava entre os
    # 4.833 que a busca ingênua perdia. São dois trabalhos diferentes: classificar pede
    # PRECISÃO, buscar pede RECALL. A árvore serve o segundo, não o primeiro.
    #
    # `mesh_arvore.json` e `arvore_para_tema.json` ficam no disco para esse uso. Se um dia
    # alguém quiser religá-la aqui, tem de medir contra o gabarito ANTES — foi assim que se
    # descobriu, e o argumento "é oficial da NLM, é completa" não sobreviveu ao número.
    return ""


def placar_de(mesh_terms, mapa, freq):
    """{tema: peso} e {tema: [descritores que o sustentam]}. O miolo do motor."""
    placar, quem = {}, {}
    for t in (mesh_terms or []):
        tema = tema_do_descritor(t, mapa)
        if not tema:
            continue
        # ESPECIFICIDADE: descritor raro pesa mais. `Cardiovascular Diseases` (48 artigos)
        # pesa 0,25; `Cardiomyopathy, Hypertrophic` (4 artigos) pesa 0,62.
        peso = 1.0 / math.log(2 + freq.get(t, 1))
        placar[tema] = placar.get(tema, 0.0) + peso
        quem.setdefault(tema, []).append(t)
    return placar, quem


# Quanto o 2º lugar precisa ter, em relação ao 1º, para virar tema SECUNDÁRIO.
# 0,40 = "tem pelo menos 40% do peso do vencedor". Abaixo disso é ruído de fundo, não
# um segundo assunto de verdade.
PISO_SECUNDARIO = 0.40


def decidir(mesh_terms, mapa, freq, margem_minima=0.15):
    """(principal, secundario, confianca, detalhe).

    ═══ 17/Ago/2026 — POR QUE EXISTE UM TEMA SECUNDÁRIO ═══

    Decisão do Dr. Eduardo, depois de ver dois casos reais do acervo:

      «Secondary Mitral Regurgitation Trajectories and Prognosis»
          Heart Failure · Stroke Volume · Mitral Valve Insufficiency · Echocardiography

    Insuficiência mitral SECUNDÁRIA é doença de ventrículo, não de valva — o MeSH acerta a
    fisiopatologia e manda para Insuficiência Cardíaca. Mas quem assinou "Doença Estrutural"
    quer receber isso. O artigo é legitimamente dos DOIS, e escolher um perde metade.

    Foi o mesmo raciocínio que ele deu para manter Miocardiopatias separada de IC:
    *"a separação serve basicamente quando eu pesquisar amiloidose — não vir um número
    muito grande de artigos de IC que não batem"*. Tema fino para achar, tema largo para
    entregar.

    Efeito colateral que resolve outro problema: os 72 artigos que o motor devolvia como
    INDECISO (empate entre dois temas) agora ficam com os dois — em vez de ficarem sem
    nenhum, que era perder artigo bom por excesso de escrúpulo.

    mapa  : {descritor: tema}       — a decisão clínica dele
    freq  : {descritor: n_artigos}  — frequência no acervo, para o peso de especificidade
    """
    if not mesh_terms:
        return None, None, 0.0, "sem MeSH"

    placar, quem = placar_de(mesh_terms, mapa, freq)
    if not placar:
        return SEM_TEMA, None, 0.0, "nenhum descritor com tema"

    ordem = sorted(placar.items(), key=lambda x: -x[1])
    top, p1 = ordem[0]
    p2 = ordem[1][1] if len(ordem) > 1 else 0.0
    total = sum(placar.values())
    margem = (p1 - p2) / total if total else 1.0

    # o 2º só vira secundário se tiver PESO DE VERDADE. Sem este piso, todo artigo ganharia
    # um segundo tema por qualquer descritor solto, e o filtro de entrega perderia o sentido.
    secundario = None
    if len(ordem) > 1 and p1 > 0 and (p2 / p1) >= PISO_SECUNDARIO:
        secundario = ordem[1][0]

    det = " · ".join(quem[top][:4])
    if secundario:
        det += f"   [2º: {secundario} ← {', '.join(quem[secundario][:2])}]"
    return top, secundario, margem, det
