-- =====================================================================
-- SCHEMA — Portal Corpo Clínico
-- =====================================================================
-- Centraliza o corpo clínico (profissionais, salas, escala de atendimento).
-- Substitui as planilhas "Corpo clínico" e "Mapa de Sala".
-- Executar no Supabase SQL Editor.
-- =====================================================================

-- 1. cc_salas — salas/espaços de atendimento
CREATE TABLE IF NOT EXISTS cc_salas (
  id        SERIAL PRIMARY KEY,
  nome      TEXT NOT NULL,
  tipo      TEXT,                    -- consultorio | procedimento | spa | fotona
  ordem     INT DEFAULT 0,
  ativo     BOOLEAN DEFAULT TRUE,
  criado_em TIMESTAMPTZ DEFAULT NOW()
);

-- 2. cc_profissionais — fichas do corpo clínico
CREATE TABLE IF NOT EXISTS cc_profissionais (
  id                 SERIAL PRIMARY KEY,
  nome               TEXT NOT NULL,
  especialidade      TEXT,
  empresa            TEXT,
  foto_url           TEXT,
  -- atendimento
  atende_online      BOOLEAN DEFAULT FALSE,
  atende_convenio    BOOLEAN DEFAULT FALSE,
  tempo_primeira_vez TEXT,           -- "1 hora", "45 min"...
  tempo_retorno      TEXT,
  valor_consulta     NUMERIC(10,2),
  faixa_idade        TEXT,           -- "A partir dos 14 anos", "Todas as idades"
  -- registro profissional
  conselho           TEXT,           -- CRM | CRN | CREFITO
  conselho_numero    TEXT,
  rqe                TEXT,
  -- dados cadastrais
  cpf                TEXT,
  celular            TEXT,
  email              TEXT,
  instagram          TEXT,
  -- conteúdo
  procedimentos      TEXT,           -- resumo dos tratamentos/procedimentos que realiza
  observacoes        TEXT,           -- notas livres (antigo campo "Detalhes")
  ativo              BOOLEAN DEFAULT TRUE,
  criado_em          TIMESTAMPTZ DEFAULT NOW(),
  atualizado_em      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cc_prof_nome ON cc_profissionais (nome);

-- 3. cc_escala — grade de atendimento (dia × sala × profissional)
--    Cada registro = um bloco de atendimento. É a fonte da verdade dos horários.
CREATE TABLE IF NOT EXISTS cc_escala (
  id              SERIAL PRIMARY KEY,
  profissional_id INT NOT NULL REFERENCES cc_profissionais(id) ON DELETE CASCADE,
  sala_id         INT REFERENCES cc_salas(id),
  dia_semana      INT NOT NULL,      -- 1=segunda ... 5=sexta ... 6=sábado
  hora_inicio     TIME,
  hora_fim        TIME,              -- pode ficar NULL até o Agendamento confirmar
  observacao      TEXT,
  criado_em       TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cc_escala_prof ON cc_escala (profissional_id);
CREATE INDEX IF NOT EXISTS idx_cc_escala_dia  ON cc_escala (dia_semana);

-- Trigger: atualiza atualizado_em
CREATE OR REPLACE FUNCTION cc_touch()
RETURNS TRIGGER AS $$
BEGIN NEW.atualizado_em = NOW(); RETURN NEW; END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_cc_prof_touch ON cc_profissionais;
CREATE TRIGGER trg_cc_prof_touch
  BEFORE UPDATE ON cc_profissionais
  FOR EACH ROW EXECUTE FUNCTION cc_touch();

-- =====================================================================
-- RLS — leitura pra qualquer autenticado; escrita também (refina depois)
-- =====================================================================
ALTER TABLE cc_salas         ENABLE ROW LEVEL SECURITY;
ALTER TABLE cc_profissionais ENABLE ROW LEVEL SECURITY;
ALTER TABLE cc_escala        ENABLE ROW LEVEL SECURITY;

CREATE POLICY "cc_sel" ON cc_salas         FOR SELECT TO authenticated USING (true);
CREATE POLICY "cc_ins" ON cc_salas         FOR INSERT TO authenticated WITH CHECK (true);
CREATE POLICY "cc_upd" ON cc_salas         FOR UPDATE TO authenticated USING (true) WITH CHECK (true);
CREATE POLICY "cc_del" ON cc_salas         FOR DELETE TO authenticated USING (true);

CREATE POLICY "cc_sel" ON cc_profissionais FOR SELECT TO authenticated USING (true);
CREATE POLICY "cc_ins" ON cc_profissionais FOR INSERT TO authenticated WITH CHECK (true);
CREATE POLICY "cc_upd" ON cc_profissionais FOR UPDATE TO authenticated USING (true) WITH CHECK (true);
CREATE POLICY "cc_del" ON cc_profissionais FOR DELETE TO authenticated USING (true);

CREATE POLICY "cc_sel" ON cc_escala        FOR SELECT TO authenticated USING (true);
CREATE POLICY "cc_ins" ON cc_escala        FOR INSERT TO authenticated WITH CHECK (true);
CREATE POLICY "cc_upd" ON cc_escala        FOR UPDATE TO authenticated USING (true) WITH CHECK (true);
CREATE POLICY "cc_del" ON cc_escala        FOR DELETE TO authenticated USING (true);
