-- Seed 012: as regras de cirurgia valem também para a Oxy Recovery
-- 2026-08-04
--
-- CONTEXTO
-- O Manual de Regras de Repasse v1.0 só definia cirurgia para a Endovascular SP,
-- e a migration_009 seedou só as linhas dessa empresa. Em Julho/2026 apareceram
-- duas cirurgias da Christiane na Oxy — Endolift (Cirurgia - Clínica) e Morpheus
-- (Cirurgia - Hospital). O motor já calculou certo, porque as regras de cirurgia
-- não olham a empresa; faltava a tabela `honorarios_regras` refletir isso.
--
-- Thiago em 04/08/2026: "foi a exceção da exceção, mas vimos que pode acontecer" —
-- mesmas regras da Endovascular.
--
-- Rodar DEPOIS de migration_009.

INSERT INTO public.honorarios_regras (empresa, categoria, profissional, percentual, observacao) VALUES
  ('Oxy Recovery', 'Cirurgia - Clínica',  NULL, 0.80,
   'Regra 2 — cirurgia feita na clínica. Raro na Oxy, mas acontece (Endolift, Jul/2026)'),
  ('Oxy Recovery', 'Cirurgia - Hospital', NULL, 0.85,
   'Regra 1 — SÓ quando a Tabela é plano de saúde. Particular vira 80% ou 90% conforme a origem do lead')
ON CONFLICT DO NOTHING;

-- Conferência: as regras de cirurgia devem aparecer para as duas empresas.
-- SELECT empresa, categoria, percentual, observacao
--   FROM public.honorarios_regras
--  WHERE categoria LIKE 'Cirurgia%'
--  ORDER BY empresa, categoria;
