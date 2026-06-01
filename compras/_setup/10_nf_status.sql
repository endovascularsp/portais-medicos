-- =====================================================================
-- Status da Nota Fiscal por solicitação
-- =====================================================================
-- A Recepção precisa saber como a NF vai chegar quando recebe o material:
--   pendente — ainda não chegou (nem impressa nem por e-mail)
--   parcial  — chegou parte (ex.: compra no Mercado Livre com vários
--              fornecedores, NFs chegam aos poucos)
--   completa — todas as NFs já chegaram
--
-- Campo disponível em qualquer etapa do Kanban. Default 'pendente'.
-- Executar no Supabase SQL Editor ANTES de subir o HTML novo do Kanban
-- (a query do portal passa a selecionar nf_status). Idempotente.
-- =====================================================================

DO $$ BEGIN
  CREATE TYPE compras_nf_status AS ENUM ('pendente', 'parcial', 'completa');
EXCEPTION WHEN duplicate_object THEN null; END $$;

ALTER TABLE compras_solicitacoes
  ADD COLUMN IF NOT EXISTS nf_status compras_nf_status NOT NULL DEFAULT 'pendente';
