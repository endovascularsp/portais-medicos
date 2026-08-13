-- Migration 012: Honorários — registro das execuções da rotina
-- 2026-08-13
--
-- CONTEXTO
-- Até aqui, pôr a base do mês em dia era alguém abrir um terminal e rodar
-- `_honorarios_fechar.py`. O processo já estava todo escrito; o que era manual
-- era apertar o start — e ninguém além de quem rodou sabia se tinha rodado,
-- quando, e no que deu.
--
-- Esta tabela é o que a tela do card de Fechamento lê para mostrar
-- "atualizado hoje às 03:12 · 4 divergências esperando decisão". Serve tanto
-- para a rotina automática da madrugada quanto para o botão "Atualizar base".
--
-- SEPARAÇÃO QUE IMPORTA (decisão do Thiago em 13/08/2026)
--   tipo='base'       busca no Saudevianet, calcula e enche a fila de
--                     divergências. NÃO encosta em portal de médico.
--   tipo='publicacao' reescreve os portais. É ato deliberado, nunca automático.
--
-- O motivo é o mês em aberto ser verdade parcial: compensação ainda está
-- chegando, e o médico não pode ver número mudando sozinho no meio do mês.
--
-- Depende de: migration_010 (is_admin_user / has_card já existem).

CREATE TABLE IF NOT EXISTS public.honorarios_execucoes (
  id                    bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  tipo                  text        NOT NULL CHECK (tipo IN ('base', 'publicacao')),
  periodo_id            text        NOT NULL,
  status                text        NOT NULL DEFAULT 'enfileirado'
                          CHECK (status IN ('enfileirado', 'rodando', 'ok',
                                            'divergencias', 'erro')),
  -- E-mail de quem clicou, ou 'rotina' quando foi a madrugada.
  disparado_por         text        NOT NULL DEFAULT 'rotina',
  iniciado_em           timestamptz NOT NULL DEFAULT now(),
  terminado_em          timestamptz,
  divergencias_abertas  integer,
  lancamentos           integer,
  mensagem              text,
  criado_em             timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.honorarios_execucoes IS
  'Uma linha por rodada da rotina de honorários. É o que a tela mostra como '
  '"última atualização". Nunca guarda dado de paciente nem de dinheiro por '
  'linha — só o resumo do que a rodada fez.';

COMMENT ON COLUMN public.honorarios_execucoes.status IS
  'divergencias NÃO é erro: é o processo pedindo decisão humana. A rotina '
  'termina com sucesso e deixa a fila esperando alguém no portal.';

-- A tela sempre pergunta "e a última?" — por tipo e por período.
CREATE INDEX IF NOT EXISTS honorarios_execucoes_recentes_idx
  ON public.honorarios_execucoes (tipo, iniciado_em DESC);

ALTER TABLE public.honorarios_execucoes ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS honorarios_execucoes_read  ON public.honorarios_execucoes;
DROP POLICY IF EXISTS honorarios_execucoes_write ON public.honorarios_execucoes;

CREATE POLICY honorarios_execucoes_read ON public.honorarios_execucoes
  FOR SELECT TO authenticated
  USING (public.is_admin_user() OR public.has_card('honorarios'));

-- Quem pode ver a tela pode pedir uma atualização. Quem EXECUTA é a rotina,
-- com a service key, que ignora RLS — esta policy cobre só o pedido saindo
-- da tela.
CREATE POLICY honorarios_execucoes_write ON public.honorarios_execucoes
  FOR INSERT TO authenticated
  WITH CHECK (public.is_admin_user() OR public.has_card('honorarios'));
