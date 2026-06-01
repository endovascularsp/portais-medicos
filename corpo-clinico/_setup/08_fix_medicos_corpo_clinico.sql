-- =====================================================================
-- FIX: tirar 'corpo_clinico' dos MÉDICOS
-- =====================================================================
-- Problema: 06_card_acesso.sql deu o card 'corpo_clinico' a TODOS os
-- usuários sem 'gestor' — incluindo os 14 médicos. No Gestor Hub, esse
-- card fica visível, então `visiveis !== 0` e o redirect automático pro
-- Hub individual do médico (role=medico + slug + medico_proprio) NÃO
-- dispara: o médico trava vendo só o card Corpo Clínico.
--
-- Regra de negócio: profissional só enxerga os portais próprios
-- (Recebimento / Produtividade / Insights, no Hub individual dele).
-- Corpo Clínico é card de gestão/recepção, não de médico.
--
-- Recepção/funcionários NÃO são afetados — mantêm 'corpo_clinico'.
-- Executar no Supabase SQL Editor.
-- =====================================================================

-- 1) DIAGNÓSTICO — rode primeiro e confira (slug preenchido? tem medico_proprio?)
SELECT email, name, role, slug, cards
FROM public.users
WHERE role = 'medico'
ORDER BY name;

-- 2) FIX — remove só 'corpo_clinico' dos médicos (idempotente)
UPDATE public.users
SET cards = array_remove(cards, 'corpo_clinico')
WHERE role = 'medico'
  AND cards @> ARRAY['corpo_clinico'];

-- 3) CONFERÊNCIA — nenhum médico deve mais ter 'corpo_clinico'
SELECT email, name, slug, cards
FROM public.users
WHERE role = 'medico'
ORDER BY name;
