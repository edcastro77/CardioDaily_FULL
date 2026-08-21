-- 2º TEMA (21/Ago/2026). Duas etapas, nesta ordem — inverter estragaria.
-- Piso 0,40 mantido por decisao dele: 2o tema so com >=40% do peso do 1o.
-- So toca onde tema_secundario IS NULL: nao sobrescreve nada.

BEGIN;

-- (1) os que o MeSH resolveu — tema DE VERDADE
UPDATE artigos SET tema_secundario='Cardiometabólica' WHERE doc_id='10.1002/clc.70401' AND tema_secundario IS NULL;
UPDATE artigos SET tema_secundario='Coronária/DAC' WHERE doc_id='10.1002/clc.70398' AND tema_secundario IS NULL;
UPDATE artigos SET tema_secundario='Miocardiopatias' WHERE doc_id='10.1016/j.hfc.2026.02.010' AND tema_secundario IS NULL;
UPDATE artigos SET tema_secundario='Miocardiopatias' WHERE doc_id='10.1016/j.hfc.2026.02.009' AND tema_secundario IS NULL;
UPDATE artigos SET tema_secundario='Coronária/DAC' WHERE doc_id='10.1161/STROKEAHA.125.054990' AND tema_secundario IS NULL;
UPDATE artigos SET tema_secundario='Imagem Cardiovascular' WHERE doc_id='10.1161/CIRCIMAGING.125.019726' AND tema_secundario IS NULL;
UPDATE artigos SET tema_secundario='Imagem Cardiovascular' WHERE doc_id='10.1016/j.jacc.2026.02.5122' AND tema_secundario IS NULL;
UPDATE artigos SET tema_secundario='Cardio-Oncologia' WHERE doc_id='10.1161/HYPERTENSIONAHA.125.26016' AND tema_secundario IS NULL;
UPDATE artigos SET tema_secundario='Insuficiência Cardíaca' WHERE doc_id='10.1016/j.jacc.2023.04.003' AND tema_secundario IS NULL;
UPDATE artigos SET tema_secundario='Cardiometabólica' WHERE doc_id='10.1093/ehjcvp/pvag024' AND tema_secundario IS NULL;
UPDATE artigos SET tema_secundario='Cardiometabólica' WHERE doc_id='10.1016/j.ahj.2026.107510' AND tema_secundario IS NULL;
UPDATE artigos SET tema_secundario='Imagem Cardiovascular' WHERE doc_id='10.1093/eschf/xvag151' AND tema_secundario IS NULL;
UPDATE artigos SET tema_secundario='Intervenção/Hemodinâmica' WHERE doc_id='10.1056/NEJMoa2600440' AND tema_secundario IS NULL;
UPDATE artigos SET tema_secundario='Imagem Cardiovascular' WHERE doc_id='10.1016/j.jacc.2026.03.174' AND tema_secundario IS NULL;
UPDATE artigos SET tema_secundario='Cardiometabólica' WHERE doc_id='10.1002/clc.70400' AND tema_secundario IS NULL;
UPDATE artigos SET tema_secundario='Coronária/DAC' WHERE doc_id='10.1002/clc.70389' AND tema_secundario IS NULL;
UPDATE artigos SET tema_secundario='Cardio-Obstetrícia' WHERE doc_id='10.1001/jamanetworkopen.2026.28586' AND tema_secundario IS NULL;
UPDATE artigos SET tema_secundario='Aorta/Congênitas/Genética' WHERE doc_id='10.1093/ehjci/jeag141' AND tema_secundario IS NULL;
UPDATE artigos SET tema_secundario='Imagem Cardiovascular' WHERE doc_id='10.1093/eurheartj/ehag373' AND tema_secundario IS NULL;
UPDATE artigos SET tema_secundario='Intervenção/Hemodinâmica' WHERE doc_id='10.1161/STROKEAHA.126.055632' AND tema_secundario IS NULL;

-- (2) o que sobrou: o vazio ganha NOME (LEI 11), nunca fica NULL
UPDATE artigos SET tema_secundario='Não se aplica' WHERE tema_secundario IS NULL;

SELECT count(*) FILTER (WHERE tema_secundario IS NULL) AS nulos,
       count(*) FILTER (WHERE tema_secundario = 'Não se aplica') AS nao_se_aplica,
       count(*) FILTER (WHERE tema_secundario NOT IN ('Não se aplica')) AS com_2o_tema
FROM artigos;
COMMIT;
