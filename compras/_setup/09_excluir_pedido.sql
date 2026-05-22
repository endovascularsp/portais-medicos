-- =====================================================================
-- Permite excluir solicitações de compra
-- =====================================================================
-- Faltava a policy de DELETE em compras_solicitacoes (só tinha INSERT
-- e UPDATE). Os itens, anexos e histórico vão junto automaticamente
-- via ON DELETE CASCADE.
--
-- No portal, o botão "Excluir pedido" aparece só pra administradores
-- (card 'gestor') — ver renderAcoes() no kanban.
-- Executar no Supabase SQL Editor. Idempotente.
-- =====================================================================

DROP POLICY IF EXISTS "compras_delete_authenticated" ON compras_solicitacoes;
CREATE POLICY "compras_delete_authenticated" ON compras_solicitacoes
  FOR DELETE TO authenticated USING (true);
