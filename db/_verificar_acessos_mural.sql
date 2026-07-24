-- =====================================================================
-- VERIFICAÇÃO DE ACESSOS — Mural + Equipes
-- Rode no SQL Editor do Supabase. É tudo SELECT, não altera nada.
-- =====================================================================
-- Por que isso existe: o SQL Editor roda como service_role e IGNORA a RLS,
-- então não dá pra "sentir" a restrição rodando um SELECT lá. As queries
-- abaixo REPLICAM a regra de public.pode_ver_aviso() na mão, mostrando o
-- que cada pessoa enxergaria de verdade no portal.

-- ---------------------------------------------------------------------
-- 1. RAIO-X: quantos avisos cada pessoa enxerga, de quantos existem
--    Se todo mundo vê o total, ou não há aviso direcionado, ou a
--    restrição não está pegando.
-- ---------------------------------------------------------------------
SELECT
  u.name                                    AS pessoa,
  u.role                                    AS funcao,
  coalesce(d.nome, '⚠️ SEM EQUIPE')         AS equipe,
  count(a.id)                               AS ve,
  (SELECT count(*) FROM mural_avisos)       AS de_um_total_de,
  CASE
    WHEN u.role = 'admin' THEN 'admin — vê tudo por supervisão'
    WHEN d.slug IS NULL   THEN 'sem equipe — só recebe avisos "Todos"'
    ELSE 'restrito à equipe'
  END                                       AS motivo
FROM users u
LEFT JOIN compras_departamentos d ON d.id = u.departamento_id
LEFT JOIN mural_avisos a ON (
      u.role = 'admin'                                    -- admin vê tudo
   OR a.autor_email = u.email                             -- autor vê o próprio
   OR 'todos' = ANY(a.equipes)                            -- aviso geral
   OR (d.slug IS NOT NULL AND d.slug = ANY(a.equipes))    -- mesma equipe
)
WHERE 'mural' = ANY(u.cards) OR 'gestor' = ANY(u.cards)
GROUP BY u.name, u.role, d.nome, d.slug
ORDER BY count(a.id) DESC, u.name;

-- ---------------------------------------------------------------------
-- 2. Detalhe por aviso: quem exatamente recebe cada um
--    Use pra conferir um aviso específico que você publicou de teste.
-- ---------------------------------------------------------------------
SELECT
  a.titulo,
  a.equipes,
  count(u.email)                            AS pessoas_que_recebem,
  string_agg(u.name, ', ' ORDER BY u.name)  AS quem
FROM mural_avisos a
LEFT JOIN users u ON (
      ('mural' = ANY(u.cards) OR 'gestor' = ANY(u.cards))
  AND (
        u.role = 'admin'
     OR a.autor_email = u.email
     OR 'todos' = ANY(a.equipes)
     OR EXISTS (SELECT 1 FROM compras_departamentos d
                 WHERE d.id = u.departamento_id AND d.slug = ANY(a.equipes))
  )
)
GROUP BY a.id, a.titulo, a.equipes
ORDER BY a.created_at DESC;

-- ---------------------------------------------------------------------
-- 3. Pendências de cadastro — o que ainda precisa da sua mão
-- ---------------------------------------------------------------------
-- 3a. Tem o Mural mas está sem equipe (só recebe avisos "Todos"):
SELECT email, name, role FROM users
WHERE ('mural' = ANY(cards) OR 'gestor' = ANY(cards))
  AND departamento_id IS NULL
  AND role <> 'admin'
ORDER BY name;

-- 3b. Aponta pra equipe desativada (não deveria retornar nada):
SELECT u.email, u.name, d.nome AS equipe_inativa
FROM users u JOIN compras_departamentos d ON d.id = u.departamento_id
WHERE d.ativo = false;

-- 3c. Sobrou alguém com o role antigo (não deveria retornar nada):
SELECT email, name, role FROM users WHERE role = 'recepcao';

-- 3d. Avisos marcados com equipe que não existe mais no cadastro
--     (badge apareceria como slug cru no portal):
SELECT a.titulo, e AS equipe_orfa
FROM mural_avisos a, unnest(a.equipes) AS e
WHERE e <> 'todos'
  AND NOT EXISTS (SELECT 1 FROM compras_departamentos d WHERE d.slug = e);

-- ---------------------------------------------------------------------
-- 4. Distribuição geral do cadastro
-- ---------------------------------------------------------------------
SELECT
  coalesce(d.nome, '⚠️ SEM EQUIPE') AS equipe,
  count(*) FILTER (WHERE u.role = 'admin')       AS admins,
  count(*) FILTER (WHERE u.role = 'medico')      AS medicos,
  count(*) FILTER (WHERE u.role = 'funcionario') AS funcionarios,
  count(*)                                       AS total
FROM users u
LEFT JOIN compras_departamentos d ON d.id = u.departamento_id
GROUP BY d.nome
ORDER BY d.nome NULLS FIRST;
