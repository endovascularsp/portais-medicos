-- =====================================================================
-- FIX: completa 6 funcionários que já existiam antes do seed
-- =====================================================================
-- O 06_seed_funcionarios.sql usou ON CONFLICT (email) DO NOTHING, então
-- quem já existia foi pulado inteiro — ficou sem departamento e sem o
-- card compras_solicitante.
--
-- Este script:
--   - 5 pessoas: ADICIONA compras_solicitante (sem remover cards atuais)
--     + preenche o departamento
--   - Heloisa: corrige só o departamento (Concierge → Gestão); cards
--     intactos (ela já tem 'gestor')
--
-- NÃO toca em thiago.luiz@ nem drigor@ — eles não aparecem aqui.
-- O CASE em cards torna o script idempotente (rodar 2x não duplica).
-- =====================================================================

-- Angelina — Administrativo
UPDATE users SET
  departamento_id = (SELECT id FROM compras_departamentos WHERE nome='Administrativo'),
  cards = CASE WHEN 'compras_solicitante' = ANY(cards) THEN cards
               ELSE cards || ARRAY['compras_solicitante'] END
WHERE email = 'angelina.lima@endovascularsp.com.br';

-- Camily, Julia, Samanta — Recepção
UPDATE users SET
  departamento_id = (SELECT id FROM compras_departamentos WHERE nome='Recepção'),
  cards = CASE WHEN 'compras_solicitante' = ANY(cards) THEN cards
               ELSE cards || ARRAY['compras_solicitante'] END
WHERE email IN ('camily.nascimento@endovascularsp.com.br',
                'julia.beserra@endovascularsp.com.br',
                'samanta.neves@endovascularsp.com.br');

-- Solange — Cirurgias
UPDATE users SET
  departamento_id = (SELECT id FROM compras_departamentos WHERE nome='Cirurgias'),
  cards = CASE WHEN 'compras_solicitante' = ANY(cards) THEN cards
               ELSE cards || ARRAY['compras_solicitante'] END
WHERE email = 'solange.lucindo@endovascularsp.com.br';

-- Heloisa — só corrige a equipe. Cards intactos.
-- Era 'Gestão', mas a migration_005 aposentou essa equipe (ativo=false) e
-- moveu as 4 pessoas dela pra Administrativo. Se este script rodasse de novo
-- com 'Gestão', a Heloisa voltaria pra uma equipe inativa e sumiria dos
-- avisos direcionados do Mural.
UPDATE users SET
  departamento_id = (SELECT id FROM compras_departamentos WHERE nome='Administrativo')
WHERE email = 'heloisa.incontri@endovascularsp.com.br';
