-- ═══════════════════════════════════════════════════════════════════════════
--  LIMPEZA DO SUPABASE — 02/Ago/2026
--  Preparado pelo Claude · EXECUTADO PELO DR. EDUARDO (o Claude nunca apaga no banco)
--
--  POR QUÊ: tudo que subiu até aqui foi analisado com o motor único e com o
--  classificador antigo — tipo errado → motor errado → prompt errado → nota errada.
--  E a nota ANCORA a perícia inteira (medido em 02/Ago: 86% do texto muda com ela).
--  Não dá para consertar linha a linha: a análise inteira nasceu do veredito errado.
--
--  COMO USAR: rode os SELECT primeiro, CONFIRA os números, e só então o DELETE.
--  No Supabase: SQL Editor → cole um bloco por vez.
-- ═══════════════════════════════════════════════════════════════════════════


-- ─── PASSO 1 · OLHAR ANTES DE APAGAR (não muda nada) ───────────────────────
select count(*) as total_de_artigos from artigos;

select date_trunc('month', created_at)::date as mes, count(*)
from artigos group by 1 order by 1;

-- os DOI corrompidos com ')' (tarefa #19, aberta desde 25/Jul)
select doc_id, titulo from artigos where doc_id like '%)%' or doc_id like '%(%';

-- as notas que não deviam ter sido publicadas (a porta publica a partir de 6)
select doc_id, nota_aplicabilidade_clinica, titulo
from artigos where nota_aplicabilidade_clinica < 6 order by 1;


-- ─── PASSO 2 · A CÓPIA DE SEGURANÇA (faça ANTES do delete) ─────────────────
-- Cria uma tabela paralela com tudo. Se der errado, dá para voltar.
create table if not exists artigos_backup_20260802 as select * from artigos;
select count(*) as linhas_no_backup from artigos_backup_20260802;


-- ─── PASSO 3 · APAGAR ──────────────────────────────────────────────────────
-- ESCOLHA UMA das três opções. Descomente só a que você quiser.

-- (A) LIMPEZA TOTAL — recomeça do zero. É o que a análise de 02/Ago sustenta:
--     nenhuma linha publicada até aqui passou pelos motores por tipo.
-- delete from artigos;

-- (B) SÓ O QUE FOI ANALISADO NO PERÍODO RUIM (ajuste as datas se quiser)
-- delete from artigos where created_at >= '2026-07-01';

-- (C) SÓ O QUE ESTÁ COMPROVADAMENTE QUEBRADO (conservador)
-- delete from artigos where doc_id like '%)%' or doc_id like '%(%'
--                        or nota_aplicabilidade_clinica < 6;


-- ─── PASSO 4 · CONFERIR ────────────────────────────────────────────────────
select count(*) as sobraram from artigos;

-- Quando tudo estiver bem e você não quiser mais o backup:
-- drop table artigos_backup_20260802;
