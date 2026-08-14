-- ═══════════════════════════════════════════════════════════════════════════════
-- APAGAR OS 3 PROTOCOLOS DE ESTUDO · 11/Ago/2026
--
--   *"tem que tirar do supabase — não pode nem aparecer esses trocos"* — Dr. Eduardo
--
-- São três artigos "Rationale and Design": descrevem um ensaio que AINDA NÃO ACONTECEU.
-- Não têm resultado, não têm N final, não têm desfecho medido. Os três estavam com NOTA 8.
--
-- POR QUE TIRARAM 8: o extrator leu o documento, viu randomização, dois braços e desfecho
-- primário pré-especificado, e escreveu `desenho: rct`. Estava CERTO — o desenho descrito
-- É um RCT. O motor então deu o teto do RCT, 10. Ninguém errou: faltava a palavra
-- `protocolo` no vocabulário do sistema. Ela existe desde 11/Ago.
--
-- ⚠️ COMO RODAR
--    1. app.supabase.com → projeto hzqtogcpwdzhjfroxtfz → SQL Editor
--    2. Rode PRIMEIRO o SELECT de conferência (bloco 1). Tem que devolver EXATAMENTE 3
--       linhas, e os títulos têm que ser os três abaixo.
--    3. Só então rode o DELETE (bloco 2).
--
-- ⚠️ Apagar linha é irreversível e não existe "desfazer" aqui. Por isso quem roda é você,
--    e por isso a conferência vem antes. Se o bloco 1 devolver 2 ou 4 linhas, PARE e me diga.
-- ═══════════════════════════════════════════════════════════════════════════════


-- ─── BLOCO 1 · CONFERÊNCIA (rode este primeiro; não muda nada) ───
select doc_id, nota_aplicabilidade, revista, titulo
from artigos
where doc_id in (
  '10.1016/j.cardfail.2025.05.019',   -- PRAISE-MR  · Design and Rationale
  '10.1016/j.cardfail.2025.06.009',   -- LEVEL      · Rationale and Design
  '10.1016/j.cardfail.2025.07.013'    -- KETO-AHF   · Rationale and Design
);
-- esperado: 3 linhas, todas do Journal of Cardiac Failure, todas com nota 8


-- ─── BLOCO 2 · APAGAR (só depois de conferir o bloco 1) ───
delete from artigos
where doc_id in (
  '10.1016/j.cardfail.2025.05.019',
  '10.1016/j.cardfail.2025.06.009',
  '10.1016/j.cardfail.2025.07.013'
);
-- esperado: "DELETE 3"


-- ─── BLOCO 3 · CONFERÊNCIA DEPOIS (deve devolver ZERO linhas) ───
select count(*) as ainda_no_banco
from artigos
where doc_id in (
  '10.1016/j.cardfail.2025.05.019',
  '10.1016/j.cardfail.2025.06.009',
  '10.1016/j.cardfail.2025.07.013'
);
-- esperado: 0


-- ─── BLOCO 4 · A REDE, para o futuro ───
-- Isto NÃO é para rodar agora: é para você usar daqui a um mês e conferir que a porta
-- continua fechada. Se voltar a devolver linha, o bloqueio do classificador furou.
select doc_id, nota_aplicabilidade, titulo
from artigos
where titulo ~* '(rationale and design|design and rationale|study protocol|statistical analysis plan|protocol for an? )';
-- esperado, para sempre: 0 linhas
