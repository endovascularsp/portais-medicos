# -*- coding: utf-8 -*-
"""
_propagar_ver_conta.py — leva o botão "Ver conta" a todos os portais de
Recebimento.

O memorial de cálculo foi feito em 07/08/2026 e ficou só no admin do Gestor
(recebimento.html). A varredura de paridade em 10/08 mostrou que faltava nos
admins da Oxy e de Cirurgias e nos 40 portais individuais — justamente onde o
médico olha.

O que é copiado, do arquivo que o Thiago já validou:
  - o CSS do modal (bloco "Base de cálculo");
  - a coluna "Conta" no cabeçalho da tabela de atendimentos;
  - o botão em cada linha, e o `_ATEND_NA_TELA` que ele indexa;
  - as funções abrirBase/fecharBase e o markup do modal.

Os campos que a conta usa (ISS, taxa comercial, regra aplicada) já existem em
todos os portais — conferido antes de escrever, inclusive dentro dos blocos
criptografados dos individuais.

Uso:
    python _tools/_propagar_ver_conta.py            # simula
    python _tools/_propagar_ver_conta.py --escrever
"""
from __future__ import annotations
import argparse
import io
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
FONTE = REPO / "recebimento.html"


class Falha(Exception):
    pass


def recorta(txt: str, ini: str, fim: str, rotulo: str) -> str:
    i = txt.find(ini)
    if i < 0:
        raise Falha(f"não achei o início de {rotulo}")
    j = txt.find(fim, i + len(ini))
    if j < 0:
        raise Falha(f"não achei o fim de {rotulo}")
    return txt[i:j]


def pecas() -> dict:
    """Tira do recebimento.html as partes a copiar. Fonte única: se o Thiago
    pedir um ajuste no memorial, muda-se lá e roda-se isto de novo."""
    f = FONTE.read_text(encoding="utf-8")
    return {
        # O bloco termina na media query do modal. Cortar no próximo "/* ===" pegava
        # 18 KB — todo o resto da folha de estilo entrava junto.
        "css": recorta(f, "/* ── Base de cálculo ─", "\n.prof-header{", "CSS do modal"),
        "modal": recorta(f, "<!-- ── Base de cálculo:", "\n<script>\nconst ", "markup do modal"),
        "js": recorta(f, "// ── Base de cálculo ─", "\nfunction fecharBase()", "funções")
              + "\nfunction fecharBase(){\n"
                "  document.getElementById('bc-fundo').classList.remove('aberto');\n}\n"
                "document.addEventListener('keydown', e=>{ if(e.key === 'Escape') fecharBase(); });\n",
    }


def aplicar(t: str, p: dict) -> str:
    if "abrirBase(" in t:
        raise Falha("já tem o botão")

    # --- CSS: entra junto com o resto do estilo da tabela -------------------
    alvo = ".atend-table .cat-badge{"
    i = t.find(alvo)
    if i < 0:
        raise Falha("não achei o CSS da tabela de atendimentos")
    j = t.index("}", i) + 1
    t = t[:j] + "\n.atend-table .c{text-align:center;}\n" + p["css"] + t[j:]

    # --- cabeçalho: coluna nova --------------------------------------------
    cab = "<th class='r'>Repasse</th>"
    if t.count(cab) != 1:
        raise Falha(f"cabeçalho 'Repasse' aparece {t.count(cab)}x")
    t = t.replace(cab, cab + "\n            <th class='c'>Conta</th>", 1)

    # --- corpo da tabela ----------------------------------------------------
    m = re.search(r"(const atends\s*=\s*[^;]+;\s*\n\s*document\.getElementById\('body-atend'\)\.innerHTML\s*=\s*)"
                  r"atends\.length===0\s*\n(\s*)\?('<tr><td colspan=\")(\d+)(\"[^']*'\s*)\n\s*:\s*atends\.map\(a=>",
                  t)
    if not m:
        raise Falha("não achei a montagem da tabela de atendimentos")
    t = (t[:m.start()] + m.group(1).replace("const atends", "const atends", 1)
         + "atends.length===0\n" + m.group(2) + "?" + m.group(3)
         + str(int(m.group(4)) + 1) + m.group(5)
         + "\n" + m.group(2) + ": atends.map((a,i)=>" + t[m.end():])
    # guarda a lista que o botão indexa
    t = t.replace("const atends=d.atendimentos||[];",
                  "const atends=d.atendimentos||[];\n  _ATEND_NA_TELA = atends;   "
                  "// o botão \"Ver conta\" indexa nesta lista", 1)

    # --- botão em cada linha ------------------------------------------------
    fim_linha = ("'<td class=\"r\" style=\"color:var(--verde);font-weight:600\">'"
                 "+fmtBRL(a['Repasse Profissional (R$)'])+'</td>'+")
    if t.count(fim_linha) != 1:
        raise Falha(f"última célula da linha aparece {t.count(fim_linha)}x")
    t = t.replace(fim_linha, fim_linha +
                  "\n        '<td class=\"c\"><button class=\"bc-btn\" onclick=\"abrirBase('+i+')\">"
                  "Ver conta</button></td>'+", 1)

    # --- modal e funções ----------------------------------------------------
    # O modal entra logo antes do <script> principal — fora de qualquer div de
    # layout. Dentro de um container ele herdaria overflow e posicionamento, e
    # a janela apareceria cortada ou atrás do conteúdo.
    marca = "\n<script>\nconst "
    if t.count(marca) != 1:
        raise Falha(f"âncora do script principal aparece {t.count(marca)}x")
    k = t.index(marca)
    t = t[:k] + "\n" + p["modal"] + t[k:]

    # as funções vão para o fim do script principal, antes do último </script>
    k2 = t.rindex("</script>")
    t = t[:k2] + "\n" + p["js"] + "\n" + t[k2:]

    for peca in ("abrirBase(", "fecharBase(", "bc-fundo", "_ATEND_NA_TELA", "bc-btn"):
        if peca not in t:
            raise Falha(f"'{peca}' não entrou")
    return t


def alvos() -> list:
    out = []
    for p in sorted(REPO.glob("*.html")):
        if p.name in ("index.html", "recebimento.html"):
            continue
        out.append(p)
    for pasta in ("oxy", "cirurgias"):
        out += sorted((REPO / pasta).glob("*.html"))
    return [p for p in out if "atend-table" in p.read_text(encoding="utf-8", errors="replace")]


def main(escrever: bool) -> int:
    p = pecas()
    print(f"\n=== Propagar o 'Ver conta' · escrever={escrever} ===")
    print(f"    CSS {len(p['css'])} chars · modal {len(p['modal'])} · funções {len(p['js'])}\n")
    ok = pulados = 0
    for path in alvos():
        t = io.open(path, encoding="utf-8").read()
        bruto = path.read_bytes()
        fim = "\r\n" if bruto.count(b"\r\n") > bruto.count(b"\n") // 2 else "\n"
        try:
            novo = aplicar(t, p)
        except Falha as e:
            pulados += 1
            print(f"  [PULADO] {str(path.relative_to(REPO))[:50]:52s} {e}")
            continue
        if escrever:
            io.open(path, "w", encoding="utf-8", newline=fim).write(novo)
        ok += 1
        print(f"  [OK]     {str(path.relative_to(REPO))[:50]:52s} +{len(novo)-len(t):>5d} chars")
    print(f"\n  {ok} arquivo(s) · {pulados} pulado(s)")
    if not escrever:
        print("\n  [simulação] nada gravado. Rode com --escrever.")
    return pulados


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--escrever", action="store_true")
    raise SystemExit(1 if main(ap.parse_args().escrever) else 0)
