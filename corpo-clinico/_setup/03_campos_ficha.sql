-- =====================================================================
-- Campos extras em cc_profissionais — alinha com a "Ficha de Cadastro
-- de novo profissional" (dados pessoais, empresa, bancários, etc.)
-- Executar no Supabase SQL Editor depois do 01_schema.sql.
-- =====================================================================

ALTER TABLE cc_profissionais
  -- Dados pessoais
  ADD COLUMN IF NOT EXISTS data_nascimento  DATE,
  ADD COLUMN IF NOT EXISTS sexo             TEXT,
  ADD COLUMN IF NOT EXISTS estado_civil     TEXT,
  ADD COLUMN IF NOT EXISTS rg               TEXT,
  ADD COLUMN IF NOT EXISTS endereco         TEXT,
  ADD COLUMN IF NOT EXISTS cidade           TEXT,
  ADD COLUMN IF NOT EXISTS estado           TEXT,
  ADD COLUMN IF NOT EXISTS cep              TEXT,
  -- Dados da empresa (se houver)
  ADD COLUMN IF NOT EXISTS cnpj             TEXT,
  ADD COLUMN IF NOT EXISTS razao_social     TEXT,
  ADD COLUMN IF NOT EXISTS optante_simples  BOOLEAN,
  -- Dados bancários / relação
  ADD COLUMN IF NOT EXISTS relacao_clinica  TEXT,   -- 'PF' | 'PJ'
  ADD COLUMN IF NOT EXISTS banco            TEXT,
  ADD COLUMN IF NOT EXISTS agencia          TEXT,
  ADD COLUMN IF NOT EXISTS conta            TEXT,
  ADD COLUMN IF NOT EXISTS pix              TEXT,
  -- Redes / atendimento
  ADD COLUMN IF NOT EXISTS facebook         TEXT,
  ADD COLUMN IF NOT EXISTS valor_pacote     NUMERIC(10,2),
  ADD COLUMN IF NOT EXISTS dias_retorno     TEXT;   -- "Dias para próxima consulta de retorno/rotina"
