-- Seed 011: procedimentos classificados pelo Thiago ao resolver a fila de Julho/2026.
-- Incremental — só os novos. Quem já rodou o seed_010 antes precisa só deste.

INSERT INTO public.honorarios_procedimentos (chave, procedimento, categoria, origem) VALUES
  ('cirurgia - tenotomia', 'Cirurgia - Tenotomia', 'Cirurgia - Hospital', 'fila'),
  ('preenchimento (por seringa) - tabela diretoria', 'Preenchimento (Por seringa) - Tabela Diretoria', 'Procedimentos', 'fila'),
  ('exossomos - terapia regenerativa', 'Exossomos - Terapia Regenerativa', 'Procedimentos', 'fila'),
  ('hybrius evo - sessao individual (1 area)', 'Hybrius EVO - Sessão individual (1 área)', 'Laser (clínica)', 'fila'),
  ('exerese e sutura simples de pequenas lesoes (por grupo de ate 5 lesoes)', 'Exérese e sutura simples de pequenas lesões (por grupo de até 5 lesões)', 'Procedimentos', 'fila'),
  ('taxa compacta de sala de pequenas cirurgias', 'Taxa compacta de sala de pequenas cirurgias', 'Cirurgia - Clínica', 'fila')
ON CONFLICT (chave) DO UPDATE SET categoria = EXCLUDED.categoria;

-- Conferência:
-- SELECT categoria, count(*) FROM public.honorarios_procedimentos
--  GROUP BY categoria ORDER BY categoria;
