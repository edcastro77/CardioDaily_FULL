"""
contrato.py — O CONTRATO DE PUBLICAÇÃO (o portão anti-buraco).
Fonte única de verdade do que o site exige (interface `Artigo` do cardiodaily.ts).
Puro, sem dependências, testável. O Publicador NUNCA sobe nada que não passe por aqui.

Por que existe: no modelo antigo, o pipeline subia registro em branco pro Supabase e o site
renderizava card fantasma ("buracos ... supabase em branco destruía tudo"). Aqui o incompleto é RECUSADO.
"""
import os

# Campos = colunas REAIS da tabela artigos (Supabase). A tabela NÃO tem 'slug'.
CAMPOS = [
    "doc_id", "doi", "titulo", "revista", "data_publicacao", "tipo_estudo",
    "doenca_principal", "nota_aplicabilidade", "nota_trabalho_estatistico", "muda_conduta",
    "keywords", "contexto_tema", "aplicabilidade_pratica", "impacto_conduta",
    "bullets_praticos", "gancho_lista", "mcid_avaliacao", "resumo_markdown",
    "caminho_pdf", "caminho_audio", "caminho_visual_abstract",
    "publicar_no_site", "descartado", "created_at",
]

# Temas válidos (do site: cardiodaily.ts → TEMAS).
TEMAS = {
    "Coronária/DAC", "Arritmias", "Insuficiência Cardíaca", "Hipertensão",
    "Valvopatias", "Cardiologia Preventiva", "Imagem Cardíaca",
    "Cardiopatia Congênita", "Outros",
}


def _txt(v):
    return isinstance(v, str) and v.strip()


def validar(ficha, checar_arquivos=True):
    """Recebe a ficha (dict com os 16 campos). Devolve lista de VIOLAÇÕES (vazia = passou).
    Cada violação é uma string dizendo QUAL campo furou e por quê — vira o relatório do _REVISAR."""
    v = []

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
    n = ficha.get("nota_aplicabilidade")
    if not isinstance(n, int) or not (1 <= n <= 10):
        v.append(f"nota_aplicabilidade inválida: {n!r} (int 1–10)")
    elif n < 6:
        v.append(f"nota {n} < 6: por regra o artigo FICA retido (não publica). "
                 f"Bug real: um nota 5 foi parar no Supabase em 25/07.")

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

    return v


def passou(ficha, checar_arquivos=True):
    return len(validar(ficha, checar_arquivos)) == 0
