-- =====================================================================
-- CORREÇÃO — permissões de escrita (RLS) das tabelas do Corpo Clínico
-- =====================================================================
-- Sintoma: editar profissional ou escala no portal mostra "salvo com
-- sucesso", mas a mudança não persiste. Causa: RLS ligado sem as
-- policies de INSERT/UPDATE/DELETE — o Supabase bloqueia a gravação
-- silenciosamente (não retorna erro em UPDATE/DELETE).
--
-- Este script recria, do zero, TODAS as policies das 3 tabelas cc_.
-- Idempotente: pode rodar quantas vezes quiser (DROP antes de criar).
-- Executar no Supabase SQL Editor.
-- =====================================================================

-- ---- cc_salas ----
ALTER TABLE cc_salas ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "cc_sel" ON cc_salas;
DROP POLICY IF EXISTS "cc_ins" ON cc_salas;
DROP POLICY IF EXISTS "cc_upd" ON cc_salas;
DROP POLICY IF EXISTS "cc_del" ON cc_salas;
CREATE POLICY "cc_sel" ON cc_salas FOR SELECT TO authenticated USING (true);
CREATE POLICY "cc_ins" ON cc_salas FOR INSERT TO authenticated WITH CHECK (true);
CREATE POLICY "cc_upd" ON cc_salas FOR UPDATE TO authenticated USING (true) WITH CHECK (true);
CREATE POLICY "cc_del" ON cc_salas FOR DELETE TO authenticated USING (true);

-- ---- cc_profissionais ----
ALTER TABLE cc_profissionais ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "cc_sel" ON cc_profissionais;
DROP POLICY IF EXISTS "cc_ins" ON cc_profissionais;
DROP POLICY IF EXISTS "cc_upd" ON cc_profissionais;
DROP POLICY IF EXISTS "cc_del" ON cc_profissionais;
CREATE POLICY "cc_sel" ON cc_profissionais FOR SELECT TO authenticated USING (true);
CREATE POLICY "cc_ins" ON cc_profissionais FOR INSERT TO authenticated WITH CHECK (true);
CREATE POLICY "cc_upd" ON cc_profissionais FOR UPDATE TO authenticated USING (true) WITH CHECK (true);
CREATE POLICY "cc_del" ON cc_profissionais FOR DELETE TO authenticated USING (true);

-- ---- cc_escala ----
ALTER TABLE cc_escala ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "cc_sel" ON cc_escala;
DROP POLICY IF EXISTS "cc_ins" ON cc_escala;
DROP POLICY IF EXISTS "cc_upd" ON cc_escala;
DROP POLICY IF EXISTS "cc_del" ON cc_escala;
CREATE POLICY "cc_sel" ON cc_escala FOR SELECT TO authenticated USING (true);
CREATE POLICY "cc_ins" ON cc_escala FOR INSERT TO authenticated WITH CHECK (true);
CREATE POLICY "cc_upd" ON cc_escala FOR UPDATE TO authenticated USING (true) WITH CHECK (true);
CREATE POLICY "cc_del" ON cc_escala FOR DELETE TO authenticated USING (true);

-- Conferência — deve listar 12 policies (4 por tabela):
SELECT tablename, policyname, cmd
FROM pg_policies
WHERE tablename IN ('cc_salas','cc_profissionais','cc_escala')
ORDER BY tablename, cmd;
