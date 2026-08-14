# -*- coding: utf-8 -*-
"""
_propagar_ajustes_portais.py — leva ao portal os descontos e acréscimos.

Fecha o caminho aberto pela migration_013 e pela aba "Descontos e acréscimos"
do card de Fechamento: o que a equipe financeira lança lá aparece aqui, para o
profissional, em dois cards novos e num detalhe abrível.

O PROBLEMA QUE ISTO RESOLVE (Julho/2026)
Uma médica viu o valor no portal, recebeu menos na conta e ligou. O portal não
estava errado — ele respondia "quanto a clínica te deve pelo trabalho do mês", e
o desconto de um custo pessoal dela nunca passou pelo Saudevianet.

O QUE ENTRA
  1. dois cards, entre "Repasse do Mês" e "Atendimentos":
       💼 Descontos e acréscimos   − R$ 1.850,00   [entenda os valores]
       🏦 Total a Receber            R$ 55.750,00
  2. `verAjustes()`, que reaproveita a janela do "Ver conta" para listar item a
     item o que foi descontado e o que foi somado.

DECISÃO DE PROJETO: o card "Repasse do Mês" NÃO muda. Ele é a soma da coluna de
repasse da tabela de atendimentos e do Excel que o médico baixa; se passasse a
vir com desconto embutido, ele somaria as linhas, daria diferente do card, e
teríamos criado a confusão que fomos consertar. O ajuste entra como um passo a
mais, e o último número é o que cai na conta.

Os cards só existem quando há lançamento no mês — mês limpo mostra a tela de
sempre, sem card novo e sem pergunta nova.

Uso:
    python _tools/_propagar_ajustes_portais.py                     # simula
    python _tools/_propagar_ajustes_portais.py --somente Igor_Rafael_Sincos.html --escrever
    python _tools/_propagar_ajustes_portais.py --escrever
"""
from __future__ import annotations
import argparse
import io
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

CSS = """
/* O botão vive dentro de um card colorido: herda o branco do card, não o
   dourado do "Ver conta" da tabela. */
.kpi .bc-btn{border-color:rgba(255,255,255,0.55);color:#fff;background:transparent;}
.kpi .bc-btn:hover{background:rgba(255,255,255,0.18);border-color:#fff;color:#fff;}
.kpi.cinza .bc-btn{border-color:var(--gold);color:var(--gold);}
.kpi.cinza .bc-btn:hover{background:var(--gold);color:#fff;}
"""

CALCULO = """  // ── Descontos e acréscimos ──────────────────────────────────────────────
  // Valores que não passam pelo Saudevianet (plano de saúde que a clínica paga
  // e desconta, custo pessoal, devolução de cobrança indevida). São lançados à
  // mão na aba "Descontos e acréscimos" do card de Fechamento e chegam aqui
  // pelo PDATA. Sem lançamento no mês, nada aparece.
  _AJUSTES_NA_TELA = d.ajustes || [];
  const _ajEfeito = Number(r['Ajustes (R$)'] || 0);
  const cardsAjuste = _AJUSTES_NA_TELA.length ? (
    '<div class="kpi cinza"><div class="kpi-ic">💼</div><div class="kpi-label">Descontos e acr&eacute;scimos</div><div class="kpi-val">' +
      (_ajEfeito < 0 ? '&minus; ' : '+ ') + fmtBRL(Math.abs(_ajEfeito)) +
      '</div><div class="kpi-foot"><button class="bc-btn" onclick="verAjustes()">entenda os valores</button></div></div>' +
    '<div class="kpi gold"><div class="kpi-ic">🏦</div><div class="kpi-label">Total a Receber</div><div class="kpi-val">' +
      fmtBRL(Number(r['Total a Receber (R$)'] || 0)) +
      '</div><div class="kpi-foot"><span style="opacity:0.6">O que entra na sua conta</span></div></div>') : '';

"""

FUNCAO = """
// ── Descontos e acréscimos ──────────────────────────────────────────────────
// Reaproveita a janela do "Ver conta": mesma moldura, mesmo Esc para fechar.
// Por isso as duas funções escrevem o título — quem não escrevesse herdaria o
// título da outra.
let _AJUSTES_NA_TELA = [];

function verAjustes(){
  const itens = _AJUSTES_NA_TELA || [];
  if(!itens.length) return;
  const soma = itens.reduce((s,a) => s + (a.Tipo === 'acrescimo' ? 1 : -1) * Number(a.Valor||0), 0);

  document.getElementById('bc-titulo').textContent = 'Descontos e acréscimos';
  document.getElementById('bc-sub').innerHTML =
    'O que a clínica descontou ou somou fora dos atendimentos do mês';

  let html = '<table class="bc-conta">';
  itens.forEach(a => {
    const desconto = a.Tipo !== 'acrescimo';
    html += '<tr class="' + (desconto ? 'desc' : '') + '"><td>' +
      (desconto ? '(&minus;) ' : '(+) ') + (a['Descrição'] || '—') +
      '</td><td>' + fmtBRL(a.Valor) + '</td></tr>';
  });
  html += '<tr class="rep"><td>' + (soma < 0 ? 'Total descontado' : 'Total somado') +
          '</td><td>' + fmtBRL(Math.abs(soma)) + '</td></tr></table>' +
    '<div class="bc-rapida">Estes valores não vêm de atendimento: são acertos ' +
    'lançados pela clínica. O card <b>Repasse do Mês</b> continua sendo a soma ' +
    'dos seus atendimentos; o <b>Total a Receber</b> é ele mais estes acertos.</div>';

  document.getElementById('bc-corpo').innerHTML = html;
  document.getElementById('bc-fundo').classList.add('aberto');
}
"""


class Falha(Exception):
    pass


def aplicar(t: str) -> str:
    if "verAjustes(" in t:
        raise Falha("já tem os cards")

    # --- CSS ---------------------------------------------------------------
    alvo = ".bc-btn:hover{background:var(--gold);color:#fff;}"
    if t.count(alvo) != 1:
        raise Falha(f"CSS do .bc-btn aparece {t.count(alvo)}x")
    t = t.replace(alvo, alvo + CSS, 1)

    # --- cálculo, logo antes de montar a linha de KPIs ----------------------
    marca = "  document.getElementById('metrics-prof').innerHTML="
    if t.count(marca) != 1:
        raise Falha(f"bloco de KPIs aparece {t.count(marca)}x")
    t = t.replace(marca, CALCULO + marca, 1)

    # --- os dois cards, antes do card de Atendimentos -----------------------
    m = re.search(r"\n(\s*)'<div class=\"kpi navy-med\"><div class=\"kpi-ic\">📋</div>"
                  r"<div class=\"kpi-label\">Atendimentos</div>", t)
    if not m:
        raise Falha("não achei o card de Atendimentos")
    t = t[:m.start()] + "\n" + m.group(1) + "cardsAjuste+" + t[m.start():]

    # --- funções, no fim do script principal --------------------------------
    k = t.rindex("</script>")
    t = t[:k] + FUNCAO + t[k:]

    # A janela é compartilhada: o "Ver conta" precisa reescrever o título, senão
    # herda "Descontos e acréscimos" de quem abriu antes.
    if "function abrirBase(i){" in t:
        t = t.replace("function abrirBase(i){\n  const a = _ATEND_NA_TELA[i];\n  if(!a) return;",
                      "function abrirBase(i){\n  const a = _ATEND_NA_TELA[i];\n  if(!a) return;\n"
                      "  document.getElementById('bc-titulo').textContent = 'Base de cálculo';", 1)
        if "textContent = 'Base de cálculo'" not in t:
            raise Falha("não consegui devolver o título ao 'Ver conta'")

    for peca in ("verAjustes(", "cardsAjuste+", "_AJUSTES_NA_TELA"):
        if peca not in t:
            raise Falha(f"'{peca}' não entrou")
    return t


def alvos(somente: str | None) -> list:
    out = []
    for p in (sorted(REPO.glob("*.html")) + sorted((REPO / "oxy").glob("*.html"))
              + sorted((REPO / "cirurgias").glob("*.html"))):
        rel = str(p.relative_to(REPO))
        if somente and somente.lower() not in rel.lower():
            continue
        if "metrics-prof').innerHTML=" in p.read_text(encoding="utf-8", errors="replace"):
            out.append(p)
    return out


def main(escrever: bool, somente: str | None) -> int:
    print(f"\n=== Cards de descontos e acréscimos · escrever={escrever} ===\n")
    ok = pulados = 0
    for path in alvos(somente):
        t = io.open(path, encoding="utf-8").read()
        bruto = path.read_bytes()
        fim = "\r\n" if bruto.count(b"\r\n") > bruto.count(b"\n") // 2 else "\n"
        try:
            novo = aplicar(t)
        except Falha as e:
            pulados += 1
            print(f"  [PULADO] {str(path.relative_to(REPO))[:52]:54s} {e}")
            continue
        if escrever:
            io.open(path, "w", encoding="utf-8", newline=fim).write(novo)
        ok += 1
        print(f"  [OK]     {str(path.relative_to(REPO))[:52]:54s} {len(novo)-len(t):>+6d} chars")
    print(f"\n  {ok} arquivo(s) · {pulados} pulado(s)")
    if not escrever:
        print("\n  [simulação] nada gravado. Rode com --escrever.")
    return pulados


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--escrever", action="store_true")
    ap.add_argument("--somente")
    a = ap.parse_args()
    raise SystemExit(1 if main(a.escrever, a.somente) else 0)
