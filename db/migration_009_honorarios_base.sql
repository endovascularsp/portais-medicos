-- Migration 009: Honorários — base de lançamentos fora do Excel local
-- 2026-08-03
--
-- CONTEXTO
-- Até aqui o fechamento de honorários vivia inteiro num Excel na máquina do Thiago
-- (`Fechamento - Endovascular SP.xlsx`, no Drive compartilhado). As regras de repasse
-- não existiam como regra em lugar nenhum: eram ~4.700 percentuais digitados célula a
-- célula. O gerador `gerar_pdata_*.py` não calculava nada — só somava o que o Excel
-- já tinha calculado.
--
-- Esta migration é a FASE 1 do plano combinado em 03/08/2026: tirar a base da máquina
-- local. Ela NÃO liga nada nos portais ainda e NÃO recalcula o passado.
--
--   1. `honorarios_periodos`    — um registro por mês, com status.
--   2. `honorarios_lancamentos` — a Base Compensação, linha a linha.
--   3. `honorarios_regras`      — as regras de repasse, que hoje só existem em prosa
--                                 no manual de RH. Vem com seed completo.
--   4. `honorarios_taxas`       — ISS + taxa comercial de 2% por categoria.
--
-- PRINCÍPIO: Janeiro a Junho/2026 entram CONGELADOS (`congelado = true`). Já foram
-- pagos. O motor pode auditá-los, nunca reescrevê-los sem decisão explícita.
--
-- Depende de: migration_001 (has_card / is_admin_user).

-- ============================================================
-- 1. Períodos
-- ============================================================
CREATE TABLE IF NOT EXISTS public.honorarios_periodos (
  periodo_id   text PRIMARY KEY,                       -- '2026-07'
  label        text NOT NULL,                          -- 'Julho/2026'
  status       text NOT NULL DEFAULT 'aberto'
               CHECK (status IN ('aberto', 'em_revisao', 'fechado', 'publicado')),
  congelado    boolean NOT NULL DEFAULT false,         -- true = importado do Excel, não recalcular
  fechado_em   timestamptz,
  publicado_em timestamptz,
  observacao   text,
  criado_em    timestamptz NOT NULL DEFAULT now()
);

COMMENT ON COLUMN public.honorarios_periodos.congelado IS
  'Períodos já pagos e publicados nos portais antes da automação (Jan–Jun/2026). '
  'O motor audita, mas não sobrescreve.';

-- ============================================================
-- 2. Lançamentos — a Base Compensação
--    Colunas 1-14 vêm do CSV #560 do Saudevianet (export por instituição).
--    Colunas 15-22 são calculadas pelo motor de repasse.
-- ============================================================
CREATE TABLE IF NOT EXISTS public.honorarios_lancamentos (
  id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  periodo_id           text NOT NULL REFERENCES public.honorarios_periodos(periodo_id),

  -- ---- origem (CSV #560) ----
  empresa              text NOT NULL CHECK (empresa IN ('Endovascular SP', 'Oxy Recovery')),
  os_numero            text,                   -- "N° OS"  (NÃO é único: 1 OS = N linhas)
  profissional         text NOT NULL,
  solicitante          text,                   -- "Profissional solicitante"
  paciente             text,
  indicacao            text,                   -- "Indicado Por"
  tabela               text,                   -- PARTICULAR / OMINT - PREMIUM / ...
  procedimento         text,
  categoria            text,                   -- derivada do procedimento (tabela Apoio)
  conta_pagamento      text,                   -- "Conta de pagamento" == coluna NF do Excel
  data_emissao         date,
  data_compensacao     date,
  tipo_pagamento       text,
  -- Dinheiro em 4 casas, NÃO em 2. O Excel carrega sub-centavo (uma sessão de
  -- pacote sai por 9,322) e arredondar linha a linha acumula: na carga do
  -- histórico a diferença deu R$ 1,35 no semestre. Guardamos na precisão da
  -- origem e arredondamos só na exibição.
  valor_recebido       numeric(14,4) NOT NULL DEFAULT 0,
  custo                numeric(14,4) NOT NULL DEFAULT 0,
  seq                  smallint NOT NULL DEFAULT 1,   -- ver chave natural, abaixo

  -- ---- calculado pelo motor ----
  imposto              numeric(14,4) NOT NULL DEFAULT 0,   -- ISS
  taxa_comercial       numeric(14,4) NOT NULL DEFAULT 0,   -- os 2% do Dr. Igor, separados do ISS
  taxa_cartao          numeric(14,4) NOT NULL DEFAULT 0,   -- 3%, só cartão de crédito
  valor_liquido        numeric(14,4) NOT NULL DEFAULT 0,
  repasse_profissional numeric(14,4) NOT NULL DEFAULT 0,
  repasse_indicador    numeric(14,4) NOT NULL DEFAULT 0,
  repasse_clinica      numeric(14,4) NOT NULL DEFAULT 0,

  -- ---- rastreabilidade ----
  pct_aplicado         numeric(6,4),           -- 0.6000
  regra_aplicada       text,                   -- 'Geral Endovascular SP' / 'R3A NF do profissional'
  papel                text CHECK (papel IN ('executor', 'indicador')),
  nf_propria           boolean NOT NULL DEFAULT false,  -- NF no nome do profissional (Regra 3A)
  origem               text NOT NULL DEFAULT 'csv_svn'
                       CHECK (origem IN ('importacao_excel', 'csv_svn', 'manual')),
  congelado            boolean NOT NULL DEFAULT false,
  revisado_por         text,                   -- e-mail de quem resolveu, se veio da fila
  revisado_em          timestamptz,
  observacao           text,

  criado_em            timestamptz NOT NULL DEFAULT now(),
  atualizado_em        timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS honorarios_lanc_periodo_idx
  ON public.honorarios_lancamentos (periodo_id);
CREATE INDEX IF NOT EXISTS honorarios_lanc_prof_idx
  ON public.honorarios_lancamentos (profissional, periodo_id);
CREATE INDEX IF NOT EXISTS honorarios_lanc_os_idx
  ON public.honorarios_lancamentos (os_numero);

-- Chave natural para não duplicar na reimportação do mesmo CSV.
--
-- Nº OS sozinho NÃO serve: em Junho eram 414 OS para 987 linhas (vários
-- procedimentos e várias parcelas por OS).
--
-- E os 6 campos abaixo TAMBÉM não bastam sozinhos: 1.035 linhas da base são
-- repetições legítimas, não duplicatas. Um pacote "10 Sessões de Fisioterapia"
-- vira 10 linhas idênticas de R$ 66,67; "T-SCULPTOR - 8 Sessões" vira 8 linhas
-- iguais; uma visita hospitalar parcelada em 10x vira 10 linhas iguais. O maior
-- grupo tem 10 repetições. Por isso entra `seq` (1..N dentro do grupo) —
-- sem ele, a importação do histórico perderia um terço dos lançamentos.
CREATE UNIQUE INDEX IF NOT EXISTS honorarios_lanc_natural_idx
  ON public.honorarios_lancamentos
     (empresa, os_numero, procedimento, data_compensacao, valor_recebido, profissional, seq);

-- ============================================================
-- 3. Regras de repasse
--    Fonte: Manual de Regras de Repasse v1.0 (02/04/2026) + decisões do Thiago
--    em 03/08/2026. Validadas contra 4.763 lançamentos reais: 92,6% de acerto.
--    `profissional NULL` = vale para todos. Override por profissional ganha do geral.
-- ============================================================
CREATE TABLE IF NOT EXISTS public.honorarios_regras (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  empresa          text NOT NULL CHECK (empresa IN ('Endovascular SP', 'Oxy Recovery')),
  categoria        text NOT NULL,
  profissional     text,                        -- NULL = regra geral da categoria
  papel            text NOT NULL DEFAULT 'executor' CHECK (papel IN ('executor', 'indicador')),
  percentual       numeric(6,4) NOT NULL,       -- 0.6000
  base_calculo     text NOT NULL DEFAULT 'liquido' CHECK (base_calculo IN ('liquido', 'bruto')),
  vigencia_inicio  date,                        -- NULL = desde sempre (vigência fica p/ depois)
  vigencia_fim     date,
  observacao       text,
  ativo            boolean NOT NULL DEFAULT true,
  criado_em        timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS honorarios_regras_chave_idx
  ON public.honorarios_regras
     (empresa, categoria, coalesce(profissional, '*'), papel, coalesce(vigencia_inicio, '1900-01-01'));

-- ---- seed: regra geral por categoria ----
INSERT INTO public.honorarios_regras (empresa, categoria, profissional, percentual, observacao) VALUES
  ('Endovascular SP', 'Consultas',           NULL, 0.60, NULL),
  ('Endovascular SP', 'Exames de imagem',    NULL, 0.60, NULL),
  ('Endovascular SP', 'Exames gerais',       NULL, 0.60, NULL),
  ('Endovascular SP', 'Procedimentos',       NULL, 0.60, NULL),
  ('Endovascular SP', 'Fotona',              NULL, 0.60, 'Na Endo, Fotona é procedimento normal'),
  ('Endovascular SP', 'Laser (clínica)',     NULL, 0.60, NULL),
  ('Endovascular SP', 'Laser (locação)',     NULL, 0.60, NULL),
  ('Endovascular SP', 'Fisioterapia',        NULL, 0.50, NULL),
  ('Endovascular SP', 'Medicação injetável', NULL, 0.30, NULL),
  ('Endovascular SP', 'T-Sculptor',          NULL, 0.00, 'Equipamento da clínica'),
  ('Endovascular SP', 'Produtos',            NULL, 0.00, 'Não entra em repasse'),
  ('Oxy Recovery',    'Consultas',           NULL, 0.60, NULL),
  ('Oxy Recovery',    'Exames de imagem',    NULL, 0.60, NULL),
  ('Oxy Recovery',    'Exames gerais',       NULL, 0.60, NULL),
  ('Oxy Recovery',    'Procedimentos',       NULL, 0.65, 'Executor recebe mais que na Endo'),
  ('Oxy Recovery',    'Fisioterapia',        NULL, 0.50, NULL),
  ('Oxy Recovery',    'Medicação injetável', NULL, 0.30, NULL),
  ('Oxy Recovery',    'Produtos',            NULL, 0.00, 'Não entra em repasse')
ON CONFLICT DO NOTHING;

-- ---- seed: Fotona na Oxy — só Christiane e Juliana executam; o resto indica ----
INSERT INTO public.honorarios_regras (empresa, categoria, profissional, papel, percentual, observacao) VALUES
  ('Oxy Recovery', 'Fotona', 'Christiane Sayuri Lopes Inoue', 'executor',  0.20, 'Única médica que executa Fotona na Oxy'),
  ('Oxy Recovery', 'Fotona', 'Juliana Olimpio',               'executor',  0.00, 'Fisioterapeuta interna — sem repasse'),
  ('Oxy Recovery', 'Fotona', 'Juliana Olimpio de Paula',      'executor',  0.00, 'Mesma pessoa, grafia alternativa na base'),
  ('Oxy Recovery', 'Fotona', NULL,                            'indicador', 0.10, 'Demais profissionais indicam e recebem 10%')
ON CONFLICT DO NOTHING;

-- ---- seed: T-Sculptor na Oxy — a Enfermagem executa; o profissional indica ----
INSERT INTO public.honorarios_regras (empresa, categoria, profissional, papel, percentual, observacao) VALUES
  ('Oxy Recovery', 'T-Sculptor', 'Fernanda Liporaci Villela Zuchi', 'executor',  0.50, 'Fisioterapeuta executando: 50/50'),
  ('Oxy Recovery', 'T-Sculptor', NULL,                              'indicador', 0.10, 'Indicador/solicitante recebe 10%')
ON CONFLICT DO NOTHING;

-- ---- seed: exceções por profissional ----
INSERT INTO public.honorarios_regras (empresa, categoria, profissional, percentual, observacao) VALUES
  ('Endovascular SP', 'Consultas',       'Simone Matsuda Torricelli', 0.70, 'Repasse especial'),
  ('Endovascular SP', 'Exames gerais',   'Simone Matsuda Torricelli', 0.70, 'Repasse especial'),
  ('Endovascular SP', 'Consultas',       'Nicole Tenenbaum Szajubok', 0.70, 'Fellow da Dra. Simone — segue a regra dela'),
  ('Endovascular SP', 'Exames gerais',   'Nicole Tenenbaum Szajubok', 0.70, 'Fellow da Dra. Simone — segue a regra dela'),
  ('Endovascular SP', 'Procedimentos',   'Daniela Viese Roth',        0.80, 'Regra específica'),
  ('Oxy Recovery',    'Laser (clínica)', 'Christiane Sayuri Lopes Inoue', 0.35, NULL),
  ('Oxy Recovery',    'Laser (locação)', 'Christiane Sayuri Lopes Inoue', 0.20, NULL)
ON CONFLICT DO NOTHING;

-- ---- seed: cirurgias ----
-- Regra 3A (NF no nome do profissional) NÃO entra aqui: é tratada no motor, porque
-- o percentual incide sobre o BRUTO e o sinal é invertido (o profissional deve à clínica).
-- Regras 3B (paciente do médico, 90%) e 3C (paciente da clínica, 80%) dependem de um
-- campo que ainda não existe — por isso Cirurgia - Hospital particular fica sem regra
-- e cai na fila de exceções.
INSERT INTO public.honorarios_regras (empresa, categoria, profissional, percentual, observacao) VALUES
  ('Endovascular SP', 'Cirurgia - Clínica',  NULL, 0.80, 'Regra 2 — clínica particular'),
  ('Endovascular SP', 'Cirurgia - Hospital', NULL, 0.85, 'Regra 1 — SÓ quando a Tabela é plano de saúde')
ON CONFLICT DO NOTHING;

-- ============================================================
-- 4. Impostos e taxas por categoria
--    O ISS é 18%. Em Junho/2026 o Dr. Igor pediu +2% de taxa de negociação em
--    algumas categorias; na planilha isso foi embutido como "ISS 20%", o que deixou
--    o rótulo "Imposto (18%)" mentiroso nos portais. Aqui os dois ficam separados.
--    Medicação injetável entra só a partir de Julho (o aviso chegou depois do fechamento).
-- ============================================================
CREATE TABLE IF NOT EXISTS public.honorarios_taxas (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  categoria       text NOT NULL,
  iss             numeric(6,4) NOT NULL DEFAULT 0.18,
  taxa_comercial  numeric(6,4) NOT NULL DEFAULT 0,
  vigencia_inicio date,
  observacao      text
);

INSERT INTO public.honorarios_taxas (categoria, iss, taxa_comercial, vigencia_inicio, observacao) VALUES
  ('Fotona',              0.18, 0.02, '2026-06-01', 'Taxa comercial pedida pelo Dr. Igor'),
  ('Cirurgia - Clínica',  0.18, 0.02, '2026-06-01', NULL),
  ('Cirurgia - Hospital', 0.18, 0.02, '2026-06-01', NULL),
  ('Procedimentos',       0.18, 0.02, '2026-06-01', NULL),
  ('T-Sculptor',          0.18, 0.02, '2026-06-01', NULL),
  ('Laser (clínica)',     0.18, 0.02, '2026-06-01', NULL),
  ('Laser (locação)',     0.18, 0.02, '2026-06-01', NULL),
  ('Medicação injetável', 0.18, 0.02, '2026-07-01', 'Escapou do filtro em Junho — vale a partir de Julho')
ON CONFLICT DO NOTHING;

-- ============================================================
-- 5. RLS — honorário é dado sensível: só admin e quem tem o card.
--    O médico NÃO lê estas tabelas: o portal dele continua servido pelo PDATA.
-- ============================================================
ALTER TABLE public.honorarios_periodos    ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.honorarios_lancamentos ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.honorarios_regras      ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.honorarios_taxas       ENABLE ROW LEVEL SECURITY;

DO $$
DECLARE t text;
BEGIN
  FOREACH t IN ARRAY ARRAY['honorarios_periodos', 'honorarios_lancamentos',
                           'honorarios_regras', 'honorarios_taxas']
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
-- 6. Períodos já pagos — entram congelados
-- ============================================================
INSERT INTO public.honorarios_periodos (periodo_id, label, status, congelado, observacao) VALUES
  ('2026-01', 'Janeiro/2026',   'publicado', true, 'Importado do Excel — já pago e publicado'),
  ('2026-02', 'Fevereiro/2026', 'publicado', true, 'Importado do Excel — já pago e publicado'),
  ('2026-03', 'Março/2026',     'publicado', true, 'Importado do Excel — já pago e publicado'),
  ('2026-04', 'Abril/2026',     'publicado', true, 'Importado do Excel — já pago e publicado'),
  ('2026-05', 'Maio/2026',      'publicado', true, 'Importado do Excel — já pago e publicado'),
  -- Junho carrega as correções de 03/08 (T-Sculptor 10% e cirurgias de plano 85%).
  -- Decisão do Thiago: republicar com os valores corrigidos e acertar a diferença
  -- em folha — Igor +1.119,66 e Manoel +433,16 a receber; Igor -728,94 e Simone
  -- -308,00 a descontar. Enquanto não republicar, portal e base ficam divergentes.
  ('2026-06', 'Junho/2026',     'publicado', true, 'Corrigido em 03/08 — republicar e acertar diferença em folha')
ON CONFLICT (periodo_id) DO NOTHING;
