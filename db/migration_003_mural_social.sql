-- Migration 003: Mural — reações, comentários, visualizações + exclusão só admin
-- 2026-07-17
-- Depende da migration_002 (tabela mural_avisos) e das funções has_card()/is_admin_user().

-- ============================================================
-- 0. Excluir aviso: agora SÓ admin (antes era autor ou admin)
-- ============================================================
DROP POLICY IF EXISTS "mural_delete" ON public.mural_avisos;
CREATE POLICY "mural_delete" ON public.mural_avisos
  FOR DELETE TO authenticated
  USING (public.is_admin_user());

-- ============================================================
-- 1. Reações (👍 ❤️ 🎉 👏 ✅) — uma de cada emoji por pessoa
-- ============================================================
CREATE TABLE IF NOT EXISTS public.mural_reacoes (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  aviso_id    uuid NOT NULL REFERENCES public.mural_avisos(id) ON DELETE CASCADE,
  emoji       text NOT NULL,
  autor_email text NOT NULL,
  autor_nome  text,
  created_at  timestamptz NOT NULL DEFAULT now(),
  UNIQUE (aviso_id, autor_email, emoji)
);
CREATE INDEX IF NOT EXISTS mural_reacoes_aviso_idx ON public.mural_reacoes(aviso_id);
ALTER TABLE public.mural_reacoes ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "mr_read" ON public.mural_reacoes;
CREATE POLICY "mr_read" ON public.mural_reacoes FOR SELECT TO authenticated
  USING (public.has_card('mural'));

DROP POLICY IF EXISTS "mr_insert" ON public.mural_reacoes;
CREATE POLICY "mr_insert" ON public.mural_reacoes FOR INSERT TO authenticated
  WITH CHECK (public.has_card('mural') AND autor_email = (auth.jwt() ->> 'email'));

DROP POLICY IF EXISTS "mr_delete" ON public.mural_reacoes;
CREATE POLICY "mr_delete" ON public.mural_reacoes FOR DELETE TO authenticated
  USING (autor_email = (auth.jwt() ->> 'email'));

-- ============================================================
-- 2. Comentários livres — autor do comentário ou admin apagam
-- ============================================================
CREATE TABLE IF NOT EXISTS public.mural_comentarios (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  aviso_id    uuid NOT NULL REFERENCES public.mural_avisos(id) ON DELETE CASCADE,
  corpo       text NOT NULL,
  autor_email text NOT NULL,
  autor_nome  text,
  created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS mural_comentarios_aviso_idx ON public.mural_comentarios(aviso_id, created_at);
ALTER TABLE public.mural_comentarios ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "mc_read" ON public.mural_comentarios;
CREATE POLICY "mc_read" ON public.mural_comentarios FOR SELECT TO authenticated
  USING (public.has_card('mural'));

DROP POLICY IF EXISTS "mc_insert" ON public.mural_comentarios;
CREATE POLICY "mc_insert" ON public.mural_comentarios FOR INSERT TO authenticated
  WITH CHECK (public.has_card('mural') AND autor_email = (auth.jwt() ->> 'email'));

DROP POLICY IF EXISTS "mc_delete" ON public.mural_comentarios;
CREATE POLICY "mc_delete" ON public.mural_comentarios FOR DELETE TO authenticated
  USING (autor_email = (auth.jwt() ->> 'email') OR public.is_admin_user());

-- ============================================================
-- 3. Visualizações (quem viu) — cada pessoa registra a própria;
--    só o AUTOR do aviso (ou admin) lê a lista de quem viu.
-- ============================================================
CREATE TABLE IF NOT EXISTS public.mural_visualizacoes (
  aviso_id     uuid NOT NULL REFERENCES public.mural_avisos(id) ON DELETE CASCADE,
  viewer_email text NOT NULL,
  viewer_nome  text,
  viewed_at    timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (aviso_id, viewer_email)
);
ALTER TABLE public.mural_visualizacoes ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "mv_insert" ON public.mural_visualizacoes;
CREATE POLICY "mv_insert" ON public.mural_visualizacoes FOR INSERT TO authenticated
  WITH CHECK (public.has_card('mural') AND viewer_email = (auth.jwt() ->> 'email'));

DROP POLICY IF EXISTS "mv_read" ON public.mural_visualizacoes;
CREATE POLICY "mv_read" ON public.mural_visualizacoes FOR SELECT TO authenticated
  USING (
    public.is_admin_user()
    OR EXISTS (
      SELECT 1 FROM public.mural_avisos a
      WHERE a.id = aviso_id AND a.autor_email = (auth.jwt() ->> 'email')
    )
  );
