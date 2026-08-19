# -*- coding: utf-8 -*-
r"""
_conta_azul_gerar_portal.py — puxa o Conta Azul e injeta os dados em custos/index.html.

Mesmo desenho dos outros portais da casa: página estática com os dados dentro,
entre as marcas de bloco. A página NÃO fala com o Conta Azul — se falasse, o
token da contabilidade da empresa viajaria dentro do HTML.

QUATRO DECISÕES QUE MUDAM OS NÚMEROS NA TELA:

1. PUXA POR COMPETÊNCIA, NÃO POR VENCIMENTO. A busca do Conta Azul exige a data
   de vencimento, mas aceita filtrar junto pela competência — e é a competência
   que diz quando o gasto ACONTECEU. A primeira versão puxava por vencimento e
   somava por competência, e errava dos dois lados ao mesmo tempo: entravam
   R$ 3,7 milhões de compras de 2024/2025 cujas parcelas caem em 2026, e ficavam
   de fora as compras de 2026 com parcela em 2027. O custo de 2026 aparecia
   inflado em mais de 50% (R$ 10,2 mi em vez de R$ 6,6 mi).

2. A FILA DE PAGAMENTO É PUXADA À PARTE, por vencimento e sem recorte de
   competência. Uma parcela de uma compra de 2024 que vence semana que vem
   continua saindo do caixa — o recorte de competência responde "quanto custou",
   e não pode apagar o "quanto sai".

3. TRANSFERÊNCIA E EMPRÉSTIMO VÃO MARCADOS (`m:1`) e ficam fora das contas por
   padrão. São dinheiro andando entre contas da própria casa: entram como
   despesa numa ponta e receita na outra.

4. "ENDOVASCULAR SP" ESTÁ CADASTRADO DUAS VEZES lá (um em maiúsculas com
   R$ 4,7 milhões, outro com R$ 29 mil). Aqui os dois viram um só, comparando
   sem acento e sem maiúscula.

Vai junto o GRUPO DE DRE de cada categoria (`entrada_dre` do Conta Azul), que é
o que permite o drill grupo → categoria → quem recebeu → lançamento. Cobre
90,6% do valor; o resto cai em "Sem grupo definido", e isso aparece na tela em
vez de ser escondido numa conta de "outros".

Uso:
    python _tools/_conta_azul_gerar_portal.py                 # ano passado + este
    python _tools/_conta_azul_gerar_portal.py --de 2024-01-01
    python _tools/_conta_azul_gerar_portal.py --simular       # não grava
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

# Só quando é o programa: trocar o wrapper de quem importou fecha o de dentro e
# o script chamador morre com "I/O operation on closed file".
if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _conta_azul_api import get                                   # noqa: E402

REPO = Path(__file__).resolve().parent.parent
PORTAL = REPO / "custos" / "index.html"
PAGAR = "/v1/financeiro/eventos-financeiros/contas-a-pagar/buscar"
RECEBER = "/v1/financeiro/eventos-financeiros/contas-a-receber/buscar"

# Janela de vencimento propositalmente larga: quem recorta é a competência.
VENC_ABERTO = ("2019-01-01", "2035-12-31")

# Categorias que são movimento de dinheiro, não resultado. Comparadas sem acento
# e sem maiúscula, por trecho — o Conta Azul tem "TRANSFERÊNCIAS ENTRE CONTAS"
# nas despesas e "TRANSFERÊNCIA ENTRE CONTAS" (singular) nas receitas.
MOVIMENTO = ("transferencia", "emprestimo", "resgate", "aplicacao financeira",
             "adiantamentos para futuros aumentos de capital", "aporte de capital")

# Os grupos chegam em CAIXA_ALTA_COM_UNDERLINE. Ninguém fala assim.
GRUPO_NOME = {
    "CUSTO_SERVICOS_PRESTADOS": "Custo dos serviços",
    "DESPESAS_ADMINISTRATIVAS": "Administrativas",
    "DESPESAS_OPERACIONAIS_NIVEL_2": "Operacionais",
    "IMPOSTOS_SOBRE_VENDAS": "Impostos sobre vendas",
    "DESPESAS_COMERCIAIS": "Comerciais",
    "COMISSOES_SOBRE_VENDAS": "Comissões",
    "OUTRAS_DESPESAS_NAO_OPERACIONAIS": "Não operacionais",
    "INVESTIMENTOS_IMOBILIZADO": "Investimentos",
    "DESPESSAS_FINANCEIRAS": "Financeiras",          # o erro de grafia é deles
    "EMPRESTIMOS_DIVIDAS": "Empréstimos e dívidas",
    "DESCONTOS_INCONDICIONAIS": "Descontos concedidos",
    "RECEITA_VENDA_PRODUTOS_SERVICOS": "Receita de serviços",
    "RECEITAS_RENDIMENTOS_FINANCEIROS": "Rendimentos financeiros",
    "OUTRAS_RECEITAS_NAO_OPERACIONAIS": "Outras receitas",
    "RECEITA_FRETES_ENTREGAS": "Fretes recebidos",
    "SEM_GRUPO": "Sem grupo definido",
}


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


def _paginar(caminho: str, **params) -> list:
    tudo, pagina = [], 1
    while True:
        try:
            r = get(caminho, pagina=pagina, tamanho_pagina=100, **params)
        except urllib.error.HTTPError as e:
            print(f"      ERRO {e.code} — trecho pulado")
            return tudo
        itens = r.get("itens", []) if isinstance(r, dict) else []
        tudo += itens
        if len(itens) < 100:
            return tudo
        pagina += 1
        if pagina > 80:
            print("      AVISO: parei na página 80 — o trecho pode estar truncado.")
            return tudo


def puxar_competencia(caminho: str, de: str, ate: str) -> list:
    """Fatia mês a mês por competência. A busca aceita intervalo livre, mas
    fatiar deixa o progresso visível em vez de um silêncio de minutos."""
    tudo = []
    for d, t in meses(de, ate):
        p = _paginar(caminho, data_vencimento_de=VENC_ABERTO[0],
                     data_vencimento_ate=VENC_ABERTO[1],
                     data_competencia_de=d, data_competencia_ate=min(t, ate))
        tudo += p
        print(f"    {d[:7]}: {len(tudo)} acumulados")
    return tudo


def puxar_em_aberto(caminho: str, de: str, ate: str) -> list:
    """Tudo que vence no intervalo, sem olhar competência — a fila do caixa."""
    tudo = []
    for d, t in meses(de, ate):
        tudo += _paginar(caminho, data_vencimento_de=d, data_vencimento_ate=min(t, ate))
    return [i for i in tudo if float(i.get("total") or 0) - float(i.get("pago") or 0) > 0.005]


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


def compactar(itens, amb, cat, pes, grupo_de_cat, campo_pessoa, com_desc):
    """Cada lançamento vira uma lista curta e posicional:
       [ambiente, categoria, pessoa, vencimento, competência, total, pago, movimento]
    A descrição sai para uma lista paralela: é o campo mais pesado e só serve no
    detalhe. Índices em vez de nomes porque repetir "ENDOVASCULAR SP" 7 mil vezes
    custa mais que a página inteira."""
    vistos, linhas, descricoes = set(), [], []
    for i in itens:
        if i.get("id") in vistos:            # a fila e a competência se sobrepõem
            continue
        vistos.add(i.get("id"))
        c = (i.get("categorias") or [{}])[0]
        cc = (i.get("centros_de_custo") or [{}])[0]
        p = i.get(campo_pessoa) or {}
        ic = cat.idx(c.get("nome"))
        grupo_de_cat.setdefault(ic, c.get("nome"))
        linhas.append([
            amb.idx(cc.get("nome")), ic, pes.idx(p.get("nome")),
            (i.get("data_vencimento") or "")[:10],
            (i.get("data_competencia") or i.get("data_vencimento") or "")[:10],
            round(float(i.get("total") or 0), 2),
            round(float(i.get("pago") or 0), 2),
            1 if e_movimento(c.get("nome")) else 0,
        ])
        if com_desc:
            descricoes.append((i.get("descricao") or "")[:64])
    return linhas, descricoes


MARCA = "/*" + "CDATA" + "*/"      # partido para a marca não existir neste arquivo


def injetar(caminho: Path, dados: dict) -> None:
    """Troca o bloco de dados do portal.

    A busca é ancorada em `const D = <marca>` em vez de procurar a marca solta,
    e o arquivo tem de conter a marca EXATAMENTE duas vezes. As duas travas
    existem pelo mesmo motivo: numa versão anterior a marca também aparecia no
    comentário do topo do HTML, a busca casou do comentário até a abertura dos
    dados e apagou a página inteira no caminho — sem erro nenhum, porque o padrão
    tinha casado direitinho com o que foi pedido.
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
    # Dois anos para trás, não um. A Visão Geral abre nos últimos 12 meses, e
    # comparar essa janela com a de um ano antes precisa de 24 meses de base —
    # com só um ano, a tela teria de desistir da comparação justamente na tela
    # em que ela mais importa.
    ap.add_argument("--de", default=f"{hoje.year-2}-01-01",
                    help="início da competência (os dois anos anteriores entram para a comparação)")
    ap.add_argument("--ate", default=f"{hoje.year}-12-31")
    ap.add_argument("--simular", action="store_true")
    a = ap.parse_args()

    print("Categorias (para pegar o grupo de DRE de cada uma):")
    cats = _paginar("/v1/categorias")
    grupo_da_categoria = {c["nome"]: (c.get("entrada_dre") or "SEM_GRUPO") for c in cats}
    print(f"    {len(cats)} categorias")

    print("Contas a pagar (por competência):")
    pagar = puxar_competencia(PAGAR, a.de, a.ate)
    print("Contas a pagar em aberto (por vencimento, sem recorte de competência):")
    fila = puxar_em_aberto(PAGAR, f"{hoje.year-1}-01-01", f"{hoje.year+2}-12-31")
    print(f"    {len(fila)} em aberto")
    print("Contas a receber (por competência):")
    receber = puxar_competencia(RECEBER, a.de, a.ate)

    amb, cat, forn, cli = Tabela(), Tabela(), Tabela(), Tabela()
    nome_de_cat = {}
    lp, dp = compactar(pagar + fila, amb, cat, forn, nome_de_cat, "fornecedor", True)
    lr, _ = compactar(receber, amb, cat, cli, nome_de_cat, "cliente", False)

    # Grupo de cada categoria, na mesma ordem da tabela de categorias.
    grupos = Tabela()
    cat_grupo = [grupos.idx(GRUPO_NOME.get(
        grupo_da_categoria.get(nome_de_cat.get(i, ""), "SEM_GRUPO"),
        grupo_da_categoria.get(nome_de_cat.get(i, ""), "SEM_GRUPO")))
        for i in range(len(cat.nomes))]

    dados = {
        "gerado_em": datetime.now().strftime("%d/%m/%Y às %H:%M"),
        "de": a.de, "ate": a.ate,
        "amb": amb.nomes, "cat": cat.nomes, "grupo": grupos.nomes, "cat_grupo": cat_grupo,
        "forn": forn.nomes, "cli": cli.nomes,
        "pagar": lp, "pagar_desc": dp, "receber": lr,
    }

    def resultado(l, ano):
        return sum(x[5] for x in l if not x[7] and x[4][:4] == ano)
    for ano in sorted({x[4][:4] for x in lp if x[4]}):
        if ano < a.de[:4]:
            continue
        print(f"  {ano}: custo R$ {resultado(lp, ano):,.2f}   receita R$ {resultado(lr, ano):,.2f}"
              .replace(",", "@").replace(".", ",").replace("@", "."))
    print(f"  {len(lp)} contas a pagar · {len(lr)} a receber · {len(amb.nomes)} ambientes · "
          f"{len(cat.nomes)} categorias · {len(grupos.nomes)} grupos · {len(forn.nomes)} fornecedores")

    if a.simular:
        print("\n[simulação] nada gravado.")
        return 0
    injetar(PORTAL, dados)
    print(f"\nGRAVADO: {PORTAL.relative_to(REPO)}  "
          f"({PORTAL.stat().st_size/1024:,.0f} KB)".replace(",", "."))
    return 0


if __name__ == "__main__":
    sys.exit(main())
