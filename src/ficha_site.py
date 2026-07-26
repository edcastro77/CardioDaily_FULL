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
import os, re, glob, unicodedata, datetime

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
    (("prevention", "statin", "lipid", "cholesterol", "aspirin"), "Cardiologia Preventiva"),
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
    return ""


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


def montar(pasta):
    """Lê uma pasta do STAGING e devolve a ficha (dict com os 16 campos)."""
    base = os.path.basename(pasta.rstrip("/"))
    can = glob.glob(os.path.join(pasta, "*_CANONICO.md"))
    canon = open(can[0], encoding="utf-8").read() if can else ""
    acri_f = glob.glob(os.path.join(pasta, "*_ACRI.txt"))
    acri = open(acri_f[0], encoding="utf-8").read() if acri_f else ""

    titulo = _campo(canon, "titulo")
    revista = _campo(canon, "revista")
    doi = _campo(canon, "doi")
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
    audio = arq("*_audio.mp3")
    visual = arq("*_visual*") or arq("*_INFOGRAFICO.png") or arq("*_infografico*")
    md = arq("*_analise.md")
    resumo = open(md, encoding="utf-8").read() if md else ""     # → resumo_markdown

    # campos extras que a tabela REAL usa (a tabela NÃO tem 'slug')
    ano = _data_valida(_campo(canon, "ano"))
    tipo = _campo(canon, "tipo")
    mrig = re.search(r"nota_trabalho_estatistico:\s*(\d+)", canon)
    rigor = int(mrig.group(1)) if mrig else None
    mcid_classe = _campo(canon, "classificacao")
    mcid_frase = _campo(canon, "frase_chave")
    mcid = f"[{mcid_classe}] {mcid_frase}" if (mcid_classe and mcid_classe != "n/a") else (mcid_frase or "")

    return {                                    # nomes = colunas REAIS da tabela artigos (Supabase)
        "doc_id": doi if doi and doi != "n/a" else slugify(titulo),
        "doi": doi if doi and doi != "n/a" else "",
        "titulo": titulo,
        "revista": revista,
        "data_publicacao": ano,
        "tipo_estudo": tipo,
        "doenca_principal": _tema(selo, keywords),
        "nota_aplicabilidade": nota,
        "nota_trabalho_estatistico": rigor,
        "muda_conduta": muda,
        "keywords": keywords,
        "contexto_tema": a_bloco,
        "aplicabilidade_pratica": aplic,
        "impacto_conduta": i_bloco,
        "bullets_praticos": bullets,
        "gancho_lista": gancho,
        "mcid_avaliacao": mcid,
        "resumo_markdown": resumo,
        "caminho_pdf": pdf,
        "caminho_audio": audio,
        "caminho_visual_abstract": visual,
        "publicar_no_site": False,              # sobe como rascunho; você libera no Administrador/site
        "descartado": False,
        "created_at": datetime.date.today().isoformat(),
    }
