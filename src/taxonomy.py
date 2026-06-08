# -*- coding: utf-8 -*-
"""
CardioDaily - Taxonomia Clínica Unificada
==========================================
FONTE ÚNICA DE VERDADE para classificação de doenças/temas.

25 categorias em Português — alinhadas com a prova de título de
especialista em Cardiologia (SBC/AMB).

Cada artigo recebe:
  • 1 categoria principal (doenca_principal)
  • até 3 palavras-chave clínicas (palavras_chave)

Autor: Dr. Eduardo Castro - CardioDaily
Atualizado: Fevereiro 2026
"""

# ============================================================================
# TAXONOMIA — 25 categorias (prova de título SBC/AMB)
# ============================================================================

TAXONOMY_CATEGORIES = [
    "Aortopatias",
    "Arritmias",
    "Cardiopatia Congênita",
    "Cardio-Oncologia",
    "Coronariopatia Aguda",
    "Coronariopatia Crônica",
    "Dislipidemias",
    "Exame Físico",
    "Farmacologia",
    "Genética",
    "Cardio-Obstetricia",
    "Insuficiencia Cardiaca",
    "Intervenção Vascular",
    "Hipertensão Arterial Sistêmica",
    "Imagem Cardiovascular",
    "Manifestações Cardiovasculares de Doenças Sistêmicas",
    "Marcapasso",
    "Miocardiopatias",
    "Parada Cardiorespiratória",
    "Choque",
    "Pericardiopatias",
    "Pré-Operatório",
    "Stroke",
    "Valvulopatias",
    "Outros",
]

# Set para validação rápida O(1)
TAXONOMY_SET = frozenset(TAXONOMY_CATEGORIES)


# ============================================================================
# MAPA DE MIGRAÇÃO — categorias antigas (inglês) → novas (PT-BR)
# Usado pelo indexar_corpus_completo.py para migrar artigos já indexados
# sem precisar re-chamar o LLM.
# ============================================================================

TAXONOMY_LEGACY_MAP: dict[str, str] = {
    # Arritmias
    "Atrial Fibrillation":                    "Arritmias",
    "Atrial Flutter":                          "Arritmias",
    "Ventricular Arrhythmias":                 "Arritmias",
    "Supraventricular Tachycardia":            "Arritmias",
    "Sudden Cardiac Death":                    "Arritmias",
    # Marcapasso
    "Bradyarrhythmias and Pacing":             "Marcapasso",
    # Insuficiência Cardíaca
    "Heart Failure General":                   "Insuficiencia Cardiaca",
    "HFrEF (Reduced Ejection Fraction)":       "Insuficiencia Cardiaca",
    "HFpEF (Preserved Ejection Fraction)":     "Insuficiencia Cardiaca",
    "HFmrEF (Mildly Reduced EF)":             "Insuficiencia Cardiaca",
    "Advanced Heart Failure":                  "Insuficiencia Cardiaca",
    # Coronariopatia Aguda
    "Acute Myocardial Infarction":             "Coronariopatia Aguda",
    "STEMI":                                   "Coronariopatia Aguda",
    "NSTEMI":                                  "Coronariopatia Aguda",
    "Acute Coronary Syndrome":                 "Coronariopatia Aguda",
    # Coronariopatia Crônica
    "Chronic Coronary Disease":                "Coronariopatia Crônica",
    # Intervenção Vascular
    "Coronary Revascularization (PCI/CABG)":   "Intervenção Vascular",
    "Transcatheter Valve Therapy (TAVR/TEER)": "Intervenção Vascular",
    "Peripheral Artery Disease":               "Intervenção Vascular",
    "Carotid Artery Disease":                  "Intervenção Vascular",
    # Valvulopatias
    "Aortic Stenosis":                         "Valvulopatias",
    "Aortic Regurgitation":                    "Valvulopatias",
    "Mitral Stenosis":                         "Valvulopatias",
    "Mitral Regurgitation":                    "Valvulopatias",
    "Tricuspid Regurgitation":                 "Valvulopatias",
    "Pulmonary Valve Disease":                 "Valvulopatias",
    "Infective Endocarditis":                  "Valvulopatias",
    "Prosthetic Valves":                       "Valvulopatias",
    # Pré-Operatório / Cirurgia
    "Cardiac Surgery":                         "Pré-Operatório",
    "Heart Transplantation":                   "Pré-Operatório",
    # Choque
    "Mechanical Circulatory Support (VAD/LVAD)": "Choque",
    # Miocardiopatias
    "Hypertrophic Cardiomyopathy":             "Miocardiopatias",
    "Dilated Cardiomyopathy":                  "Miocardiopatias",
    "Arrhythmogenic Cardiomyopathy (ARVC)":    "Miocardiopatias",
    "Restrictive Cardiomyopathy":              "Miocardiopatias",
    "Takotsubo Cardiomyopathy":                "Miocardiopatias",
    "Cardiac Amyloidosis":                     "Miocardiopatias",
    "Cardiac Sarcoidosis":                     "Miocardiopatias",
    "Myocarditis":                             "Miocardiopatias",
    # Cardio-Obstetricia
    "Peripartum Cardiomyopathy":               "Cardio-Obstetricia",
    # Genética
    "Fabry Disease":                           "Genética",
    "Genetic Cardiomyopathies (PKP2/LMNA/TTN)": "Genética",
    # Manifestações CV de Doenças Sistêmicas
    "Chagas Disease":                          "Manifestações Cardiovasculares de Doenças Sistêmicas",
    "Cardiac Hemochromatosis":                 "Manifestações Cardiovasculares de Doenças Sistêmicas",
    "Pulmonary Hypertension":                  "Manifestações Cardiovasculares de Doenças Sistêmicas",
    "Diabetes and Cardiovascular Disease":     "Manifestações Cardiovasculares de Doenças Sistêmicas",
    "Obesity and Metabolic Heart Disease":     "Manifestações Cardiovasculares de Doenças Sistêmicas",
    # Hipertensão
    "Systemic Hypertension":                   "Hipertensão Arterial Sistêmica",
    # Pericardiopatias
    "Pericarditis and Pericardial Disease":    "Pericardiopatias",
    # Cardio-Oncologia
    "Cardio-Oncology":                         "Cardio-Oncologia",
    # Farmacologia (apenas efeito adverso / mecanismo / interação — não eficácia)
    "Drug Adverse Effects":                    "Farmacologia",
    "Drug Interaction":                        "Farmacologia",
    "Pharmacokinetics":                        "Farmacologia",
    # SGLT2/GLP-1 → pela condição tratada
    "SGLT2 Inhibitors in Heart Failure":       "Insuficiência Cardíaca",
    "SGLT2 Inhibitors in Diabetes":            "Cardiometabólica",
    "GLP-1 Receptor Agonists (incl. Tirzepatide)": "Cardiometabólica",
    "Obesity Treatment":                       "Cardiometabólica",
    # Anticoagulação/antiplaquetário → pela condição
    "Anticoagulation Therapy":                 "Arritmias",
    "Antiplatelet Therapy":                    "Intervenção Vascular",
    "Cardiovascular Prevention":               "Prevenção CV",
    "Pulmonary Embolism":                      "Outros",
    "Deep Vein Thrombosis":                    "Outros",
    "Venous Thromboembolism":                  "Outros",
    # Dislipidemias
    "Lipid-Lowering Therapy (Statins/PCSK9)":  "Dislipidemias",
    "Dyslipidemia":                            "Dislipidemias",
    # Aortopatias
    "Aortic Aneurysm":                         "Aortopatias",
    "Aortic Dissection":                       "Aortopatias",
    # Imagem
    "Echocardiography":                        "Imagem Cardiovascular",
    "Cardiac MRI":                             "Imagem Cardiovascular",
    "Cardiac CT":                              "Imagem Cardiovascular",
    "Nuclear Cardiology":                      "Imagem Cardiovascular",
    # Cardiopatia Congênita
    "Adult Congenital Heart Disease":          "Cardiopatia Congênita",
    # Outros
    "Statistics and Methodology":              "Outros",
    "Cardiac Rehabilitation":                  "Outros",
    "Sports Cardiology":                       "Outros",
    "Cardiopulmonary Exercise Testing":        "Outros",
    "Palliative Care in Cardiology":           "Outros",
    "Other":                                   "Outros",
}


# ============================================================================
# PROMPT DE CLASSIFICAÇÃO
# ============================================================================

PROMPT_CLASSIFICATION = """
Você é um cardiologista especialista classificando literatura médica para
estudo de prova de título de especialista em Cardiologia (SBC/AMB).

TAREFA:
Analise o artigo e retorne:
1. A categoria principal (1 das 25 abaixo)
2. Até 3 palavras-chave clínicas específicas (termos técnicos precisos)

CATEGORIAS VÁLIDAS:
{categories}

REGRAS DE CLASSIFICAÇÃO:
- Stroke / AVC / oclusão de artéria basilar / trombectomia mecânica → "Stroke"
- Insuficiência cardíaca (HFrEF, HFpEF, HFmrEF, IC avançada) → "Insuficiencia Cardiaca"
- FA, flutter, TSV, TV, morte súbita → "Arritmias"
- IAM, STEMI, NSTEMI, SCA → "Coronariopatia Aguda"
- DAC estável, angina crônica → "Coronariopatia Crônica"
- TAVI, TEER, MitraClip, PCI, CABG, intervenção periférica → "Intervenção Vascular"
- Estenose aórtica, regurgitação mitral/tricúspide, endocardite, prótese → "Valvulopatias"
- Aneurisma de aorta, dissecção aórtica → "Aortopatias"
- CMH, MCD, amiloidose, miocardite, sarcoidose → "Miocardiopatias"
- Estatinas, PCSK9, LDL → "Dislipidemias"
- SGLT2 para IC → "Insuficiência Cardíaca" | SGLT2/GLP-1 para DM/obesidade → "Cardiometabólica"
- Anticoagulantes em FA → "Arritmias" | antiplaquetários pós-ICP → "Intervenção Vascular"
- "Farmacologia" SOMENTE quando o foco é efeito adverso, interação ou mecanismo do fármaco — NUNCA para estudos de eficácia clínica
- Gestação, periparto, SCAD, pré-eclâmpsia → "Cardio-Obstetricia"
- Cardiotoxicidade, imunoterapia, quimioterapia → "Cardio-Oncologia"
- ECO, RM cardíaca, TC cardíaca → "Imagem Cardiovascular"
- Marcapasso, CDI, CRT → "Marcapasso"
- Pericardite, tamponamento → "Pericardiopatias"
- HAS, hipertensão resistente → "Hipertensão Arterial Sistêmica"
- CHIP, PKP2, LMNA, canalopatias, Fabry → "Genética"
- Cardiopatia congênita → "Cardiopatia Congênita"
- Choque cardiogênico, ECMO, Impella → "Choque"
- PCR, ressuscitação cardiopulmonar → "Parada Cardiorespiratória"
- Avaliação pré-operatória, cirurgia cardíaca, pós-operatório → "Pré-Operatório"
- Diabetes, lúpus, amiloidose, Chagas, HIV cardíaco → "Manifestações Cardiovasculares de Doenças Sistêmicas"
- Use "Outros" APENAS para temas não cardiovasculares

ARTIGO:
Título: {title}
Conteúdo: {content}

Responda APENAS com JSON (sem markdown):
{{"category": "categoria exata da lista", "palavras_chave": ["termo1", "termo2", "termo3"], "population": ["lista"], "intervention": ["lista"]}}

IMPORTANTE: palavras_chave devem ser termos clínicos específicos do artigo
(ex: "oclusão de artéria basilar", "trombectomia mecânica", "outcome funcional 90 dias")
— não categorias genéricas.
"""


# ============================================================================
# FUNÇÕES DE VALIDAÇÃO
# ============================================================================

def migrate_legacy_category(value: str) -> str | None:
    """
    Converte categoria antiga (inglês, 73 cats) para nova (PT-BR, 25 cats).
    Retorna None se não houver mapeamento (indica re-classificação necessária).
    """
    if not value:
        return None
    # Já é categoria nova?
    if value in TAXONOMY_SET:
        return value
    # Mapeamento direto
    if value in TAXONOMY_LEGACY_MAP:
        return TAXONOMY_LEGACY_MAP[value]
    # Match case-insensitive
    v_low = value.lower()
    for old, new in TAXONOMY_LEGACY_MAP.items():
        if old.lower() == v_low:
            return new
    return None


def validate_category(value: str) -> str:
    """
    Valida e normaliza categoria.
    Tenta: exato → legacy map → parcial → 'Outros'.
    """
    if not value or not isinstance(value, str):
        return "Outros"

    value_stripped = value.strip()

    # Match exato na taxonomia nova
    if value_stripped in TAXONOMY_SET:
        return value_stripped

    # Migração de categoria antiga
    migrated = migrate_legacy_category(value_stripped)
    if migrated:
        return migrated

    # Match case-insensitive na taxonomia nova
    v_low = value_stripped.lower()
    for cat in TAXONOMY_CATEGORIES:
        if cat.lower() == v_low:
            return cat

    # Match parcial
    for cat in TAXONOMY_CATEGORIES:
        if v_low in cat.lower() or cat.lower() in v_low:
            return cat

    return "Outros"


def get_categories_string() -> str:
    """Retorna categorias separadas por vírgula (para prompts)."""
    return ", ".join(TAXONOMY_CATEGORIES)


# ============================================================================
# EXECUÇÃO DIRETA (diagnóstico)
# ============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("CARDIODAILY - TAXONOMIA CLÍNICA (Prova de Título SBC/AMB)")
    print("=" * 60)
    print(f"\nTotal de categorias: {len(TAXONOMY_CATEGORIES)}")
    print(f"Entradas de migração: {len(TAXONOMY_LEGACY_MAP)}")

    print("\n📋 CATEGORIAS:")
    for i, cat in enumerate(TAXONOMY_CATEGORIES, 1):
        print(f"  {i:2}. {cat}")

    print("\n🧪 TESTES:")
    tests = [
        ("Stroke",                          "Stroke"),
        ("Atrial Fibrillation",             "Arritmias"),
        ("Heart Failure General",           "Insuficiencia Cardiaca"),
        ("STEMI",                           "Coronariopatia Aguda"),
        ("Aortic Stenosis",                 "Valvulopatias"),
        ("Cardiac Amyloidosis",             "Miocardiopatias"),
        ("Echocardiography",                "Imagem Cardiovascular"),
        ("Other",                           "Outros"),
        ("Other",                           "Outros"),
        ("Insuficiencia Cardiaca",          "Insuficiencia Cardiaca"),
        ("", "Outros"),
    ]
    for input_val, expected in tests:
        result = validate_category(input_val)
        status = "✅" if result == expected else "❌"
        print(f"  {status} '{input_val}' → '{result}' (esperado: '{expected}')")
