# -*- coding: utf-8 -*-
"""
_produtividade_origem.py — leva para a Produtividade o "Origem dos Atendimentos"
(Particular x Planos) que já existe no card de Recebimento, e acerta as colunas
da lista de atendimentos.

Pedido do Thiago em 11/08/2026: os dois gráficos iguais aos do Recebimento, e a
tabela de baixo com Data | Paciente (com os procedimentos sob o nome) |
Pagamento | Tabela de preço | Valor.

Nada de dado novo é preciso: `por_tabela` e a tabela de cada procedimento já
viajam no PDATA desde 05/08/2026, quando entrou o filtro de Tabela. O valor da
fatia sai dos PROCEDIMENTOS, não do atendimento, porque uma mesma OS pode
misturar tabelas — somar pelo atendimento jogaria a OS inteira para o convênio
de um procedimento só.

Uso:
    python _tools/_produtividade_origem.py --conferir
    python _tools/_produtividade_origem.py --piloto
    python _tools/_produtividade_origem.py --todos
"""
from __future__ import annotations
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
MARCA = "origem-produtividade"        # já aplicado? não repete

# ---------------------------------------------------------------------------
# CSS — mesmo desenho do Recebimento, com os tokens da Produtividade
# ---------------------------------------------------------------------------
CSS = """<style id="origem-produtividade">
/* ============================================================================
   Origem dos Atendimentos — Particular x Planos (11/08/2026)

   Mesmo desenho do card de Recebimento: pílulas com o total de cada lado, uma
   barra de proporção e a lista das tabelas de preço. Dourado é particular,
   navy é plano — a mesma dupla de cores dos gráficos daqui.
   ============================================================================ */
.origem-badge{font-size:11px;font-weight:700;padding:3px 10px;border-radius:12px;
  background:#EEF3F9;color:#2E6DA4;text-transform:none;letter-spacing:normal;}
.origem-pills{display:flex;gap:10px;margin-bottom:16px;flex-wrap:wrap;}
.origem-pill{padding:8px 16px;border-radius:24px;font-size:13px;font-weight:700;
  display:flex;align-items:center;gap:8px;}
.origem-pill.particular{background:#F5F0E6;color:#8A7348;border:1.5px solid #E0D2B4;}
.origem-pill.plano{background:#E7EDF5;color:#23476F;border:1.5px solid #BACBE0;}
.origem-bar{height:12px;border-radius:6px;background:#DDE4ED;overflow:hidden;margin-bottom:14px;}
.origem-bar-inner{height:100%;border-radius:6px;transition:width .6s ease;}
.tabela-row{display:flex;align-items:center;justify-content:space-between;
  padding:9px 4px;border-bottom:1px solid #EDF1F6;font-size:13px;}
.tabela-row:last-child{border-bottom:none;}
.tabela-nome{font-weight:600;color:var(--texto);}
.tabela-tipo{font-size:11px;font-weight:600;padding:2px 8px;border-radius:12px;margin-left:8px;}
.tabela-tipo.part{background:#F5F0E6;color:#8A7348;}
.tabela-tipo.plano{background:#E7EDF5;color:#23476F;}
.tabela-val{font-weight:700;color:#8A7348;text-align:right;}
.tabela-pct{font-size:12px;color:var(--texto2);margin-left:10px;min-width:44px;text-align:right;}
.origem-vazio{padding:26px 4px;color:var(--texto2);font-size:13px;text-align:center;}
/* Chip da coluna "Tabela de preço" da lista de atendimentos */
.tabela-chip{display:inline-block;font-size:11px;font-weight:700;padding:2px 8px;
  border-radius:10px;white-space:nowrap;margin:1px 2px 1px 0;}
.tabela-chip.part{background:#F5F0E6;color:#8A7348;}
.tabela-chip.plano{background:#E7EDF5;color:#23476F;}
</style>
</head>"""

# ---------------------------------------------------------------------------
# JS comum aos dois tipos de portal
# ---------------------------------------------------------------------------
JS_COMUM = """
// ---------------------------------------------------------------------------
// Origem dos Atendimentos — Particular x Planos (11/08/2026)
// ---------------------------------------------------------------------------
// Plano é a tabela de preço que traz OMINT ou SULAM no nome; o resto é
// particular. É o MESMO teste do card de Recebimento, de propósito: se um dia
// mudar, muda nos dois, senão o médico vê dois números para a mesma coisa.
const COR_PARTICULAR = '#A18960';
const COR_PLANO      = '#23476F';
let chartOrigem = null;

function ehPlano(tab){ return /OMINT|SULAM/i.test(tab || ''); }

// A tabela mora no procedimento. O atendimento só serve de reserva, para
// publicação antiga em que o procedimento ainda não carregava o campo.
function _tabDe(p, a){
  return (p && p.tabela) || (a && a.tabela) || '(sem tabela)';
}

function agruparTabelas(atends){
  const acc = {};
  (atends || []).forEach(a=>{
    (a.procedimentos || []).forEach(p=>{
      const t = _tabDe(p, a);
      if(!acc[t]) acc[t] = {valor:0, qtd:0};
      acc[t].valor += p.valor || 0;
      acc[t].qtd   += p.qtd   || 1;
    });
  });
  return Object.entries(acc)
    .map(([tabela, d])=>({tabela, valor:Math.round(d.valor*100)/100, qtd:d.qtd}))
    .sort((x,y)=>y.valor-x.valor);
}

// Uma OS pode ter procedimentos de tabelas diferentes: aparecem todas, sem repetir.
function chipsTabela(procs, fallback){
  const ts = [...new Set((procs||[]).map(p=>_tabDe(p, {tabela:fallback})))];
  if(!ts.length) return '—';
  return ts.map(t=>`<span class="tabela-chip ${ehPlano(t)?'plano':'part'}">${t}</span>`).join('');
}

function renderOrigem(atends){
  const lista = document.getElementById('origem-lista');
  if(!lista) return;
  const linhas = agruparTabelas(atends);
  const total  = linhas.reduce((s,t)=>s+t.valor, 0);
  const plano  = linhas.filter(t=>ehPlano(t.tabela)).reduce((s,t)=>s+t.valor, 0);
  const part   = total - plano;
  const pct    = total>0 ? part/total : 0;

  if(!linhas.length){
    lista.innerHTML = '<div class="origem-vazio">Sem atendimentos no período selecionado.</div>';
    if(chartOrigem){ chartOrigem.destroy(); chartOrigem = null; }
    return;
  }

  const pills =
    '<div class="origem-pills">' +
    '<div class="origem-pill particular">📈 Particular: ' + br(part) +
      ' <span style="opacity:.7">(' + (pct*100).toFixed(1) + '%)</span></div>' +
    '<div class="origem-pill plano">🏥 Planos: ' + br(plano) +
      ' <span style="opacity:.7">(' + ((1-pct)*100).toFixed(1) + '%)</span></div>' +
    '</div>' +
    '<div class="origem-bar"><div class="origem-bar-inner" style="width:100%;background:linear-gradient(90deg,' +
      COR_PARTICULAR + ' ' + (pct*100).toFixed(1) + '%,' + COR_PLANO + ' ' + (pct*100).toFixed(1) + '%)"></div></div>';

  const corpo = linhas.map(t=>{
    const cls = ehPlano(t.tabela) ? 'plano' : 'part';
    const rot = ehPlano(t.tabela) ? 'Plano' : 'Particular';
    return '<div class="tabela-row">' +
      '<div style="display:flex;align-items:center">' +
        '<span class="tabela-nome">' + (t.tabela || '—') + '</span>' +
        '<span class="tabela-tipo ' + cls + '">' + rot + '</span></div>' +
      '<div style="display:flex;align-items:center">' +
        '<span class="tabela-val">' + br(t.valor) + '</span>' +
        '<span class="tabela-pct">' + (total>0 ? ((t.valor/total)*100).toFixed(1) : '0') + '%</span></div>' +
      '</div>';
  }).join('');

  lista.innerHTML = pills + corpo;

  const ctx = document.getElementById('chart-origem');
  if(!ctx) return;
  if(chartOrigem) chartOrigem.destroy();
  chartOrigem = new Chart(ctx, {
    type:'doughnut',
    data:{labels:['Particular','Planos de Saúde'],
          datasets:[{data:[part, plano], backgroundColor:[COR_PARTICULAR, COR_PLANO],
                     borderColor:'#fff', borderWidth:2}]},
    options:{
      responsive:true, maintainAspectRatio:false,
      plugins:{
        legend:{position:'right', labels:{font:{size:11}, boxWidth:14, padding:10, color:'#0D1E30'}},
        tooltip:{callbacks:{label:c=>{
          const tot = c.dataset.data.reduce((a,b)=>a+b, 0);
          const v = c.parsed, p = tot>0 ? ((v/tot)*100).toFixed(1) : '0';
          return ' ' + br(v) + ' (' + p + '%)';
        }}}}
    }
  });
}
"""

# ---------------------------------------------------------------------------
# Portal individual
# ---------------------------------------------------------------------------
MARKUP_IND = """    <div class='grid-pag'>
      <div class='pag-section'>
        <div class='section-title'>🏷️ Origem dos Atendimentos <span class='origem-badge'>Particular vs Planos</span></div>
        <div id='origem-lista'></div>
      </div>
      <div class='pag-section'>
        <div class='section-title'>◕ Mix Particular / Planos</div>
        <div class='chart-wrap'><canvas id='chart-origem'></canvas></div>
      </div>
    </div>
    <div class='table-section'>"""

TROCAS_IND = [
    # 1. CSS
    ("</head>", CSS, 1),
    # 2. os dois painéis, antes da lista de atendimentos
    ("    <div class='table-section'>", MARKUP_IND, 1),
    # 3. cabeçalho da lista: a coluna "Procedimentos" vivia vazia (os
    #    procedimentos já aparecem sob o nome do paciente) e vira "Tabela de preço"
    ("""              <th>Procedimentos</th>
              <th>Pagamento</th>""",
     """              <th>Pagamento</th>
              <th>Tabela de preço</th>""", 1),
    # 4. a célula vazia correspondente
    ("""      <td></td>
      <td>${badgePag(a.pagamento)}${parc}</td>""",
     """      <td>${badgePag(a.pagamento)}${parc}</td>
      <td>${chipsTabela(a.procedimentos, a.tabela)}</td>""", 1),
    # 5. JS
    ("function render(){", JS_COMUM + "\nfunction render(){", 1),
    # 6. desenhar junto com o resto
    ("  renderChartPagamento(pag);",
     "  renderChartPagamento(pag);\n  renderOrigem(atendimentos);", 1),
    # 7. export com a mesma coluna da tela
    ("""  const linhas = [['Data','Paciente','Procedimentos','Forma de Pagamento','Parcelas','Valor (R$)']];""",
     """  const linhas = [['Data','Paciente','Procedimentos','Forma de Pagamento','Tabela de preço','Parcelas','Valor (R$)']];""", 1),
    ("""    linhas.push([ a.data || '', a.paciente || '', procs, a.pagamento || '',
                  (a.parcelas || 1), valor.toFixed(2).replace('.', ',') ]);""",
     """    const tabs = [...new Set((a.procedimentos || []).map(p => _tabDe(p, a)))].join(' | ');
    linhas.push([ a.data || '', a.paciente || '', procs, a.pagamento || '', tabs,
                  (a.parcelas || 1), valor.toFixed(2).replace('.', ',') ]);""", 1),
    ("""  linhas.push(['', '', '', '', 'TOTAL', totalGeral.toFixed(2).replace('.', ',')]);""",
     """  linhas.push(['', '', '', '', '', 'TOTAL', totalGeral.toFixed(2).replace('.', ',')]);""", 1),
]

# ---------------------------------------------------------------------------
# Admin (visão geral)
# ---------------------------------------------------------------------------
MARKUP_ADM = """  <div class='grid-2'>
    <div class='card-box chart-card'>
      <div class='section-title'>🏷️ Origem dos Atendimentos <span class='origem-badge'>Particular vs Planos</span></div>
      <div id='origem-lista'></div>
    </div>
    <div class='card-box chart-card'>
      <div class='section-title'>◕ Mix Particular / Planos</div>
      <div class='chart-wrap'><canvas id='chart-origem'></canvas></div>
    </div>
  </div>
  <div class='pac-section'>"""

TROCAS_ADM = [
    ("</head>", CSS, 1),
    ("  <div class='pac-section'>", MARKUP_ADM, 1),
    # a lista do admin precisa carregar a tabela junto
    ("""            pagamento:a.pagamento||'', parcelas:a.parcelas||1, valor:a.valor||0""",
     """            pagamento:a.pagamento||'', parcelas:a.parcelas||1, valor:a.valor||0,
            tabela:a.tabela||''""", 1),
    ("""  const head = `<tr>${showProf?'<th>Profissional</th>':''}<th>Data</th><th>Paciente</th><th>Pagamento</th><th style='text-align:right'>Valor</th></tr>`;""",
     """  const head = `<tr>${showProf?'<th>Profissional</th>':''}<th>Data</th><th>Paciente</th><th>Pagamento</th><th>Tabela de preço</th><th style='text-align:right'>Valor</th></tr>`;""", 1),
    ("""<td>${badgePag(l.pagamento)}${parc}</td>""",
     """<td>${badgePag(l.pagamento)}${parc}</td><td>${chipsTabela(l.procArr, l.tabela)}</td>""", 1),
    ("function renderPacientes(){", JS_COMUM + "\nfunction renderPacientes(){", 1),
    # desenha nos dois caminhos do render (visão geral e profissional filtrado)
    ("""function render(){
  renderPacientes();""",
     """function render(){
  renderPacientes();
  {
    // A origem acompanha o filtro de profissional e o de período, por isso é
    // calculada aqui em cima: o render() de profissional sai antes do fim.
    const _pf = (document.getElementById('prof-filtro')||{}).value || null;
    const _at = coletarAtendimentos(_pidsSel(), _pf).linhas
                  .map(l=>({procedimentos:l.procArr, tabela:l.tabela, valor:l.valor}));
    renderOrigem(_at);
  }""", 1),
    ("""  const head = ['Profissional','Data','Paciente','Procedimentos','Pagamento','Parcelas','Valor'];""",
     """  const head = ['Profissional','Data','Paciente','Procedimentos','Pagamento','Tabela de preço','Parcelas','Valor'];""", 1),
    ("""  const linhas = _pacLast.map(l=>[l.prof,l.data,l.paciente,procStr(l),l.pagamento,l.parcelas,l.valor.toFixed(2).replace('.',',')].map(esc).join(';'));""",
     """  const tabStr = l => [...new Set((l.procArr||[]).map(p=>_tabDe(p, l)))].join(' | ');
  const linhas = _pacLast.map(l=>[l.prof,l.data,l.paciente,procStr(l),l.pagamento,tabStr(l),l.parcelas,l.valor.toFixed(2).replace('.',',')].map(esc).join(';'));""", 1),
]


def aplicar(caminho: Path, trocas, escrever: bool) -> str:
    txt = caminho.read_text(encoding="utf-8")
    if MARCA in txt:
        return "já tinha"
    for velho, novo, n in trocas:
        achou = txt.count(velho)
        if achou != n:
            return f"ABORTADO: esperava {n} ocorrência(s) de {velho[:48]!r}, achei {achou}"
        txt = txt.replace(velho, novo, n)
    if escrever:
        caminho.write_text(txt, encoding="utf-8")
    return "ok"


def alvos():
    ind = sorted(p for p in (RAIZ / "produtividade").glob("*.html") if p.name != "index.html")
    ind += sorted(p for p in (RAIZ / "oxy-produtividade").glob("*.html") if p.name != "index.html")
    adm = [RAIZ / "produtividade" / "index.html", RAIZ / "oxy-produtividade" / "index.html"]
    return ind, adm


def main():
    conferir = "--conferir" in sys.argv
    piloto   = "--piloto"   in sys.argv
    todos    = "--todos"    in sys.argv
    if not (conferir or piloto or todos):
        print(__doc__)
        return

    ind, adm = alvos()
    if piloto:
        ind = [RAIZ / "produtividade" / "Igor_Rafael_Sincos_Produtividade.html"]
        adm = [RAIZ / "produtividade" / "index.html"]

    escrever = not conferir
    for p in adm:
        print(f"{aplicar(p, TROCAS_ADM, escrever):<9} {p.relative_to(RAIZ)}")
    for p in ind:
        print(f"{aplicar(p, TROCAS_IND, escrever):<9} {p.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
