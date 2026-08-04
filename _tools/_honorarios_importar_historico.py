# -*- coding: utf-8 -*-
"""
_honorarios_importar_historico.py — Fase 1 da automação do fechamento.

Lê a Base Compensação do Excel de fechamento e gera o SQL de carga do histórico
Jan–Jun/2026 para `honorarios_lancamentos` (migration_009).

PRINCÍPIO: o histórico entra CONGELADO, com os valores exatamente como foram pagos.
Nada é recalculado aqui — o motor de repasse audita depois, sem reescrever.

O que o script deriva (não inventa valor, só organiza):
  - periodo_id            <- Mês + Ano
  - seq                   <- ordem dentro do grupo da chave natural (pacotes de sessões
                             e parcelas geram linhas idênticas; sem isso perderíamos 1.035)
  - imposto/taxa_comercial<- separa o ISS (18%) dos 2% de taxa comercial que em Junho
                             foram embutidos na coluna "Imposto (18%)" como se fossem 20%
  - nf_propria            <- NF no nome do profissional (ou "Externa") => Regra 3A
  - papel                 <- executor / indicador (Fotona e T-Sculptor na Oxy)
  - pct_aplicado          <- repasse / base, só para conferência

Uso:
    python _tools/_honorarios_importar_historico.py --dry-run
    python _tools/_honorarios_importar_historico.py
"""
from __future__ import annotations
import argparse
import unicodedata
from pathlib import Path

import pandas as pd

PLANILHA = r"G:\Drives compartilhados\Endovascular SP\2. Financeiro\4. Honorários médicos\Fechamento - Endovascular SP.xlsx"
REPO = Path(__file__).resolve().parent.parent
SAIDA_DIR = REPO / "db"
NOME = "seed_009_honorarios_historico"
LOTE = 500          # linhas por INSERT
POR_ARQUIVO = 1000  # linhas por arquivo — 2 MB de uma vez trava o SQL Editor do navegador

MES_MAP = {"Janeiro": "01", "Fevereiro": "02", "Março": "03",
           "Abril": "04", "Maio": "05", "Junho": "06",
           "Julho": "07", "Agosto": "08", "Setembro": "09",
           "Outubro": "10", "Novembro": "11", "Dezembro": "12"}

# Categorias que ganharam os 2% de taxa comercial (pedido do Dr. Igor, a partir de Junho).
# Medicação injetável não entra: o aviso chegou depois do fechamento de Junho.
CAT_TAXA_COMERCIAL = {
    "cirurgia - clinica", "cirurgia - hospital", "fotona",
    "laser (clinica)", "laser (locacao)", "procedimentos", "t-sculptor",
}

CHAVE_NATURAL = ["Empresa", "Nº OS", "Procedimento", "Data compensação",
                 "Valor recebido", "Profissional"]

NUM = ["Valor recebido", "Imposto (18%)", "Taxa cartão (3%)", "Custo",
       "Valor Líquido", "% Profissional", "% Indicador", "% Clínica"]


def nrm(v) -> str:
    s = unicodedata.normalize("NFKD", str(v or "")).encode("ascii", "ignore").decode()
    return " ".join(s.lower().split())


def sql_txt(v) -> str:
    """Literal de texto seguro. NaN/vazio viram NULL."""
    if v is None:
        return "NULL"
    try:
        if pd.isna(v):
            return "NULL"
    except (TypeError, ValueError):
        pass
    s = str(v).strip()
    if not s or s.lower() == "nan":
        return "NULL"
    return "'" + s.replace("'", "''") + "'"


def sql_data(v) -> str:
    if v is None or pd.isna(v):
        return "NULL"
    try:
        return "'" + pd.to_datetime(v).strftime("%Y-%m-%d") + "'"
    except Exception:
        return "NULL"


def sql_num(v) -> str:
    """4 casas, não 2: o Excel carrega sub-centavo (sessão de pacote sai por 9,322)
    e cortar em centavos linha a linha acumulou R$ 1,35 de diferença no semestre."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return "0"
    return "0" if pd.isna(f) else f"{f:.4f}"


def nf_propria(row) -> bool:
    """Regra 3A: a NF saiu no nome do profissional (ou 'Externa', grafia antiga)."""
    nf = nrm(row["NF"])
    if not nf:
        return False
    if nf == "externa":
        return True
    return any(t in nf for t in nrm(row["Profissional"]).split() if len(t) > 3)


def papel_de(row) -> str:
    """Na Oxy, Fotona e T-Sculptor têm executor e indicador distintos.
    A coluna Profissional da base acumula os dois papéis — aqui separamos."""
    if row["Empresa"] != "Oxy Recovery":
        return "executor"
    cat, prof = nrm(row["Categoria"]), nrm(row["Profissional"])
    if cat == "fotona":
        return "executor" if ("christiane" in prof or "juliana" in prof) else "indicador"
    if cat == "t-sculptor":
        return "executor" if "fernanda" in prof else "indicador"
    return "executor"


def separa_imposto(row):
    """Devolve (iss, taxa_comercial).

    Em Junho a taxa comercial de 2% foi embutida na coluna 'Imposto (18%)' — as linhas
    dessas categorias saíram com 20%. Aqui os dois voltam a ser coisas separadas, para
    o portal parar de mostrar 'Imposto (18%)' num número que é 20%."""
    bruto = float(row["Valor recebido"] or 0)
    imposto = float(row["Imposto (18%)"] or 0)
    if bruto <= 0 or imposto <= 0:
        return imposto, 0.0
    if nrm(row["Categoria"]) in CAT_TAXA_COMERCIAL and abs(imposto / bruto - 0.20) < 0.005:
        # o total continua sendo exatamente o que a planilha cobrou; só se separa em dois
        iss = round(0.18 * bruto, 4)
        return iss, round(imposto - iss, 4)
    return round(imposto, 4), 0.0


COLUNAS = [
    "periodo_id", "empresa", "os_numero", "profissional", "solicitante", "paciente",
    "indicacao", "tabela", "procedimento", "categoria", "conta_pagamento",
    "data_emissao", "data_compensacao", "tipo_pagamento", "valor_recebido", "custo",
    "seq", "imposto", "taxa_comercial", "taxa_cartao", "valor_liquido",
    "repasse_profissional", "repasse_indicador", "repasse_clinica",
    "pct_aplicado", "regra_aplicada", "papel", "nf_propria", "origem", "congelado",
]


def main(dry_run: bool):
    df = pd.read_excel(PLANILHA, sheet_name="Base Compensação")
    df = df[df["Profissional"].notna()].copy()
    for c in NUM:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)

    df["periodo_id"] = "2026-" + df["Mês"].map(MES_MAP)
    faltando = df[df["periodo_id"].isna()]
    if not faltando.empty:
        raise SystemExit(f"ABORTADO: {len(faltando)} linhas com Mês fora do mapa: "
                         f"{sorted(faltando['Mês'].dropna().unique())}")

    # seq dentro do grupo da chave natural (pacotes de sessões / parcelas)
    ks = []
    for c in CHAVE_NATURAL:
        k = "_k_" + c
        df[k] = df[c].astype(str)
        ks.append(k)
    df["seq"] = df.groupby(ks).cumcount() + 1

    df["nf_propria"] = df.apply(nf_propria, axis=1)
    df["papel"] = df.apply(papel_de, axis=1)
    imp = df.apply(separa_imposto, axis=1, result_type="expand")
    df["iss"], df["taxa_comercial"] = imp[0], imp[1]

    def pct(r):
        base = float(r["Valor recebido"]) if r["nf_propria"] else float(r["Valor Líquido"])
        if abs(base) < 0.01:
            return None
        return round(float(r["% Profissional"]) / base, 4)
    df["pct_aplicado"] = df.apply(pct, axis=1)

    print(f"Linhas ............: {len(df)}")
    print(f"Períodos ..........: {sorted(df['periodo_id'].unique())}")
    print(f"Empresas ..........: {sorted(df['Empresa'].unique())}")
    print(f"Linhas com seq > 1 : {int((df['seq'] > 1).sum())} (pacotes e parcelas)")
    print(f"NF do profissional : {int(df['nf_propria'].sum())} (Regra 3A)")
    print(f"Papel indicador ...: {int((df['papel'] == 'indicador').sum())}")
    print(f"Com taxa comercial : {int((df['taxa_comercial'] > 0).sum())} "
          f"(R$ {df['taxa_comercial'].sum():,.2f} separados do ISS)")
    print(f"Repasse total .....: R$ {df['% Profissional'].sum():,.2f}")

    if dry_run:
        print("\n[dry-run] nada foi escrito.")
        return

    linhas = []
    for _, r in df.iterrows():
        linhas.append("(" + ", ".join([
            sql_txt(r["periodo_id"]), sql_txt(r["Empresa"]), sql_txt(r["Nº OS"]),
            sql_txt(r["Profissional"]), sql_txt(r["Solicitante"]), sql_txt(r["Paciente"]),
            sql_txt(r["Indicação"]), sql_txt(r["Tabela"]), sql_txt(r["Procedimento"]),
            sql_txt(r["Categoria"]), sql_txt(r["NF"]),
            sql_data(r["Data emissão"]), sql_data(r["Data compensação"]),
            sql_txt(r["Tipo de pagamento"]),
            sql_num(r["Valor recebido"]), sql_num(r["Custo"]), str(int(r["seq"])),
            sql_num(r["iss"]), sql_num(r["taxa_comercial"]), sql_num(r["Taxa cartão (3%)"]),
            sql_num(r["Valor Líquido"]), sql_num(r["% Profissional"]),
            sql_num(r["% Indicador"]), sql_num(r["% Clínica"]),
            # pd.isna, NÃO `is None`: o apply devolve None em algumas linhas e float
            # em outras, então o pandas tipa a coluna como float e o None vira NaN —
            # `is None` não pega, e o SQL saía com um literal `nan` solto.
            "NULL" if pd.isna(r["pct_aplicado"]) else f"{r['pct_aplicado']:.4f}",
            "'importacao_historica'", sql_txt(r["papel"]),
            "true" if r["nf_propria"] else "false",
            "'importacao_excel'", "true",
        ]) + ")")

    for velho in SAIDA_DIR.glob(f"{NOME}*.sql"):
        velho.unlink()

    cab = ", ".join(COLUNAS)
    conflito = ("ON CONFLICT (empresa, os_numero, procedimento, data_compensacao,"
                " valor_recebido, profissional, seq) DO NOTHING;")
    n_arq = (len(linhas) + POR_ARQUIVO - 1) // POR_ARQUIVO

    print()
    for a in range(n_arq):
        fatia = linhas[a * POR_ARQUIVO:(a + 1) * POR_ARQUIVO]
        partes = [
            f"-- Seed 009 — parte {a + 1} de {n_arq}: histórico de honorários Jan–Jun/2026\n"
            f"-- Lançamentos {a * POR_ARQUIVO + 1} a {a * POR_ARQUIVO + len(fatia)} de {len(linhas)}.\n"
            "-- Gerado por _tools/_honorarios_importar_historico.py a partir da Base\n"
            "-- Compensação do Excel. Valores COMO FORAM PAGOS — nada recalculado.\n"
            "--\n"
            "-- Rodar DEPOIS de migration_009, e as partes EM ORDEM.\n"
            "-- Reexecutável: o ON CONFLICT usa a chave natural (com seq), então\n"
            "-- rodar duas vezes não duplica.\n"
        ]
        for i in range(0, len(fatia), LOTE):
            bloco = ",\n  ".join(fatia[i:i + LOTE])
            partes.append(f"INSERT INTO public.honorarios_lancamentos ({cab}) VALUES\n  {bloco}\n{conflito}\n")
        if a == n_arq - 1:
            partes.append(
                "\n-- CONFERÊNCIA — rode isto depois da última parte:\n"
                "-- SELECT periodo_id, count(*) AS linhas,\n"
                "--        round(sum(valor_recebido), 2) AS recebido,\n"
                "--        round(sum(repasse_profissional), 2) AS repasse\n"
                "--   FROM public.honorarios_lancamentos GROUP BY periodo_id ORDER BY periodo_id;\n"
            )
        alvo = SAIDA_DIR / f"{NOME}_{a + 1:02d}.sql"
        alvo.write_text("\n".join(partes), encoding="utf-8")
        print(f"  {alvo.name}  {len(fatia):5d} lançamentos  {alvo.stat().st_size / 1024:6.0f} KB")
    print(f"\nTotal: {len(linhas)} lançamentos em {n_arq} arquivos.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    main(ap.parse_args().dry_run)
