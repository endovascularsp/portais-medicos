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
from collections import Counter, defaultdict
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


def atendimentos(D: dict, pid: str) -> dict:
    out = defaultdict(list)
    for _, v in (D.get(pid, {}).get("profs") or {}).items():
        for a in v.get("atendimentos", []):
            out[v["profissional"]].append(a)
    return out


def _ch(a: dict) -> tuple:
    return (str(a.get("Nº OS") or a.get("N° OS") or ""), str(a.get("Procedimento") or ""),
            f"{float(a.get('Valor recebido') or 0):.2f}", str(a.get("Paciente") or ""))


def _rep(a: dict) -> float:
    return float(a.get("Repasse Profissional (R$)") or 0)


def _os(a: dict) -> str:
    return str(a.get("Nº OS") or a.get("N° OS") or "—")


def _pct(a: dict) -> str:
    """O percentual aplicado naquela linha, quando dá para saber."""
    p = a.get("% Aplicado")
    if p is None:
        p = a.get("% Repasse Prof")
    if p is None:
        liq = float(a.get("Valor Líquido") or 0)
        return f"{_rep(a)/liq*100:.0f}%" if liq else "—"
    return f"{float(p)*100:.0f}%"


def comparar(antes_l: list, agora_l: list):
    """Casa os atendimentos de antes e de agora, respeitando repetições.

    Índice em LISTA, não em dicionário: um pacote de 10 sessões gera 10 linhas
    idênticas, e um dicionário guardaria só a última.
    """
    ca, cd = defaultdict(list), defaultdict(list)
    for a in antes_l:
        ca[_ch(a)].append(a)
    for a in agora_l:
        cd[_ch(a)].append(a)
    saiu, entrou, mudou = [], [], []
    for k in set(ca) | set(cd):
        la, lb = ca.get(k, []), cd.get(k, [])
        n = min(len(la), len(lb))
        for i in range(n):
            if abs(_rep(la[i]) - _rep(lb[i])) > 0.005:
                mudou.append((la[i], lb[i]))
        saiu.extend(la[n:])
        entrou.extend(lb[n:])

    # linha que saiu e voltou com outro nome na MESMA OS, mesmo valor e paciente:
    # o Saudevianet renomeou o procedimento. O repasse pode ter mudado junto.
    def sem_nome(a):
        return (_os(a), f"{float(a.get('Valor recebido') or 0):.2f}", str(a.get("Paciente") or ""))
    disp = defaultdict(list)
    for b in entrou:
        disp[sem_nome(b)].append(b)
    renomeadas, sumiram = [], []
    for a in saiu:
        k = sem_nome(a)
        if disp[k]:
            renomeadas.append((a, disp[k].pop(0)))
        else:
            sumiram.append(a)
    novas = [b for lst in disp.values() for b in lst]
    return sumiram, novas, mudou + [p for p in renomeadas if abs(_rep(p[0]) - _rep(p[1])) > 0.005], \
        [p for p in renomeadas if abs(_rep(p[0]) - _rep(p[1])) <= 0.005]


def detalhe_por_os(antes_l: list, agora_l: list) -> list:
    """Uma linha por OS afetada, com o motivo daquela OS especificamente."""
    sumiram, novas, mudou, _renom = comparar(antes_l, agora_l)
    porta = defaultdict(lambda: {"antes": 0.0, "depois": 0.0, "pac": "", "proc": set(),
                                 "causas": set(), "de": "", "para": ""})
    for a in sumiram:
        d = porta[_os(a)]
        d["antes"] += _rep(a); d["pac"] = d["pac"] or str(a.get("Paciente") or "")
        d["proc"].add(str(a.get("Procedimento") or ""))
        d["causas"].add("saiu")
    for b in novas:
        d = porta[_os(b)]
        d["depois"] += _rep(b); d["pac"] = d["pac"] or str(b.get("Paciente") or "")
        d["proc"].add(str(b.get("Procedimento") or ""))
        d["causas"].add("solicitante" if "solicitante" in str(b.get("Regra aplicada") or "")
                        else "entrou")
    for a, b in mudou:
        d = porta[_os(b)]
        d["antes"] += _rep(a); d["depois"] += _rep(b)
        d["pac"] = d["pac"] or str(b.get("Paciente") or "")
        d["proc"].add(str(b.get("Procedimento") or ""))
        d["de"], d["para"] = _pct(a), _pct(b)
        regra = str(b.get("Regra aplicada") or "")
        # "Indicador ..." não é redução: o profissional entrou como indicador, e
        # o valor foi para a coluna de repasse de indicador. Dizer "percentual
        # recalculado" aqui daria a entender que ele perdeu o dinheiro.
        d["ind"] = d.get("ind", 0.0) + float(b.get("Repasse Indicador (R$)") or 0)
        d["causas"].add("indicador" if regra.lower().startswith("indicador")
                        else ("lead" if "lead" in regra else "regra"))

    TEXTO = {
        "saiu":        "pagamento cancelado ou reprocessado no Saudevianet — o valor não entrou neste mês",
        "entrou":      "lançamento que passou a constar no fechamento",
        "solicitante": "cirurgia lançada sem executante; o atendimento passou a ser do médico solicitante",
        "lead":        "percentual da cirurgia ajustado conforme a origem do paciente",
        "indicador":   "atuou como indicador, não como executor — o valor foi para o repasse de indicador",
        "regra":       "percentual recalculado pela regra da categoria",
    }
    out = []
    for os_, d in porta.items():
        txt = "; ".join(TEXTO[c] for c in sorted(d["causas"], key=lambda c: list(TEXTO).index(c)))
        if "indicador" in d["causas"] and d.get("ind"):
            txt += f" ({brl(d['ind'])})"
        elif d["de"] and d["para"] and d["de"] != d["para"]:
            txt += f" (de {d['de']} para {d['para']})"
        out.append({"os": os_, "paciente": d["pac"],
                    "proc": " · ".join(sorted(d["proc"]))[:70],
                    "antes": d["antes"], "depois": d["depois"], "motivo": txt})
    out.sort(key=lambda x: abs(x["depois"] - x["antes"]), reverse=True)
    return out


# O motivo NÃO é escrito à mão: é deduzido comparando os atendimentos de antes e
# de agora. Texto fixo envelhece e passa a mentir no mês seguinte; esta função
# olha o que de fato mudou em cada linha.
def motivo(antes_l: list, agora_l: list) -> str:
    """O resumo de uma linha da tabela: as causas agrupadas, com valor."""
    sumiram, novas, mudou, renomeadas = comparar(antes_l, agora_l)
    causas = []
    if sumiram:
        v = sum(_rep(a) for a in sumiram)
        causas.append(f"{len(sumiram)} lançamento(s) deixaram de constar no Saudevianet "
                      f"({brl(v)} de repasse)")
    if novas:
        v = sum(_rep(a) for a in novas)
        rot = ("cirurgia lançada sem executante, agora atribuída ao solicitante"
               if any("solicitante" in str(a.get("Regra aplicada") or "") for a in novas)
               else "lançamentos que passaram a entrar no fechamento")
        causas.append(f"{len(novas)} {rot} ({brl(v)})")
    reg = [(a, b) for a, b in mudou
           if str(a.get("Regra aplicada") or "") != str(b.get("Regra aplicada") or "")]
    if reg:
        v = sum(_rep(b) - _rep(a) for a, b in reg)
        lead = sum(1 for _, b in reg if "lead" in str(b.get("Regra aplicada") or ""))
        rot = ("percentual da cirurgia recalculado conforme a origem do paciente"
               if lead >= len(reg) / 2 else "percentual recalculado pela regra da categoria")
        causas.append(f"{len(reg)} {rot} ({sinal(v)})")
    resto = [(a, b) for a, b in mudou if (a, b) not in reg]
    if resto:
        v = sum(_rep(b) - _rep(a) for a, b in resto)
        rot = "ajuste(s) de arredondamento" if abs(v) < 1 else "linha(s) com valor recalculado"
        causas.append(f"{len(resto)} {rot} ({sinal(v)})")
    if renomeadas and not causas:
        causas.append("procedimento renomeado no Saudevianet, sem efeito no valor")
    return "; ".join(causas) or "recálculo com os dados atuais"


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
table.comobs{font-size:12.5px}
table.comobs td,table.comobs th{padding:9px 8px}
td.obs{font-size:11.5px;color:#4A6278;line-height:1.5;max-width:280px}
td.os{font-family:Consolas,monospace;font-size:11.5px;color:#0D1E30;white-space:nowrap}
td.os i{font-style:normal;color:#7E93A8}
h3{font-size:14px;font-weight:700;margin:22px 0 2px}
h3 .mini{font-weight:400;color:#7E93A8;font-size:12px}
.mini{font-size:11px;color:#7E93A8;margin-top:2px;line-height:1.4}
table.det{font-size:12px;margin-top:8px}
table.det td,table.det th{padding:7px 8px}
table.det tbody tr:nth-child(even) td{background:#FAFCFE}
h2.quebra{break-before:page;margin-top:36px}
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
        la, ld = atendimentos(A, p), atendimentos(D, p)
        muda = [n for n in nomes if abs(d.get(n, 0) - a.get(n, 0)) >= 0.005]
        muda.sort(key=lambda n: -(d.get(n, 0) - a.get(n, 0)))
        iguais = sum(a.get(n, 0) for n in nomes if n not in muda)
        det = {n: detalhe_por_os(la.get(n, []), ld.get(n, [])) for n in muda}

        def col_os(n):
            oss = [x["os"] for x in det[n]]
            if len(oss) <= 3:
                return "<br>".join(html.escape(o) for o in oss)
            return ("<br>".join(html.escape(o) for o in oss[:2])
                    + f"<br><i>e mais {len(oss)-2}</i>")

        corpo = "".join(
            f"<tr><td><b>{html.escape(n)}</b></td>"
            f"<td class='os'>{col_os(n)}</td>"
            f"<td class='n'>{brl(a.get(n,0))}</td>"
            f"<td class='n'>{brl(d.get(n,0))}</td>"
            f"<td class='n {'pos' if d.get(n,0)-a.get(n,0)>=0 else 'neg'}'>"
            f"{sinal(d.get(n,0)-a.get(n,0))}</td>"
            f"<td class='obs'>{html.escape(motivo(la.get(n,[]), ld.get(n,[])))}</td></tr>"
            for n in muda)
        if iguais:
            corpo += (f"<tr class='neutro'><td>demais profissionais, sem alteração</td>"
                      f"<td class='os'>—</td>"
                      f"<td class='n'>{brl(iguais)}</td><td class='n'>{brl(iguais)}</td>"
                      f"<td class='n'>—</td><td class='obs'>—</td></tr>")
        ta, td = sum(a.values()), sum(d.values())
        corpo += (f"<tr class='total'><td>Total</td><td></td><td class='n'>{brl(ta)}</td>"
                  f"<td class='n'>{brl(td)}</td>"
                  f"<td class='n {'pos' if td-ta>=0 else 'neg'}'>{sinal(td-ta)}</td>"
                  f"<td></td></tr>")

        # --- detalhamento: uma linha por OS, com o motivo daquela OS ---------
        blocos = []
        for n in muda:
            linhas_os = "".join(
                f"<tr><td class='os'>{html.escape(x['os'])}</td>"
                f"<td>{html.escape(x['paciente'])}<div class='mini'>{html.escape(x['proc'])}</div></td>"
                f"<td class='n'>{brl(x['antes']) if x['antes'] else '—'}</td>"
                f"<td class='n'>{brl(x['depois']) if x['depois'] else '—'}</td>"
                f"<td class='n {'pos' if x['depois']-x['antes']>=0 else 'neg'}'>"
                f"{sinal(x['depois']-x['antes'])}</td>"
                f"<td class='obs'>{html.escape(x['motivo'])}</td></tr>" for x in det[n])
            tt = sum(x["depois"] - x["antes"] for x in det[n])
            blocos.append(
                f"<h3>{html.escape(n)} <span class='mini'>· {len(det[n])} OS · "
                f"{sinal(tt)}</span></h3>"
                f"<table class='det'><thead><tr><th>OS</th><th>Paciente e procedimento</th>"
                f"<th class='n'>Pago</th><th class='n'>Correto</th><th class='n'>Dif.</th>"
                f"<th>Motivo</th></tr></thead><tbody>{linhas_os}</tbody></table>")

        return (f"<h2>{html.escape(labels[p])}</h2>"
                f"<div class='exp'>O que foi pago no fechamento anterior, o valor "
                f"apurado agora com os dados atuais do Saudevianet, e o que explica "
                f"a diferença de cada um.</div>"
                f"<table class='comobs'><thead><tr><th>Profissional</th><th>OS</th>"
                f"<th class='n'>Pago</th>"
                f"<th class='n'>Valor correto</th><th class='n'>Diferença</th>"
                f"<th>O que foi corrigido</th></tr></thead>"
                f"<tbody>{corpo}</tbody></table>"
                f"<h2 class='quebra'>Detalhamento por ordem de serviço</h2>"
                f"<div class='exp'>Cada OS afetada, com o motivo específico daquela "
                f"ordem. Qualquer linha pode ser conferida no portal, no botão "
                f"“Ver conta”.</div>" + "".join(blocos))

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

    # Com um período só, a tabela do "líquido" seria a mesma da do período —
    # mostrar as duas confundiria. O documento então traz uma só.
    um_so = len(periodos) == 1
    tabela_liquido = "" if um_so else f"""
<h2>O acerto de cada profissional</h2>
<div class="exp">Esta é a tabela que vale. O valor de um mês isolado engana: o que
sai de um período muitas vezes entra no seguinte.</div>
<table><thead><tr><th>Profissional</th>{cabs}<th class="n">A acertar</th></tr></thead>
<tbody>{corpo}</tbody></table>"""

    # A nota da OS cancelada é obrigatória quando só Junho é apresentado: sem ela,
    # os R$ 12,7 mil a menos do Dr. Igor parecem perda, e não adiamento.
    nota_taciana = ("""
<div class="caixa">
  <b>Sobre a maior diferença deste mês.</b> A cirurgia da paciente Taciana Rabelo
  teve, no Saudevianet, o pagamento de R$ 30.000,00 lançado em 25/06
  <b>cancelado</b>, e um novo pagamento emitido com compensação em julho. A
  cirurgia é a mesma, realizada em 26/06 — o que mudou foi quando o dinheiro
  entrou. Junho estava contando um valor que não foi recebido; ele aparece,
  corrigido e maior, no fechamento de julho.
</div>""" if um_so else """
<div class="caixa">
  <b>Por que o Dr. Igor cai em Junho e sobe em Julho.</b> A cirurgia da paciente
  Taciana Rabelo teve, no Saudevianet, o pagamento de R$ 30.000,00 lançado em
  25/06 <b>cancelado</b>, e um novo pagamento de R$ 42.232,50 compensado em 21/07.
  A cirurgia é a mesma, realizada em 26/06; o dinheiro entrou em julho, e por um
  valor maior. Junho estava contando dinheiro que não entrou.
</div>""")

    doc = f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<title>Acerto de honorários — {html.escape(' e '.join(labels[p] for p in periodos))}</title>
<style>{CSS}</style></head><body><div class="folha">

<div class="cab">
  <div class="olho">Endovascular SP · Gestão Administrativa</div>
  <h1>Acerto de honorários</h1>
  <div class="sub">{html.escape(' e '.join(labels[p] for p in periodos))}
    {'foi recalculado' if um_so else 'foram recalculados'} com os dados atuais do
    Saudevianet. Este documento mostra o que muda para cada profissional.</div>
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
{tabela_liquido}
{nota_taciana}
{''.join(tabela_periodo(p) for p in periodos)}

<h2>O que mudou no cálculo</h2>
<div class="exp">Além da correção acima, {'duas' if um_so else 'três'} mudanças de
regra foram aplicadas.</div>
<table><thead><tr><th>Mudança</th><th>Efeito</th></tr></thead><tbody>
{'' if um_so else '''<tr><td><b>Compensações que chegaram depois</b></td>
    <td>O fechamento de julho foi tirado em 03/08. Pagamentos compensados entre 25 e
        31/07 entraram no sistema depois e ficaram de fora.</td></tr>'''}
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
