-- =====================================================================
-- REFACTOR: fluxo de 4 etapas → 7 etapas
-- =====================================================================
-- ⚠️ ATENÇÃO: este SQL APAGA todas as solicitações de teste (e itens,
-- anexos, histórico relacionados). Use só se confirmar que não há
-- dados reais ainda. Confirmado em 2026-05-20 (Thiago).
--
-- Novo fluxo:
--   1. compras_pendentes      — recém-criada, Compradora vai triar
--   2. aguardando_aprovacao   — Compradora moveu pra você aprovar
--   3. compra_aprovada        — você aprovou, Compradora vai comprar
--   4. compra_realizada       — Compradora comprou, Financeiro vai lançar no Conta Azul
--   5. inclusao_conta_azul    — Financeiro lançou, aguardando produto chegar
--   6. recebimento            — produto chegou, Compradora vai encerrar
--   7. concluida              — fluxo encerrado
--
-- + recusada (estado paralelo a qualquer etapa)
-- =====================================================================

-- 1) Limpa dados de teste (cascade derruba itens, anexos, historico)
TRUNCATE compras_historico, compras_anexos, compras_itens, compras_solicitacoes
  RESTART IDENTITY CASCADE;

-- 2) Troca o ENUM da coluna status pra TEXT temporariamente
ALTER TABLE compras_solicitacoes ALTER COLUMN status DROP DEFAULT;
ALTER TABLE compras_solicitacoes ALTER COLUMN status TYPE TEXT;

-- 3) Drop do ENUM antigo (sem dados, é seguro)
DROP TYPE IF EXISTS compras_status CASCADE;

-- 4) Cria ENUM novo com 7 etapas + recusada
CREATE TYPE compras_status AS ENUM (
  'compras_pendentes',
  'aguardando_aprovacao',
  'compra_aprovada',
  'compra_realizada',
  'inclusao_conta_azul',
  'recebimento',
  'concluida',
  'recusada'
);

-- 5) Volta a coluna pro ENUM novo, com default 'compras_pendentes'
ALTER TABLE compras_solicitacoes ALTER COLUMN status TYPE compras_status USING status::compras_status;
ALTER TABLE compras_solicitacoes ALTER COLUMN status SET DEFAULT 'compras_pendentes';

-- 6) Renomeia/adiciona campos pros marcos do novo fluxo
ALTER TABLE compras_solicitacoes
  RENAME COLUMN pago_em TO encerrado_em;
ALTER TABLE compras_solicitacoes
  RENAME COLUMN pago_por TO encerrado_por;

ALTER TABLE compras_solicitacoes
  ADD COLUMN IF NOT EXISTS encaminhado_aprovacao_em TIMESTAMPTZ;
ALTER TABLE compras_solicitacoes
  ADD COLUMN IF NOT EXISTS conta_azul_em TIMESTAMPTZ;
ALTER TABLE compras_solicitacoes
  ADD COLUMN IF NOT EXISTS conta_azul_por TEXT;
ALTER TABLE compras_solicitacoes
  ADD COLUMN IF NOT EXISTS conta_azul_ref TEXT;
ALTER TABLE compras_solicitacoes
  ADD COLUMN IF NOT EXISTS recebido_em TIMESTAMPTZ;
ALTER TABLE compras_solicitacoes
  ADD COLUMN IF NOT EXISTS recebido_por TEXT;

-- 7) Atualiza índice por status
DROP INDEX IF EXISTS idx_solic_status;
CREATE INDEX idx_solic_status ON compras_solicitacoes (status);
