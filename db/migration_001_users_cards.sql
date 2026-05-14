-- Migration 001: Acrescenta granularidade de acessos via campo cards[]
-- 2026-05-14
-- Compatível com a tabela public.users existente (email, name, role, slug, created_at).

-- ============================================================
-- 1. Adiciona coluna cards (lista de cards/portais permitidos)
-- ============================================================
ALTER TABLE public.users ADD COLUMN IF NOT EXISTS cards text[] NOT NULL DEFAULT '{}';

-- ============================================================
-- 2. Popula os 2 admins atuais
-- ============================================================
UPDATE public.users SET cards = ARRAY['gestor', 'atendimentos', 'previas', 'medico_proprio']
WHERE email = 'drigor@endovascularsp.com.br';

UPDATE public.users SET cards = ARRAY['gestor', 'atendimentos', 'previas']
WHERE email = 'thiago.luiz@endovascularsp.com.br';

-- ============================================================
-- 3. Popula os 14 médicos (medico_proprio = vêem o próprio portal)
-- ============================================================
UPDATE public.users SET cards = ARRAY['medico_proprio']
WHERE role = 'medico' AND (cards IS NULL OR cardinality(cards) = 0);

-- ============================================================
-- 4. Cadastra usuários novos: Sol (Atendimentos) + Recepção (Prévias)
-- ============================================================
INSERT INTO public.users (email, name, role, cards) VALUES
  ('solange.lucindo@endovascularsp.com.br',    'Solange Lucindo',    'recepcao', ARRAY['atendimentos']),
  ('camily.nascimento@endovascularsp.com.br',  'Camily Nascimento',  'recepcao', ARRAY['previas']),
  ('samanta.neves@endovascularsp.com.br',      'Samanta Neves',      'recepcao', ARRAY['previas']),
  ('julia.beserra@endovascularsp.com.br',      'Julia Beserra',      'recepcao', ARRAY['previas'])
ON CONFLICT (email) DO UPDATE SET
  name = EXCLUDED.name,
  role = EXCLUDED.role,
  cards = EXCLUDED.cards;

-- ============================================================
-- 5. Funções helper pra usar nas RLS dos vários portais
-- ============================================================
CREATE OR REPLACE FUNCTION public.has_card(card_name text) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = public
AS $$
  SELECT EXISTS (
    SELECT 1 FROM users
    WHERE email = (auth.jwt() ->> 'email')
      AND card_name = ANY(cards)
  )
$$;

CREATE OR REPLACE FUNCTION public.is_admin_user() RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = public
AS $$
  SELECT EXISTS (
    SELECT 1 FROM users
    WHERE email = (auth.jwt() ->> 'email')
      AND role = 'admin'
  )
$$;

-- ============================================================
-- 6. RLS: user lê própria linha; admin lê/edita todas
-- ============================================================
ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "users_read_self" ON public.users;
CREATE POLICY "users_read_self" ON public.users
  FOR SELECT TO authenticated
  USING (email = (auth.jwt() ->> 'email'));

DROP POLICY IF EXISTS "users_admin_all" ON public.users;
CREATE POLICY "users_admin_all" ON public.users
  FOR ALL TO authenticated
  USING (public.is_admin_user())
  WITH CHECK (public.is_admin_user());
