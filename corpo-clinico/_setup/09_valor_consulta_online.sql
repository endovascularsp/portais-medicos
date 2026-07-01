-- =====================================================================
-- 09 — Valor de consulta on-line
-- Adiciona a coluna valor_consulta_online em cc_profissionais para
-- diferenciar o valor da consulta on-line do valor presencial
-- (valor_consulta), já que nem sempre são iguais.
-- Executar no Supabase SQL Editor (projeto egpcrqrvctnpxbdjdhtf).
-- Idempotente (IF NOT EXISTS).
-- =====================================================================

ALTER TABLE cc_profissionais
  ADD COLUMN IF NOT EXISTS valor_consulta_online NUMERIC(10,2);
