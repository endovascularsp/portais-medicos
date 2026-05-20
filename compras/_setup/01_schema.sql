-- =====================================================================
-- SCHEMA — Portal Compras
-- =====================================================================
-- Executar no Supabase SQL Editor.
-- Idempotente: usa CREATE TABLE IF NOT EXISTS quando possivel.
--
-- Ordem importa (FKs):
--   1. departamentos, centros_custo, fornecedores (sem FK)
--   2. users.departamento_id (FK pra departamentos)
--   3. solicitacoes (FK pra depto + centro_custo + users)
--   4. itens, anexos, historico (FK pra solicitacoes)
-- =====================================================================

-- ENUMs
DO $$ BEGIN
  CREATE TYPE compras_status AS ENUM (
    'aguardando_aprovacao',
    'em_cotacao',
    'aguardando_pagto',
    'concluida',
    'recusada'
  );
EXCEPTION WHEN duplicate_object THEN null; END $$;

DO $$ BEGIN
  CREATE TYPE compras_urgencia AS ENUM ('baixa', 'media', 'alta');
EXCEPTION WHEN duplicate_object THEN null; END $$;

DO $$ BEGIN
  CREATE TYPE compras_metodo_pagto AS ENUM (
    'pix',
    'boleto',
    'cartao_credito',
    'link_pagamento'
  );
EXCEPTION WHEN duplicate_object THEN null; END $$;

DO $$ BEGIN
  CREATE TYPE compras_anexo_tipo AS ENUM ('pdf', 'imagem', 'excel', 'link');
EXCEPTION WHEN duplicate_object THEN null; END $$;

-- =====================================================================
-- 1. compras_departamentos
-- =====================================================================
CREATE TABLE IF NOT EXISTS compras_departamentos (
  id           SERIAL PRIMARY KEY,
  nome         TEXT NOT NULL UNIQUE,
  gestor_email TEXT,                       -- quem aprova; pode ser null inicialmente
  ativo        BOOLEAN DEFAULT TRUE,
  criado_em    TIMESTAMPTZ DEFAULT NOW()
);

-- =====================================================================
-- 2. compras_centros_custo (2 unidades: Endo + Oxy)
-- =====================================================================
CREATE TABLE IF NOT EXISTS compras_centros_custo (
  id        SERIAL PRIMARY KEY,
  codigo    TEXT NOT NULL UNIQUE,           -- 'END', 'OXY'
  nome      TEXT NOT NULL,                  -- 'Endovascular', 'Oxy Recovery'
  ativo     BOOLEAN DEFAULT TRUE,
  criado_em TIMESTAMPTZ DEFAULT NOW()
);

-- =====================================================================
-- 3. compras_fornecedores
-- =====================================================================
CREATE TABLE IF NOT EXISTS compras_fornecedores (
  id              SERIAL PRIMARY KEY,
  nome            TEXT NOT NULL,
  cnpj            TEXT,
  contato_nome    TEXT,
  contato_email   TEXT,
  contato_telefone TEXT,
  ativo           BOOLEAN DEFAULT TRUE,
  validado        BOOLEAN DEFAULT FALSE,    -- false quando solicitante cadastra novo
  criado_por      TEXT,                     -- email de quem cadastrou
  criado_em       TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (nome)
);

-- =====================================================================
-- 4. users.departamento_id  (FK opcional pra tabela existente)
-- =====================================================================
ALTER TABLE users
  ADD COLUMN IF NOT EXISTS departamento_id INT REFERENCES compras_departamentos(id);

-- =====================================================================
-- 5. compras_solicitacoes
-- =====================================================================
CREATE TABLE IF NOT EXISTS compras_solicitacoes (
  id                 SERIAL PRIMARY KEY,
  numero             TEXT UNIQUE,                  -- ex: '2026-001' gerado por trigger
  solicitante_email  TEXT NOT NULL,
  departamento_id    INT REFERENCES compras_departamentos(id),
  centro_custo_id    INT REFERENCES compras_centros_custo(id),
  justificativa      TEXT NOT NULL,
  urgencia           compras_urgencia DEFAULT 'media',
  data_limite        DATE,
  observacoes        TEXT,
  status             compras_status DEFAULT 'aguardando_aprovacao',
  -- aprovação
  aprovador_email    TEXT,
  aprovado_em        TIMESTAMPTZ,
  motivo_recusa      TEXT,
  -- cotação/compra
  comprador_email    TEXT,
  comprado_em        TIMESTAMPTZ,
  valor_final        NUMERIC(12,2),
  metodo_pagamento   compras_metodo_pagto,
  -- pagamento
  pago_em            TIMESTAMPTZ,
  pago_por           TEXT,
  -- metadata
  criado_em          TIMESTAMPTZ DEFAULT NOW(),
  atualizado_em      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_solic_status         ON compras_solicitacoes (status);
CREATE INDEX IF NOT EXISTS idx_solic_solicitante    ON compras_solicitacoes (solicitante_email);
CREATE INDEX IF NOT EXISTS idx_solic_dept           ON compras_solicitacoes (departamento_id);
CREATE INDEX IF NOT EXISTS idx_solic_criado         ON compras_solicitacoes (criado_em DESC);

-- =====================================================================
-- 6. compras_itens (carrinho: N itens por solicitação)
-- =====================================================================
CREATE TABLE IF NOT EXISTS compras_itens (
  id                  SERIAL PRIMARY KEY,
  solicitacao_id      INT NOT NULL REFERENCES compras_solicitacoes(id) ON DELETE CASCADE,
  descricao           TEXT NOT NULL,                    -- texto livre (decisão: sem catálogo)
  quantidade          NUMERIC(10,2) DEFAULT 1,
  unidade             TEXT,                              -- un, cx, L, kg... opcional
  fornecedor_sugerido_id INT REFERENCES compras_fornecedores(id),
  valor_estimado      NUMERIC(12,2),
  -- preenchido pela Compradora
  fornecedor_final_id INT REFERENCES compras_fornecedores(id),
  valor_final         NUMERIC(12,2),
  criado_em           TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_itens_solic ON compras_itens (solicitacao_id);

-- =====================================================================
-- 7. compras_anexos (PDF/imagem/Excel/link)
-- =====================================================================
CREATE TABLE IF NOT EXISTS compras_anexos (
  id              SERIAL PRIMARY KEY,
  solicitacao_id  INT NOT NULL REFERENCES compras_solicitacoes(id) ON DELETE CASCADE,
  tipo            compras_anexo_tipo NOT NULL,
  filename        TEXT,
  file_path       TEXT,                                 -- caminho no Supabase Storage
  url_externa     TEXT,                                 -- pra tipo=link (Mercado Livre etc)
  descricao       TEXT,
  uploaded_by     TEXT,
  uploaded_em     TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_anexos_solic ON compras_anexos (solicitacao_id);

-- =====================================================================
-- 8. compras_historico (log de mudanças)
-- =====================================================================
CREATE TABLE IF NOT EXISTS compras_historico (
  id                SERIAL PRIMARY KEY,
  solicitacao_id    INT NOT NULL REFERENCES compras_solicitacoes(id) ON DELETE CASCADE,
  acao              TEXT NOT NULL,                      -- 'criada' | 'editada' | 'aprovada' | 'recusada' | 'cotada' | 'paga' | 'comentario'
  por_email         TEXT NOT NULL,
  comentario        TEXT,
  dados_anteriores  JSONB,                              -- snapshot antes da mudança
  criado_em         TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_hist_solic ON compras_historico (solicitacao_id, criado_em DESC);

-- =====================================================================
-- TRIGGER: atualiza compras_solicitacoes.atualizado_em automaticamente
-- =====================================================================
CREATE OR REPLACE FUNCTION compras_touch_atualizado()
RETURNS TRIGGER AS $$
BEGIN
  NEW.atualizado_em = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_solic_touch ON compras_solicitacoes;
CREATE TRIGGER trg_solic_touch
  BEFORE UPDATE ON compras_solicitacoes
  FOR EACH ROW EXECUTE FUNCTION compras_touch_atualizado();

-- =====================================================================
-- TRIGGER: gera numero sequencial 'AAAA-NNN' ao criar solicitação
-- =====================================================================
CREATE OR REPLACE FUNCTION compras_gerar_numero()
RETURNS TRIGGER AS $$
DECLARE
  ano TEXT;
  seq INT;
BEGIN
  IF NEW.numero IS NULL THEN
    ano := TO_CHAR(NOW(), 'YYYY');
    SELECT COALESCE(MAX(CAST(SPLIT_PART(numero, '-', 2) AS INT)), 0) + 1
      INTO seq
      FROM compras_solicitacoes
      WHERE numero LIKE ano || '-%';
    NEW.numero := ano || '-' || LPAD(seq::TEXT, 3, '0');
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_solic_numero ON compras_solicitacoes;
CREATE TRIGGER trg_solic_numero
  BEFORE INSERT ON compras_solicitacoes
  FOR EACH ROW EXECUTE FUNCTION compras_gerar_numero();

-- =====================================================================
-- RLS (Row Level Security) — políticas básicas
-- =====================================================================
-- TODO: definir políticas detalhadas após decidir.
-- Por enquanto: deixar tudo aberto pra service_role; bloquear anon.
-- Ajustar quando ligarmos o frontend ao Supabase.

ALTER TABLE compras_departamentos     ENABLE ROW LEVEL SECURITY;
ALTER TABLE compras_centros_custo     ENABLE ROW LEVEL SECURITY;
ALTER TABLE compras_fornecedores      ENABLE ROW LEVEL SECURITY;
ALTER TABLE compras_solicitacoes      ENABLE ROW LEVEL SECURITY;
ALTER TABLE compras_itens             ENABLE ROW LEVEL SECURITY;
ALTER TABLE compras_anexos            ENABLE ROW LEVEL SECURITY;
ALTER TABLE compras_historico         ENABLE ROW LEVEL SECURITY;

-- Liberar leitura pra qualquer usuário autenticado (refinar depois)
CREATE POLICY "compras_select_authenticated" ON compras_departamentos
  FOR SELECT TO authenticated USING (true);
CREATE POLICY "compras_select_authenticated" ON compras_centros_custo
  FOR SELECT TO authenticated USING (true);
CREATE POLICY "compras_select_authenticated" ON compras_fornecedores
  FOR SELECT TO authenticated USING (true);

-- Solicitações: visibilidade vai depender do card. Por ora libera read pra autenticados.
CREATE POLICY "compras_select_authenticated" ON compras_solicitacoes
  FOR SELECT TO authenticated USING (true);
CREATE POLICY "compras_select_authenticated" ON compras_itens
  FOR SELECT TO authenticated USING (true);
CREATE POLICY "compras_select_authenticated" ON compras_anexos
  FOR SELECT TO authenticated USING (true);
CREATE POLICY "compras_select_authenticated" ON compras_historico
  FOR SELECT TO authenticated USING (true);

-- =====================================================================
-- FIM
-- =====================================================================
