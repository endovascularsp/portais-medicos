# -*- coding: utf-8 -*-
"""
_propagar_menu_mes_produtividade.py — troca as abas de mês por menu suspenso nos
portais de Produtividade (admin Gestor, admin Oxy e os individuais).

Só o filtro de MÊS. Categoria e Tabela de preço NÃO entram aqui: os dados de
Produtividade não têm esses campos — cada atendimento traz apenas paciente,
data, procedimentos, pagamento, parcelas e valor. Colocar os filtros sem o dado
por trás só criaria menus vazios.

O piloto foi feito à mão em produtividade/index.html; este script leva o mesmo
para os demais, com âncora exata e ocorrência única. Se qualquer âncora falhar,
o arquivo é pulado inteiro.

Uso:
    python _tools/_propagar_menu_mes_produtividade.py --dry-run
    python _tools/_propagar_menu_mes_produtividade.py
"""
from __future__ import annotations
import argparse
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PASTAS = ["produtividade", "oxy-produtividade"]
MARCA = "periodo-select"   # presente => já propagado

def montagem(rotulo: str):
    """O bloco que monta as abas. Os admins resolvem o nome do mês com
    labelOf(pid); os portais individuais usam info.periodos[pid].label."""
    de = f"""  const tabs = document.getElementById('periodo-tabs');
  tabs.innerHTML = '';
  pids.forEach((pid,i)=>{{
    const t = document.createElement('button');
    t.className = 'tab' + (i===pids.length-1?' active':'');
    t.textContent = {rotulo};
    t.dataset.pid = pid;
    t.onclick = ()=>selecionarMes(pid);
    tabs.appendChild(t);
  }});"""
    para = f"""  // Menu suspenso de mês (antes eram botões lado a lado, que estouravam a linha
  // conforme os meses se acumulavam). Mais recente no topo.
  const selPer = document.getElementById('periodo-select');
  if(selPer){{
    selPer.innerHTML = pids.slice().reverse()
      .map(pid=>'<option value="'+pid+'">'+{rotulo}+'</option>').join('');
    selPer.value = pids[pids.length-1];
  }}"""
    return de, para


# Variantes aceitas para a montagem das abas — a primeira que casar é usada.
MONTAGENS = [montagem("labelOf(pid)"), montagem("info.periodos[pid].label")]

TROCAS = [
    # 1. markup: div das abas -> menu suspenso
    ("<div class='periodo-tabs' id='periodo-tabs'></div>",
     "<select id='periodo-select' class='prof-select' onchange='selecionarMes(this.value)'></select>"),

    # 3. selecionarMes: marcar aba -> selecionar no menu
    ("""  filtroAtual = {tipo:'mes', pid};
  document.querySelectorAll('.tab').forEach(t=>{
    t.classList.toggle('active', t.dataset.pid===pid);
    t.classList.remove('desativa');
  });
  render();""",
     """  filtroAtual = {tipo:'mes', pid};
  const selPer = document.getElementById('periodo-select');
  if(selPer && selPer.value !== pid) selPer.value = pid;
  render();"""),

    # 4. aplicarRange: desativar abas -> refletir o mês final no menu
    ("""  filtroAtual = {tipo:'range', pids:selPids};
  document.querySelectorAll('.tab').forEach(t=>{
    t.classList.remove('active');
    t.classList.add('desativa');
  });
  render();""",
     """  filtroAtual = {tipo:'range', pids:selPids};
  const selPer = document.getElementById('periodo-select');
  if(selPer) selPer.value = ate;
  render();"""),
]


def main(dry_run: bool):
    alvos = sorted(p for pasta in PASTAS for p in (REPO / pasta).glob("*.html"))
    print(f"{len(alvos)} arquivos de Produtividade\n")
    feitos = pulados = ja = 0
    for alvo in alvos:
        rel = alvo.relative_to(REPO)
        html = alvo.read_text(encoding="utf-8")
        if MARCA in html:
            print(f"  [JÁ FEITO]  {rel}")
            ja += 1
            continue
        montagens_ok = [m for m in MONTAGENS if html.count(m[0]) == 1]
        ruins = [(i, html.count(de)) for i, (de, _) in enumerate(TROCAS, 1) if html.count(de) != 1]
        if len(montagens_ok) != 1:
            ruins.append(("montagem das abas", len(montagens_ok)))
        if ruins:
            print(f"  [PULADO]    {rel}  ->  âncoras fora do padrão: "
                  + ", ".join(f"{i} ({n}x)" for i, n in ruins))
            pulados += 1
            continue
        novo = html
        for de, para in TROCAS + montagens_ok:
            novo = novo.replace(de, para, 1)
        print(f"  [OK]        {rel}")
        feitos += 1
        if not dry_run:
            alvo.write_text(novo, encoding="utf-8")

    print(f"\n  alterados: {feitos} · já feitos: {ja} · pulados: {pulados}")
    if dry_run:
        print("  [dry-run] nada gravado.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    main(ap.parse_args().dry_run)
