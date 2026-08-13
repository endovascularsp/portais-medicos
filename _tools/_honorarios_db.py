# -*- coding: utf-8 -*-
"""
_honorarios_db.py — leitura das tabelas de honorários no Supabase.

Credenciais em `Endovascular_Farmer\\.env` (SUPABASE_URL e SUPABASE_SERVICE_KEY),
fora do repositório. A chave NUNCA é impressa em log nem em mensagem de erro.

Usa a API REST (PostgREST), que funciona sem instalar driver de Postgres.
Pagina sozinha: o PostgREST devolve no máximo 1.000 linhas por requisição.
"""
from __future__ import annotations
import json
import os
import re
import urllib.parse
import urllib.request
from pathlib import Path

ENV = Path(r"C:\Users\thiag\Documents\Endovascular_Farmer\.env")
PAGINA = 1000


def _cred() -> tuple:
    # Fora desta máquina — GitHub Actions, por exemplo — não existe .env: as
    # credenciais chegam por variável de ambiente. O ambiente ganha do arquivo,
    # para que o mesmo script rode nos dois lugares sem edição.
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY")
    if url and key:
        return url.rstrip("/"), key

    if not ENV.exists():
        raise SystemExit(
            f"ABORTADO: {ENV} não encontrado e SUPABASE_URL/SUPABASE_SERVICE_KEY "
            "não estão no ambiente.")
    txt = ENV.read_text(encoding="utf-8", errors="replace")
    def pega(nome):
        m = re.search(rf"^\s*{nome}\s*=\s*(.+)$", txt, re.M)
        return m.group(1).strip().strip('"').strip("'") if m else None
    url, key = pega("SUPABASE_URL"), pega("SUPABASE_SERVICE_KEY")
    if not url or not key or key == "COLE_AQUI_A_CHAVE":
        raise SystemExit("ABORTADO: SUPABASE_URL ou SUPABASE_SERVICE_KEY ausente/não preenchida no .env")
    return url.rstrip("/"), key


def buscar(tabela: str, select: str = "*", filtros: dict | None = None,
           ordem: str | None = None, limite: int | None = None) -> list:
    """Lê uma tabela inteira, paginando. `filtros` no formato do PostgREST:
    {'periodo_id': 'eq.2026-07'}"""
    url, key = _cred()
    base = f"{url}/rest/v1/{tabela}"
    q = {"select": select}
    if filtros:
        q.update(filtros)
    if ordem:
        q["order"] = ordem
    out, inicio = [], 0
    while True:
        fim = inicio + PAGINA - 1
        if limite is not None:
            fim = min(fim, inicio + (limite - len(out)) - 1)
        req = urllib.request.Request(
            base + "?" + urllib.parse.urlencode(q, quote_via=urllib.parse.quote),
            headers={"apikey": key, "Authorization": f"Bearer {key}",
                     "Accept": "application/json", "Range-Unit": "items",
                     "Range": f"{inicio}-{fim}"})
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                lote = json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            corpo = e.read().decode("utf-8", "replace")[:400]
            # nunca ecoar a URL completa: ela não leva a chave, mas o corpo pode citar cabeçalhos
            raise SystemExit(f"ABORTADO: HTTP {e.code} ao ler '{tabela}'. Resposta: {corpo}")
        out.extend(lote)
        if len(lote) < PAGINA or (limite is not None and len(out) >= limite):
            return out
        inicio += PAGINA


def atualizar(tabela: str, registro_id: str, campos: dict) -> dict:
    """PATCH de UM registro, sempre por id. Nunca aceita filtro aberto —
    escrita com a service_role ignora RLS, então o alvo tem que ser explícito."""
    url, key = _cred()
    dados = json.dumps(campos).encode("utf-8")
    req = urllib.request.Request(
        f"{url}/rest/v1/{tabela}?id=eq.{urllib.parse.quote(str(registro_id))}",
        data=dados, method="PATCH",
        headers={"apikey": key, "Authorization": f"Bearer {key}",
                 "Content-Type": "application/json", "Prefer": "return=representation"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            volta = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise SystemExit(f"ABORTADO: HTTP {e.code} ao atualizar '{tabela}': "
                         f"{e.read().decode('utf-8', 'replace')[:300]}")
    if len(volta) != 1:
        raise SystemExit(f"ABORTADO: o PATCH afetou {len(volta)} registros, esperava 1.")
    return volta[0]


def inserir(tabela: str, registro: dict) -> dict:
    """INSERT de UM registro. Devolve o que ficou gravado.
    Escrita com a service_role ignora RLS — por isso um de cada vez, e o chamador
    tem que ter conferido antes que o registro ainda não existe."""
    url, key = _cred()
    req = urllib.request.Request(
        f"{url}/rest/v1/{tabela}",
        data=json.dumps(registro).encode("utf-8"), method="POST",
        headers={"apikey": key, "Authorization": f"Bearer {key}",
                 "Content-Type": "application/json", "Prefer": "return=representation"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            volta = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise SystemExit(f"ABORTADO: HTTP {e.code} ao inserir em '{tabela}': "
                         f"{e.read().decode('utf-8', 'replace')[:300]}")
    if len(volta) != 1:
        raise SystemExit(f"ABORTADO: o INSERT criou {len(volta)} registros, esperava 1.")
    return volta[0]


def remover(tabela: str, registro_id: str) -> dict:
    """DELETE de UM registro, sempre por id, e devolve o que foi apagado.

    Nunca aceita filtro aberto: com a service_role o RLS é ignorado, e um
    `DELETE` com filtro errado apagaria o período inteiro sem avisar. O
    chamador tem que ter mostrado antes exatamente o que sai.
    """
    url, key = _cred()
    req = urllib.request.Request(
        f"{url}/rest/v1/{tabela}?id=eq.{urllib.parse.quote(str(registro_id))}",
        method="DELETE",
        headers={"apikey": key, "Authorization": f"Bearer {key}",
                 "Prefer": "return=representation"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            volta = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise SystemExit(f"ABORTADO: HTTP {e.code} ao remover de '{tabela}': "
                         f"{e.read().decode('utf-8', 'replace')[:300]}")
    if len(volta) != 1:
        raise SystemExit(f"ABORTADO: o DELETE afetou {len(volta)} registros, esperava 1.")
    return volta[0]


def inserir_lote(tabela: str, registros: list) -> int:
    """INSERT em lote, sem upsert — falha se alguma linha já existir.

    É o que carrega o fechamento sem SQL colado à mão. Falhar no conflito é
    proposital: se a linha já existe, alguém tem que olhar antes, não deixar o
    banco decidir sozinho o que fazer com dinheiro.
    """
    if not registros:
        return 0
    url, key = _cred()
    req = urllib.request.Request(
        f"{url}/rest/v1/{tabela}",
        data=json.dumps(registros, ensure_ascii=False, default=str).encode("utf-8"),
        method="POST",
        headers={"apikey": key, "Authorization": f"Bearer {key}",
                 "Content-Type": "application/json",
                 "Prefer": "return=representation"})
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            volta = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise SystemExit(f"ABORTADO: HTTP {e.code} ao inserir em '{tabela}': "
                         f"{e.read().decode('utf-8', 'replace')[:400]}")
    if len(volta) != len(registros):
        raise SystemExit(f"ABORTADO: o INSERT gravou {len(volta)} de {len(registros)}.")
    return len(volta)


def upsert(tabela: str, registros: list, conflito: str) -> int:
    """INSERT ... ON CONFLICT DO UPDATE, em lote.

    Diferente de `inserir`, aqui o lote é permitido — mas só para tabelas de
    CATÁLOGO (procedimento -> categoria), nunca para lançamento de dinheiro.
    O chamador informa a coluna de conflito, que precisa ter índice único.

    Devolve quantos registros voltaram gravados.
    """
    if not registros:
        return 0
    if tabela not in ("honorarios_procedimentos",):
        raise SystemExit(f"ABORTADO: upsert em lote não é permitido em '{tabela}'.")
    url, key = _cred()
    req = urllib.request.Request(
        f"{url}/rest/v1/{tabela}?on_conflict={urllib.parse.quote(conflito)}",
        data=json.dumps(registros, ensure_ascii=False).encode("utf-8"), method="POST",
        headers={"apikey": key, "Authorization": f"Bearer {key}",
                 "Content-Type": "application/json",
                 "Prefer": "resolution=merge-duplicates,return=representation"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            volta = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise SystemExit(f"ABORTADO: HTTP {e.code} no upsert em '{tabela}': "
                         f"{e.read().decode('utf-8', 'replace')[:300]}")
    if len(volta) != len(registros):
        raise SystemExit(f"ABORTADO: o upsert devolveu {len(volta)} de {len(registros)}.")
    return len(volta)


def testar() -> None:
    url, _ = _cred()
    print(f"Projeto: {url}")
    print("Chave ..: lida do .env (não exibida)\n")
    per = buscar("honorarios_periodos", "periodo_id,label,status,congelado", ordem="periodo_id")
    print(f"{'período':10s} {'label':16s} {'status':11s} congelado")
    for p in per:
        print(f"  {p['periodo_id']:8s} {p['label']:16s} {p['status']:11s} {p['congelado']}")

    linhas = buscar("honorarios_lancamentos",
                    "periodo_id,valor_recebido,repasse_profissional,repasse_indicador,repasse_clinica")
    print(f"\nLançamentos lidos: {len(linhas)}")
    agg = {}
    for l in linhas:
        a = agg.setdefault(l["periodo_id"], [0, 0.0, 0.0])
        a[0] += 1
        a[1] += float(l["valor_recebido"] or 0)
        a[2] += float(l["repasse_profissional"] or 0)
    print(f"\n{'período':10s} {'linhas':>8s} {'recebido':>16s} {'repasse':>16s}")
    for pid in sorted(agg):
        n, rec, rep = agg[pid]
        print(f"  {pid:8s} {n:8d} {rec:16,.2f} {rep:16,.2f}")
    tn = sum(a[0] for a in agg.values())
    tr = sum(a[1] for a in agg.values())
    tp = sum(a[2] for a in agg.values())
    print(f"  {'TOTAL':8s} {tn:8d} {tr:16,.2f} {tp:16,.2f}")

    for t in ("honorarios_regras", "honorarios_procedimentos", "honorarios_excecoes"):
        print(f"\n{t}: {len(buscar(t, 'id'))} registros")


if __name__ == "__main__":
    testar()
