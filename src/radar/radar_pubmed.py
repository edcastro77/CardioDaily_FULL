#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CardioDaily — Radar PubMed
Backend: busca PubMed + análise Gemini + áudio OpenAI TTS
Dr. Eduardo Castro
"""

import os
import re
import ssl
import time
import json
import requests
from datetime import datetime, timedelta
from pathlib import Path
from collections import Counter
from io import StringIO
from xml.etree import ElementTree as ET

# Fix SSL para PubMed
ssl._create_default_https_context = ssl._create_unverified_context

try:
    from Bio import Entrez, Medline
    BIO_AVAILABLE = True
except ImportError:
    BIO_AVAILABLE = False

try:
    from google import genai
    from google.genai import types
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

# ─── Categorias ───────────────────────────────────────────────────────────────

CATEGORIAS = {
    'doenca_coronariana': [
        # Síndromes agudas
        'acute coronary syndrome', 'myocardial infarction', 'STEMI', 'NSTEMI',
        'non-ST-elevation myocardial infarction', 'unstable angina',
        # Doença crônica
        'chronic coronary syndrome', 'stable coronary artery disease',
        'coronary artery disease', 'angina pectoris', 'coronary atherosclerosis',
        # Antiplaquetários e antitrombóticos
        'dual antiplatelet therapy', 'DAPT', 'antiplatelet therapy',
        'ticagrelor', 'prasugrel', 'clopidogrel', 'aspirin cardiovascular',
        'thrombolysis myocardial infarction',
        # Diagnóstico
        'coronary angiography', 'stress echocardiography coronary',
        'exercise stress test', 'coronary calcium score', 'calcium score cardiovascular',
        'myocardial perfusion scintigraphy', 'cardiac stress MRI',
        # Revascularização
        'coronary revascularization', 'complete revascularization',
        'coronary artery bypass graft', 'CABG outcomes',
        # Fisiologia coronária / imagem intracoronária
        'fractional flow reserve coronary', 'FFR coronary', 'instantaneous wave-free ratio', 'iFR',
        'intravascular ultrasound coronary', 'IVUS coronary',
        'chronic total occlusion', 'CTO revascularization',
        # Tratamento clínico e reabilitação
        'optimized medical therapy coronary', 'post-infarction rehabilitation',
        'hibernating myocardium', 'stunned myocardium',
        # SCAD
        'spontaneous coronary artery dissection', 'SCAD',
        # Biomarcadores
        'high-sensitivity troponin', 'troponin myocardial infarction',
    ],

    'cardio_metabolica': [
        # GLP-1 / GIP
        'GLP-1 receptor agonist cardiovascular', 'GLP-1 agonist heart failure',
        'semaglutide cardiovascular', 'liraglutide cardiovascular',
        'tirzepatide cardiovascular', 'dulaglutide cardiovascular',
        'obesity cardiovascular outcomes', 'weight loss cardiovascular',
        # SGLT2
        'SGLT2 inhibitor cardiovascular', 'empagliflozin', 'dapagliflozin', 'canagliflozin',
        # Diabetes e síndrome metabólica
        'diabetes mellitus cardiovascular outcomes', 'type 1 diabetes cardiovascular',
        'type 2 diabetes cardiovascular', 'insulin resistance cardiovascular',
        'metabolic syndrome cardiovascular', 'cardiovascular kidney metabolic syndrome',
        'visceral fat cardiovascular', 'lean mass cardiovascular',
        # Dislipidemia
        'dyslipidemia cardiovascular', 'hypertriglyceridemia cardiovascular',
        # Hipertensão e doença vascular
        'hypertension cardiovascular risk', 'blood pressure cardiovascular outcomes',
        'antihypertensive therapy outcomes', 'preeclampsia cardiovascular risk',
        'pulmonary hypertension outcomes',
        # Estilo de vida e prevenção
        'diet nutrition cardiovascular', 'exercise cardiovascular outcomes',
        'lifestyle intervention cardiovascular', 'sleep health cardiovascular',
        'mental health cardiovascular', 'physical activity cardiovascular',
        # Prevenção primária e secundária
        'primary prevention cardiovascular', 'secondary prevention cardiovascular',
        'cardiovascular risk factors prevention',
        # Populações especiais
        'women cardiovascular outcomes', 'sex differences cardiovascular',
        'gender cardiovascular', 'pediatric cardiovascular',
        'race ethnicity cardiovascular disparities',
        'pregnancy cardiovascular outcomes',
    ],

    'arritmias': [
        # FA
        'atrial fibrillation', 'atrial flutter', 'catheter ablation atrial fibrillation',
        'pulmonary vein isolation', 'rhythm control atrial fibrillation',
        'rate control atrial fibrillation', 'cardioversion atrial fibrillation',
        # Anticoagulação
        'direct oral anticoagulant', 'DOAC', 'anticoagulation atrial fibrillation',
        'stroke prevention atrial fibrillation', 'left atrial appendage occlusion',
        'WATCHMAN', 'warfarin atrial fibrillation',
        # Arritmias ventriculares
        'ventricular tachycardia', 'ventricular fibrillation',
        'sudden cardiac death', 'sudden cardiac arrest',
        'catheter ablation ventricular tachycardia',
        # Dispositivos
        'implantable cardioverter defibrillator', 'ICD', 'subcutaneous ICD',
        'wearable defibrillator',
        # Estimulação
        'pacemaker', 'cardiac resynchronization therapy', 'CRT',
        'conduction system pacing', 'left bundle branch pacing', 'His bundle pacing',
        # Síndromes
        'long QT syndrome', 'Brugada syndrome', 'Wolff-Parkinson-White',
        'supraventricular tachycardia',
    ],

    'insuficiencia_cardiaca': [
        # Geral
        'heart failure', 'HFrEF', 'HFpEF', 'HFmrEF',
        'heart failure with reduced ejection fraction',
        'heart failure with preserved ejection fraction',
        # Farmacologia
        'sacubitril valsartan', 'neprilysin inhibitor',
        'SGLT2 inhibitor heart failure', 'empagliflozin heart failure',
        'dapagliflozin heart failure', 'vericiguat', 'omecamtiv mecarbil',
        'beta blocker heart failure', 'ACE inhibitor heart failure',
        'mineralocorticoid receptor antagonist', 'finerenone',
        # Deficiência de ferro
        'iron deficiency heart failure', 'ferric carboxymaltose heart failure',
        'intravenous iron heart failure',
        # Biomarcadores e monitorização
        'natriuretic peptide heart failure', 'BNP heart failure', 'NT-proBNP',
        'remote monitoring heart failure', 'CardioMEMS',
        # Síndrome cardiorrenal
        'cardiorenal syndrome', 'cardiorenal interaction',
        # Etiologias e comorbidades
        'cardiomyopathy heart failure', 'chronic ischemic heart disease heart failure',
        'congenital heart disease heart failure', 'cardiac hypertrophy',
        'left ventricular hypertrophy heart failure',
        # Avaliação funcional
        'cardiopulmonary exercise test heart failure', 'VO2 max heart failure',
        'exercise capacity heart failure',
        # Remodelamento e dispositivos
        'cardiac remodeling heart failure', 'ventricular remodeling',
        'cardiac resynchronization therapy heart failure', 'CRT-D',
        'implantable cardioverter defibrillator heart failure',
        'left ventricular assist device', 'LVAD outcomes',
        # Transplante
        'heart transplantation outcomes', 'cardiac transplant',
        # Hospitalização
        'heart failure hospitalization', 'worsening heart failure', 'acute decompensated heart failure',
    ],

    'valvulopatias': [
        # Estenose aórtica
        'aortic stenosis', 'TAVI', 'TAVR', 'transcatheter aortic valve',
        'surgical aortic valve replacement SAVR', 'aortic valve stenosis outcomes',
        'low-flow low-gradient aortic stenosis',
        # Mitral
        'mitral regurgitation', 'MitraClip', 'transcatheter mitral valve repair',
        'mitral valve repair', 'mitral valve replacement',
        'mitral stenosis', 'rheumatic mitral stenosis',
        'TEER mitral', 'transcatheter mitral valve replacement TMVR',
        # Tricúspide
        'tricuspid regurgitation', 'transcatheter tricuspid valve',
        'tricuspid valve repair', 'TRILUMINATE', 'TRISCEND',
        # Pulmonar
        'pulmonary valve replacement', 'transcatheter pulmonary valve',
        # Endocardite
        'infective endocarditis', 'endocarditis outcomes',
        'endocarditis surgery', 'endocarditis antibiotic treatment',
        # Doença valvar reumática
        'rheumatic heart disease', 'rheumatic valve disease',
        # Próteses
        'metallic prosthetic valve', 'biological prosthetic valve',
        'prosthetic valve outcomes', 'valve-in-valve',
        # Geral
        'valve replacement outcomes', 'bioprosthesis valve',
        'prosthetic valve thrombosis',
    ],

    'miocardiopatias': [
        # Miocardiopatia hipertrófica
        'hypertrophic cardiomyopathy', 'HCM', 'obstructive hypertrophic cardiomyopathy',
        'mavacamten', 'aficamten', 'cardiac myosin inhibitor',
        'septal reduction therapy', 'alcohol septal ablation',
        # Miocardiopatia dilatada
        'dilated cardiomyopathy', 'DCM', 'non-ischemic cardiomyopathy',
        # Amiloidose
        'cardiac amyloidosis', 'transthyretin amyloidosis', 'ATTR amyloidosis',
        'tafamidis', 'acoramidis', 'patisiran cardiac', 'vutrisiran cardiac',
        # Miocardite e doença inflamatória
        'myocarditis', 'immune checkpoint myocarditis', 'giant cell myocarditis',
        'viral myocarditis', 'inflammatory cardiomyopathy',
        # Cardiotoxicidade (não oncológica)
        'cardiotoxicity cardiomyopathy', 'drug-induced cardiomyopathy',
        # Doença pericárdica
        'pericarditis', 'pericardial disease', 'pericardial effusion',
        'constrictive pericarditis', 'pericardiocentesis',
        # Outras miocardiopatias
        'arrhythmogenic cardiomyopathy', 'ARVC', 'left ventricular non-compaction',
        'cardiac sarcoidosis', 'Fabry disease cardiac', 'Danon disease',
        'Chagas cardiomyopathy', 'Chagas disease cardiac',
    ],

    'intervencao_hemodinamica': [
        # ICP
        'percutaneous coronary intervention', 'PCI outcomes',
        'drug-eluting stent', 'bioresorbable scaffold',
        'complex PCI', 'left main PCI', 'bifurcation PCI', 'bifurcation stenting',
        'chronic total occlusion PCI', 'CTO PCI',
        # Imagem intracoronária
        'intravascular ultrasound', 'IVUS guided PCI',
        'optical coherence tomography coronary', 'OCT guided PCI',
        # Fisiologia
        'fractional flow reserve', 'FFR guided PCI',
        'instantaneous wave-free ratio PCI', 'iFR',
        # Técnicas de aterectomia
        'rotational atherectomy', 'orbital atherectomy',
        'intravascular lithotripsy', 'coronary atherectomy',
        # Suporte hemodinâmico
        'mechanical circulatory support PCI', 'Impella PCI',
        'high-risk PCI outcomes',
        # Structural
        'structural heart disease intervention', 'transcatheter structural',
        # Cirurgia cardíaca
        'coronary artery bypass surgery', 'CABG surgery outcomes',
        'robotic cardiac surgery', 'minimally invasive cardiac surgery',
        'off-pump coronary artery bypass',
        # Anticoagulação perioperatória
        'anticoagulation cardiac surgery', 'antiplatelet cardiac surgery',
        # Transplante e reabilitação
        'cardiac transplantation surgery', 'cardiac rehabilitation outcomes',
    ],

    'cardio_oncologia': [
        # Cardiotoxicidade
        'cardiotoxicity chemotherapy', 'anthracycline cardiotoxicity',
        'anthracycline cardiomyopathy', 'doxorubicin cardiotoxicity',
        # Imunoterapia
        'immune checkpoint inhibitor cardiac', 'checkpoint inhibitor myocarditis',
        'pembrolizumab cardiac', 'nivolumab cardiac',
        # Terapias alvo
        'HER2 cardiotoxicity', 'trastuzumab cardiotoxicity',
        'tyrosine kinase inhibitor cardiac', 'VEGF inhibitor cardiovascular',
        'BTK inhibitor atrial fibrillation', 'ibrutinib cardiovascular',
        # Radioterapia
        'radiation-induced heart disease', 'radiation cardiotoxicity',
        # Prevenção e monitorização
        'cardio-oncology surveillance', 'cardioprotection cancer therapy',
        'cancer cardiovascular risk', 'cancer therapy cardiovascular outcomes',
        # CAR-T
        'CAR-T cell cardiac', 'chimeric antigen receptor cardiovascular',
    ],

    'cardiobstetrica': [
        # Miocardiopatia periparto
        'peripartum cardiomyopathy', 'PPCM', 'bromocriptine peripartum cardiomyopathy',
        # SCAD
        'spontaneous coronary artery dissection pregnancy', 'SCAD pregnancy',
        # Hipertensão na gravidez
        'preeclampsia cardiovascular', 'hypertension pregnancy cardiovascular',
        'gestational hypertension outcomes',
        # Cardiopatia congênita e gravidez
        'congenital heart disease pregnancy', 'heart disease pregnancy outcomes',
        # Anticoagulação na gravidez
        'anticoagulation pregnancy', 'heparin pregnancy cardiac',
        # Arritmias na gravidez
        'arrhythmia pregnancy', 'atrial fibrillation pregnancy',
        # Risco cardiovascular pós-gestacional
        'pregnancy complications cardiovascular risk', 'preeclampsia future cardiovascular',
        'maternal cardiovascular outcomes',
        # Intervenção na gravidez
        'cardiac intervention pregnancy', 'TAVI pregnancy',
    ],

    'cardio_genomica': [
        # Genética de doenças cardiovasculares
        'genetic cardiovascular disease', 'cardiovascular genetics',
        'inherited heart disease', 'hereditary cardiomyopathy',
        # Risco poligênico
        'polygenic risk score cardiovascular', 'polygenic risk cardiovascular prevention',
        # GWAS
        'genome-wide association cardiovascular', 'GWAS cardiovascular',
        # Hipercolesterolemia familiar
        'familial hypercholesterolemia genetics', 'PCSK9 genetic',
        'lipoprotein a genetics', 'Lp(a) genetics',
        # Arritmias hereditárias
        'inherited arrhythmia syndrome', 'long QT syndrome genetics',
        'Brugada syndrome genetics', 'catecholaminergic polymorphic VT',
        # Terapia genética
        'gene therapy cardiovascular', 'RNA therapy cardiovascular',
        'CRISPR cardiovascular', 'base editing cardiovascular',
        # Farmacogenômica e precisão
        'pharmacogenomics cardiology', 'clopidogrel pharmacogenomics',
        'precision medicine cardiology', 'precision cardiovascular medicine',
        # Saúde digital
        'digital health cardiology', 'artificial intelligence cardiology',
        'machine learning cardiovascular', 'wearable cardiovascular',
        'remote patient monitoring cardiovascular',
        # Qualidade, desfechos e equidade
        'quality of care cardiology', 'quality improvement cardiovascular',
        'cardiovascular outcomes research', 'mortality cardiovascular outcomes',
        'health disparities cardiovascular', 'equitable cardiovascular care',
        'social determinants cardiovascular', 'race ethnicity cardiovascular outcomes',
        # Política, diretrizes e saúde pública
        'cardiovascular guidelines implementation', 'clinical practice guidelines cardiovascular',
        'health policy cardiovascular', 'ethics cardiology',
        'health services research cardiovascular', 'cost-effectiveness cardiovascular',
    ],

    'uti_cardiologica': [
        # Choque cardiogênico
        'cardiogenic shock', 'cardiogenic shock outcomes',
        'cardiogenic shock management', 'cardiogenic shock registry',
        # Suporte mecânico
        'Impella cardiogenic shock', 'IABP cardiogenic shock',
        'ECMO cardiogenic shock', 'veno-arterial ECMO',
        'mechanical circulatory support cardiogenic shock',
        'temporary mechanical circulatory support',
        # Vasoativos
        'vasopressors cardiogenic shock', 'norepinephrine cardiogenic shock',
        'dobutamine heart failure', 'levosimendan acute heart failure',
        # Parada cardíaca
        'cardiac arrest resuscitation', 'out-of-hospital cardiac arrest',
        'in-hospital cardiac arrest', 'ROSC outcomes',
        'post-cardiac arrest care', 'targeted temperature management',
        # VD e monitorização
        'right ventricular failure ICU', 'right heart failure acute',
        'pulmonary artery catheter', 'hemodynamic monitoring ICU',
        # IC aguda
        'acute decompensated heart failure ICU', 'acute heart failure ICU management',
        # Complicações e custo
        'complications cardiac intensive care', 'cardiac ICU complications',
        'cost-effectiveness cardiac ICU', 'critical care cardiology outcomes',
    ],

    'aorta_congenitas': [
        # Aneurisma aórtico
        'aortic aneurysm', 'thoracic aortic aneurysm', 'abdominal aortic aneurysm',
        'aortic root aneurysm',
        # Dissecção aórtica
        'aortic dissection', 'aortic dissection type A', 'aortic dissection type B',
        'acute aortic syndrome', 'intramural hematoma aorta', 'penetrating aortic ulcer',
        # Intervenção
        'TEVAR thoracic', 'EVAR', 'open aortic repair', 'aortic surgery outcomes',
        # Síndromes genéticas
        'Marfan syndrome aorta', 'bicuspid aortic valve aortopathy',
        'Loeys-Dietz syndrome', 'Ehlers-Danlos cardiovascular',
        # Cardiopatias congênitas do adulto
        'adult congenital heart disease', 'ACHD',
        'Fontan circulation outcomes', 'tetralogy of Fallot adult',
        'transposition of great arteries adult', 'Eisenmenger syndrome',
        'atrial septal defect closure', 'ventricular septal defect adult',
        'patent foramen ovale closure', 'PFO closure stroke',
    ],

    'imagem_cardiovascular': [
        # Ecocardiografia
        'echocardiography outcomes', 'strain echocardiography', 'global longitudinal strain',
        '3D echocardiography', 'transesophageal echocardiography',
        'point-of-care echocardiography', 'stress echocardiography',
        'artificial intelligence echocardiography',
        # Ressonância magnética
        'cardiac MRI', 'cardiac magnetic resonance outcomes',
        'late gadolinium enhancement', 'cardiac MRI cardiomyopathy',
        'CMR myocarditis', 'CMR viability', 'cardiac fMRI',
        # TC cardíaca
        'coronary CT angiography', 'CCTA', 'cardiac CT',
        'CT fractional flow reserve', 'FFRCT',
        'coronary artery calcium score', 'CAC score',
        'CT calcium scoring cardiovascular risk', 'cardiac CT angiography',
        # Medicina nuclear
        'nuclear cardiology', 'myocardial perfusion imaging',
        'PET myocardial perfusion', 'FDG PET cardiac',
        'cardiac amyloidosis scintigraphy', 'pyrophosphate scan ATTR',
        # OCT e imagem intracoronária
        'optical coherence tomography cardiovascular', 'OCT cardiovascular imaging',
        # ECG e teste de esforço
        'ECG cardiovascular diagnosis', 'electrocardiogram cardiovascular',
        'exercise testing cardiovascular prognosis',
        'exercise ECG cardiovascular',
        # Ultrassom vascular
        'vascular ultrasound cardiovascular', 'carotid ultrasound cardiovascular risk',
        'ankle-brachial index', 'vascular imaging outcomes',
        # Angiografia
        'invasive coronary angiography', 'cardiac catheterization',
        # Prognóstico por imagem
        'cardiovascular imaging prognosis', 'imaging biomarkers cardiovascular',
        # IA em imagem
        'artificial intelligence cardiac imaging', 'deep learning echocardiography',
        'machine learning cardiac CT',
        # Multimodalidade
        'multimodality imaging cardiology', 'hybrid imaging cardiovascular',
    ],
}

CATEGORIAS_PT = {
    'doenca_coronariana':       'Coronária/DAC',
    'cardio_metabolica':        'Cardiometabólica',
    'arritmias':                'Arritmias',
    'insuficiencia_cardiaca':   'Insuficiência Cardíaca',
    'valvulopatias':            'Valvulopatias',
    'miocardiopatias':          'Miocardiopatias',
    'intervencao_hemodinamica': 'Intervenção/Hemodinâmica',
    'cardio_oncologia':         'Cardio-Oncologia',
    'cardiobstetrica':          'Cardio-Obstétrica',
    'cardio_genomica':          'Cardio-Genômica',
    'uti_cardiologica':         'UTI Cardiológica',
    'aorta_congenitas':         'Aorta/Congênitas',
    'imagem_cardiovascular':    'Imagem Cardiovascular',
    # legado (ainda aceitos via --categoria)
    'prevencao_cv':             'Prevenção CV',
    'hipertensao_pulmonar':     'Hipertensão Pulmonar',
    'cardiogeriatria':          'Cardiogeriatria',
    'cirurgia_cardiaca':        'Cirurgia Cardíaca',
}

JOURNAL_MAP = {
    'Circulation':              'Circulation',
    'J Am Coll Cardiol':        'J Am Coll Cardiol',
    'N Engl J Med':             'N Engl J Med',
    'JAMA':                     'JAMA',
    'Lancet':                   'Lancet',
    'Eur Heart J':              'Eur Heart J',
    'Heart':                    'Heart',
    'JACC Heart Fail':          'JACC Heart Fail',
    'JACC Cardiovasc Imaging':  'JACC Cardiovasc Imaging',
    'JACC Cardiovasc Interv':   'JACC Cardiovasc Interv',
    'Circ Heart Fail':          'Circ Heart Fail',
    'Circ Arrhythm Electrophysiol': 'Circ Arrhythm Electrophysiol',
    'Hypertension':             'Hypertension',
    'Atherosclerosis':          'Atherosclerosis',
    'Stroke':                   'Stroke',
    'J Am Heart Assoc':         'J Am Heart Assoc',
}

# ─── Prompts ──────────────────────────────────────────────────────────────────

PROMPT_TRIAGEM = """
Você é o curador do Radar PubMed CardioDaily.

Analise os resumos abaixo e classifique cada artigo:

CLASSIFICAÇÃO:
🔴 ALTA PRIORIDADE (8-10): RCT grande, resultado que muda prática, revista top-tier
🟠 MÉDIA PRIORIDADE (5-7): Meta-análise, coorte grande, refina conduta
🟡 BAIXA PRIORIDADE (3-4): Retrospectivo, N pequeno, nicho específico
⚪ DESCARTAR (1-2): Pré-clínico, case report, muito específico

PARA CADA ARTIGO:
1. Classificação (emoji + nota)
2. Por que chamou atenção (1-2 frases)
3. Potencial de impacto clínico

NO FINAL:
- Liste os 🔴 que merecem análise completa
- Resuma tendências da semana
- Sugira temas para Radar

LEMBRE: Você trabalha apenas com RESUMOS. Use "pode mudar", "sugere", não afirme certezas.
"""

PROMPT_PODCAST_PUBMED = """
Você é o roteirista do Radar PubMed CardioDaily — podcast de atualização em cardiologia.

FILOSOFIA: duração proporcional à QUALIDADE dos artigos, não a um tempo pré-definido.
- Artigos excelentes = análise profunda
- Artigos ruins = explicação breve de por que ignorar
- Se a semana foi fraca, diga isso honestamente

FORMATO DE SAÍDA:
- APENAS texto para narração em voz alta
- SEM títulos de seção, numeração, indicações de música ou pausa
- Texto corrido, fluido, 100% pronto para TTS

Comece sempre com:
"Olá! Eu sou Eduardo Castro e este é o Radar PubMed do CardioDaily — seu filtro semanal do que realmente importa na literatura. Fatos à mesa, sem firula!"

Organize por QUALIDADE (não por ordem):

ARTIGOS EXCELENTES:
- Problema clínico e contexto
- Metodologia, população, resultados com números (HR, IC95%, NNT, p-valor)
- Impacto prático: para quem usar, dose, quando evitar

ARTIGOS MEDIANOS:
- Resumo compacto, foco no uso prático em situações específicas

ARTIGOS FRACOS:
- Agrupe: "Também vieram artigos sobre X, Y e Z, mas com N pequeno..."

Termine sempre com:
"Eu sou o Dr. Eduardo Castro e este foi o Radar PubMed de hoje. Fatos à mesa para um bom aprendizado. Até a próxima!"

REGRAS: SEMPRE cite números. NUNCA coloque títulos ou marcadores no texto narrado.
"""

PROMPT_NUMERO = """
Você é o roteirista do Radar Semanal CardioDaily — especialista em curadoria de literatura cardiológica.

FILOSOFIA: duração proporcional à QUALIDADE dos artigos, não a um tempo pré-definido.

FORMATO DE SAÍDA:
- APENAS texto para narração em voz alta
- SEM títulos de seção, numeração, indicações de música ou pausa
- Texto corrido, fluido, 100% pronto para TTS

Comece sempre com:
"Olá! Eu sou Eduardo Castro e este é o Radar {REVISTA}, volume {VOLUME}, número {ISSUE} — aqui no CardioDaily, Fatos à mesa, sem firula!"

Organize por QUALIDADE:

ARTIGOS EXCELENTES (RCT grande, resultado que muda prática):
- Problema clínico, pergunta e desenho (tipo, N, população, desfechos)
- Resultados com números: HR, IC95%, NNT, p-valor
- Impacto prático: para quem, como, quando evitar

ARTIGOS MEDIANOS: resumo compacto, foco no útil

ARTIGOS FRACOS: agrupe brevemente

EDITORIAIS RELEVANTES: mencione o ponto central brevemente

Termine sempre com:
"Eu sou o Dr. Eduardo Castro e este foi o Radar {REVISTA} de hoje. Fatos à mesa para um bom aprendizado. Até a próxima!"

REGRAS: SEMPRE cite números. NUNCA coloque marcadores no texto narrado.
"""


# ─── Classe principal ─────────────────────────────────────────────────────────

class RadarPubMed:
    """Radar CardioDaily — busca PubMed + análise Gemini + áudio TTS."""

    def __init__(self):
        self._gemini = None
        self._openai_key = None
        self._ncbi_key = None
        self._email = None
        self._modelo = 'gemini-2.5-pro'
        self._configured = False

    def configure(self, gemini_key: str, email: str, ncbi_key: str = '',
                  openai_key: str = '', modelo: str = 'gemini-2.5-pro'):
        """Configura APIs. Deve ser chamado antes de usar."""
        self._email = email
        self._ncbi_key = ncbi_key
        self._openai_key = openai_key
        self._modelo = modelo

        if not BIO_AVAILABLE:
            raise RuntimeError("biopython não instalado: pip install biopython")

        Entrez.email = email
        Entrez.tool = 'CardioDaily Radar'
        if ncbi_key:
            Entrez.api_key = ncbi_key

        if GENAI_AVAILABLE and gemini_key:
            self._gemini = genai.Client(api_key=gemini_key)
        elif gemini_key:
            raise RuntimeError("google-genai não instalado: pip install google-genai")

        self._configured = True

    # ── PubMed ────────────────────────────────────────────────────────────────

    def buscar_por_categoria(self, categoria: str, dias: int = 7,
                             max_results: int = 50) -> list[dict]:
        """Busca artigos por categoria pré-definida."""
        if categoria == 'todas':
            kws = []
            for v in CATEGORIAS.values():
                kws.extend(v)
        else:
            kws = CATEGORIAS.get(categoria, ['cardiology'])
        return self._buscar_pubmed(kws, dias, max_results)

    def buscar_por_keywords(self, keywords_str: str, dias: int = 7,
                            max_results: int = 50) -> list[dict]:
        """Busca artigos por keywords customizadas (string separada por vírgula)."""
        kws = [k.strip() for k in keywords_str.split(',') if k.strip()]
        return self._buscar_pubmed(kws, dias, max_results)

    def _buscar_pubmed(self, keywords: list, dias: int, max_results: int) -> list[dict]:
        self._check_configured()
        end_date = datetime.now()
        start_date = end_date - timedelta(days=dias)
        date_filter = (
            f'("{start_date.strftime("%Y/%m/%d")}"[Date - Publication] : '
            f'"{end_date.strftime("%Y/%m/%d")}"[Date - Publication])'
        )
        kw_query = ' OR '.join([f'"{k}"' for k in keywords])
        query = f'({kw_query}) AND {date_filter}'

        handle = Entrez.esearch(db='pubmed', term=query,
                                retmax=max_results, sort='pub_date')
        results = Entrez.read(handle)
        handle.close()

        id_list = results.get('IdList', [])
        if not id_list:
            return []

        time.sleep(0.4)
        handle = Entrez.efetch(db='pubmed', id=','.join(id_list),
                               rettype='xml', retmode='xml')
        records = Entrez.read(handle)
        handle.close()

        articles = []
        for record in records.get('PubmedArticle', []):
            try:
                medline = record.get('MedlineCitation', {})
                article_data = medline.get('Article', {})
                pmid = str(medline.get('PMID', ''))
                title = article_data.get('ArticleTitle', 'Sem título')
                abstract_data = article_data.get('Abstract', {})
                abstract_texts = abstract_data.get('AbstractText', [])
                abstract = ' '.join([str(p) for p in abstract_texts]) \
                    if isinstance(abstract_texts, list) else str(abstract_texts)
                journal_info = article_data.get('Journal', {})
                journal = journal_info.get('ISOAbbreviation',
                                           journal_info.get('Title', ''))
                pub_date = journal_info.get('JournalIssue', {}).get('PubDate', {})
                date_str = f"{pub_date.get('Year', '')}/{pub_date.get('Month', '')}"
                pub_types = [str(pt) for pt in
                             article_data.get('PublicationTypeList', [])]
                articles.append({
                    'pmid': pmid, 'title': title, 'abstract': abstract,
                    'journal': journal, 'date': date_str, 'types': pub_types,
                    'url': f'https://pubmed.ncbi.nlm.nih.gov/{pmid}/',
                })
            except Exception:
                continue
        return articles

    # ── Radar Número ──────────────────────────────────────────────────────────

    def get_ultimo_numero(self, journal: str) -> tuple[str | None, str | None]:
        """Detecta volume/issue mais recente de uma revista."""
        self._check_configured()
        time.sleep(0.3)
        handle = Entrez.esearch(db='pubmed', term=f'"{journal}"[Journal]',
                                retmax=30, sort='pub date')
        record = Entrez.read(handle)
        handle.close()
        if not record['IdList']:
            return None, None
        time.sleep(0.4)
        handle = Entrez.efetch(db='pubmed', id=record['IdList'],
                               rettype='xml', retmode='xml')
        root = ET.fromstring(handle.read())
        handle.close()
        counts = Counter()
        for art in root.findall('.//PubmedArticle'):
            try:
                j = art.find('MedlineCitation/Article/Journal')
                v = j.findtext('JournalIssue/Volume') or ''
                i = j.findtext('JournalIssue/Issue') or ''
                y = (j.findtext('JournalIssue/PubDate/Year') or
                     j.findtext('JournalIssue/PubDate/MedlineDate') or '')
                if v and i:
                    counts[(v, i, y)] += 1
            except Exception:
                pass
        if not counts:
            return None, None
        (vol, iss, yr), _ = counts.most_common(1)[0]
        return vol, iss

    def fetch_artigos_numero(self, journal: str, volume: str,
                             issue: str) -> list[dict]:
        """Busca artigos de um número específico."""
        self._check_configured()
        query = f'"{journal}"[Journal] AND {volume}[Volume] AND {issue}[Issue]'
        handle = Entrez.esearch(db='pubmed', term=query, retmax=80)
        record = Entrez.read(handle)
        handle.close()
        pmids = record['IdList']
        if not pmids:
            return []
        time.sleep(0.4)
        handle = Entrez.efetch(db='pubmed', id=pmids,
                               rettype='medline', retmode='text')
        records = list(Medline.parse(StringIO(handle.read())))
        handle.close()

        arts = []
        for rec in records:
            title = rec.get('TI', '')
            if not title:
                continue
            authors = rec.get('AU', [])
            au_str = ', '.join(authors[:3]) + \
                     (' et al.' if len(authors) > 3 else '')
            pt = set(rec.get('PT', []))
            if pt & {'Randomized Controlled Trial', 'Clinical Trial',
                     'Multicenter Study'}:
                atype = 'ORIGINAL (RCT/ECR)'
            elif pt & {'Meta-Analysis', 'Systematic Review'}:
                atype = 'META-ANÁLISE/REVISÃO SISTEMÁTICA'
            elif pt & {'Review'}:
                atype = 'REVISÃO'
            elif pt & {'Editorial'}:
                atype = 'EDITORIAL'
            elif pt & {'Comment', 'Letter'}:
                atype = 'COMENTÁRIO/CARTA'
            else:
                atype = 'ARTIGO ORIGINAL'
            arts.append({
                'pmid': rec.get('PMID', ''),
                'doi': rec.get('LID', '').replace(' [doi]', '').strip(),
                'title': title, 'abstract': rec.get('AB', ''),
                'authors': au_str, 'type': atype,
                'year': rec.get('DP', ''),
                'has_abstract': bool(rec.get('AB', '')),
            })
        return arts

    # ── Gemini ────────────────────────────────────────────────────────────────

    def analisar_triagem(self, artigos: list[dict], contexto: str) -> str:
        """Triagem de artigos com Gemini."""
        resumos = ''
        for i, art in enumerate(artigos, 1):
            resumos += (
                f"\n### ARTIGO {i}\n"
                f"- PMID: {art['pmid']}\n"
                f"- Título: {art['title']}\n"
                f"- Revista: {art['journal']}\n"
                f"- Data: {art['date']}\n"
                f"- Tipos: {', '.join(art['types'][:3])}\n\n"
                f"**Resumo:** {art['abstract'][:800]}\n\n---\n"
            )
        prompt = (
            f"{PROMPT_TRIAGEM}\n\n"
            f"## ARTIGOS ({len(artigos)}):\n{resumos}\n\n"
            f"CONTEXTO: {contexto}"
        )
        return self._chamar_gemini(prompt)

    def gerar_script_pubmed(self, artigos: list[dict], triagem: str,
                            contexto: str) -> str:
        """Gera script de podcast a partir de artigos + triagem."""
        resumos = ''
        for i, art in enumerate(artigos, 1):
            resumos += (
                f"\n### ARTIGO {i}\n"
                f"- PMID: {art['pmid']}\n"
                f"- Título: {art['title']}\n"
                f"- Revista: {art['journal']}\n"
                f"- Data: {art['date']}\n"
                f"- Tipos: {', '.join(art['types'][:3])}\n\n"
                f"**Resumo:** {art['abstract']}\n\n---\n"
            )
        prompt = (
            f"{PROMPT_PODCAST_PUBMED}\n\n"
            f"## TRIAGEM PRÉVIA:\n{triagem}\n\n"
            f"## ARTIGOS COMPLETOS ({len(artigos)}):\n{resumos}\n\n"
            f"CONTEXTO: {contexto}"
        )
        return self._chamar_gemini(prompt)

    def gerar_script_numero(self, journal: str, volume: str, issue: str,
                            artigos: list[dict]) -> str:
        """Gera script do Radar Número de uma revista."""
        main_arts = [a for a in artigos
                     if a['has_abstract'] and
                     'COMENTÁRIO' not in a['type'] and
                     'CARTA' not in a['type']]
        editorials = [a for a in artigos if 'EDITORIAL' in a['type']]
        if not main_arts:
            main_arts = [a for a in artigos if a['has_abstract']]

        ctx = [
            f'# {journal} — Volume {volume}, Número {issue}',
            f'# Total: {len(artigos)} artigos | Com abstract: {len(main_arts)}\n',
        ]
        for i, a in enumerate(main_arts, 1):
            ctx.append(
                f'---\n## Artigo {i} [{a["type"]}]\n'
                f'**Título:** {a["title"]}\n'
                f'**Autores:** {a["authors"]}\n'
                f'**Ano:** {a["year"]}\n'
                f'**DOI:** {a["doi"]}\n'
                f'**Abstract:**\n{a["abstract"]}\n'
            )
        if editorials:
            ctx.append('\n---\n## EDITORIAIS\n')
            for ed in editorials[:5]:
                ctx.append(f'- **{ed["title"]}** — {ed["authors"]}\n')
        contexto_str = '\n'.join(ctx)

        prompt_tpl = PROMPT_NUMERO \
            .replace('{REVISTA}', journal) \
            .replace('{VOLUME}', volume) \
            .replace('{ISSUE}', issue)
        prompt = (
            f'{prompt_tpl}\n\n---\n\n'
            f'## ARTIGOS:\n\n{contexto_str}\n\n---\n'
            f'Gere o roteiro completo agora:'
        )
        return self._chamar_gemini(prompt)

    def _chamar_gemini(self, prompt: str) -> str:
        self._check_configured()
        if not self._gemini:
            raise RuntimeError("Gemini não configurado — verifique GEMINI_API_KEY")

        # Modelos em ordem de preferência: Pro → Flash (fallback)
        modelos = [self._modelo]
        if '2.5-pro' in self._modelo or 'pro' in self._modelo.lower():
            modelos.append('gemini-2.0-flash')

        max_tentativas = 4
        espera_base = 15  # segundos

        for modelo in modelos:
            for tentativa in range(1, max_tentativas + 1):
                try:
                    if modelo != self._modelo or tentativa > 1:
                        print(f"   🔄 Tentativa {tentativa}/{max_tentativas} [{modelo}]…")
                    response = self._gemini.models.generate_content(
                        model=modelo,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            temperature=0.7,
                            max_output_tokens=32768,
                        ),
                    )
                    if modelo != self._modelo:
                        print(f"   ✅ Respondido por fallback: {modelo}")
                    return response.text

                except Exception as e:
                    msg = str(e)
                    is_503 = '503' in msg or 'UNAVAILABLE' in msg or 'high demand' in msg.lower()
                    is_429 = '429' in msg or 'quota' in msg.lower() or 'RESOURCE_EXHAUSTED' in msg

                    if (is_503 or is_429) and tentativa < max_tentativas:
                        espera = espera_base * tentativa  # 15s, 30s, 45s
                        print(f"   ⏳ Gemini indisponível ({modelo}) — aguardando {espera}s antes de tentar novamente…")
                        time.sleep(espera)
                        continue
                    elif tentativa == max_tentativas:
                        print(f"   ⚠️  {modelo} falhou após {max_tentativas} tentativas: {msg[:120]}")
                        break  # tenta próximo modelo
                    else:
                        raise  # erro não recuperável — propaga imediatamente

        raise RuntimeError("Todos os modelos Gemini falharam. Tente novamente mais tarde.")

    # ── Áudio ─────────────────────────────────────────────────────────────────

    def gerar_audio(self, script: str, output_path: str,
                    voice: str = 'onyx', model: str = 'tts-1-hd',
                    speed: float = 1.1) -> bool:
        """Gera MP3 via OpenAI TTS (sem pydub/ffmpeg)."""
        if not self._openai_key:
            raise RuntimeError("OPENAI_API_KEY não configurado")
        texto = limpar_para_audio(script).strip()
        if not texto:
            return False

        max_chars = 4096
        if len(texto) <= max_chars:
            return self._tts_single(texto, output_path, voice, model, speed)
        return self._tts_chunked(texto, output_path, voice, model, speed, max_chars)

    def _tts_single(self, texto, output_path, voice, model, speed) -> bool:
        resp = requests.post(
            'https://api.openai.com/v1/audio/speech',
            headers={'Authorization': f'Bearer {self._openai_key}',
                     'Content-Type': 'application/json'},
            json={'model': model, 'input': texto, 'voice': voice,
                  'response_format': 'mp3', 'speed': speed},
            timeout=300,
        )
        if resp.status_code != 200:
            raise RuntimeError(f"TTS HTTP {resp.status_code}: {resp.text[:200]}")
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_bytes(resp.content)
        return True

    def _tts_chunked(self, texto, output_path, voice, model, speed, max_chars) -> bool:
        paragraphs = texto.split('\n\n')
        chunks, current = [], ''
        for p in paragraphs:
            p = p.strip()
            if not p:
                continue
            if len(current) + len(p) + 2 <= max_chars:
                current = (current + '\n\n' + p).strip()
            else:
                if current:
                    chunks.append(current)
                if len(p) > max_chars:
                    sentences = re.split(r'(?<=[.!?])\s+', p)
                    sub = ''
                    for s in sentences:
                        if len(sub) + len(s) + 1 <= max_chars:
                            sub = (sub + ' ' + s).strip()
                        else:
                            if sub:
                                chunks.append(sub)
                            sub = s
                    if sub:
                        chunks.append(sub)
                else:
                    current = p
        if current:
            chunks.append(current)

        all_bytes = []
        for i, chunk in enumerate(chunks):
            resp = requests.post(
                'https://api.openai.com/v1/audio/speech',
                headers={'Authorization': f'Bearer {self._openai_key}',
                         'Content-Type': 'application/json'},
                json={'model': model, 'input': chunk, 'voice': voice,
                      'response_format': 'mp3', 'speed': speed},
                timeout=300,
            )
            if resp.status_code != 200:
                raise RuntimeError(
                    f"TTS chunk {i+1} HTTP {resp.status_code}: {resp.text[:200]}")
            all_bytes.append(resp.content)
            time.sleep(0.5)

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'wb') as f:
            for b in all_bytes:
                f.write(b)
        return True

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _check_configured(self):
        if not self._configured:
            raise RuntimeError("Radar não configurado — chame .configure() primeiro")


# ─── Utilitários ──────────────────────────────────────────────────────────────

def limpar_para_audio(texto: str) -> str:
    """Remove formatação markdown para texto limpo de TTS."""
    texto = re.sub(r'^\s*(?:Claro!?|Aqui está|Segue)[^\n]*roteiro[^\n]*\n',
                   '', texto, flags=re.IGNORECASE)
    texto = re.sub(r'^#{1,6}\s+.*$', '', texto, flags=re.MULTILINE)
    texto = re.sub(r'\*\*([^*]+)\*\*', r'\1', texto)
    texto = re.sub(r'\*([^*]+)\*', r'\1', texto)
    texto = re.sub(r'__([^_]+)__', r'\1', texto)
    texto = re.sub(r'_([^_]+)_', r'\1', texto)
    texto = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', texto)
    texto = re.sub(r'^[-=]{3,}$', '', texto, flags=re.MULTILINE)
    texto = re.sub(
        r'\([^)]*(?:música|pausa|som|efeito|início|fim|encerra|sobe|desce|'
        r'fade|tema|dramática|dramático|fundo|volume)[^)]*\)',
        '', texto, flags=re.IGNORECASE)
    texto = re.sub(
        r'^\s*\d+\.\s+[A-ZÁÉÍÓÚÂÊÔÃÕÇ][A-ZÁÉÍÓÚÂÊÔÃÕÇ\s\?]+$',
        '', texto, flags=re.MULTILINE)
    texto = re.sub(
        r'^\s*[A-ZÁÉÍÓÚÂÊÔÃÕÇ][A-ZÁÉÍÓÚÂÊÔÃÕÇ\s]{2,}:?\s*$',
        '', texto, flags=re.MULTILINE)
    texto = re.sub(r'^\s*\*?\s*VEREDITO:\s*', '', texto,
                   flags=re.MULTILINE | re.IGNORECASE)
    texto = re.sub(r'^\s*[\-\*•]\s+', '', texto, flags=re.MULTILINE)
    texto = re.sub(
        r'\[[^\]]*(?:PAUSA|MÚSICA|MUSICA|SOM|EFEITO|VINHETA|\d{1,2}:\d{2})[^\]]*\]',
        '', texto, flags=re.IGNORECASE)
    texto = re.sub(r'[\U0001F300-\U0001F9FF\u2600-\u26FF\u2700-\u27BF]', '', texto)
    texto = re.sub(r'[\(\[]\d{1,2}:\d{2}[\)\]]', '', texto)
    texto = re.sub(r'^\s*[\-\=\*\_\#\>]+\s*$', '', texto, flags=re.MULTILINE)
    texto = re.sub(r'\n{3,}', '\n\n', texto)
    texto = re.sub(r'[ \t]+', ' ', texto)
    texto = re.sub(r' +\n', '\n', texto)
    return texto.strip()
