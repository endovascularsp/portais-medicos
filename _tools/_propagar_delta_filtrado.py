# -*- coding: utf-8 -*-
r"""
_propagar_delta_filtrado.py — faz a comparação com o mês anterior respeitar os
filtros da tela, nos 3 dashboards e nos 35 portais de Recebimento.

O defeito (achado pelo Thiago em 18/08/2026): os gráficos acompanhavam os
filtros, mas o "delta" dos KPIs não. `prevSoma` filtrava só por empresa — então,
com "Simone Matsuda + Produtos" na tela, o card comparava os R$ 767,92 dela
contra os R$ 320.934,74 de TODOS no mês anterior, e mostrava "↓ 99,8%". Uma
queda que nunca existiu.

O princípio do conserto é um só: **o mês anterior passa pelos mesmos filtros do
mês atual**. Comparação entre recortes diferentes não é comparação.

Dois formatos, porque o código é diferente:
  · dashboards  -> já existe `_filtrarProfs`; basta passar o mês anterior por ele
  · portais     -> não existe; entra uma função pequena que filtra os
                   atendimentos do mês anterior pelos mesmos critérios

No modo intervalo a comparação é suprimida ("—"): o total atual cobre vários
meses e o anterior seria um só. Melhor não comparar do que comparar errado.

A Produtividade NÃO entra: ela já faz certo — compara o mesmo profissional
contra ele mesmo (`profAgg`) sobre a base já filtrada.

Uso:
    python _tools/_propagar_delta_filtrado.py            # simula
    python _tools/_propagar_delta_filtrado.py --escrever
"""
from __future__ import annotations
import argparse
import io
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
REPO = Path(__file__).resolve().parent.parent

# ── dashboards: visão geral ──────────────────────────────────────────────────
# Duas variantes: o admin da Endo filtra por empresa fixa; os de Oxy e Cirurgias
# aceitam FILTRO_EMPRESA==='todos'. A substituição é a mesma nos dois, porque
# quem passa a filtrar é o `_filtrarProfs`, que já entende as duas.
ADMIN_GERAL_DE_VARIANTES = [
  """  const prevSoma = (key) => {
    if(!prev) return null;
    const profsPrev = (TODOS_PERIODOS[prev]||{}).profs||{};
    return Object.values(profsPrev)
      .filter(p=>(p.empresa||'Endovascular SP')===FILTRO_EMPRESA)
      .reduce((a,d)=>a+(d.resumo?.[key]||0),0);
  };""",
  """  const prevSoma = (key) => {
    if(!prev) return null;
    const profsPrev = (TODOS_PERIODOS[prev]||{}).profs||{};
    return Object.values(profsPrev)
      .filter(p=> FILTRO_EMPRESA==='todos' || (p.empresa||'Endovascular SP')===FILTRO_EMPRESA)
      .reduce((a,d)=>a+(d.resumo?.[key]||0),0);
  };""",
]
ADMIN_GERAL_DE = ADMIN_GERAL_DE_VARIANTES[0]
ADMIN_GERAL_PARA = """  // O mês anterior passa pelos MESMOS filtros do mês atual. Antes só a empresa
  // era aplicada: filtrando "Simone Matsuda + Produtos", o card comparava os
  // R$ 767,92 dela contra o total de TODOS no mês anterior, e cuspia
  // "↓ 99,8%". Comparação entre coisas diferentes não é comparação.
  //
  // No modo intervalo não há comparação possível: o total atual cobre vários
  // meses e o anterior seria um só. Melhor mostrar "—" do que um número errado.
  const baseAnterior = (!prev || RANGE_ATIVO)
    ? null
    : _soDoProfFiltrado(_filtrarProfs((TODOS_PERIODOS[prev]||{}).profs || {}));
  const prevSoma = (key) => {
    if(!baseAnterior) return null;
    return Object.values(baseAnterior)
      .reduce((a,d)=>a+(d.resumo?.[key]||0),0);
  };"""

# ── dashboards: página individual ────────────────────────────────────────────
# O admin de Cirurgias não tem a linha de comentário; o resto é idêntico.
ADMIN_IND_DE_VARIANTES = [
  """  // Delta vs período anterior para o mesmo profissional
  const prevPid = _getPeriodoAnterior(PERIODO_ATUAL);
  const prevProf = prevPid ? ((TODOS_PERIODOS[prevPid]||{}).profs||{})[id] : null;""",
  """  const prevPid = _getPeriodoAnterior(PERIODO_ATUAL);
  const prevProf = prevPid ? ((TODOS_PERIODOS[prevPid]||{}).profs||{})[id] : null;""",
]
ADMIN_IND_DE = ADMIN_IND_DE_VARIANTES[0]
ADMIN_IND_PARA = """  // Delta vs período anterior para o mesmo profissional — pelo mesmo recorte.
  // Sem passar o mês anterior pelo filtro, comparar "Produtos" deste mês contra
  // o MÊS INTEIRO do anterior dava queda onde não houve queda.
  const prevPid = _getPeriodoAnterior(PERIODO_ATUAL);
  const prevProf = prevPid
    ? (_filtrarProfs((TODOS_PERIODOS[prevPid]||{}).profs || {})[id] || null)
    : null;"""

# ── portais individuais ──────────────────────────────────────────────────────
PORTAL_DE_VARIANTES = ADMIN_IND_DE_VARIANTES
PORTAL_DE = ADMIN_IND_DE
PORTAL_PARA = """  // Delta vs período anterior — pelo MESMO recorte de categoria/tabela.
  // Comparar "Produtos" deste mês contra o mês inteiro do anterior mostrava
  // queda onde não houve queda.
  const prevPid = _getPeriodoAnterior(PERIODO_ATUAL);
  const prevProf = prevPid ? _profAnteriorFiltrado(prevPid, id) : null;"""

PORTAL_FN_DE = """function filtrarPorCategoria(v){ FILTRO_CATEGORIA = v || ''; _reaplicarInd(); }"""
PORTAL_FN_PARA = """// O mês anterior tem de ser lido pelo mesmo filtro do mês atual, senão a
// comparação é entre recortes diferentes. Devolve o profissional recalculado só
// com os atendimentos que passam pelo filtro; se ele não existia no mês
// anterior, devolve null e o card mostra "—".
function _profAnteriorFiltrado(pid, id){
  const p = ((TODOS_PERIODOS[pid]||{}).profs||{})[id];
  if(!p) return null;
  if(!FILTRO_CATEGORIA && !FILTRO_TABELA) return p;
  const ats = (p.atendimentos||[]).filter(a =>
    (!FILTRO_CATEGORIA || a.Categoria === FILTRO_CATEGORIA) &&
    (!FILTRO_TABELA    || a.Tabela    === FILTRO_TABELA));
  return _recalcularProf(p, ats);
}

function filtrarPorCategoria(v){ FILTRO_CATEGORIA = v || ''; _reaplicarInd(); }"""


def alvos():
    admins = [REPO / "recebimento.html", REPO / "oxy" / "index.html",
              REPO / "cirurgias" / "index.html"]
    portais = [f for f in sorted(REPO.glob("*.html"))
               if f.name not in ("index.html", "recebimento.html")]
    for sub in ("oxy", "cirurgias"):
        portais += [f for f in sorted((REPO / sub).glob("*.html"))
                    if f.name != "index.html"]
    return admins, portais


def aplicar(caminho: Path, trocas, escrever: bool) -> str:
    txt = caminho.read_text(encoding="utf-8")
    novo = txt
    feitas = []
    for nome, de, para in trocas:
        n = novo.count(de)
        if n == 0 and para.split("\n")[0].strip() in novo:
            feitas.append(f"{nome}=já")
            continue
        if n != 1:
            return f"ABORTA em '{nome}': âncora {n}x"
        novo = novo.replace(de, para, 1)
        feitas.append(nome)
    if novo == txt:
        return "nada a fazer"
    if escrever:
        caminho.write_text(novo, encoding="utf-8")
    return ("ok: " if escrever else "faria: ") + ", ".join(feitas)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--escrever", action="store_true")
    a = ap.parse_args()
    admins, portais = alvos()
    problemas = 0

    print("=== DASHBOARDS ===")
    for f in admins:
        if not f.exists():
            continue
        txt = f.read_text(encoding="utf-8")
        de = next((v for v in ADMIN_GERAL_DE_VARIANTES if v in txt), ADMIN_GERAL_DE)
        di = next((v for v in ADMIN_IND_DE_VARIANTES if v in txt), ADMIN_IND_DE)
        r = aplicar(f, [("geral", de, ADMIN_GERAL_PARA),
                        ("individual", di, ADMIN_IND_PARA)], a.escrever)
        if r.startswith("ABORTA"):
            problemas += 1
        print(f"  {str(f.relative_to(REPO)).replace(chr(92),'/'):24} {r}")

    print(f"\n=== PORTAIS DE MÉDICO ({len(portais)}) ===")
    contagem = {}
    for f in portais:
        tx = f.read_text(encoding="utf-8")
        dp = next((v for v in PORTAL_DE_VARIANTES if v in tx), PORTAL_DE)
        r = aplicar(f, [("função", PORTAL_FN_DE, PORTAL_FN_PARA),
                        ("delta", dp, PORTAL_PARA)], a.escrever)
        contagem[r] = contagem.get(r, 0) + 1
        if r.startswith("ABORTA"):
            problemas += 1
            print(f"  {str(f.relative_to(REPO)).replace(chr(92),'/'):46} {r}")
    for r, n in sorted(contagem.items(), key=lambda kv: -kv[1]):
        print(f"  {n:3} arquivo(s): {r}")

    if not a.escrever:
        print("\n[simulação] nada gravado. Rode com --escrever.")
    print(f"problemas: {problemas}")
    return 1 if problemas else 0


if __name__ == "__main__":
    sys.exit(main())
