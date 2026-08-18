"""
temas.py — A FONTE ÚNICA DE TEMA DO CARDIODAILY.

═══ 17/Ago/2026 — POR QUE ESTE ARQUIVO EXISTE ═══

Até hoje o CardioDaily tinha QUATRO vocabulários de tema que não se falavam:

    Radar CATEGORIAS          469 termos em inglês    busca no PubMed
    ficha_site.KW_TEMA        ~45 termos em inglês    decidia `doenca_principal`
    contrato.TEMAS            9 rótulos               validava na gravação
    user_manager.TEMA_DOENCAS 7 slugs minúsculos      o que o assinante escolhia

Só 3 de 9 coincidiam. Miocardiopatias, UTI e Intervenção têm volume real e não existiam
em lugar nenhum: iam todos para "Outros".

E o custo apareceu na tela: o Dr. Eduardo digitou "OBSTETRIC" no painel e achou **1**
artigo. Pelos descritores MeSH, o acervo tem **15**. Ele procurou certo; o sistema é que
só olhava o título.

    *"o tema MeSH diz respeito à minha capacidade de disponibilizar o material correto
     para quem quer receber mensagens de imagem cardiovascular ou síndrome metabólica.
     Então isso não pode esperar."*

Tema não é etiqueta de arquivo — é a chave de entrega.

═══ A ARQUITETURA, DETERMINADA POR ELE EM 17/Ago ═══

    13 TEMAS      → dentro do sistema: classificação, banco, busca, Radar
     6 CATEGORIAS → o que o assinante escolhe na hora de assinar

    *"nós vamos enviar aos assinantes artigos dentro de 6 categorias — que eu vou
     determinar — mas no sistema tem que ter o processo com os 13 temas."*

A granularidade fina fica no motor; o cardápio de venda fica curto. Um agrupa o outro, e
**nenhum dos dois é lista solta**: a categoria é derivada do tema, aqui, e mais em lugar
nenhum. Se alguém precisar de tema ou categoria, importa daqui.
"""

# ═══════════════════════════════════════════════════════════════════════════════════
# OS 13 TEMAS — a classificação interna
# ═══════════════════════════════════════════════════════════════════════════════════
TEMAS = [
    "Coronária/DAC",              # 1
    "Insuficiência Cardíaca",     # 2
    "Arritmias/Anticoagulantes",  # 3  ← ele juntou anticoagulação aqui em 17/Ago
    "Cardiometabólica",           # 4
    "Valvulopatias",              # 5
    "Miocardiopatias",            # 6
    "UTI Cardiológica",           # 7
    "Intervenção/Hemodinâmica",   # 8
    "Imagem Cardiovascular",      # 9
    "Aorta/Congênitas/Genética",  # 10 ← absorveu a antiga Cardio-Genômica
    "Cardio-Oncologia",           # 11
    "Hipertensão/HAS",            # 12
    "Cardio-Obstetrícia",         # 13
]

# escotilha: o motor NÃO chuta. Quando os descritores não decidem, o artigo fica aqui e
# aparece na revisão humana — em vez de ser jogado num tema qualquer, que foi o defeito
# do `ficha_site.KW_TEMA` (o primeiro grupo da lista que casasse vencia).
SEM_TEMA = "Sem tema"

# ═══════════════════════════════════════════════════════════════════════════════════
# AS 6 CATEGORIAS — o cardápio do assinante (decisão do Dr. Eduardo, 17/Ago/2026)
#
# ⚠️ A categoria NÃO é digitada em lugar nenhum: ela é DERIVADA do tema, por este mapa.
#    Foi ter duas listas escritas à mão que criou o problema todo.
# ═══════════════════════════════════════════════════════════════════════════════════
CATEGORIAS = {
    "Cardio-Renal-Metabólica": [
        "Coronária/DAC", "Cardiometabólica", "Hipertensão/HAS",
    ],
    "Doença Estrutural": [
        "Valvulopatias", "Intervenção/Hemodinâmica", "Aorta/Congênitas/Genética",
    ],
    "Cardiomiopatias, IC e Populações Especiais": [
        "Insuficiência Cardíaca", "Miocardiopatias", "Cardio-Oncologia",
        "Cardio-Obstetrícia",
    ],
    "Imagem Cardiovascular": ["Imagem Cardiovascular"],
    "Urgência e Emergência": ["UTI Cardiológica"],
    "Arritmias": ["Arritmias/Anticoagulantes"],
}

# o caminho inverso, montado a partir do de cima — nunca escrito à mão
_TEMA_PARA_CATEGORIA = {t: c for c, ts in CATEGORIAS.items() for t in ts}


def categoria_de(tema):
    """A categoria de venda deste tema. `None` se o tema não estiver em nenhuma."""
    return _TEMA_PARA_CATEGORIA.get(tema)


def temas_da_categoria(categoria):
    """Os temas que um assinante desta categoria deve receber."""
    return list(CATEGORIAS.get(categoria, []))


def temas_de(categorias):
    """Os temas de VÁRIAS categorias — é o que a entrega usa para filtrar."""
    fora = []
    for c in categorias or []:
        fora.extend(CATEGORIAS.get(c, []))
    return sorted(set(fora))


# ═══════════════════════════════════════════════════════════════════════════════════
# SANIDADE — conferida no import, porque uma lista pode ser editada por engano
#
# Sem isto, alguém acrescenta um tema em TEMAS, esquece de pô-lo numa categoria, e o
# artigo daquele tema simplesmente nunca é entregue a ninguém — em silêncio. É o mesmo
# formato do defeito que este arquivo veio matar.
# ═══════════════════════════════════════════════════════════════════════════════════
def _conferir():
    problemas = []
    sem_cat = [t for t in TEMAS if t not in _TEMA_PARA_CATEGORIA]
    if sem_cat:
        problemas.append(f"tema sem categoria (ninguém recebe): {sem_cat}")
    fantasma = [t for t in _TEMA_PARA_CATEGORIA if t not in TEMAS]
    if fantasma:
        problemas.append(f"categoria aponta para tema inexistente: {fantasma}")
    contados = [t for ts in CATEGORIAS.values() for t in ts]
    dup = {t for t in contados if contados.count(t) > 1}
    if dup:
        problemas.append(f"tema em MAIS DE UMA categoria (entrega dupla): {sorted(dup)}")
    if problemas:
        raise ValueError("temas.py inconsistente — " + " · ".join(problemas))


_conferir()
