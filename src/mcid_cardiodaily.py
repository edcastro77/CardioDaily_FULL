"""
mcid_cardiodaily.py — OS LIMIARES DO CARDIODAILY (05/Ago/2026).

═══════════════════════════════════════════════════════════════════════════════════════
POR QUE ESTE ARQUIVO EXISTE
═══════════════════════════════════════════════════════════════════════════════════════

Medido em 05/Ago, nas 24 meta-análises do lote:

    mcid_reportado = false ............ 21 de 24
    efeito_excede_limiar = null ....... 22 de 24
    ic_sustenta_relevancia = null ..... 24 de 24   ← NUNCA respondido, nem uma vez

Os tetos 6 e 7 que a régua nova criou (efeito não excede o limiar · IC não sustenta) eram, na
prática, DECORATIVOS: `null` não capa, de propósito, e o extrator respondia `null` porque não
tinha contra o que comparar. **21 de 24 meta-análises não declaram limiar de importância clínica.**

Isso não é falha do extrator. É a fotografia da literatura — do mesmo jeito que Trim-and-Fill em
1/24 e TSA em 2/24. O artigo não diz o que considera clinicamente relevante.

A decisão do Dr. Eduardo (opção B, 05/Ago): **quando o artigo não declara limiar, o CardioDaily
aplica o SEU.** Nas palavras do que ele vem construindo o dia todo — quem decide o que importa
para o paciente é o cardiologista, não o autor do artigo.

É isto que separa o CardioDaily de um resumidor: a régua tem dono, tem número e é auditável.

═══════════════════════════════════════════════════════════════════════════════════════
COMO MEXER NISTO
═══════════════════════════════════════════════════════════════════════════════════════

Todo número aqui é do Dr. Eduardo e pode ser mudado por ele SEM tocar em código de motor.
Discordou de um limiar? Muda a linha, roda a bateria (`teste_motor.py`), pronto.

A trava `teste_mcid_cardiodaily` reprova se a tabela sumir ou se um limiar virar zero.
"""

# ═══════════════════════════════════════════════════════════════════════════════════════
# DESFECHO DURO — morte, IAM, AVC, hospitalização por insuficiência cardíaca
# ═══════════════════════════════════════════════════════════════════════════════════════
#
# Régua dele, e já estava escrita no prompt do artigo original desde antes ("ARD ≥1%/ano
# relevante"). Agora vira código.
#
# O RACIOCÍNIO: risco relativo engana. Uma RRR de 20% sobre um risco basal de 10%/ano evita
# 2 eventos em 100 pacientes-ano; a MESMA RRR de 20% sobre risco basal de 1%/ano evita 0,2.
# O primeiro muda a prática, o segundo é ruído com IC estreito. Por isso o limiar é ABSOLUTO.
#
#     ARR ≥ 1,0%/ano ......... relevante
#     ARR 0,5 a 1,0%/ano ..... limítrofe → o IC precisa sustentar (teto 7)
#     ARR < 0,5%/ano ......... não relevante (teto 6)
ARR_ANO_RELEVANTE = 1.0      # %/ano
ARR_ANO_LIMITROFE = 0.5      # %/ano

# O NNT VALORIZA, mas NÃO é régua — correção expressa dele em 04/Ago, ao definir a Escada.
NNT_IMPACTANTE = 25


# ═══════════════════════════════════════════════════════════════════════════════════════
# DESFECHO SUBSTITUTO — os valores consagrados da literatura
# ═══════════════════════════════════════════════════════════════════════════════════════
#
# ⚠️ O TETO 8 CONTINUA VALENDO: desfecho substituto não chega a 9, por melhor que seja o efeito.
# Estes limiares servem para distinguir substituto que MEXEU de substituto que não mexeu — não
# para promover substituto a desfecho duro.
#
# Cada linha traz a fonte, para você poder discordar com base.
LIMIAR_SUBSTITUTO = {
    # lipídios
    "ldl":        (30.0, "mg/dL", "CTT: ~39 mg/dL (1 mmol/L) → RR 0,78 em eventos maiores"),
    "colesterol": (30.0, "mg/dL", "idem LDL"),
    "lp(a)":      (25.0, "%",     "redução percentual; ensaios de fase 3 usam 25-30%"),
    "lpa":        (25.0, "%",     "idem"),
    "triglicer":  (30.0, "%",     "REDUCE-IT usou redução de ~20%; 30% é o consenso conservador"),

    # pressão
    "pressao sistolica": (5.0, "mmHg", "SPRINT/CTT: 5 mmHg → ~10% em eventos CV"),
    "pas":               (5.0, "mmHg", "idem"),
    "pressao diastolica":(3.0, "mmHg", "proporcional ao sistólico"),

    # função e estrutura cardíaca
    "feve":       (5.0,  "pontos %", "5 p.p. é o mínimo que muda classificação/indicação de CDI"),
    "fracao de ejecao": (5.0, "pontos %", "idem"),
    "gls":        (2.0,  "pontos %", "strain longitudinal global: 2 p.p. (EACVI)"),
    "strain":     (2.0,  "pontos %", "idem"),
    "massa vi":   (10.0, "%",        "regressão de HVE clinicamente relevante"),

    # biomarcadores
    "nt-probnp":  (30.0, "%", "PARADIGM-HF/GUIDE-IT: 30% de redução"),
    "ntprobnp":   (30.0, "%", "idem"),
    "bnp":        (30.0, "%", "idem"),
    "troponina":  (25.0, "%", "conservador; sem MCID consagrado para uso crônico"),

    # qualidade de vida e capacidade funcional
    "kccq":       (5.0,  "pontos", "5 pts = clinicamente importante; 10-15 = grande (Spertus)"),
    "mlhfq":      (5.0,  "pontos", "Minnesota: 5 pontos"),
    "sf-36":      (5.0,  "pontos", "5 pontos por domínio"),
    "6 minutos":  (30.0, "metros", "TC6M: 30-50 m; 30 é o piso"),
    "tc6m":       (30.0, "metros", "idem"),
    "caminhada":  (30.0, "metros", "idem"),
    "vo2":        (1.0,  "mL/kg/min", "VO2 pico: 1,0-1,5; 1,0 é o piso (Weisman)"),
}

# desfechos que NUNCA são "duros", por mais bonito que seja o número
SUBSTITUTOS = ("surrogate", "substituto", "biomarcador", "biomarker", "prom",
               "qualidade de vida", "laboratorial")


def _sem_acento(s):
    """Tira acento e normaliza — o extrator escreve 'pressão arterial sistólica', a tabela guarda
    'pressao sistolica'. Sem isto, o limiar da PA nunca casava (pego pela trava em 05/Ago)."""
    import unicodedata
    s = unicodedata.normalize("NFD", (s or "").lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def limiar_do_desfecho(nome_desfecho):
    """Devolve (valor, unidade, fonte) do limiar CardioDaily para um desfecho substituto.

    Casa por SUBSTRING em minúsculas — o extrator escreve o nome livremente
    ('LDL-colesterol', 'NT-proBNP aos 12 meses', 'KCCQ-OSS'). Devolve None se não reconhecer:
    limiar inventado é pior que limiar ausente.
    """
    n = _sem_acento(nome_desfecho).strip()
    if not n:
        return None
    # o mais específico primeiro (evita 'bnp' casar antes de 'nt-probnp')
    for chave in sorted(LIMIAR_SUBSTITUTO, key=len, reverse=True):
        if _sem_acento(chave) in n:
            return LIMIAR_SUBSTITUTO[chave]
    # 05/Ago: a PA vem escrita de mil jeitos — "pressão arterial sistólica", "PA sistólica",
    # "PAS de consultório". Casa por PALAVRAS presentes, não por sequência exata.
    if "sistolic" in n and ("pressao" in n or "pa " in n or n.startswith("pa")):
        return LIMIAR_SUBSTITUTO["pressao sistolica"]
    if "diastolic" in n and ("pressao" in n or "pa " in n or n.startswith("pa")):
        return LIMIAR_SUBSTITUTO["pressao diastolica"]
    return None


def eh_substituto(tipo_desfecho, nome_desfecho=""):
    """O desfecho é substituto? Olha o TIPO declarado e, se ele calar, o NOME."""
    t = _sem_acento(tipo_desfecho).strip()
    if any(_sem_acento(s) in t for s in SUBSTITUTOS):
        return True
    if t in ("continuo", "ordinal") and limiar_do_desfecho(nome_desfecho):
        return True          # contínuo que casa com a tabela de substitutos É substituto
    return False
