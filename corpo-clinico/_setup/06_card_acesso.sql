-- =====================================================================
-- Card de acesso 'corpo_clinico'
-- O portal Corpo Clínico nasceu aberto a todos; agora virou card
-- controlável na Gestão de Acessos. Este UPDATE dá o card aos
-- funcionários atuais pra ninguém perder o acesso.
--
-- Quem tem 'gestor' já é coberto pelo guarda-chuva — não recebe o card.
-- Thiago e Dr. Igor preservados explicitamente (não alterar permissões).
-- Executar no Supabase SQL Editor.
-- =====================================================================

UPDATE users
SET cards = array_append(COALESCE(cards, '{}'), 'corpo_clinico')
WHERE NOT (COALESCE(cards, '{}') @> ARRAY['corpo_clinico'])
  AND NOT (COALESCE(cards, '{}') @> ARRAY['gestor'])
  AND email NOT IN ('thiago.luiz@endovascularsp.com.br', 'drigor@endovascularsp.com.br');
