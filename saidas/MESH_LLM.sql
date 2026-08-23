-- MESH_LLM.sql · gerado por scripts/mesh_backfill.py
-- Descritores propostos pelo modelo e RESOLVIDOS contra o vocabulário
-- oficial da NLM. A varredura semanal os SUBSTITUI pelo MeSH humano
-- assim que a NLM indexar — é para isso que serve `mesh_origem`.

ALTER TABLE artigos ADD COLUMN IF NOT EXISTS mesh_origem text;

UPDATE artigos SET mesh_origem='pubmed'
 WHERE mesh_origem IS NULL AND cardinality(mesh_terms) > 0;

UPDATE artigos SET mesh_terms=ARRAY['Cardiovascular Diseases','Risk Factors','Women','Female','Male','Humans','Latin America','Caribbean Region','Cross-Sectional Studies','Retrospective Studies']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.36660/abc.20250655i';
UPDATE artigos SET mesh_terms=ARRAY['Diabetes Mellitus, Type 2','Tirzepatide','Hypoglycemic Agents','Weight Loss','Cost-Benefit Analysis','Humans','Aged']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1016/j.vhri.2026.101666';
UPDATE artigos SET mesh_terms=ARRAY['Heart Valve Prosthesis Implantation','Aortic Valve','Heart Valve Prosthesis','Transcatheter Aortic Valve Replacement','Biocompatible Materials','Sheep']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1093/ehjvshd/xwag039';
UPDATE artigos SET mesh_terms=ARRAY['Mitral Valve Insufficiency','Heart Failure','Echocardiography','Cohort Studies','Retrospective Studies','Humans','Aged','Female','Male']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1016/j.jacadv.2026.103057';
UPDATE artigos SET mesh_terms=ARRAY['Aortic Valve Stenosis','Bicuspid Aortic Valve Disease','Survival Rate','Cohort Studies','Registries','Humans','Aged','Female','Male']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1093/ehjvshd/xwag052';

-- conferência: rode e confira que `vazios` deu ZERO
SELECT count(*) FILTER (WHERE mesh_terms IS NULL OR cardinality(mesh_terms)=0) AS vazios,
       count(*) FILTER (WHERE mesh_origem='pubmed')   AS do_pubmed,
       count(*) FILTER (WHERE mesh_origem='mesh_llm') AS do_modelo,
       count(*) AS total
  FROM artigos;
UPDATE artigos SET mesh_terms=ARRAY['Aortic Valve Stenosis','Heart Valve Prosthesis Implantation','Monocytes','Immunity, Innate','Fibrosis','Calcinosis','Humans','Aged','Female','Male','Cross-Sectional Studies']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1093/ehjvshd/xwag055';
UPDATE artigos SET mesh_terms=ARRAY['Aortic Aneurysm','Aortic Aneurysm, Abdominal','Aorta','anatomy  and  histology','Immunohistochemistry','Matrix Metalloproteinase 2','Matrix Metalloproteinase 9','Sex Factors','Female','Male','Humans','Cross-Sectional Studies']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1093/ehjopen/oeag084';

-- conferência: rode e confira que `vazios` deu ZERO
SELECT count(*) FILTER (WHERE mesh_terms IS NULL OR cardinality(mesh_terms)=0) AS vazios,
       count(*) FILTER (WHERE mesh_origem='pubmed')   AS do_pubmed,
       count(*) FILTER (WHERE mesh_origem='mesh_llm') AS do_modelo,
       count(*) AS total
  FROM artigos;
UPDATE artigos SET mesh_terms=ARRAY['Obesity','Anti-Obesity Agents','Diabetes Mellitus, Type 2','Cardiovascular Diseases','Practice Guidelines as Topic','Humans']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.2337/doci25-0008';
UPDATE artigos SET mesh_terms=ARRAY['ST Elevation Myocardial Infarction','Myocardial Infarction','Ferritins','Biomarkers','Humans','Male','Cohort Studies']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1093/ehjopen/oeag092';
UPDATE artigos SET mesh_terms=ARRAY['Diabetes Mellitus, Type 2','Neoplasms','Anthracyclines','Glucagon-Like Peptide-1 Receptor Agonists','Cardiotoxicity','mortality','Cohort Studies','Humans','Adult','Female','Male']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1093/ehjopen/oeag109';
UPDATE artigos SET mesh_terms=ARRAY['Cardiovascular Diseases','Cerebrovascular Disorders','Semaglutide','Tirzepatide','Obesity','Diabetes Mellitus, Type 2','Humans','Cohort Studies']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1016/j.jacadv.2026.102917';
UPDATE artigos SET mesh_terms=ARRAY['Heart Failure','Diuretics','Emergency Medicine','Hospitalization','Acute Kidney Injury','Aged','Humans','Cohort Studies']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1016/j.jchf.2026.103235';
UPDATE artigos SET mesh_terms=ARRAY['Heart Transplantation','Coronary Angiography','Coronary Disease','Atherosclerosis','Humans','Registries','Cohort Studies']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1093/eurheartj/ehag488';
UPDATE artigos SET mesh_terms=ARRAY['Heart Failure','Hospitalization','Pulmonary Artery','Cardiac Catheterization','Monitoring, Physiologic','Risk Factors','Humans','Cohort Studies']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1016/j.jchf.2026.103239';
UPDATE artigos SET mesh_terms=ARRAY['Cardiotoxicity','Anthracyclines','Heart Failure','Echocardiography','Risk Assessment','Predictive Value of Tests','Humans','Cohort Studies']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1016/j.jaccao.2026.06.005';
UPDATE artigos SET mesh_terms=ARRAY['Cardiovascular Diseases','Kidney Diseases','Metabolic Syndrome','Neoplasms','Biomarkers','Proteomics','Metabolomics','Cohort Studies','Humans']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1016/j.jaccao.2026.05.012';
UPDATE artigos SET mesh_terms=ARRAY['Prostatic Neoplasms','Leuprolide','Platelet Activation','Blood Platelets','Humans','Male','Cohort Studies']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1016/j.jaccao.2026.07.007';
UPDATE artigos SET mesh_terms=ARRAY['Atrial Fibrillation','Anticoagulants','Hemoglobins','Anemia','Neoplasms','Humans','Aged','Cohort Studies']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1016/j.jaccao.2026.07.005';
UPDATE artigos SET mesh_terms=ARRAY['Coronary Artery Disease','Angina Pectoris','Patient Reported Outcome Measures','Quality of Life','Prognosis','Cohort Studies','Humans','Aged','Female','Male']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1161/CIRCOUTCOMES.125.013063';
UPDATE artigos SET mesh_terms=ARRAY['Dyslipidemias','Atherosclerosis','Cholesterol, LDL','Hypolipidemic Agents','Practice Guidelines as Topic','Humans']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.36660/abc.20250640i';
UPDATE artigos SET mesh_terms=ARRAY['Coronary Artery Disease','Echocardiography, Stress','Heart Valve Diseases','Heart Failure','Cardiomyopathies','Myocardial Infarction','Contrast Media','Heart Transplantation','Humans','Child','Practice Guidelines as Topic']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.36660/abc.20260223i';
UPDATE artigos SET mesh_terms=ARRAY['Tachycardia, Ventricular','Ventricular Fibrillation','Defibrillators, Implantable','Anti-Arrhythmia Agents','Catheter Ablation','Intensive Care Units','Practice Guidelines as Topic']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.36660/abc.20260215i';
UPDATE artigos SET mesh_terms=ARRAY['Diagnostic Imaging','Echocardiography','Magnetic Resonance Imaging','Positron Emission Tomography Computed Tomography','Radionuclide Imaging','Practice Guidelines as Topic','Humans']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.36660/abc.20260221i';
UPDATE artigos SET mesh_terms=ARRAY['Heart Failure','Cardiomyopathy, Dilated','Defibrillators, Implantable','Cardiac Resynchronization Therapy Devices','Death, Sudden, Cardiac','mortality','Humans','Randomized Controlled Trials as Topic','Meta-Analysis as Topic']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.36660/abc.20250675';
UPDATE artigos SET mesh_terms=ARRAY['Dengue','Thrombocytopenia','Platelet Aggregation Inhibitors','Anticoagulants','Heparin','Atrial Fibrillation','Practice Guidelines as Topic','Humans']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.36660/abc.20260216i';
UPDATE artigos SET mesh_terms=ARRAY['Ultrasonography','Echocardiography','Point-of-Care Systems','Cardiovascular Diseases','Critical Care','Emergency Medicine','Humans','Practice Guidelines as Topic']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.36660/abc.20260222i';
UPDATE artigos SET mesh_terms=ARRAY['Atrial Fibrillation','Anticoagulants','Catheter Ablation','Arrhythmias, Cardiac','Humans','Aged','Practice Guidelines as Topic','Meta-Analysis as Topic']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1055/a-2787-0186';
UPDATE artigos SET mesh_terms=ARRAY['Aortic Valve Stenosis','Registries','Cohort Studies','Humans','Aged','Female','Male']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1161/CIRCULATIONAHA.126.081405';
UPDATE artigos SET mesh_terms=ARRAY['Atrial Remodeling','Body Mass Index','Obesity','Overweight','Echocardiography','Humans','Female','Male','Cohort Studies']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1136/heartjnl-2025-327623';
UPDATE artigos SET mesh_terms=ARRAY['Cardiovascular Diseases','Echocardiography','Ultrasonography, Interventional','Risk Assessment','Hypertension','Diabetes Mellitus','Coronary Disease','Humans']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1016/j.tcm.2026.07.002';
UPDATE artigos SET mesh_terms=ARRAY['Aortic Valve Stenosis','Echocardiography','Ventricular Remodeling','Atrial Remodeling','Cohort Studies','Humans','Aged','Female','Male']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1093/ehjvshd/xwag044';
UPDATE artigos SET mesh_terms=ARRAY['Breast Neoplasms','Antibodies, Monoclonal','Immunoconjugates','Ado-Trastuzumab Emtansine','Cardiotoxicity','Drug-Related Side Effects and Adverse Reactions','Humans']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1016/j.jaccao.2026.07.006';
UPDATE artigos SET mesh_terms=ARRAY['Stroke','Carotid Stenosis','radiotherapy','Head and Neck Neoplasms','Radiation Injuries','Risk Factors','Humans','Practice Guidelines as Topic']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1016/j.jaccao.2026.06.003';
UPDATE artigos SET mesh_terms=ARRAY['Heart Failure','Enalapril','Losartan','Cohort Studies','Humans','Aged','Male','Female']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.36660/abc.20260069iand';
UPDATE artigos SET mesh_terms=ARRAY['Hypertension','Acupuncture Therapy','Endothelium, Vascular','Adult','Humans','Randomized Controlled Trials as Topic']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.36660/abc.20260462i';
UPDATE artigos SET mesh_terms=ARRAY['Cardiomyopathy, Hypertrophic','Tachycardia, Ventricular','Thromboembolism','Cohort Studies','Humans','Aged','Male','Female']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1016/j.jacadv.2026.102919';
UPDATE artigos SET mesh_terms=ARRAY['Atrial Fibrillation','Heart Atria','Atrial Appendage','Prosthesis Implantation','Catheter Ablation','Humans','Aged','Cohort Studies']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1016/j.jacadv.2026.102870';
UPDATE artigos SET mesh_terms=ARRAY['Cholesterol, LDL','Lipoproteins, LDL','Machine Learning','Algorithms','Sensitivity and Specificity','Reproducibility of Results','Cross-Sectional Studies','Retrospective Studies','Humans']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1001/jamacardio.2026.2314';
UPDATE artigos SET mesh_terms=ARRAY['Acute Kidney Injury','Cardiac Surgical Procedures','Sodium-Glucose Transporter 2 Inhibitors','Humans','Aged','Female','Male','Randomized Controlled Trials as Topic']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1001/jama.2026.9268';
UPDATE artigos SET mesh_terms=ARRAY['Atherosclerosis','Cholesterol, LDL','Quality Improvement','Decision Support Systems, Clinical','Telemedicine','Humans','Adult','Randomized Controlled Trials as Topic']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1001/jamacardio.2026.2510';
UPDATE artigos SET mesh_terms=ARRAY['Coronary Disease','Risk Factors','mortality','Cost of Illness','United States','Humans','Registries','Models, Statistical']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1001/jamacardio.2026.2435';
UPDATE artigos SET mesh_terms=ARRAY['Mitral Valve Insufficiency','Echocardiography','Mitral Valve Annuloplasty','Cohort Studies','Survival Rate','mortality','Aged','Humans']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1001/jamacardio.2026.2389';
UPDATE artigos SET mesh_terms=ARRAY['Cardiovascular Diseases','Angiotensin-Converting Enzyme Inhibitors','Angiotensin Receptor Antagonists','Risk Factors','Humans','Randomized Controlled Trials as Topic','Meta-Analysis as Topic']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1093/ehjopen/oeag119';
UPDATE artigos SET mesh_terms=ARRAY['Heart Failure','Echocardiography','Echocardiography, Doppler','Heart Diseases','Humans','Practice Guidelines as Topic']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1093/ehjci/jeag006';
UPDATE artigos SET mesh_terms=ARRAY['Coronary Disease','Risk Factors','Hypertension','Hypercholesterolemia','Electrocardiography','Cohort Studies','Humans','Female','Male']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='fatores-de-risco-no-desenvolvimento-de-doenca-arterial-coronariana-experiencia-d';
UPDATE artigos SET mesh_terms=ARRAY['Heart Failure','Ubiquinone','Dietary Supplements','Randomized Controlled Trials as Topic','Treatment Outcome','Hospitalization','mortality','Humans','Female','Male']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='the-effect-of-coenzyme-q10-on-morbidity-and-mortality-in-chronic-heart-failure-r';
UPDATE artigos SET mesh_terms=ARRAY['Cardiovascular Diseases','Women''s Health','Life Cycle Stages','Practice Guidelines as Topic','Humans','Female','Obesity','Diabetes Mellitus, Type 2','Hypertension','Metabolic Syndrome','Polycystic Ovary Syndrome','Menopause']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.36660/abc.2020615i';
UPDATE artigos SET mesh_terms=ARRAY['Amyloidosis','Cardiomyopathies','Heart Failure','Prealbumin','Aged','Humans','Cohort Studies']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1016/j.jacadv.2026.103019';
UPDATE artigos SET mesh_terms=ARRAY['Myocardial Infarction','Platelet Activation','Receptors, Fc','Biomarkers','Risk Factors','Recurrence','Hemorrhage','Humans','Cohort Studies']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1016/j.jacadv.2026.102981';
UPDATE artigos SET mesh_terms=ARRAY['Atrial Fibrillation','Anticoagulants','Catheter Ablation','Atrial Appendage','Practice Guidelines as Topic','Humans','Adult','Aged']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.36660/abc.20250618i';
UPDATE artigos SET mesh_terms=ARRAY['Heart Failure','Cardiomyopathies','Heart Failure, Systolic','Heart Defects, Congenital','Adult','Humans','Registries','Cohort Studies']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1016/j.jacadv.2026.103042';
UPDATE artigos SET mesh_terms=ARRAY['Heart Failure','Hodgkin Disease','mortality','Neoplasms, Second Primary','Aged','Humans','Registries','Cohort Studies']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1016/j.jacadv.2026.103058';
UPDATE artigos SET mesh_terms=ARRAY['Acute Coronary Syndrome','Shock, Cardiogenic','Percutaneous Coronary Intervention','Registries','Humans','Aged','Female','Male']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1016/j.jacadv.2026.103041';
UPDATE artigos SET mesh_terms=ARRAY['Cholesterol, LDL','Hydroxymethylglutaryl-CoA Reductase Inhibitors','Veterans','Humans','Aged','Male','Female','Cohort Studies']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1016/j.jacadv.2026.103004';
UPDATE artigos SET mesh_terms=ARRAY['Heart Defects, Congenital','Adult','Perioperative Care','Risk Assessment','Postoperative Complications','mortality','Prognosis','Registries','Humans']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1016/j.jacadv.2026.102975';
UPDATE artigos SET mesh_terms=ARRAY['Chest Pain','Acute Coronary Syndrome','Aortic Dissection','Pulmonary Embolism','Emergency Service, Hospital','Diagnostic Techniques, Cardiovascular','Practice Guidelines as Topic','Humans','Adult']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.36660/abc.20250620i';
UPDATE artigos SET mesh_terms=ARRAY['Cardiomyopathies','Amyloidosis','Heart Failure','Treatment Outcome','Quality of Life','Aged','Humans','Randomized Controlled Trials as Topic']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1001/jamacardio.2026.2413';
UPDATE artigos SET mesh_terms=ARRAY['Obesity','Cardiovascular Diseases','Heart Failure','Sleep Apnea, Obstructive','Diabetes Mellitus, Type 2','Glucagon-Like Peptide-1 Receptor Agonists','Semaglutide','Tirzepatide','Humans','Practice Guidelines as Topic']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.36660/abc.20250621i';
UPDATE artigos SET mesh_terms=ARRAY['Heart Failure','Echocardiography','Ventricular Remodeling','mortality','Registries','Cohort Studies','Humans','Aged','Female','Male']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1001/jamacardio.2026.2779';
UPDATE artigos SET mesh_terms=ARRAY['Hypertension','Practice Guidelines as Topic','Primary Health Care','Risk Assessment','Blood Pressure Determination','Humans','Aged','Male','Female','Guideline Adherence']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.36660/abc.20250624i';
UPDATE artigos SET mesh_terms=ARRAY['Heart Arrest','Sports','Emergency Medical Services','Cardiopulmonary Resuscitation','Defibrillators','Practice Guidelines as Topic','Humans']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.36660/abc.20260220i';
UPDATE artigos SET mesh_terms=ARRAY['Alzheimer Disease','Cerebral Amyloid Angiopathy','Amyloid beta-Peptides','Blood Component Transfusion','Humans','Cohort Studies','Review Literature as Topic']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='risk-of-transmission-of-amyloid-pathology-via-transfused-blood-products';
UPDATE artigos SET mesh_terms=ARRAY['Venous Thromboembolism','Anticoagulants','Neoplasms','Humans','Practice Guidelines as Topic','Cohort Studies']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1016/j.chest.2026.05.035';
UPDATE artigos SET mesh_terms=ARRAY['Arrhythmias, Cardiac','Atrial Fibrillation','Tachycardia, Supraventricular','Electrophysiologic Techniques, Cardiac','Catheter Ablation','Defibrillators, Implantable','Athletes','Humans']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1016/j.jacep.2026.06.028';
UPDATE artigos SET mesh_terms=ARRAY['Physical Fitness','Motor Activity','Accelerometry','Exercise Test','Obesity','Overweight','Adult','Female','Male','Humans','Cross-Sectional Studies']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1136/lma-2025-000005';
UPDATE artigos SET mesh_terms=ARRAY['Heart Failure','Adrenergic beta-Antagonists','Metoprolol','mortality','Humans','Aged','Female','Male','Randomized Controlled Trials as Topic']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='effect-of-metoprolol-cr-xl-in-chronic-heart-failure-metoprolol-cr-xl-randomised';
UPDATE artigos SET mesh_terms=ARRAY['Dyslipidemias','Cholesterol, LDL','Atherosclerosis','Cardiovascular Diseases','Practice Guidelines as Topic','Humans','Aged','HIV Infections']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1093/eurheartj/ehaf190';
UPDATE artigos SET mesh_terms=ARRAY['Atrial Fibrillation','Atrial Appendage','Anticoagulants','Embolic Protection Devices','Humans','Aged','Female','Male','Randomized Controlled Trials as Topic','Meta-Analysis as Topic']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1016/j.jacadv.2026.102933';
UPDATE artigos SET mesh_terms=ARRAY['Heart Failure','Shock, Cardiogenic','Pediatrics','Critical Care','Extracorporeal Membrane Oxygenation','Heart-Assist Devices','Practice Guidelines as Topic','Humans']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1161/CIR.0000000000001461';
UPDATE artigos SET mesh_terms=ARRAY['Cardiovascular Diseases','Vaccination','Influenza Vaccines','COVID-19 Vaccines','Respiratory Syncytial Virus Vaccines','Pneumococcal Vaccines','Herpes Zoster Vaccine','Practice Guidelines as Topic','Aged','Humans']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1016/j.jacc.2026.07.004';
UPDATE artigos SET mesh_terms=ARRAY['Amyloidosis','Bortezomib','Cyclophosphamide','Dexamethasone','Humans','Practice Guidelines as Topic']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1016/j.htct.2026.106482';
UPDATE artigos SET mesh_terms=ARRAY['Artificial Intelligence','Machine Learning','Generative Artificial Intelligence','Cardiology','Health Equity','Health Inequities','Humans','Practice Guidelines as Topic']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1016/j.jacadv.2026.102967';
UPDATE artigos SET mesh_terms=ARRAY['Tachycardia, Supraventricular','Tachycardia, Paroxysmal','Catheter Ablation','Adenosine','Humans','Adult','Practice Guidelines as Topic','Treatment Outcome']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1016/j.jacadv.2026.103016';
UPDATE artigos SET mesh_terms=ARRAY['Heart Failure','Adrenergic beta-Antagonists','Hospitalization','Humans','Cohort Studies','Randomized Controlled Trials as Topic','Meta-Analysis as Topic']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1016/j.jacadv.2026.102929';
UPDATE artigos SET mesh_terms=ARRAY['Atherosclerosis','Platelet Aggregation Inhibitors','Aspirin','Practice Guidelines as Topic','Humans','Aged']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1016/j.jacc.2026.05.037';
UPDATE artigos SET mesh_terms=ARRAY['Cardiomyopathies','Pregnancy','Pregnancy Complications, Cardiovascular','Arrhythmias, Cardiac','Heart Failure','Practice Guidelines as Topic','Cohort Studies','Humans']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1016/j.jacc.2026.06.004';
UPDATE artigos SET mesh_terms=ARRAY['Cardiovascular Diseases','Caffeine','Coffee','Energy Drinks','Atrial Fibrillation','Hypertension','Humans','Practice Guidelines as Topic']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1161/CIR.0000000000001454';
UPDATE artigos SET mesh_terms=ARRAY['Cardiomyopathy, Hypertrophic','Humans','Adult','Randomized Controlled Trials as Topic','Meta-Analysis as Topic']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1136/heartjnl-2025-327651';
UPDATE artigos SET mesh_terms=ARRAY['Coronary Artery Disease','Primary Prevention','Risk Assessment','Mass Screening','Military Personnel','Firefighters','Police','Athletes','Occupational Health','Humans','Review Literature as Topic']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1016/j.ajpc.2026.101675';
UPDATE artigos SET mesh_terms=ARRAY['Myocardial Infarction','Ventricular Dysfunction, Left','Angiotensin-Converting Enzyme Inhibitors','Heart Failure','Death, Sudden, Cardiac','Aged','Humans','Randomized Controlled Trials as Topic']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='a-clinical-trial-of-the-angiotensin-convertingenzyme-inhibitor-trandolapril-in-p';
UPDATE artigos SET mesh_terms=ARRAY['Delirium','Cardiovascular Diseases','Cardiac Surgical Procedures','Transcatheter Aortic Valve Replacement','Percutaneous Coronary Intervention','Intensive Care Units','Aged','Humans','Review Literature as Topic']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1093/eurheartj/ehag088';
UPDATE artigos SET mesh_terms=ARRAY['Substance-Related Disorders','Alcoholism','Cardiometabolic Risk Factors','Glucagon-Like Peptide-1 Receptor Agonists','Obesity','Cardiovascular Diseases','Humans']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1093/ehjopen/oeag101';
UPDATE artigos SET mesh_terms=ARRAY['Heart Failure','Ultrasonography','Biomarkers','Natriuresis','Diuretics','Humans','Aged']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.15420/cfr.2025.52';
UPDATE artigos SET mesh_terms=ARRAY['Hypertension, Pulmonary','Pulmonary Arterial Hypertension','Pulmonary Heart Disease','Vascular Remodeling','Ventricular Dysfunction, Right','Vasodilator Agents','Humans']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1136/bmjmed-2022-000137';
UPDATE artigos SET mesh_terms=ARRAY['Diabetes Mellitus, Type 2','Diabetes Mellitus, Type 1','Kidney Diseases','Sodium-Glucose Transporter 2 Inhibitors','Glucagon-Like Peptide-1 Receptor Agonists','Mineralocorticoid Receptor Antagonists','Practice Guidelines as Topic','Humans']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1177/19322968241292041.118';
UPDATE artigos SET mesh_terms=ARRAY['Cardiovascular Diseases','Hormone Replacement Therapy','Estrogens','Postmenopause','Female','Humans','Meta-Analysis as Topic','Randomized Controlled Trials as Topic','Practice Guidelines as Topic']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1093/ehjopen/oeag054';
UPDATE artigos SET mesh_terms=ARRAY['Aortic Valve Stenosis','Transcatheter Aortic Valve Replacement','Humans','Aged','Female','Male','Randomized Controlled Trials as Topic','Meta-Analysis as Topic']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1016/j.jacadv.2026.102856';
UPDATE artigos SET mesh_terms=ARRAY['Heart Failure','Heart Failure, Diastolic','Spironolactone','Sodium-Glucose Transporter 2 Inhibitors','Mineralocorticoid Receptor Antagonists','Blood Pressure','Renin','Aged','Humans','Randomized Controlled Trials as Topic']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1016/j.jchf.2026.103111';
UPDATE artigos SET mesh_terms=ARRAY['Lipoprotein(a)','Cardiovascular Diseases','Risk Factors','Women''s Health','Pregnancy','Menopause','Female','Humans','Review Literature as Topic']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1016/j.jacadv.2026.102744';
UPDATE artigos SET mesh_terms=ARRAY['Myocardial Bridging','Myocardial Ischemia','Angina Pectoris','Coronary Vasospasm','Tomography, X-Ray Computed','Coronary Angiography','Fractional Flow Reserve, Myocardial','Humans','Review Literature as Topic']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1093/eurheartj/ehaf1038';
UPDATE artigos SET mesh_terms=ARRAY['Radiation Injuries','radiotherapy','Dose-Response Relationship, Radiation','Heart Diseases','Coronary Disease','Heart Failure','Atrial Fibrillation','Humans','Female','Review Literature as Topic']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1016/j.jaccao.2026.04.009';
UPDATE artigos SET mesh_terms=ARRAY['Pericarditis','Myocarditis','Electrocardiography','Artificial Intelligence','Machine Learning','Humans','Male','Female','Cohort Studies']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1016/j.jacadv.2026.103046';
UPDATE artigos SET mesh_terms=ARRAY['Myocarditis','Cardiomyopathies','Heart Failure','Heart Septal Defects, Atrial','Pulmonary Artery','Infant','Humans','Cohort Studies']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1016/j.jacadv.2026.103006';
UPDATE artigos SET mesh_terms=ARRAY['Stroke','Atrial Fibrillation','Atrial Remodeling','Biomarkers','Electrocardiography','Echocardiography','Cohort Studies','Humans','Aged','Female','Male']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1016/j.jacadv.2026.102990';
UPDATE artigos SET mesh_terms=ARRAY['Metabolic Syndrome','Social Determinants of Health','Socioeconomic Factors','Life Style','mortality','Cardiovascular Diseases','Cerebrovascular Disorders','Kidney Diseases','Cohort Studies','Humans','Aged','Female','Male']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1136/bmjph-2025-004599';
UPDATE artigos SET mesh_terms=ARRAY['Calcification, Physiologic','Coronary Artery Disease','Coronary Vessels','anatomy  and  histology','Autopsy','Humans','Aged','Registries']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1093/ehjopen/oeag076';
UPDATE artigos SET mesh_terms=ARRAY['Atrial Fibrillation','Cardiac Surgical Procedures','Extracorporeal Circulation','Humans','Female','Male','Cohort Studies']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1093/ehjopen/oeag095';
UPDATE artigos SET mesh_terms=ARRAY['Cardiovascular Diseases','Risk Assessment','Health Status','Health Literacy','Women','Female','Adult','Humans','Cross-Sectional Studies']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1016/j.jacadv.2026.102862';
UPDATE artigos SET mesh_terms=ARRAY['ST Elevation Myocardial Infarction','Myocardial Reperfusion Injury','Artificial Intelligence','Machine Learning','Electrocardiography','Coronary Angiography','Magnetic Resonance Imaging','Cohort Studies','Humans','Adult']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1016/j.jacadv.2026.102864';
UPDATE artigos SET mesh_terms=ARRAY['Peripheral Arterial Disease','Atherosclerosis','Rivaroxaban','Aspirin','Hypolipidemic Agents','Exercise Therapy','Humans','Practice Guidelines as Topic']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1093/eurheartj/ehag516';
UPDATE artigos SET mesh_terms=ARRAY['Shock, Septic','Fluid Therapy','Vasoconstrictor Agents','Norepinephrine','Hemodynamics','Resuscitation','Humans','Adult','Aged','Review Literature as Topic']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1097/MCC.0000000000001409';
UPDATE artigos SET mesh_terms=ARRAY['Atrial Fibrillation','Catheter Ablation','Anticoagulants','Humans','Adult','Aged','Randomized Controlled Trials as Topic','Meta-Analysis as Topic']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1093/ehjopen/oeag067';
UPDATE artigos SET mesh_terms=ARRAY['Atrial Fibrillation','Cardiac Pacing, Artificial','Pacemaker, Artificial','Heart Conduction System','Electrocardiography','Atrial Function, Left','Humans','Review Literature as Topic']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1001/jamacardio.2026.2226';
UPDATE artigos SET mesh_terms=ARRAY['Heart Diseases','Influenza Vaccines','Influenza, Human','Myocardial Infarction','Heart Failure','Aged','Humans','Meta-Analysis as Topic']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.3390/jcm15145343';
UPDATE artigos SET mesh_terms=ARRAY['Atrial Fibrillation','Tachycardia, Ventricular','Death, Sudden, Cardiac','Heart Failure','Electrocardiography','Artificial Intelligence','Defibrillators, Implantable','Humans']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1016/j.jacep.2026.05.005';
UPDATE artigos SET mesh_terms=ARRAY['Coronary Artery Disease','Acute Coronary Syndrome','Platelet Aggregation Inhibitors','Aspirin','Percutaneous Coronary Intervention','Atrial Fibrillation','Humans','Practice Guidelines as Topic']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1093/ehjopen/oeag107';
UPDATE artigos SET mesh_terms=ARRAY['Hypertension','Antihypertensive Agents','Life Style','Blood Pressure Monitoring, Ambulatory','Drug Delivery Systems','Nanotechnology','Adult','Humans','Review Literature as Topic']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.2174';
UPDATE artigos SET mesh_terms=ARRAY['Brachytherapy','Ultrasonography, Interventional','Coronary Disease','Humans','Cohort Studies']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1016/j.jacadv.2026.102890';
UPDATE artigos SET mesh_terms=ARRAY['Tricuspid Valve Insufficiency','Natriuretic Peptide, Brain','Heart Valve Prosthesis Implantation','mortality','Treatment Outcome','Cohort Studies','Aged','Humans']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1016/j.jacadv.2026.102921';
UPDATE artigos SET mesh_terms=ARRAY['Cardiomyopathy, Hypertrophic','Echocardiography','Genotype','Risk Assessment','Prognosis','Cohort Studies','Humans','Aged','Female','Male']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1016/j.jacadv.2026.102863';
UPDATE artigos SET mesh_terms=ARRAY['Lymphoma','Cardiovascular Diseases','Hospitalization','Cohort Studies','Population Surveillance','Survivors','Aged','Humans']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1016/j.jacadv.2026.102860';
UPDATE artigos SET mesh_terms=ARRAY['Peripheral Arterial Disease','Atherosclerosis','anatomy  and  histology','Lower Extremity','Humans','Aged','Registries']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1016/j.jacadv.2026.102882';
UPDATE artigos SET mesh_terms=ARRAY['Anxiety','Heart Diseases','Mass Screening','Psychometrics','Surveys and Questionnaires','Cross-Sectional Studies','Child','Adolescent','Caregivers','Humans']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1016/j.jacadv.2026.102858';
UPDATE artigos SET mesh_terms=ARRAY['Diastole','Ventricular Dysfunction, Left','Insulin Resistance','Triglycerides','Glucose','Waist-Height Ratio','Humans','Male','Female','Military Personnel','Athletes','Cross-Sectional Studies']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1016/j.jacadv.2026.102865';
UPDATE artigos SET mesh_terms=ARRAY['Breast Neoplasms','radiotherapy','Radiotherapy, Adjuvant','Heart Diseases','Coronary Artery Disease','Cohort Studies','Registries','Humans','Female']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1001/jamaoncol.2026.2066';
UPDATE artigos SET mesh_terms=ARRAY['Arthroplasty, Replacement, Hip','Arthroplasty, Replacement, Knee','Venous Thromboembolism','Aspirin','Rivaroxaban','Postoperative Period','Humans','Aged','Female','Male','Randomized Controlled Trials as Topic']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1056/NEJMoa2603649';
UPDATE artigos SET mesh_terms=ARRAY['Heart Arrest','Marathon Running','Weather','Temperature','Air Pollution','Registries','Cohort Studies','Humans']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1016/j.jacadv.2026.102965';
UPDATE artigos SET mesh_terms=ARRAY['Heart Arrest','Cardiopulmonary Resuscitation','Extracorporeal Membrane Oxygenation','Treatment Outcome','Cohort Studies','Humans','Adult','Male','Female']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1016/j.jacadv.2026.103049';
UPDATE artigos SET mesh_terms=ARRAY['Amyloidosis','Cardiomyopathies','Heart Failure','Registries','Cohort Studies','Humans','Aged','Female','Male']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1016/j.jacadv.2026.103068';
UPDATE artigos SET mesh_terms=ARRAY['Coronary Artery Disease','Tomography Scanners, X-Ray Computed','Aged','Humans','Male','Female','Cohort Studies']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1016/j.jacadv.2026.103031';
UPDATE artigos SET mesh_terms=ARRAY['Tricuspid Valve Insufficiency','Heart Valve Prosthesis Implantation','Heart Valve Prosthesis','Aged','Humans','Cohort Studies']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1016/j.jacadv.2026.103033';
UPDATE artigos SET mesh_terms=ARRAY['Heart Failure','Obesity','Sodium-Glucose Transporter 2 Inhibitors','Mineralocorticoid Receptor Antagonists','Glucagon-Like Peptide-1 Receptor Agonists','Humans','Aged','Practice Guidelines as Topic']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1016/j.jacc.2026.06.018';
UPDATE artigos SET mesh_terms=ARRAY['Atrial Fibrillation','Atrial Flutter','Electrocardiography','Aged','Humans','Stroke','Dementia','Cohort Studies']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.3390/';
UPDATE artigos SET mesh_terms=ARRAY['Hypertension','Practice Guidelines as Topic','diagnosis','Antihypertensive Agents','Blood Pressure Monitoring, Ambulatory','Humans','Aged','Diabetes Mellitus, Type 2']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='hypertension-in-adults-diagnosis-and-management-ng136';
UPDATE artigos SET mesh_terms=ARRAY['Heart Failure','Spironolactone','Mineralocorticoid Receptor Antagonists','Humans','Aged','Female','Male','Randomized Controlled Trials as Topic']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='the-effect-of-spironolactone-on-morbidity-and-mortality-in-patients-with-severe';
UPDATE artigos SET mesh_terms=ARRAY['Cardiovascular Diseases','Atherosclerosis','Hypertension','Risk Factors','Incidence','Prevalence','Cohort Studies','Humans','Adult','Middle Aged']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='epidemiological-approaches-to-heart-disease-the-framingham-study';
UPDATE artigos SET mesh_terms=ARRAY['Cardiovascular Diseases','Lipoprotein(a)','Atherosclerosis','Myocardial Infarction','Stroke','Peripheral Arterial Disease','Risk Assessment','Humans','Practice Guidelines as Topic']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1093/eurjpc/zwag313';
UPDATE artigos SET mesh_terms=ARRAY['Exercise Therapy','Frailty','Stroke','Spinal Cord Injuries','Arthritis','Cardiomyopathies','Heart Transplantation','Heart-Assist Devices','Defibrillators, Implantable','Humans','Aged']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1161/CIR.0000000000001456';
UPDATE artigos SET mesh_terms=ARRAY['Atherosclerosis','Cardiovascular Diseases','Hypertriglyceridemia','Triglycerides','Humans','Diabetes Mellitus, Type 2','Pancreatitis']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1093/eurjpc/zwag341';
UPDATE artigos SET mesh_terms=ARRAY['Coronary Artery Disease','Angioplasty, Balloon, Coronary','Ultrasonography, Interventional','Tomography, Optical Coherence','Humans','Review Literature as Topic']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.31661/gmj.v15i.4274';
UPDATE artigos SET mesh_terms=ARRAY['Cardiovascular Diseases','Pregnancy','Prenatal Care','Pre-Eclampsia','Biomarkers','Blood Pressure','Metabolic Syndrome']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1016/j.jacadv.2026.102962';
UPDATE artigos SET mesh_terms=ARRAY['Cardiotoxicity','Radiomics','Antineoplastic Agents','radiotherapy','Echocardiography','Tomography, X-Ray Computed','Positron Emission Tomography Computed Tomography','Breast Neoplasms','Humans','Female','Review Literature as Topic']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1016/j.jacadv.2026.102942';
UPDATE artigos SET mesh_terms=ARRAY['HIV Infections','Cardiovascular Diseases','Biomarkers','Risk Factors','Primary Prevention','Prognosis','Cohort Studies','Humans']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1016/j.jacadv.2026.102984';
UPDATE artigos SET mesh_terms=ARRAY['Percutaneous Coronary Intervention','Coronary Angiography','Ultrasonography, Interventional','Tomography, Optical Coherence','Humans','Aged','Registries','Italy']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1016/j.jacadv.2026.102982';
UPDATE artigos SET mesh_terms=ARRAY['Death, Sudden, Cardiac','Hypertrophy, Left Ventricular','Coronary Artery Disease','Electrocardiography','Cohort Studies','Humans','Aged','Female','Male']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1016/j.ijcard.2026.134680';
UPDATE artigos SET mesh_terms=ARRAY['Heart Failure','Obesity','Tirzepatide','Humans','Aged','Female','Male','Randomized Controlled Trials as Topic']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1016/j.jchf.2026.103218';
UPDATE artigos SET mesh_terms=ARRAY['Heart Failure','Biomarkers','Electrocardiography','Inflammation','Death, Sudden, Cardiac','Humans','Aged','Cohort Studies']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1016/j.jacadv.2026.102922';
UPDATE artigos SET mesh_terms=ARRAY['Cardiovascular Diseases','Kidney Diseases','Diabetes Mellitus, Type 2','Heart Failure','Sodium-Glucose Transporter 2 Inhibitors','Humans','Aged']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.3389/fphar.2026.1800868';
UPDATE artigos SET mesh_terms=ARRAY['Cannabis','Arrhythmias, Cardiac','Electrocardiography','Adult','Humans','Female','Male','Randomized Controlled Trials as Topic']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1016/j.jacc.2026.07.014';
UPDATE artigos SET mesh_terms=ARRAY['Myocardial Infarction','ST Elevation Myocardial Infarction','Nicorandil','Angioplasty, Balloon, Coronary','Humans','Male','Female','Randomized Controlled Trials as Topic']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1016/j.jacc.2026.07.005';
UPDATE artigos SET mesh_terms=ARRAY['Pediatric Obesity','Anti-Obesity Agents','Blood Pressure','Hypertension','Renal Insufficiency, Chronic','Child','Adolescent','Humans','Review Literature as Topic']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1007/s00467-026-07293-8';
UPDATE artigos SET mesh_terms=ARRAY['Breast Neoplasms','Cardiovascular Diseases','Cardiotoxicity','Antineoplastic Agents','radiotherapy','Survivors','Female','Humans']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1001/jamacardio.2026.2546';
UPDATE artigos SET mesh_terms=ARRAY['Dyslipidemias','Atherosclerosis','Cardiovascular Diseases','Cholesterol, LDL','Lipoprotein(a)','Risk Assessment','Hypolipidemic Agents','Practice Guidelines as Topic','Humans','Child','Adult']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.36660/abc.20250640';
UPDATE artigos SET mesh_terms=ARRAY['Cardiomyopathy, Hypertrophic','Genetic Testing','Mass Screening','Pedigree','Child','Adolescent','Humans','Cohort Studies']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1016/j.jchf.2026.103283';
UPDATE artigos SET mesh_terms=ARRAY['Venous Thromboembolism','Neoplasms','Anticoagulants','Hemorrhage','Risk Assessment','Cohort Studies','Registries','Humans','Aged']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1016/j.jaccao.2026.05.002';
UPDATE artigos SET mesh_terms=ARRAY['Angina Pectoris','Coronary Artery Disease','Percutaneous Coronary Intervention','Coronary Angiography','Coronary Circulation','Microvascular Angina','Humans','Randomized Controlled Trials as Topic']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1093/eurheartj/ehag113';
UPDATE artigos SET mesh_terms=ARRAY['Aortic Valve Stenosis','Coronary Artery Disease','Angina Pectoris','Percutaneous Coronary Intervention','Transcatheter Aortic Valve Replacement','Treatment Outcome','Aged','Humans','Randomized Controlled Trials as Topic']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1093/ehjvshd/xwag047';
UPDATE artigos SET mesh_terms=ARRAY['Shock, Cardiogenic','Myocardial Infarction','Palliative Care','Terminal Care','Hospitalization','Intensive Care Units','Aged','Cohort Studies']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1016/j.jacadv.2026.102869';
UPDATE artigos SET mesh_terms=ARRAY['Stroke','C-Reactive Protein','Cholesterol','Lipoproteins','Inflammation','mortality','Treatment Outcome','Cohort Studies','Humans']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1016/j.jacadv.2026.102880';
UPDATE artigos SET mesh_terms=ARRAY['Atherosclerosis','Coronary Artery Disease','Adipose Tissue','Tomography, X-Ray Computed','Plaque, Atherosclerotic','Longitudinal Studies','Adult','Middle Aged','Female','Male','Humans']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1016/j.jcmg.2026.05.014';
UPDATE artigos SET mesh_terms=ARRAY['Coronary Artery Disease','Diabetes Mellitus, Type 2','Obesity','Semaglutide','Tirzepatide','Acute Coronary Syndrome','Myocardial Infarction','Angina Pectoris','Humans','Randomized Controlled Trials as Topic','Meta-Analysis as Topic']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1016/j.numecd.2026.104859';
UPDATE artigos SET mesh_terms=ARRAY['Aortic Valve Stenosis','Transcatheter Aortic Valve Replacement','Echocardiography','Tomography, X-Ray Computed','Humans','Practice Guidelines as Topic']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1161/CIRCIMAGING.125.018670';
UPDATE artigos SET mesh_terms=ARRAY['Critical Care','Emergencies','Echocardiography','Ultrasonography','Shock, Cardiogenic','Heart Failure','Humans','Practice Guidelines as Topic']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1093/ehjci/jeaf246';
UPDATE artigos SET mesh_terms=ARRAY['Foramen Ovale, Patent','Septal Occluder Device','Platelet Aggregation Inhibitors','Treatment Outcome','Hemorrhage','Cohort Studies','Registries','Humans','Female','Male']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1016/j.jacadv.2026.102943';
UPDATE artigos SET mesh_terms=ARRAY['Neoplasms','mortality','Cause of Death','Cohort Studies','Humans','Aged','Adult','United States']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1016/j.jacadv.2026.103035';
UPDATE artigos SET mesh_terms=ARRAY['Endocarditis','Cardiac Catheterization','Anti-Bacterial Agents','Heart Defects, Congenital','Adolescent','Child','Cohort Studies','Registries']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1016/j.jacadv.2026.102969';
UPDATE artigos SET mesh_terms=ARRAY['Coronary Disease','Myocardial Infarction','Risk Factors','Cancer Survivors','Cardiovascular Diseases','Life Expectancy','Humans','Cohort Studies']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1016/j.jacadv.2026.102968';
UPDATE artigos SET mesh_terms=ARRAY['Aortic Valve Stenosis','Transcatheter Aortic Valve Replacement','Obesity','Body Mass Index','Aged','Humans','Registries','Cohort Studies']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1016/j.jacadv.2026.102985';
UPDATE artigos SET mesh_terms=ARRAY['Hypertension','Biomarkers','Inflammation','Hemostasis','Cohort Studies','Humans','Female','Middle Aged']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1016/j.jacadv.2026.103071';
UPDATE artigos SET mesh_terms=ARRAY['Coronary Artery Disease','Myocardial Infarction','Plaque, Atherosclerotic','Vascular Calcification','Tomography, Optical Coherence','Artificial Intelligence','Image Interpretation, Computer-Assisted','Humans','Cross-Sectional Studies','Cohort Studies']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1016/j.jacadv.2026.103077';
UPDATE artigos SET mesh_terms=ARRAY['Coronary Artery Bypass','Echocardiography, Transesophageal','Randomized Controlled Trials as Topic','Feasibility Studies','Humans','Adult','Middle Aged','Aged']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1016/j.jacadv.2026.103030';
UPDATE artigos SET mesh_terms=ARRAY['Coronary Artery Disease','Vascular Calcification','Lithotripsy','Stents','Registries','Humans','Aged']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1016/j.jacadv.2026.103010';
UPDATE artigos SET mesh_terms=ARRAY['Coronary Disease','Proteomics','Mendelian Randomization Analysis','Genomics','Asian People','Humans','Cohort Studies']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1016/j.jacc.2026.05.049';
UPDATE artigos SET mesh_terms=ARRAY['Heart Failure','Tolvaptan','Antidiuretic Hormone Receptor Antagonists','Treatment Outcome','Hospitalization','Humans','Aged','Randomized Controlled Trials as Topic']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1001/';
UPDATE artigos SET mesh_terms=ARRAY['Cardiovascular Diseases','Heart Failure','Pulmonary Disease, Chronic Obstructive','Aged','Humans','Female','Male','Cohort Studies','Air Pollution','Particulate Matter','Wildfires']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1016/j.jacc.2025.12.079';
UPDATE artigos SET mesh_terms=ARRAY['Cardiomyopathies','Heart Ventricles','Magnetic Resonance Imaging','Prognosis','Cohort Studies','Humans','Adult','Female','Male']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1016/j.jacc.2026.03.033';
UPDATE artigos SET mesh_terms=ARRAY['Coronary Disease','Cardiovascular Diseases','Risk Factors','Life Style','Cohort Studies','Longitudinal Studies','Recurrence','Humans','Middle Aged','Female','Male']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1161/CIRCOUTCOMES.125.013159';
UPDATE artigos SET mesh_terms=ARRAY['Atrial Fibrillation','Clonal Hematopoiesis','Cerebral Small Vessel Diseases','Cognition Disorders','Magnetic Resonance Imaging','Aged','Cohort Studies']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1161/CIRCULATIONAHA.126.079459';
UPDATE artigos SET mesh_terms=ARRAY['Atrial Fibrillation','Alzheimer Disease','Anticoagulants','Warfarin','Cognition','Mental Status and Dementia Tests','Aged','Humans','Female','Male','Cohort Studies','Registries']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1093/eurheartj/ehag584';
UPDATE artigos SET mesh_terms=ARRAY['Artificial Intelligence','Electrocardiography','mortality','Prognosis','Aged','Humans','Cohort Studies']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1016/j.jacadv.2026.102875';
UPDATE artigos SET mesh_terms=ARRAY['Cardiovascular Diseases','etiology','Randomized Controlled Trials as Topic','Cohort Studies','Confounding Factors, Epidemiologic','Humans']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1093/eurjpc/zwag267';
UPDATE artigos SET mesh_terms=ARRAY['Heart Failure','Myocardial Infarction','Coronary Disease','Atrial Fibrillation','Hypertension','Adrenergic beta-Antagonists','Humans','Review Literature as Topic']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1016/j.jacc.2026.06.015';
UPDATE artigos SET mesh_terms=ARRAY['Heart Failure','Losartan','Angiotensin Receptor Antagonists','Humans','Aged','Male','Female','Randomized Controlled Trials as Topic']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1016/S0140-';
UPDATE artigos SET mesh_terms=ARRAY['Cardiovascular Diseases','Polypharmacy','Deprescriptions','Medication Reconciliation','Humans','Practice Guidelines as Topic','Aged','Pediatrics']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1161/CIR.0000000000001459';
UPDATE artigos SET mesh_terms=ARRAY['Cardiovascular Diseases','Cognition Disorders','Frailty','Aged','Humans','Practice Guidelines as Topic']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1016/j.jacc.2026.07.009';
UPDATE artigos SET mesh_terms=ARRAY['Heart Failure','Body Composition','Magnetic Resonance Imaging','Absorptiometry, Photon','Humans','Aged','Female','Male','Cross-Sectional Studies']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1016/j.jchf.2026.103242';
UPDATE artigos SET mesh_terms=ARRAY['Obesity','Overweight','Tirzepatide','Quality of Life','Patient Acceptance of Health Care','Health Services Accessibility','Humans','Cross-Sectional Studies']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1016/j.obpill.2026.100288';
UPDATE artigos SET mesh_terms=ARRAY['Obesity','Semaglutide','C-Reactive Protein','Biomarkers','Cardiovascular Diseases','Humans','Cohort Studies']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='10.1161/CIRCULATIONAHA.125.074482';
UPDATE artigos SET mesh_terms=ARRAY['Heart Failure','Coronary Disease','Carvedilol','Ventricular Function, Left','Exercise','Humans','Aged','Male','Female','Randomized Controlled Trials as Topic']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='randomised-placebo-controlled-trial-of-carvedilol-in-patients-with-congestive-he';
UPDATE artigos SET mesh_terms=ARRAY['Coronary Artery Disease','Percutaneous Coronary Intervention','Fractional Flow Reserve, Myocardial','Angiography','Humans','Aged','Male','Female','Randomized Controlled Trials as Topic']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='fractional-flow-reserve-versus-angiography-for-guiding-percutaneous-coronary-int';
UPDATE artigos SET mesh_terms=ARRAY['Myocardial Infarction','Heart Failure','Eplerenone','Mineralocorticoid Receptor Antagonists','Ventricular Dysfunction, Left','Humans','Aged','Female','Male','Randomized Controlled Trials as Topic']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='eplerenone-a-selective-aldosterone-blocker-in-patients-with-left-ventricular-dys';
UPDATE artigos SET mesh_terms=ARRAY['Myocardial Infarction','Ventricular Dysfunction, Left','Captopril','Angiotensin-Converting Enzyme Inhibitors','Heart Failure','mortality','Humans','Randomized Controlled Trials as Topic']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='effect-of-captopril-on-mortality-and-morbidity-in-patients-with-left-ventricular';
UPDATE artigos SET mesh_terms=ARRAY['Myocardial Infarction','Heart Failure','Ventricular Dysfunction, Left','Valsartan','Captopril','Angiotensin Receptor Antagonists','Angiotensin-Converting Enzyme Inhibitors','Humans','Aged','Female','Male','Randomized Controlled Trials as Topic']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='valsartan-captopril-or-both-in-myocardial-infarction-complicated-by-heart-failur';
UPDATE artigos SET mesh_terms=ARRAY['Heart Failure','Carvedilol','Adrenergic beta-Antagonists','Humans','Adult','Female','Male','Randomized Controlled Trials as Topic']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='the-effect-of-carvedilol-on-morbidity-and-mortality-in-patients-with-chronic-hea';
UPDATE artigos SET mesh_terms=ARRAY['Heart Failure','Enalapril','Angiotensin-Converting Enzyme Inhibitors','Survival Rate','Hospitalization','Humans','Male','Female','Randomized Controlled Trials as Topic']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='effect-of-enalapril-on-survival-in-patients-with-reduced-left-ventricular-ejecti';
UPDATE artigos SET mesh_terms=ARRAY['Heart Failure','Enalapril','Angiotensin-Converting Enzyme Inhibitors','mortality','Humans','Aged','Female','Male','Randomized Controlled Trials as Topic']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='effects-of-enalapril-on-mortality-in-severe-congestive-heart-failure-results-of';
UPDATE artigos SET mesh_terms=ARRAY['Heart Failure','Bisoprolol','Adrenergic beta-Antagonists','Humans','Female','Male','Randomized Controlled Trials as Topic']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='the-cardiac-insufficiency-bisoprolol-study-ii-cibis-ii-a-randomised-trial';
UPDATE artigos SET mesh_terms=ARRAY['Myocardial Infarction','Defibrillators, Implantable','Ventricular Dysfunction, Left','Death, Sudden, Cardiac','mortality','Humans','Male','Female','Randomized Controlled Trials as Topic']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='prophylactic-use-of-an-implantable-cardioverterdefibrillator-after-acute-myocard';
UPDATE artigos SET mesh_terms=ARRAY['Coronary Artery Disease','Coronary Artery Bypass','Defibrillators, Implantable','Ventricular Fibrillation','Tachycardia, Ventricular','Ventricular Dysfunction, Left','Humans','Randomized Controlled Trials as Topic']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='prophylactic-use-of-implanted-cardiac-defibrillators-in-patients-at-high-risk-fo';
UPDATE artigos SET mesh_terms=ARRAY['Ventricular Fibrillation','Tachycardia, Ventricular','Defibrillators, Implantable','Amiodarone','Anti-Arrhythmia Agents','Survival Rate','Humans','Aged','Male','Female','Randomized Controlled Trials as Topic']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='a-comparison-of-antiarrhythmic-drug-therapy-with-implantable-defibrillators-in-p';
UPDATE artigos SET mesh_terms=ARRAY['Myocardial Infarction','Heart Failure','Ventricular Dysfunction, Left','Defibrillators, Implantable','Death, Sudden, Cardiac','Humans','Male','Female','Aged','Randomized Controlled Trials as Topic']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='prophylactic-implantation-of-a-defibrillator-in-patients-with-myocardial-infarct';
UPDATE artigos SET mesh_terms=ARRAY['Heart Failure','Defibrillators, Implantable','Amiodarone','Death, Sudden, Cardiac','Ventricular Fibrillation','Humans','Female','Male','Randomized Controlled Trials as Topic']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='amiodarone-or-an-implantable-cardioverterdefibrillator-for-congestive-heart-fail';
UPDATE artigos SET mesh_terms=ARRAY['Heart Failure','Cardiac Resynchronization Therapy','Ventricular Dysfunction, Left','Electric Stimulation Therapy','Humans','Aged','Male','Female','Randomized Controlled Trials as Topic']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='the-effect-of-cardiac-resynchronization-on-morbidity-and-mortality-in-heart-fail';
UPDATE artigos SET mesh_terms=ARRAY['Heart Failure','Defibrillators, Implantable','Electric Countershock','Ventricular Fibrillation','Tachycardia, Ventricular','mortality','Humans','Cohort Studies']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='prognostic-importance-of-defibrillator-shocks-in-patients-with-heart-failure';
UPDATE artigos SET mesh_terms=ARRAY['Heart Failure','Vasodilator Agents','Hydralazine','Isosorbide Dinitrate','Prazosin','mortality','Humans','Male','Randomized Controlled Trials as Topic']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='effect-of-vasodilator-therapy-on-mortality-in-chronic-congestive-heart-failure-r';
UPDATE artigos SET mesh_terms=ARRAY['Heart Failure','Digoxin','Hospitalization','mortality','Humans','Aged','Female','Male','Randomized Controlled Trials as Topic']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='the-effect-of-digoxin-on-mortality-and-morbidity-in-patients-with-heart-failure';
UPDATE artigos SET mesh_terms=ARRAY['Cardiomyopathy, Dilated','Heart Failure','Defibrillators, Implantable','Tachycardia, Ventricular','Death, Sudden, Cardiac','Humans','Adult','Male','Female','Randomized Controlled Trials as Topic']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='prophylactic-defibrillator-implantation-in-patients-with-nonischemic-dilated-car';
UPDATE artigos SET mesh_terms=ARRAY['Heart Failure','Vasodilator Agents','Hydralazine','Isosorbide Dinitrate','Black or African American','Humans','Male','Female','Randomized Controlled Trials as Topic']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='combination-of-isosorbide-dinitrate-and-hydralazine-in-blacks-with-heart-failure';
UPDATE artigos SET mesh_terms=ARRAY['Myocardial Infarction','Heart Failure','Ventricular Dysfunction, Left','Death, Sudden, Cardiac','Heart Arrest','Cohort Studies','Humans','Aged','Female','Male']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='sudden-death-in-patients-with-myocardial-infarction-and-left-ventricular-dysfunc';
UPDATE artigos SET mesh_terms=ARRAY['Myocardial Infarction','Heart Failure','Losartan','Captopril','Angiotensin Receptor Antagonists','Angiotensin-Converting Enzyme Inhibitors','Humans','Aged','Male','Female','Randomized Controlled Trials as Topic']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='effects-of-losartan-and-captopril-on-mortality-and-morbidity-in-high-risk-patien';
UPDATE artigos SET mesh_terms=ARRAY['Myocardial Infarction','Ventricular Fibrillation','Tachycardia, Ventricular','Catheter Ablation','Defibrillators, Implantable','Secondary Prevention','Humans','Aged','Male','Female','Randomized Controlled Trials as Topic']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='prophylactic-catheter-ablation-for-the-prevention-of-defibrillator-therapy';
UPDATE artigos SET mesh_terms=ARRAY['Atrial Fibrillation','Heart Failure','Amiodarone','Electric Countershock','Humans','Aged','Male','Female','Randomized Controlled Trials as Topic']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='rhythm-control-versus-rate-control-for-atrial-fibrillation-and-heart-failure';
UPDATE artigos SET mesh_terms=ARRAY['Heart Failure','Angiotensin Receptor Antagonists','Aged','Female','Male','Humans','Randomized Controlled Trials as Topic']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='effects-of-candesartan-in-patients-with-chronic-heart-failure-and-preserved-left';
UPDATE artigos SET mesh_terms=ARRAY['Myocardial Infarction','Defibrillators, Implantable','Death, Sudden, Cardiac','Tachycardia, Ventricular','Heart Failure','Humans','Male','Female','Randomized Controlled Trials as Topic']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='defibrillator-implantation-early-after-myocardial-infarction';
UPDATE artigos SET mesh_terms=ARRAY['Heart Failure','Furosemide','Administration, Intravenous','Diuretics','Humans','Aged','Male','Female','Randomized Controlled Trials as Topic']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='diuretic-strategies-in-patients-with-acute-decompensated-heart-failure';
UPDATE artigos SET mesh_terms=ARRAY['Heart Failure','Exercise','Exercise Therapy','Quality of Life','Patient Reported Outcome Measures','Humans','Female','Male','Randomized Controlled Trials as Topic']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='effects-of-exercise-training-on-health-status-in-patients-with-chronic-heart-fai';
UPDATE artigos SET mesh_terms=ARRAY['Heart Failure','Cardiac Resynchronization Therapy','Ventricular Dysfunction, Left','Pacemaker, Artificial','Humans','Aged','Female','Male','Randomized Controlled Trials as Topic']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='cardiac-resynchronization-in-chronic-heart-failure';
UPDATE artigos SET mesh_terms=ARRAY['Heart Failure','Practice Guidelines as Topic','Sodium-Glucose Transporter 2 Inhibitors','Mineralocorticoid Receptor Antagonists','Angiotensin-Converting Enzyme Inhibitors','Adrenergic beta-Antagonists','Natriuretic Peptide, Brain','Echocardiography','Adult','Humans']::text[], mesh_origem='mesh_llm'
 WHERE doc_id='chronic-heart-failure-in-adults-diagnosis-and-management-ng106';

-- conferência: rode e confira que `vazios` deu ZERO
SELECT count(*) FILTER (WHERE mesh_terms IS NULL OR cardinality(mesh_terms)=0) AS vazios,
       count(*) FILTER (WHERE mesh_origem='pubmed')   AS do_pubmed,
       count(*) FILTER (WHERE mesh_origem='mesh_llm') AS do_modelo,
       count(*) AS total
  FROM artigos;
