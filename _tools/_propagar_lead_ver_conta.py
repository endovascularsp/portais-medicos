# -*- coding: utf-8 -*-
r"""
_propagar_lead_ver_conta.py — mostra o LEAD e explica a Taxa de Aquisição dentro
do "Ver conta", nos 35 portais de médico e nos 3 dashboards.

Antes desta mudança o médico via "Repasse — 40%" e, no rodapé, a regra crua:
`Geral Endovascular SP + taxa de aquisição (−20 pts)`. A informação estava lá,
mas em linguagem de sistema. Com a Taxa de Aquisição valendo desde Julho/2026,
"por que 40%?" é a primeira pergunta que ele vai fazer — e a janela existe
exatamente para responder isso sozinha.

Passa a mostrar:
  · no bloco de identificação, ao lado da Indicação, de quem foi o LEAD;
  · na linha de fecho, a conta por extenso quando a taxa incidiu:
    "a categoria paga 60%, menos 20 pontos da Taxa de Aquisição, porque o
     paciente foi trazido pela clínica".

Lê da REGRA GRAVADA, não recalcula — mesma razão da coluna Lead na Base de
dados: duas implementações da mesma decisão de dinheiro um dia discordam.

Uso:
    python _tools/_propagar_lead_ver_conta.py
    python _tools/_propagar_lead_ver_conta.py --escrever
"""
from __future__ import annotations
import argparse
import io
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
REPO = Path(__file__).resolve().parent.parent

FN_DE = "function abrirBase(i){"
FN_PARA = """// De quem foi o lead deste atendimento, lido da regra que o motor gravou.
// Não recalcula: reimplementar a classificação aqui criaria duas verdades sobre
// a mesma decisão de dinheiro.
function _leadDaLinha(regra){
  const r = (regra || '').normalize('NFD').replace(/[\\u0300-\\u036f]/g,'').toLowerCase();
  if(!r) return null;
  if(r.includes('nf do profissional') || r.includes('profissional da casa')) return null;
  if(r.includes('lead da clinica') || r.includes('taxa de aquisicao')) return 'clinica';
  if(r.includes('lead do medico')) return 'medico';
  return null;
}

function abrirBase(i){"""

ID_DE = "    _idItem('Indicação',  a['Indicação']) +\n    '</dl>';"
ID_PARA = """    _idItem('Indicação',  a['Indicação']) +
    _idItem('Paciente trazido por',
            _leadDaLinha(a['Regra aplicada']) === 'clinica' ? 'Clínica'
          : _leadDaLinha(a['Regra aplicada']) === 'medico'  ? 'Você' : null) +
    '</dl>';"""

CONTA_DE = """      '<div class="bc-rapida">' + fmtBRL(liquido) + ' &times; ' +
        (pct*100).toFixed(0) + '% = ' + fmtBRL(repasse) + '</div>';"""
CONTA_PARA = """      '<div class="bc-rapida">' + fmtBRL(liquido) + ' &times; ' +
        (pct*100).toFixed(0) + '% = ' + fmtBRL(repasse) +
        _porqueDoPercentual(a['Regra aplicada'], pct) + '</div>';"""

FN2_DE = "function fecharBase(){"
FN2_PARA = """// Explica de onde saiu o percentual quando ele não é o cheio da categoria.
// Sem isto o médico lê "40%" e não tem como saber que a categoria dele paga 60%
// e que os 20 pontos foram a Taxa de Aquisição do Paciente.
function _porqueDoPercentual(regra, pct){
  const lead = _leadDaLinha(regra);
  const r = (regra || '').normalize('NFD').replace(/[\\u0300-\\u036f]/g,'').toLowerCase();
  if(lead === 'clinica' && r.includes('taxa de aquisicao')){
    const cheio = Math.round((pct + 0.20) * 100);
    return '<br><span style="opacity:0.75">A categoria paga ' + cheio + '%. '
         + 'Saíram 20 pontos da Taxa de Aquisição do Paciente, porque este '
         + 'paciente foi trazido pela clínica.</span>';
  }
  if(lead === 'clinica'){
    return '<br><span style="opacity:0.75">Percentual de cirurgia para paciente '
         + 'trazido pela clínica.</span>';
  }
  if(lead === 'medico'){
    return '<br><span style="opacity:0.75">Percentual cheio: este paciente foi '
         + 'trazido por você.</span>';
  }
  return '';
}

function fecharBase(){"""

TROCAS = [("função do lead", FN_DE, FN_PARA),
          ("linha na identificação", ID_DE, ID_PARA),
          ("explicação do percentual", CONTA_DE, CONTA_PARA),
          ("função da explicação", FN2_DE, FN2_PARA)]


def alvos():
    fs = [REPO / "recebimento.html", REPO / "oxy" / "index.html",
          REPO / "cirurgias" / "index.html"]
    fs += [f for f in sorted(REPO.glob("*.html"))
           if f.name not in ("index.html", "recebimento.html")]
    for sub in ("oxy", "cirurgias"):
        fs += [f for f in sorted((REPO / sub).glob("*.html")) if f.name != "index.html"]
    return fs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--escrever", action="store_true")
    a = ap.parse_args()
    contagem, problemas = {}, 0
    for f in alvos():
        if not f.exists():
            continue
        txt = novo = f.read_text(encoding="utf-8")
        if "_leadDaLinha" in txt:
            contagem["já tinha"] = contagem.get("já tinha", 0) + 1
            continue
        erro = None
        for nome, de, para in TROCAS:
            if novo.count(de) != 1:
                erro = f"ABORTA em '{nome}' ({novo.count(de)}x)"
                break
            novo = novo.replace(de, para, 1)
        if erro:
            problemas += 1
            print(f"  {str(f.relative_to(REPO)):46} {erro}")
            continue
        if a.escrever:
            f.write_text(novo, encoding="utf-8")
        contagem["ok" if a.escrever else "faria"] = contagem.get("ok" if a.escrever else "faria", 0) + 1
    for k, v in sorted(contagem.items(), key=lambda kv: -kv[1]):
        print(f"  {v:3} arquivo(s): {k}")
    if not a.escrever:
        print("\n[simulação] nada gravado. Rode com --escrever.")
    print(f"problemas: {problemas}")
    return 1 if problemas else 0


if __name__ == "__main__":
    sys.exit(main())
