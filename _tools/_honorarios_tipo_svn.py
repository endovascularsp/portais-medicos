# -*- coding: utf-8 -*-
"""
_honorarios_tipo_svn.py — grava no catálogo como o Saudevianet classifica cada
procedimento, para servir de segunda opinião na tela de revisão.

POR QUE ISSO EXISTE
O catálogo diz a categoria (que decide o percentual) e veio inteiro da aba
"Apoio" do Excel, sem conferência. O SVN tem uma classificação própria, no campo
`tipo_procedimento`. Quando as duas discordam, é sinal de que alguém precisa
olhar.

O QUE ISSO NÃO É
Não é fonte da verdade, e o motor não usa este campo para calcular nada. O SVN
chama Morpheus de "PDT", chama "Varizes - ressecção de colaterais com anestesia
local" de "Procedimentos" e chama visita hospitalar de "Consulta". Erra nos dois
sentidos. Serve só para a tela dizer "olha, aqui os dois discordam".

Uso:
    python _tools/_honorarios_tipo_svn.py            # simula
    python _tools/_honorarios_tipo_svn.py --escrever
"""
from __future__ import annotations
import argparse
import json
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _honorarios_db as DB  # noqa: E402

CACHE = Path(r"C:\Users\thiag\Documents\Endovascular_Farmer\svn_560_cache")


def chave(s) -> str:
    """Mesma normalização do catálogo: sem acento, minúsculo, espaços colapsados."""
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode()
    return " ".join(s.lower().split())


def tipos_do_svn() -> dict:
    """chave do procedimento -> tipo mais frequente no SVN."""
    arqs = sorted(CACHE.glob("560_*_baix_dt_recebimento.json"))
    if not arqs:
        raise SystemExit(f"ABORTADO: nenhum cache do relatório 560 em {CACHE}")
    votos = defaultdict(Counter)
    for a in arqs:
        for r in json.loads(a.read_text(encoding="utf-8")):
            k = chave(r.get("proc_tx_nome"))
            t = str(r.get("tipo_procedimento") or "").strip()
            if k and t and t.lower() != "none":
                votos[k][t] += 1
    # Um procedimento pode aparecer com tipos diferentes entre meses. Vale o mais
    # frequente; a divergência interna não muda o que a tela precisa mostrar.
    return {k: c.most_common(1)[0][0] for k, c in votos.items()}


def main(escrever: bool) -> int:
    tipos = tipos_do_svn()
    catalogo = DB.buscar("honorarios_procedimentos", "id,chave,procedimento,categoria,tipo_svn")
    print(f"\n=== tipo_svn no catálogo · escrever={escrever} ===")
    print(f"    {len(tipos)} procedimento(s) com tipo no SVN · {len(catalogo)} no catálogo\n")

    mudar, discordam, sem_tipo = [], [], 0
    for p in catalogo:
        novo = tipos.get(p["chave"])
        if not novo:
            sem_tipo += 1
            continue
        if novo != p.get("tipo_svn"):
            mudar.append((p, novo))
        cir_nosso = str(p["categoria"]).startswith("Cirurgia")
        if cir_nosso != (novo == "Cirurgia"):
            discordam.append((p, novo))

    for p, novo in mudar:
        print(f"  {p['procedimento'][:52]:54s} tipo_svn: {str(p.get('tipo_svn')):14s} -> {novo}")
        if escrever:
            DB.atualizar("honorarios_procedimentos", p["id"], {"tipo_svn": novo})

    print(f"\n  {len(mudar)} atualizado(s) · {sem_tipo} sem tipo no SVN (não aparecem no cache)")

    if discordam:
        print(f"\n  === {len(discordam)} onde catálogo e SVN discordam sobre ser cirurgia ===")
        for p, novo in sorted(discordam, key=lambda x: x[0]["procedimento"]):
            print(f"    {p['procedimento'][:48]:50s} nós={p['categoria']:20s} SVN={novo}")
        print("\n  Estes é que aparecem em 'Precisa de atenção' na tela de Catálogo.")

    if not escrever:
        print("\n  [simulação] nada gravado. Rode com --escrever.")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--escrever", action="store_true")
    raise SystemExit(main(ap.parse_args().escrever))
