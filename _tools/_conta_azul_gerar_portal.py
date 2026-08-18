# -*- coding: utf-8 -*-
r"""
_conta_azul_gerar_portal.py — puxa o Conta Azul e injeta os dados em custos/index.html.

Mesmo desenho dos outros portais da casa: página estática com os dados dentro,
entre marcas /*CDATA*/. Sem servidor, sem chamada do navegador para o Conta Azul
— o que também evita o problema chato de expor o token da API no HTML.

DUAS COISAS QUE ESTE ARQUIVO DECIDE, e que mudam os números na tela:

1. TRANSFERÊNCIA E EMPRÉSTIMO NÃO SÃO RESULTADO. A maior "despesa" de 2026 no
   Conta Azul é `TRANSFERÊNCIAS ENTRE CONTAS`, R$ 2,03 milhões — dinheiro indo de
   uma conta da casa para outra conta da casa. Do lado da receita, R$ 2,7 milhões
   da mesma coisa. Somar isso infla custo e receita ao mesmo tempo e faz o portal
   mentir. Aqui esses lançamentos vão marcados (`m:1`) e ficam FORA das contas por
   padrão — o portal tem um botão para mostrá-los quando alguém quiser conferir
   saldo de conta.

2. "ENDOVASCULAR SP" ESTÁ CADASTRADO DUAS VEZES no Conta Azul (um em maiúsculas
   com R$ 4,7 milhões, outro com R$ 29 mil). São dois centros de custo diferentes
   lá, quase certamente criados sem querer. Aqui os dois viram um só, comparando
   sem acento e sem maiúscula. Se um dia forem separados de propósito, é aqui que
   se desfaz.

O formato gravado usa índices (o ambiente vira um número que aponta para a lista
de nomes) porque são milhares de lançamentos e o arquivo vai junto com a página:
repetir "ENDOVASCULAR SP" 2.500 vezes custa mais que a página inteira.

Uso:
    python _tools/_conta_azul_gerar_portal.py                       # ano corrente
    python _tools/_conta_azul_gerar_portal.py --de 2025-01-01
    python _tools/_conta_azul_gerar_portal.py --simular             # não grava
"""
from __future__ import annotations
import argparse
import io
import json
import re
import sys
import unicodedata
import urllib.error
from datetime import date, datetime
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _conta_azul_api import get                                   # noqa: E402

REPO = Path(__file__).resolve().parent.parent
PORTAL = REPO / "custos" / "index.html"
PAGAR = "/v1/financeiro/eventos-financeiros/contas-a-pagar/buscar"
RECEBER = "/v1/financeiro/eventos-financeiros/contas-a-receber/buscar"

# Categorias que são movimento de dinheiro, não resultado. Comparadas sem acento
# e sem maiúscula, por trecho — o Conta Azul tem "TRANSFERÊNCIAS ENTRE CONTAS"
# nas despesas e "TRANSFERÊNCIA ENTRE CONTAS" (singular) nas receitas.
MOVIMENTO = ("transferencia", "emprestimo", "resgate", "aplicacao financeira",
             "adiantamentos para futuros aumentos de capital", "aporte de capital")


def chave(s: str) -> str:
    s = unicodedata.normalize("NFD", str(s or "")).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", s).strip().lower()


def e_movimento(nome: str) -> bool:
    k = chave(nome)
    return any(t in k for t in MOVIMENTO)


def meses(de: str, ate: str):
    a, m = int(de[:4]), int(de[5:7])
    fim = (int(ate[:4]), int(ate[5:7]))
    while (a, m) <= fim:
        u = 31
        while True:
            try:
                date(a, m, u); break
            except ValueError:
                u -= 1
        yield f"{a}-{m:02d}-01", f"{a}-{m:02d}-{u:02d}"
        a, m = (a + 1, 1) if m == 12 else (a, m + 1)


def puxar(caminho: str, de: str, ate: str) -> list:
    tudo = []
    for d, t in meses(de, ate):
        pagina = 1
        while True:
            try:
                r = get(caminho, data_vencimento_de=d, data_vencimento_ate=min(t, ate),
                        pagina=pagina, tamanho_pagina=100)
            except urllib.error.HTTPError as e:
                print(f"    {d[:7]}: ERRO {e.code} — mês pulado")
                break
            itens = r.get("itens", []) if isinstance(r, dict) else []
            tudo += itens
            if len(itens) < 100:
                break
            pagina += 1
            if pagina > 60:
                print(f"    {d[:7]}: AVISO — parei na página 60")
                break
        print(f"    {d[:7]}: {len(tudo)} acumulados")
    return tudo


class Tabela:
    """Lista de nomes sem repetição, devolvendo o índice. Mescla variações do
    mesmo nome (maiúscula/acento) para não haver dois 'Endovascular SP'."""

    def __init__(self):
        self.nomes, self.por_chave = [], {}

    def idx(self, nome) -> int:
        nome = (nome or "").strip() or "(em branco)"
        k = chave(nome)
        if k not in self.por_chave:
            self.por_chave[k] = len(self.nomes)
            self.nomes.append(nome)          # guarda a 1ª grafia vista
        return self.por_chave[k]


def compactar(itens: list, amb: Tabela, cat: Tabela, pes: Tabela, campo_pessoa: str):
    """Cada lançamento vira uma lista curta e posicional:
       [ambiente, categoria, pessoa, vencimento, competência, total, pago, movimento]
    A descrição fica fora: é o campo mais pesado e só serve no detalhe, que a
    tela monta a partir da lista separada `desc` no mesmo índice."""
    linhas, descricoes = [], []
    for i in itens:
        c = (i.get("categorias") or [{}])[0]
        cc = (i.get("centros_de_custo") or [{}])[0]
        p = i.get(campo_pessoa) or {}
        linhas.append([
            amb.idx(cc.get("nome")),
            cat.idx(c.get("nome")),
            pes.idx(p.get("nome")),
            (i.get("data_vencimento") or "")[:10],
            (i.get("data_competencia") or i.get("data_vencimento") or "")[:10],
            round(float(i.get("total") or 0), 2),
            round(float(i.get("pago") or 0), 2),
            1 if e_movimento(c.get("nome")) else 0,
        ])
        descricoes.append((i.get("descricao") or "")[:90])
    return linhas, descricoes


MARCA = "/*" + "CDATA" + "*/"      # partido para a marca não existir neste arquivo


def injetar(caminho: Path, dados: dict) -> None:
    """Troca o bloco de dados do portal.

    A busca é ancorada em `const D = <marca>` em vez de procurar a marca solta,
    e o arquivo tem de conter a marca EXATAMENTE duas vezes. As duas travas
    existem pelo mesmo motivo: na primeira versão a marca também aparecia no
    comentário do topo do HTML, a busca casou do comentário até a abertura dos
    dados e apagou a página inteira no caminho — sem erro nenhum, porque o
    padrão tinha casado direitinho com o que foi pedido.
    """
    txt = caminho.read_text(encoding="utf-8")
    if txt.count(MARCA) != 2:
        raise SystemExit(
            f"ABORTADO: {caminho.name} tem {txt.count(MARCA)} ocorrências da marca de dados; "
            "o esperado é 2 (abre e fecha). Não vou escrever para não apagar a página.")
    padrao = re.compile(r"(const D\s*=\s*)" + re.escape(MARCA) + r".*?" + re.escape(MARCA), re.S)
    if len(padrao.findall(txt)) != 1:
        raise SystemExit(f"ABORTADO: não achei `const D = {MARCA}…` em {caminho.name}.")
    novo = json.dumps(dados, ensure_ascii=False, separators=(",", ":"))
    caminho.write_text(padrao.sub(lambda m: m.group(1) + MARCA + novo + MARCA, txt, count=1),
                       encoding="utf-8")


def main() -> int:
    hoje = date.today()
    ap = argparse.ArgumentParser()
    ap.add_argument("--de", default=f"{hoje.year}-01-01")
    ap.add_argument("--ate", default=f"{hoje.year}-12-31")
    ap.add_argument("--simular", action="store_true")
    a = ap.parse_args()

    print("Contas a pagar:")
    pagar = puxar(PAGAR, a.de, a.ate)
    print("Contas a receber:")
    receber = puxar(RECEBER, a.de, a.ate)

    amb, cat, forn, cli = Tabela(), Tabela(), Tabela(), Tabela()
    lp, dp = compactar(pagar, amb, cat, forn, "fornecedor")
    lr, dr = compactar(receber, amb, cat, cli, "cliente")

    dados = {
        "gerado_em": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "de": a.de, "ate": a.ate,
        "amb": amb.nomes, "cat": cat.nomes,
        "forn": forn.nomes, "cli": cli.nomes,
        "pagar": lp, "pagar_desc": dp,
        "receber": lr, "receber_desc": dr,
    }

    def soma(l, so_resultado=True):
        return sum(x[5] for x in l if not (so_resultado and x[7]))
    print(f"\n  {len(lp)} contas a pagar   — resultado R$ {soma(lp):,.2f}"
          f"   (movimento R$ {sum(x[5] for x in lp if x[7]):,.2f})"
          .replace(",", "@").replace(".", ",").replace("@", "."))
    print(f"  {len(lr)} contas a receber — resultado R$ {soma(lr):,.2f}"
          f"   (movimento R$ {sum(x[5] for x in lr if x[7]):,.2f})"
          .replace(",", "@").replace(".", ",").replace("@", "."))
    print(f"  {len(amb.nomes)} ambientes · {len(cat.nomes)} categorias · "
          f"{len(forn.nomes)} fornecedores · {len(cli.nomes)} clientes")

    if a.simular:
        print("\n[simulação] nada gravado.")
        return 0
    injetar(PORTAL, dados)
    kb = PORTAL.stat().st_size / 1024
    print(f"\nGRAVADO: {PORTAL.relative_to(REPO)}  ({kb:,.0f} KB)"
          .replace(",", "."))
    return 0


if __name__ == "__main__":
    sys.exit(main())
