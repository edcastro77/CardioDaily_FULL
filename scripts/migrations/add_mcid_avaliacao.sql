-- Migração: adiciona coluna mcid_avaliacao na tabela artigos
-- Executar no Supabase Dashboard → SQL Editor
-- Data: 2026-05-29

ALTER TABLE artigos
  ADD COLUMN IF NOT EXISTS mcid_avaliacao TEXT;

COMMENT ON COLUMN artigos.mcid_avaliacao IS
  'Avaliação MCID (Diferença Minimamente Importante Clinicamente): '
  'MCID utilizado ou estimado, tamanho do efeito (ARR/NNT/MD/SMD), '
  'IC 95%, comparação limite inferior IC vs MCID, veredito clínico. '
  'Formato: "MCID: X | Efeito: Y (IC95% A–B) | Limite inf. supera MCID: SIM/NÃO | Veredito: ..."';
