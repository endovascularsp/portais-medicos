# -*- coding: utf-8 -*-
"""
_honorarios_acerto.py — monta o documento de acerto de um profissional: o que
mudou entre o que foi comunicado antes e o que está publicado agora, linha a
linha, com a conta aberta.

Serve para sentar com o médico e validar junto. Não inventa nada: o "antes" sai
do PDATA publicado num commit anterior do próprio repositório, e o "depois" do
que está no ar. Se o número não bate, dá para abrir o commit e conferir.

Gera um HTML — abre com dois cliques e imprime bem.

Uso:
    python _tools/_honorarios_acerto.py --prof "Igor Rafael Sincos" \
        --antes 79b7984 --periodos 2026-06,2026-07
"""
from __future__ import annotations
import argparse
import html
import json
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SAIDA = Path.home() / "Downloads"


def pdata_do_commit(commit: str | None) -> dict:
    """O PDATA do recebimento.html — de um commit, ou do arquivo atual."""
    if commit:
        txt = subprocess.run(["git", "show", f"{commit}:recebimento.html"],
                             capture_output=True, cwd=REPO).stdout.decode("utf-8")
    else:
        txt = (REPO / "recebimento.html").read_text(encoding="utf-8")
    m = re.search(r"const TODOS_PERIODOS\s*=\s*/\*PDATA\*/(\{.*?\});", txt, re.S)
    if not m:
        raise SystemExit(f"ABORTADO: não achei o PDATA em {commit or 'recebimento.html'}")
    return json.loads(m.group(1))


def linhas_do_prof(pdata: dict, periodo: str, prof: str) -> list:
    """Todos os atendimentos do profissional no período, de todas as empresas."""
    out = []
    for slug, v in (pdata.get(periodo, {}).get("profs") or {}).items():
        if v.get("profissional") != prof:
            continue
        for a in v.get("atendimentos", []):
            out.append({**a, "_empresa": v.get("empresa")})
    return out


def chave(a: dict) -> tuple:
    return (str(a.get("Nº OS") or a.get("N° OS") or "").strip(),
            str(a.get("Procedimento") or "").strip(),
            f"{float(a.get('Valor recebido') or 0):.2f}",
            str(a.get("Paciente") or "").strip())


def brl(v) -> str:
    return "R$ " + f"{float(v or 0):,.2f}".replace(",", "@").replace(".", ",").replace("@", ".")


def bloco_conta(a: dict) -> str:
    """A conta da linha, no formato que o Thiago aprovou."""
    receb = float(a.get("Valor recebido") or 0)
    liq = float(a.get("Valor Líquido") or 0)
    rep = float(a.get("Repasse Profissional (R$)") or 0)
    total_imp = float(a.get("Imposto (18%)") or 0)
    com = float(a.get("Taxa comercial (2%)") or 0)
    car = float(a.get("Taxa cartão (3%)") or 0)
    iss = round(total_imp - com, 2)
    if rep < 0:
        pct = abs(rep) / receb if receb else 0
        return (f"<div class='nf'>Faturado na nota fiscal do profissional — a clínica não recebeu "
                f"este valor. O valor negativo é a comissão de {pct*100:.0f}% que a clínica retém.</div>"
                f"<table class='conta'>"
                f"<tr><td>Valor na nota do profissional</td><td>{brl(receb)}</td></tr>"
                f"<tr class='d'><td>(−) Comissão da clínica — {pct*100:.0f}%</td><td>{brl(abs(rep))}</td></tr>"
                f"<tr class='b'><td>Fica com o profissional</td><td>{brl(receb + rep)}</td></tr></table>")
    linhas = [f"<tr><td>Valor recebido</td><td>{brl(receb)}</td></tr>"]
    if iss > 0:
        linhas.append(f"<tr class='d'><td>(−) ISS 18%</td><td>{brl(iss)}</td></tr>")
    if com > 0:
        linhas.append(f"<tr class='d'><td>(−) Taxa comercial 2%</td><td>{brl(com)}</td></tr>")
    if car > 0:
        linhas.append(f"<tr class='d'><td>(−) Taxa de cartão 3%</td><td>{brl(car)}</td></tr>")
    linhas.append(f"<tr class='b'><td>= Valor líquido <span class='leve'>(base de cálculo)</span></td>"
                  f"<td>{brl(liq)}</td></tr>")
    pct = (rep / liq * 100) if liq else 0
    linhas.append(f"<tr class='r'><td>Repasse — {pct:.0f}%</td><td>{brl(rep)}</td></tr>")
    regra = a.get("Regra aplicada")
    fim = (f"<div class='regra'>{brl(liq)} × {pct:.0f}% = {brl(rep)}"
           + (f" &nbsp;·&nbsp; regra: <code>{html.escape(str(regra))}</code>" if regra else "")
           + "</div>")
    return "<table class='conta'>" + "".join(linhas) + "</table>" + fim


def cartao(a: dict, rotulo: str, cor: str) -> str:
    ident = " · ".join(x for x in [
        f"OS {a.get('Nº OS') or a.get('N° OS') or '—'}",
        str(a.get("Categoria") or ""), str(a.get("Tabela") or ""),
        str(a.get("Tipo de pagamento") or ""),
        f"compensado em {a.get('Data compensação')}" if a.get("Data compensação") else "",
        str(a.get("_empresa") or ""),
    ] if x)
    return (f"<div class='item {cor}'>"
            f"<div class='tag'>{html.escape(rotulo)}</div>"
            f"<div class='pac'>{html.escape(str(a.get('Paciente') or '—'))}</div>"
            f"<div class='proc'>{html.escape(str(a.get('Procedimento') or '—'))}</div>"
            f"<div class='ident'>{html.escape(ident)}</div>"
            f"{bloco_conta(a)}</div>")


CSS = """
body{font-family:'Segoe UI',system-ui,sans-serif;background:#EEF2F6;color:#0D1E30;margin:0;padding:28px;}
.wrap{max-width:900px;margin:0 auto;}
h1{font-size:22px;margin:0 0 4px;} .sub{color:#4A6278;font-size:13px;margin-bottom:24px;}
.resumo{background:#0B1F3A;color:#fff;border-radius:12px;padding:20px 24px;margin-bottom:26px;}
.resumo table{width:100%;border-collapse:collapse;font-size:14px;}
.resumo td{padding:7px 0;border-bottom:1px solid rgba(255,255,255,0.12);}
.resumo td:last-child,.resumo td:nth-child(2),.resumo td:nth-child(3){text-align:right;
  font-variant-numeric:tabular-nums;white-space:nowrap;padding-left:16px;}
.resumo tr:last-child td{border-bottom:none;font-weight:800;font-size:16px;padding-top:12px;}
.resumo .pos{color:#7CD992;} .resumo .neg{color:#F19A8E;}
h2{font-size:16px;margin:28px 0 6px;} .exp{color:#4A6278;font-size:13px;margin-bottom:14px;line-height:1.6;}
.item{background:#fff;border:1px solid #DDE4ED;border-left:5px solid #A18960;border-radius:10px;
  padding:16px 18px;margin-bottom:14px;}
.item.sai{border-left-color:#C0392B;} .item.entra{border-left-color:#2D7A3C;}
.tag{font-size:10px;font-weight:800;letter-spacing:.6px;text-transform:uppercase;color:#4A6278;margin-bottom:6px;}
.pac{font-weight:700;font-size:15px;} .proc{font-size:13px;color:#0D1E30;margin-top:2px;}
.ident{font-size:11px;color:#4A6278;margin:6px 0 12px;}
table.conta{width:100%;border-collapse:collapse;font-size:13px;}
table.conta td{padding:6px 0;border-bottom:1px solid #EEF2F6;}
table.conta td:last-child{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap;padding-left:14px;}
table.conta .d td{color:#C0392B;}
table.conta .b td{border-top:2px solid #0D1E30;border-bottom:none;font-weight:800;padding-top:9px;}
table.conta .r td{font-weight:800;color:#A18960;font-size:14px;border-bottom:none;}
.leve{font-weight:400;font-size:11px;color:#4A6278;}
.regra{margin-top:9px;background:#F2F5F9;border-radius:7px;padding:8px 12px;font-size:12px;text-align:center;}
.regra code{font-family:Consolas,monospace;font-size:11px;}
.nf{background:#FFF8E6;border:1px solid #F0D48A;border-radius:8px;padding:10px 13px;
  font-size:12.5px;color:#6B5310;margin-bottom:12px;line-height:1.5;}
.rodape{margin-top:32px;font-size:11px;color:#4A6278;text-align:center;line-height:1.7;}
@media print{body{background:#fff;padding:0;} .item{break-inside:avoid;}}
"""


def main(prof: str, antes: str, periodos: list):
    pd_antes, pd_agora = pdata_do_commit(antes), pdata_do_commit(None)
    partes, tot_a, tot_d = [], 0.0, 0.0
    resumo = []

    for pid in periodos:
        la = linhas_do_prof(pd_antes, pid, prof)
        ld = linhas_do_prof(pd_agora, pid, prof)
        ra = sum(float(x.get("Repasse Profissional (R$)") or 0) for x in la)
        rd = sum(float(x.get("Repasse Profissional (R$)") or 0) for x in ld)
        tot_a += ra
        tot_d += rd
        label = (pd_agora.get(pid) or {}).get("label", pid)
        resumo.append((label, ra, rd, len(la), len(ld)))

        ca = {chave(x): x for x in la}
        cd = {chave(x): x for x in ld}
        saem = [ca[k] for k in ca.keys() - cd.keys()]
        entram = [cd[k] for k in cd.keys() - ca.keys()]
        # Linha que ficou, mas com valor diferente — é o caso mais fácil de
        # passar batido: o total muda e não há linha entrando nem saindo para
        # explicar. Aconteceu com a Dra. Christiane (+R$ 1.498,39 sem nenhuma
        # linha nova). Sem isto, o documento mostrava a diferença sem a causa.
        mudam = []
        for k in ca.keys() & cd.keys():
            va = float(ca[k].get("Repasse Profissional (R$)") or 0)
            vd = float(cd[k].get("Repasse Profissional (R$)") or 0)
            if abs(va - vd) > 0.005:
                mudam.append((ca[k], cd[k], vd - va))
        if not saem and not entram and not mudam:
            continue
        partes.append(f"<h2>{html.escape(label)}</h2>")
        if saem:
            partes.append("<div class='exp'>Estas linhas <b>saíram</b> do fechamento deste mês.</div>")
            for a in sorted(saem, key=lambda x: -float(x.get("Repasse Profissional (R$)") or 0)):
                partes.append(cartao(a, "saiu deste mês", "sai"))
        if entram:
            partes.append("<div class='exp'>Estas linhas <b>entraram</b> no fechamento deste mês.</div>")
            for a in sorted(entram, key=lambda x: -float(x.get("Repasse Profissional (R$)") or 0)):
                partes.append(cartao(a, "entrou neste mês", "entra"))
        if mudam:
            partes.append("<div class='exp'>Estas linhas <b>continuam</b> no fechamento, mas o valor "
                          "do repasse mudou. Abaixo, a conta como ficou.</div>")
            for _a, d, dif in sorted(mudam, key=lambda x: -abs(x[2])):
                rot = (f"repasse {'subiu' if dif > 0 else 'caiu'} {brl(abs(dif))}")
                partes.append(cartao(d, rot, "entra" if dif > 0 else "sai"))

    linhas_res = "".join(
        f"<tr><td>{html.escape(lb)}</td><td>{brl(a)}</td><td>{brl(d)}</td>"
        f"<td class='{'pos' if d-a >= 0 else 'neg'}'>{'+' if d-a >= 0 else '−'}{brl(abs(d-a))[3:]}</td></tr>"
        for lb, a, d, na, nd in resumo)
    linhas_res += (f"<tr><td>Total</td><td>{brl(tot_a)}</td><td>{brl(tot_d)}</td>"
                   f"<td class='{'pos' if tot_d-tot_a >= 0 else 'neg'}'>"
                   f"{'+' if tot_d-tot_a >= 0 else '−'}{brl(abs(tot_d-tot_a))[3:]}</td></tr>")

    doc = (f"<!doctype html><html lang='pt-BR'><head><meta charset='utf-8'>"
           f"<title>Acerto de honorários — {html.escape(prof)}</title><style>{CSS}</style></head><body>"
           f"<div class='wrap'><h1>Acerto de honorários — {html.escape(prof)}</h1>"
           f"<div class='sub'>Comparação entre o que havia sido comunicado e o que está publicado agora. "
           f"Cada linha traz a conta aberta, para conferir na calculadora.</div>"
           f"<div class='resumo'><table><tr><td></td><td>Antes</td><td>Agora</td><td>Diferença</td></tr>"
           f"{linhas_res}</table></div>"
           + "".join(partes) +
           f"<div class='rodape'>Gerado a partir do que está publicado no portal.<br>"
           f"O \"antes\" foi lido da versão <code>{html.escape(antes)}</code> do próprio repositório — "
           f"qualquer número aqui pode ser reconferido lá.</div></div></body></html>")

    alvo = SAIDA / f"Acerto - {prof} - {'_'.join(periodos)}.html"
    alvo.write_text(doc, encoding="utf-8")
    print(f"\n=== {prof} ===")
    for lb, a, d, na, nd in resumo:
        print(f"  {lb:16s} {brl(a):>16s} -> {brl(d):>16s}   ({na} -> {nd} linhas)")
    print(f"  {'TOTAL':16s} {brl(tot_a):>16s} -> {brl(tot_d):>16s}   diferença {brl(tot_d-tot_a)}")
    print(f"\nGerado: {alvo}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--prof", required=True)
    ap.add_argument("--antes", required=True, help="commit com o PDATA anterior")
    ap.add_argument("--periodos", required=True)
    a = ap.parse_args()
    main(a.prof, a.antes, [p.strip() for p in a.periodos.split(",")])
