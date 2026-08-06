# -*- coding: utf-8 -*-
"""
_propagar_layout_produtividade.py — leva o layout do Recebimento para os demais
portais de Produtividade, depois do piloto aprovado em produtividade/index.html.

Dois alvos, com tratamentos diferentes:

  ADMIN OXY (oxy-produtividade/index.html)
      Já tem tema claro PRÓPRIO ("tema claro invertido", com a barra de filtros
      escura). Isso é identidade da Oxy e NÃO é tocado. Recebe só o que faltava:
      os filtros de Categoria/Tabela e o novo desenho dos gráficos.

  PORTAIS INDIVIDUAIS (23: 16 Endovascular + 7 Oxy)
      Ainda estão no tema escuro. Recebem o pacote completo: página clara,
      cartões brancos, gráfico de pagamento em rosca e os dois filtros novos.
      Os cards de indicador continuam escuros, como no admin.

Cada transformação é ancorada em texto exato (ou numa função inteira, delimitada
por regex) e exige o número de ocorrências esperado. Se um arquivo divergir do
template, ele é PULADO e reportado — nunca gravado pela metade.

Uso:
    python _tools/_propagar_layout_produtividade.py            # simula
    python _tools/_propagar_layout_produtividade.py --escrever
"""
from __future__ import annotations
import argparse
import io
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


# ===========================================================================
# Utilitários de edição — falham alto em vez de gravar coisa errada
# ===========================================================================
class Falha(Exception):
    pass


def troca(t: str, alvo: str, novo: str, rotulo: str) -> str:
    n = t.count(alvo)
    if n != 1:
        raise Falha(f"{rotulo}: âncora aparece {n}x, esperava 1x")
    return t.replace(alvo, novo, 1)


def troca_funcao(t: str, assinatura: str, novo_corpo: str, rotulo: str) -> str:
    """Substitui uma função inteira: da assinatura até o '}' na coluna 0."""
    i = t.find(assinatura)
    if i < 0 or t.count(assinatura) != 1:
        raise Falha(f"{rotulo}: assinatura aparece {t.count(assinatura)}x, esperava 1x")
    m = re.compile(r"\n\}\n").search(t, i)
    if not m:
        raise Falha(f"{rotulo}: não achei o fim da função")
    return t[:i] + novo_corpo + t[m.end():]


# ===========================================================================
# Peças comuns
# ===========================================================================
MARKUP_FILTROS = """    <div class='f-grp'>
      <span class='periodo-label'>Categoria:</span>
      <select id='cat-filtro' class='prof-select' onchange='setFiltroCategoria(this.value)'></select>
    </div>
    <div class='f-grp'>
      <span class='periodo-label'>Tabela:</span>
      <select id='tab-filtro' class='prof-select' onchange='setFiltroTabela(this.value)'></select>
    </div>
"""

JS_CORES = """
// ---------------------------------------------------------------------------
// Paleta dos gráficos — a mesma do card de Recebimento (05/08/2026)
// ---------------------------------------------------------------------------
const CORES = ['#A18960','#23476f','#c7ad82','#3a5e80','#7c6948','#1a3654',
               '#d4bd8e','#4a6e95','#9c8458','#2d4f70','#bda079','#5a7da3'];
const EIXO_TICK  = '#4A6278';   // texto dos eixos, legível no branco
const EIXO_GRADE = '#eee';      // linhas de grade discretas, como no Recebimento

function semDados(ctx, msg){
  const c = ctx.getContext('2d');
  c.clearRect(0, 0, ctx.width, ctx.height);
  c.font = '13px Segoe UI'; c.fillStyle = EIXO_TICK; c.textAlign = 'center';
  c.fillText(msg, ctx.width/2, ctx.height/2);
}
"""

# Rosca de pagamento — o corpo depois da linha `const vals = ...`.
ROSCA = """  const ctx = document.getElementById('chart-pag');
  if(chartPag) chartPag.destroy();
  if(!labels.length){ semDados(ctx, 'Sem dados de pagamento'); return; }
  // Rosca com legenda à direita — igual ao "Por Tipo de Pagamento" do Recebimento.
  chartPag = new Chart(ctx, {
    type:'doughnut',
    data:{labels, datasets:[{data:vals, backgroundColor:CORES,
                             borderColor:'#fff', borderWidth:2}]},
    options:{
      responsive:true, maintainAspectRatio:false,
      plugins:{
        legend:{position:'right', labels:{font:{size:11}, boxWidth:14, padding:10,
                                          color:'#0D1E30'}},
        tooltip:{callbacks:{label:c=>{
          const tot=c.dataset.data.reduce((a,b)=>a+b,0);
          const v=c.parsed, pct=tot>0?((v/tot)*100).toFixed(1):'0';
          return ' '+br(v)+' ('+pct+'%)';
        }}}}
    }
  });
}
"""


# ===========================================================================
# PORTAIS INDIVIDUAIS
# ===========================================================================
CSS_INDIVIDUAL = """</style>
<style id="layout-unificado-recebimento">
/* ============================================================================
   Layout unificado com o card de Recebimento — 05/08/2026.

   Este portal estava em tema escuro (fundo navy, cartões de gráfico em
   gradiente). Passa a usar o mesmo desenho do Recebimento: página clara,
   cartões brancos, mesma tipografia de título.

   OS CARDS DE INDICADOR (.card) FICAM ESCUROS — são os "flutuantes", iguais
   aos do admin. Só o conteúdo dos cartões de gráfico é que clareia.

   Vem depois do CSS original de propósito: sobrescreve por ordem, sem precisar
   editar dezenas de regras espalhadas.
   ============================================================================ */
:root{
  --cinza-bg:#F2F5F9; --cinza-borda:#DDE4ED;
  --bg:#F2F5F9;   /* era #0B1F3A — é o que clareia a página */
}
body{background:var(--cinza-bg);}

/* Cartão de gráfico: branco, como o .card do Recebimento */
.pag-section{background:#fff;border:1px solid var(--cinza-borda);}
.pag-section .section-title{color:var(--texto);}
.pag-card{background:var(--cinza-cl);border:1px solid var(--cinza-borda);}
.pag-tipo{color:var(--texto2);}
.pag-val{color:var(--texto);}
.pag-qtd{color:var(--texto2);}

/* Títulos de seção: do Recebimento (sai o maiúsculo espaçado) */
.section-title{font-size:16px;font-weight:700;color:var(--texto);
  letter-spacing:normal;text-transform:none;}

/* Barra de filtros: os campos numa linha só, como no Recebimento */
.prof-select{padding:6px 12px;border:1.5px solid var(--borda);border-radius:20px;
  font-size:12px;font-weight:600;color:var(--navy);background:#fff;
  cursor:pointer;font-family:inherit;outline:none;transition:border 0.15s;}
.prof-select:focus{border-color:var(--gold);}
@media (min-width:1100px){
  .periodo-bloco{gap:8px;padding:12px 16px;align-items:center;}
  .periodo-bloco > .f-grp{min-width:0;flex:1 1 150px;}
  .periodo-bloco > .f-grp.grp-intervalo{flex:2 1 340px;}
  .periodo-bloco .prof-select{max-width:none;min-width:0;width:100%;flex:1 1 0;}
  .periodo-bloco .range-filter{min-width:0;flex:1 1 auto;flex-wrap:nowrap;gap:5px;}
  .periodo-bloco .range-filter select{min-width:0;flex:1 1 0;padding:4px 6px;}
  .periodo-bloco .periodo-label{white-space:nowrap;flex:none;}
  .periodo-bloco .range-ate{flex:none;}
  .periodo-bloco .range-btn{padding:5px 9px;white-space:nowrap;flex:none;}
  .periodo-bloco .range-sep{flex:none;}
}
</style>
</head>"""

JS_FILTROS_INDIVIDUAL = """
// ---------------------------------------------------------------------------
// Filtros de Categoria e Tabela de preço — 05/08/2026
// ---------------------------------------------------------------------------
// Filtrar não esconde linhas: RECALCULA o período a partir dos atendimentos.
// Faturamento, nº de atendimentos, pacientes, o gráfico, a lista e o export
// passam todos a mostrar só o que sobrou do filtro.
let FILTRO_CATEGORIA = 'todas';
let FILTRO_TABELA    = 'todas';

function _passa(p, a){
  const cat = p.categoria || '';
  const tab = p.tabela || a.tabela || '';
  return (FILTRO_CATEGORIA === 'todas' || cat === FILTRO_CATEGORIA)
      && (FILTRO_TABELA    === 'todas' || tab === FILTRO_TABELA);
}

// Devolve o atendimento só com os procedimentos que passaram, ou null.
function _filtrarAtend(a){
  const procs = (a.procedimentos || []).filter(p=>_passa(p, a));
  if(!procs.length) return null;
  const v = procs.reduce((s,p)=>s+(p.valor||0), 0);
  return Object.assign({}, a, {procedimentos:procs, valor:Math.round(v*100)/100});
}

function _preencherSelectsFiltros(){
  const prof = Object.keys(DADOS)[0];
  const per  = (DADOS[prof] || {}).periodos || {};
  const cats = new Set(), tabs = new Set();
  Object.values(per).forEach(p=>{
    const r = p.resumo || {};
    Object.keys(r.por_categoria || {}).forEach(c=>cats.add(c));
    Object.keys(r.por_tabela    || {}).forEach(t=>tabs.add(t));
  });
  const opts = (rot, vals)=> `<option value='todas'>${rot}</option>` +
    [...vals].sort((a,b)=>a.localeCompare(b,'pt'))
      .map(v=>`<option value="${v.replace(/"/g,'&quot;')}">${v}</option>`).join('');
  const sc = document.getElementById('cat-filtro');
  const st = document.getElementById('tab-filtro');
  if(sc){ sc.innerHTML = opts('Todas as categorias', cats); sc.value = FILTRO_CATEGORIA; }
  if(st){ st.innerHTML = opts('Todas as tabelas', tabs);    st.value = FILTRO_TABELA; }
}

function setFiltroCategoria(v){ FILTRO_CATEGORIA = v || 'todas'; render(); }
function setFiltroTabela(v){    FILTRO_TABELA    = v || 'todas'; render(); }
"""

AGREGAR_INDIVIDUAL = """function agregar(pids){
  const prof = Object.keys(DADOS)[0];
  const info = DADOS[prof];
  const semFiltro = FILTRO_CATEGORIA === 'todas' && FILTRO_TABELA === 'todas';
  let total=0, atend=0, pacientes=0;
  const pag = {}, pacs = new Set();
  const atendimentos = [];
  pids.forEach(pid=>{
    const p = info.periodos[pid];
    if(!p) return;
    if(semFiltro){
      // Caminho sem filtro: usa os totais já calculados na publicação.
      const r = p.resumo;
      total += r.total;
      atend += r.n_atend;
      pacientes += r.n_pacientes;
      Object.entries(r.por_pagamento).forEach(([tipo, d])=>{
        if(!pag[tipo]) pag[tipo] = {valor:0, qtd:0};
        pag[tipo].valor += d.valor;
        pag[tipo].qtd += d.qtd;
      });
      (p.atendimentos||[]).forEach(a=>atendimentos.push(a));
    } else {
      (p.atendimentos||[]).forEach(a0=>{
        const a = _filtrarAtend(a0);
        if(!a) return;
        total += a.valor;
        atend += 1;
        if(a.paciente) pacs.add(a.paciente);
        const tp = a.pagamento || '—';
        if(!pag[tp]) pag[tp] = {valor:0, qtd:0};
        pag[tp].valor += a.valor;
        pag[tp].qtd += 1;
        atendimentos.push(a);
      });
    }
  });
  if(!semFiltro) pacientes = pacs.size;
  return {total:Math.round(total*100)/100, atend, pacientes, pag, atendimentos};
}
"""


def patch_individual(t: str) -> str:
    if "layout-unificado-recebimento" in t:
        raise Falha("já tem o bloco de layout")

    # 1. CSS — entra logo antes do </head>
    t = troca(t, "</style>\n</head>", CSS_INDIVIDUAL, "âncora do CSS")

    # 2. Markup: marca o grupo do Intervalo e acrescenta os dois filtros
    t = troca(t,
              "<div class='f-grp'>\n        <span class='periodo-label'>Intervalo:",
              "<div class='f-grp grp-intervalo'>\n        <span class='periodo-label'>Intervalo:",
              "classe grp-intervalo")
    t = troca(t,
              "          <button class='range-btn clear' onclick='limparRange()'>Limpar</button>\n"
              "        </div>\n      </div>\n    </div>\n",
              "          <button class='range-btn clear' onclick='limparRange()'>Limpar</button>\n"
              "        </div>\n      </div>\n" + MARKUP_FILTROS + "    </div>\n",
              "markup dos filtros")

    # 3. JS: paleta + filtros
    t = troca(t, "let chartPag = null;",
              "let chartPag = null;\n" + JS_CORES + JS_FILTROS_INDIVIDUAL,
              "âncora do JS")

    # 4. agregar() recalculado
    t = troca_funcao(t, "function agregar(pids){", AGREGAR_INDIVIDUAL, "função agregar")

    # 5. preencher os selects na inicialização
    t = troca(t,
              "  deSel.value = pids[0];\n  ateSel.value = pids[pids.length-1];\n"
              "  filtroAtual = {tipo:'mes', pid:pids[pids.length-1]};",
              "  deSel.value = pids[0];\n  ateSel.value = pids[pids.length-1];\n"
              "  _preencherSelectsFiltros();\n"
              "  filtroAtual = {tipo:'mes', pid:pids[pids.length-1]};",
              "chamada na inicialização")

    # 6. gráfico de pagamento vira rosca
    t = troca_funcao(t, "function renderChartPagamento(pag){",
                     "function renderChartPagamento(pag){\n"
                     "  const entries = Object.entries(pag).sort((a,b)=>b[1].valor-a[1].valor);\n"
                     "  const labels = entries.map(([t])=>t);\n"
                     "  const vals = entries.map(([,d])=>d.valor);\n" + ROSCA,
                     "gráfico de pagamento")
    return t


# ===========================================================================
# ADMIN OXY
# ===========================================================================
CSS_ADMIN_OXY = """<style id="filtros-linha-unica">
/* Cinco campos numa linha só, como no Recebimento. A Oxy mantém o tema próprio
   da barra (fundo escuro, que é identidade dela) — aqui só se ajusta a largura
   e o tamanho dos títulos de seção. */
@media (min-width:1250px){
  .periodo-bloco{gap:8px;padding:12px 16px;align-items:center;}
  .periodo-bloco > .f-grp{min-width:0;flex:1 1 140px;}
  .periodo-bloco > .f-grp.grp-intervalo{flex:2 1 360px;}
  .periodo-bloco .prof-select{max-width:none;min-width:0;width:100%;flex:1 1 0;}
  .periodo-bloco .range-filter{min-width:0;flex:1 1 auto;flex-wrap:nowrap;gap:5px;}
  .periodo-bloco .range-filter select{min-width:0;flex:1 1 0;padding:4px 6px;}
  .periodo-bloco .periodo-label{white-space:nowrap;flex:none;}
  .periodo-bloco .range-ate{flex:none;}
  .periodo-bloco .range-btn{padding:5px 9px;white-space:nowrap;flex:none;}
  .periodo-bloco .range-sep{flex:none;}
}
.section-title{font-size:16px;font-weight:700;letter-spacing:normal;text-transform:none;}
/* Categoria e Tabela herdam o .prof-select branco que a Oxy já usava no filtro
   de Profissional — os três campos ficam iguais sobre a barra escura. */
</style>
<style id="boot-spinner-v1">"""

JS_FILTROS_ADMIN = """// ---------------------------------------------------------------------------
// Filtros de Categoria e Tabela de preço — 05/08/2026
// ---------------------------------------------------------------------------
// DADOS_RAW é o dado publicado, nunca muda. DADOS é a visão filtrada, que é o
// que todo o resto da página lê. Sem filtro, as duas são o mesmo objeto.
//
// Ao filtrar, cada mês é RECALCULADO a partir da lista de atendimentos, para
// que os indicadores não continuem mostrando o mês inteiro.
let DADOS = DADOS_RAW;
let FILTRO_CATEGORIA = 'todas';
let FILTRO_TABELA    = 'todas';

function _passa(p, a){
  const cat = p.categoria || '';
  const tab = p.tabela || a.tabela || '';
  return (FILTRO_CATEGORIA === 'todas' || cat === FILTRO_CATEGORIA)
      && (FILTRO_TABELA    === 'todas' || tab === FILTRO_TABELA);
}

function _recalcularPeriodo(r){
  const at = [], pag = {}, pcat = {}, ptab = {}, pacs = new Set();
  let total = 0;
  (r.atendimentos || []).forEach(a=>{
    const procs = (a.procedimentos || []).filter(p=>_passa(p, a));
    if(!procs.length) return;
    const v = procs.reduce((s,p)=>s+(p.valor||0), 0);
    total += v;
    at.push(Object.assign({}, a, {procedimentos:procs, valor:Math.round(v*100)/100}));
    if(a.paciente) pacs.add(a.paciente);
    const tp = a.pagamento || '—';
    if(!pag[tp]) pag[tp] = {valor:0, qtd:0};
    pag[tp].valor += v; pag[tp].qtd += 1;
    procs.forEach(p=>{
      const c = p.categoria || '—', tb = p.tabela || a.tabela || '—', q = p.qtd || 1;
      if(!pcat[c]) pcat[c] = {valor:0, qtd:0};
      pcat[c].valor += (p.valor||0); pcat[c].qtd += q;
      if(!ptab[tb]) ptab[tb] = {valor:0, qtd:0};
      ptab[tb].valor += (p.valor||0); ptab[tb].qtd += q;
    });
  });
  return {label:r.label, total:Math.round(total*100)/100, n_atend:at.length,
          n_pacientes:pacs.size, por_pagamento:pag, por_categoria:pcat,
          por_tabela:ptab, atendimentos:at};
}

function _aplicarFiltros(){
  if(FILTRO_CATEGORIA === 'todas' && FILTRO_TABELA === 'todas'){
    DADOS = DADOS_RAW;
  } else {
    const out = {};
    Object.entries(DADOS_RAW).forEach(([prof, pers])=>{
      const np = {};
      Object.entries(pers).forEach(([pid, r])=>{
        const nr = _recalcularPeriodo(r);
        if(nr.n_atend > 0) np[pid] = nr;
      });
      if(Object.keys(np).length) out[prof] = np;
    });
    DADOS = out;
  }
  _atualizarSelectProf();
}

// O profissional selecionado pode não ter nada dentro do filtro escolhido —
// nesse caso a lista volta para "Todos" em vez de mostrar uma tela vazia.
function _atualizarSelectProf(){
  const sel = document.getElementById('prof-filtro');
  if(!sel) return;
  const atual = sel.value;
  const nomes = Object.keys(DADOS).sort((a,b)=>a.localeCompare(b,'pt'));
  sel.innerHTML = `<option value=''>Todos os profissionais</option>` +
    nomes.map(p=>`<option value="${p.replace(/"/g,'&quot;')}">${p}</option>`).join('');
  sel.value = nomes.indexOf(atual) >= 0 ? atual : '';
}

function _preencherSelectsFiltros(){
  const cats = new Set(), tabs = new Set();
  Object.values(DADOS_RAW).forEach(pers=>Object.values(pers).forEach(r=>{
    Object.keys(r.por_categoria || {}).forEach(c=>cats.add(c));
    Object.keys(r.por_tabela    || {}).forEach(t=>tabs.add(t));
  }));
  const opts = (rot, vals)=> `<option value='todas'>${rot}</option>` +
    [...vals].sort((a,b)=>a.localeCompare(b,'pt'))
      .map(v=>`<option value="${v.replace(/"/g,'&quot;')}">${v}</option>`).join('');
  const sc = document.getElementById('cat-filtro');
  const st = document.getElementById('tab-filtro');
  if(sc){ sc.innerHTML = opts('Todas as categorias', cats); sc.value = FILTRO_CATEGORIA; }
  if(st){ st.innerHTML = opts('Todas as tabelas', tabs);    st.value = FILTRO_TABELA; }
}

function setFiltroCategoria(v){ FILTRO_CATEGORIA = v || 'todas'; _aplicarFiltros(); render(); }
function setFiltroTabela(v){    FILTRO_TABELA    = v || 'todas'; _aplicarFiltros(); render(); }

// A lista de meses vem sempre do dado bruto: um filtro que zera um mês não pode
// fazer o mês sumir do menu suspenso.
function pidsDisponiveis(){
  return PORDER.filter(p=>Object.values(DADOS_RAW).some(d=>d[p]));
}
function labelOf(pid){
  return Object.values(DADOS_RAW).find(d=>d[pid])?.[pid]?.label || pid;
}
"""

RANKING_ADMIN = """// Só o primeiro nome, como no Recebimento — nome inteiro em barra vertical
// vira uma parede de texto inclinado.
function nomeCurto(n){
  const p = String(n||'').trim().split(/\\s+/);
  return p[0] || n;
}

function renderChartRanking(rows, highlight){
  const ctx = document.getElementById('chart-ranking');
  if(chartRanking) chartRanking.destroy();
  if(!rows.length){ semDados(ctx, 'Sem dados no período'); return; }
  const top = rows.slice(0,10);
  // Nomes repetidos (dois "Maria") ganham a inicial do sobrenome.
  const curtos = top.map(r=>nomeCurto(r.prof));
  const labels = top.map((r,i)=>{
    if(curtos.filter(n=>n===curtos[i]).length === 1) return curtos[i];
    const p = String(r.prof).trim().split(/\\s+/);
    return p.length > 1 ? `${p[0]} ${p[1][0]}.` : curtos[i];
  });
  const vals  = top.map(r=>r.total);
  const cores = top.map(r=> (highlight && r.prof===highlight) ? CORES[1] : CORES[0]);
  chartRanking = new Chart(ctx,{
    type:'bar',
    data:{labels, datasets:[{data:vals, backgroundColor:cores, borderRadius:6, maxBarThickness:46}]},
    options:{
      responsive:true, maintainAspectRatio:false,
      plugins:{legend:{display:false},
        tooltip:{callbacks:{title:c=>top[c[0].dataIndex].prof,
                            label:c=>' '+br(c.parsed.y)}}},
      scales:{
        y:{beginAtZero:true, ticks:{callback:v=>br(v), font:{size:10}, color:EIXO_TICK},
           grid:{color:EIXO_GRADE}},
        x:{ticks:{font:{size:11}, color:EIXO_TICK}, grid:{display:false}}
      }
    }
  });
}
"""

COR_HEAT = """// Intensidade de dourado — quanto maior o valor, mais forte o fundo.
// Era uma escala vermelho→verde, que destoava da paleta do Recebimento e dava
// a impressão errada de "ruim/bom" (produzir menos não é um erro).
function corHeat(frac){
  const f = Math.max(0, Math.min(1, frac));
  return `rgba(161,137,96,${(0.08 + f*0.42).toFixed(3)})`;
}
"""


def patch_admin_oxy(t: str) -> str:
    if "cat-filtro" in t:
        raise Falha("já tem os filtros")

    # 1. Markup
    t = troca(t,
              "<div class='f-grp'>\n      <span class='periodo-label'>Intervalo:",
              "<div class='f-grp grp-intervalo'>\n      <span class='periodo-label'>Intervalo:",
              "classe grp-intervalo")
    t = troca(t,
              "      <select id='prof-filtro' class='prof-select' onchange='render()'></select>\n"
              "    </div>\n  </div>",
              "      <select id='prof-filtro' class='prof-select' onchange='render()'></select>\n"
              "    </div>\n" + MARKUP_FILTROS + "  </div>",
              "markup dos filtros")

    # 2. CSS da barra
    t = troca(t, '<style id="boot-spinner-v1">', CSS_ADMIN_OXY, "CSS da barra")

    # 3. DADOS vira visão filtrada + bloco de filtros no lugar dos dois helpers
    t = troca(t, "const DADOS   = {", "const DADOS_RAW = {", "renomear DADOS")
    t = troca(t,
              "function pidsDisponiveis(){\n"
              "  return PORDER.filter(p=>Object.values(DADOS).some(d=>d[p]));\n}\n"
              "function labelOf(pid){\n"
              "  return Object.values(DADOS).find(d=>d[pid])?.[pid]?.label || pid;\n}\n",
              JS_FILTROS_ADMIN,
              "bloco de filtros")

    # 4. Inicialização: o select de profissional passa a ser montado pelo filtro
    t = troca(t,
              "  const pfSel = document.getElementById('prof-filtro');\n"
              "  pfSel.innerHTML = `<option value=''>Todos os profissionais</option>` +\n"
              "    Object.keys(DADOS).sort((a,b)=>a.localeCompare(b,'pt'))\n"
              "      .map(p=>`<option value=\"${p.replace(/\"/g,'&quot;')}\">${p}</option>`).join('');\n",
              "  _preencherSelectsFiltros();\n  _atualizarSelectProf();\n",
              "inicialização do select")

    # 5. Gráficos e escala de destaque
    t = troca(t, "function renderChartRanking(rows, highlight){",
              JS_CORES + "\n" + "function renderChartRanking(rows, highlight){",
              "paleta antes do ranking")
    t = troca_funcao(t, "function renderChartRanking(rows, highlight){", RANKING_ADMIN, "ranking")
    t = troca_funcao(t, "function renderChartPagamento(pagGlobal){",
                     "function renderChartPagamento(pagGlobal){\n"
                     "  const entries = Object.entries(pagGlobal).sort((a,b)=>b[1].valor-a[1].valor);\n"
                     "  const labels = entries.map(([t])=>t);\n"
                     "  const vals = entries.map(([,d])=>d.valor);\n" + ROSCA,
                     "gráfico de pagamento")
    t = troca_funcao(t, "function corHeat(frac){", COR_HEAT, "escala de destaque")

    # 6. Eixos da evolução passam a usar as constantes
    t = troca(t,
              "        y:{beginAtZero:true, ticks:{callback:v=>br(v), font:{size:10}, color:'#4A6278'},\n"
              "           grid:{color:'rgba(0,0,0,0.06)'}},\n"
              "        x:{ticks:{font:{size:11,weight:'600'}, color:'#0D1E30'}, grid:{display:false}}",
              "        y:{beginAtZero:true, ticks:{callback:v=>br(v), font:{size:10}, color:EIXO_TICK},\n"
              "           grid:{color:EIXO_GRADE}},\n"
              "        x:{ticks:{font:{size:11}, color:EIXO_TICK}, grid:{display:false}}",
              "eixos da evolução")
    return t


# ===========================================================================
def main(escrever: bool) -> int:
    alvos = []
    for pasta in ("produtividade", "oxy-produtividade"):
        for p in sorted((REPO / pasta).glob("*.html")):
            if p.name == "index.html":
                if pasta == "oxy-produtividade":
                    alvos.append((p, "admin-oxy"))
                continue
            alvos.append((p, "individual"))

    print(f"\n=== Propagação do layout · escrever={escrever} ===")
    print(f"    {sum(1 for _, k in alvos if k == 'individual')} portais individuais"
          f" + {sum(1 for _, k in alvos if k == 'admin-oxy')} admin Oxy\n")

    ok, pulados = 0, []
    for path, tipo in alvos:
        bruto = path.read_bytes()
        # Os portais estão em CRLF. A leitura em modo texto converte tudo para
        # \n; na hora de gravar é preciso devolver o CRLF, senão o arquivo
        # inteiro aparece como alterado no git.
        fim = "\r\n" if bruto.count(b"\r\n") > bruto.count(b"\n") // 2 else "\n"
        t = io.open(path, encoding="utf-8").read()
        try:
            novo = patch_individual(t) if tipo == "individual" else patch_admin_oxy(t)
        except Falha as e:
            pulados.append((path, str(e)))
            print(f"  [PULADO] {path.parent.name}/{path.name[:44]:46s} {e}")
            continue
        if escrever:
            io.open(path, "w", encoding="utf-8", newline=fim).write(novo)
        ok += 1
        print(f"  [OK]     {path.parent.name}/{path.name[:44]:46s} "
              f"{len(t):>9,} -> {len(novo):>9,} chars")

    print(f"\n  {ok} arquivo(s) tratado(s) · {len(pulados)} pulado(s)")
    if not escrever:
        print("\n  [simulação] nada gravado. Rode com --escrever.")
    return len(pulados)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--escrever", action="store_true")
    raise SystemExit(1 if main(ap.parse_args().escrever) else 0)
