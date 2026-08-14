-- Migration 013: Honorários — descontos e acréscimos lançados à mão
-- 2026-08-14
--
-- CONTEXTO
-- O portal de Recebimento sempre respondeu "quanto a clínica te deve pelo
-- trabalho do mês". O que cai na conta às vezes é outro número: a clínica paga
-- o plano de saúde do Dr. Igor e desconta do repasse; uma cobrança indevida é
-- devolvida no mês seguinte; um custo pessoal é descontado. Nada disso passa
-- pelo Saudevianet — não existe OS, não existe procedimento, não há como o
-- motor saber.
--
-- Em Julho/2026 isso gerou o problema que originou esta tabela: uma médica viu
-- o valor no portal, recebeu menos na conta e ligou. O portal não estava
-- errado; ele respondia a outra pergunta.
--
-- Esta tabela é a resposta manual, lançada pela equipe financeira na aba
-- "Descontos e acréscimos" do card de Fechamento.
--
-- DECISÕES DO THIAGO (14/08/2026)
--   1. CENTRO DE CUSTO é obrigatório. O profissional pode ter até 3 portais
--      (Endovascular SP, Oxy Recovery, Cirurgias); sem dizer de qual sai, o
--      mesmo desconto apareceria três vezes ou nenhuma.
--   2. O período é o MÊS EM QUE SE APLICA o desconto, escolhido por quem
--      lança — não o mês do fato que o originou. A cobrança indevida pode ser
--      de Julho e a devolução cair em Agosto.
--   3. Lançamento que chegar depois da publicação não aparece sozinho: o
--      portal do médico é arquivo gerado. Nesse caso, republica-se o mês.
--   4. A `descricao` é lida pelo médico, palavra por palavra. A `observacao`
--      fica só na tela da equipe.
--   5. `repete` marca o que se repete todo mês (o plano de saúde), para a tela
--      oferecer trazer os do mês anterior em vez de relançar na unha.
--
-- O SINAL NÃO MORA NO VALOR: `valor` é sempre positivo e `tipo` diz se soma ou
-- subtrai. Valor negativo com tipo 'desconto' viraria desconto ao contrário na
-- primeira distração, e o portal do médico é o pior lugar para isso aparecer.
--
-- Depende de: migration_001 (has_card / is_admin_user), migration_009
-- (honorarios_periodos).

CREATE TABLE IF NOT EXISTS public.honorarios_ajustes (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  periodo_id     text          NOT NULL REFERENCES public.honorarios_periodos(periodo_id),
  profissional   text          NOT NULL,
  centro_custo   text          NOT NULL
                   CHECK (centro_custo IN ('Endovascular SP', 'Oxy Recovery', 'Cirurgias')),
  tipo           text          NOT NULL CHECK (tipo IN ('desconto', 'acrescimo')),
  descricao      text          NOT NULL CHECK (length(btrim(descricao)) >= 3),
  observacao     text,
  valor          numeric(14,2) NOT NULL CHECK (valor > 0),
  repete         boolean       NOT NULL DEFAULT false,
  -- lançamento criado a partir de outro, quando a tela traz os do mês anterior
  origem_id      uuid          REFERENCES public.honorarios_ajustes(id) ON DELETE SET NULL,
  criado_por     text          NOT NULL,
  criado_em      timestamptz   NOT NULL DEFAULT now(),
  atualizado_por text,
  atualizado_em  timestamptz
);

COMMENT ON TABLE public.honorarios_ajustes IS
  'Descontos e acréscimos que não passam pelo Saudevianet e por isso são '
  'lançados à mão. Entram no portal do médico como o card "Descontos e '
  'acréscimos" e no detalhe do "entenda os valores".';

COMMENT ON COLUMN public.honorarios_ajustes.periodo_id IS
  'Mês em que o desconto/acréscimo é APLICADO, escolhido por quem lança. Não é '
  'o mês do fato que o originou.';

COMMENT ON COLUMN public.honorarios_ajustes.centro_custo IS
  'De qual portal do profissional o valor sai. Obrigatório: quem tem 3 portais '
  'veria o mesmo desconto 3 vezes se isto ficasse em branco.';

COMMENT ON COLUMN public.honorarios_ajustes.descricao IS
  'O MÉDICO LÊ ESTE TEXTO. Escrever pensando nisso; o que for interno vai em '
  'observacao.';

COMMENT ON COLUMN public.honorarios_ajustes.valor IS
  'Sempre positivo. Quem decide o sinal é `tipo`.';

-- A tela sempre pergunta "o que tem neste mês?" e o publicador "o que tem
-- deste profissional neste mês?".
CREATE INDEX IF NOT EXISTS honorarios_ajustes_periodo_idx
  ON public.honorarios_ajustes (periodo_id, profissional);

ALTER TABLE public.honorarios_ajustes ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS honorarios_ajustes_read  ON public.honorarios_ajustes;
DROP POLICY IF EXISTS honorarios_ajustes_write ON public.honorarios_ajustes;

-- Mesma regra das demais tabelas de honorários: admin ou card 'honorarios'.
CREATE POLICY honorarios_ajustes_read ON public.honorarios_ajustes
  FOR SELECT TO authenticated
  USING (public.is_admin_user() OR public.has_card('honorarios'));

CREATE POLICY honorarios_ajustes_write ON public.honorarios_ajustes
  FOR ALL TO authenticated
  USING (public.is_admin_user() OR public.has_card('honorarios'))
  WITH CHECK (public.is_admin_user() OR public.has_card('honorarios'));
