-- Migration 010: Honorários — catálogo de procedimentos e fila de exceções
-- 2026-08-03
--
-- CONTEXTO
-- A migration_009 tirou a base do Excel. Esta prepara o motor de repasse.
--
-- Duas peças faltavam:
--
--   1. `honorarios_procedimentos` — o CSV do SVN traz o PROCEDIMENTO, não a
--      CATEGORIA, e é a categoria que decide o percentual. Essa tradução vivia
--      numa aba "Apoio" do Excel com 184 linhas e um VLOOKUP. Vira tabela aqui.
--
--      De quebra, normaliza duas grafias que o Excel tratava como categorias
--      distintas: "Exames de Imagem"/"Exames de imagem" e
--      "Medicação Injetável"/"Medicação injetável".
--
--   2. `honorarios_excecoes` — a fila. O motor NUNCA chuta: quando não sabe
--      resolver, cria uma exceção e para naquela linha. É o que substitui o
--      "Thiago decide de cabeça" e o que permite outra pessoa tocar o fechamento.
--
-- Depende de: migration_001 (has_card/is_admin_user), migration_009.

-- ============================================================
-- 1. Catálogo de procedimentos (procedimento -> categoria)
-- ============================================================
CREATE TABLE IF NOT EXISTS public.honorarios_procedimentos (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  chave        text NOT NULL,          -- procedimento normalizado (sem acento, minúsculo)
  procedimento text NOT NULL,          -- grafia original, para exibir
  categoria    text NOT NULL,
  ativo        boolean NOT NULL DEFAULT true,
  origem       text NOT NULL DEFAULT 'apoio_excel'
               CHECK (origem IN ('apoio_excel', 'fila', 'manual')),
  criado_em    timestamptz NOT NULL DEFAULT now(),
  criado_por   text
);

CREATE UNIQUE INDEX IF NOT EXISTS honorarios_procedimentos_chave_idx
  ON public.honorarios_procedimentos (chave);

COMMENT ON COLUMN public.honorarios_procedimentos.chave IS
  'Procedimento sem acento e em minúsculas. O SVN varia a grafia entre meses '
  '("10 Sessões de fisioterapia" x "10 Sessões de Fisioterapia") — casar pela '
  'chave evita que a mesma coisa vire dois procedimentos.';

-- ============================================================
-- 2. Fila de exceções
--    Uma linha aqui = uma decisão que o motor não pode tomar sozinho.
-- ============================================================
CREATE TABLE IF NOT EXISTS public.honorarios_excecoes (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  periodo_id     text NOT NULL REFERENCES public.honorarios_periodos(periodo_id),
  tipo           text NOT NULL CHECK (tipo IN (
                   'procedimento_sem_categoria',  -- não está no catálogo
                   'cirurgia_sem_origem_lead',    -- hospital particular: 80% ou 90%?
                   'sem_regra',                   -- categoria sem repasse cadastrado
                   'profissional_invalido',       -- campo com "Oxy Recovery", vazio, etc.
                   'divergencia_valor'            -- calculado != o que veio do SVN
                 )),
  status         text NOT NULL DEFAULT 'aberta'
                 CHECK (status IN ('aberta', 'resolvida', 'ignorada')),

  -- contexto suficiente pra decidir sem abrir o CSV
  lancamento_id  uuid REFERENCES public.honorarios_lancamentos(id) ON DELETE CASCADE,
  empresa        text,
  os_numero      text,
  profissional   text,
  paciente       text,
  procedimento   text,
  categoria      text,
  tabela         text,
  indicacao      text,
  valor_recebido numeric(14,4),
  data_compensacao date,

  descricao      text NOT NULL,   -- o que o motor não soube
  sugestao       text,            -- palpite do motor, quando existe (nunca aplicado sozinho)
  resolucao      jsonb,           -- o que foi decidido
  resolvido_por  text,
  resolvido_em   timestamptz,
  criado_em      timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS honorarios_excecoes_fila_idx
  ON public.honorarios_excecoes (status, periodo_id, tipo);

-- Não repetir a mesma pergunta: uma exceção aberta por (período, tipo, procedimento, OS).
CREATE UNIQUE INDEX IF NOT EXISTS honorarios_excecoes_unica_idx
  ON public.honorarios_excecoes
     (periodo_id, tipo, coalesce(procedimento, ''), coalesce(os_numero, ''),
      coalesce(profissional, ''))
  WHERE status = 'aberta';

-- ============================================================
-- 3. RLS — mesmo critério da 009
-- ============================================================
ALTER TABLE public.honorarios_procedimentos ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.honorarios_excecoes      ENABLE ROW LEVEL SECURITY;

DO $$
DECLARE t text;
BEGIN
  FOREACH t IN ARRAY ARRAY['honorarios_procedimentos', 'honorarios_excecoes']
  LOOP
    EXECUTE format('DROP POLICY IF EXISTS %I_read  ON public.%I', t, t);
    EXECUTE format('DROP POLICY IF EXISTS %I_write ON public.%I', t, t);
    EXECUTE format(
      'CREATE POLICY %I_read ON public.%I FOR SELECT TO authenticated
         USING (public.is_admin_user() OR public.has_card(''honorarios''))', t, t);
    EXECUTE format(
      'CREATE POLICY %I_write ON public.%I FOR ALL TO authenticated
         USING (public.is_admin_user() OR public.has_card(''honorarios''))
         WITH CHECK (public.is_admin_user() OR public.has_card(''honorarios''))', t, t);
  END LOOP;
END $$;

-- ============================================================
-- 4. Julho/2026 — primeiro período que o motor vai calcular
-- ============================================================
INSERT INTO public.honorarios_periodos (periodo_id, label, status, congelado, observacao)
VALUES ('2026-07', 'Julho/2026', 'aberto', false,
        'Primeiro período calculado pelo motor. Fechado em paralelo com o Excel para conferência.')
ON CONFLICT (periodo_id) DO NOTHING;
