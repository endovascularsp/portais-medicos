-- =====================================================================
-- SEED FUNCIONÁRIOS — cadastro em massa (23 pessoas)
-- Gerado de User_Download_20052026_231213_File.xlsx
-- =====================================================================

-- 1) Departamentos faltantes (ON CONFLICT evita duplicar os 6 do seed)
INSERT INTO compras_departamentos (nome) VALUES
  ('Administrativo'),
  ('Agendamento'),
  ('Cirurgias'),
  ('Concierge'),
  ('Enfermagem'),
  ('Faturamento'),
  ('Financeiro'),
  ('Gestão'),
  ('Marketing'),
  ('Recepção')
ON CONFLICT (nome) DO NOTHING;

-- 2) Funcionários. ON CONFLICT (email) DO NOTHING preserva quem já existe.
INSERT INTO users (email, name, role, cards, departamento_id) VALUES
  ('adriana.santana@endovascularsp.com.br', 'Adriana Santana', 'admin', ARRAY['gestor'], (SELECT id FROM compras_departamentos WHERE nome='Gestão')),
  ('faturamento@endovascularsp.com.br', 'Aluma Alves', 'recepcao', ARRAY['compras_solicitante'], (SELECT id FROM compras_departamentos WHERE nome='Faturamento')),
  ('atendimento.01@endovascularsp.com.br', 'Ana Luiza', 'recepcao', ARRAY['compras_solicitante'], (SELECT id FROM compras_departamentos WHERE nome='Agendamento')),
  ('angelina.lima@endovascularsp.com.br', 'Angelina Lima', 'recepcao', ARRAY['compras_solicitante'], (SELECT id FROM compras_departamentos WHERE nome='Administrativo')),
  ('camilla.gomes@endovascularsp.com.br', 'Camilla Gomes', 'recepcao', ARRAY['compras_solicitante'], (SELECT id FROM compras_departamentos WHERE nome='Enfermagem')),
  ('camily.nascimento@endovascularsp.com.br', 'Camily Nascimento', 'recepcao', ARRAY['compras_solicitante'], (SELECT id FROM compras_departamentos WHERE nome='Recepção')),
  ('carina.evangelista@endovascularsp.com.br', 'Carina Evangelista', 'recepcao', ARRAY['compras_solicitante'], (SELECT id FROM compras_departamentos WHERE nome='Concierge')),
  ('controladoria@endovascularsp.com.br', 'Cláudia Endovascular', 'recepcao', ARRAY['compras_solicitante'], (SELECT id FROM compras_departamentos WHERE nome='Cirurgias')),
  ('daniele.silva@endovascularsp.com.br', 'Daniele Silva', 'recepcao', ARRAY['compras_solicitante'], (SELECT id FROM compras_departamentos WHERE nome='Financeiro')),
  ('danielle.santos@endovascularsp.com.br', 'Danielle Santos', 'recepcao', ARRAY['compras_solicitante'], (SELECT id FROM compras_departamentos WHERE nome='Concierge')),
  ('heloisa.incontri@endovascularsp.com.br', 'Heloisa Incontri', 'admin', ARRAY['gestor'], (SELECT id FROM compras_departamentos WHERE nome='Gestão')),
  ('drigor@endovascularsp.com.br', 'Igor Rafael Sincos , M.D., Ph.D.', 'admin', ARRAY['gestor'], (SELECT id FROM compras_departamentos WHERE nome='Gestão')),
  ('josilene.lino@endovascularsp.com.br', 'Josilene Lino', 'recepcao', ARRAY['compras_solicitante'], (SELECT id FROM compras_departamentos WHERE nome='Enfermagem')),
  ('julia.beserra@endovascularsp.com.br', 'Julia Beserra', 'recepcao', ARRAY['compras_solicitante'], (SELECT id FROM compras_departamentos WHERE nome='Recepção')),
  ('juliana.olimpio@endovascularsp.com.br', 'Juliana Olimpio', 'recepcao', ARRAY['compras_solicitante'], (SELECT id FROM compras_departamentos WHERE nome='Enfermagem')),
  ('luana.specchio@endovascularsp.com.br', 'Luana Specchio', 'recepcao', ARRAY['compras_solicitante'], (SELECT id FROM compras_departamentos WHERE nome='Enfermagem')),
  ('mariana.rodrigues@endovascularsp.com.br', 'Mariana Rodrigues', 'recepcao', ARRAY['compras_solicitante'], (SELECT id FROM compras_departamentos WHERE nome='Enfermagem')),
  ('marketing@endovascularsp.com.br', 'Marketing EndovascularSP', 'recepcao', ARRAY['compras_solicitante'], (SELECT id FROM compras_departamentos WHERE nome='Marketing')),
  ('mayara.soares@endovascularsp.com.br', 'Mayara Soares', 'recepcao', ARRAY['compras_solicitante'], (SELECT id FROM compras_departamentos WHERE nome='Agendamento')),
  ('micaele.albuquerque@endovascularsp.com.br', 'Micaele Albuquerque', 'recepcao', ARRAY['compras_solicitante'], (SELECT id FROM compras_departamentos WHERE nome='Financeiro')),
  ('samanta.neves@endovascularsp.com.br', 'Samanta Neves', 'recepcao', ARRAY['compras_solicitante'], (SELECT id FROM compras_departamentos WHERE nome='Recepção')),
  ('solange.lucindo@endovascularsp.com.br', 'Solange Lucindo', 'recepcao', ARRAY['compras_solicitante'], (SELECT id FROM compras_departamentos WHERE nome='Cirurgias')),
  ('thiago.luiz@endovascularsp.com.br', 'Thiago Luiz', 'admin', ARRAY['gestor'], (SELECT id FROM compras_departamentos WHERE nome='Gestão'))
ON CONFLICT (email) DO NOTHING;
