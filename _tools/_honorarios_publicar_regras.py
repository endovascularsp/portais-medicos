# -*- coding: utf-8 -*-
"""
_honorarios_publicar_regras.py — leva para a aba "Regras" do portal aquilo que
não está no banco.

Os percentuais por categoria e os impostos vivem em tabelas (honorarios_regras,
honorarios_taxas) e o portal lê direto de lá, sempre atual.

Mas parte das regras não é percentual por categoria e mora no código:
as quatro situações de cirurgia, a comissão de 10% quando o médico fatura na NF
dele, quem fica fora do fechamento e quem executa sem receber repasse.

Se a página exibisse esses números escritos à mão, um dia alguém mudaria o
código e a tela continuaria mostrando o valor velho — e a aba existe justamente
para o Dr. Igor confiar no que lê. Então este script LÊ do código e injeta na
página, entre marcadores. Roda junto com o fechamento, todo mês.

Uso:
    python _tools/_honorarios_publicar_regras.py            # simula
    python _tools/_honorarios_publicar_regras.py --escrever
"""
from __future__ import annotations
import argparse
import io
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _honorarios_regras as R   # noqa: E402

REPO = Path(__file__).resolve().parent.parent
ALVO = REPO / "fechamento" / "index.html"
MARCADOR = re.compile(r"(/\*REGRAS_CODIGO\*/)(.*?)(/\*REGRAS_CODIGO\*/)", re.S)


def montar() -> dict:
    """O que o código sabe e o banco não. Lido, nunca digitado."""
    return {
        "impostos": [
            {"rotulo": "ISS", "valor": R.ISS,
             "quando": "Sempre, sobre o valor recebido."},
            {"rotulo": "Taxa de cartão", "valor": R.TAXA_CARTAO,
             "quando": "Só quando o pagamento foi em cartão de crédito."},
            {"rotulo": "Taxa comercial", "valor": R.TAXA_COMERCIAL,
             "quando": "Nas categorias e a partir das datas definidas na tabela de taxas."},
        ],
        # Desde 18/08/2026 é UMA regra só: quem trouxe o paciente decide. Onde a
        # cirurgia foi feita e quem paga deixaram de importar — o 80% da clínica
        # e o 85% do plano não existem mais.
        "cirurgia": [
            {"situacao": "Cirurgia — paciente trazido pelo médico",
             "pct": R.CIRURGIA_LEAD_MEDICO,
             "porque": "O médico trouxe o paciente. Vale no hospital, na clínica "
                       "e por plano de saúde — o lugar e o pagador não mudam o "
                       "percentual."},
            {"situacao": "Cirurgia — paciente trazido pela clínica",
             "pct": R.CIRURGIA_LEAD_CLINICA,
             "porque": "A clínica adquiriu o paciente e retém a Taxa de Aquisição "
                       "de 20 pontos. Conta como da clínica: o campo escrito "
                       "\"Clínica\", os canais próprios (site, Google, redes, app "
                       "do plano) e a indicação feita por OUTRO profissional da "
                       "casa."},
            {"situacao": "Cirurgia na Oxy Recovery",
             "pct": R.OXY_CIRURGIA_LEAD_MEDICO,
             "porque": "A Oxy ficou fora da regra nova: lá seguem 80% na clínica, "
                       "85% por plano e 80% quando o lead é da clínica."},
        ],
        # A Taxa de Aquisição não é só de cirurgia: vale para toda categoria.
        "taxa_aquisicao": {
            "pct": R.TAXA_AQUISICAO,
            "texto": "Quando o paciente foi trazido pela clínica, o percentual da "
                     "categoria cai 20 pontos — uma consulta de 60% paga 40%. É a "
                     "Taxa de Aquisição do Paciente. Não se aplica na Oxy Recovery, "
                     "nem quando quem trouxe o paciente foi o próprio profissional, "
                     "um médico de fora ou alguém do círculo do paciente.",
        },
        "nf_propria": {
            "pct": R.REPASSE_CLINICA_NF_PROPRIA,
            "texto": "Quando a cirurgia é faturada na nota fiscal do próprio médico, "
                     "o dinheiro não passa pela clínica. Não há valor líquido a "
                     "repartir: a clínica apenas retém a comissão sobre o "
                     "procedimento, e por isso o repasse aparece negativo no relatório.",
        },
        "fora": sorted(R.IGNORAR_PROFISSIONAL),
        "sem_repasse": sorted(R.SEM_REPASSE_PROPRIO),
        "redireciona": sorted(R.REDIRECIONA_PARA_SOLICITANTE),
    }


def main(escrever: bool) -> int:
    dados = montar()
    txt = ALVO.read_text(encoding="utf-8")
    m = MARCADOR.search(txt)
    if not m:
        raise SystemExit(f"ABORTADO: não achei os marcadores /*REGRAS_CODIGO*/ em {ALVO.name}")

    novo_json = json.dumps(dados, ensure_ascii=False, indent=2)
    igual = m.group(2).strip() == novo_json.strip()

    print(f"\n=== Regras do código -> {ALVO.relative_to(REPO)} ===")
    print(f"  impostos ..............: {len(dados['impostos'])}")
    print(f"  situações de cirurgia .: {len(dados['cirurgia'])}")
    print(f"  fora do fechamento ....: {len(dados['fora'])}")
    print(f"  executam sem repasse ..: {len(dados['sem_repasse'])}")
    print(f"  redirecionam ao solicitante: {len(dados['redireciona'])}")
    print(f"\n  {'já está em dia' if igual else 'DESATUALIZADO — a página mostra números antigos'}")

    if igual or not escrever:
        if not igual and not escrever:
            print("\n  [simulação] nada gravado. Rode com --escrever.")
        return 0

    bruto = ALVO.read_bytes()
    fim = "\r\n" if bruto.count(b"\r\n") > bruto.count(b"\n") // 2 else "\n"
    io.open(ALVO, "w", encoding="utf-8", newline=fim).write(
        txt[:m.start(2)] + novo_json + txt[m.end(2):])
    print("  Página atualizada.")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--escrever", action="store_true")
    raise SystemExit(main(ap.parse_args().escrever))
