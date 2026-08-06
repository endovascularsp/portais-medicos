# -*- coding: utf-8 -*-
"""
_remover_csv_geral.py — tira o botão "⬇ CSV" dos portais de Recebimento.

Decisão do Thiago em 06/08/2026. Existiam DOIS botões de exportação na mesma
tela, e isso gerava dúvida:

  ⬇ CSV            no cabeçalho — CSV resumido, uma linha por profissional;
  ⬇ Exportar Excel dentro do painel do profissional — .xlsx detalhado, uma
                   linha por atendimento, com as colunas de ISS e taxa
                   comercial separadas.

O segundo é o que interessa. O primeiro, além de redundante, não tinha o
detalhe por linha e nos portais individuais gerava um arquivo de uma linha só.

Remove três coisas por arquivo:
  1. o botão no cabeçalho;
  2. a função exportarCSVGeral;
  3. a função _download, que só existia para ela (conferido: nenhuma outra
     chamada). O .xlsx usa _downloadBin, que fica.

Uso:
    python _tools/_remover_csv_geral.py            # simula
    python _tools/_remover_csv_geral.py --escrever
"""
from __future__ import annotations
import argparse
import io
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

BOTAO = ("\n    <button class='header-action-btn' onclick='exportarCSVGeral()' "
         "title='Exportar CSV consolidado do período'>⬇ CSV</button>")


class Falha(Exception):
    pass


def corta_funcao(t: str, assinatura: str) -> str:
    """Remove a função inteira, da assinatura até o '}' na coluna 0."""
    if t.count(assinatura) != 1:
        raise Falha(f"'{assinatura}' aparece {t.count(assinatura)}x")
    i = t.index(assinatura)
    m = re.compile(r"\n\}\n").search(t, i)
    if not m:
        raise Falha(f"não achei o fim de '{assinatura}'")
    # come também a linha em branco que sobra antes
    ini = i
    while ini > 0 and t[ini - 1] == "\n" and t[ini - 2:ini - 1] == "\n":
        ini -= 1
    return t[:ini] + t[m.end():]


def limpar(t: str) -> tuple[str, str]:
    """Devolve (html, o_que_foi_feito).

    Só os 3 admins têm o botão na tela. Nos outros 40 portais a função existe
    sem botão nenhum — é código morto, herdado do template. Nos dois casos ela
    sai, mas o relatório distingue, para ficar claro o que o médico deixa de
    ver e o que era invisível de todo jeito."""
    if "exportarCSVGeral" not in t:
        raise Falha("já não tem o CSV geral")
    n = t.count(BOTAO)
    if n > 1:
        raise Falha(f"markup do botão aparece {n}x")
    marca = "botão + função" if n == 1 else "função órfã (não havia botão)"
    if n == 1:
        t = t.replace(BOTAO, "", 1)
    t = corta_funcao(t, "function exportarCSVGeral(){")

    # _download só existia para o CSV geral — confere antes de tirar
    restantes = len(re.findall(r"\b_download\s*\(", t)) - len(re.findall(r"function _download\s*\(", t))
    if restantes:
        raise Falha(f"_download ainda tem {restantes} chamada(s) — não removo")
    t = corta_funcao(t, "function _download(conteudo,nome){")

    if "exportarCSVGeral" in t or "_download(" in t.replace("_downloadBin(", ""):
        raise Falha("sobrou referência ao CSV geral")
    # o .xlsx tem de continuar inteiro
    for peca in ("exportarCSVProf", "_downloadBin", "_xlsxArquivo", "_XLSX_COLS"):
        if peca not in t:
            raise Falha(f"'{peca}' sumiu — o Excel quebraria")
    return t, marca


def main(escrever: bool) -> int:
    alvos = sorted(
        [p for p in REPO.glob("*.html")] +
        [p for p in (REPO / "oxy").glob("*.html")] +
        [p for p in (REPO / "cirurgias").glob("*.html")],
        key=lambda p: str(p))
    print(f"\n=== Remover o CSV geral · escrever={escrever} ===\n")
    ok = pulados = 0
    for p in alvos:
        t = io.open(p, encoding="utf-8").read()
        if "exportarCSVGeral" not in t:
            continue
        bruto = p.read_bytes()
        fim = "\r\n" if bruto.count(b"\r\n") > bruto.count(b"\n") // 2 else "\n"
        try:
            novo, marca = limpar(t)
        except Falha as e:
            pulados += 1
            print(f"  [PULADO] {str(p.relative_to(REPO))[:50]:52s} {e}")
            continue
        if escrever:
            io.open(p, "w", encoding="utf-8", newline=fim).write(novo)
        ok += 1
        print(f"  [OK]     {str(p.relative_to(REPO))[:50]:52s} -{len(t)-len(novo):>4d} chars  {marca}")
    print(f"\n  {ok} arquivo(s) · {pulados} pulado(s)")
    if not escrever:
        print("\n  [simulação] nada gravado. Rode com --escrever.")
    return pulados


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--escrever", action="store_true")
    raise SystemExit(1 if main(ap.parse_args().escrever) else 0)
