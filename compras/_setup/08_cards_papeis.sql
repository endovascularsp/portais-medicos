-- =====================================================================
-- Atribuição de papéis no Portal Compras
-- =====================================================================
-- Angelina  → Compradora  (compras_compradora)
-- Micaele   → Financeiro  (compras_financeiro)
--
-- Aprovador: Thiago já aprova via card 'gestor' (a regra ehAprovador
-- aceita 'gestor'). Não precisa card extra. A regra automática por
-- valor (>R$2k) ficou pra depois.
--
-- CASE torna idempotente — rodar 2x não duplica o card.
-- =====================================================================

-- Angelina — Compradora
UPDATE users SET
  cards = CASE WHEN 'compras_compradora' = ANY(cards) THEN cards
               ELSE cards || ARRAY['compras_compradora'] END
WHERE email = 'angelina.lima@endovascularsp.com.br';

-- Micaele — Financeiro
UPDATE users SET
  cards = CASE WHEN 'compras_financeiro' = ANY(cards) THEN cards
               ELSE cards || ARRAY['compras_financeiro'] END
WHERE email = 'micaele.albuquerque@endovascularsp.com.br';
