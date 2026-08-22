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
