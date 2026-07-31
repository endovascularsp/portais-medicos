-- Migration 008: Mural — notificação por e-mail
-- 2026-07-30
--
-- CONTEXTO
-- Até aqui o Mural era 100% "pull": o aviso só chegava em quem resolvesse abrir
-- o portal. Quem não entrava, não ficava sabendo. Esta migration cria a base do
-- "push": ao publicar, quem é da equipe marcada recebe um e-mail com o TÍTULO e
-- um botão pro Mural.
--
-- O e-mail NUNCA leva o corpo do aviso nem o anexo — só a chamada e o link.
-- Dois motivos:
--   1. Privacidade — o aviso é restrito por equipe dentro do portal, mas e-mail
--      se encaminha. O texto completo sairia do controle da RLS (mesma lição do
--      furo do anexo, migration_007).
--   2. Métrica — se a pessoa lê tudo no e-mail, ela não entra no Mural e o
--      contador "👁 quem viu" para de significar "quem leu".
--
-- ATENÇÃO À DIFERENÇA ENTRE **VER** E **RECEBER**:
--   VER o aviso (pode_ver_aviso, migration_005): admin vê tudo, autor vê o
--     próprio, mais 'todos' e a equipe marcada.
--   RECEBER e-mail (esta migration): SÓ 'todos' ou a equipe marcada, menos o
--     autor. Admin NÃO é notificado de aviso que não é da equipe dele — senão os
--     7 admins receberiam e-mail de todo recado de toda equipe e parariam de ler.
--     Eles continuam vendo tudo ao abrir o portal.
--
-- Depende de: migration_001 (has_card/is_admin_user), 002/003 (mural),
--             005 (equipes + pode_ver_aviso), 007 (pode_mural).

-- ============================================================
-- 1. O aviso registra se pediu notificação
--    (checkbox do modal, marcado por padrão — serve de histórico:
--     "esse aviso foi só pro feed" x "esse foi por e-mail também")
-- ============================================================
ALTER TABLE public.mural_avisos
  ADD COLUMN IF NOT EXISTS notificar_email boolean NOT NULL DEFAULT true;

-- ============================================================
-- 2. Log de envios
--    Quem escreve aqui é SÓ a Edge Function (service_role) — por isso não
--    existe policy de INSERT/UPDATE/DELETE pra 'authenticated'. Sem policy,
--    a RLS nega; o service_role passa por cima da RLS por definição.
--    Serve pra três coisas: não enviar duas vezes, mostrar "📧 5" no rodapé
--    do aviso pro autor, e segurar a cobrança em 1 por dia.
-- ============================================================
CREATE TABLE IF NOT EXISTS public.mural_emails (
  id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  aviso_id           uuid NOT NULL REFERENCES public.mural_avisos(id) ON DELETE CASCADE,
  tipo               text NOT NULL CHECK (tipo IN ('novo_aviso', 'comentario', 'cobranca')),
  destinatario_email text NOT NULL,
  destinatario_nome  text,
  status             text NOT NULL DEFAULT 'enviado' CHECK (status IN ('enviado', 'erro')),
  erro               text,
  provider_id        text,          -- id da mensagem no Resend, pra rastrear entrega
  created_at         timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS mural_emails_aviso_idx ON public.mural_emails (aviso_id, tipo, created_at DESC);

ALTER TABLE public.mural_emails ENABLE ROW LEVEL SECURITY;

-- Ler o log: só o autor do aviso ou admin. NÃO usar EXISTS simples em
-- mural_avisos aqui — isso passaria pela mural_read e deixaria qualquer colega
-- de equipe ver a lista de destinatários.
DROP POLICY IF EXISTS "me_read" ON public.mural_emails;
CREATE POLICY "me_read" ON public.mural_emails
  FOR SELECT TO authenticated
  USING (
    public.is_admin_user()
    OR EXISTS (
      SELECT 1 FROM public.mural_avisos a
      WHERE a.id = aviso_id AND a.autor_email = (auth.jwt() ->> 'email')
    )
  );

-- ============================================================
-- 3. Quem recebe — o coração da coisa
--    Uma equipe = compras_departamentos.slug (tabela única de equipes).
--    p_excluir_email tira o autor da própria lista.
-- ============================================================
CREATE OR REPLACE FUNCTION public.mural_destinatarios(p_equipes text[], p_excluir_email text)
RETURNS TABLE (email text, nome text)
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = public
AS $$
  SELECT u.email, COALESCE(u.name, split_part(u.email, '@', 1))
  FROM users u
  LEFT JOIN compras_departamentos d ON d.id = u.departamento_id
  WHERE
    -- tem acesso ao Mural (card próprio ou guarda-chuva, igual ao pode_mural)
    ('mural' = ANY(COALESCE(u.cards, '{}'::text[])) OR 'gestor' = ANY(COALESCE(u.cards, '{}'::text[])))
    -- médico nunca é notificado, mesmo que ganhe o card por engano:
    -- ele não tem link pro Mural no Hub dele e receberia um e-mail sem destino
    AND COALESCE(u.role, '') <> 'medico'
    AND u.email IS DISTINCT FROM lower(COALESCE(p_excluir_email, ''))
    AND (
      'todos' = ANY(p_equipes)
      OR (d.slug IS NOT NULL AND d.slug = ANY(p_equipes))
    )
  ORDER BY 1
$$;

-- Destinatários de um aviso concreto (usada pela Edge Function, com service_role).
CREATE OR REPLACE FUNCTION public.mural_destinatarios_aviso(p_aviso_id uuid)
RETURNS TABLE (email text, nome text)
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = public
AS $$
  SELECT d.email, d.nome
  FROM mural_avisos a
  CROSS JOIN LATERAL public.mural_destinatarios(a.equipes, a.autor_email) d
  WHERE a.id = p_aviso_id
$$;

-- Quem devia ter lido e ainda não abriu o Mural. Base do botão "cobrar".
CREATE OR REPLACE FUNCTION public.mural_nao_leram(p_aviso_id uuid)
RETURNS TABLE (email text, nome text)
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = public
AS $$
  SELECT d.email, d.nome
  FROM public.mural_destinatarios_aviso(p_aviso_id) d
  WHERE NOT EXISTS (
    SELECT 1 FROM mural_visualizacoes v
    WHERE v.aviso_id = p_aviso_id AND v.viewer_email = d.email
  )
$$;

-- As três acima são SECURITY DEFINER e devolvem NOMES E E-MAILS de gente —
-- não podem ficar abertas. Só o service_role (Edge Function) chama.
REVOKE EXECUTE ON FUNCTION public.mural_destinatarios(text[], text)   FROM PUBLIC, anon, authenticated;
REVOKE EXECUTE ON FUNCTION public.mural_destinatarios_aviso(uuid)     FROM PUBLIC, anon, authenticated;
REVOKE EXECUTE ON FUNCTION public.mural_nao_leram(uuid)               FROM PUBLIC, anon, authenticated;

-- ============================================================
-- 4. Contadores pro portal
--    O portal precisa dizer "vai notificar 5 pessoas" ANTES de o aviso existir,
--    e "3 ainda não leram" depois. Devolvem só NÚMERO, nunca a lista.
-- ============================================================
-- Prévia no modal: quantas pessoas seriam notificadas por essa combinação de equipes.
CREATE OR REPLACE FUNCTION public.mural_contar_destinatarios(p_equipes text[])
RETURNS integer
LANGUAGE plpgsql STABLE SECURITY DEFINER
SET search_path = public
AS $$
DECLARE n integer;
BEGIN
  IF NOT public.pode_mural() THEN RETURN 0; END IF;
  SELECT count(*) INTO n
  FROM public.mural_destinatarios(p_equipes, auth.jwt() ->> 'email');
  RETURN n;
END;
$$;

-- Quantos ainda não leram — só o autor do aviso ou admin.
CREATE OR REPLACE FUNCTION public.mural_contar_nao_leram(p_aviso_id uuid)
RETURNS integer
LANGUAGE plpgsql STABLE SECURITY DEFINER
SET search_path = public
AS $$
DECLARE n integer;
BEGIN
  IF NOT (
    public.is_admin_user()
    OR EXISTS (SELECT 1 FROM mural_avisos a
                WHERE a.id = p_aviso_id AND a.autor_email = (auth.jwt() ->> 'email'))
  ) THEN
    RETURN 0;
  END IF;
  SELECT count(*) INTO n FROM public.mural_nao_leram(p_aviso_id);
  RETURN n;
END;
$$;

REVOKE EXECUTE ON FUNCTION public.mural_contar_destinatarios(text[]) FROM PUBLIC, anon;
REVOKE EXECUTE ON FUNCTION public.mural_contar_nao_leram(uuid)       FROM PUBLIC, anon;
GRANT  EXECUTE ON FUNCTION public.mural_contar_destinatarios(text[]) TO authenticated;
GRANT  EXECUTE ON FUNCTION public.mural_contar_nao_leram(uuid)       TO authenticated;

-- ============================================================
-- 5. Conferência — rode depois e leia o resultado
-- ============================================================
-- Quantas pessoas receberiam um aviso "pra Todos" (deve bater com o nº de
-- funcionários não-médicos com acesso ao Mural):
--   SELECT count(*) FROM mural_destinatarios(ARRAY['todos'], NULL);
--
-- E um aviso só pra Enfermagem:
--   SELECT * FROM mural_destinatarios(ARRAY['enfermagem'], NULL);
--
-- Gente com acesso ao Mural mas SEM equipe (só vai receber e-mail de 'Todos'):
--   SELECT u.email, u.name FROM users u
--    WHERE ('mural' = ANY(u.cards) OR 'gestor' = ANY(u.cards))
--      AND COALESCE(u.role,'') <> 'medico' AND u.departamento_id IS NULL;
--
-- Últimos e-mails disparados:
--   SELECT e.created_at, e.tipo, e.status, e.destinatario_email, a.titulo
--     FROM mural_emails e JOIN mural_avisos a ON a.id = e.aviso_id
--    ORDER BY e.created_at DESC LIMIT 50;
