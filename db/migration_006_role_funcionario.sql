-- Migration 006: role 'recepcao' → 'funcionario'
-- 2026-07-24
--
-- MOTIVO
-- `users.role` e `users.departamento_id` (equipe) medem coisas diferentes:
--   role   = o que a pessoa PODE FAZER (nível de poder no sistema)
--   equipe = ONDE ela trabalha (segmentação de conteúdo, ver migration_005)
-- Os dois precisam existir. O problema era o NOME de um dos roles: 'recepcao'
-- na verdade significa "funcionário comum, sem poder especial" — não tem
-- relação com a equipe Recepção. Exemplos do próprio banco:
--   Aluma Alves    role='recepcao'  equipe=Faturamento
--   Camilla Gomes  role='recepcao'  equipe=Enfermagem
--   conta Marketing role='recepcao' equipe=Marketing
-- Depois da migration_005 (que criou a equipe Recepção de verdade) isso virou
-- contradição na tela do Gestão de Acessos.
--
-- SEGURANÇA DA MUDANÇA
-- O valor 'recepcao' não é testado em NENHUM lugar do código — só 'admin'
-- (is_admin_user / RLS) e 'medico' (roteamento de login, slug) têm efeito
-- funcional. Renomear não altera nenhum comportamento.

-- ============================================================
-- 1. Afrouxa o constraint pra aceitar os dois durante a troca
-- ============================================================
ALTER TABLE public.users DROP CONSTRAINT IF EXISTS users_role_check;
ALTER TABLE public.users ADD CONSTRAINT users_role_check
  CHECK (role IN ('admin', 'medico', 'recepcao', 'funcionario'));

-- ============================================================
-- 2. Renomeia
-- ============================================================
UPDATE public.users SET role = 'funcionario' WHERE role = 'recepcao';

-- ============================================================
-- 3. Fecha o constraint — 'recepcao' deixa de ser aceito
-- ============================================================
ALTER TABLE public.users DROP CONSTRAINT IF EXISTS users_role_check;
ALTER TABLE public.users ADD CONSTRAINT users_role_check
  CHECK (role IN ('admin', 'medico', 'funcionario'));

-- ============================================================
-- 4. Conferência — rode depois e leia o resultado
-- ============================================================
-- Não pode sobrar ninguém com 'recepcao' (deve voltar 0 linhas):
--   SELECT email, name, role FROM users WHERE role = 'recepcao';
--
-- Distribuição final por função e equipe:
--   SELECT u.role, d.nome AS equipe, count(*)
--     FROM users u LEFT JOIN compras_departamentos d ON d.id = u.departamento_id
--    GROUP BY u.role, d.nome ORDER BY u.role, d.nome;
