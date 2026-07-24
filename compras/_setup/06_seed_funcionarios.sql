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
  ('faturamento@endovascularsp.com.br', 'Aluma Alves', 'funcionario', ARRAY['compras_solicitante'], (SELECT id FROM compras_departamentos WHERE nome='Faturamento')),
  ('atendimento.01@endovascularsp.com.br', 'Ana Luiza', 'funcionario', ARRAY['compras_solicitante'], (SELECT id FROM compras_departamentos WHERE nome='Agendamento')),
  ('angelina.lima@endovascularsp.com.br', 'Angelina Lima', 'funcionario', ARRAY['compras_solicitante'], (SELECT id FROM compras_departamentos WHERE nome='Administrativo')),
  ('camilla.gomes@endovascularsp.com.br', 'Camilla Gomes', 'funcionario', ARRAY['compras_solicitante'], (SELECT id FROM compras_departamentos WHERE nome='Enfermagem')),
  ('camily.nascimento@endovascularsp.com.br', 'Camily Nascimento', 'funcionario', ARRAY['compras_solicitante'], (SELECT id FROM compras_departamentos WHERE nome='Recepção')),
  ('carina.evangelista@endovascularsp.com.br', 'Carina Evangelista', 'funcionario', ARRAY['compras_solicitante'], (SELECT id FROM compras_departamentos WHERE nome='Concierge')),
  ('controladoria@endovascularsp.com.br', 'Cláudia Endovascular', 'funcionario', ARRAY['compras_solicitante'], (SELECT id FROM compras_departamentos WHERE nome='Cirurgias')),
  ('daniele.silva@endovascularsp.com.br', 'Daniele Silva', 'funcionario', ARRAY['compras_solicitante'], (SELECT id FROM compras_departamentos WHERE nome='Financeiro')),
  ('danielle.santos@endovascularsp.com.br', 'Danielle Santos', 'funcionario', ARRAY['compras_solicitante'], (SELECT id FROM compras_departamentos WHERE nome='Concierge')),
  ('heloisa.incontri@endovascularsp.com.br', 'Heloisa Incontri', 'admin', ARRAY['gestor'], (SELECT id FROM compras_departamentos WHERE nome='Gestão')),
  ('drigor@endovascularsp.com.br', 'Igor Rafael Sincos , M.D., Ph.D.', 'admin', ARRAY['gestor'], (SELECT id FROM compras_departamentos WHERE nome='Gestão')),
  ('josilene.lino@endovascularsp.com.br', 'Josilene Lino', 'funcionario', ARRAY['compras_solicitante'], (SELECT id FROM compras_departamentos WHERE nome='Enfermagem')),
  ('julia.beserra@endovascularsp.com.br', 'Julia Beserra', 'funcionario', ARRAY['compras_solicitante'], (SELECT id FROM compras_departamentos WHERE nome='Recepção')),
  ('juliana.olimpio@endovascularsp.com.br', 'Juliana Olimpio', 'funcionario', ARRAY['compras_solicitante'], (SELECT id FROM compras_departamentos WHERE nome='Enfermagem')),
  ('luana.specchio@endovascularsp.com.br', 'Luana Specchio', 'funcionario', ARRAY['compras_solicitante'], (SELECT id FROM compras_departamentos WHERE nome='Enfermagem')),
  ('mariana.rodrigues@endovascularsp.com.br', 'Mariana Rodrigues', 'funcionario', ARRAY['compras_solicitante'], (SELECT id FROM compras_departamentos WHERE nome='Enfermagem')),
  ('marketing@endovascularsp.com.br', 'Marketing EndovascularSP', 'funcionario', ARRAY['compras_solicitante'], (SELECT id FROM compras_departamentos WHERE nome='Marketing')),
  ('mayara.soares@endovascularsp.com.br', 'Mayara Soares', 'funcionario', ARRAY['compras_solicitante'], (SELECT id FROM compras_departamentos WHERE nome='Agendamento')),
  ('micaele.albuquerque@endovascularsp.com.br', 'Micaele Albuquerque', 'funcionario', ARRAY['compras_solicitante'], (SELECT id FROM compras_departamentos WHERE nome='Financeiro')),
  ('samanta.neves@endovascularsp.com.br', 'Samanta Neves', 'funcionario', ARRAY['compras_solicitante'], (SELECT id FROM compras_departamentos WHERE nome='Recepção')),
  ('solange.lucindo@endovascularsp.com.br', 'Solange Lucindo', 'funcionario', ARRAY['compras_solicitante'], (SELECT id FROM compras_departamentos WHERE nome='Cirurgias')),
  ('thiago.luiz@endovascularsp.com.br', 'Thiago Luiz', 'admin', ARRAY['gestor'], (SELECT id FROM compras_departamentos WHERE nome='Gestão'))
ON CONFLICT (email) DO NOTHING;
