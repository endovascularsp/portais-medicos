# -*- coding: utf-8 -*-
r"""
_propagar_filtro_prof_admins.py — leva para os admins da Oxy e de Cirurgias o
que foi feito no `recebimento.html` em 17/08/2026.

O que muda (detalhe e motivo em [[project_filtros_gestor_recebimento]]):
  · `Profissional` deixa de ser atalho de navegação e vira FILTRO, acumulando
    com Categoria e Tabela, no mês único e no intervalo;
  · card novo "Detalhe dos Atendimentos", com a OS, só quando há um
    profissional filtrado;
  · cards de "Descontos e acréscimos" e "Total a Receber" na visão geral
    filtrada — o Total só quando o recorte é o mês todo, porque o desconto vale
    o mês inteiro e não obedece a Categoria/Tabela.

O `recebimento.html` foi o piloto e já está no ar; não é tocado aqui.

Uso:
    python _tools/_propagar_filtro_prof_admins.py            # simula
    python _tools/_propagar_filtro_prof_admins.py --escrever
"""
from __future__ import annotations
import argparse
import io
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
REPO = Path(__file__).resolve().parent.parent
PILOTO = REPO / "recebimento.html"
ALVOS = [REPO / "oxy" / "index.html", REPO / "cirurgias" / "index.html"]

# ── 1. declaração dos filtros ────────────────────────────────────────────────
DE_1 = """let FILTRO_CATEGORIA = '';
let FILTRO_TABELA    = '';"""
PARA_1 = """let FILTRO_CATEGORIA = '';
let FILTRO_TABELA    = '';
// Profissional virou FILTRO DE VERDADE em 17/08/2026. Antes era só um atalho de
// navegação: escolher um nome abria a página individual dele, e mexer em
// Categoria depois jogava a tela de volta para a visão geral — mas o <select>
// continuava mostrando o nome, então a tela mentia.
let FILTRO_PROF = '';
// Guarda o conjunto filtrado por empresa/categoria/tabela mas SEM o filtro de
// profissional, para o <select> continuar oferecendo todos os nomes daquele
// recorte — senão, ao escolher uma pessoa, ela seria a única opção da lista.
let _PROFS_ANTES_DO_FILTRO_PROF = {};

function _soDoProfFiltrado(mapa){
  if(!FILTRO_PROF) return mapa;
  const out = {};
  if(mapa[FILTRO_PROF]) out[FILTRO_PROF] = mapa[FILTRO_PROF];
  return out;
}"""

# ── 2. mês único ─────────────────────────────────────────────────────────────
DE_2 = """function _aplicarFiltros(){
  const novo = _filtrarProfs(_DADOS_PROFS_PERIODO);
  Object.keys(DADOS_PROFS).forEach(k => delete DADOS_PROFS[k]);
  Object.entries(novo).forEach(([k,v]) => DADOS_PROFS[k] = v);
}"""
PARA_2 = """function _aplicarFiltros(){
  const novo = _filtrarProfs(_DADOS_PROFS_PERIODO);
  _PROFS_ANTES_DO_FILTRO_PROF = novo;
  const comProf = _soDoProfFiltrado(novo);
  Object.keys(DADOS_PROFS).forEach(k => delete DADOS_PROFS[k]);
  Object.entries(comProf).forEach(([k,v]) => DADOS_PROFS[k] = v);
}"""

# ── 3. intervalo ─────────────────────────────────────────────────────────────
DE_3 = """  Object.keys(DADOS_PROFS).forEach(k => delete DADOS_PROFS[k]);
  Object.assign(DADOS_PROFS, agg);"""
PARA_3 = """  // O filtro de profissional vale no intervalo também — entra aqui, depois da
  // agregação dos meses.
  _PROFS_ANTES_DO_FILTRO_PROF = agg;
  Object.keys(DADOS_PROFS).forEach(k => delete DADOS_PROFS[k]);
  Object.assign(DADOS_PROFS, _soDoProfFiltrado(agg));"""

# ── 4. handler do select ─────────────────────────────────────────────────────
# Nestes dois a última linha é compacta (`if(...) mostrarProf(...)` numa linha
# só), diferente do piloto. Mesma lógica, formatação diferente — por isso a
# âncora é a daqui, não a do recebimento.html.
DE_4 = """function filtrarPorProf(profKey){
  if(!profKey){
    document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
    const gv = document.getElementById('view-geral');
    if(gv) gv.classList.add('active');
    renderGeral();
    return;
  }
  if(DADOS_PROFS[profKey]) mostrarProf(profKey);
}"""
PARA_4 = """function filtrarPorProf(profKey){
  FILTRO_PROF = profKey || '';
  _reaplicar();
}"""

# ── 5. repopulação do select ─────────────────────────────────────────────────
DE_5 = """  const valorAtual = sel.value;
  const profs = Object.entries(DADOS_PROFS)
    .filter(([,v])=> (v.resumo?.['Repasse Profissional (R$)']||0) > 0
                  || (v.resumo?.['Valor recebido']||0) > 0)
    .sort((a,b)=>a[1].profissional.localeCompare(b[1].profissional,'pt-BR'));
  sel.innerHTML = '<option value="">— Visão Geral —</option>' +
    profs.map(([k,v])=>'<option value="'+k+'">'+v.profissional+'</option>').join('');
  if(valorAtual && DADOS_PROFS[valorAtual]) sel.value = valorAtual;
  else sel.value = '';"""
PARA_5 = """  // A lista vem do recorte SEM o filtro de profissional: com ele, a pessoa
  // escolhida seria a única opção e não haveria como trocar para outra.
  const base = Object.keys(_PROFS_ANTES_DO_FILTRO_PROF||{}).length
    ? _PROFS_ANTES_DO_FILTRO_PROF : DADOS_PROFS;
  const profs = Object.entries(base)
    .filter(([,v])=> (v.resumo?.['Repasse Profissional (R$)']||0) > 0
                  || (v.resumo?.['Valor recebido']||0) > 0)
    .sort((a,b)=>a[1].profissional.localeCompare(b[1].profissional,'pt-BR'));
  sel.innerHTML = '<option value="">— Todos —</option>' +
    profs.map(([k,v])=>'<option value="'+k+'">'+v.profissional+'</option>').join('');
  if(FILTRO_PROF && base[FILTRO_PROF]){ sel.value = FILTRO_PROF; return; }
  if(FILTRO_PROF){
    // Cair o filtro aqui, depois de DADOS_PROFS já ter sido filtrado por ele,
    // deixaria a tela vazia: é preciso devolver o recorte inteiro.
    FILTRO_PROF = '';
    Object.keys(DADOS_PROFS).forEach(k => delete DADOS_PROFS[k]);
    Object.entries(base).forEach(([k,v]) => DADOS_PROFS[k] = v);
  }
  sel.value = '';"""

# ── 6. markup do card de detalhe ─────────────────────────────────────────────
DE_6 = """          </tr></thead><tbody id='body-repasse'></tbody></table>
        </div>
      </div>"""
PARA_6 = """          </tr></thead><tbody id='body-repasse'></tbody></table>
        </div>
      </div>
      <!-- Detalhe por atendimento. Só aparece com um profissional filtrado:
           com todos, seriam centenas de linhas sem utilidade. -->
      <div class='full-col card' id='card-detalhe' style='display:none'>
        <div class='section-title'>&#128203; Detalhe dos Atendimentos
          <span class='badge' id='badge-detalhe'></span></div>
        <div class='table-scroll'>
          <table class='repasse-table'><thead><tr>
            <th>N&#186; OS</th>
            <th>Data comp.</th>
            <th>Paciente</th>
            <th>Procedimento</th>
            <th>Categoria</th>
            <th>Tabela</th>
            <th>Pagamento</th>
            <th style='text-align:right'>Valor Recebido</th>
            <th style='text-align:right'>Valor L&#237;quido</th>
            <th style='text-align:center'>%</th>
            <th style='text-align:right'>Repasse Prof.</th>
          </tr></thead><tbody id='body-detalhe'></tbody>
          <tfoot><tr id='foot-detalhe'></tr></tfoot></table>
        </div>
      </div>"""

# ── 7. render do detalhe, no fim de renderGeral ──────────────────────────────
DE_7 = """    renderTabelas(todasTabelas,'origem-geral-lista','chart-origem-geral');
  }
}"""
PARA_7 = """    renderTabelas(todasTabelas,'origem-geral-lista','chart-origem-geral');
  }

  _renderDetalhe(todos);
}

// Lista atendimento por atendimento, com a OS. Só com profissional filtrado.
// Respeita Categoria e Tabela porque lê `d.atendimentos`, que _recalcularProf
// já entregou filtrado.
function _renderDetalhe(todos){
  const card = document.getElementById('card-detalhe');
  const corpo = document.getElementById('body-detalhe');
  if(!card || !corpo) return;
  if(!FILTRO_PROF){ card.style.display='none'; corpo.innerHTML=''; return; }

  const ats = (todos||[]).flatMap(d => d.atendimentos || []);
  if(!ats.length){ card.style.display='none'; corpo.innerHTML=''; return; }

  // Mais recente primeiro; a data vem como dd/mm/aaaa, então compara invertida.
  const chaveData = s => String(s||'').split('/').reverse().join('');
  const ord = ats.slice().sort((a,b) =>
    chaveData(b['Data compensação']).localeCompare(chaveData(a['Data compensação'])));

  const pct = a => {
    const p = a['% Aplicado'];
    return (p===undefined||p===null||p==='') ? '—' : (Number(p)*100).toFixed(0)+'%';
  };
  corpo.innerHTML = ord.map(a =>
    '<tr>'+
    '<td style="font-weight:600">'+(a['Nº OS']||'—')+'</td>'+
    '<td>'+(a['Data compensação']||'—')+'</td>'+
    '<td class="prof">'+(a['Paciente']||'—')+'</td>'+
    '<td>'+(a['Procedimento']||'—')+'</td>'+
    '<td>'+(a['Categoria']||'—')+'</td>'+
    '<td>'+(a['Tabela']||'—')+'</td>'+
    '<td>'+(a['Tipo de pagamento']||'—')+'</td>'+
    '<td class="r">'+fmtBRL(a['Valor recebido']||0)+'</td>'+
    '<td class="r" style="color:var(--azul)">'+fmtBRL(a['Valor Líquido']||0)+'</td>'+
    '<td style="text-align:center">'+pct(a)+'</td>'+
    '<td class="r" style="color:var(--verde);font-weight:600">'+
      fmtBRL(a['Repasse Profissional (R$)']||0)+'</td>'+
    '</tr>').join('');

  const soma = c => ord.reduce((s,a)=>s+(a[c]||0),0);
  const pe = document.getElementById('foot-detalhe');
  if(pe) pe.innerHTML =
    '<td colspan="7" style="font-weight:700">TOTAL — '+ord.length+' atendimento(s)</td>'+
    '<td class="r" style="font-weight:700">'+fmtBRL(soma('Valor recebido'))+'</td>'+
    '<td class="r" style="font-weight:700">'+fmtBRL(soma('Valor Líquido'))+'</td>'+
    '<td></td>'+
    '<td class="r" style="font-weight:700">'+fmtBRL(soma('Repasse Profissional (R$)'))+'</td>';

  const bd = document.getElementById('badge-detalhe');
  if(bd) bd.textContent = ord.length + (ord.length===1 ? ' atendimento' : ' atendimentos');
  card.style.display='';
}"""

# ── 8. cards de desconto na visão geral ──────────────────────────────────────
DE_8 = "  document.getElementById('metrics-geral').innerHTML="
PARA_8 = """  // O lançamento de desconto é por PESSOA e vale o MÊS INTEIRO — não obedece a
  // Categoria nem a Tabela. Por isso "Total a Receber" só aparece quando o
  // recorte é o mês todo: com filtro de categoria, "repasse parcial menos
  // desconto do mês" seria um número sem significado.
  let kpiAjustes = '';
  if(FILTRO_PROF && todos.length === 1){
    const ef = Number(todos[0].resumo?.['Ajustes (R$)'] || 0);
    const itens = (todos[0].ajustes || []).length;
    const parcial = !!(FILTRO_CATEGORIA || FILTRO_TABELA);
    const sinal = ef < 0 ? '&minus; ' : (ef > 0 ? '+ ' : '');
    const legenda = itens
      ? (parcial ? 'Do m&ecirc;s inteiro — n&atilde;o segue os filtros acima'
                 : itens + (itens===1 ? ' lan&ccedil;amento' : ' lan&ccedil;amentos'))
      : 'Nada descontado ou somado neste m&ecirc;s';
    kpiAjustes =
      '<div class="kpi cinza"><div class="kpi-ic">💼</div><div class="kpi-label">Descontos e acr&eacute;scimos</div><div class="kpi-val">'
      + sinal + fmtBRL(Math.abs(ef))
      + '</div><div class="kpi-foot"><span style="opacity:0.6">'+legenda+'</span></div></div>';
    if(!parcial){
      kpiAjustes +=
        '<div class="kpi gold"><div class="kpi-ic">🏦</div><div class="kpi-label">Total a Receber</div><div class="kpi-val">'
        + fmtBRL(totalRep + ef)
        + '</div><div class="kpi-foot"><span style="opacity:0.6">O que entra na conta dele</span></div></div>';
    }
  }

  document.getElementById('metrics-geral').innerHTML="""

# O último card da fileira muda por arquivo (o texto do rodapé difere), então a
# âncora é só o fecho da linha de Receita Clínica.
SUFIXO_KPI = "' do líquido</span></div></div>';"
SUFIXO_KPI_NOVO = "' do líquido</span></div></div>'+\n    kpiAjustes;"

TROCAS = [("declaração dos filtros", DE_1, PARA_1),
          ("filtro no mês único",    DE_2, PARA_2),
          ("filtro no intervalo",    DE_3, PARA_3),
          ("handler do select",      DE_4, PARA_4),
          ("repopulação do select",  DE_5, PARA_5),
          ("markup do detalhe",      DE_6, PARA_6),
          ("render do detalhe",      DE_7, PARA_7),
          ("cards de desconto",      DE_8, PARA_8),
          ("fecho dos KPIs",         SUFIXO_KPI, SUFIXO_KPI_NOVO)]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--escrever", action="store_true")
    a = ap.parse_args()

    falhou = False
    for alvo in ALVOS:
        rel = alvo.relative_to(REPO)
        print(f"\n=== {rel} ===")
        if not alvo.exists():
            print("   ABORTADO: não existe"); falhou = True; continue
        txt = alvo.read_text(encoding="utf-8")
        if "FILTRO_PROF" in txt:
            print("   já propagado — pulando (o script é seguro de repetir)")
            continue
        novo = txt
        for nome, de, para in TROCAS:
            n = novo.count(de)
            if n != 1:
                print(f"   ABORTADO em '{nome}': âncora aparece {n}x, esperado 1")
                falhou = True
                break
            novo = novo.replace(de, para, 1)
            print(f"   ok  {nome}")
        else:
            if a.escrever:
                alvo.write_text(novo, encoding="utf-8")
                print(f"   GRAVADO (+{len(novo)-len(txt)} bytes)")
            else:
                print(f"   [simulação] gravaria +{len(novo)-len(txt)} bytes")
    if not a.escrever:
        print("\n[simulação] nada gravado. Rode com --escrever.")
    return 1 if falhou else 0


if __name__ == "__main__":
    sys.exit(main())
