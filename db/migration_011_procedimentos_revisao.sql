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
  ADD COLUMN IF NOT EXISTS observacao         text;

COMMENT ON COLUMN public.honorarios_procedimentos.revisado_em IS
  'Quando um humano confirmou esta categoria na tela. NULL = ainda veio do '
  'Excel sem conferência. É isso que separa "está certo" de "ninguém olhou".';

COMMENT ON COLUMN public.honorarios_procedimentos.categoria_anterior IS
  'O que a categoria era antes da revisão. Guardado para explicar diferença de '
  'repasse entre um fechamento e outro sem ter que garimpar histórico.';

-- Nota: o SVN tem um campo próprio de tipo de procedimento e ele NÃO entra
-- aqui. É justamente por ele ser inconsistente que as categorias desta casa
-- foram criadas. A tela de revisão se apoia só em dado nosso: quanto cada
-- procedimento move, o valor médio por lançamento e os percentuais que saíram.

-- Quem já foi revisado sai da fila de atenção; o índice serve à tela.
CREATE INDEX IF NOT EXISTS honorarios_procedimentos_revisao_idx
  ON public.honorarios_procedimentos (revisado_em NULLS FIRST, categoria);


-- ============================================================
-- 2. Categoria decidida por OS (procedimentos ambíguos)
-- ============================================================
-- Alguns nomes não permitem decidir a categoria pelo nome. O caso vivo é
-- "Laser": tanto pode ser Laser Transdérmico (categoria "Laser (clínica)",
-- 60%) quanto a fibra de laser usada em cirurgia (categoria "Cirurgia -
-- Hospital", 80% ou 90%). Só o contexto da OS resolve — quais outros
-- procedimentos foram lançados junto.
--
-- Essas 22 decisões existiam desde 03/08/2026 num dicionário Python
-- (`OVERRIDES_POR_OS`, em _honorarios_catalogo.py). Funcionavam, mas ficavam
-- invisíveis para quem usa o portal: não dava para ver o que foi decidido, nem
-- por quem, nem mudar sem editar código. É o oposto do que o card de
-- Fechamento existe para fazer.
--
-- A tabela é DE PROPÓSITO independente de período: a mesma OS parcelada volta
-- em vários meses e a decisão vale para todos. Por isso não entrou na fila de
-- exceções, que é por período.
CREATE TABLE IF NOT EXISTS public.honorarios_categoria_os (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  os_numero    text NOT NULL,
  chave        text NOT NULL,          -- procedimento normalizado
  procedimento text NOT NULL,          -- grafia original, para exibir
  categoria    text NOT NULL,
  motivo       text,                   -- o que na OS levou a essa conclusão
  paciente     text,
  profissional text,
  decidido_por text,
  decidido_em  timestamptz NOT NULL DEFAULT now(),
  criado_em    timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS honorarios_categoria_os_unica_idx
  ON public.honorarios_categoria_os (os_numero, chave);

COMMENT ON TABLE public.honorarios_categoria_os IS
  'Categoria resolvida caso a caso, quando o nome do procedimento não basta. '
  'Vale para todos os períodos em que a OS aparecer.';


-- ============================================================
-- 3. RLS — mesmo critério da 009/010
-- ============================================================
-- honorarios_procedimentos já está coberta: as políticas da 010 são FOR ALL
-- sobre a tabela inteira, então as colunas novas entram junto.
ALTER TABLE public.honorarios_categoria_os ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS honorarios_categoria_os_read  ON public.honorarios_categoria_os;
DROP POLICY IF EXISTS honorarios_categoria_os_write ON public.honorarios_categoria_os;

CREATE POLICY honorarios_categoria_os_read ON public.honorarios_categoria_os
  FOR SELECT TO authenticated
  USING (public.is_admin_user() OR public.has_card('honorarios'));

CREATE POLICY honorarios_categoria_os_write ON public.honorarios_categoria_os
  FOR ALL TO authenticated
  USING (public.is_admin_user() OR public.has_card('honorarios'))
  WITH CHECK (public.is_admin_user() OR public.has_card('honorarios'));
