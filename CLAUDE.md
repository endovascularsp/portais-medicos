# Gestor Financeiro — Endovascular SP

Projeto de gestão financeira e portais de honorários médicos da clínica Endovascular SP.
Publicado via GitHub Pages em: **https://endovascularsp.github.io/portais-medicos/**

---

## Estrutura do Repositório GitHub

```
portais-medicos/              ← raiz do repositório (GitHub Pages)
├── index.html                ← Dashboard admin (todas as empresas)
├── hub/                      ← Páginas Hub individuais por médico
├── produtividade/            ← Portais de produtividade (Endovascular SP)
├── oxy/                      ← Portais individuais Oxy Recovery
├── cirurgias/                ← Portais individuais Cirurgias
└── oxy-produtividade/        ← Portais de produtividade Oxy Recovery
```

A pasta local equivalente ao repositório é:
`Gestor Financeiro Endovascular/Portal Público/` → arquivos que vão na **raiz** do repo
`Gestor Financeiro Endovascular/hub/`            → pasta `hub/` do repo
`Gestor Financeiro Endovascular/produtividade/`  → pasta `produtividade/` do repo
`Gestor Financeiro Endovascular/Portal Público Oxy/` → arquivos que vão em `oxy/`
`Gestor Financeiro Endovascular/Portal Público Cirurgias/` → arquivos que vão em `cirurgias/`
`Gestor Financeiro Endovascular/oxy-produtividade/` → pasta `oxy-produtividade/` do repo

---

## Empresas e Portais

O sistema tem **3 empresas** separadas, todas alimentadas pela mesma planilha de fechamento:

| Empresa | Filtro na planilha | Regra de separação |
|---|---|---|
| Endovascular SP | `Empresa == 'Endovascular SP'` | Categorias que NÃO contêm "Cirurgia" |
| Cirurgias | `Empresa == 'Endovascular SP'` | Categorias que contêm "Cirurgia - Hospital" ou "Cirurgia - Clínica" |
| Oxy Recovery | `Empresa == 'Oxy Recovery'` | Todos os registros |

> **Regra crítica:** A separação Endovascular SP / Cirurgias é feita pela coluna `Categoria` da planilha Base Compensação. Não existe empresa "Cirurgias" na planilha — a separação é lógica, por categoria.

---

## Planilha de Entrada

**Arquivo principal:** `Fechamento - Endovascular SP.xlsx`
- Aba usada: **`Base Compensação`**
- Colunas relevantes:
  - `Empresa` — "Endovascular SP" ou "Oxy Recovery"
  - `Mês` — "Janeiro", "Fevereiro", "Março" etc.
  - `Ano` — 2026
  - `Profissional` — nome completo
  - `Categoria` — determina Endovascular SP vs Cirurgias
  - `Tabela` — PARTICULAR, OMINT, SULAMÉRICA etc.
  - `Tipo de pagamento`
  - `Procedimento`, `Paciente`, `Data compensação`
  - `Valor recebido`, `Imposto (18%)`, `Taxa cartão (3%)`, `Custo`, `Valor Líquido`
  - `% Profissional` ← valor em R$ do repasse ao profissional (não é percentual)
  - `% Indicador` ← valor em R$ do repasse ao indicador
  - `% Clínica` ← valor em R$ da receita da clínica

---

## Estrutura do PDATA (JSON nos portais)

Cada portal HTML contém um bloco `const TODOS_PERIODOS = /*PDATA*/{...};` com os dados.

```json
{
  "2026-01": {
    "label": "Janeiro/2026",
    "profs": {
      "Igor_Rafael_Sincos": {
        "profissional": "Igor Rafael Sincos",
        "empresa": "Endovascular SP",
        "mes": "Janeiro", "ano": 2026, "periodo_id": "2026-01",
        "resumo": {
          "Valor recebido": 0.0, "Imposto (18%)": 0.0,
          "Taxa cartão (3%)": 0.0, "Custo": 0.0, "Valor Líquido": 0.0,
          "Repasse Profissional (R$)": 0.0,
          "Repasse Clínica (R$)": 0.0, "Repasse Indicador (R$)": 0.0
        },
        "por_categoria": [{"Categoria": "...", "Valor recebido": 0.0, ...}],
        "por_pagamento": [{"Tipo de pagamento": "...", "Valor recebido": 0.0}],
        "por_tabela": [{"Tabela": "...", "Valor recebido": 0.0}],
        "atendimentos": [{ "Paciente": "...", "Procedimento": "...", ... }]
      },
      "Igor_Rafael_Sincos_Cir": { ... },
      "Augusto_Ferreira_de_Carvalho_Caparica_Oxy": { ... }
    }
  }
}
```

### Sufixos de chave por empresa
- `Endovascular SP` → sem sufixo: `Igor_Rafael_Sincos`
- `Cirurgias` → sufixo `_Cir`: `Igor_Rafael_Sincos_Cir`
- `Oxy Recovery` → sufixo `_Oxy`: `Augusto_Ferreira_de_Carvalho_Caparica_Oxy`

---

## Profissionais — Endovascular SP

| Profissional | Slug (chave no PDATA) | Senha | Hub |
|---|---|---|---|
| Igor Rafael Sincos | `Igor_Rafael_Sincos` | igo2026 | Igor_Rafael_Sincos_Hub.html |
| Jonathan Batista Souza | `Jonathan_Batista_Souza` | jon2026 | Jonathan_Batista_Souza_Hub.html |
| Carolina Mardegan | `Carolina_Mardegan` | car2026 | Carolina_Mardegan_Hub.html |
| Christiane Sayuri Lopes Inoue | `Christiane_Sayuri_Lopes_Inoue` | chr2026 | Christiane_Sayuri_Lopes_Inoue_Hub.html |
| Manoel Augusto Lobato | `Manoel_Augusto_Lobato` | man2026 | Manoel_Augusto_Lobato_Hub.html |
| João Fukuda | `João_Fukuda` | joa2026 | João_Fukuda_Hub.html |
| Maria Fernanda R Fernandes | `Maria_Fernanda_R_Fernandes` | maf2026 | Maria_Fernanda_R_Fernandes_Hub.html |
| Simone Matsuda Torricelli | `Simone_Matsuda_Torricelli` | sim2026 | Simone_Matsuda_Torricelli_Hub.html |
| Andrea Ostaszewski Klepacz | `Andrea_Ostaszewski_Klepacz` | and2026 | Andrea_Ostaszewski_Klepacz_Hub.html |
| Clara Silva Freitas | `Clara_Silva_Freitas` | cla2026 | Clara_Silva_Freitas_Hub.html |
| Larissa Medeiros Santos | `Larissa_Medeiros_Santos` | lar2026 | Larissa_Medeiros_Santos_Hub.html |
| Eduardo Araujo Pires | `Eduardo_Araujo_Pires` | edu2026 | Eduardo_Araujo_Pires_Hub.html |
| Daniela Viese Roth | `Daniela_Viese_Roth` | dan2026 | Daniela_Viese_Roth_Hub.html |
| Fernanda Liporaci Villela Zuchi | `Fernanda_Liporaci_Villela_Zuchi` | — | Fernanda_Liporaci_Villela_Zuchi_Hub.html |
| Gabriela Richards | `Gabriela_Richards` | — (sem senha) | Gabriela_Richards_Hub.html |
| Alvaro Machado Gaudencio | `Alvaro_Machado_Gaudencio` | — (sem senha) | Alvaro_Machado_Gaudencio_Hub.html |

---

## Dashboard Admin (index.html)

Variáveis JavaScript críticas no `index.html`:

```javascript
let FILTRO_EMPRESA = 'Endovascular SP';   // empresa exibida por padrão
let _DADOS_PROFS_PERIODO = {};            // cache do período completo (sem filtro)
let DADOS_PROFS = {};                     // dados filtrados pela empresa ativa
const TODOS_PERIODOS = /*PDATA*/{...};   // injetar JSON aqui
```

Funções principais:
- `inicializarPortalPermanente()` — constrói tabs de período + filtro de empresa, chama `mudarPeriodo`
- `mudarPeriodo(id, updateTabs)` — carrega período, filtra por `FILTRO_EMPRESA`, chama `renderGeral()`
- `filtrarEmpresas(emp)` — troca empresa ativa, refiltrar `_DADOS_PROFS_PERIODO`, redesenha gráficos

O bloco que detecta empresas e constrói os botões 🏥/💊/🔬 fica dentro de `inicializarPortalPermanente()`, antes de `mudarPeriodo(PERIODO_ATUAL, false)`.

---

## Script de Geração do PDATA

Para regenerar o PDATA a partir do Excel de fechamento:

```python
import pandas as pd, json, numpy as np

class NpEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.integer): return int(obj)
        if isinstance(obj, np.floating): return float(obj)
        return super().default(obj)

df = pd.read_excel('Fechamento - Endovascular SP.xlsx', sheet_name='Base Compensação')

MES_MAP = {'Janeiro':'01','Fevereiro':'02','Março':'03','Abril':'04',
           'Maio':'05','Junho':'06','Julho':'07','Agosto':'08',
           'Setembro':'09','Outubro':'10','Novembro':'11','Dezembro':'12'}

def slugify(name):
    import unicodedata
    return unicodedata.normalize('NFC', name).replace(' ', '_')

def is_cirurgia(cat):
    return 'cirurgia' in str(cat).lower() if pd.notna(cat) else False

TODOS_PERIODOS = {}

for mes in df['Mês'].unique():
    mes_num = MES_MAP[mes]
    pid = f'2026-{mes_num}'
    df_mes = df[df['Mês'] == mes]
    profs = {}

    for emp_orig in ['Endovascular SP', 'Oxy Recovery']:
        df_emp = df_mes[df_mes['Empresa'] == emp_orig]
        for prof_name, df_prof in df_emp.groupby('Profissional'):
            subsets = []
            if emp_orig == 'Endovascular SP':
                df_nao = df_prof[~df_prof['Categoria'].apply(is_cirurgia)]
                df_cir = df_prof[df_prof['Categoria'].apply(is_cirurgia)]
                if not df_nao.empty: subsets.append(('Endovascular SP', df_nao, ''))
                if not df_cir.empty: subsets.append(('Cirurgias', df_cir, '_Cir'))
            else:
                subsets.append(('Oxy Recovery', df_prof, '_Oxy'))

            for emp_label, df_sub, suffix in subsets:
                slug = slugify(prof_name) + suffix
                resumo = {
                    'Profissional': prof_name,
                    'Valor recebido':           round(float(df_sub['Valor recebido'].sum()), 2),
                    'Imposto (18%)':            round(float(df_sub['Imposto (18%)'].sum()), 2),
                    'Taxa cartão (3%)':         round(float(df_sub['Taxa cartão (3%)'].sum()), 2),
                    'Custo':                    round(float(df_sub['Custo'].sum()), 2),
                    'Valor Líquido':            round(float(df_sub['Valor Líquido'].sum()), 2),
                    'Repasse Profissional (R$)':round(float(df_sub['% Profissional'].sum()), 2),
                    'Repasse Clínica (R$)':     round(float(df_sub['% Clínica'].sum()), 2),
                    'Repasse Indicador (R$)':   round(float(df_sub['% Indicador'].sum()), 2),
                }
                # por_categoria, por_pagamento, por_tabela, atendimentos:
                # (ver script completo em honorarios_auto/gerar_pdata.py)
                profs[slug] = {
                    'profissional': prof_name, 'empresa': emp_label,
                    'mes': mes, 'ano': 2026, 'periodo_id': pid,
                    'resumo': resumo, 'por_categoria': [], 'por_pagamento': [],
                    'por_tabela': [], 'atendimentos': []
                }
    TODOS_PERIODOS[pid] = {'label': f'{mes}/2026', 'profs': profs}
```

Para injetar no `index.html`, substituir o bloco entre `/*PDATA*/` e o `;` seguinte.

---

## Fluxo de Trabalho Mensal

1. Receber Excel de fechamento do mês → salvar como `Fechamento - Endovascular SP.xlsx`
2. Rodar script Python para gerar novo PDATA
3. Injetar PDATA no `index.html` (dashboard admin)
4. Injetar PDATA nos portais individuais de cada profissional
5. Injetar PDATA nos portais Oxy Recovery e Cirurgias
6. Atualizar planilha `Acessos_Portal_Honorarios_2026.xlsx` se houver novos profissionais
7. `git add -A && git commit -m "Fechamento Mês/2026" && git push`

---

## Repositório GitHub

- **Organização:** endovascularsp
- **Repositório:** portais-medicos
- **URL GitHub Pages:** https://endovascularsp.github.io/portais-medicos/
- **Branch principal:** main (ou gh-pages — confirmar)

---

## Notas Técnicas Importantes

- O JSON do PDATA usa `json.dumps(..., ensure_ascii=False)` para preservar acentos (ã, é, ç etc.)
- Usar sempre `NpEncoder` para serializar tipos numpy do pandas
- O `index.html` tem ~1.1 MB quando o PDATA de 3 meses está injetado — é normal
- Não usar `load_workbook(..., data_only=True)` e salvar — destrói as fórmulas da planilha
- O campo `% Profissional` na planilha é **valor em R$**, não percentual
- Perfis sem senha (Gabriela Richards, Alvaro Machado Gaudencio) têm `MODO_MEDICO = false` desabilitado — acesso livre
