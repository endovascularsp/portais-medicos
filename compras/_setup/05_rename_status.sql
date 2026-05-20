-- =====================================================================
-- RENAME cruzado das etapas 1 e 3
-- =====================================================================
-- Antes:
--   1 = compras_pendentes    (era a etapa "recém-criada")
--   3 = compra_aprovada      (era "Compra Aprovada")
--
-- Depois:
--   1 = pedido_feito         (renomeado da antiga "compras_pendentes")
--   3 = compras_pendentes    (renomeado da antiga "compra_aprovada")
--
-- A ordem importa: primeiro libera o nome 'compras_pendentes' (passo 1),
-- depois rebatiza compra_aprovada com esse nome (passo 2).
-- Também atualiza o default da coluna status.
-- =====================================================================

-- Passo 1: libera o nome 'compras_pendentes' renomeando a etapa 1
ALTER TYPE compras_status RENAME VALUE 'compras_pendentes' TO 'pedido_feito';

-- Passo 2: a etapa 3 herda o nome 'compras_pendentes'
ALTER TYPE compras_status RENAME VALUE 'compra_aprovada' TO 'compras_pendentes';

-- Passo 3: atualiza o default da coluna status pra refletir o novo nome
ALTER TABLE compras_solicitacoes ALTER COLUMN status SET DEFAULT 'pedido_feito';
