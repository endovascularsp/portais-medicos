-- =====================================================================
-- RLS Policies — INSERT/UPDATE pra Portal Compras
-- =====================================================================
-- Executar APOS 01_schema.sql e 02_seed.sql.
-- Define quem pode criar/editar registros via Supabase.
--
-- Estratégia MVP: liberal pra authenticated. Validação fina fica no
-- frontend. Refinamos quando tivermos uso real e RLS por papel.
-- =====================================================================

-- Solicitações: authenticated pode INSERT e UPDATE
CREATE POLICY "compras_insert_authenticated" ON compras_solicitacoes
  FOR INSERT TO authenticated WITH CHECK (true);
CREATE POLICY "compras_update_authenticated" ON compras_solicitacoes
  FOR UPDATE TO authenticated USING (true) WITH CHECK (true);

-- Itens: authenticated INSERT/UPDATE/DELETE
CREATE POLICY "compras_insert_authenticated" ON compras_itens
  FOR INSERT TO authenticated WITH CHECK (true);
CREATE POLICY "compras_update_authenticated" ON compras_itens
  FOR UPDATE TO authenticated USING (true) WITH CHECK (true);
CREATE POLICY "compras_delete_authenticated" ON compras_itens
  FOR DELETE TO authenticated USING (true);

-- Anexos: authenticated INSERT/UPDATE/DELETE
CREATE POLICY "compras_insert_authenticated" ON compras_anexos
  FOR INSERT TO authenticated WITH CHECK (true);
CREATE POLICY "compras_update_authenticated" ON compras_anexos
  FOR UPDATE TO authenticated USING (true) WITH CHECK (true);
CREATE POLICY "compras_delete_authenticated" ON compras_anexos
  FOR DELETE TO authenticated USING (true);

-- Histórico: authenticated INSERT (não atualiza nem deleta)
CREATE POLICY "compras_insert_authenticated" ON compras_historico
  FOR INSERT TO authenticated WITH CHECK (true);

-- Fornecedores: authenticated INSERT (pra cadastro 'na hora')
-- UPDATE só admin (refinar depois)
CREATE POLICY "compras_insert_authenticated" ON compras_fornecedores
  FOR INSERT TO authenticated WITH CHECK (true);
CREATE POLICY "compras_update_authenticated" ON compras_fornecedores
  FOR UPDATE TO authenticated USING (true) WITH CHECK (true);

-- Departamentos e Centros de Custo: só admin altera (apenas SELECT pra authenticated, já no schema)
-- (não precisa nova policy)

-- =====================================================================
-- Supabase Storage: bucket 'compras-anexos'
-- =====================================================================
-- IMPORTANTE: criar manualmente no painel do Supabase
--   Storage → New bucket → nome: 'compras-anexos', Public: NO
--
-- Depois roda este SQL pra liberar upload/download pra authenticated:

INSERT INTO storage.buckets (id, name, public)
  VALUES ('compras-anexos', 'compras-anexos', false)
  ON CONFLICT (id) DO NOTHING;

CREATE POLICY "compras_anexos_upload" ON storage.objects
  FOR INSERT TO authenticated
  WITH CHECK (bucket_id = 'compras-anexos');

CREATE POLICY "compras_anexos_read" ON storage.objects
  FOR SELECT TO authenticated
  USING (bucket_id = 'compras-anexos');

CREATE POLICY "compras_anexos_delete" ON storage.objects
  FOR DELETE TO authenticated
  USING (bucket_id = 'compras-anexos');
