-- Migration 002: Mural de Avisos
-- 2026-07-17
-- Card novo "Mural de Avisos" (data-card = 'mural') no Gestor Hub.
-- Todos os funcionários NÃO-médicos com o card publicam e leem; publica na hora.
-- Cada aviso é marcado para 1+ equipes (recepcao, atendimento, enfermagem,
-- concierge, administrativo) ou 'todos'.
-- Reaproveita as funções public.has_card(text) e public.is_admin_user()
-- criadas na migration_001_users_cards.sql.

-- ============================================================
-- 1. Tabela dos avisos
-- ============================================================
CREATE TABLE IF NOT EXISTS public.mural_avisos (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  titulo      text NOT NULL,
  corpo       text NOT NULL,
  equipes     text[] NOT NULL DEFAULT '{}',   -- ['todos'] ou combinação de recepcao/atendimento/enfermagem/concierge/administrativo
  autor_email text NOT NULL,
  autor_nome  text,
  fixado      boolean NOT NULL DEFAULT false,  -- avisos fixados aparecem no topo (só admin fixa pela UI)
  created_at  timestamptz NOT NULL DEFAULT now()
);

-- Ordena o feed: fixados primeiro, depois mais recentes.
CREATE INDEX IF NOT EXISTS mural_avisos_ordem_idx
  ON public.mural_avisos (fixado DESC, created_at DESC);

-- ============================================================
-- 2. RLS — quem tem o card 'mural' lê e publica; autor/admin editam e apagam
-- ============================================================
ALTER TABLE public.mural_avisos ENABLE ROW LEVEL SECURITY;

-- Ler: qualquer usuário autenticado com o card 'mural'
DROP POLICY IF EXISTS "mural_read" ON public.mural_avisos;
CREATE POLICY "mural_read" ON public.mural_avisos
  FOR SELECT TO authenticated
  USING (public.has_card('mural'));

-- Publicar: quem tem o card 'mural' e assina o aviso com o próprio email
DROP POLICY IF EXISTS "mural_insert" ON public.mural_avisos;
CREATE POLICY "mural_insert" ON public.mural_avisos
  FOR INSERT TO authenticated
  WITH CHECK (public.has_card('mural') AND autor_email = (auth.jwt() ->> 'email'));

-- Editar: o próprio autor OU um admin
DROP POLICY IF EXISTS "mural_update" ON public.mural_avisos;
CREATE POLICY "mural_update" ON public.mural_avisos
  FOR UPDATE TO authenticated
  USING (autor_email = (auth.jwt() ->> 'email') OR public.is_admin_user())
  WITH CHECK (autor_email = (auth.jwt() ->> 'email') OR public.is_admin_user());

-- Apagar: o próprio autor OU um admin
DROP POLICY IF EXISTS "mural_delete" ON public.mural_avisos;
CREATE POLICY "mural_delete" ON public.mural_avisos
  FOR DELETE TO authenticated
  USING (autor_email = (auth.jwt() ->> 'email') OR public.is_admin_user());

-- ============================================================
-- 3. Concede o card 'mural' a quem já deve publicar/ler no lançamento
--    (todos os NÃO-médicos já cadastrados). Ajuste depois pela Gestão de Acessos.
-- ============================================================
UPDATE public.users
  SET cards = array_append(cards, 'mural')
  WHERE role <> 'medico'
    AND NOT ('mural' = ANY(cards));
