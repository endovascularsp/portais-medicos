-- SEED — Portal Corpo Clínico (gerado de Planilha Geral + Mapa de Sala)

-- 1) Salas
INSERT INTO cc_salas (id, nome, tipo, ordem) VALUES
  (1, 'Consultório 1 US', 'consultorio', 1),
  (2, 'Consultório  2 US e WC', 'consultorio', 2),
  (3, 'Consultório  3 US', 'consultorio', 3),
  (4, 'Consultório  4 US', 'consultorio', 4),
  (5, 'Consultório  5 (externo)', 'consultorio', 5),
  (6, 'Consultório  6 WC', 'consultorio', 6),
  (7, 'Sala de Procedimento 1 US', 'procedimento', 7),
  (8, 'Sala de Procedimentos 2 US e Laser', 'procedimento', 8),
  (9, 'SPA', 'spa', 9),
  (10, 'Fotona', 'fotona', 10);

-- 2) Profissionais
INSERT INTO cc_profissionais (id, nome, especialidade, empresa, atende_online,
  atende_convenio, tempo_primeira_vez, tempo_retorno, valor_consulta, faixa_idade,
  conselho, conselho_numero, rqe, cpf, celular, email, instagram, observacoes) VALUES
  (1, 'Augusto Caparica', 'Urologista', 'Endovascular', TRUE, FALSE, '50 min', '20 min', 1200.0, 'A partir dos 14 anos', 'CRM', '111113', '43500.0', '079.221.337-82', '11985693747', 'a.caparica@hotmail.com', 'draugustocaparica', 'Quarta das 13:00 às 17:00'),
  (2, 'Andrea Klepacs', 'Cirurgiã Vascular', 'Endovascular', TRUE, FALSE, '1 hora', '45 min', 1200.0, 'A partir dos 15 anos', 'CRM', '128575', '51419.0', '041.774.209-64', '11 99417-1335', 'andreaklepacz@hotmail.com', 'dra.andreaklepacs', 'Segundas e terças integral, quarta e quinta dàs 08h30 às 13h00'),
  (3, 'Carolina Mardegan', 'Cirurgiã Vascular', 'Endovascular', TRUE, TRUE, '1 hora', '1 hora', 900.0, 'A partir dos 15 anos', 'CRM', '155653', '85754.0', '066.592.316-33', '11997899498', 'carolmardegan@hotmail.com', 'carol.mardegan', 'Quarta-feira integral'),
  (4, 'Christiane Inoue', 'Dermatologista', 'Endovascular', TRUE, FALSE, '1 hora 15', '45 min', 900.0, 'Todas as idades', 'CRM', '156013', '96474 / 77770', '336.144.478-04', '11976765454', 'christiane.lopess@gmail.com', 'drachris.inoue.dermato', 'Todos os dias'),
  (5, 'Clara Freitas', 'Cirurgiã Vascular', 'Endovascular', TRUE, TRUE, '1 hora', '45 min', 900.0, 'Todas as idades', 'CRM', '205328', '123529 / 1235291', '81.144.684-08', '8499925484', 'sfreitasclara@gmail.com', 'dra.clarafreitas_', 'Quinta-feira das 14:00 às 19:00'),
  (6, 'Daniela Viese', 'Cirurgiã Vascular', 'Endovascular', TRUE, FALSE, '45 min', '30 min', 990.0, 'A partir dos 15 anos', 'CRM', '166762', 'Não tem', '056.212.529-93', '11984452008', 'daniellaroth@gmail.com', 'danivieseroth', 'Segunda integral - conflito de sala com Chris'),
  (7, 'Eduardo Pires', 'Ortopedista', 'Endovascular', TRUE, FALSE, '1 hora', '1 hora', 600.0, 'Todas as idades', 'CRM', '161919', '79114.0', '330.290.778-88', '11982074554', 'dreduardoaraujopires@gmail.com', 'dreduardopires', 'Terça - das 08:30 às 12:00'),
  (8, 'Fernanda Liporaci', 'Fisioterapeuta', 'Endovascular', TRUE, FALSE, '1 hora', '1 hora', 480.0, 'A partir dos 18 anos', 'CREFITO', '68977', 'Não tem', '088.098.427-90', '11930631047', 'fer31liporaci@gmail.com', 'fisiofernandaliporaci', 'Terça 08:30 às 16:00 e quinta das 11:00 às 18:00'),
  (9, 'Gustavo Resstel', 'Cirurgião Vascular', 'Endovascular', TRUE, TRUE, '45 min', '30 min', 900.0, 'Todas as idades', 'CRM', '241025', '109806.0', '037.939.531-22', '11912880528', 'contato@gustavoresstel.com', 'dr.gustavoresstel', 'Terça das 14:00 às 19:00'),
  (10, 'Igor Rafael Sincos', 'Cirurgião Vascular', 'Endovascular', TRUE, TRUE, '45 min', '30 min', 1200.0, 'Todas as idades', 'CRM', '117876', '126825.0', '004.980.609-26', '11984477382', 'drigor@endovascularsp.com.br', 'drigor_sincos', 'Segunda, terça e quinta integral 08:30 às 19:00'),
  (11, 'João Fukuda', 'Cirurgião Vascular', 'Endovascular', TRUE, TRUE, '45 min', '30 min', 900.0, 'A partir dos 12 anos', 'CRM', '47514', '94184 / 108815', '447.487.959-72', '11992291745', 'jtfukuda@gmail.com', 'dr.joaofukuda', 'Segunda e quarta integral 08:30 às 19:00'),
  (12, 'Jonathan Batista', 'Cardiologista', 'Endovascular', TRUE, FALSE, '1 hora', '30 min', 900.0, 'A partir dos 08 anos', 'CRM', '141563', '63278 / 622781', '049.703.886-28', '11965961577', 'jbatisouza@yahoo.com.br', 'dr.jonathan_souza', 'Realiza Eco, eletro, doppler de carótidas, Mapa, Holter'),
  (13, 'Manoel Augusto Lobato', 'Cirurgião Vascular', 'Endovascular', TRUE, TRUE, '45 min', '30 min', 900.0, 'Todas as idades', 'CRM', '112088', '35971.0', '288.429.208-00', '11984841516', 'lobatocirurgiavascular@gmail.com', 'drmanoellobato', 'Quarta e sexta das 14:00 às 19:00'),
  (14, 'Maria Fernanda', 'Nutricionista', 'Endovascular', TRUE, FALSE, '60 min', '30min', 500.0, 'A partir dos 12 anos', 'CRN', '11238', 'Não tem', '358.129.988-76', '4799006282', 'Contatofefenutri@gmail.com', 'fernandafernandes.nutri', 'Definir mapa de sala'),
  (15, 'Mateus Nogueira', 'Médico do Esporte', 'Endovascular', TRUE, FALSE, '1 hora 30', '30 min', 1200.0, 'A partir dos 12 anos', 'CRM', '97070', '46345.0', '274.116.338-36', '11998911235', 'mateusnogueira@msn.com', 'drmateus.nogueira', 'Segunda, quinta e sexta - integral'),
  (16, 'Paulo Laredo', 'Cirurgião Vascular', 'Endovascular', FALSE, FALSE, '1 hora', '1 hora', 2000.0, 'Todas as idades', 'CRM', '128011', '134211.0', '68548800259.0', '9284419775', 'paulolaredopinto@yahoo.com.br', 'paulolaredo.vascular', '1 semana por mês'),
  (17, 'Simone Matsuda', 'Endocrinologista', 'Endovascular', TRUE, FALSE, '1 hora 30', '50 min', 1780.0, 'A partir dos 15 anos', 'CRM', '120781', '140563.0', '223.387.588-54', '11982170018', 'simone.matsuda@gmail.com', 'drasimonematsuda', 'Segunda das 14:00 às 19:00 - terça integral'),
  (18, 'Juliana Olimpio', 'Fisioterapeuta', 'Endovascular', NULL, NULL, NULL, NULL, NULL, NULL, 'CREFITO', NULL, NULL, NULL, NULL, NULL, NULL, '[só no Mapa de Sala — ficha a completar]'),
  (19, 'Julia Bargieri', 'Nutricionista CRN', 'Endovascular', NULL, NULL, NULL, NULL, NULL, NULL, 'CRN', NULL, NULL, NULL, NULL, NULL, NULL, '[só no Mapa de Sala — ficha a completar]');

-- 3) Escala (grade do Mapa de Sala). hora_fim fica NULL — Agendamento confirma.
INSERT INTO cc_escala (profissional_id, sala_id, dia_semana, hora_inicio) VALUES
  (10, 1, 1, '08:30'),
  (11, 2, 1, '08:30'),
  (2, 3, 1, '08:30'),
  (15, 6, 1, '08:30'),
  (18, 10, 1, '08:30'),
  (4, 5, 1, '13:00'),
  (17, 4, 1, '14:00'),
  (10, 1, 2, '08:30'),
  (7, 2, 2, '08:30'),
  (2, 3, 2, '08:30'),
  (17, 4, 2, '08:30'),
  (4, 5, 2, '08:30'),
  (18, 10, 2, '08:30'),
  (8, 9, 2, '09:00'),
  (9, 2, 2, '14:00'),
  (3, 1, 3, '08:30'),
  (11, 2, 3, '08:30'),
  (2, 3, 3, '08:30'),
  (17, 4, 3, '08:30'),
  (4, 5, 3, '08:30'),
  (18, 10, 3, '08:30'),
  (6, 3, 3, '13:00'),
  (13, 2, 3, '14:00'),
  (10, 1, 4, '08:30'),
  (12, 2, 4, '08:30'),
  (2, 3, 4, '08:30'),
  (17, 4, 4, '08:30'),
  (4, 5, 4, '08:30'),
  (15, 6, 4, '08:30'),
  (18, 10, 4, '08:30'),
  (8, 9, 4, '11:00'),
  (5, 3, 4, '14:00'),
  (19, 4, 5, '08:30'),
  (4, 5, 5, '08:30'),
  (15, 6, 5, '08:30'),
  (18, 10, 5, '08:30'),
  (13, 2, 5, '14:00');

-- Reseta as sequences pros próximos inserts via portal
SELECT setval('cc_salas_id_seq',         (SELECT MAX(id) FROM cc_salas));
SELECT setval('cc_profissionais_id_seq', (SELECT MAX(id) FROM cc_profissionais));
SELECT setval('cc_escala_id_seq',        (SELECT MAX(id) FROM cc_escala));
