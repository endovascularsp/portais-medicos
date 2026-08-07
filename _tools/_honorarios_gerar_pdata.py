# -*- coding: utf-8 -*-
"""
_honorarios_gerar_pdata.py — monta o PDATA de um período a partir do Supabase.

Fase 3A: substitui a leitura do Excel por leitura do banco. A estrutura do JSON é
exatamente a que os portais já esperam (mesmos nomes de campo do gerador antigo),
MAIS quatro campos novos por atendimento, que existem para a melhoria futura do
botão "como se chega a este valor" no portal de Recebimento:

    Regra aplicada · % Aplicado · ISS (18%) · Taxa comercial (2%)

Incluí-los agora não custa nada; incluir depois exigiria refazer o gerador e
republicar os 20 portais.

NÃO publica nada. Só monta o objeto e, com --validar, compara com o que já está
no ar para provar que o gerador reproduz fielmente o que o Excel produzia.

Uso:
    python _tools/_honorarios_gerar_pdata.py --periodo 2026-06 --validar
    python _tools/_honorarios_gerar_pdata.py --periodo 2026-07 --salvar
"""
from __future__ import annotations
import argparse
import json
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _honorarios_db as DB  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
RECEBIMENTO = REPO / "recebimento.html"

MESES = {"01": "Janeiro", "02": "Fevereiro", "03": "Março", "04": "Abril",
         "05": "Maio", "06": "Junho", "07": "Julho", "08": "Agosto",
         "09": "Setembro", "10": "Outubro", "11": "Novembro", "12": "Dezembro"}

# Quem NÃO tem portal. Diferente de quem não gera repasse: a base registra todo
# lançamento, mas o portal é do corpo clínico. Confere com o que o gerador antigo
# excluía — por isso Junho publicou 25 chaves e o banco tem 28.
# A Juliana SAIU desta lista em 07/08/2026. Ela executa e gera receita de
# verdade; o que ela não tem é repasse (é da casa, recebe salário — ver
# R.SEM_REPASSE_PROPRIO). Mantê-la aqui escondia R$ 58.164,76 de receita do
# painel só de Julho. Agora aparece com repasse zero e o líquido inteiro como
# receita da clínica — que é o fato.
SEM_PORTAL = {
    "paulo laredo", "paulo laredo pinto",
    "alvaro", "agendamento cirurgico e visita hospitalar", "enfermagem", "sala spa",
    "oxy recovery", "endovascular sp",
}


def chave(s) -> str:
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode()
    return " ".join(s.lower().split())


def slugify(nome: str) -> str:
    return unicodedata.normalize("NFC", str(nome)).replace(" ", "_")


def r2(v) -> float:
    try:
        return round(float(v or 0), 2)
    except (TypeError, ValueError):
        return 0.0


def data_br(v) -> str:
    """'2026-07-15' -> '15/07/2026'. O portal exibe assim."""
    if not v:
        return ""
    s = str(v)[:10]
    p = s.split("-")
    return f"{p[2]}/{p[1]}/{p[0]}" if len(p) == 3 else s


def origem_de(tabela) -> str:
    """Mesma regra do gerador antigo — é o que está publicado hoje."""
    return "Particular" if str(tabela or "").upper().strip() == "PARTICULAR" else "Plano de Saúde"


def txt(v) -> str:
    return "" if v is None else str(v).strip()


def empresa_portal(l: dict) -> str:
    """A empresa do PDATA: Endovascular SP vira 'Cirurgias' nas linhas de cirurgia."""
    if l["empresa"] == "Endovascular SP" and str(l["categoria"] or "").lower().startswith("cirurgia"):
        return "Cirurgias"
    return l["empresa"]


SUFIXO = {"Endovascular SP": "", "Cirurgias": "_Cir", "Oxy Recovery": "_Oxy"}


def montar_atendimento(l: dict) -> dict:
    liq = float(l["valor_liquido"] or 0)
    rp = float(l["repasse_profissional"] or 0)
    ri = float(l["repasse_indicador"] or 0)
    iss = float(l["imposto"] or 0)
    tcom = float(l["taxa_comercial"] or 0)
    return {
        "Nº OS": txt(l["os_numero"]),
        "Solicitante": txt(l["solicitante"]),
        "Indicação": txt(l["indicacao"]),
        "NF": txt(l["conta_pagamento"]),
        "Data emissão": data_br(l["data_emissao"]),
        "Data compensação": data_br(l["data_compensacao"]),
        "Paciente": txt(l["paciente"]),
        "Procedimento": txt(l["procedimento"]),
        "Categoria": txt(l["categoria"]),
        "Tabela": txt(l["tabela"]),
        "Origem": origem_de(l["tabela"]),
        "Tipo de pagamento": txt(l["tipo_pagamento"]),
        "Data agendamento": data_br(l["data_emissao"]),
        "Valor recebido": r2(l["valor_recebido"]),
        # o portal chama de "Imposto (18%)" a soma que foi efetivamente deduzida;
        # os dois componentes vão separados logo abaixo
        "Imposto (18%)": r2(iss + tcom),
        "Taxa cartão (3%)": r2(l["taxa_cartao"]),
        "Custo": r2(l["custo"]),
        "Valor Líquido": r2(liq),
        "% Repasse Prof": round(rp / liq, 4) if liq else 0.0,
        "Repasse Profissional (R$)": r2(rp),
        "% Repasse Indicador": round(ri / liq, 4) if liq else 0.0,
        "Repasse Indicador (R$)": r2(ri),
        "Repasse Clínica (R$)": r2(l["repasse_clinica"]),
        # --- novos: sustentam o botão de base de cálculo no portal ---
        "Regra aplicada": txt(l["regra_aplicada"]),
        "% Aplicado": round(float(l["pct_aplicado"]), 4) if l["pct_aplicado"] is not None else None,
        "ISS (18%)": r2(iss),
        "Taxa comercial (2%)": r2(tcom),
    }


def montar(periodo_id: str, com_periodo_id: bool = True) -> dict:
    mes = MESES[periodo_id.split("-")[1]]
    ano = int(periodo_id.split("-")[0])
    linhas = DB.buscar("honorarios_lancamentos", "*", {"periodo_id": f"eq.{periodo_id}"})

    grupos: dict = {}
    for l in linhas:
        if chave(l["profissional"]) in SEM_PORTAL:
            continue
        emp = empresa_portal(l)
        grupos.setdefault((l["profissional"], emp), []).append(l)

    profs = {}
    for (prof, emp), ls in grupos.items():
        soma = lambda c: r2(sum(float(x[c] or 0) for x in ls))  # noqa: E731
        resumo = {
            "Profissional": prof,
            "Valor recebido": soma("valor_recebido"),
            "Imposto (18%)": r2(sum(float(x["imposto"] or 0) + float(x["taxa_comercial"] or 0) for x in ls)),
            "Taxa cartão (3%)": soma("taxa_cartao"),
            "Custo": soma("custo"),
            "Valor Líquido": soma("valor_liquido"),
            "Repasse Profissional (R$)": soma("repasse_profissional"),
            "Repasse Clínica (R$)": soma("repasse_clinica"),
            "Repasse Indicador (R$)": soma("repasse_indicador"),
        }

        por_cat: dict = {}
        for x in ls:
            a = por_cat.setdefault(txt(x["categoria"]), [0.0, 0.0, 0.0])
            a[0] += float(x["valor_recebido"] or 0)
            a[1] += float(x["valor_liquido"] or 0)
            a[2] += float(x["repasse_profissional"] or 0)
        por_categoria = [{"Profissional": prof, "Categoria": c, "Valor recebido": r2(v[0]),
                          "Valor Líquido": r2(v[1]), "Repasse Profissional (R$)": r2(v[2])}
                         for c, v in sorted(por_cat.items())]

        por_pag: dict = {}
        for x in ls:
            t = txt(x["tipo_pagamento"]) or "Outros"
            por_pag[t] = por_pag.get(t, 0.0) + float(x["valor_recebido"] or 0)
        por_pagamento = [{"Profissional": prof, "Tipo de pagamento": t, "Valor recebido": r2(v)}
                         for t, v in sorted(por_pag.items())]

        por_tab: dict = {}
        for x in ls:
            t = txt(x["tabela"])
            if t:
                por_tab[t] = por_tab.get(t, 0.0) + float(x["valor_recebido"] or 0)
        por_tabela = [{"Profissional": prof, "Tabela": t, "Origem": origem_de(t), "Valor recebido": r2(v)}
                      for t, v in sorted(por_tab.items())]

        # Ordena pela data REAL (ISO), não pelo texto dd/mm/aaaa. O gerador antigo
        # ordenava pela string já formatada, o que põe 01/12 antes de 02/01.
        atendimentos = [montar_atendimento(x) for x in
                        sorted(ls, key=lambda x: (str(x["data_emissao"] or ""),
                                                  str(x["data_compensacao"] or ""),
                                                  str(x["os_numero"] or "")))]

        inner = {"profissional": prof, "empresa": emp, "mes": mes, "ano": ano,
                 "resumo": resumo, "por_categoria": por_categoria,
                 "por_pagamento": por_pagamento, "por_tabela": por_tabela,
                 "atendimentos": atendimentos}
        if com_periodo_id:
            inner["periodo_id"] = periodo_id
        profs[slugify(prof) + SUFIXO[emp]] = inner

    return {"label": f"{mes}/{ano}", "profs": profs}


# ---------------------------------------------------------------------------
# Validação contra o que já está publicado
# ---------------------------------------------------------------------------
def pdata_publicado(caminho: Path) -> dict:
    html = caminho.read_text(encoding="utf-8")
    i = html.find("/*PDATA*/")
    j = i + len("/*PDATA*/")
    while html[j] in " \n\r\t":
        j += 1
    d, k, ins, esc = 0, j, False, False
    while k < len(html):
        c = html[k]
        if ins:
            if esc: esc = False
            elif c == "\\": esc = True
            elif c == '"': ins = False
        else:
            if c == '"': ins = True
            elif c == "{": d += 1
            elif c == "}":
                d -= 1
                if d == 0: break
        k += 1
    return json.loads(html[j:k + 1])


CAMPOS_NOVOS = {"Regra aplicada", "% Aplicado", "ISS (18%)", "Taxa comercial (2%)"}


def validar(periodo_id: str) -> int:
    gerado = montar(periodo_id)
    pub = pdata_publicado(RECEBIMENTO).get(periodo_id)
    if not pub:
        print(f"ABORTADO: {periodo_id} não está publicado no recebimento.html")
        return 1

    g, p = gerado["profs"], pub["profs"]
    print(f"=== VALIDAÇÃO {periodo_id} — gerado do banco x publicado no portal ===")
    print(f"  label:  gerado {gerado['label']!r} · publicado {pub['label']!r}"
          f"  {'OK' if gerado['label'] == pub['label'] else '<<< DIFERE'}")
    print(f"  chaves: gerado {len(g)} · publicado {len(p)}")
    for s in sorted(set(g) - set(p)):
        print(f"     só no gerado ...: {s}")
    for s in sorted(set(p) - set(g)):
        print(f"     só no publicado : {s}")

    def difere(va, vb):
        if isinstance(vb, (int, float)) and isinstance(va, (int, float)):
            return abs(va - vb) > 0.015
        return str(va) != str(vb)

    relatorio, campos_at = {}, {}
    for slug in sorted(set(g) & set(p)):
        a, b = g[slug], p[slug]
        r = {"cabecalho": [], "resumo": {}, "listas": [], "atend": 0}
        for campo in ("profissional", "empresa", "mes", "ano", "periodo_id"):
            if a.get(campo) != b.get(campo):
                r["cabecalho"].append(f"{campo}: {a.get(campo)!r} x {b.get(campo)!r}")
        for campo, vb in b["resumo"].items():
            va = a["resumo"].get(campo)
            if difere(va, vb):
                r["resumo"][campo] = (va, vb)
        for lista in ("por_categoria", "por_pagamento", "por_tabela", "atendimentos"):
            if len(a[lista]) != len(b[lista]):
                r["listas"].append(f"{lista}: {len(a[lista])} x {len(b[lista])}")
        # Compara SEM depender da ordem: o gerador novo ordena cronologicamente e o
        # antigo ordenava pelo texto da data. Ordem diferente não é erro de valor.
        def canon(it):
            return (str(it.get("Nº OS")), str(it.get("Data compensação")),
                    str(it.get("Procedimento")), f"{it.get('Valor recebido', 0):.2f}",
                    str(it.get("Paciente")))
        if len(a["atendimentos"]) == len(b["atendimentos"]):
            for ia, ib in zip(sorted(a["atendimentos"], key=canon),
                              sorted(b["atendimentos"], key=canon)):
                for campo, vb in ib.items():
                    if difere(ia.get(campo), vb):
                        r["atend"] += 1
                        campos_at[campo] = campos_at.get(campo, 0) + 1
        if any([r["cabecalho"], r["resumo"], r["listas"], r["atend"]]):
            relatorio[slug] = r

    if not relatorio:
        print("\n  IDÊNTICO. O gerador reproduz exatamente o que está publicado.")
    else:
        print(f"\n  {len(relatorio)} de {len(set(g) & set(p))} chaves com diferença:\n")
        for slug, r in relatorio.items():
            print(f"  • {slug}")
            for c in r["cabecalho"]:
                print(f"      cabeçalho: {c}")
            for campo, (va, vb) in r["resumo"].items():
                if isinstance(va, (int, float)):
                    print(f"      resumo · {campo}: {va:,.2f} (banco) x {vb:,.2f} (portal)"
                          f"   dif {va - vb:+,.2f}")
                else:
                    print(f"      resumo · {campo}: {va!r} x {vb!r}")
            for c in r["listas"]:
                print(f"      contagem: {c}")
            if r["atend"]:
                print(f"      {r['atend']} campos de atendimento divergentes")
        print(f"\n  Campos de atendimento que divergiram: {campos_at}")

    exemplo = next(iter(g.values()))["atendimentos"][0]
    print("\n  Campos NOVOS incluídos por atendimento (para o botão de base de cálculo):")
    for c in ("Regra aplicada", "% Aplicado", "ISS (18%)", "Taxa comercial (2%)"):
        print(f"     {c}: {exemplo.get(c)!r}")
    return 1 if relatorio else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--periodo", required=True)
    ap.add_argument("--validar", action="store_true")
    ap.add_argument("--salvar", action="store_true")
    a = ap.parse_args()
    if a.validar:
        sys.exit(validar(a.periodo))
    obj = montar(a.periodo)
    print(f"{a.periodo}: {len(obj['profs'])} chaves · "
          f"{sum(len(v['atendimentos']) for v in obj['profs'].values())} atendimentos")
    for slug in sorted(obj["profs"]):
        v = obj["profs"][slug]
        print(f"  {slug:44s} {v['empresa']:16s} {len(v['atendimentos']):4d}ln  "
              f"R$ {v['resumo']['Repasse Profissional (R$)']:>12,.2f}")
    if a.salvar:
        destino = REPO / "db" / f"pdata_{a.periodo.replace('-', '_')}.json"
        destino.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"\nSalvo: {destino} ({destino.stat().st_size/1024:.0f} KB)")


if __name__ == "__main__":
    main()
