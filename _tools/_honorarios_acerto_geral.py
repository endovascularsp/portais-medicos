# -*- coding: utf-8 -*-
"""
_honorarios_acerto_geral.py — o documento de acerto do time inteiro, para levar
impresso à reunião.

Diferente do `_honorarios_acerto.py`, que abre linha a linha para UM
profissional, este é a visão de conjunto: quanto foi pago, quanto era o correto,
e o líquido a acertar por pessoa.

A regra que ele impõe é apresentar o LÍQUIDO dos períodos juntos, nunca um mês
isolado. Em Junho e Julho de 2026, olhar só Junho mostraria o Dr. Igor com
R$ 12,7 mil a menos — quando na verdade ele tem R$ 22,7 mil a mais, porque o
pagamento cancelado em Junho voltou em Julho por um valor maior.

O "antes" sai do PDATA publicado num commit anterior do próprio repositório:
qualquer número do documento pode ser reconferido lá.

Uso:
    python _tools/_honorarios_acerto_geral.py --antes 79b7984 --periodos 2026-06,2026-07
"""
from __future__ import annotations
import argparse
import html
import io
import json
import re
import subprocess
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SAIDA = Path.home() / "Downloads"


def pdata(commit: str | None) -> dict:
    if commit:
        txt = subprocess.run(["git", "show", f"{commit}:recebimento.html"],
                             capture_output=True, cwd=REPO).stdout.decode("utf-8")
    else:
        txt = (REPO / "recebimento.html").read_text(encoding="utf-8")
    m = re.search(r"const TODOS_PERIODOS\s*=\s*/\*PDATA\*/(\{.*?\});", txt, re.S)
    if not m:
        raise SystemExit(f"ABORTADO: não achei o PDATA em {commit or 'recebimento.html'}")
    return json.loads(m.group(1))


def por_prof(D: dict, pid: str) -> dict:
    out = defaultdict(float)
    for _, v in (D.get(pid, {}).get("profs") or {}).items():
        out[v["profissional"]] += v["resumo"].get("Repasse Profissional (R$)", 0)
    return out


def brl(v) -> str:
    s = f"{abs(float(v or 0)):,.2f}".replace(",", "@").replace(".", ",").replace("@", ".")
    return ("−" if float(v or 0) < 0 else "") + "R$ " + s


def sinal(v) -> str:
    s = f"{abs(float(v)):,.2f}".replace(",", "@").replace(".", ",").replace("@", ".")
    return ("+" if v >= 0 else "−") + " R$ " + s


CSS = """
@page{size:A4;margin:16mm 14mm}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Segoe UI',system-ui,sans-serif;color:#0D1E30;line-height:1.55;
  background:#EEF2F6;padding:28px}
.folha{max-width:900px;margin:0 auto;background:#fff;padding:44px 48px;
  border-radius:12px;box-shadow:0 2px 20px rgba(11,31,58,.10)}
.cab{border-bottom:3px solid #A18960;padding-bottom:18px;margin-bottom:26px}
.olho{font-size:11px;letter-spacing:.16em;text-transform:uppercase;color:#A18960;font-weight:700}
h1{font-size:26px;font-weight:700;margin-top:6px;letter-spacing:-.01em}
.sub{font-size:14px;color:#4A6278;margin-top:6px;max-width:62ch}
h2{font-size:17px;font-weight:700;margin:32px 0 4px}
.exp{font-size:13.5px;color:#4A6278;margin-bottom:14px;max-width:70ch}
table{width:100%;border-collapse:collapse;font-size:13.5px;margin-top:10px}
th{text-align:left;font-size:10.5px;letter-spacing:.5px;text-transform:uppercase;
  color:#4A6278;font-weight:700;padding:9px 10px;border-bottom:2px solid #0D1E30}
th.n,td.n{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
td{padding:9px 10px;border-bottom:1px solid #E3E9F0}
tr.total td{border-top:2px solid #0D1E30;border-bottom:none;font-weight:800;
  font-size:14.5px;padding-top:12px}
tr.neutro td{color:#7E93A8}
.pos{color:#2D7A3C;font-weight:700}
.neg{color:#C0392B;font-weight:700}
.dest{background:#FBF8F2}
.caixa{border-left:4px solid #A18960;background:#FBF8F2;padding:16px 20px;
  border-radius:0 8px 8px 0;margin:20px 0;font-size:13.5px;color:#4A6278;line-height:1.65}
.caixa b{color:#0D1E30}
.resumo{display:flex;gap:14px;margin:22px 0;flex-wrap:wrap}
.cartao{flex:1 1 200px;border:1px solid #DDE4ED;border-radius:10px;padding:16px 18px}
.cartao.forte{background:#0B1F3A;color:#fff;border-color:#0B1F3A}
.cartao .r{font-size:10.5px;letter-spacing:.5px;text-transform:uppercase;color:#4A6278;font-weight:700}
.cartao.forte .r{color:rgba(255,255,255,.65)}
.cartao .v{font-size:23px;font-weight:800;margin-top:4px;font-variant-numeric:tabular-nums}
.pe{font-size:12px;color:#7E93A8;margin-top:12px}
.rodape{margin-top:36px;padding-top:16px;border-top:1px solid #E3E9F0;
  font-size:11px;color:#7E93A8;line-height:1.7}
@media print{body{background:#fff;padding:0}
  .folha{box-shadow:none;padding:0;max-width:none}
  h2{break-after:avoid} table{break-inside:auto} tr{break-inside:avoid}}
"""


def main(antes_commit: str, periodos: list):
    A, D = pdata(antes_commit), pdata(None)
    labels = {p: (D.get(p, {}).get("label") or p) for p in periodos}
    ant = {p: por_prof(A, p) for p in periodos}
    dep = {p: por_prof(D, p) for p in periodos}
    nomes = sorted({n for p in periodos for n in set(ant[p]) | set(dep[p])})

    # --- linhas com alguma mudança ---
    linhas = []
    for n in nomes:
        difs = {p: dep[p].get(n, 0) - ant[p].get(n, 0) for p in periodos}
        tot = sum(difs.values())
        if all(abs(v) < 0.005 for v in difs.values()):
            continue
        linhas.append((n, difs, tot))
    linhas.sort(key=lambda x: -x[2])

    receber = sum(t for _, _, t in linhas if t > 0)
    descontar = sum(t for _, _, t in linhas if t < 0)
    sem_mudanca = len(nomes) - len(linhas)

    # --- tabela por período ---
    def tabela_periodo(p):
        a, d = ant[p], dep[p]
        muda = [n for n in nomes if abs(d.get(n, 0) - a.get(n, 0)) >= 0.005]
        muda.sort(key=lambda n: -(d.get(n, 0) - a.get(n, 0)))
        iguais = sum(a.get(n, 0) for n in nomes if n not in muda)
        corpo = "".join(
            f"<tr><td>{html.escape(n)}</td><td class='n'>{brl(a.get(n,0))}</td>"
            f"<td class='n'>{brl(d.get(n,0))}</td>"
            f"<td class='n {'pos' if d.get(n,0)-a.get(n,0)>=0 else 'neg'}'>"
            f"{sinal(d.get(n,0)-a.get(n,0))}</td></tr>" for n in muda)
        if iguais:
            corpo += (f"<tr class='neutro'><td>demais profissionais, sem alteração</td>"
                      f"<td class='n'>{brl(iguais)}</td><td class='n'>{brl(iguais)}</td>"
                      f"<td class='n'>—</td></tr>")
        ta, td = sum(a.values()), sum(d.values())
        corpo += (f"<tr class='total'><td>Total</td><td class='n'>{brl(ta)}</td>"
                  f"<td class='n'>{brl(td)}</td>"
                  f"<td class='n {'pos' if td-ta>=0 else 'neg'}'>{sinal(td-ta)}</td></tr>")
        return (f"<h2>{html.escape(labels[p])}</h2>"
                f"<div class='exp'>O que foi pago no fechamento anterior e o valor "
                f"apurado agora, com os dados atuais do Saudevianet.</div>"
                f"<table><thead><tr><th>Profissional</th><th class='n'>Pago</th>"
                f"<th class='n'>Valor correto</th><th class='n'>Diferença</th></tr></thead>"
                f"<tbody>{corpo}</tbody></table>")

    # --- tabela do líquido ---
    cabs = "".join(f"<th class='n'>{html.escape(labels[p])}</th>" for p in periodos)
    corpo = "".join(
        f"<tr class='{'dest' if abs(t) > 1000 else ''}'><td>{html.escape(n)}</td>"
        + "".join(f"<td class='n {'pos' if difs[p]>=0 else 'neg'}'>"
                  f"{sinal(difs[p]) if abs(difs[p])>=0.005 else '—'}</td>" for p in periodos)
        + f"<td class='n {'pos' if t>=0 else 'neg'}'>{sinal(t)}</td></tr>"
        for n, difs, t in linhas)
    tot_p = {p: sum(d[p] for _, d, _ in linhas) for p in periodos}
    corpo += ("<tr class='total'><td>Total</td>"
              + "".join(f"<td class='n {'pos' if tot_p[p]>=0 else 'neg'}'>{sinal(tot_p[p])}</td>"
                        for p in periodos)
              + f"<td class='n {'pos' if receber+descontar>=0 else 'neg'}'>"
                f"{sinal(receber+descontar)}</td></tr>")

    doc = f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<title>Acerto de honorários — {html.escape(' e '.join(labels[p] for p in periodos))}</title>
<style>{CSS}</style></head><body><div class="folha">

<div class="cab">
  <div class="olho">Endovascular SP · Gestão Administrativa</div>
  <h1>Acerto de honorários</h1>
  <div class="sub">{html.escape(' e '.join(labels[p] for p in periodos))} foram recalculados
    com os dados atuais do Saudevianet. Este documento mostra o que muda para cada
    profissional.</div>
</div>

<div class="resumo">
  <div class="cartao forte"><div class="r">A pagar</div>
    <div class="v">{brl(receber)}</div></div>
  <div class="cartao"><div class="r">A descontar</div>
    <div class="v">{brl(abs(descontar))}</div></div>
  <div class="cartao"><div class="r">Profissionais afetados</div>
    <div class="v">{len(linhas)}</div>
    <div class="pe">{sem_mudanca} sem nenhuma alteração</div></div>
</div>

<h2>O acerto de cada profissional</h2>
<div class="exp">Esta é a tabela que vale. O valor de um mês isolado engana: o que
sai de um período muitas vezes entra no seguinte.</div>
<table><thead><tr><th>Profissional</th>{cabs}<th class="n">A acertar</th></tr></thead>
<tbody>{corpo}</tbody></table>

<div class="caixa">
  <b>Por que o Dr. Igor cai em Junho e sobe em Julho.</b> A cirurgia da paciente
  Taciana Rabelo teve, no Saudevianet, o pagamento de R$ 30.000,00 lançado em
  25/06 <b>cancelado</b>, e um novo pagamento de R$ 42.232,50 compensado em 21/07.
  A cirurgia é a mesma, realizada em 26/06; o dinheiro entrou em julho, e por um
  valor maior. Junho estava contando dinheiro que não entrou.
</div>

{''.join(tabela_periodo(p) for p in periodos)}

<h2>O que mudou no cálculo</h2>
<div class="exp">Além da correção acima, três mudanças de regra foram aplicadas.</div>
<table><thead><tr><th>Mudança</th><th>Efeito</th></tr></thead><tbody>
<tr><td><b>Compensações que chegaram depois</b></td>
    <td>O fechamento de julho foi tirado em 03/08. Pagamentos compensados entre 25 e
        31/07 entraram no sistema depois e ficaram de fora.</td></tr>
<tr><td><b>Cirurgias lançadas sem executante</b></td>
    <td>Lançadas como “Agendamento Cirúrgico” ou “Enfermagem”, saíam inteiras do
        fechamento. Agora o atendimento é do médico solicitante.</td></tr>
<tr><td><b>Profissional da casa</b></td>
    <td>Quem é assalariado executa e gera receita, mas não recebe repasse. A receita
        passa a aparecer no painel como receita da clínica.</td></tr>
</tbody></table>

<div class="rodape">
  Todos os valores saem do que está publicado nos portais e podem ser conferidos lá,
  atendimento por atendimento, pelo botão “Ver conta”.<br>
  A coluna “Pago” foi lida da versão <code>{html.escape(antes_commit)}</code> do
  repositório do projeto — qualquer número deste documento pode ser reconferido nela.
</div>

</div></body></html>"""

    alvo = SAIDA / f"Acerto de honorarios - {'_'.join(periodos)}.html"
    io.open(alvo, "w", encoding="utf-8").write(doc)
    print(f"\n=== {' e '.join(labels[p] for p in periodos)} ===")
    print(f"  a pagar .............: {brl(receber)}")
    print(f"  a descontar .........: {brl(abs(descontar))}")
    print(f"  profissionais afetados: {len(linhas)} · sem alteração: {sem_mudanca}")
    print(f"\nGerado: {alvo}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--antes", required=True, help="commit com o PDATA do que foi pago")
    ap.add_argument("--periodos", required=True)
    a = ap.parse_args()
    main(a.antes, [p.strip() for p in a.periodos.split(",")])
