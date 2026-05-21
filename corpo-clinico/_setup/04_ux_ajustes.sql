-- =====================================================================
-- Ajustes de UX — Portal Corpo Clínico
-- Executar no Supabase SQL Editor.
-- =====================================================================

-- 1) Padroniza a especialidade: "Cirurgiã/Cirurgião Vascular" tratados
--    como especialidades diferentes quebravam o filtro. Unifica em
--    "Cirurgia Vascular" (termo neutro).
UPDATE cc_profissionais
SET especialidade = 'Cirurgia Vascular'
WHERE lower(especialidade) IN ('cirurgiã vascular', 'cirurgião vascular', 'cirurgia vascular');

-- 2) Campo novo: quais convênios o profissional atende (texto livre).
--    O 'atende_convenio' (Sim/Não) continua; este detalha QUAIS.
ALTER TABLE cc_profissionais ADD COLUMN IF NOT EXISTS convenios TEXT;
