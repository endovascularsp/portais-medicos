# -*- coding: utf-8 -*-
"""
_honorarios_decidir_morpheus.py — grava a decisão do Morpheus por OS.

Decisão do Thiago em 11/08/2026, para os lançamentos que JÁ existem com o nome
genérico "Morpheus":

    todas as OS do Dr. Igor    → Cirurgia - Hospital   (foram feitas no hospital)
    todas as OS da Dra. Chris  → Cirurgia - Clínica    (foram feitas na clínica)

Não é regra deduzida do conteúdo da OS — é o que aconteceu, dito por quem sabe.
Daqui para frente o problema não se repete: o "Morpheus" puro foi inativado no
SVN e desdobrado em "Morpheus - Clínica" e "Morpheus - Hospital", então o nome
já chega decidido.

As decisões vão para `honorarios_categoria_os`, que é independente de período:
a mesma OS parcelada reaparece em vários meses e a decisão vale para todos.

O que muda em dinheiro: só as 3 linhas da Dra. Christiane. "Cirurgia - Clínica"
é sempre 80/20, e elas saíram a 90% pela regra de lead — Junho −R$ 1.392,50 e
Julho −R$ 192,50. As 60 do Dr. Igor já estão como Cirurgia - Hospital: a
gravação não mexe em número nenhum, só registra a decisão e tira o Morpheus da
fila de dúvidas.

ESTE SCRIPT NÃO RECALCULA NADA. Junho e Julho são refeitos depois, de uma vez
só, quando as outras decisões do catálogo estiverem fechadas.

Uso:
    python _tools/_honorarios_decidir_morpheus.py            # mostra
    python _tools/_honorarios_decidir_morpheus.py --aplicar  # grava
"""
from __future__ import annotations
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _honorarios_db as db

# O console do Windows abre em cp1252 e engasga em "→" e nos acentos.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

QUEM = "thiago.luiz@endovascularsp.com.br"
ALVO = "morpheus"

REGRA = {
    "Igor Rafael Sincos":              ("Cirurgia - Hospital",
                                        "Feita no hospital (Dr. Igor). Decidido pelo Thiago em 11/08/2026."),
    "Christiane Sayuri Lopes Inoue":   ("Cirurgia - Clínica",
                                        "Feita na clínica (Dra. Christiane, Oxy Recovery). "
                                        "Decidido pelo Thiago em 11/08/2026."),
}


def norm(s) -> str:
    s = unicodedata.normalize("NFKD", str(s or ""))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return " ".join(s.lower().split())


def main():
    aplicar = "--aplicar" in sys.argv

    lanc = [x for x in db.buscar("honorarios_lancamentos")
            if norm(x.get("procedimento")) == ALVO]
    ja = {(r["os_numero"], r["chave"]): r for r in db.buscar("honorarios_categoria_os")}

    # Uma decisão por OS, não por lançamento: a OS parcelada volta todo mês.
    por_os = {}
    for x in lanc:
        os_num = str(x.get("os_numero") or "").strip()
        prof = str(x.get("profissional") or "")
        if not os_num or prof not in REGRA:
            print(f"  IGNORADO: OS {os_num!r}, profissional {prof!r} — fora da regra")
            continue
        d = por_os.setdefault(os_num, {"prof": prof, "pac": x.get("paciente"),
                                       "proc": x.get("procedimento"), "n": 0,
                                       "cat_hoje": x.get("categoria")})
        d["n"] += 1

    muda = igual = 0
    for os_num, d in sorted(por_os.items()):
        cat, motivo = REGRA[d["prof"]]
        marca = "=" if cat == d["cat_hoje"] else "MUDA"
        if marca == "MUDA":
            muda += 1
        else:
            igual += 1
        existe = " (já gravada)" if (os_num, ALVO) in ja else ""
        print(f"  {marca:<4} OS {os_num} | {d['n']:>2} lanç | {d['prof'][:28]:<28} | "
              f"{d['cat_hoje']} → {cat}{existe}")

    print(f"\n{len(por_os)} OS: {igual} confirmam a categoria atual, {muda} mudam.")

    if not aplicar:
        print("(nada gravado — rode com --aplicar)")
        return

    gravadas = 0
    for os_num, d in sorted(por_os.items()):
        cat, motivo = REGRA[d["prof"]]
        registro = {
            "os_numero": os_num, "chave": ALVO, "procedimento": d["proc"],
            "categoria": cat, "motivo": motivo, "paciente": d["pac"],
            "profissional": d["prof"], "decidido_por": QUEM,
        }
        antiga = ja.get((os_num, ALVO))
        if antiga:
            db.atualizar("honorarios_categoria_os", antiga["id"],
                         {k: v for k, v in registro.items() if k not in ("os_numero", "chave")})
        else:
            db.inserir("honorarios_categoria_os", registro)
        gravadas += 1

    # Com a decisão registrada, o Morpheus sai da fila de dúvidas do catálogo.
    for p in db.buscar("honorarios_procedimentos"):
        if norm(p.get("procedimento")) == ALVO and not p.get("revisado_em"):
            db.atualizar("honorarios_procedimentos", p["id"], {
                "revisado_em": "2026-08-11", "revisado_por": QUEM,
                "observacao": ("Resolvido por OS em 11/08/2026: as do Dr. Igor foram no "
                               "hospital, as da Dra. Christiane na clínica. O nome genérico "
                               "foi inativado no SVN e desdobrado em Morpheus - Clínica e "
                               "Morpheus - Hospital."),
            })

    print(f"Gravadas {gravadas} decisões de OS. Morpheus saiu da fila de dúvidas.")
    print("Junho e Julho ainda precisam ser refeitos — este script não recalcula.")


if __name__ == "__main__":
    main()
