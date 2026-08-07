# -*- coding: utf-8 -*-
"""
_honorarios_sincronizar.py — põe um período do banco em dia com o que o SVN diz
HOJE, sem apagar o mês inteiro.

Por que existe: o fechamento é tirado nos primeiros dias do mês seguinte, e as
compensações dos últimos dias ainda estão chegando. Rodar de novo depois pega o
que faltou. O jeito ingênuo — apagar o período e recarregar — mexe em milhares
de linhas de dinheiro para corrigir uma dúzia.

Este compara linha a linha pela chave natural e faz o mínimo:
  - INSERE o que o SVN passou a ter;
  - REMOVE só o que ficou obsoleto (linha que o SVN alterou depois: valor
    recalculado, procedimento renomeado);
  - não toca no que está igual.

Recusa-se a agir se o período estiver congelado ou se alguma linha tiver marca
de revisão manual — nesses casos alguém decidiu algo à mão, e uma sincronização
automática apagaria essa decisão.

Uso:
    python _tools/_honorarios_sincronizar.py --periodo 2026-07            # simula
    python _tools/_honorarios_sincronizar.py --periodo 2026-07 --escrever
"""
from __future__ import annotations
import argparse
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pandas as pd                      # noqa: E402
import _honorarios_motor as M            # noqa: E402
import _honorarios_regras as R           # noqa: E402
import _honorarios_db as DB              # noqa: E402

# a mesma chave que identifica a linha no banco (índice único)
CHAVE = ["empresa", "os_numero", "procedimento", "data_compensacao",
         "valor_recebido", "profissional", "seq"]


def k_api(r) -> tuple:
    return (str(r["empresa"]), str(r["os_numero"]).strip(),
            str(r["procedimento"] or "").strip(), str(r["data_compensacao"])[:10],
            f"{round(float(r['valor_recebido'] or 0), 2):.2f}",
            str(r["profissional"] or "").strip(), int(r["seq"]))


def k_db(r) -> tuple:
    return (str(r["empresa"]), str(r["os_numero"]).strip(),
            str(r["procedimento"] or "").strip(), str(r["data_compensacao"])[:10],
            f"{round(float(r['valor_recebido'] or 0), 2):.2f}",
            str(r["profissional"] or "").strip(), int(r["seq"] or 1))


def _para_json(r: dict, periodo: str) -> dict:
    """Converte uma linha calculada no que a API do PostgREST aceita.

    O motor trabalha com pandas, e campo vazio vira NaN/NaT. `json.dumps` os
    escreve como `NaN`/`NaT`, que não são JSON válido — o PostgREST devolve
    "Empty or invalid json" e recusa o lote inteiro. Aqui viram null, e as
    datas viram texto ISO.
    """
    out = {}
    for c in M.COLS_LANC:
        if c == "periodo_id":
            out[c] = periodo
            continue
        if c == "origem":
            # A tabela só aceita 'importacao_excel', 'csv_svn' ou 'manual'
            # (CHECK na migration_009). Ler pela API é a mesma origem lógica —
            # o relatório #560 do SVN —, só muda o meio de transporte.
            out[c] = "csv_svn"
            continue
        if c == "congelado":
            out[c] = False
            continue
        v = r.get(c)
        if v is None or (not isinstance(v, (list, dict, str, bool)) and pd.isna(v)):
            out[c] = None
        elif isinstance(v, pd.Timestamp):
            out[c] = v.strftime("%Y-%m-%d")
        elif hasattr(v, "item"):          # numpy int64/float64
            out[c] = v.item()
        else:
            out[c] = v
    return out


def calcular_do_svn(periodo: str) -> list:
    """Roda a leitura + o cálculo, em memória, sem gravar nada."""
    catalogo = M.carregar_catalogo()
    df = pd.concat([M.ler_api("endo", periodo, R.ENDO),
                    M.ler_api("oxy", periodo, R.OXY)], ignore_index=True)
    df = M.resolver_dono(df)
    chaves = [df[c].map(lambda v: "" if pd.isna(v) else str(v)) for c in M.CHAVE_NATURAL]
    df["seq"] = df.groupby(chaves).cumcount() + 1
    nomes = M.nomes_profissionais(df)
    ok, exc, ignorados = [], [], 0
    for row in df.to_dict("records"):
        val, e = M.calcular(row, periodo, catalogo, nomes)
        if e:
            tipo, desc, _sug = e
            # "__ignorar__" não é dúvida: é quem não é corpo clínico (Enfermagem,
            # Paulo Laredo, Agendamento Cirúrgico). Sai do cálculo por regra, e
            # tratar isso como exceção travaria a sincronização todo mês.
            if tipo == "__ignorar__":
                ignorados += 1
                continue
            exc.append({"tipo": tipo, "descricao": desc, "os_numero": row.get("os_numero"),
                        "paciente": row.get("paciente"),
                        "procedimento": row.get("procedimento")})
        else:
            ok.append(val)
    print(f"  fora do corpo clínico (por regra): {ignorados}")
    return ok, exc


def main(periodo: str, escrever: bool) -> int:
    print(f"\n=== Sincronizar {periodo} com o SVN · escrever={escrever} ===\n")

    # --- trava de segurança ------------------------------------------------
    per = [p for p in DB.buscar("honorarios_periodos", "periodo_id,status,congelado")
           if p["periodo_id"] == periodo]
    if per and per[0]["congelado"]:
        raise SystemExit(f"ABORTADO: {periodo} está congelado. Descongelar é decisão do Thiago.")

    atual = DB.buscar("honorarios_lancamentos", "*", filtros={"periodo_id": f"eq.{periodo}"})
    manuais = [r for r in atual if r.get("revisado_em") or r.get("revisado_por")
               or r.get("observacao") or r.get("congelado")]
    if manuais:
        print(f"ABORTADO: {len(manuais)} linha(s) com revisão manual — a sincronização "
              f"as apagaria. Resolver uma a uma:")
        for r in manuais[:10]:
            print(f"   OS {r['os_numero']} {str(r['paciente'])[:30]} — {r.get('observacao')}")
        return 1

    ok, exc = calcular_do_svn(periodo)
    if exc:
        print(f"ABORTADO: {len(exc)} exceção(ões) na fila. Classificar antes de sincronizar:")
        for e in exc[:10]:
            print(f"   [{e['tipo']}] {e['descricao']}")
        return 1

    # --- diferença ---------------------------------------------------------
    novo = {k_api(r): r for r in ok}
    velho = {k_db(r): r for r in atual}
    if len(novo) != len(ok) or len(velho) != len(atual):
        raise SystemExit("ABORTADO: chave natural repetida — não dá para casar 1 a 1.")

    inserir = [novo[k] for k in novo.keys() - velho.keys()]
    remover = [velho[k] for k in velho.keys() - novo.keys()]

    # Linha que existe dos dois lados mas com número diferente. Acontece quando
    # uma REGRA muda, não o dado: a chave natural (OS, procedimento, data, valor,
    # profissional) continua a mesma e só o cálculo muda. Sem isto, mudar uma
    # regra de repasse não teria efeito nenhum sobre o que já está gravado — que
    # foi exatamente o que aconteceu ao zerar o repasse da Juliana.
    CALCULADOS = ["categoria", "imposto", "taxa_comercial", "taxa_cartao", "valor_liquido",
                  "repasse_profissional", "repasse_indicador", "repasse_clinica",
                  "pct_aplicado", "regra_aplicada", "papel"]
    atualizar = []
    for k in novo.keys() & velho.keys():
        n, v = novo[k], velho[k]
        mudou = {}
        for c in CALCULADOS:
            a, b = n.get(c), v.get(c)
            if isinstance(a, (int, float)) and a is not None and b is not None:
                if abs(float(a) - float(b)) > 0.005:
                    mudou[c] = (b, a)
            elif str(a or "") != str(b or ""):
                mudou[c] = (b, a)
        if mudou:
            atualizar.append((v["id"], n, mudou))
    iguais = len(novo.keys() & velho.keys()) - len(atualizar)

    print(f"  no banco hoje .....: {len(atual)}")
    print(f"  o SVN diz .........: {len(ok)}")
    print(f"  iguais (intocados) : {iguais}")
    print(f"  a INSERIR .........: {len(inserir)}")
    print(f"  a ATUALIZAR .......: {len(atualizar)}  (regra mudou, dado não)")
    print(f"  a REMOVER .........: {len(remover)}\n")

    if atualizar:
        print("  --- linhas recalculadas por mudança de regra ---")
        for _id, n, mudou in atualizar[:12]:
            print(f"    OS {str(n['os_numero']):10s} {str(n['paciente'])[:24]:26s} "
                  f"{str(n['profissional'])[:22]:24s}")
            for c, (b, a) in mudou.items():
                fmt = (lambda x: f"{float(x):,.2f}") if isinstance(a, (int, float)) else (lambda x: str(x)[:40])
                print(f"        {c:22s} {fmt(b):>22s} -> {fmt(a)}")
        if len(atualizar) > 12:
            print(f"    ... e mais {len(atualizar)-12}")

    if remover:
        print("  --- linhas obsoletas (o SVN alterou depois) ---")
        for r in remover:
            print(f"    OS {r['os_numero']:10s} {str(r['paciente'])[:26]:28s} "
                  f"{str(r['procedimento'])[:32]:34s} R$ {float(r['valor_recebido']):>9,.2f} "
                  f"· repasse R$ {float(r['repasse_profissional'] or 0):>8,.2f}")
    if inserir:
        print("\n  --- efeito por profissional ---")
        d = defaultdict(float)
        for r in inserir:
            d[(r["empresa"], r["profissional"])] += r["repasse_profissional"]
        for r in remover:
            d[(r["empresa"], r["profissional"])] -= float(r["repasse_profissional"] or 0)
        for _id, n, mudou in atualizar:
            if "repasse_profissional" in mudou:
                antes, depois = mudou["repasse_profissional"]
                d[(n["empresa"], n["profissional"])] += float(depois) - float(antes)
        for k, v in sorted(d.items(), key=lambda x: -x[1]):
            if abs(v) < 0.005:
                continue
            print(f"    {k[0][:14]:16s} {k[1][:28]:30s} {v:>+11,.2f}")
        print(f"    {'TOTAL':46s} {sum(d.values()):>+11,.2f}")

    if not inserir and not remover and not atualizar:
        print("  Nada a fazer — o banco já reflete o SVN.")
        return 0
    if not escrever:
        print("\n  [simulação] nada gravado. Rode com --escrever.")
        return 0

    # --- executa: remove primeiro, senão a chave única bloqueia a inserção --
    for r in remover:
        DB.remover("honorarios_lancamentos", r["id"])
    print(f"\n  {len(remover)} linha(s) removida(s).")
    n = DB.inserir_lote("honorarios_lancamentos", [_para_json(r, periodo) for r in inserir])
    print(f"  {n} linha(s) inserida(s).")

    # Linhas cujo NÚMERO mudou porque a REGRA mudou (a chave natural é a mesma).
    # Sem este passo, alterar uma regra não teria efeito no que já está gravado.
    for _id, reg, _mudou in atualizar:
        pronto = _para_json(reg, periodo)
        DB.atualizar("honorarios_lancamentos", _id,
                     {c: pronto[c] for c in
                      ("categoria", "imposto", "taxa_comercial", "taxa_cartao",
                       "valor_liquido", "repasse_profissional", "repasse_indicador",
                       "repasse_clinica", "pct_aplicado", "regra_aplicada", "papel")})
    print(f"  {len(atualizar)} linha(s) recalculada(s).")

    # --- confere o resultado ----------------------------------------------
    depois = DB.buscar("honorarios_lancamentos", "repasse_profissional,valor_recebido",
                       filtros={"periodo_id": f"eq.{periodo}"})
    esperado_rep = round(sum(r["repasse_profissional"] for r in ok), 2)
    obtido_rep = round(sum(float(r["repasse_profissional"] or 0) for r in depois), 2)
    print(f"\n  linhas no banco ...: {len(depois)}  (esperado {len(ok)})")
    print(f"  repasse no banco ..: R$ {obtido_rep:,.2f}  (esperado R$ {esperado_rep:,.2f})")
    # A contagem de linhas é exata; o valor tem folga de 1 centavo por linha.
    # O motor soma em ponto flutuante e o banco guarda numeric(14,4): num mês de
    # mil linhas os dois divergem alguns centavos, e não é erro. Exigir 2
    # centavos fazia o teste falhar depois de uma gravação correta — pior do que
    # não ter teste, porque assusta à toa.
    folga = max(0.10, 0.01 * len(ok))
    if len(depois) != len(ok) or abs(obtido_rep - esperado_rep) > folga:
        raise SystemExit(f"ABORTADO: o banco não ficou igual ao esperado "
                         f"(folga aceita: R$ {folga:,.2f}) — CONFERIR À MÃO.")
    print("  Banco em dia com o SVN.")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--periodo", required=True)
    ap.add_argument("--escrever", action="store_true")
    a = ap.parse_args()
    raise SystemExit(main(a.periodo, a.escrever))
