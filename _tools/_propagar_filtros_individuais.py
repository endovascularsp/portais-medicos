# -*- coding: utf-8 -*-
"""
_propagar_filtros_individuais.py — leva aos 40 portais individuais de Recebimento
os três recursos que só existiam nos admins:

  1. menu suspenso de mês, no lugar dos botões lado a lado;
  2. filtro de Categoria;
  3. filtro de Tabela de preço.

Por que importa: os botões de mês foram trocados no admin justamente porque
estouravam a linha conforme os meses se acumulavam — e já são sete. Quem mais
sofre com isso é o médico, que é quem abre o portal individual.

Filtrar aqui não esconde linhas: RECALCULA o período a partir dos atendimentos
que sobraram, para os cartões do topo não continuarem mostrando o mês inteiro
com uma tabela filtrada embaixo. É a mesma decisão já tomada no admin.

O portal individual tem arquitetura diferente do admin — um profissional fixo
(PROF_FIXO) em vez de vários — então o código é adaptado, não copiado.

Uso:
    python _tools/_propagar_filtros_individuais.py --piloto Igor_Rafael_Sincos.html
    python _tools/_propagar_filtros_individuais.py --piloto Igor_Rafael_Sincos.html --escrever
    python _tools/_propagar_filtros_individuais.py --escrever
"""
from __future__ import annotations
import argparse
import io
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


class Falha(Exception):
    pass


# ---------------------------------------------------------------------------
# Markup
# ---------------------------------------------------------------------------
MARKUP_VELHO = """      <div class='f-grp'>
        <span class='periodo-label-novo'>Mês:</span>
        <div id='periodo-tabs' class='tabs-flex'></div>
      </div>"""

MARKUP_NOVO = """      <div class='f-grp'>
        <span class='periodo-label-novo'>Mês:</span>
        <select id='periodo-select' class='prof-select' onchange='mudarPeriodo(this.value)'></select>
      </div>"""

FILTROS = """      <div class='f-grp'>
        <span class='periodo-label-novo'>Categoria:</span>
        <select id='cat-filtro' class='prof-select' onchange='filtrarPorCategoria(this.value)'></select>
      </div>
      <div class='f-grp'>
        <span class='periodo-label-novo'>Tabela:</span>
        <select id='tab-filtro' class='prof-select' onchange='filtrarPorTabela(this.value)'></select>
      </div>
"""

# ---------------------------------------------------------------------------
# JS — adaptado do admin para o portal de um profissional só
# ---------------------------------------------------------------------------
JS = """
// ── Filtros de Categoria e Tabela ───────────────────────────────────────────
// Mesma decisão do admin: filtrar RECALCULA o período. Sem isso os cartões do
// topo continuariam mostrando o mês inteiro com uma tabela filtrada embaixo —
// o médico veria dois números diferentes na mesma tela.
let FILTRO_CATEGORIA = '';
let FILTRO_TABELA    = '';

function _somaAtend(ats, campo){
  return ats.reduce((a,x)=>a+(x[campo]||0),0);
}

function _quebra(ats, chave, campos){
  const m = {};
  ats.forEach(x => {
    const k = x[chave] || '—';
    if(!m[k]) m[k] = {};
    campos.forEach(c => m[k][c] = (m[k][c]||0) + (x[c]||0));
  });
  return m;
}

function _recalcularProf(p, ats){
  const out = Object.assign({}, p);
  out.atendimentos = ats;
  out.resumo = Object.assign({}, p.resumo, {
    'Valor recebido':            _somaAtend(ats,'Valor recebido'),
    'Imposto (18%)':             _somaAtend(ats,'Imposto (18%)'),
    'Taxa cartão (3%)':          _somaAtend(ats,'Taxa cartão (3%)'),
    'Custo':                     _somaAtend(ats,'Custo'),
    'Valor Líquido':             _somaAtend(ats,'Valor Líquido'),
    'Repasse Profissional (R$)': _somaAtend(ats,'Repasse Profissional (R$)'),
    'Repasse Clínica (R$)':      _somaAtend(ats,'Repasse Clínica (R$)'),
    'Repasse Indicador (R$)':    _somaAtend(ats,'Repasse Indicador (R$)')
  });
  const qc = _quebra(ats,'Categoria',['Valor recebido','Valor Líquido','Repasse Profissional (R$)']);
  out.por_categoria = Object.keys(qc).sort().map(c => Object.assign(
    {Profissional:p.profissional, Categoria:c}, qc[c]));
  const qp = _quebra(ats,'Tipo de pagamento',['Valor recebido']);
  out.por_pagamento = Object.keys(qp).sort().map(t => ({
    Profissional:p.profissional, 'Tipo de pagamento':t, 'Valor recebido':qp[t]['Valor recebido']}));
  const qt = _quebra(ats,'Tabela',['Valor recebido']);
  out.por_tabela = Object.keys(qt).sort().map(tb => {
    const ex = (p.por_tabela||[]).find(x => x.Tabela === tb) || {};
    return {Profissional:p.profissional, Tabela:tb, Origem:ex.Origem,
            'Valor recebido':qt[tb]['Valor recebido']};
  });
  return out;
}

// Monta os menus a partir do que existe no que está na tela. Se o filtro atual
// não existir mais no mês novo, volta para "todas" em vez de mostrar tela vazia.
function _atualizarSelectsFiltros(){
  const p = DADOS_PROFS[PROF_FIXO] || {};
  const cats = new Set(), tabs = new Set();
  (_ATEND_BRUTOS || p.atendimentos || []).forEach(a => {
    if(a.Categoria) cats.add(a.Categoria);
    if(a.Tabela)    tabs.add(a.Tabela);
  });
  const preencher = (id, valores, atual) => {
    const sel = document.getElementById(id);
    if(!sel) return '';
    const lista = Array.from(valores).sort((a,b)=>a.localeCompare(b,'pt-BR'));
    sel.innerHTML = '<option value="">— Todas —</option>' +
      lista.map(v=>'<option value="'+v.replace(/"/g,'&quot;')+'">'+v+'</option>').join('');
    const manter = lista.includes(atual) ? atual : '';
    sel.value = manter;
    return manter;
  };
  FILTRO_CATEGORIA = preencher('cat-filtro', cats, FILTRO_CATEGORIA);
  FILTRO_TABELA    = preencher('tab-filtro', tabs, FILTRO_TABELA);
}

// Guarda os atendimentos do período SEM filtro. É deles que os menus são
// montados — senão, ao escolher uma categoria, as outras sumiriam da lista e
// não haveria como voltar.
let _ATEND_BRUTOS = null;

function _aplicarFiltroInd(){
  const p = DADOS_PROFS[PROF_FIXO];
  if(!p) return;
  if(_ATEND_BRUTOS === null) _ATEND_BRUTOS = p.atendimentos || [];
  _atualizarSelectsFiltros();
  if(!FILTRO_CATEGORIA && !FILTRO_TABELA) return;
  const ats = _ATEND_BRUTOS.filter(a =>
    (!FILTRO_CATEGORIA || a.Categoria === FILTRO_CATEGORIA) &&
    (!FILTRO_TABELA    || a.Tabela    === FILTRO_TABELA));
  DADOS_PROFS[PROF_FIXO] = _recalcularProf(p, ats);
}

function filtrarPorCategoria(v){ FILTRO_CATEGORIA = v || ''; _reaplicarInd(); }
function filtrarPorTabela(v){    FILTRO_TABELA    = v || ''; _reaplicarInd(); }

function _reaplicarInd(){
  // Redesenha do zero a partir da fonte, para o filtro anterior não se somar ao
  // novo. RANGE_ATIVO tem caminho próprio porque agrega vários meses.
  _ATEND_BRUTOS = null;
  if(RANGE_ATIVO){ _renderRange(); return; }
  mudarPeriodo(PERIODO_ATUAL, false);
}
"""


def aplicar(t: str) -> str:
    if "cat-filtro" in t:
        raise Falha("já tem os filtros")

    # 1. menu de mês -------------------------------------------------------
    if t.count(MARKUP_VELHO) != 1:
        raise Falha(f"markup do seletor de mês aparece {t.count(MARKUP_VELHO)}x")
    t = t.replace(MARKUP_VELHO, MARKUP_NOVO, 1)

    # 2. filtros, depois do grupo do Intervalo ------------------------------
    fecha = ("          <button class='range-btn clear' onclick='limparRange()'>Limpar</button>\n"
             "        </div>\n      </div>\n")
    if t.count(fecha) != 1:
        raise Falha(f"fim do grupo Intervalo aparece {t.count(fecha)}x")
    t = t.replace(fecha, fecha + FILTROS, 1)

    # 3. JS ----------------------------------------------------------------
    anc = "function inicializarPortalPermanente(){"
    if t.count(anc) != 1:
        raise Falha(f"inicializarPortalPermanente aparece {t.count(anc)}x")
    t = t.replace(anc, JS + "\n" + anc, 1)

    # 4. o seletor passa a ser preenchido como lista suspensa ---------------
    velho_tabs = """  const tabsEl = document.getElementById('periodo-tabs');
  if(tabsEl){
    tabsEl.style.display = 'flex';
    tabsEl.innerHTML = periodos.slice().reverse().map(pid => {
      const lbl = TODOS_PERIODOS[pid].label;
      return '<button class="tab-novo'+(pid===PERIODO_ATUAL?' active':'')+
             '" data-pid="'+pid+'" onclick="mudarPeriodo(\\''+pid+'\\')">'+ lbl +'</button>';
    }).join('');
  }"""
    novo_sel = """  // Menu suspenso: com sete meses os botões lado a lado estouravam a linha.
  const selPer = document.getElementById('periodo-select');
  if(selPer){
    selPer.innerHTML = periodos.slice().reverse()
      .map(pid => '<option value="'+pid+'">'+TODOS_PERIODOS[pid].label+'</option>').join('');
    selPer.value = PERIODO_ATUAL;
  }"""
    if t.count(velho_tabs) != 1:
        raise Falha(f"montagem das abas de mês aparece {t.count(velho_tabs)}x")
    t = t.replace(velho_tabs, novo_sel, 1)

    # 5. mudarPeriodo: sincroniza o select e aplica o filtro ----------------
    velho_ativa = """  // Atualiza aba ativa
  if(updateTabs !== false){
    document.querySelectorAll('#periodo-tabs .tab-novo').forEach(t => {
      t.classList.toggle('active', t.dataset.pid === id);
    });
  }"""
    novo_ativa = """  const selPer = document.getElementById('periodo-select');
  if(selPer && selPer.value !== id) selPer.value = id;
  _ATEND_BRUTOS = null;   // mês novo, filtro recalculado do zero
  _aplicarFiltroInd();"""
    if t.count(velho_ativa) != 1:
        raise Falha(f"bloco da aba ativa aparece {t.count(velho_ativa)}x")
    t = t.replace(velho_ativa, novo_ativa, 1)

    # 6. o intervalo de meses também respeita o filtro ----------------------
    velho_range = """  DADOS_PROFS[fixo] = agg;
  Object.keys(CHARTS).forEach(k => { if(CHARTS[k]){ CHARTS[k].destroy(); delete CHARTS[k]; }});
  mostrarProf(fixo);"""
    novo_range = """  DADOS_PROFS[fixo] = agg;
  _ATEND_BRUTOS = null;   // o intervalo tem atendimentos próprios, de vários meses
  _aplicarFiltroInd();
  Object.keys(CHARTS).forEach(k => { if(CHARTS[k]){ CHARTS[k].destroy(); delete CHARTS[k]; }});
  mostrarProf(fixo);"""
    if t.count(velho_range) != 1:
        raise Falha(f"fim do _renderRange aparece {t.count(velho_range)}x")
    t = t.replace(velho_range, novo_range, 1)

    for peca in ("periodo-select", "cat-filtro", "tab-filtro", "_aplicarFiltroInd",
                 "_recalcularProf", "filtrarPorCategoria"):
        if peca not in t:
            raise Falha(f"'{peca}' não entrou")
    if "periodo-tabs" in t.replace(".tabs-flex", ""):
        # sobra só a regra de CSS, que é inofensiva; o id não pode mais ser usado
        if "getElementById('periodo-tabs')" in t:
            raise Falha("ainda há código usando o seletor antigo")
    return t


def alvos() -> list:
    out = [p for p in sorted(REPO.glob("*.html"))
           if p.name not in ("index.html", "recebimento.html")]
    for pasta in ("oxy", "cirurgias"):
        out += [p for p in sorted((REPO / pasta).glob("*.html")) if p.name != "index.html"]
    return [p for p in out if "periodo-tabs" in p.read_text(encoding="utf-8", errors="replace")]


def main(escrever: bool, piloto: str | None) -> int:
    lista = alvos()
    if piloto:
        lista = [p for p in lista if p.name == piloto or str(p).endswith(piloto)]
        if not lista:
            raise SystemExit(f"ABORTADO: piloto {piloto!r} não encontrado.")
    print(f"\n=== Filtros nos portais individuais · escrever={escrever} ===")
    print(f"    {len(lista)} arquivo(s)\n")
    ok = pulados = 0
    for path in lista:
        t = io.open(path, encoding="utf-8").read()
        bruto = path.read_bytes()
        fim = "\r\n" if bruto.count(b"\r\n") > bruto.count(b"\n") // 2 else "\n"
        try:
            novo = aplicar(t)
        except Falha as e:
            pulados += 1
            print(f"  [PULADO] {str(path.relative_to(REPO))[:50]:52s} {e}")
            continue
        if escrever:
            io.open(path, "w", encoding="utf-8", newline=fim).write(novo)
        ok += 1
        print(f"  [OK]     {str(path.relative_to(REPO))[:50]:52s} +{len(novo)-len(t):>5d} chars")
    print(f"\n  {ok} arquivo(s) · {pulados} pulado(s)")
    if not escrever:
        print("\n  [simulação] nada gravado. Rode com --escrever.")
    return pulados


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--escrever", action="store_true")
    ap.add_argument("--piloto")
    a = ap.parse_args()
    raise SystemExit(1 if main(a.escrever, a.piloto) else 0)
