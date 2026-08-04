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
    if fatos_f:
        try:
            _f = json.load(open(fatos_f[0], encoding="utf-8"))
            fracao_ejecao = _f.get("fracao_ejecao")
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
        except Exception:
            pass

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
    NAO_SE_APLICA = "nao_se_aplica"   # o tipo do documento não tem esse conceito. Nunca terá.
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
    ano = _data_valida(_campo(canon, "ano")) or _data_valida(_n.get("ano", ""))   # 04/Ago: 2ª fonte, o nome do PubMed
    tipo = _campo(canon, "tipo")
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

    return {                                    # nomes = colunas REAIS da tabela artigos (Supabase)
        "doc_id": doi if doi and doi != "n/a" else slugify(titulo),
        "doi": doi if doi and doi != "n/a" else None,   # SEM doi → NULL (não ""): dois "" colidem na UNIQUE(doi)
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
        "motor": motor,                         # ORIGINAL | META | DIRETRIZ | REVISAO — a régua usada
        "tipo_documento": tipo_documento,
        "veredito_dominios": veredito_dominios,  # jsonb: os domínios medidos que produziram a nota
        "publicar_no_site": False,              # sobe como rascunho; você libera no Administrador/site
        "descartado": False,
        "created_at": datetime.date.today().isoformat(),
        "_fracao_ejecao": fracao_ejecao,        # METADADO (prefixo _ → NÃO sobe): trava de inversão FE no contrato
    }
