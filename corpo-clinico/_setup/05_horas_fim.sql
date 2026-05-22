-- Horários de fim dos turnos — extraídos dos merges do Mapa de Sala Excel.
-- Cada turno: do hora_inicio até o último slot que o Excel pinta.
-- Executar no Supabase SQL Editor.

UPDATE cc_escala SET hora_fim = '18:30' WHERE dia_semana = 1 AND sala_id = 1 AND hora_inicio = '08:30';  -- Dr. Igor Sincos - Vascular - CRM 11
UPDATE cc_escala SET hora_fim = '18:30' WHERE dia_semana = 1 AND sala_id = 2 AND hora_inicio = '08:30';  -- Dr. João Fukuda - Vascular - CRM 47
UPDATE cc_escala SET hora_fim = '18:30' WHERE dia_semana = 1 AND sala_id = 3 AND hora_inicio = '08:30';  -- Dra. Andréa Klepacz - Vascular - CR
UPDATE cc_escala SET hora_fim = '18:30' WHERE dia_semana = 1 AND sala_id = 6 AND hora_inicio = '08:30';  -- Dr. Mateus Nogueira - Médico do Esp
UPDATE cc_escala SET hora_fim = '18:30' WHERE dia_semana = 1 AND sala_id = 10 AND hora_inicio = '08:30';  -- Juliana Olimpio - Fisioterapeuta
UPDATE cc_escala SET hora_fim = '18:30' WHERE dia_semana = 1 AND sala_id = 5 AND hora_inicio = '13:00';  -- Dra. Christiane Inoue - Dermatologi
UPDATE cc_escala SET hora_fim = '18:30' WHERE dia_semana = 1 AND sala_id = 4 AND hora_inicio = '14:00';  -- Dra. Simone Matsuda - Endocriologis
UPDATE cc_escala SET hora_fim = '18:30' WHERE dia_semana = 2 AND sala_id = 1 AND hora_inicio = '08:30';  -- Dr. Igor Sincos - Vascular - CRM 11
UPDATE cc_escala SET hora_fim = '11:30' WHERE dia_semana = 2 AND sala_id = 2 AND hora_inicio = '08:30';  -- Dr. Eduardo Pires - Ortopedista - C
UPDATE cc_escala SET hora_fim = '18:30' WHERE dia_semana = 2 AND sala_id = 3 AND hora_inicio = '08:30';  -- Dra. Andréa Klepacz - Vascular - CR
UPDATE cc_escala SET hora_fim = '18:30' WHERE dia_semana = 2 AND sala_id = 4 AND hora_inicio = '08:30';  -- Dra. Simone Matsuda - Endocriologis
UPDATE cc_escala SET hora_fim = '18:30' WHERE dia_semana = 2 AND sala_id = 5 AND hora_inicio = '08:30';  -- Dra. Christiane Inoue - Dermatologi
UPDATE cc_escala SET hora_fim = '18:30' WHERE dia_semana = 2 AND sala_id = 10 AND hora_inicio = '08:30';  -- Juliana Olimpio - Fisioterapeuta
UPDATE cc_escala SET hora_fim = '16:00' WHERE dia_semana = 2 AND sala_id = 9 AND hora_inicio = '09:00';  -- Fernanda Liporaci - Fisioterapeuta 
UPDATE cc_escala SET hora_fim = '18:30' WHERE dia_semana = 2 AND sala_id = 2 AND hora_inicio = '14:00';  -- Dr. Gustavo Resstel - Vascular - CR
UPDATE cc_escala SET hora_fim = '18:30' WHERE dia_semana = 3 AND sala_id = 1 AND hora_inicio = '08:30';  -- Dra. Carol Mardegan - Vascular - CR
UPDATE cc_escala SET hora_fim = '13:30' WHERE dia_semana = 3 AND sala_id = 2 AND hora_inicio = '08:30';  -- Dr. João Fukuda - Vascular - CRM 47
UPDATE cc_escala SET hora_fim = '12:30' WHERE dia_semana = 3 AND sala_id = 3 AND hora_inicio = '08:30';  -- Dra. Andréa Klepacz - Vascular - CR
UPDATE cc_escala SET hora_fim = '18:30' WHERE dia_semana = 3 AND sala_id = 4 AND hora_inicio = '08:30';  -- Dra. Simone Matsuda - Endocriologis
UPDATE cc_escala SET hora_fim = '18:30' WHERE dia_semana = 3 AND sala_id = 5 AND hora_inicio = '08:30';  -- Dra. Christiane Inoue - Dermatologi
UPDATE cc_escala SET hora_fim = '18:30' WHERE dia_semana = 3 AND sala_id = 10 AND hora_inicio = '08:30';  -- Juliana Olimpio - Fisioterapeuta
UPDATE cc_escala SET hora_fim = '18:00' WHERE dia_semana = 3 AND sala_id = 3 AND hora_inicio = '13:00';  -- Dra. Daniela Viese - Vascular - CRM
UPDATE cc_escala SET hora_fim = '18:30' WHERE dia_semana = 3 AND sala_id = 2 AND hora_inicio = '14:00';  -- Dr. Manoel Lobato - Vascular - CRM 
UPDATE cc_escala SET hora_fim = '18:30' WHERE dia_semana = 4 AND sala_id = 1 AND hora_inicio = '08:30';  -- Dr. Igor Sincos - Vascular - CRM 11
UPDATE cc_escala SET hora_fim = '18:30' WHERE dia_semana = 4 AND sala_id = 2 AND hora_inicio = '08:30';  -- Dr. Jonathan Batista - Cardiologist
UPDATE cc_escala SET hora_fim = '13:30' WHERE dia_semana = 4 AND sala_id = 3 AND hora_inicio = '08:30';  -- Dra. Andréa Klepacz - Vascular - CR
UPDATE cc_escala SET hora_fim = '18:30' WHERE dia_semana = 4 AND sala_id = 4 AND hora_inicio = '08:30';  -- Dra. Simone Matsuda - Endocriologis
UPDATE cc_escala SET hora_fim = '18:30' WHERE dia_semana = 4 AND sala_id = 5 AND hora_inicio = '08:30';  -- Dra. Christiane Inoue - Dermatologi
UPDATE cc_escala SET hora_fim = '18:30' WHERE dia_semana = 4 AND sala_id = 6 AND hora_inicio = '08:30';  -- Dr. Mateus Nogueira - Médico do Esp
UPDATE cc_escala SET hora_fim = '18:30' WHERE dia_semana = 4 AND sala_id = 10 AND hora_inicio = '08:30';  -- Juliana Olimpio - Fisioterapeuta
UPDATE cc_escala SET hora_fim = '17:30' WHERE dia_semana = 4 AND sala_id = 9 AND hora_inicio = '11:00';  -- Fernanda Liporaci - Fisioterapeuta 
UPDATE cc_escala SET hora_fim = '18:30' WHERE dia_semana = 4 AND sala_id = 3 AND hora_inicio = '14:00';  -- Dra. Clara Freitas - Vascular - CRM
UPDATE cc_escala SET hora_fim = '18:30' WHERE dia_semana = 5 AND sala_id = 4 AND hora_inicio = '08:30';  -- Julia Bargieri - Nutricionista CRN
UPDATE cc_escala SET hora_fim = '18:30' WHERE dia_semana = 5 AND sala_id = 5 AND hora_inicio = '08:30';  -- Dra. Christiane Inoue - Dermatologi
UPDATE cc_escala SET hora_fim = '18:30' WHERE dia_semana = 5 AND sala_id = 6 AND hora_inicio = '08:30';  -- Dr. Mateus Nogueira - Médico do Esp
UPDATE cc_escala SET hora_fim = '18:30' WHERE dia_semana = 5 AND sala_id = 10 AND hora_inicio = '08:30';  -- Juliana Olimpio - Fisioterapeuta
UPDATE cc_escala SET hora_fim = '18:30' WHERE dia_semana = 5 AND sala_id = 2 AND hora_inicio = '14:00';  -- Dr. Manoel Lobato - Vascular - CRM 
