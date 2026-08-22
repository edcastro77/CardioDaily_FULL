"""
ficha_site.py — monta a FICHA (os 16 campos do contrato do site) a partir de uma pasta do STAGING.
Determinístico: lê o _CANONICO.md (frontmatter) + o _ACRI.txt + os arquivos gerados.
NÃO chama LLM (barato, testável). O que não montar fica vazio — e o CONTRATO recusa. Nada de buraco no ar.

Mapa canônico → contrato do site (interface Artigo):
  identidade → doc_id, titulo, slug, revista       veredito → nota_aplicabilidade
  reaproveitamento.keywords → keywords             reaproveitamento.aplicabilidade → aplicabilidade_pratica
  ACRI[selo] → doenca_principal                    ACRI[A] → contexto_tema, gancho_lista
  ACRI[I] → impacto_conduta, bullets_praticos      arquivos → caminho_pdf/audio/visual_abstract
"""
import os, re, glob, unicodedata, datetime, json
import voo as _VOO          # plano de voo (09/Ago)

# selo do ACRI → tema do site (cardiodaily.ts → TEMAS)
SELO_TEMA = {
    "IC": "Insuficiência Cardíaca", "INSUFICIÊNCIA": "Insuficiência Cardíaca",
    "CORONÁRIA": "Coronária/DAC", "CORONARIA": "Coronária/DAC", "DAC": "Coronária/DAC",
    "ARRITMIA": "Arritmias", "ARRITMIAS": "Arritmias",
    "ESTRUTURAL": "Valvopatias", "VÁLVULA": "Valvopatias", "VALVULA": "Valvopatias", "VALVOPATIA": "Valvopatias",
    "PREVENÇÃO": "Cardiologia Preventiva", "PREVENCAO": "Cardiologia Preventiva", "PREVENÇAO": "Cardiologia Preventiva",
    "IMAGEM": "Imagem Cardíaca", "HIPERTENSÃO": "Hipertensão", "HIPERTENSAO": "Hipertensão", "HAS": "Hipertensão",
    "CONGÊNITA": "Cardiopatia Congênita", "CONGENITA": "Cardiopatia Congênita", "ONCO": "Outros",
}
# rede de segurança por keyword, se o selo faltar
KW_TEMA = [
    (("hfpef", "hfref", "heart failure", "insuficiência", "dapagliflozin", "sacubitril", "ejection fraction"), "Insuficiência Cardíaca"),
    (("coronary", "pci", "stent", "acute coronary", "myocardial infarction", "stemi", "nstemi", "dac"), "Coronária/DAC"),
    (("atrial fibrillation", "ablation", "arrhythm", "pacing", "icd", "flutter"), "Arritmias"),
    (("valve", "tavr", "tavi", "mitral", "aortic stenosis"), "Valvopatias"),
    (("hypertension", "blood pressure"), "Hipertensão"),
    (("prevention", "statin", "lipid", "cholesterol", "aspirin", "diabetes", "tirzepatide",
      "semaglutide", "glp-1", "glp1", "obesity", "cardiometabolic", "lipoprotein", "pcsk9"), "Cardiologia Preventiva"),
    (("mri", "ct", "imaging", "echocard", "strain"), "Imagem Cardíaca"),
]


def slugify(s, maxlen=80):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii").lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s[:maxlen].rstrip("-")


def _campo(txt, chave):
    m = re.search(rf'{chave}:\s*"(.*?)"\s*$', txt, re.M)
    return m.group(1).strip() if m else ""


def _lista_yaml(txt, chave):
    m = re.search(rf"{chave}:\s*\[(.*?)\]", txt, re.S)
    if not m:
        return []
    return [x.strip().strip('"') for x in re.findall(r'"([^"]*)"', m.group(1))]


def _bloco_acri(acri, letra):
    # tolera os dois formatos do ACRI: "**A — Análise:**" e "**A —**"
    m = re.search(rf"\*\*{letra}\b[^*]*\*\*\s*(.*?)(?=\n\s*\*\*[ACRI]\b|\Z)", acri, re.S)
    if not m:
        return ""
    t = m.group(1)
    t = re.sub(r"\*+", "", t)              # tira negrito/itálico
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _frases(t, minlen=25, maxlen=240):
    """Frases acionáveis p/ bullets/gancho. Frase densa que passa de `maxlen` NÃO é descartada
    (era o buraco que zerava os bullets de artigo bem escrito → contrato recusava): é SEGMENTADA
    em cláusulas legíveis — travessão/;/: primeiro, vírgula só se ainda estourar, palavra no extremo."""
    out = []
    for p in re.split(r"(?<=[.;!?])\s+", (t or "").strip()):
        p = p.strip()
        if not p:
            continue
        if len(p) <= maxlen:
            if len(p) >= minlen:
                out.append(p)
        else:
            out.extend(_segmentar(p, minlen, maxlen))
    return out


def _push(out, frag, minlen, maxlen):
    frag = frag.strip(" ,;:—–")
    if not frag:
        return
    if len(frag) < minlen:                                   # curto demais → cola no anterior se couber
        if out and len(out[-1]) + 1 + len(frag) <= maxlen:
            out[-1] = f"{out[-1]} {frag}"
    else:
        out.append(frag)


def _por_palavra(c, maxlen):
    pedacos, buf = [], ""
    for w in c.split():
        cand = f"{buf} {w}".strip()
        if len(cand) <= maxlen:
            buf = cand
        elif buf:
            pedacos.append(buf); buf = w
        else:
            buf = w
    if buf:
        pedacos.append(buf)
    return pedacos


def _segmentar(frase, minlen=25, maxlen=240):
    """Quebra uma frase longa demais em cláusulas dentro de [minlen, maxlen], sem perder conteúdo."""
    out = []
    for forte in re.split(r"\s*[—–;:]\s*", frase):           # 1) marcadores fortes (não vírgula)
        forte = forte.strip(" ,;:—–")
        if not forte:
            continue
        if len(forte) <= maxlen:
            _push(out, forte, minlen, maxlen)
            continue
        for sub in re.split(r",\s+", forte):                 # 2) só agora a vírgula
            sub = sub.strip(" ,")
            if len(sub) <= maxlen:
                _push(out, sub, minlen, maxlen)
            else:                                            # 3) extremo: quebra por palavra
                for w in _por_palavra(sub, maxlen):
                    _push(out, w, minlen, maxlen)
    return out


def _tema(selo, keywords):
    tag = re.sub(r"[^A-Za-zÀ-ÿ ]", "", selo).strip().upper()
    for k, v in SELO_TEMA.items():
        if tag.startswith(k):
            return v
    kws = " ".join(keywords).lower()
    for termos, tema in KW_TEMA:
        if any(x in kws for x in termos):
            return tema
    return "Outros"   # último recurso: 'Outros' é tema VÁLIDO do site. Nunca "" (recusaria nota≥6 no contrato)


def _data_valida(ano):
    """Coage o ano numa DATE válida p/ o Postgres (que rejeita '2026' puro).
    AAAA-MM-DD mantém · AAAA-MM → dia 01 · AAAA → 01-01 · nada reconhecível → '' (o contrato então retém)."""
    s = (ano or "").strip()
    m = re.search(r"\d{4}-\d{2}-\d{2}", s)
    if m: return m.group(0)
    m = re.search(r"(\d{4})-(\d{2})", s)
    if m: return f"{m.group(1)}-{m.group(2)}-01"
    m = re.search(r"\d{4}", s)
    if m: return f"{m.group(0)}-01-01"
    return ""


def _do_nome_do_arquivo(pasta):
    """Título, revista e ano a partir do NOME que o classificador deu — `AAAA-MM-Revista-Titulo`.
    O classificador monta esse nome com metadado do PubMed, então isto é CATÁLOGO, não chute.
    Devolve {} se o nome não seguir o padrão (PDF solto, nome manual) — e aí o campo fica vazio
    mesmo, que é o certo: melhor o contrato recusar do que inventar capa."""
    import re as _re
    base = os.path.basename(str(pasta).rstrip("/"))
    m = _re.match(r"^(\d{4})-(\d{2})-([^-]+)-(.+)$", base)
    if not m:
        return {}
    ano, mes, rev, tit = m.groups()
    return {"ano": ano, "mes": mes,
            "revista": rev.replace("_", " ").strip(),
            "titulo": tit.replace("_", " ").strip()}


def _doi_ou_sintetico(doi, doc_id):
    """O DOI da linha — e um SINTÉTICO quando o documento simplesmente não tem DOI.

    ═══ 06/Ago/2026 — POR QUE ISTO EXISTE ═══
    A coluna `doi` do Supabase é NOT NULL. Antes, sem DOI, gravávamos `None` e o banco recusava a
    linha inteira com `23502` — foi o que aconteceu com a diretriz do NICE (NG136) na rodada real.

    Nem todo documento tem DOI, e isso não é defeito do dado: **o NICE publica por código próprio
    (NG136), não por DOI**, e o mesmo vale para vários documentos de sociedade e para as diretrizes
    brasileiras. Medido em 06/Ago: 2 de 131 pacotes sem DOI — os dois, NICE.

    DECISÃO DO DR. EDUARDO (opção A, 06/Ago): gravar um identificador sintético **com o prefixo
    `Sintetico_`**. O prefixo é o ponto: qualquer um que olhe a coluna vê na hora que aquilo não é
    um DOI de verdade, e ninguém vai tentar resolver aquilo no doi.org. Era a minha única objeção
    à opção A, e o prefixo dele a resolve.

    O sintético é derivado do `doc_id`, que já é único — então a UNIQUE(doi) continua honesta.
    O caminho do Storage usa `doc_id`, não o DOI: nada de mídia muda.
    """
    d = (doi or "").strip()
    if d and d.lower() != "n/a":
        return d
    return f"Sintetico_{doc_id}" if doc_id else None


# ═══════════ 21/Ago/2026 — 32 ARTIGOS FALHARAM POR ESTA LINHA ESTAR NO LUGAR ERRADO ═══════════
# `NAO_SE_APLICA` era uma variável LOCAL, declarada lá dentro do `montar()`. Quando escrevi o
# `_decidir_tema` (uma função separada, acima), usei o nome achando que era constante de módulo.
#
#     NameError: name 'NAO_SE_APLICA' is not defined      × 32 artigos, na hora de publicar
#
# **Compilou.** O `py_compile` não pega escopo, e o meu teste de fumaça chamou
# `_decidir_tema` direto — caminho em que o erro não aparece, porque eu passei pelo ramo que
# retorna antes. A bateria não pegou porque roda em `CARDIODAILY_SEM_REDE`, e esse ramo... também
# usa a constante. Ele só não estourou lá porque a trava chama `montar()`, e dentro de `montar()`
# o nome EXISTE (é local dele) — o interpretador resolve pelo escopo de quem chama? Não: resolve
# pelo GLOBAL, e como `montar` roda depois de definir a local, o NameError só aparece quando
# `_decidir_tema` é chamado a partir do publicador, com a ficha completa.
#
# É a mesma família do `_re` importado na linha 256 e usado na 173, e do `_VOO` que custou 10
# artigos pagos em 10/Ago: **nome definido depois de onde é usado.** Compila, e quebra em produção.
#
# Constante de módulo mora no TOPO do módulo. Sem exceção.
NAO_SE_APLICA = "nao_se_aplica"   # o tipo do documento não tem esse conceito. Nunca terá.

_MESH_FREQ = None      # frequência dos descritores no acervo — o peso IDF do desempate


def _mesh_do_doi(doi):
    """Descritores MeSH do PubMed. [] = procurei e não achou (≠ NULL = não procurei).

    ⚠️ Eu tinha escrito `puxar_mesh.mesh_de_doi(doi)` — função que NÃO EXISTE. O arquivo tem
    `doi_para_pmid(dois)` e `mesh_de(pmids)`, e ele mora em `scripts/`, não em `src/`. Com o
    `except: pass` que eu havia posto, o ImportError seria engolido e `mesh_terms` ficaria
    vazio PARA SEMPRE, sem uma linha de aviso. Nome inventado + exceção surda = coluna morta
    que ninguém descobre. É o defeito de 06/Ago (prompt calado) na forma mais barata de todas.
    """
    if not doi or doi == "n/a":
        return []
    import sys as _s
    # `_HERE` NÃO EXISTE neste módulo — eu escrevi `if "_HERE" in globals()` e o `else`
    # mascarou o erro. A trava de escopo (21/Ago) pegou. Caminho direto, sem fantasma:
    _sc = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
    if _sc not in _s.path:
        _s.path.insert(0, _sc)
    try:
        import puxar_mesh as _PM
        pmid = _PM.doi_para_pmid([doi]).get(doi.lower())
        return _PM.mesh_de([pmid]).get(pmid, []) if pmid else []
    except Exception as e:
        print(f"       ⚠️  MeSH indisponível ({type(e).__name__}: {e}) — segue só com o LLM")
        return []


def _tema_por_mesh(mesh):
    """(principal, secundario) pelo mapa de descritores. (None, None) se não decidir."""
    global _MESH_FREQ
    try:
        import collections
        import tema_mesh as _TM
        mapa = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                           "dados", "mesh_para_tema.json"), encoding="utf-8"))
        if _MESH_FREQ is None:
            # o peso do desempate é IDF: descritor raro vale mais que descritor comum. A tabela
            # de frequência vem do acervo e é gerada por `scripts/gerar_freq_mesh.py`. Se não
            # existir, todos os descritores pesam igual — pior, mas não quebra.
            f = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dados", "mesh_freq.json")
            _MESH_FREQ = collections.Counter(json.load(open(f, encoding="utf-8"))) \
                if os.path.exists(f) else collections.Counter()
        p, s, _margem, _det = _TM.decidir(mesh, mapa, _MESH_FREQ)
        return p, s
    except Exception as e:
        print(f"       ⚠️  mapa MeSH falhou: {type(e).__name__}: {e}")
        return None, None


def _mesh_com_plano_b(doi, titulo, texto, revista):
    """(descritores, mesh_origem) — a lista NUNCA volta vazia sem que a origem diga por quê.

    ═══ 22/Ago/2026 — POR QUE O PLANO B (decisão do Dr. Eduardo) ═══
    Medido no acervo de 704: **208 com `mesh_terms` vazio**, 157 deles de 2026. E numa amostra
    de 25 desses, perguntando ao PubMed naquele instante: **0/25 já tinham MeSH.** 21 estavam
    no PubMed sem descritor; 4 nem no PubMed (diretrizes SBC).

    Ou seja: "roda a varredura de novo" não conserta — o indexador HUMANO da NLM leva de
    semanas a meses, e a fila enche justamente dos artigos mais novos, que são os que ele mais
    quer entregar. E `mesh_terms` não é enfeite: é por ele que o **Pesquisador** acha material.
    Artigo sem descritor existe no banco e é invisível para quem procura.

    A ordem é a mesma do tema, e pela mesma razão: **o humano manda, o modelo cobre a lacuna.**
      pubmed ...... descritor da NLM. Substitui qualquer outro, sempre.
      mesh_llm .... o modelo propôs e a amarra RESOLVEU contra o vocabulário oficial.
      falha ....... nem um nem outro. NÃO é "esse artigo não tem descritor" — é defeito, e o
                    contrato retém a linha em vez de publicar um buraco.
    """
    mesh = _mesh_do_doi(doi)
    if mesh:
        return mesh, "pubmed"
    try:
        import mesh_llm as _ML
        termos, origem, detalhe = _ML.descritores(titulo, texto, revista)
        if termos:
            print(f"       🔤 MeSH pelo modelo: {len(termos)} descritores ({detalhe})")
            return termos, origem
        print(f"       ⚠️  MeSH (modelo) não entregou: {detalhe}")
    except Exception as e:
        # sem `except: pass` — ver `_mesh_do_doi`: exceção surda aqui mata a coluna em silêncio.
        print(f"       ⚠️  MeSH (modelo) falhou: {type(e).__name__}: {e}")
    return [], "falha"


def _decidir_tema(titulo, revista, texto, doi):
    """(tema, tema_secundario, tema_origem, mesh_terms, mesh_origem) — nenhum deles NULL. Nunca.

    ═══ A ORDEM, e por que ela é esta (decisão do Dr. Eduardo, 20/Ago) ═══
    Medido num gabarito cego de 40 artigos que ELE marcou a mão, contando "o tema que ele daria
    está no par que o sistema gravou" (que é o que decide se o assinante RECEBE):

        MeSH sozinho ....... 80 %
        LLM com o TRIPÉ .... 92 %   (meta declarada antes de mexer: 90 %)

    Por isso: **o LLM decide, o MeSH entra como 2º tema e desempate.** Até 20/Ago era o
    contrário — o MeSH decidia e o LLM só entrava na ausência de descritor. A arquitetura
    estava invertida em relação ao que os números mostram, e ninguém tinha medido: em 17/Ago
    eu apresentei COBERTURA ("499 de 520 com tema") como se fosse ACERTO.

    ⚠️ O MeSH continua valendo, e não é consolo: ele é humano (indexador da NLM) e
    determinístico, enquanto o LLM varia entre rodadas. Como 2º tema ele faz o que faz bem —
    ampliar o alcance — sem decidir sozinho.

    ═══ OS QUATRO VALORES DE `tema_origem`, e o que cada um significa ═══
      llm .................... o tripé fechou e decidiu
      mesh ................... o LLM falhou e o descritor humano salvou
      fora_do_escopo ......... o tripé NÃO fechou: não há leitor cardiológico
      falha_do_classificador . nem o LLM nem o MeSH responderam (rede, JSON, enum)
    Os dois últimos são `Sem tema`, e o contrato RETÉM a linha. **É de propósito que sejam
    palavras diferentes:** "não é cardiologia" e "o programa quebrou" são coisas opostas, e
    tratá-las como a mesma foi o defeito de 18/Ago com o `nao_avaliavel`.
    """
    import temas as _T
    # ═══ MODO OFFLINE — para a BATERIA, não para produção ═══
    # Ao ligar o tema aqui, `montar()` passou a chamar o PubMed e o LLM. A bateria chama
    # `montar()` (teste_ficha_sem_contradicao) e TRAVOU: 3.600 travas viraram reféns da rede.
    # Trava que depende de rede não é trava — ela falha por motivo errado, demora, e ensina a
    # ignorar o vermelho. Com `CARDIODAILY_SEM_REDE=1` a decisão vira determinística e o resto
    # da ficha continua sendo conferido.
    if os.getenv("CARDIODAILY_SEM_REDE"):
        return "Coronária/DAC", NAO_SE_APLICA, "offline_para_teste", ["Heart Failure"], "offline_para_teste"
    mesh, mesh_origem = _mesh_com_plano_b(doi, titulo, texto, revista)

    tema = sec = None
    origem = "falha_do_classificador"
    try:
        import tema_llm as _TL
        tema, sec, _porque = _TL.classificar(titulo, texto, revista)
        if tema == "fora_do_escopo":
            return _T.SEM_TEMA, NAO_SE_APLICA, "fora_do_escopo", mesh, mesh_origem
        if tema:
            origem = "llm"
    except Exception as e:
        # ⚠️ NUNCA em silêncio. Um `except: pass` aqui transformaria "o classificador quebrou"
        # em "o artigo não tem tema" — que é a confusão que a LEI 11 existe para impedir.
        print(f"       ⚠️  tema (LLM) falhou: {type(e).__name__}: {e}")
        tema = None

    # ── o MeSH: rede quando o LLM não respondeu, e 2º TEMA quando respondeu sem secundário ──
    # O 2º tema vale muito: o assinante de QUALQUER das duas categorias recebe o artigo. Medido
    # nos 40 — contar o PAR em vez de só o 1º tema levou o acerto de 77 % para 92 %.
    if mesh and (not tema or not sec):
        p, s = _tema_por_mesh(mesh)
        if not tema and p:
            tema, sec, origem = p, (sec or s), "mesh"
        elif tema and not sec:
            sec = next((c for c in (p, s) if c and c != tema), None)

    if not tema:
        return _T.SEM_TEMA, NAO_SE_APLICA, origem, mesh, mesh_origem
    # `Não se aplica` e não vazio: a MAIORIA dos artigos tem um tema só, e isso é o normal,
    # não uma falha. Vazio aqui seria indistinguível de "o programa não chegou a olhar".
    return tema, (sec or NAO_SE_APLICA), origem, mesh, mesh_origem


def montar(pasta):
    """Lê uma pasta do STAGING e devolve a ficha (dict com os 16 campos)."""
    base = os.path.basename(pasta.rstrip("/"))
    can = glob.glob(os.path.join(pasta, "*_CANONICO.md"))
    canon = open(can[0], encoding="utf-8").read() if can else ""
    acri_f = glob.glob(os.path.join(pasta, "*_ACRI.txt"))
    acri = open(acri_f[0], encoding="utf-8").read() if acri_f else ""

    # fenótipo de fração de ejeção (fato da extração) — vira a TRAVA do portão contra a inversão HFpEF↔reduzida
    # e o MOTOR que deu a nota (02/Ago): sem ele, uma nota 8 de DIRETRIZ e uma de ORIGINAL são
    # indistinguíveis no banco — e são réguas completamente diferentes.
    fatos_f = glob.glob(os.path.join(pasta, "*_fatos.json"))
    fracao_ejecao, motor, tipo_documento, veredito_dominios = None, "ORIGINAL", "original", {}
    desenho = ""
    if fatos_f:
        try:
            _f = json.load(open(fatos_f[0], encoding="utf-8"))
            fracao_ejecao = _f.get("fracao_ejecao")
            # 10/Ago — o DESENHO viaja junto para o contrato poder comparar com a caixa.
            # Sem esta linha a trava `CAIXA ERRADA` do contrato nunca dispararia: ela leria
            # um campo que a ficha não carrega e devolveria "" para sempre. É o mesmo defeito
            # de 06/Ago (motor certo + schema certo + PROMPT calado = campo null eternamente) e
            # de 05/Ago (as palavras-chave da meta nasceram sem instrução). Trava que depende
            # de campo ausente não é trava: é decoração que dá APROVADO por ausência.
            desenho = str(_f.get("desenho") or "").strip()
            import notas_prototipo as _N
            _r = _N.score(_f)
            motor = _r.get("motor") or "ORIGINAL"
            tipo_documento = _N.tipo_do_documento(_f)
            # OS DOMÍNIOS ABERTOS, num campo só (jsonb). Decisão do Dr. Eduardo, 02/Ago:
            # colunas específicas por tipo (pct_nivel_c, utilidade…) CRIARIAM buraco por desenho —
            # toda meta-análise nasceria com elas vazias. Ele viu isso na minha proposta e recusou.
            # Aqui cada artigo carrega os domínios DO SEU motor: nunca vazio, nunca campo de outro tipo.
            veredito_dominios = {"motor": motor,
                                 **{k: v for k, v in (_r.get("dominios_meta")
                                                      or _r.get("dominios_agree")
                                                      or _r.get("dominios_revisao_rigor") or {}).items()},
                                 **({"utilidade": _r["utilidade"],
                                     **(_r.get("dominios_revisao_util") or {})} if motor == "REVISAO" else {}),
                                 **({"pct_nivel_c": _r.get("pct_nivel_c"),
                                     "pct_classe_i_em_c": _r.get("pct_classe_i_em_c")} if motor == "DIRETRIZ" else {}),
                                 **({"teto_desenho": _r.get("teto_desenho"),
                                     "nhlbi": _r.get("nhlbi")} if motor == "ORIGINAL" else {})}
            _VOO.marcar("P1_FICHA", artigo=os.path.basename(str(pasta).rstrip("/")),
                        motor=motor, tipo_documento=tipo_documento)
        except Exception as e:
            # ═══ 09/Ago — O PIOR PONTO MUDO DO SISTEMA INTEIRO ═══
            # Era `except Exception: pass`, e o que ele engolia não era um detalhe: era o
            # `json.load` dos FATOS **e** o `notas_prototipo.score()`. Quando qualquer um
            # falhava, a ficha seguia com os padrões declarados acima:
            #
            #     motor = "ORIGINAL" · tipo_documento = "original" · fracao_ejecao = None
            #
            # E aí, em cascata e tudo em silêncio:
            #   · o contrato não reconhece a diretriz → TODA diretriz com nota <6 é recusada,
            #     anulando a decisão do Dr. Eduardo de 05/Ago (a diretriz não tem porta);
            #   · a trava de INVERSÃO DE FRAÇÃO DE EJEÇÃO é desligada — a que impede publicar
            #     "levosimendana para ICFEr" num ensaio de ICFEp;
            #   · o banco grava a régua errada na coluna `motor`, e uma nota 8 de diretriz
            #     fica indistinguível de uma nota 8 de RCT.
            #
            # Três decisões clínicas apagadas por uma linha de duas palavras.
            _VOO.marcar("P1_FICHA", ok=False,
                        artigo=os.path.basename(str(pasta).rstrip("/")),
                        erro=f"{type(e).__name__}: {e}")
            print(f"  ⚠️  FICHA SEM MOTOR: {os.path.basename(str(pasta).rstrip('/'))[:46]} — "
                  f"{type(e).__name__}: {str(e)[:70]}")
            print(f"      A linha vai como ORIGINAL/original e a trava de fração de ejeção "
                  f"fica DESLIGADA para este artigo.")

    titulo = _campo(canon, "titulo")
    revista = _campo(canon, "revista")
    doi = _campo(canon, "doi")

    # ═══════════ 04/Ago 06h — A CAPA TEM DUAS FONTES, E A SEGUNDA É MELHOR ═══════════
    # 10 meta-análises com nota 6 a 9 — perícia, PDF, áudio e visual prontos, tudo pago — foram
    # RECUSADAS pelo contrato com "titulo vazio · revista vazia · data_publicacao ausente". O
    # `SCHEMA_FATOS_META`, que escrevi de madrugada, tinha os blocos de método (PRISMA, Cochrane,
    # AMSTAR-2, GRADE) e não tinha a IDENTIFICAÇÃO. O portão estava certo; o buraco era meu.
    #
    # O schema já foi corrigido. Mas existe uma segunda fonte, e ela é MAIS CONFIÁVEL que o LLM
    # relendo o PDF: o NOME DO ARQUIVO. Quem o montou foi o classificador, com metadado do PubMed —
    # `AAAA-MM-Revista-Titulo`. Isso é dado de catálogo, não leitura de modelo.
    #
    # Por isso a ordem passa a ser: FATOS primeiro; se vier vazio, o NOME. Custa zero, não chama
    # LLM nenhum, e recupera os 10 artigos já pagos sem re-analisar nada.
    _n = _do_nome_do_arquivo(pasta)
    titulo = titulo or _n.get("titulo", "")
    revista = revista or _n.get("revista", "")
    keywords = _lista_yaml(canon, "keywords")
    aplic = _campo(canon, "aplicabilidade")
    mnota = re.search(r"nota_aplicabilidade_clinica:\s*(\d+)", canon)
    nota = int(mnota.group(1)) if mnota else None
    muda = _campo(canon, "muda_conduta")

    selo = ""
    ms = re.search(r"^\s*\[(.*?)\]", acri, re.M)
    if ms:
        selo = ms.group(1)
    a_bloco = _bloco_acri(acri, "A")
    i_bloco = _bloco_acri(acri, "I")

    # gancho: a parte vívida do paciente (depois de "—") ou 1ª frase do bloco A
    gancho = ""
    mg = re.search(r"[—-]\s*((?:exatamente|o\s+cara|o\s+paciente|aquele|a\s+paciente)[^.]*\.)", a_bloco, re.I)
    if mg:
        gancho = mg.group(1).strip()
    elif a_bloco:
        gancho = _frases(a_bloco)[:1] and _frases(a_bloco)[0] or a_bloco[:160]
    # ═══ 05/Ago — O GANCHO ERA IDÊNTICO AO CONTEXTO em 9 das 18 diretrizes ═══
    # São campos com finalidades DIFERENTES: o gancho é a isca da lista (uma frase, para o
    # assinante clicar); o contexto é o "por que isto importa" do card. Quando o bloco A do ACRI
    # tem uma frase só, o `_frases(a_bloco)[0]` devolvia o bloco INTEIRO — e os dois campos
    # ficavam com o mesmo texto. Repetir a mesma frase em dois lugares não é buraco de dado,
    # é buraco EDITORIAL: o leitor lê duas vezes a mesma coisa e o gancho perde a função.
    if gancho and a_bloco and gancho.strip() == a_bloco.strip():
        _fr = _frases(a_bloco)
        gancho = _fr[0].strip() if len(_fr) > 1 else (a_bloco.strip()[:150].rsplit(" ", 1)[0] + "…")

    # bullets: frases acionáveis do bloco Impacto; completa com aplicabilidade se faltar
    bullets = _frases(i_bloco)
    if len(bullets) < 2:
        bullets += _frases(aplic)
    bullets = bullets[:4]

    arq = lambda pat: (glob.glob(os.path.join(pasta, pat)) or [""])[0]
    pdf = arq("*_analise.pdf") or arq("*_analise.md")     # análise crítica (peça central); PDF se já renderizado
    md = arq("*_analise.md")
    resumo = open(md, encoding="utf-8").read() if md else ""     # → resumo_markdown

    # ═══════════ OS DOIS SELOS — 02/Ago/2026, decisão do Dr. Eduardo ═══════════
    #
    # "a tabela tem que ser igual em todas as pastas — se um campo for ficar vazio naquela pasta
    #  porque não tem o campo, a pasta já preenche o 'não se aplica' nos campos que iriam ficar vazios"
    #
    # O QUE ISTO CONSERTA: hoje a mesma coluna VAZIA quer dizer três coisas diferentes, e ninguém
    # consegue distinguir olhando o banco:
    #     (a) não se aplica àquele tipo   (b) não atingiu a porta   (c) BURACO — o sistema falhou
    # Medido em 02/Ago nas 4.307 linhas: `mcid_avaliacao` 35,8 % vazio, `caminho_audio` 71,7 %,
    # `gancho_abertura` 75,8 %. Impossível saber quanto daquilo era defeito e quanto era natureza.
    #
    # A REGRA: "não se aplica" e "não gerado" são INFORMAÇÃO e vão escritos, com o motivo.
    # Vazio (NULL) passa a significar UMA coisa só: DEFEITO. Aí o NOT NULL vira trava de verdade.
    # (a constante subiu para o topo do módulo em 21/Ago — ver o comentário lá)
    NAO_GERADO = "nao_gerado"         # poderia ter, não atingiu a porta por nota.

    def _porta(caminho, nota_minima, o_que):
        """Arquivo que existe → caminho. Não existe → DIZ POR QUÊ, não deixa vazio."""
        if caminho:
            return caminho
        if nota is not None and nota < nota_minima:
            return f"{NAO_GERADO}: nota {nota} (a porta do {o_que} e {nota_minima})"
        return f"{NAO_GERADO}: nota {nota} atingiu a porta do {o_que} mas o arquivo NAO existe"

    audio = _porta(arq("*_audio.mp3"), 8, "audio")
    visual = _porta(arq("*_visual*") or arq("*_INFOGRAFICO.png") or arq("*_infografico*"), 7, "visual")
    gab = arq("*_gancho_abertura.txt")                           # gancho de abertura (nota≥8) — no PORTÃO
    gancho_abertura = (open(gab, encoding="utf-8").read().strip() if gab
                       else _porta("", 8, "gancho de abertura"))

    # campos extras que a tabela REAL usa (a tabela NÃO tem 'slug')
    # ═══ 05/Ago — O MÊS ESTAVA SENDO JOGADO FORA (29 de 29 linhas em AAAA-01-01) ═══
    # O canônico guarda só o ANO (4 dígitos), então `_data_valida` devolvia AAAA-01-01. O focused
    # update do ESC é de NOVEMBRO e estava gravado como janeiro — erro de até 11 meses, que quebra
    # ordenação por data, "artigo da semana" e qualquer agenda de envio.
    # O MÊS existe: está no nome do arquivo (`AAAA-MM-Revista-Titulo`), posto lá pelo classificador
    # com metadado do PubMed. A 2ª fonte já era usada para o ano; passa a dar o mês também.
    _ano_canon = _campo(canon, "ano")
    _aaaa_mm = (f"{_n['ano']}-{_n['mes']}" if _n.get("ano") and _n.get("mes") else "")
    # ═══ 06/Ago — E QUANDO OS DOIS ANOS DISCORDAM? O PUBMED MANDA ═══
    # A regra de 05/Ago só pegava o mês se `_ano_canon == _n['ano']`. Quando os dois divergiam,
    # ela DESISTIA e usava o ano do canônico — perdendo o mês E ficando com o ano pior.
    # Pego pela trava na rodada real de 06/Ago: `Tirzepatide for Obesity` está em pasta 2025-03
    # (nome posto pelo classificador com metadado do PubMed) e o extrator leu `ano: 2024` do PDF.
    # A ficha gravou 2024-01-01: errou o ano E o mês, 14 meses de diferença.
    # QUEM MANDA: o nome do arquivo, quando traz AAAA-MM. Não é preferência — é a LEI 8. O nome
    # vem do PubMed (catálogo); o `ano` do canônico é o modelo LENDO o PDF, e um PDF traz data de
    # submissão, de aceite, de publicação online e de edição impressa. O extrator escolhe uma.
    # A capa já é reparada por DOI→PubMed pelo mesmo motivo (`reparar_capa.py`).
    if _aaaa_mm:
        ano = _data_valida(_aaaa_mm)
    else:
        ano = _data_valida(_ano_canon) or _data_valida(_n.get("ano", ""))
    tipo = _campo(canon, "tipo")
    # ═══ 05/Ago — DUAS COLUNAS PARA A MESMA PERGUNTA, DISCORDANDO ═══
    # Medido no Supabase: as 18 diretrizes tinham `tipo_documento: diretriz` E
    # `tipo_estudo: artigo_original` NA MESMA LINHA. O `tipo` vem do campo `tipo` do canônico,
    # que o extrator da diretriz não preenche — sobrava o padrão do artigo original.
    # É o padrão que já mordeu duas vezes hoje (muda_conduta em 3 caminhos, desfecho_duro em 2):
    # quando duas colunas respondem a mesma coisa, uma hora elas divergem.
    # Quem manda é a PASTA (LEI 8). O `tipo_estudo` passa a ser DERIVADO dela, não paralelo.
    # ⚠️ a fonte NÃO é o canônico: ele guarda `tipo: "artigo_original"` até numa diretriz —
    # quem o escreve não recebe o tipo da pasta. A fonte certa é o `tipo_documento` calculado
    # ACIMA nesta mesma função, a partir dos FATOS + da pasta (notas_prototipo.tipo_do_documento).
    _tipo_doc = (tipo_documento or "").strip().lower()
    _ROTULO_POR_TIPO = {
        "diretriz": "diretriz_pratica_clinica",
        "meta": "revisao_sistematica_meta_analise",
        "revisao_narrativa": "revisao_narrativa",
    }
    if _tipo_doc in _ROTULO_POR_TIPO:
        tipo = _ROTULO_POR_TIPO[_tipo_doc]
    mrig = re.search(r"nota_trabalho_estatistico:\s*(\d+)", canon)
    rigor = int(mrig.group(1)) if mrig else None

    # MCID — SÓ EXISTE para artigo original e meta-análise. Os extratores de DIRETRIZ e de REVISÃO
    # NARRATIVA não produzem `relevancia_clinica` (conferido em 02/Ago: 0 menções nos dois prompts),
    # e isso é CERTO: diretriz não tem desfecho primário, revisão narrativa não tem efeito agregado
    # próprio. Cobrar MCID delas seria o mesmo "superficializar" que a gente combateu o dia inteiro.
    mcid_classe = _campo(canon, "classificacao")
    mcid_frase = _campo(canon, "frase_chave")
    if mcid_classe and mcid_classe != "n/a":
        mcid = f"[{mcid_classe}] {mcid_frase}"
    elif mcid_frase:
        mcid = mcid_frase
    elif motor in ("DIRETRIZ", "REVISAO"):
        mcid = (f"{NAO_SE_APLICA}: {'diretriz nao tem desfecho primario' if motor == 'DIRETRIZ' else 'revisao narrativa nao tem efeito agregado proprio'}")
    else:
        mcid = f"{NAO_SE_APLICA}: MCID nao reportado pelos autores"

    # ═══ NENHUM CAMPO SAI VAZIO — 03/Ago/2026 ═══
    # Medido antes de travar o banco: com um ACRI vazio, 8 dos 10 campos saíam em branco. Se o
    # NOT NULL entrasse primeiro, a Chave 2 morreria no primeiro artigo com ACRI fraco — eu teria
    # entregue uma trava que quebra em vez de proteger. Ordem certa: o CÓDIGO garante, depois o banco exige.
    #
    # A regra é a mesma dos dois selos: campo em branco vira uma FRASE que diz o que faltou. O banco
    # nunca recebe vazio, e quem lê a linha sabe na hora qual peça do pacote falhou.
    def _ou_selo(valor, de_onde):
        if isinstance(valor, list):
            return valor if valor else [f"ausente: {de_onde}"]
        return valor if (valor and str(valor).strip()) else f"ausente: {de_onde}"

    # ═══════════ 20/Ago/2026 — O TEMA ENTRA NO PORTÃO (LEI 5) ═══════════
    # O que aconteceu: em 17/Ago eu construí a máquina de temas (MeSH + 13 temas + LLM), rodei UMA
    # vez pelo `scripts/marcar_temas.py` e dei por resolvido. Só que aquele script dá PATCH direto
    # em `artigos` — ou seja, era um SEGUNDO PORTÃO, exatamente o que a LEI 5 proíbe e o que ele já
    # tinha me dito ("não pode ter dois portões"). Enquanto ele rodava, o banco parecia certo.
    # Parou de rodar, o portão de verdade continuou publicando, e a coluna nasceu vazia:
    #     até 17/Ago ..... 21 sem tema em 507
    #     18/Ago ......... 18 em 26
    #     19/Ago ......... 78 em 83     ← o buraco não é falha, é ausência da máquina no caminho
    # Agora quem preenche é AQUI, dentro do portão único, junto com todas as outras colunas.
    tema, tema_secundario, tema_origem, mesh_terms, mesh_origem = _decidir_tema(
        titulo, revista, " ".join(str(x) for x in (a_bloco, aplic, resumo) if x), doi)

    _doc_id = doi if doi and doi != "n/a" else slugify(titulo)
    return {                                    # nomes = colunas REAIS da tabela artigos (Supabase)
        "doc_id": _doc_id,
        "doi": _doi_ou_sintetico(doi, _doc_id),
        "titulo": titulo,
        "revista": revista,
        "data_publicacao": _ou_selo(ano, "o documento nao traz ano legivel"),
        "tipo_estudo": tipo,
        "doenca_principal": _ou_selo(_tema(selo, keywords), "sem tema no canonico"),
        "nota_aplicabilidade": nota,
        "nota_trabalho_estatistico": rigor,
        "muda_conduta": _ou_selo(muda, "campo muda_conduta ausente no canonico"),
        "keywords": _ou_selo(keywords, "sem keywords no canonico"),
        "contexto_tema": _ou_selo(a_bloco, "bloco A do ACRI vazio"),
        "aplicabilidade_pratica": _ou_selo(aplic, "campo aplicabilidade ausente no canonico"),
        "impacto_conduta": _ou_selo(i_bloco, "bloco I do ACRI vazio"),
        "bullets_praticos": _ou_selo(bullets, "sem frase acionavel no ACRI"),
        "gancho_lista": _ou_selo(gancho, "sem gancho no ACRI"),
        "gancho_abertura": gancho_abertura,     # abertura provocativa (nota≥8) — gerada no portão, não por fora
        "mcid_avaliacao": mcid,
        "resumo_markdown": resumo,
        "caminho_pdf": pdf,
        "caminho_audio": audio,
        "caminho_visual_abstract": visual,
        # ─── TEMA: as 4 colunas, e NENHUMA sai NULL (LEI 11) ───
        "tema": tema,                           # um dos 13, ou 'Sem tema' (que o contrato RETÉM)
        "tema_secundario": tema_secundario,     # 2º tema, ou 'Não se aplica' — nunca vazio
        "tema_origem": tema_origem,             # llm | mesh | fora_do_escopo | falha_do_classificador
        # 22/Ago — [] deixou de ser resposta aceitável. O Dr. Eduardo: "null e [] na prática
        # são a mesma coisa para mim". Vazio aqui significa DEFEITO, e a origem diz qual.
        "mesh_terms": mesh_terms,
        "mesh_origem": mesh_origem,             # pubmed · mesh_llm · falha
        "motor": motor,                         # ORIGINAL | META | DIRETRIZ | REVISAO — a régua usada
        "tipo_documento": tipo_documento,
        "veredito_dominios": veredito_dominios,  # jsonb: os domínios medidos que produziram a nota
        "publicar_no_site": False,              # sobe como rascunho; você libera no Administrador/site
        "created_at": datetime.date.today().isoformat(),
        "_fracao_ejecao": fracao_ejecao,        # METADADO (prefixo _ → NÃO sobe): trava de inversão FE no contrato
        "_desenho": desenho,                    # METADADO: alimenta a trava CAIXA ERRADA do contrato (10/Ago)
    }
