"""Propaga o refactor visual do piloto Igor pros outros 14 portais Endo individuais.

Aplica as mesmas substituições de string que foram feitas manualmente no Igor.
Preserva: PDATA, PROF_FIXO, LINKS, hash de senha, link do Hub específico de cada
médico.

Uso: python _propagar_visual_endo_individuais.py [--dry-run]
"""
import os, re, sys, shutil

ARQUIVOS = [
    'Andrea_Ostaszewski_Klepacz.html',
    'Carolina_Mardegan.html',
    'Christiane_Sayuri_Lopes_Inoue.html',
    'Clara_Silva_Freitas.html',
    'Daniela_Viese_Roth.html',
    'Eduardo_Araujo_Pires.html',
    'Fernanda_Liporaci_Villela_Zuchi.html',
    'Gabriela_Richards.html',
    'Jonathan_Batista_Souza.html',
    'João_Fukuda.html',
    'Larissa_Medeiros_Santos.html',
    'Manoel_Augusto_Lobato.html',
    'Maria_Fernanda_R_Fernandes.html',
    'Simone_Matsuda_Torricelli.html',
]
DRY = '--dry-run' in sys.argv

# ===== Substituições (OLD → NEW) =====
# Cada item: (descrição, old_str, new_str) ou (descrição, regex, replacement)

SUBS = []

# 1. :root — adicionar variáveis paleta nova
SUBS.append(('vars CSS :root',
"""  --header-bg:#0B1F3A;--header-linha:#1A5296;}""",
"""  --header-bg:#0B1F3A;--header-linha:#1A5296;
  /* Paleta nova — mesma do Recebimento Endo (gold escuro + navy médio) */
  --gold:#A18960;--gold-cl:#c7ad82;--gold-bg:#F5F0E5;--gold-borda:rgba(161,137,96,0.40);
  --navy-med:#23476f;--navy-bg:#E0E8F0;--navy-borda:rgba(35,71,111,0.40);
  --navy:#0B1F3A;--azul:#1A5296;--cinza-cl:#F7FAFD;--borda:#C4D4E8;--texto2:#4A6278;}"""))

# 2. body — overflow-x:hidden
SUBS.append(('body overflow-x',
"""body{font-family:'Segoe UI',system-ui,sans-serif;background:var(--cinza-bg);color:var(--texto-primario);min-height:100vh;}""",
"""body{font-family:'Segoe UI',system-ui,sans-serif;background:var(--cinza-bg);color:var(--texto-primario);min-height:100vh;overflow-x:hidden;}
html{overflow-x:hidden;}"""))

# 3. .prof-header compactado
SUBS.append(('prof-header compacto',
""".prof-header{background:linear-gradient(135deg,var(--azul-escuro) 0%,var(--azul-medio) 100%);color:white;border-radius:var(--radius);padding:22px 26px;margin-bottom:22px;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:12px;}
.prof-header h2{font-size:20px;font-weight:700;}
.prof-header-actions{display:flex;gap:8px;align-items:center;}
.prof-avatar{width:56px;height:56px;border-radius:50%;background:rgba(255,255,255,0.2);display:flex;align-items:center;justify-content:center;font-size:22px;font-weight:700;}""",
""".prof-header{background:linear-gradient(135deg,var(--azul-escuro) 0%,var(--azul-medio) 100%);color:white;border-radius:var(--radius);padding:10px 16px;margin-bottom:16px;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:10px;}
.prof-header h2{font-size:14px;font-weight:700;display:inline;margin-right:8px;}
.prof-header > div:first-child{display:flex;align-items:baseline;gap:8px;flex-wrap:wrap;}
.prof-header > div:first-child span{font-size:12px;opacity:0.85;}
.prof-header-actions{display:none;} /* botoes movidos pro header top */
.prof-avatar{display:none;}"""))

# 4. Bloco grande de CSS: .portais-nav antigo → novo (com header-actions, periodo-bloco, kpis, etc)
OLD_PORTAIS_NAV = """/* ===== NAVEGAÇÃO MULTI-PORTAL ===== */
.portais-nav{background:#162d50;border-bottom:1px solid rgba(255,255,255,0.10);
  padding:7px 32px;display:flex;align-items:center;gap:10px;flex-wrap:wrap;}
.portais-nav-label{color:rgba(255,255,255,0.5);font-size:11px;font-weight:600;
  letter-spacing:0.6px;text-transform:uppercase;white-space:nowrap;}
.portais-nav-btn{display:inline-flex;align-items:center;gap:6px;
  padding:5px 14px;border-radius:20px;font-size:12px;font-weight:600;
  text-decoration:none;transition:all 0.15s;white-space:nowrap;border:1.5px solid;}

.portais-nav-btn.hub{color:#94a3b8;border-color:rgba(148,163,184,0.35);background:rgba(148,163,184,0.08);}
.portais-nav-btn.hub:hover{background:rgba(148,163,184,0.20);border-color:#94a3b8;}
.portais-nav-btn.endo{color:#7eb8f7;border-color:rgba(126,184,247,0.35);background:rgba(126,184,247,0.08);}
.portais-nav-btn.endo:hover{background:rgba(126,184,247,0.18);border-color:#7eb8f7;}
.portais-nav-btn.oxy{color:#6dd5a0;border-color:rgba(109,213,160,0.35);background:rgba(109,213,160,0.08);}
.portais-nav-btn.oxy:hover{background:rgba(109,213,160,0.18);border-color:#6dd5a0;}
.portais-nav-btn.cir{color:#f5a623;border-color:rgba(245,166,35,0.35);background:rgba(245,166,35,0.08);}
.portais-nav-btn.cir:hover{background:rgba(245,166,35,0.18);border-color:#f5a623;}
.portais-nav-btn.prod{color:#c084fc;border-color:rgba(192,132,252,0.35);background:rgba(192,132,252,0.08);}
.portais-nav-btn.prod:hover{background:rgba(192,132,252,0.18);border-color:#c084fc;}
.portais-nav-btn.prod.active{background:rgba(192,132,252,0.22);border-color:#c084fc;font-weight:700;}
/* mobile-600 */
@media(max-width:600px){
  .header{padding:0 14px;}
  .portais-nav{padding:7px 14px;}
  .metric-valor{font-size:21px;}
  .metric-card{padding:14px 16px;}
  .chart-wrap{height:220px;}
}"""

NEW_PORTAIS_NAV = """/* ─────────────────── Padrão visual novo (espelha Recebimento Endo) ─────────────────── */
/* Portais-nav: alinhado com o admin-nav do recebimento (fundo navy, ativo gold) */
.portais-nav{background:var(--navy);border-bottom:1px solid rgba(255,255,255,0.08);
  padding:8px 32px;display:flex;align-items:center;gap:10px;flex-wrap:wrap;}
.portais-nav-label{color:rgba(255,255,255,0.55);font-size:11px;font-weight:700;
  letter-spacing:0.5px;text-transform:uppercase;white-space:nowrap;margin-right:4px;}
.portais-nav-btn{display:inline-flex;align-items:center;gap:5px;padding:5px 14px;
  border-radius:20px;font-size:12px;font-weight:600;cursor:pointer;text-decoration:none;
  border:1.5px solid;transition:all 0.15s;background:#fff;white-space:nowrap;}
.portais-nav-btn.endo{color:var(--azul);border-color:rgba(255,255,255,0.25);}
.portais-nav-btn.endo:hover{background:var(--azul);color:#fff;border-color:var(--azul);}
.portais-nav-btn.endo.active{color:#fff;border-color:var(--gold);background:var(--gold);opacity:0.95;cursor:default;pointer-events:none;}
.portais-nav-btn.oxy{color:#6dd5a0;border-color:rgba(109,213,160,0.40);background:rgba(109,213,160,0.08);}
.portais-nav-btn.oxy:hover{background:rgba(109,213,160,0.22);border-color:#6dd5a0;}
.portais-nav-btn.cir{color:#f5a623;border-color:rgba(245,166,35,0.40);background:rgba(245,166,35,0.08);}
.portais-nav-btn.cir:hover{background:rgba(245,166,35,0.22);border-color:#f5a623;}

/* Header-actions: botões CSV/Imprimir/Home no canto direito do header */
.header-actions{display:flex;align-items:center;gap:8px;flex-shrink:0;}
.header-action-btn{display:inline-flex;align-items:center;gap:6px;padding:6px 13px;
  border-radius:20px;background:rgba(255,255,255,0.10);border:1.5px solid rgba(255,255,255,0.20);
  color:#fff;font-size:12px;font-weight:600;cursor:pointer;text-decoration:none;font-family:inherit;
  transition:all 0.15s;}
.header-action-btn:hover{background:rgba(255,255,255,0.18);border-color:rgba(255,255,255,0.35);}
.header-action-btn.home{background:rgba(148,163,184,0.15);border-color:rgba(148,163,184,0.40);color:#cbd5e1;}
.header-action-btn.home:hover{background:rgba(148,163,184,0.28);}

/* Periodo-bloco: tabs de mês em card branco */
.periodo-bloco{display:flex;align-items:center;gap:10px;margin-bottom:22px;flex-wrap:wrap;
  background:#fff;padding:14px 18px;border-radius:12px;border:1px solid var(--borda);
  box-shadow:var(--sombra);}
.periodo-label-novo{font-size:10px;font-weight:700;color:var(--texto2);
  letter-spacing:0.4px;text-transform:uppercase;}
.f-grp{display:flex;align-items:center;gap:6px;flex-wrap:wrap;}
.tab-novo{padding:5px 12px;border-radius:20px;border:1.5px solid var(--borda);background:#fff;
  font-size:12px;font-weight:600;cursor:pointer;color:var(--texto2);transition:all 0.15s;
  font-family:inherit;}
.tab-novo.active{background:var(--navy);border-color:var(--navy);color:#fff;}
.tab-novo:hover:not(.active){border-color:var(--gold);color:var(--gold);}
.tabs-flex{display:flex;gap:6px;flex-wrap:wrap;}
.range-sep{width:1px;height:30px;background:var(--borda);}
.range-filter{display:flex;align-items:center;gap:8px;flex-wrap:wrap;}
.range-filter select{padding:4px 8px;border-radius:8px;border:1.5px solid var(--borda);
  background:#fff;font-size:12px;color:var(--texto-primario);font-weight:600;cursor:pointer;
  font-family:inherit;outline:none;transition:border 0.15s;}
.range-filter select:focus{border-color:var(--gold);}
.range-ate{font-size:12px;color:var(--texto2);}
.range-btn{padding:5px 11px;border-radius:20px;font-size:11px;font-weight:700;
  cursor:pointer;border:1.5px solid;transition:all 0.15s;font-family:inherit;}
.range-btn.apply{background:var(--gold);color:#fff;border-color:var(--gold);}
.range-btn.apply:hover{background:var(--navy);border-color:var(--navy);}
.range-btn.clear{background:#fff;color:var(--texto2);border-color:var(--borda);}
.range-btn.clear:hover{background:var(--cinza-cl);}

/* KPIs novos (kpi-row substitui metrics-grid) */
.kpi-row{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));
  gap:16px;margin-bottom:22px;}
.kpi{background:linear-gradient(180deg,var(--navy) 0%,#13315b 100%);border-radius:12px;
  padding:18px 56px 18px 20px;box-shadow:var(--sombra);
  border:1px solid var(--navy);border-left:4px solid var(--gold);position:relative;}
.kpi-ic{position:absolute;top:16px;right:16px;width:38px;height:38px;border-radius:50%;
  display:flex;align-items:center;justify-content:center;font-size:17px;
  background:rgba(255,255,255,0.16);}
.kpi.gold{border-left-color:var(--gold);}
.kpi.navy-med{border-left-color:var(--navy-med);}
.kpi.cinza{border-left-color:rgba(255,255,255,0.30);}
.kpi-label{font-size:11px;color:rgba(255,255,255,0.70);font-weight:700;letter-spacing:0.5px;
  text-transform:uppercase;margin-bottom:6px;}
.kpi-val{font-size:22px;font-weight:800;color:#fff;line-height:1.1;}
.kpi-foot{font-size:11px;color:rgba(255,255,255,0.85);margin-top:10px;
  font-weight:600;display:flex;align-items:center;gap:6px;flex-wrap:wrap;}
.delta-pos{color:#7CD992;font-weight:800;}
.delta-neg{color:#F19A8E;font-weight:800;}
.delta-flat{color:rgba(255,255,255,0.55);font-weight:700;}

/* Cores Particular / Plano alinhadas (gold escuro / navy médio) */
.origem-pill.particular{background:var(--gold-bg);color:var(--gold);border:1.5px solid var(--gold-borda);}
.origem-pill.plano{background:var(--navy-bg);color:var(--navy-med);border:1.5px solid var(--navy-borda);}
.tabela-tipo.part{background:var(--gold-bg);color:var(--gold);}
.tabela-tipo.plano{background:var(--navy-bg);color:var(--navy-med);}
.tabela-val{color:var(--gold);}

/* mobile-600 */
@media(max-width:600px){
  .header{padding:0 14px;flex-wrap:wrap;gap:8px;}
  .header > div{flex-wrap:wrap;}
  .portais-nav{padding:7px 14px;gap:6px;}
  .portais-nav-btn{padding:4px 10px;font-size:11px;}
  .metric-valor{font-size:21px;}
  .metric-card{padding:14px 16px;}
  .chart-wrap{height:220px;}
  .kpi-val{font-size:19px;}
  .kpi{padding:14px 42px 14px 14px;}
  .kpi-ic{width:30px;height:30px;top:12px;right:10px;font-size:14px;}
  .periodo-bloco{padding:12px 14px;gap:8px;}
  .tabs-flex{flex-wrap:wrap;}
  .header-actions{gap:6px;}
  .header-action-btn{padding:5px 10px;font-size:11px;}
  .two-col,.three-col{grid-template-columns:1fr;gap:14px;}
  .card{padding:14px 16px;}
}"""

SUBS.append(('CSS portais-nav block', OLD_PORTAIS_NAV, NEW_PORTAIS_NAV))

# 4-alt. Variação minimalista: 5 arquivos (Andrea, Eduardo, Gabriela, Jonathan, João)
# têm bloco portais-nav em <style> SEPARADO. Casa só se a sub principal falhou.
OLD_PORTAIS_NAV_ALT_RE = re.compile(
    r'<style>\s*\.portais-nav\{background:#162d50;border-bottom:1px solid rgba\(255,255,255,0\.10\);\s*'
    r'padding:8px 20px;[^}]+\}'
    r'.*?'
    r'\.portais-nav-btn\.prod:hover\{[^}]+\}\s*</style>',
    re.DOTALL
)
NEW_PORTAIS_NAV_ALT = '<style>' + NEW_PORTAIS_NAV + '</style>'
# Marcador para identificar arquivo da variante alt:
ALT_MARKER = '  .portais-nav{background:#162d50;border-bottom:1px solid rgba(255,255,255,0.10);\n    padding:8px 20px'

# 5. HTML: remover modo-medico-banner
SUBS.append(('remover modo-medico-banner',
"""    <div class="modo-medico-banner">
      <span style="font-size:18px">&#128101;</span>
      <div><strong>&#193;rea Restrita &#8212; Acesso Individual</strong>
      <span id="banner-nome" style="display:block;opacity:0.8;font-size:12px;"></span></div>
    </div>
    <div id='periodo-tabs' class='periodo-tabs'></div>""",
"""    <div class='periodo-bloco'>
      <div class='f-grp'>
        <span class='periodo-label-novo'>Mês:</span>
        <div id='periodo-tabs' class='tabs-flex'></div>
      </div>
      <div class='range-sep'></div>
      <div class='f-grp'>
        <span class='periodo-label-novo'>Intervalo:</span>
        <div class='range-filter'>
          <select id='range-de'></select>
          <span class='range-ate'>até</span>
          <select id='range-ate'></select>
          <button class='range-btn apply' onclick='aplicarRange()'>Aplicar</button>
          <button class='range-btn clear' onclick='limparRange()'>Limpar</button>
        </div>
      </div>
    </div>
    <div id='periodo-tabs-old' style='display:none'></div>"""))

# 6. Esconder empresa-filtro e periodo-bar (deixar IDs pra não quebrar refs JS)
SUBS.append(('esconder filtros antigos',
"""    <div id='empresa-filtro' class='empresa-filtro'></div>
    <div class='periodo-bar' id='periodo-label'></div>""",
"""    <div id='empresa-filtro' class='empresa-filtro' style='display:none'></div>
    <div class='periodo-bar' id='periodo-label' style='display:none'></div>"""))

# 7-8. metrics-grid → kpi-row
SUBS.append(('metrics-geral → kpi-row',
"""<div class='metrics-grid' id='metrics-geral'></div>""",
"""<div class='kpi-row' id='metrics-geral'></div>"""))

SUBS.append(('metrics-prof → kpi-row',
"""<div class='metrics-grid' id='metrics-prof'></div>""",
"""<div class='kpi-row' id='metrics-prof'></div>"""))

# 9. JS paleta CORES
SUBS.append(('JS paleta CORES',
"""const CORES=['#2E6DA4','#E07B28','#2D7A3C','#8E44AD','#C0392B','#16A085','#D35400','#2980B9','#27AE60','#F39C12','#1ABC9C','#E74C3C'];
const COR_PARTICULAR='#2D7A3C';
const COR_PLANO='#2E6DA4';""",
"""// Paleta dos gráficos: mesma do Recebimento Endo (gold escuro + navy médio)
const CORES=['#A18960','#23476f','#c7ad82','#3a5e80','#7c6948','#1a3654','#d4bd8e','#4a6e95','#9c8458','#2d4f70','#bda079','#5a7da3'];
const COR_PARTICULAR='#A18960';
const COR_PLANO='#23476f';"""))

# 10. JS renderGeral — adicionar helpers ANTES, mas só uma vez. Marca por presença de _getPeriodoAnterior.
# 10. JS renderGeral — duas variantes (Object.entries vs Object.values)
SUBS.append(('JS helpers + renderGeral (v.entries)',
"""function renderGeral(){
  const todos=Object.entries(DADOS_PROFS).map(([k,v])=>({...v,_key:k}));
  if(!todos.length)return;
  const soma=(key)=>todos.reduce((a,d)=>a+(d.resumo?.[key]||0),0);
  const totalRec=soma('Valor recebido'),totalLiq=soma('Valor Líquido');
  const totalRep=soma('Repasse Profissional (R$)'),totalCli=soma('Repasse Clínica (R$)');

  document.getElementById('header-periodo').textContent=PERIODO_LABEL;
  document.getElementById('periodo-label').textContent='Período: '+PERIODO_LABEL;""",
"""// ── Helpers de comparação com período anterior (padrão Recebimento Endo) ──
function _getPeriodoAnterior(pid){
  if(!pid || !TODOS_PERIODOS) return null;
  const todos = Object.keys(TODOS_PERIODOS).sort();
  const idx = todos.indexOf(pid);
  return idx > 0 ? todos[idx-1] : null;
}
function _delta(atual, anterior, isInteger){
  if(anterior === null || anterior === undefined) return '<span class="delta-flat">—</span>';
  if(!atual && !anterior) return '<span class="delta-flat">—</span>';
  const diff = (atual||0) - (anterior||0);
  if(Math.abs(diff) < 0.01 && !isInteger) return '<span class="delta-flat">→ estável</span>';
  if(isInteger && diff === 0) return '<span class="delta-flat">→ estável</span>';
  const pct = anterior ? Math.abs(diff/anterior)*100 : 0;
  const sinal = diff > 0 ? '↑' : '↓';
  const cls = diff > 0 ? 'delta-pos' : 'delta-neg';
  const valFmt = isInteger ? Math.abs(diff).toFixed(0) : fmtBRL(Math.abs(diff)).replace('R$ ','R$');
  return '<span class="'+cls+'">'+sinal+' '+valFmt+(pct>0?' ('+pct.toFixed(1)+'%)':'')+'</span>';
}

function renderGeral(){
  const todos=Object.entries(DADOS_PROFS).map(([k,v])=>({...v,_key:k}));
  if(!todos.length)return;
  const soma=(key)=>todos.reduce((a,d)=>a+(d.resumo?.[key]||0),0);
  const totalRec=soma('Valor recebido'),totalLiq=soma('Valor Líquido');
  const totalRep=soma('Repasse Profissional (R$)'),totalCli=soma('Repasse Clínica (R$)');

  document.getElementById('header-periodo').textContent=PERIODO_LABEL;
  const pl=document.getElementById('periodo-label'); if(pl) pl.textContent='Período: '+PERIODO_LABEL;"""))

# Variante: Christiane usa Object.values em vez de entries
SUBS.append(('JS helpers + renderGeral (v.values)',
"""function renderGeral(){
  const todos=Object.values(DADOS_PROFS);
  if(!todos.length)return;
  const soma=(key)=>todos.reduce((a,d)=>a+(d.resumo?.[key]||0),0);
  const totalRec=soma('Valor recebido'),totalLiq=soma('Valor Líquido');
  const totalRep=soma('Repasse Profissional (R$)'),totalCli=soma('Repasse Clínica (R$)');

  document.getElementById('header-periodo').textContent=PERIODO_LABEL;
  document.getElementById('periodo-label').textContent='Período: '+PERIODO_LABEL;""",
"""// ── Helpers de comparação com período anterior (padrão Recebimento Endo) ──
function _getPeriodoAnterior(pid){
  if(!pid || !TODOS_PERIODOS) return null;
  const todos = Object.keys(TODOS_PERIODOS).sort();
  const idx = todos.indexOf(pid);
  return idx > 0 ? todos[idx-1] : null;
}
function _delta(atual, anterior, isInteger){
  if(anterior === null || anterior === undefined) return '<span class="delta-flat">—</span>';
  if(!atual && !anterior) return '<span class="delta-flat">—</span>';
  const diff = (atual||0) - (anterior||0);
  if(Math.abs(diff) < 0.01 && !isInteger) return '<span class="delta-flat">→ estável</span>';
  if(isInteger && diff === 0) return '<span class="delta-flat">→ estável</span>';
  const pct = anterior ? Math.abs(diff/anterior)*100 : 0;
  const sinal = diff > 0 ? '↑' : '↓';
  const cls = diff > 0 ? 'delta-pos' : 'delta-neg';
  const valFmt = isInteger ? Math.abs(diff).toFixed(0) : fmtBRL(Math.abs(diff)).replace('R$ ','R$');
  return '<span class="'+cls+'">'+sinal+' '+valFmt+(pct>0?' ('+pct.toFixed(1)+'%)':'')+'</span>';
}

function renderGeral(){
  const todos=Object.values(DADOS_PROFS);
  if(!todos.length)return;
  const soma=(key)=>todos.reduce((a,d)=>a+(d.resumo?.[key]||0),0);
  const totalRec=soma('Valor recebido'),totalLiq=soma('Valor Líquido');
  const totalRep=soma('Repasse Profissional (R$)'),totalCli=soma('Repasse Clínica (R$)');

  document.getElementById('header-periodo').textContent=PERIODO_LABEL;
  const pl=document.getElementById('periodo-label'); if(pl) pl.textContent='Período: '+PERIODO_LABEL;"""))

# 11. JS mostrarProf — substitui o bloco de KPIs metric-card pelos novos kpi com delta
OLD_METRICS_PROF = """  document.getElementById('metrics-prof').innerHTML=
    '<div class="metric-card azul"><div class="metric-label">Valor Recebido</div><div class="metric-valor">'+fmtBRL(r['Valor recebido'])+'</div><div class="metric-sub">Bruto compensado</div></div>'+
    '<div class="metric-card cinza"><div class="metric-label">Valor L&iacute;quido</div><div class="metric-valor">'+fmtBRL(liq)+'</div><div class="metric-sub">Ap&oacute;s impostos e taxas</div></div>'+
    '<div class="metric-card verde"><div class="metric-label">Repasse do M&ecirc;s</div><div class="metric-valor">'+fmtBRL(rep)+'</div><div class="metric-sub">'+fmtPct(liq>0?rep/liq:0)+' do valor l&iacute;quido</div></div>'+
    '<div class="metric-card laranja"><div class="metric-label">Atendimentos</div><div class="metric-valor">'+(d.atendimentos||[]).length+'</div><div class="metric-sub">Procedimentos no per&iacute;odo</div></div>';"""

NEW_METRICS_PROF = """  // Delta vs período anterior para o mesmo profissional
  const prevPid = _getPeriodoAnterior(PERIODO_ATUAL);
  const prevProf = prevPid ? ((TODOS_PERIODOS[prevPid]||{}).profs||{})[id] : null;
  const prevResumo = prevProf?.resumo || {};
  const dRecP = _delta(r['Valor recebido'], prevResumo['Valor recebido']);
  const dLiqP = _delta(liq, prevResumo['Valor Líquido']);
  const dRepP = _delta(rep, prevResumo['Repasse Profissional (R$)']);
  const dAtP  = _delta((d.atendimentos||[]).length, (prevProf?.atendimentos||[]).length, true);

  document.getElementById('metrics-prof').innerHTML=
    '<div class="kpi gold"><div class="kpi-ic">💰</div><div class="kpi-label">Valor Recebido</div><div class="kpi-val">'+fmtBRL(r['Valor recebido'])+'</div><div class="kpi-foot">'+dRecP+'<span style="opacity:0.6">Bruto compensado</span></div></div>'+
    '<div class="kpi cinza"><div class="kpi-ic">🧮</div><div class="kpi-label">Valor L&iacute;quido</div><div class="kpi-val">'+fmtBRL(liq)+'</div><div class="kpi-foot">'+dLiqP+'<span style="opacity:0.6">Após impostos e taxas</span></div></div>'+
    '<div class="kpi gold"><div class="kpi-ic">💸</div><div class="kpi-label">Repasse do M&ecirc;s</div><div class="kpi-val">'+fmtBRL(rep)+'</div><div class="kpi-foot">'+dRepP+'<span style="opacity:0.6">'+fmtPct(liq>0?rep/liq:0)+' do líquido</span></div></div>'+
    '<div class="kpi navy-med"><div class="kpi-ic">📋</div><div class="kpi-label">Atendimentos</div><div class="kpi-val">'+(d.atendimentos||[]).length+'</div><div class="kpi-foot">'+dAtP+'<span style="opacity:0.6">Procedimentos no período</span></div></div>';"""

SUBS.append(('JS mostrarProf KPIs', OLD_METRICS_PROF, NEW_METRICS_PROF))

# 12. JS inicializarPortalPermanente — adiciona popular range + RANGE_ATIVO + funções
OLD_INIT = """function inicializarPortalPermanente(){
  const periodos = Object.keys(TODOS_PERIODOS).sort(); // crescente cronológico
  if(!periodos.length) return;
  PERIODO_ATUAL = periodos[periodos.length-1]; // mais recente

  // Monta abas de período (só exibe se >1)
  const tabsEl = document.getElementById('periodo-tabs');
  if(tabsEl && periodos.length > 1){
    tabsEl.style.display = 'flex';
    tabsEl.innerHTML = periodos.slice().reverse().map(pid => {
      const lbl = TODOS_PERIODOS[pid].label;
      return '<button class="periodo-tab'+(pid===PERIODO_ATUAL?' active':'')+
             '" onclick="mudarPeriodo(\\''+pid+'\\')">'+ lbl +'</button>';
    }).join('');
  }

  mudarPeriodo(PERIODO_ATUAL, false);
}"""

NEW_INIT = """// Range de período (agregação multi-mês). Quando RANGE_ATIVO != null, mostrarProf agrega.
let RANGE_ATIVO = null; // {de: 'YYYY-MM', ate: 'YYYY-MM'} ou null

function inicializarPortalPermanente(){
  const periodos = Object.keys(TODOS_PERIODOS).sort();
  if(!periodos.length) return;
  PERIODO_ATUAL = periodos[periodos.length-1];

  const tabsEl = document.getElementById('periodo-tabs');
  if(tabsEl){
    tabsEl.style.display = 'flex';
    tabsEl.innerHTML = periodos.slice().reverse().map(pid => {
      const lbl = TODOS_PERIODOS[pid].label;
      return '<button class="tab-novo'+(pid===PERIODO_ATUAL?' active':'')+
             '" data-pid="'+pid+'" onclick="mudarPeriodo(\\''+pid+'\\')">'+ lbl +'</button>';
    }).join('');
  }

  // Popular range-de / range-ate
  const opts = periodos.map(pid => '<option value="'+pid+'">'+TODOS_PERIODOS[pid].label+'</option>').join('');
  const rde = document.getElementById('range-de');
  const rate = document.getElementById('range-ate');
  if(rde) { rde.innerHTML = opts; rde.value = periodos[0]; }
  if(rate){ rate.innerHTML = opts; rate.value = periodos[periodos.length-1]; }

  mudarPeriodo(PERIODO_ATUAL, false);
}

function aplicarRange(){
  const de = document.getElementById('range-de').value;
  const ate = document.getElementById('range-ate').value;
  if(!de || !ate) return;
  if(de > ate){ alert('O mês "de" deve ser anterior ou igual ao mês "até".'); return; }
  RANGE_ATIVO = {de, ate};
  PERIODO_ATUAL = ate;
  document.querySelectorAll('#periodo-tabs .tab-novo').forEach(t => t.classList.remove('active'));
  _renderRange();
}

function limparRange(){
  RANGE_ATIVO = null;
  const periodos = Object.keys(TODOS_PERIODOS).sort();
  const rde = document.getElementById('range-de');
  const rate = document.getElementById('range-ate');
  if(rde)  rde.value = periodos[0];
  if(rate) rate.value = periodos[periodos.length-1];
  mudarPeriodo(PERIODO_ATUAL, true);
}

function _renderRange(){
  if(!RANGE_ATIVO) return;
  const periodos = Object.keys(TODOS_PERIODOS).sort()
    .filter(pid => pid >= RANGE_ATIVO.de && pid <= RANGE_ATIVO.ate);
  if(!periodos.length) return;
  const fixo = (typeof PROF_FIXO !== 'undefined' && PROF_FIXO) ? PROF_FIXO : null;
  if(!fixo) { renderGeral(); return; }

  const agg = {profissional:'', empresa:'', mes:'', ano:'', periodo_id:'',
    resumo:{}, por_categoria:[], por_pagamento:[], por_tabela:[], atendimentos:[]};
  const cat = {}, pag = {}, tab = {};
  for(const pid of periodos){
    const p = ((TODOS_PERIODOS[pid]||{}).profs||{})[fixo];
    if(!p) continue;
    if(!agg.profissional){ agg.profissional = p.profissional; agg.empresa = p.empresa; }
    Object.entries(p.resumo||{}).forEach(([k,v])=>{
      if(typeof v === 'number') agg.resumo[k] = (agg.resumo[k]||0) + v;
      else if(!agg.resumo[k]) agg.resumo[k] = v;
    });
    (p.por_categoria||[]).forEach(c => {
      const key = c.Categoria || '—';
      cat[key] = cat[key] || {Categoria: key, 'Valor recebido': 0};
      cat[key]['Valor recebido'] += (c['Valor recebido']||0);
    });
    (p.por_pagamento||[]).forEach(c => {
      const key = c['Tipo de pagamento'] || 'Outros';
      pag[key] = pag[key] || {'Tipo de pagamento': key, 'Valor recebido': 0};
      pag[key]['Valor recebido'] += (c['Valor recebido']||0);
    });
    (p.por_tabela||[]).forEach(c => {
      const key = c.Tabela || '—';
      tab[key] = tab[key] || {Tabela: key, Origem: c.Origem, 'Valor recebido': 0};
      tab[key]['Valor recebido'] += (c['Valor recebido']||0);
    });
    (p.atendimentos||[]).forEach(a => agg.atendimentos.push(a));
  }
  agg.por_categoria = Object.values(cat);
  agg.por_pagamento = Object.values(pag);
  agg.por_tabela    = Object.values(tab);

  const lDe  = (TODOS_PERIODOS[periodos[0]]||{}).label || periodos[0];
  const lAte = (TODOS_PERIODOS[periodos[periodos.length-1]]||{}).label || periodos[periodos.length-1];
  PERIODO_LABEL = (periodos.length === 1) ? lDe : (lDe + ' → ' + lAte);
  const hp = document.getElementById('header-periodo'); if(hp) hp.textContent = PERIODO_LABEL;

  DADOS_PROFS[fixo] = agg;
  Object.keys(CHARTS).forEach(k => { if(CHARTS[k]){ CHARTS[k].destroy(); delete CHARTS[k]; }});
  mostrarProf(fixo);
}"""

SUBS.append(('JS inicializarPortalPermanente + range', OLD_INIT, NEW_INIT))

# 13. JS mudarPeriodo — adicionar RANGE_ATIVO=null + ajustar seletor
SUBS.append(('JS mudarPeriodo reset range',
"""function mudarPeriodo(id, updateTabs){
  PERIODO_ATUAL = id;
  const pdata = TODOS_PERIODOS[id];
  if(!pdata) return;

  // Atualiza DADOS_PROFS com dados do período selecionado
  Object.keys(DADOS_PROFS).forEach(k => delete DADOS_PROFS[k]);
  Object.assign(DADOS_PROFS, pdata.profs);""",
"""function mudarPeriodo(id, updateTabs){
  PERIODO_ATUAL = id;
  RANGE_ATIVO = null; // qualquer clique em tab cancela o range
  const pdata = TODOS_PERIODOS[id];
  if(!pdata) return;

  // Atualiza DADOS_PROFS com dados do período selecionado
  Object.keys(DADOS_PROFS).forEach(k => delete DADOS_PROFS[k]);
  Object.assign(DADOS_PROFS, pdata.profs);"""))

# 14. JS mudarPeriodo querySelector
SUBS.append(('JS mudarPeriodo tab seletor',
"""    document.querySelectorAll('.periodo-tab').forEach(t => {
      t.classList.toggle('active', t.textContent === pdata.label);
    });""",
"""    document.querySelectorAll('#periodo-tabs .tab-novo').forEach(t => {
      t.classList.toggle('active', t.dataset.pid === id);
    });"""))

# REGEX (parts dinâmicas): header inline com botão Home (link Hub específico por médico)
# O link 'hub/<Nome>_Hub.html' varia. Vou usar regex.
HEADER_OLD_RE = re.compile(
    r"<div style='display:flex;align-items:center;gap:12px;'><a href='(hub/[^']+\.html)' style='display:inline-flex[^']+'[^>]*>🏠 Home</a><span id='header-periodo' style='font-size:13px;opacity:0\.85;'></span><span class='header-badge'>[^<]+</span></div>"
)
HEADER_NEW_TPL = """<div class='header-actions'>
    <a href='{hub}' class='header-action-btn home'>🏠 Home</a>
    <button class='header-action-btn' onclick='exportarCSVProf()' title='Exportar CSV do período'>⬇ CSV</button>
    <button class='header-action-btn' onclick='window.print()' title='Imprimir página'>🖨️ Imprimir</button>
    <span id='header-periodo' style='font-size:13px;opacity:0.85;margin-left:6px;'></span>
  </div>"""

def aplicar(arq):
    with open(arq, 'r', encoding='utf-8') as f:
        original = f.read()
    novo = original
    aplicados = []
    nao_aplicados = []
    for desc, old, new in SUBS:
        if old in novo:
            novo = novo.replace(old, new)
            aplicados.append(desc)
        else:
            nao_aplicados.append(desc)

    # Regex header
    m = HEADER_OLD_RE.search(novo)
    if m:
        hub_link = m.group(1)
        novo = HEADER_OLD_RE.sub(HEADER_NEW_TPL.format(hub=hub_link), novo)
        aplicados.append('header inline → header-actions')
    else:
        nao_aplicados.append('header inline → header-actions (regex)')

    # Variante alt: CSS portais-nav em <style> separado (Andrea, Eduardo, Gabriela, Jonathan, João)
    if ALT_MARKER in novo:
        m2 = OLD_PORTAIS_NAV_ALT_RE.search(novo)
        if m2:
            # NEW_PORTAIS_NAV_ALT já não tem o <style> que envolve (queremos substituir tudo)
            novo = OLD_PORTAIS_NAV_ALT_RE.sub(lambda _: '<style>' + NEW_PORTAIS_NAV + '</style>', novo)
            aplicados.append('CSS portais-nav alt (style separado)')
            # Remove o "NAO APLICADO: CSS portais-nav block" se estava lá
            nao_aplicados = [n for n in nao_aplicados if n != 'CSS portais-nav block']

    if novo == original:
        return aplicados, nao_aplicados, False
    if not DRY:
        with open(arq, 'w', encoding='utf-8', newline='') as f:
            f.write(novo)
    return aplicados, nao_aplicados, True

print('='*80)
print('Propagacao visual nos portais Endo individuais')
print('Modo:', 'DRY-RUN' if DRY else 'APLICANDO')
print('='*80)
total_alt = 0
total_ok = 0
total_skip = 0
for arq in ARQUIVOS:
    if not os.path.exists(arq):
        print(f'  [PULAR] {arq} nao existe')
        continue
    aplicados, nao_aplicados, alterou = aplicar(arq)
    status = 'OK' if alterou else 'SEM MUDANCA'
    print(f'\n[{status}] {arq}')
    print(f'  Aplicados: {len(aplicados)}/{len(SUBS)+1}')
    if nao_aplicados:
        for d in nao_aplicados:
            print(f'    ! NAO APLICADO: {d}')
    if alterou: total_alt += 1
    if len(nao_aplicados) == 0: total_ok += 1
    else: total_skip += 1

print(f'\n{"="*80}')
print(f'Total: {total_alt} arquivos alterados, {total_ok} 100% aplicados, {total_skip} parcial')
