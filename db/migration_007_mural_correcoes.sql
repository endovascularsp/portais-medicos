-- Migration 007: Mural — fecha 2 furos encontrados na varredura de 24/07/2026
-- 2026-07-24
--
-- FURO 1 (grave) — ANEXO VAZAVA PARA FORA DA EQUIPE
--   A migration_004 liberou o bucket 'mural-anexos' pra QUALQUER pessoa com o
--   card 'mural', sem olhar a equipe do aviso. Como o Supabase Storage deixa
--   listar o bucket, alguém de outra equipe conseguia:
--     sb.storage.from('mural-anexos').list('mural')   -> ve os nomes dos arquivos
--     sb.storage.from('mural-anexos').createSignedUrl(path)  -> baixa
--   Ou seja: o TEXTO do aviso ficava restrito, mas o ANEXO dele não. Um aviso
--   pro Financeiro com planilha de folha salarial vazava pra clínica inteira,
--   e o próprio nome do arquivo já entregava o assunto.
--   Correção: a leitura do anexo passa a exigir que exista um aviso VISÍVEL
--   apontando pra aquele arquivo (o EXISTS abaixo passa pela policy mural_read).
--
-- FURO 2 (médio) — GUARDA-CHUVA 'gestor' ENTRAVA E VIA FEED VAZIO
--   O Gestor Hub mostra o card do Mural pra quem tem o guarda-chuva 'gestor'
--   (Gestor_Hub.html, coberto() -> 'mural' retorna true) e o portal deixa
--   entrar com 'mural' OU 'gestor'. Mas a RLS exigia has_card('mural') puro.
--   Resultado: quem tinha só 'gestor' entrava, via "Nenhum aviso publicado
--   ainda" e tomava erro ao tentar publicar — sem nenhuma pista do motivo.
--   Correção: as policies passam a aceitar o guarda-chuva, igual ao Hub.

-- ============================================================
-- 1. Helper: quem tem acesso ao Mural (card próprio ou guarda-chuva)
-- ============================================================
CREATE OR REPLACE FUNCTION public.pode_mural() RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = public
AS $$
  SELECT public.has_card('mural') OR public.has_card('gestor')
$$;

-- ============================================================
-- 2. Avisos — troca has_card('mural') pelo helper. A regra de EQUIPE
--    (pode_ver_aviso, migration_005) continua valendo por cima.
-- ============================================================
DROP POLICY IF EXISTS "mural_read" ON public.mural_avisos;
CREATE POLICY "mural_read" ON public.mural_avisos
  FOR SELECT TO authenticated
  USING (public.pode_mural() AND public.pode_ver_aviso(equipes, autor_email));

DROP POLICY IF EXISTS "mural_insert" ON public.mural_avisos;
CREATE POLICY "mural_insert" ON public.mural_avisos
  FOR INSERT TO authenticated
  WITH CHECK (public.pode_mural() AND autor_email = (auth.jwt() ->> 'email'));

-- ============================================================
-- 3. Reações e comentários — mesma troca. A herança de visibilidade
--    (EXISTS em mural_avisos) já foi feita na migration_005.
-- ============================================================
DROP POLICY IF EXISTS "mr_insert" ON public.mural_reacoes;
CREATE POLICY "mr_insert" ON public.mural_reacoes FOR INSERT TO authenticated
  WITH CHECK (
    public.pode_mural()
    AND autor_email = (auth.jwt() ->> 'email')
    AND EXISTS (SELECT 1 FROM public.mural_avisos a WHERE a.id = aviso_id)
  );

DROP POLICY IF EXISTS "mc_insert" ON public.mural_comentarios;
CREATE POLICY "mc_insert" ON public.mural_comentarios FOR INSERT TO authenticated
  WITH CHECK (
    public.pode_mural()
    AND autor_email = (auth.jwt() ->> 'email')
    AND EXISTS (SELECT 1 FROM public.mural_avisos a WHERE a.id = aviso_id)
  );

DROP POLICY IF EXISTS "mv_insert" ON public.mural_visualizacoes;
CREATE POLICY "mv_insert" ON public.mural_visualizacoes FOR INSERT TO authenticated
  WITH CHECK (
    public.pode_mural()
    AND viewer_email = (auth.jwt() ->> 'email')
    AND EXISTS (SELECT 1 FROM public.mural_avisos a WHERE a.id = aviso_id)
  );

-- ============================================================
-- 4. FURO 1 — anexo herda a visibilidade do aviso
--    storage.objects.name é o caminho dentro do bucket ('mural/<ts>_<arquivo>'),
--    que é exatamente o que o portal grava em mural_avisos.anexo_path.
-- ============================================================
DROP POLICY IF EXISTS "mural_anexo_read" ON storage.objects;
CREATE POLICY "mural_anexo_read" ON storage.objects
  FOR SELECT TO authenticated
  USING (
    bucket_id = 'mural-anexos'
    AND public.pode_mural()
    AND EXISTS (
      SELECT 1 FROM public.mural_avisos a
      WHERE a.anexo_path = storage.objects.name
    )
  );

-- O envio continua liberado pra quem acessa o Mural: o upload acontece ANTES
-- de o aviso existir, então não dá pra amarrar o INSERT a um aviso visível.
DROP POLICY IF EXISTS "mural_anexo_insert" ON storage.objects;
CREATE POLICY "mural_anexo_insert" ON storage.objects
  FOR INSERT TO authenticated
  WITH CHECK (bucket_id = 'mural-anexos' AND public.pode_mural());

-- ============================================================
-- 5. Conferência
-- ============================================================
-- Quem tinha o guarda-chuva sem o card (eram esses que viam feed vazio):
--   SELECT email, name, cards FROM users
--    WHERE 'gestor' = ANY(cards) AND NOT ('mural' = ANY(cards));
--
-- Anexos órfãos (upload que ficou sem aviso — agora ninguém lê, pode limpar):
--   SELECT o.name FROM storage.objects o
--    WHERE o.bucket_id = 'mural-anexos'
--      AND NOT EXISTS (SELECT 1 FROM mural_avisos a WHERE a.anexo_path = o.name);
