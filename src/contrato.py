"""
contrato.py — O CONTRATO DE PUBLICAÇÃO (o portão anti-buraco).
Fonte única de verdade do que o site exige (interface `Artigo` do cardiodaily.ts).
Puro, sem dependências, testável. O Publicador NUNCA sobe nada que não passe por aqui.

Por que existe: no modelo antigo, o pipeline subia registro em branco pro Supabase e o site
renderizava card fantasma ("buracos ... supabase em branco destruía tudo"). Aqui o incompleto é RECUSADO.
"""
import os, re

# Campos = colunas REAIS da tabela artigos (Supabase). A tabela NÃO tem 'slug'.
CAMPOS = [
    "doc_id", "doi", "titulo", "revista", "data_publicacao", "tipo_estudo",
    "doenca_principal", "nota_aplicabilidade", "nota_trabalho_estatistico", "muda_conduta",
    "keywords", "contexto_tema", "aplicabilidade_pratica", "impacto_conduta",
    "bullets_praticos", "gancho_lista", "mcid_avaliacao", "resumo_markdown",
    "caminho_pdf", "caminho_audio", "caminho_visual_abstract",
    "publicar_no_site", "created_at",
]

# Temas válidos (do site: cardiodaily.ts → TEMAS).
TEMAS = {
    "Coronária/DAC", "Arritmias", "Insuficiência Cardíaca", "Hipertensão",
    "Valvopatias", "Cardiologia Preventiva", "Imagem Cardíaca",
    "Cardiopatia Congênita", "Outros",
}


def _txt(v):
    return isinstance(v, str) and v.strip()


# ═══ OS TRÊS SELOS E QUEM ACEITA CADA UM — 03/Ago/2026 ═══
# O `ficha_site` passou a nunca mandar campo vazio (o BANCO agora exige NOT NULL). Mas há dois
# tipos de "não vazio" com significados opostos, e misturá-los seria trocar um buraco por outro:
#
#   nao_se_aplica: …  → o TIPO não tem esse conceito (diretriz não tem desfecho primário). LEGÍTIMO.
#   nao_gerado: …     → não atingiu a porta por nota (áudio só ≥8). LEGÍTIMO.
#   ausente: …        → a peça DEVIA existir e não veio (bloco do ACRI vazio). É DEFEITO.
#
# ⚠️ O ERRO QUE ISTO CONSERTA, pego antes de rodar: os selos `ausente:` têm 27 a 48 caracteres, e o
# contrato aprovava por TAMANHO — `aplicabilidade_pratica` exige ≥40 e o selo tem 48; `impacto_conduta`
# exige ≥20 e o selo tem 30; `gancho_lista` exige ≥10 e o selo tem 27. Os três PASSARIAM.
# Eu teria fechado o buraco no banco e aberto um no portão editorial, que é o que importa.
# O banco garante que a linha está COMPLETA; o contrato garante que ela está BOA. Trabalhos diferentes.
PREFIXO_DEFEITO = "ausente:"


def validar(ficha, checar_arquivos=True):
    """Recebe a ficha (dict com os 16 campos). Devolve lista de VIOLAÇÕES (vazia = passou).
    Cada violação é uma string dizendo QUAL campo furou e por quê — vira o relatório do _REVISAR."""
    v = []

    # 0) SELO DE DEFEITO — vale mais que qualquer checagem de tamanho, e vem antes de todas.
    for c, valor in ficha.items():
        if c.startswith("_"):
            continue
        alvos = valor if isinstance(valor, list) else [valor]
        for x in alvos:
            if isinstance(x, str) and x.strip().startswith(PREFIXO_DEFEITO):
                v.append(f"{c}: {x.strip()} — a peça devia existir e não veio (RETÉM, não publica)")
                break

    # 1) presença de todos os campos
    for c in CAMPOS:
        if c not in ficha:
            v.append(f"campo ausente: {c}")

    # 2) identidade / texto obrigatório e coerente
    if not _txt(ficha.get("doc_id")):
        v.append("doc_id vazio")
    if not _txt(ficha.get("titulo")) or len(ficha.get("titulo", "").strip()) < 10:
        v.append("titulo vazio ou curto demais (<10 chars) — cheira a buraco de nome")
    if not _txt(ficha.get("revista")):
        v.append("revista vazia")

    # 3) tema
    dp = ficha.get("doenca_principal", "")
    if not _txt(dp):
        v.append("doenca_principal vazia")
    elif dp not in TEMAS:
        v.append(f"doenca_principal fora da lista do site: '{dp}'")

    # 4) nota (motor de rigor) — e a PORTA: nota <6 FICA retido, não vai pro site.
    #
    # ═══ 06/Ago — O CONTRATO NÃO SABIA DA EXCEÇÃO DA DIRETRIZ (LEI 9, cometida por mim) ═══
    #
    # Em 05/Ago o Dr. Eduardo decidiu: *"as diretrizes — precisamos manter esta classificação mas
    # não teremos NENHUM IMPEDIMENTO PARA SUBIR. Mesmo com as limitações, é o que tem para hoje."*
    # Eu implementei isso no `decidir_entregaveis` (analisador), escrevi a trava
    # `teste_diretriz_nao_tem_porta` mirando ali — e NÃO VARRI O CONTRATO, que é outro bloco e
    # decide sozinho. A trava ficou verde e a porta continuou fechada, em silêncio.
    #
    # MEDIDO na rodada real de 06/Ago: das 31 diretrizes, **13 RECUSADAS** — ESC (imagem, atleta,
    # HF familiar), AHA (ICFEp, atleta master, ética em transplante), ESPEN, NICE (hipertensão),
    # AACE. Exatamente os documentos pelos quais o cardiologista é cobrado na prática.
    #
    # POR QUE NÃO É BRECHA (as palavras dele, 05/Ago): para uma meta ruim existe outra melhor, e
    # reter não custa nada ao leitor. Com diretriz é o contrário — não existe "outra diretriz de
    # fibrilação atrial", existe A diretriz. Se ela é fraca, o médico precisa saber que é fraca
    # **e mesmo assim precisa dela**. Reter não protege ninguém: esconde o que rege a prática.
    # O aviso vem pela RECOMENDAÇÃO (RECOMENDADA · COM RESSALVAS · REFERÊNCIA · NÃO RECOMENDADA),
    # que informa em vez de barrar.
    #
    # ⚠️ A EXCEÇÃO É SÓ DA DIRETRIZ: *"ESTA REGRA SÓ VALE PARA DIRETRIZ."* Meta, revisão e artigo
    # original continuam retidos abaixo de 6 (LEI 10 — o CardioDaily publica menos e reprova mais).
    _eh_diretriz = str(ficha.get("tipo_documento") or "").strip().lower() == "diretriz"
    n = ficha.get("nota_aplicabilidade")
    if not isinstance(n, int) or not (1 <= n <= 10):
        v.append(f"nota_aplicabilidade inválida: {n!r} (int 1–10)")
    elif n < 6 and not _eh_diretriz:
        v.append(f"nota {n} < 6: por regra o artigo FICA retido (não publica). "
                 f"Bug real: um nota 5 foi parar no Supabase em 25/07.")

    # 4b) ═══ O DESENHO CONTRADIZ A CAIXA — RETÉM (10/Ago/2026) ═══
    #
    # É a rede de segurança da LEI 8, ponto 4: *"na dúvida, REVISÃO HUMANA. Classificar errado
    # custa mais caro que não classificar."* Todas as travas do classificador olham o artigo
    # ANTES de ler; esta olha DEPOIS, quando o extrator já leu o texto inteiro e disse o que viu.
    #
    # O CASO REAL (rodada de 10/Ago, 4 artigos): o classificador pôs em ARTIGOS_ORIGINAIS e o
    # extrator devolveu `desenho: meta`. Como o prompt e o motor obedecem à PASTA (LEI 8), os
    # quatro foram julgados com a régua do artigo original — e um Nature Medicine levou nota 3.
    # Ninguém a jusante percebeu, porque cada peça ficou internamente coerente e errada:
    # exatamente o que a LEI 8 descreve.
    #
    # POR QUE AQUI, E NÃO NO CLASSIFICADOR: o classificador decide pela primeira página; o
    # extrator lê o artigo todo. Quando os dois discordam, quem tem mais informação é o extrator
    # — mas ele não pode CORRIGIR a caixa (isso reabriria a "duas fontes de verdade" que a LEI 8
    # fechou). O que ele pode é DENUNCIAR, e a denúncia segura a publicação.
    #
    # NÃO é apagar nada: o pacote fica no STAGING com o `_REVISAR_publicacao.txt` dizendo a
    # contradição, e o Dr. Eduardo decide reclassificar ou aceitar.
    _DESENHO_DE_OUTRO_TIPO = {
        "meta": "meta-análise", "meta_analise": "meta-análise",
        "revisao_sistematica": "revisão sistemática", "revisao": "revisão",
        "revisao_narrativa": "revisão narrativa", "diretriz": "diretriz", "guideline": "diretriz",
    }
    _td = str(ficha.get("tipo_documento") or "").strip().lower()
    _de = str(ficha.get("_desenho") or ficha.get("desenho") or "").strip().lower()
    if _td == "original" and _de in _DESENHO_DE_OUTRO_TIPO:
        v.append(f"CAIXA ERRADA: está na trilha de artigo original, mas o extrator leu o texto "
                 f"inteiro e diz que o desenho é {_DESENHO_DE_OUTRO_TIPO[_de]} "
                 f"(desenho={_de!r}). Motor e prompt errados → nota errada (LEI 8). "
                 f"Reclassifique antes de publicar.")

    # 5) keywords
    kw = ficha.get("keywords")
    if not isinstance(kw, list) or len([k for k in kw if _txt(k)]) < 3:
        v.append("keywords: precisa de ≥3 não-vazias")

    # 6) os campos NARRATIVOS — onde o site fica em branco se ninguém preenche
    if not _txt(ficha.get("contexto_tema")) or len(ficha.get("contexto_tema", "")) < 40:
        v.append("contexto_tema vazio ou raso (<40 chars)")
    if not _txt(ficha.get("aplicabilidade_pratica")) or len(ficha.get("aplicabilidade_pratica", "")) < 40:
        v.append("aplicabilidade_pratica vazia ou rasa (<40 chars)")
    if not _txt(ficha.get("impacto_conduta")) or len(ficha.get("impacto_conduta", "")) < 20:
        v.append("impacto_conduta vazio ou raso (<20 chars)")
    bl = ficha.get("bullets_praticos")
    if not isinstance(bl, list) or len([b for b in bl if _txt(b)]) < 2:
        v.append("bullets_praticos: precisa de ≥2 não-vazios")
    if not _txt(ficha.get("gancho_lista")) or len(ficha.get("gancho_lista", "")) < 10:
        v.append("gancho_lista vazio ou curto (<10 chars)")

    # 7) arquivos — a peça central é o PDF da análise crítica (obrigatório)
    if checar_arquivos:
        pdf = ficha.get("caminho_pdf", "")
        if not _txt(pdf) or not os.path.exists(pdf):
            v.append(f"caminho_pdf ausente/inexistente: '{pdf}' (o PDF da análise é a peça central)")
        # áudio obrigatório só se nota ≥8 (porta do áudio); visual abstract só se ≥7
        if isinstance(n, int):
            aud = ficha.get("caminho_audio", "")
            if n >= 8 and (not _txt(aud) or not os.path.exists(aud)):
                v.append(f"nota ≥8 exige áudio, mas caminho_audio ausente: '{aud}'")
            vis = ficha.get("caminho_visual_abstract", "")
            if n >= 7 and not _txt(vis):
                v.append("nota ≥7 exige visual abstract (caminho_visual_abstract vazio)")

    # 8) created_at
    if not _txt(ficha.get("created_at")):
        v.append("created_at vazio")

    # 9) TRAVA DE FRAÇÃO DE EJEÇÃO — cadeado determinístico contra SIGLA TROCADA (buraco real 27/07:
    #    análise de HFpEF/preservada rotulada "ICFER" — e ICFER SIGNIFICA reduzida; a correta é ICFEP).
    #    A sigla tem sentido FIXO: ICFER/HFrEF = reduzida; ICFEP/HFpEF = preservada. Se a sigla no texto
    #    contradiz o fenótipo (FATO da extração), é inversão clínica → RECUSA — MESMO que a palavra certa
    #    apareche junto ("Preservada (ICFER)"). Olha a SIGLA, não a palavra solta (palavra pode ser contraste).
    #    Corrige o furo da 1ª versão, que exigia "nunca dizer preservada" e deixava passar "Preservada (ICFER)".
    fe = ficha.get("_fracao_ejecao")
    if fe in ("preservada", "reduzida"):
        alvo = " ".join(str(ficha.get(c, "")) for c in
                        ("titulo", "gancho_lista", "contexto_tema", "aplicabilidade_pratica",
                         "impacto_conduta", "resumo_markdown"))
        sigla_reduzida = re.search(r"\bIC-?FE[Rr]\b|\bHFrEF\b", alvo, re.I)      # ICFER, IC-FER, ICFEr, HFrEF
        sigla_preservada = re.search(r"\bIC-?FE[Pp]\b|\bHFpEF\b", alvo, re.I)    # ICFEP, IC-FEP, ICFEp, HFpEF
        if fe == "preservada" and sigla_reduzida:
            v.append(f"INVERSÃO FE: estudo de fração PRESERVADA mas o texto usa a sigla "
                     f"'{sigla_reduzida.group()}' (que significa REDUZIDA) — sigla trocada, buraco zero recusa")
        if fe == "reduzida" and sigla_preservada:
            v.append(f"INVERSÃO FE: estudo de fração REDUZIDA mas o texto usa a sigla "
                     f"'{sigla_preservada.group()}' (que significa PRESERVADA) — sigla trocada, buraco zero recusa")

    return v


def passou(ficha, checar_arquivos=True):
    return len(validar(ficha, checar_arquivos)) == 0
