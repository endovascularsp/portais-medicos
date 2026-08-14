# -*- coding: utf-8 -*-
"""
_tirar_clinica_do_medico.py — tira a parte da clínica de tudo que o médico vê.

Pedido do Dr. Igor, 14/08/2026, pelo Thiago: o memorial de cálculo termina no
que o médico recebe. O quanto fica para a clínica sai de dois lugares:

  1. o modal "Ver conta" — a linha final "Fica com a clínica";
  2. o Excel que o médico exporta — a última coluna, "% Clínica".

NÃO mexe em nada interno. Ficam intocados, de propósito:
  - a aba "Base de dados" do card de Fechamento (`fechamento/index.html`), que
    tem lista de colunas própria, lida direto do banco, e só a gestão abre;
  - os 3 admins do Gestor (`recebimento.html`, `oxy/index.html`,
    `cirurgias/index.html`), que são MODO_MEDICO=false — visão da clínica
    inteira, sem senha de médico.

O alvo é escolhido pelo próprio arquivo (`MODO_MEDICO = true`), não por lista de
nomes: portal novo que apareça amanhã entra sozinho.

Reintrodução: portal novo é clonado de um portal já existente da mesma pasta
(`_honorarios_criar_portal.py`), então nasce sem a linha. O caminho de volta
seria rodar `_propagar_ver_conta.py`, que copia de `recebimento.html` — mas ele
pula quem já tem o botão, e todo portal de médico tem.

Uso:
    python _tools/_tirar_clinica_do_medico.py                    # simula tudo
    python _tools/_tirar_clinica_do_medico.py --somente Igor_Rafael_Sincos.html --escrever
    python _tools/_tirar_clinica_do_medico.py --escrever
"""
from __future__ import annotations
import argparse
import io
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

NOTA_COL = (
    "  // A parte da clínica não vai no arquivo do médico (pedido do Dr. Igor,\n"
    "  // 14/08/2026). O número continua na aba \"Base de dados\" do card de\n"
    "  // Fechamento, que é interna.\n"
)
NOTA_MODAL = (
    "    // O memorial termina no que o médico recebe: a parte da clínica saiu a\n"
    "    // pedido do Dr. Igor em 14/08/2026. Ela continua na aba \"Base de dados\"\n"
    "    // do card de Fechamento, que só a gestão abre.\n"
)

# Cada peça: (rótulo, regex, texto que entra no lugar)
PECAS = [
    ("coluna % Clínica",
     re.compile(r"[ \t]*\{h:'% Clínica',[^\n]*\n"),
     NOTA_COL),
    ("função _repasseClinica",
     re.compile(r"\n// % Clínica passa a ser gravado.*?\nfunction _repasseClinica\(a\)\{.*?\n\}\n",
                re.S),
     "\n"),
    ("const clinica",
     re.compile(r"[ \t]*const clinica\s*=\s*_num\(a\['Repasse Clínica \(R\$\)'\]\);\n"),
     ""),
    ("linha 'Fica com a clínica'",
     re.compile(r"[ \t]*// Até Maio/2026 a parte da clínica.*?"
                r"\n[ \t]*if\(Math\.abs\(fica\)[^\n]*\n", re.S),
     NOTA_MODAL),
]

PROIBIDOS = ("Fica com a clínica", "_repasseClinica", "const fica", "const clinica")


class Falha(Exception):
    pass


def aplicar(t: str) -> str:
    if "Fica com a clínica" not in t and "_repasseClinica" not in t:
        raise Falha("já está sem a parte da clínica")
    cols_antes = t.count("{h:'")
    for rotulo, rx, novo in PECAS:
        achados = rx.findall(t)
        if len(achados) != 1:
            raise Falha(f"'{rotulo}' aparece {len(achados)}x (esperado 1)")
        t = rx.sub(lambda _m: novo, t, count=1)
    for p in PROIBIDOS:
        if p in t:
            raise Falha(f"sobrou '{p}' no arquivo")
    if t.count("{h:'") != cols_antes - 1:
        raise Falha(f"contagem de colunas errada: {cols_antes} → {t.count('{h:')}")
    return t


def alvos(somente: str | None) -> list:
    """Portais de médico: MODO_MEDICO = true. Os admins do Gestor ficam de fora."""
    out = []
    for p in sorted(REPO.glob("*.html")) + sorted((REPO / "oxy").glob("*.html")) \
            + sorted((REPO / "cirurgias").glob("*.html")):
        if somente and somente.lower() not in str(p.relative_to(REPO)).lower():
            continue
        t = p.read_text(encoding="utf-8", errors="replace")
        if re.search(r"MODO_MEDICO\s*=\s*true", t) and "Fica com a clínica" in t:
            out.append(p)
    return out


def main(escrever: bool, somente: str | None) -> int:
    print(f"\n=== Tirar a parte da clínica do que o médico vê · escrever={escrever} ===\n")
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
    ap.add_argument("--somente", help="filtra pelo caminho, ex.: Igor_Rafael_Sincos.html")
    a = ap.parse_args()
    raise SystemExit(1 if main(a.escrever, a.somente) else 0)
