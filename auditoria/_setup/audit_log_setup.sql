-- =====================================================================
-- AUDITORIA DE ACOES — Portal Endovascular SP
-- =====================================================================
-- O que faz:
--   Captura INSERT / UPDATE / DELETE em 21 tabelas sensiveis, com:
--   - quem fez (email + user_id via auth)
--   - quando (timestamp)
--   - o que (tabela + operacao + id do registro)
--   - estado antes (JSONB - so em UPDATE/DELETE)
--   - estado depois (JSONB - so em INSERT/UPDATE)
--
-- Como rodar:
--   Cole TUDO no Supabase SQL Editor e rode.
--   Idempotente: pode re-rodar sem problema (usa IF NOT EXISTS,
--   DROP TRIGGER IF EXISTS, CREATE OR REPLACE).
--
-- Como consultar (depois de rodar):
--   SELECT * FROM audit_log
--    WHERE tabela = 'users' AND operacao = 'DELETE'
--    ORDER BY criado_em DESC LIMIT 50;
--
-- Como arquivar (rotina mensal):
--   SELECT arquivar_audit_log();
-- =====================================================================


-- =====================================================================
-- 1. Tabelas: audit_log + audit_log_archive
-- =====================================================================

CREATE TABLE IF NOT EXISTS audit_log (
  id            BIGSERIAL PRIMARY KEY,
  tabela        TEXT NOT NULL,
  operacao      TEXT NOT NULL CHECK (operacao IN ('INSERT','UPDATE','DELETE')),
  registro_id   TEXT,
  por_email     TEXT,
  por_user_id   UUID,
  dados_antes   JSONB,
  dados_depois  JSONB,
  criado_em     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_log_criado     ON audit_log (criado_em DESC);
CREATE INDEX IF NOT EXISTS idx_audit_log_tabela     ON audit_log (tabela, criado_em DESC);
CREATE INDEX IF NOT EXISTS idx_audit_log_email      ON audit_log (por_email, criado_em DESC);
CREATE INDEX IF NOT EXISTS idx_audit_log_operacao   ON audit_log (operacao, criado_em DESC);
CREATE INDEX IF NOT EXISTS idx_audit_log_registro   ON audit_log (tabela, registro_id);

-- Tabela de arquivamento (mesma estrutura)
CREATE TABLE IF NOT EXISTS audit_log_archive (
  id            BIGINT PRIMARY KEY,
  tabela        TEXT NOT NULL,
  operacao      TEXT NOT NULL,
  registro_id   TEXT,
  por_email     TEXT,
  por_user_id   UUID,
  dados_antes   JSONB,
  dados_depois  JSONB,
  criado_em     TIMESTAMPTZ NOT NULL,
  arquivado_em  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_archive_criado ON audit_log_archive (criado_em DESC);
CREATE INDEX IF NOT EXISTS idx_audit_archive_tabela ON audit_log_archive (tabela, criado_em DESC);


-- =====================================================================
-- 2. Funcao trigger generica
-- =====================================================================
-- SECURITY DEFINER faz a funcao rodar com permissoes do dono (postgres),
-- contornando RLS de INSERT em audit_log (que vamos bloquear pra anon/authenticated).
-- Isso garante que apenas o trigger consegue gravar - ninguem do front consegue
-- forjar logs.

CREATE OR REPLACE FUNCTION audit_trigger_fn()
RETURNS TRIGGER
SECURITY DEFINER
SET search_path = public, pg_temp
LANGUAGE plpgsql
AS $$
DECLARE
  v_registro_id TEXT;
  v_email TEXT;
  v_user_id UUID;
  v_dados_antes JSONB;
  v_dados_depois JSONB;
BEGIN
  -- Tenta extrair 'id' do registro (cobre SERIAL int, UUID, qualquer tipo)
  IF TG_OP = 'DELETE' THEN
    v_registro_id := (row_to_json(OLD)::jsonb->>'id');
    v_dados_antes := row_to_json(OLD)::jsonb;
    v_dados_depois := NULL;
  ELSIF TG_OP = 'UPDATE' THEN
    v_registro_id := (row_to_json(NEW)::jsonb->>'id');
    v_dados_antes := row_to_json(OLD)::jsonb;
    v_dados_depois := row_to_json(NEW)::jsonb;
  ELSE  -- INSERT
    v_registro_id := (row_to_json(NEW)::jsonb->>'id');
    v_dados_antes := NULL;
    v_dados_depois := row_to_json(NEW)::jsonb;
  END IF;

  -- Tenta pegar email/user_id do JWT da sessao Supabase.
  -- auth.jwt() retorna NULL se rodando direto via SQL Editor (sem sessao user).
  BEGIN
    v_email := NULLIF(auth.jwt()->>'email', '');
    v_user_id := auth.uid();
  EXCEPTION WHEN OTHERS THEN
    v_email := NULL;
    v_user_id := NULL;
  END;
  -- Fallback: se nao tem auth (rodou via service_role ou SQL Editor),
  -- registra como 'sistema'
  IF v_email IS NULL THEN
    v_email := COALESCE(current_setting('request.jwt.claims', true)::jsonb->>'email', 'sistema/sql_editor');
  END IF;

  INSERT INTO audit_log (
    tabela, operacao, registro_id, por_email, por_user_id,
    dados_antes, dados_depois
  ) VALUES (
    TG_TABLE_NAME, TG_OP, v_registro_id, v_email, v_user_id,
    v_dados_antes, v_dados_depois
  );

  RETURN COALESCE(NEW, OLD);
END;
$$;


-- =====================================================================
-- 3. Aplicar trigger nas 21 tabelas
-- =====================================================================
-- Padrao do trigger: AFTER INSERT OR UPDATE OR DELETE, FOR EACH ROW.
-- DROP antes de CREATE pra ser idempotente.

DO $$
DECLARE
  tabelas TEXT[] := ARRAY[
    -- Criticas
    'users',
    'user_secrets',
    -- Compras (NAO inclui compras_historico - ja e log)
    'compras_solicitacoes',
    'compras_itens',
    'compras_anexos',
    'compras_departamentos',
    'compras_fornecedores',
    'compras_centros_custo',
    -- Corpo Clinico
    'cc_escala',
    'cc_profissionais',
    'cc_salas',
    -- Atendimentos Hospitalares
    'atendimentos',
    'capturas_formulario',
    'hospitais',
    'medicos',
    'procedimentos',
    'linhas_repasse',
    'extratos',
    -- Previas Recepcao
    'prev_previas_geradas',
    'prev_tabelas_preco',
    -- Envya (recebe via webhook)
    'attendances'
  ];
  t TEXT;
  trigger_name TEXT;
BEGIN
  FOREACH t IN ARRAY tabelas LOOP
    trigger_name := 'trg_audit_' || t;
    -- Verifica se a tabela existe antes de tentar aplicar (defensivo)
    IF EXISTS (
      SELECT 1 FROM information_schema.tables
      WHERE table_schema = 'public' AND table_name = t
    ) THEN
      EXECUTE format('DROP TRIGGER IF EXISTS %I ON public.%I;', trigger_name, t);
      EXECUTE format(
        'CREATE TRIGGER %I
           AFTER INSERT OR UPDATE OR DELETE ON public.%I
           FOR EACH ROW EXECUTE FUNCTION audit_trigger_fn();',
        trigger_name, t
      );
      RAISE NOTICE 'OK trigger criado: %', trigger_name;
    ELSE
      RAISE NOTICE 'SKIP tabela nao existe: %', t;
    END IF;
  END LOOP;
END $$;


-- =====================================================================
-- 4. RLS — Row Level Security do audit_log
-- =====================================================================
-- Regras:
--   - SELECT: so usuarios com cards contendo 'gestor' (admin)
--   - INSERT/UPDATE/DELETE diretos: bloqueados pra TODOS (so via trigger)
--   - Trigger contorna isso porque usa SECURITY DEFINER

ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_log_archive ENABLE ROW LEVEL SECURITY;

-- Limpa policies antigas (idempotente)
DROP POLICY IF EXISTS audit_log_select_gestor ON audit_log;
DROP POLICY IF EXISTS audit_log_archive_select_gestor ON audit_log_archive;

-- SELECT: so quem tem card 'gestor' na tabela users (mesma logica dos outros admins)
CREATE POLICY audit_log_select_gestor ON audit_log
  FOR SELECT TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM users u
      WHERE u.email = COALESCE(auth.jwt()->>'email', '')
        AND 'gestor' = ANY(u.cards)
    )
  );

CREATE POLICY audit_log_archive_select_gestor ON audit_log_archive
  FOR SELECT TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM users u
      WHERE u.email = COALESCE(auth.jwt()->>'email', '')
        AND 'gestor' = ANY(u.cards)
    )
  );

-- INSERT/UPDATE/DELETE diretos: SEM policy = ninguem consegue.
-- O trigger funciona porque usa SECURITY DEFINER (bypassa RLS).


-- =====================================================================
-- 5. Funcao de arquivamento (rotina mensal)
-- =====================================================================
-- Move eventos com mais de 1 ano pra audit_log_archive e remove do audit_log.
-- Pode ser rodada manualmente: SELECT arquivar_audit_log();
-- Ou agendada via pg_cron (Supabase Pro) — ver bloco opcional abaixo.

CREATE OR REPLACE FUNCTION arquivar_audit_log()
RETURNS TABLE(linhas_movidas BIGINT, executado_em TIMESTAMPTZ)
SECURITY DEFINER
SET search_path = public, pg_temp
LANGUAGE plpgsql
AS $$
DECLARE
  v_count BIGINT;
BEGIN
  WITH movidas AS (
    DELETE FROM audit_log
    WHERE criado_em < NOW() - INTERVAL '1 year'
    RETURNING *
  )
  INSERT INTO audit_log_archive (
    id, tabela, operacao, registro_id, por_email, por_user_id,
    dados_antes, dados_depois, criado_em
  )
  SELECT id, tabela, operacao, registro_id, por_email, por_user_id,
         dados_antes, dados_depois, criado_em
  FROM movidas;

  GET DIAGNOSTICS v_count = ROW_COUNT;
  RAISE NOTICE 'Arquivamento: % linhas movidas', v_count;

  RETURN QUERY SELECT v_count, NOW();
END;
$$;


-- =====================================================================
-- 6. (Opcional) Agendamento via pg_cron
-- =====================================================================
-- Descomente as 2 linhas abaixo SE o Supabase do projeto tiver pg_cron habilitado
-- (geralmente disponivel no plano Pro+). Roda dia 1 de cada mes as 03:00 UTC.
-- Pra verificar se pg_cron esta disponivel: SELECT * FROM pg_extension WHERE extname='pg_cron';

-- SELECT cron.schedule('arquivar-audit-log-mensal', '0 3 1 * *',
--   'SELECT arquivar_audit_log();');


-- =====================================================================
-- 7. Teste rapido (rodar APOS o setup completo)
-- =====================================================================
-- Faz uma operacao bobinha em compras_fornecedores pra ver se o trigger gravou.
-- Descomente, rode, depois apague o teste se quiser.

-- INSERT INTO compras_fornecedores (nome, ativo) VALUES ('TESTE AUDITORIA', false);
-- SELECT id, tabela, operacao, registro_id, por_email, criado_em
--   FROM audit_log
--   WHERE tabela = 'compras_fornecedores'
--   ORDER BY criado_em DESC LIMIT 1;
-- DELETE FROM compras_fornecedores WHERE nome = 'TESTE AUDITORIA';


-- =====================================================================
-- FIM
-- =====================================================================
-- Apos rodar, verifique:
--   - SELECT COUNT(*) FROM information_schema.triggers
--      WHERE trigger_name LIKE 'trg_audit_%';
--   (deve retornar 21, ou menos se alguma tabela ainda nao existir)
--
--   - SELECT tablename FROM pg_tables WHERE schemaname='public'
--      AND tablename IN ('audit_log','audit_log_archive');
--   (deve retornar 2)
-- =====================================================================
