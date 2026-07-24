-- Migration 005: Equipes — cadastro único + visibilidade restrita por equipe no Mural
-- 2026-07-24
--
-- CONTEXTO
-- Até aqui, `mural_avisos.equipes[]` era só uma ETIQUETA: a policy `mural_read`
-- liberava todo aviso pra qualquer um com o card 'mural'. O chip de equipe
-- filtrava a tela, mas qualquer pessoa via qualquer aviso.
--
-- Esta migration:
--   1. Promove `compras_departamentos` a tabela ÚNICA de equipes (ganha `slug`).
--      Continua sendo a mesma tabela que o Portal Compras usa pra rotear aprovação —
--      de propósito: um funcionário tem UMA equipe, não uma equipe e um departamento.
--   2. Consolida "Gestão" em "Administrativo" e cria "Médicos".
--   3. Passa a RESTRINGIR de verdade a leitura do Mural, na RLS (servidor),
--      não só escondendo na tela.
--
-- Depende de: migration_001 (has_card/is_admin_user), migration_002/003 (mural),
--             compras/_setup/01_schema.sql (compras_departamentos + users.departamento_id).

-- ============================================================
-- 1. slug nas equipes
-- ============================================================
ALTER TABLE public.compras_departamentos ADD COLUMN IF NOT EXISTS slug text;

UPDATE public.compras_departamentos SET slug = v.slug
FROM (VALUES
  ('Recepção',       'recepcao'),
  ('Agendamento',    'agendamento'),
  ('Concierge',      'concierge'),
  ('Enfermagem',     'enfermagem'),
  ('Cirurgias',      'cirurgias'),
  ('Administrativo', 'administrativo'),
  ('Financeiro',     'financeiro'),
  ('Faturamento',    'faturamento'),
  ('Marketing',      'marketing'),
  ('Gestão',         'gestao')
) AS v(nome, slug)
WHERE compras_departamentos.nome = v.nome
  AND compras_departamentos.slug IS DISTINCT FROM v.slug;

-- Equipe nova: Médicos (só registro por enquanto — acesso continua sendo o card 'mural')
INSERT INTO public.compras_departamentos (nome, slug)
VALUES ('Médicos', 'medicos')
ON CONFLICT (nome) DO UPDATE SET slug = EXCLUDED.slug;

-- Qualquer departamento que exista no banco e não esteja na lista acima ganha
-- um slug derivado do nome — assim ninguém fica sem equipe por descuido.
UPDATE public.compras_departamentos
SET slug = regexp_replace(
      lower(translate(nome,
        'ÁÀÂÃÄÉÈÊËÍÌÎÏÓÒÔÕÖÚÙÛÜÇáàâãäéèêëíìîïóòôõöúùûüç',
        'AAAAAEEEEIIIIOOOOOUUUUCaaaaaeeeeiiiiooooouuuuc')),
      '[^a-z0-9]+', '_', 'g')
WHERE slug IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS compras_departamentos_slug_idx
  ON public.compras_departamentos (slug);

-- ============================================================
-- 2. Consolidação: "Gestão" vira "Administrativo"
--    (decisão de 24/07/2026 — Adriana, Heloisa, Dr. Igor, Thiago)
--    Os históricos de compras_solicitacoes continuam apontando pra Gestão;
--    por isso a equipe é DESATIVADA, nunca apagada (a FK quebraria).
-- ============================================================
UPDATE public.users
SET departamento_id = (SELECT id FROM public.compras_departamentos WHERE nome = 'Administrativo')
WHERE departamento_id = (SELECT id FROM public.compras_departamentos WHERE nome = 'Gestão');

-- Se "Gestão" tinha aprovador de compras próprio e "Administrativo" não tem,
-- herda o aprovador pra ninguém ficar sem rota de aprovação.
UPDATE public.compras_departamentos adm
SET gestor_email = ges.gestor_email
FROM public.compras_departamentos ges
WHERE adm.nome = 'Administrativo'
  AND ges.nome = 'Gestão'
  AND adm.gestor_email IS NULL
  AND ges.gestor_email IS NOT NULL;

UPDATE public.compras_departamentos SET ativo = false WHERE nome = 'Gestão';

-- ============================================================
-- 3. Médicos sem equipe entram na equipe "Médicos" (só registro)
-- ============================================================
UPDATE public.users
SET departamento_id = (SELECT id FROM public.compras_departamentos WHERE nome = 'Médicos')
WHERE role = 'medico' AND departamento_id IS NULL;

-- ============================================================
-- 4. De-para nos avisos já publicados
--    A equipe 'atendimento' do Mural antigo não existe no cadastro;
--    o time correspondente é Agendamento (Mayara / Ana Luiza).
-- ============================================================
UPDATE public.mural_avisos
SET equipes = array_replace(equipes, 'atendimento', 'agendamento')
WHERE 'atendimento' = ANY(equipes);

-- ============================================================
-- 5. Helpers de equipe
-- ============================================================
-- Slug da equipe do usuário logado (NULL se ele não tiver equipe no cadastro).
CREATE OR REPLACE FUNCTION public.minha_equipe() RETURNS text
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = public
AS $$
  SELECT d.slug
  FROM users u
  JOIN compras_departamentos d ON d.id = u.departamento_id
  WHERE u.email = (auth.jwt() ->> 'email')
  LIMIT 1
$$;

-- Regra de visibilidade de um aviso. Vê quem:
--   - é admin (supervisão: admin já fixa e apaga qualquer aviso); ou
--   - escreveu o aviso (senão você publica pra Enfermagem e some da sua tela); ou
--   - o aviso é pra 'todos'; ou
--   - é da equipe marcada no aviso.
-- Quem está SEM equipe no cadastro só enxerga os avisos 'todos'.
CREATE OR REPLACE FUNCTION public.pode_ver_aviso(eqs text[], autor text) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = public
AS $$
  SELECT public.is_admin_user()
      OR autor = (auth.jwt() ->> 'email')
      OR 'todos' = ANY(eqs)
      OR (public.minha_equipe() IS NOT NULL AND public.minha_equipe() = ANY(eqs))
$$;

-- ============================================================
-- 6. RLS — a restrição de verdade
-- ============================================================
DROP POLICY IF EXISTS "mural_read" ON public.mural_avisos;
CREATE POLICY "mural_read" ON public.mural_avisos
  FOR SELECT TO authenticated
  USING (public.has_card('mural') AND public.pode_ver_aviso(equipes, autor_email));

-- Publicar segue liberado pra qualquer equipe (o Administrativo precisa poder
-- avisar a Enfermagem). Só a LEITURA é restrita.

-- Reações, comentários e visualizações herdam a visibilidade do aviso:
-- o EXISTS abaixo passa pela policy mural_read, então quem não vê o aviso
-- não vê nem reação, nem comentário, nem quem visualizou.
DROP POLICY IF EXISTS "mr_read" ON public.mural_reacoes;
CREATE POLICY "mr_read" ON public.mural_reacoes FOR SELECT TO authenticated
  USING (EXISTS (SELECT 1 FROM public.mural_avisos a WHERE a.id = aviso_id));

DROP POLICY IF EXISTS "mr_insert" ON public.mural_reacoes;
CREATE POLICY "mr_insert" ON public.mural_reacoes FOR INSERT TO authenticated
  WITH CHECK (
    autor_email = (auth.jwt() ->> 'email')
    AND EXISTS (SELECT 1 FROM public.mural_avisos a WHERE a.id = aviso_id)
  );

DROP POLICY IF EXISTS "mc_read" ON public.mural_comentarios;
CREATE POLICY "mc_read" ON public.mural_comentarios FOR SELECT TO authenticated
  USING (EXISTS (SELECT 1 FROM public.mural_avisos a WHERE a.id = aviso_id));

DROP POLICY IF EXISTS "mc_insert" ON public.mural_comentarios;
CREATE POLICY "mc_insert" ON public.mural_comentarios FOR INSERT TO authenticated
  WITH CHECK (
    autor_email = (auth.jwt() ->> 'email')
    AND EXISTS (SELECT 1 FROM public.mural_avisos a WHERE a.id = aviso_id)
  );

DROP POLICY IF EXISTS "mv_insert" ON public.mural_visualizacoes;
CREATE POLICY "mv_insert" ON public.mural_visualizacoes FOR INSERT TO authenticated
  WITH CHECK (
    viewer_email = (auth.jwt() ->> 'email')
    AND EXISTS (SELECT 1 FROM public.mural_avisos a WHERE a.id = aviso_id)
  );

-- ============================================================
-- 7. Conferência — rode depois e leia o resultado
-- ============================================================
-- Equipes ativas (deve listar as 10; 'Gestão' NÃO deve aparecer):
--   SELECT nome, slug, ativo FROM compras_departamentos ORDER BY ativo DESC, nome;
--
-- Gente sem equipe (essas pessoas só vão ver avisos 'Todos'):
--   SELECT email, name, role FROM users WHERE departamento_id IS NULL ORDER BY role, name;
--
-- Quantas pessoas por equipe:
--   SELECT d.nome, count(u.email) FROM compras_departamentos d
--     LEFT JOIN users u ON u.departamento_id = d.id
--     WHERE d.ativo GROUP BY d.nome ORDER BY d.nome;
