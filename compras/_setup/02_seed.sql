-- =====================================================================
-- SEED INICIAL — Portal Compras
-- Gerado de C:/Users/thiag/Downloads/novo_relatrio_20-05-2026.xlsx
-- (261 linhas históricas do Pipefy)
-- =====================================================================

-- Departamentos (6)
INSERT INTO compras_departamentos (nome) VALUES
  ('Agendamento'),
  ('Concierge'),
  ('Enfermagem'),
  ('Financeiro'),
  ('Marketing'),
  ('Recepção');

-- Centros de Custo (2 unidades)
INSERT INTO compras_centros_custo (codigo, nome) VALUES
  ('END', 'Endovascular'),
  ('OXY', 'Oxy Recovery');

-- Métodos de Pagamento já são ENUM no schema, não precisa seed.
-- Valores aceitos: 'pix', 'boleto', 'cartao_credito', 'link_pagamento'

-- Fornecedores (56) - extraidos do historico
INSERT INTO compras_fornecedores (nome) VALUES
  ('ABSOLUTA MEDICAL'),
  ('AMJ'),
  ('BALLKE PRODUTOS HOSPITALARES LTDA'),
  ('BELA METAIS'),
  ('BIOLINE FIOS CIRÚRGICOS'),
  ('BSA COMERCIO E PRODUTOS DERCARTAVEIS'),
  ('CARBOGEL INDUSTRIA E COMERCIO LTDA'),
  ('CASA DO DERMATO'),
  ('CATHLAB'),
  ('CIRURGICA LOGAN MED MAT'),
  ('CIRURGICA SINETE COMERCIO, DISTRIBUICAO E IMPORTACAO DE PRODUTOS MEDICOS LTDA.'),
  ('DOUTORKIT COMERCIO E DISTRIBUIÇÃO'),
  ('DRA CHERIE COMERCIO & CIA LTDA'),
  ('DROGARIA SÃO PAULO'),
  ('ECO TURBO'),
  ('ECOMED COMERCIO DE PRODUTOS MÉDICOS'),
  ('ESSENTIA PHARMA'),
  ('EXATA COMERCIAL LTDA'),
  ('FAM LASER'),
  ('FARMATEC'),
  ('FUNARE MACHADO PRODUTOS HOSPITALARES'),
  ('FÁRMACIA PAGUE MENOS'),
  ('GIMBA'),
  ('HOSPITALAR DISTRIBUIDORA'),
  ('HOXTEL'),
  ('JC GAGLIARDI ARTIGOS MEDICOS'),
  ('KALUNGA'),
  ('KAMICON CONFECCOES LTDA'),
  ('KOLPLAST'),
  ('L'' EQUIPE LASER'),
  ('LEDS INFINITY'),
  ('LINEA ALIMENTOS INDUSTRIA E COMERCIO S/A'),
  ('LOJA ELETROLUX COMERCIO VIRTUAL'),
  ('LÃ FAÇON'),
  ('MAGAZINE LUIZA'),
  ('MASTER EXPRESSO'),
  ('MEDICOM COMERCIO E DISTRIBUICAO'),
  ('MERCADO LIVRE'),
  ('MERCADO OXXO'),
  ('METATRON_ECOMMERCE'),
  ('OFFSHOP'),
  ('PRATIKA FARMACIA LTDA'),
  ('PRECOLANDIA COMERCIAL LTDA'),
  ('RC MÓVEIS E EQUIPAMENTOS HOSPITALARES LTDA'),
  ('RELAXMEDIC IMPORTAÇÃO EXPORTAÇÃO LTDA'),
  ('RF DISTRIBUIDORA DE ALIMENTOS LTDA'),
  ('SEAMED MATERIAIS HOSPITALARES LTDA'),
  ('SIGVARIS DO BRASIL  IND. COM. LTDA'),
  ('STIN PHARMA EXCELENCIA EM SAUDE LTDA'),
  ('SUPRI ARTIGOS HOSPITALARES'),
  ('SÓ SACHET'),
  ('TECMEDIC'),
  ('ULTRAFARMA SAÚDE EIRELI'),
  ('UNITEC INDÚSTIRA E COMÉRCIO APARELHOS'),
  ('VISTA BRANCO JALECOS'),
  ('YOSHI MOVEIS');
