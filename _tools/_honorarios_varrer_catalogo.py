# -*- coding: utf-8 -*-
"""
_honorarios_varrer_catalogo.py — marca como conferido tudo que nunca foi dúvida.

Por que existe: a aba Catálogo nasceu com os 204 procedimentos em "não conferido",
o que transformou consulta, exame de imagem e medicação injetável em tarefa de
alguém. Só existe uma dúvida de verdade neste catálogo, e ela é sempre a mesma:
**isto é cirurgia ou não é — e, se é, foi no hospital ou na clínica?** É a única
pergunta que muda o dinheiro, porque o rótulo de cirurgia tira a linha do
percentual fixo da categoria e joga na regra de lead, de 80% ou 90%.

O que fica DE FORA (segue não conferido, para decisão humana):
  1. rótulo de cirurgia com ticket médio baixo — cirurgia de verdade tem ticket
     alto; uma visita de R$ 104 dividida a 80% se denuncia sozinha;
  2. nome que promete cirurgia mas categoria de consultório, e o contrário:
     ticket de cirurgia dentro de "Procedimentos";
  3. os casos citados à mão em CASOS_ABERTOS.

Uso:
    python _tools/_honorarios_varrer_catalogo.py           # só mostra
    python _tools/_honorarios_varrer_catalogo.py --aplicar # grava
    python _tools/_honorarios_varrer_catalogo.py --desfazer # limpa a varredura

Desfazer só apaga o que ESTA varredura escreveu (reconhecido pela observação),
nunca uma conferência feita a mão na tela.
"""
from __future__ import annotations
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _honorarios_db as db

QUEM = "thiago.luiz@endovascularsp.com.br"
DATA = "2026-08-11"
SELO = "Varredura de 11/08/2026"
OBS = (SELO + ": categoria sem dúvida de cirurgia. Marcado em massa, por categoria, "
       "não linha a linha — a conferência linha a linha ficou só para os casos em "
       "que cabe dúvida de cirurgia/hospital/clínica.")

# Abaixo disto, um rótulo de cirurgia é suspeito: é ticket de consultório.
TETO_CIRURGIA = 1500.0
# Acima disto, um procedimento de consultório é suspeito: é ticket de cirurgia.
PISO_CONSULTORIO = 5000.0
# Categorias em que ticket alto não quer dizer cirurgia: Fotona tem pacote de
# R$ 6.500 e medicação tem frasco caro. Aqui o valor não levanta suspeita nenhuma.
TICKET_NAO_DIZ_NADA = ("Fotona", "Medicação injetável", "Produtos", "T-Sculptor",
                       "Laser (clínica)", "Laser (locação)")

# Nome que promete bisturi. Serve para achar o rótulo trocado nos dois sentidos.
PISTAS = ("cirurg", "endolaser", "endolift", "emboliz", "ablacao", "safena",
          "aneurisma", "angioplastia", "stent", "cateterismo", "arteriografia",
          "revasculariz", "trombolise", "filtro de veia cava", "fistula arteriovenosa")

# Dúvidas que os números sozinhos não pegam.
CASOS_ABERTOS = {
    "protocolo pernas de porcelana":
        "Nome de pacote estético dentro de Cirurgia - Clínica, ainda sem nenhum lançamento.",
    "morpheus":
        "O 'Morpheus' puro foi inativado no SVN e desdobrado em Clínica e Hospital, "
        "mas os lançamentos antigos continuam neste nome, como Cirurgia - Hospital.",
    "cirurgia de unha (1 canto)":
        "Nome diz cirurgia, categoria diz Procedimentos (60%).",
}

# Decididos pelo Thiago em 10/08/2026, na origem: ele criou os dois nomes no SVN,
# renomeou as OS antigas e inativou o genérico. Não são dúvida, são o conserto.
JA_DECIDIDOS = {
    "morpheus - clinica": "Criado no SVN em 10/08/2026 para separar do Morpheus genérico.",
    "morpheus - hospital": "Criado no SVN em 10/08/2026 para separar do Morpheus genérico.",
}


def norm(s) -> str:
    s = unicodedata.normalize("NFKD", str(s or ""))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return " ".join(s.lower().split())


def carregar():
    procs = db.buscar("honorarios_procedimentos")
    lanc = db.buscar("honorarios_lancamentos", select="procedimento,valor_recebido")
    uso = defaultdict(lambda: [0, 0.0])
    for l in lanc:
        u = uso[norm(l.get("procedimento"))]
        u[0] += 1
        u[1] += float(l.get("valor_recebido") or 0)
    return procs, uso


def separar(procs, uso):
    """Devolve (duvidas, tranquilos). `duvidas` traz o motivo, para a tela e para
    a conversa com o Dr. Igor."""
    duvidas, tranquilos = [], []
    for p in procs:
        cat = str(p.get("categoria") or "")
        nome = norm(p.get("procedimento"))
        n, total = uso.get(nome, [0, 0.0])
        media = total / n if n else 0.0
        eh_cir = cat.startswith("Cirurgia")
        pista = any(t in nome for t in PISTAS)

        motivo = None
        if nome in JA_DECIDIDOS:
            motivo = None
        elif nome in CASOS_ABERTOS:
            motivo = CASOS_ABERTOS[nome]
        elif eh_cir and n and media < TETO_CIRURGIA:
            motivo = (f"Rótulo de cirurgia com ticket médio de R$ {media:,.2f} "
                      f"em {n} lançamento(s) — ticket de consultório.")
        elif eh_cir and not n and not pista:
            motivo = "Rótulo de cirurgia, nome que não é de cirurgia e nenhum lançamento ainda."
        elif not eh_cir and media >= PISO_CONSULTORIO and cat not in TICKET_NAO_DIZ_NADA:
            motivo = (f"Fora de cirurgia, mas com ticket médio de R$ {media:,.2f} — "
                      "ticket de cirurgia.")

        (duvidas if motivo else tranquilos).append((p, n, media, motivo))
    duvidas.sort(key=lambda x: -x[2])
    return duvidas, tranquilos


def main():
    aplicar = "--aplicar" in sys.argv
    desfazer = "--desfazer" in sys.argv
    procs, uso = carregar()

    if desfazer:
        alvos = [p for p in procs if SELO in str(p.get("observacao") or "")]
        print(f"Vou limpar a marca da varredura em {len(alvos)} procedimento(s).")
        if not aplicar:
            print("Rode junto com --aplicar para valer.")
            return
        for p in alvos:
            db.atualizar("honorarios_procedimentos", p["id"],
                         {"revisado_em": None, "revisado_por": None, "observacao": None})
        print("Pronto, voltaram para não conferido.")
        return

    duvidas, tranquilos = separar(procs, uso)

    print(f"Catálogo: {len(procs)} procedimentos\n")
    print(f"== FICAM PARA DECIDIR ({len(duvidas)}) ==")
    for p, n, media, motivo in duvidas:
        print(f"  R$ {media:>10,.2f} | {n:>3} lanc | {p.get('procedimento')}  "
              f"[{p.get('categoria')}]\n      {motivo}")

    ja = [t for t in tranquilos if t[0].get("revisado_em")]
    novos = [t for t in tranquilos if not t[0].get("revisado_em")]
    print(f"\n== SEM DÚVIDA ({len(tranquilos)}) — {len(ja)} já marcados, "
          f"{len(novos)} a marcar agora ==")
    porcat = defaultdict(int)
    for p, *_ in novos:
        porcat[p.get("categoria")] += 1
    for c, n in sorted(porcat.items(), key=lambda x: -x[1]):
        print(f"  {n:>4}  {c}")

    if not aplicar:
        print("\n(nada foi gravado — rode com --aplicar)")
        return

    for p, *_ in novos:
        db.atualizar("honorarios_procedimentos", p["id"],
                     {"revisado_em": DATA, "revisado_por": QUEM, "observacao": OBS})
    print(f"\nGravado: {len(novos)} marcados como conferidos.")
    print(f"Continuam em aberto: {len(duvidas)}.")


if __name__ == "__main__":
    main()
