-- Migration 011: Honorários — revisão do catálogo de procedimentos
-- 2026-08-10
--
-- CONTEXTO
-- A categoria do procedimento decide o percentual, e o catálogo inteiro veio da
-- aba "Apoio" do Excel (`origem = 'apoio_excel'`) sem ninguém nunca ter olhado
-- linha a linha. Em 10/08/2026 apareceram quatro rótulos errados de uma vez:
--
--   Morpheus ................................ marcado como Cirurgia - Hospital
--   Visita hospitalar (paciente internado) .. marcado como Cirurgia - Hospital
--   Laser / Laser - Pacote .................. marcado como Cirurgia - Hospital
--   Radiofrequência ......................... marcado como Cirurgia - Hospital
--
-- O rótulo de cirurgia hospitalar não é cosmético: ele desvia o cálculo da regra
-- de categoria (percentual fixo) para a regra de cirurgia, que pergunta quem
-- trouxe o paciente e paga 80% ou 90%. Uma visita hospitalar de R$ 50 estava
-- sendo repartida como se fosse cirurgia.
--
-- Corrigir no console resolve o caso e não impede o próximo. Estas colunas
-- existem para que a decisão seja tomada na tela do card de Fechamento, fique
-- assinada e não precise ser tomada de novo.
--
-- NÃO altera nenhuma categoria. Só cria o espaço para registrar a revisão.
-- Depende de: migration_010.

ALTER TABLE public.honorarios_procedimentos
  ADD COLUMN IF NOT EXISTS revisado_em        timestamptz,
  ADD COLUMN IF NOT EXISTS revisado_por       text,
  ADD COLUMN IF NOT EXISTS categoria_anterior text,
  ADD COLUMN IF NOT EXISTS observacao         text,
  ADD COLUMN IF NOT EXISTS tipo_svn           text;

COMMENT ON COLUMN public.honorarios_procedimentos.revisado_em IS
  'Quando um humano confirmou esta categoria na tela. NULL = ainda veio do '
  'Excel sem conferência. É isso que separa "está certo" de "ninguém olhou".';

COMMENT ON COLUMN public.honorarios_procedimentos.categoria_anterior IS
  'O que a categoria era antes da revisão. Guardado para explicar diferença de '
  'repasse entre um fechamento e outro sem ter que garimpar histórico.';

COMMENT ON COLUMN public.honorarios_procedimentos.tipo_svn IS
  'Como o Saudevianet classifica o mesmo procedimento (Cirurgia, Consulta, '
  'Procedimentos, PDT, Exame, RET). NÃO é fonte da verdade — o SVN chama '
  'Morpheus de "PDT" e cirurgia de varizes de "Procedimentos". Serve só como '
  'segunda opinião na tela de revisão.';

-- Quem já foi revisado sai da fila de atenção; o índice serve à tela.
CREATE INDEX IF NOT EXISTS honorarios_procedimentos_revisao_idx
  ON public.honorarios_procedimentos (revisado_em NULLS FIRST, categoria);

-- RLS: as políticas da 010 são FOR ALL sobre a tabela inteira, então as colunas
-- novas já entram cobertas. Nada a fazer aqui.
