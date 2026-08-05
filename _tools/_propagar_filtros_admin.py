# -*- coding: utf-8 -*-
"""
_propagar_filtros_admin.py — leva a barra de filtros nova do recebimento.html
para os outros admins (oxy/index.html e cirurgias/index.html).

O que propaga:
  1. Mês deixa de ser botões lado a lado e vira menu suspenso.
  2. Entram os filtros de Categoria e Tabela de preço.
  3. CSS que faz os campos caberem numa linha só acima de 1250px.
  4. JS que recalcula tudo a partir dos atendimentos quando há filtro ativo.

Os três admins NÃO são cópias exatas um do outro:
  - o Oxy usa `--navy-med` no foco do select; os outros usam `--gold`;
  - o Cirurgias tem um caso `FILTRO_EMPRESA === 'todos'` que os outros não têm;
  - os dois têm uma função `mudarPeriodo` DUPLICADA (versão antiga, morta, que a
    segunda declaração sobrescreve) — por isso âncoras curtas casariam no lugar
    errado e as daqui são longas de propósito.

Cada troca é ancorada num trecho exato e exige ocorrência única. Se qualquer
âncora falhar, o arquivo é pulado inteiro sem gravar nada: meio-caminho aqui
quebra o portal.

Uso:
    python _tools/_propagar_filtros_admin.py --dry-run
    python _tools/_propagar_filtros_admin.py
"""
from __future__ import annotations
import argparse
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
FONTE = REPO / "recebimento.html"
MARCA = "grp-intervalo"   # presente => arquivo já propagado


def bloco_da_fonte(inicio: str, fim: str) -> str:
    html = FONTE.read_text(encoding="utf-8")
    i = html.find(inicio)
    j = html.find(fim, i)
    if i < 0 or j < 0:
        raise SystemExit(f"ABORTADO: bloco não encontrado na fonte: {inicio[:50]!r}")
    return html[i:j]


CSS_NOVO = bloco_da_fonte("/* Os 6 filtros numa linha só.", "\n/* KPIs novos").rstrip()
JS_NOVO = bloco_da_fonte("// ── Filtros de Categoria e Tabela de preço",
                         "// Repopula o <select id='prof-filtro'>")

FILTROS_MARKUP = """          <option value=''>— Visão Geral —</option>
        </select>
      </div>
      <div class='range-sep'></div>
      <div class='f-grp'>
        <span class='periodo-label-novo'>Categoria:</span>
        <select id='cat-filtro' class='prof-select' onchange='filtrarPorCategoria(this.value)'>
          <option value=''>— Todas —</option>
        </select>
      </div>
      <div class='range-sep'></div>
      <div class='f-grp'>
        <span class='periodo-label-novo'>Tabela:</span>
        <select id='tab-filtro' class='prof-select' onchange='filtrarPorTabela(this.value)'>
          <option value=''>— Todas —</option>
        </select>
      </div>"""

MENU_MES = """  const selPer = document.getElementById('periodo-select');
  if(selPer){
    selPer.innerHTML = periodos.slice().reverse().map(pid =>
      '<option value="'+pid+'">'+TODOS_PERIODOS[pid].label+'</option>').join('');
    selPer.value = PERIODO_ATUAL;
  }"""

RANGE_FILTRA = """    a.por_tabela    = Object.values(a._tab);
    delete a._cat; delete a._pag; delete a._tab;
  });

  if(FILTRO_CATEGORIA || FILTRO_TABELA){
    Object.keys(agg).forEach(slug => {
      const ats = (agg[slug].atendimentos||[]).filter(x =>
        (!FILTRO_CATEGORIA || x.Categoria === FILTRO_CATEGORIA) &&
        (!FILTRO_TABELA    || x.Tabela    === FILTRO_TABELA));
      if(ats.length) agg[slug] = _recalcularProf(agg[slug], ats);
      else delete agg[slug];
    });
  }"""

# ---- trocas iguais nos dois arquivos ----
COMUNS = [
    ("<div id='periodo-tabs' class='tabs-flex'></div>",
     "<select id='periodo-select' class='prof-select' onchange='mudarPeriodo(this.value)'></select>"),

    ("<div class='f-grp'>\n        <span class='periodo-label-novo'>Intervalo:",
     "<div class='f-grp grp-intervalo'>\n        <span class='periodo-label-novo'>Intervalo:"),

    ("          <option value=''>— Visão Geral —</option>\n        </select>\n      </div>",
     FILTROS_MARKUP),

    ("function _atualizarSelectProfs(){", JS_NOVO + "function _atualizarSelectProfs(){"),

    # âncora longa: existe uma cópia morta de inicializarPortalPermanente
    ("""  const tabsEl = document.getElementById('periodo-tabs');
  if(tabsEl){
    tabsEl.style.display = 'flex';
    tabsEl.innerHTML = periodos.slice().reverse().map(pid => {
      const lbl = TODOS_PERIODOS[pid].label;
      return '<button class="tab-novo'+(pid===PERIODO_ATUAL?' active':'')+
             '" data-pid="'+pid+'" onclick="mudarPeriodo(\\''+pid+'\\')">'+ lbl +'</button>';
    }).join('');
  }""", MENU_MES),

    ("""  if(updateTabs !== false){
    document.querySelectorAll('#periodo-tabs .tab-novo').forEach(t => {
      t.classList.toggle('active', t.dataset.pid === id);
    });
  }""",
     """  const selPer = document.getElementById('periodo-select');
  if(selPer && selPer.value !== id) selPer.value = id;"""),

    ("""  FILTRO_EMPRESA = emp;
  Object.keys(DADOS_PROFS).forEach(k => delete DADOS_PROFS[k]);
  Object.entries(_DADOS_PROFS_PERIODO).forEach(([k,v]) => {
    if((v.empresa || 'Endovascular SP') === FILTRO_EMPRESA) DADOS_PROFS[k] = v;
  });
  Object.keys(CHARTS)""",
     """  FILTRO_EMPRESA = emp;
  _atualizarSelectsFiltros();
  _aplicarFiltros();
  Object.keys(CHARTS)"""),

    ("  document.querySelectorAll('#periodo-tabs .tab-novo').forEach(t => t.classList.remove('active'));\n  _renderRangeGeral();",
     "  const selPer = document.getElementById('periodo-select');\n  if(selPer) selPer.value = ate;\n  _renderRangeGeral();"),

    ("    a.por_tabela    = Object.values(a._tab);\n    delete a._cat; delete a._pag; delete a._tab;\n  });",
     RANGE_FILTRA),
]

# ---- o que difere entre eles ----
ESPECIFICAS = {
    "oxy/index.html": [
        (".prof-select:focus{border-color:var(--navy-med);}",
         ".prof-select:focus{border-color:var(--navy-med);}\n\n" + CSS_NOVO),
        ("""  // Filtra só profissionais da empresa fixa deste admin (Oxy Recovery)
  Object.keys(DADOS_PROFS).forEach(k => delete DADOS_PROFS[k]);
  Object.entries(_DADOS_PROFS_PERIODO).forEach(([k,v]) => {
    if((v.empresa || 'Endovascular SP') === FILTRO_EMPRESA) DADOS_PROFS[k] = v;
  });
""",
         "  _atualizarSelectsFiltros();\n  _aplicarFiltros();\n"),
    ],
    "cirurgias/index.html": [
        (".prof-select:focus{border-color:var(--gold);}",
         ".prof-select:focus{border-color:var(--gold);}\n\n" + CSS_NOVO),
        ("""  Object.keys(DADOS_PROFS).forEach(k => delete DADOS_PROFS[k]);
  if(FILTRO_EMPRESA === 'todos'){
    Object.assign(DADOS_PROFS, _DADOS_PROFS_PERIODO);
  } else {
    Object.entries(_DADOS_PROFS_PERIODO).forEach(([k,v]) => {
      if((v.empresa || 'Endovascular SP') === FILTRO_EMPRESA) DADOS_PROFS[k] = v;
    });
  }
""",
         "  _atualizarSelectsFiltros();\n  _aplicarFiltros();\n"),
    ],
}


def main(dry_run: bool):
    print(f"Fonte: {FONTE.name} · CSS {len(CSS_NOVO):,} chars · JS {len(JS_NOVO):,} chars\n")
    for rel, especificas in ESPECIFICAS.items():
        alvo = REPO / rel
        if not alvo.exists():
            print(f"[PULADO] {rel}: não existe"); continue
        html = alvo.read_text(encoding="utf-8")
        if MARCA in html:
            print(f"[JÁ FEITO] {rel}"); continue

        trocas = COMUNS + especificas
        problemas = [(i, de) for i, (de, _) in enumerate(trocas, 1) if html.count(de) != 1]
        if problemas:
            print(f"[ABORTADO] {rel}")
            for i, de in problemas:
                print(f"    troca {i}: aparece {html.count(de)}x — {de.strip()[:70]!r}")
            continue

        novo = html
        for de, para in trocas:
            novo = novo.replace(de, para, 1)
        print(f"[OK] {rel}: {len(trocas)} trocas · {len(html):,} -> {len(novo):,} chars")
        if not dry_run:
            alvo.write_text(novo, encoding="utf-8")

    if dry_run:
        print("\n[dry-run] nada gravado.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    main(ap.parse_args().dry_run)
