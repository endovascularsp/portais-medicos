-- =====================================================================
-- Card de acesso 'confirmacao_agenda'
--
-- Portal que monta a planilha CSV de confirmação em massa da Envya a
-- partir da agenda do dia no Saudevianet.
--
-- Quem recebe: a equipe que já opera as Prévias (mesmo time de recepção /
-- agendamento que faz a confirmação hoje, um a um, na mão).
--
-- Quem NÃO recebe:
--   * role = 'medico'  -> médico com card de gestão trava no Gestor Hub e
--                         perde o redirect pro Hub próprio dele.
--   * quem tem 'gestor' -> já enxerga pelo guarda-chuva (função coberto()
--                          do Gestor_Hub.html), não precisa do card avulso.
--
-- Executar no Supabase SQL Editor.
-- =====================================================================

UPDATE users
SET cards = array_append(COALESCE(cards, '{}'), 'confirmacao_agenda')
WHERE COALESCE(cards, '{}') @> ARRAY['previas']
  AND NOT (COALESCE(cards, '{}') @> ARRAY['confirmacao_agenda'])
  AND NOT (COALESCE(cards, '{}') @> ARRAY['gestor'])
  AND COALESCE(role, '') <> 'medico';

-- Confere quem ficou com o card (deve listar a equipe de agendamento):
SELECT email, name, role, cards
FROM users
WHERE COALESCE(cards, '{}') @> ARRAY['confirmacao_agenda']
   OR COALESCE(cards, '{}') @> ARRAY['gestor']
ORDER BY role, email;
