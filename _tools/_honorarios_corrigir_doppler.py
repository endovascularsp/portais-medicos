# -*- coding: utf-8 -*-
"""
_honorarios_corrigir_doppler.py — "Cirurgia - Doppler colorido intra-operatório"
volta a ser o que sempre foi: exame de imagem.

O procedimento existia com dois nomes no SVN — `Doppler colorido intra-operatório`
(Exames de imagem, 60%, 7 lançamentos) e `Cirurgia - Doppler colorido
intra-operatório` (Cirurgia - Hospital, 2 lançamentos). É o mesmo exame; o que
mudou foi qual nome a pessoa escolheu na hora de lançar. As duas OS "de cirurgia"
têm consulta de consultório, curativo e escleroterapia na mesma OS, igual às
outras sete.

Decisão do Thiago em 11/08/2026: **o erro é nosso, não da profissional.** A
categoria é corrigida para a base ficar coerente e para nenhum lançamento novo
sair como cirurgia, mas **nada de dinheiro é recalculado** — a Dra. Carolina
Mardegan recebeu a 85% em Março e Maio e assim fica. Por isso as duas linhas
guardam uma observação explicando por que uma linha de "Exames de imagem" está
com percentual de cirurgia: não é inconsistência, é decisão registrada.

O que este script NÃO faz: não mexe em valor, percentual, repasse, imposto nem
no congelamento dos períodos, e não republica portal nenhum.

Uso:
    python _tools/_honorarios_corrigir_doppler.py            # mostra
    python _tools/_honorarios_corrigir_doppler.py --aplicar  # grava
"""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _honorarios_db as db

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

NOME = "Cirurgia - Doppler colorido intra-operatório"
NOVA = "Exames de imagem"
QUEM = "thiago.luiz@endovascularsp.com.br"

OBS_LANC = ("Categoria corrigida em 11/08/2026: era exame de imagem, não cirurgia — "
            "foi lançado no SVN com o nome errado, que tinha o prefixo 'Cirurgia -'. "
            "O valor NÃO foi recalculado por decisão do Thiago: o erro é de cadastro "
            "nosso e não pode impactar o fechamento da profissional. Por isso esta "
            "linha aparece como exame mas com o percentual de cirurgia que foi pago.")

OBS_CAT = ("Corrigido em 11/08/2026: é exame de imagem, não cirurgia. O nome com o "
           "prefixo 'Cirurgia -' é duplicata do 'Doppler colorido intra-operatório' "
           "e deve ser inativado no SVN. Os 2 lançamentos antigos ficaram com o valor "
           "pago, sem recálculo.")


def main():
    aplicar = "--aplicar" in sys.argv

    lanc = [x for x in db.buscar("honorarios_lancamentos")
            if str(x.get("procedimento") or "") == NOME]
    cat = [x for x in db.buscar("honorarios_procedimentos")
           if str(x.get("procedimento") or "") == NOME]

    print(f"Catálogo: {len(cat)} entrada(s) | Lançamentos: {len(lanc)}\n")
    for x in lanc:
        print(f"  OS {x.get('os_numero')} | {x.get('periodo_id')} | {x.get('profissional')}")
        print(f"     categoria {x.get('categoria')} -> {NOVA}")
        print(f"     valor recebido {x.get('valor_recebido')} | pct {x.get('pct_aplicado')} | "
              f"repasse {x.get('repasse_profissional')}  (NÃO MUDAM)")
    for x in cat:
        print(f"\n  catálogo: {x.get('categoria')} -> {NOVA}")

    if not aplicar:
        print("\n(nada gravado — rode com --aplicar)")
        return

    for x in lanc:
        db.atualizar("honorarios_lancamentos", x["id"], {
            "categoria": NOVA,
            "observacao": OBS_LANC,
            "revisado_em": "2026-08-11",
            "revisado_por": QUEM,
        })
    for x in cat:
        db.atualizar("honorarios_procedimentos", x["id"], {
            "categoria": NOVA,
            "categoria_anterior": x.get("categoria"),
            "revisado_em": "2026-08-11",
            "revisado_por": QUEM,
            "observacao": OBS_CAT,
        })
    print(f"\nGravado: {len(lanc)} lançamento(s) e {len(cat)} entrada(s) de catálogo.")
    print("Nenhum valor foi recalculado. Nenhum portal foi republicado.")


if __name__ == "__main__":
    main()
