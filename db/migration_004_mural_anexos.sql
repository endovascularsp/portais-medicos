-- Migration 004: Mural — anexo de arquivo por aviso
-- 2026-07-17
-- Segue o padrão do portal de Compras (bucket privado + URL assinada).
-- Depende da migration_002/003 e das funções has_card()/is_admin_user().

-- ============================================================
-- 1. Colunas de anexo no aviso (1 arquivo por aviso, opcional)
-- ============================================================
ALTER TABLE public.mural_avisos ADD COLUMN IF NOT EXISTS anexo_path text;
ALTER TABLE public.mural_avisos ADD COLUMN IF NOT EXISTS anexo_nome text;

-- ============================================================
-- 2. Bucket de storage (privado)
-- ============================================================
INSERT INTO storage.buckets (id, name, public)
  VALUES ('mural-anexos', 'mural-anexos', false)
  ON CONFLICT (id) DO NOTHING;

-- ============================================================
-- 3. Políticas de acesso ao bucket (storage.objects)
--    Ler/baixar e enviar: quem tem o card 'mural'. Apagar: só admin.
-- ============================================================
DROP POLICY IF EXISTS "mural_anexo_read" ON storage.objects;
CREATE POLICY "mural_anexo_read" ON storage.objects
  FOR SELECT TO authenticated
  USING (bucket_id = 'mural-anexos' AND public.has_card('mural'));

DROP POLICY IF EXISTS "mural_anexo_insert" ON storage.objects;
CREATE POLICY "mural_anexo_insert" ON storage.objects
  FOR INSERT TO authenticated
  WITH CHECK (bucket_id = 'mural-anexos' AND public.has_card('mural'));

DROP POLICY IF EXISTS "mural_anexo_delete" ON storage.objects;
CREATE POLICY "mural_anexo_delete" ON storage.objects
  FOR DELETE TO authenticated
  USING (bucket_id = 'mural-anexos' AND public.is_admin_user());
