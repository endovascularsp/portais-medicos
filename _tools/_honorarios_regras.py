# -*- coding: utf-8 -*-
"""
_honorarios_regras.py — as regras de repasse, num lugar só.

Este módulo é a fonte da verdade das regras no repositório. Ele alimenta tanto o
motor (`_honorarios_motor.py`) quanto o seed da tabela `honorarios_regras`
(migration_009), para que a regra no código nunca divirja da regra no banco.

Origem: Manual de Regras de Repasse v1.0 (02/04/2026), bloco "CORPO CLÍNICO" do
documento de cargos e comissionamento, mais as decisões do Thiago em 03/08/2026.
Validado contra 4.763 lançamentos reais de Jan–Jun/2026.

QUANDO A TELA DE REGRAS EXISTIR (Fase 3), o motor passa a ler de
`honorarios_regras` no Supabase e este módulo vira apenas o seed inicial.
"""
from __future__ import annotations
import unicodedata

ENDO = "Endovascular SP"
OXY = "Oxy Recovery"


def chave(s) -> str:
    """Normaliza para comparação: sem acento, minúsculo, espaços colapsados."""
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode()
    return " ".join(s.lower().split())


# ---------------------------------------------------------------------------
# Impostos e taxas
# ---------------------------------------------------------------------------
ISS = 0.18
TAXA_CARTAO = 0.03
TIPOS_COM_TAXA_CARTAO = {"cartao de credito"}   # débito NÃO desconta (decisão 03/08)

# Os 2% de taxa de negociação pedidos pelo Dr. Igor. O valor é o 1º período em que
# vale. Medicação injetável entrou depois: o aviso chegou após o fechamento de
# Junho, então só conta de Julho em diante.
TAXA_COMERCIAL = 0.02
TAXA_COMERCIAL_CATEGORIAS = {
    "fotona":              "2026-06",
    "cirurgia - clinica":  "2026-06",
    "cirurgia - hospital": "2026-06",
    "procedimentos":       "2026-06",
    "t-sculptor":          "2026-06",
    "laser (clinica)":     "2026-06",
    "laser (locacao)":     "2026-06",
    "medicacao injetavel": "2026-07",
}

# ---------------------------------------------------------------------------
# Regra 3A — o profissional emitiu a NF na própria conta
# ---------------------------------------------------------------------------
# Ele recebeu direto e repassa 10% do BRUTO à clínica. Lança negativo, para abater
# no acerto do mês. Sem ISS e sem taxa de cartão: a clínica não recebeu nada.
REPASSE_CLINICA_NF_PROPRIA = 0.10
CONTA_PROPRIA_LITERAL = {"externa"}   # grafia antiga; o padrão novo é o nome do profissional

# Planos de saúde (Regra 1 das cirurgias)
MARCAS_PLANO = ("omint", "sulam", "medsenior")

# ---------------------------------------------------------------------------
# Cirurgias
# ---------------------------------------------------------------------------
# A categoria diz ONDE a cirurgia aconteceu fisicamente.
#
# As regras de cirurgia valem para AS DUAS EMPRESAS. O manual v1.0 só falava da
# Endovascular, mas em Julho/2026 apareceram duas cirurgias da Christiane na Oxy
# (Endolift e Morpheus) — Thiago confirmou em 04/08/2026 que é raro, porém possível,
# e que segue as mesmas regras. Por isso não há chave por empresa aqui.
CIRURGIA_CLINICA = 0.80        # "Cirurgia - Clínica" — feita na clínica, sempre 80/20
CIRURGIA_PLANO = 0.85          # "Cirurgia - Hospital" por plano de saúde

# "Cirurgia - Hospital" particular: 80% se o lead é da clínica, 90% se é do médico.
# Derivado do campo "Indicado Por".
CIRURGIA_HOSPITAL_LEAD_CLINICA = 0.80
CIRURGIA_HOSPITAL_LEAD_MEDICO = 0.90

# Decisão do Dr. Igor, reafirmada em 03/08/2026: **na dúvida, conta como lead do
# médico**. A clínica prefere pagar a mais a penalizar um médico por falha de
# cadastro nossa. Então indicação vazia ou que não dá para classificar -> 90%.
#
# Canais da própria clínica (marketing e plano de saúde) são lead da clínica: são
# preenchimentos corretos, não falha de cadastro.
CANAIS_CLINICA = (
    "clinica", "internet", "google", "site", "instagram", "instragram", "facebook",
    "omint", "sulamerica", "sulamérica", "medsenior", "tiktok", "whatsapp",
)

# Marcadores de que a indicação é uma PESSOA (médico de dentro ou de fora).
# Vence os canais: "Instagram da Dra. Ludmilla" é lead da médica, não do Instagram.
# "dro" aparece porque a normalização converte o "º" de "Drº" em "o".
MARCADORES_PESSOA = ("dr ", "dr.", "dro ", "dra ", "dra.", "doutor", "doutora")

# ---------------------------------------------------------------------------
# Executores de categorias compartilhadas na Oxy
# ---------------------------------------------------------------------------
# Na Oxy a coluna Profissional acumula dois papéis. Quem não é executor da
# categoria está ali como INDICADOR e recebe o percentual de indicação.
EXECUTORES = {
    (OXY, "fotona"):     ("christiane", "juliana"),
    (OXY, "t-sculptor"): ("fernanda",),
}

# ---------------------------------------------------------------------------
# Percentuais
# ---------------------------------------------------------------------------
GERAL = {
    (ENDO, "consultas"): .60, (ENDO, "exames de imagem"): .60,
    (ENDO, "exames gerais"): .60, (ENDO, "procedimentos"): .60,
    (ENDO, "fotona"): .60, (ENDO, "laser (clinica)"): .60,
    (ENDO, "laser (locacao)"): .60, (ENDO, "fisioterapia"): .50,
    (ENDO, "medicacao injetavel"): .30, (ENDO, "t-sculptor"): .00,
    (ENDO, "produtos"): .00,
    (OXY, "consultas"): .60, (OXY, "exames de imagem"): .60,
    (OXY, "exames gerais"): .60, (OXY, "procedimentos"): .65,
    (OXY, "fisioterapia"): .50, (OXY, "medicacao injetavel"): .30,
    (OXY, "produtos"): .00,
}

# Executor da categoria compartilhada (empresa, categoria, pedaço do nome)
EXECUTOR_PCT = {
    (OXY, "fotona", "christiane"): .20,
    (OXY, "fotona", "juliana"): .00,       # fisioterapeuta interna, sem repasse
    (OXY, "t-sculptor", "fernanda"): .50,  # fisioterapeuta executando: 50/50
}

# Indicador da categoria compartilhada
INDICADOR_PCT = {
    (OXY, "fotona"): .10,
    (OXY, "t-sculptor"): .10,
}

# Override por profissional — vence a regra geral.
EXCECOES = {
    (ENDO, "consultas", "simone"): .70,
    (ENDO, "exames gerais", "simone"): .70,
    (ENDO, "consultas", "nicole"): .70,      # fellow da Dra. Simone
    (ENDO, "exames gerais", "nicole"): .70,
    (ENDO, "procedimentos", "daniela"): .80,
    (OXY, "laser (clinica)", "christiane"): .35,
    (OXY, "laser (locacao)", "christiane"): .20,
}

# Fora do corpo clínico — não geram repasse pelo motor.
IGNORAR_PROFISSIONAL = {
    "paulo laredo pinto", "paulo laredo",     # esporádico, apurado em aba própria
    "agendamento cirurgico e visita hospitalar", "enfermagem", "sala spa",
    "oxy recovery", "endovascular sp",        # linhas com a empresa no lugar do nome
}


def origem_lead(indicacao, nomes_profissionais=()) -> tuple:
    """Classifica o campo "Indicado Por" em (percentual, descrição da regra).

    Ordem importa: "Clínica" explícito vence tudo; depois pessoa; depois canal;
    e o que sobra cai no princípio do Dr. Igor (não penalizar o médico)."""
    k = chave(indicacao)

    if k in ("clinica", "clinica endovascular", "endovascular"):
        return CIRURGIA_HOSPITAL_LEAD_CLINICA, "R3C lead da clínica"

    if k:
        alvo = f" {k} "
        if any(m in alvo for m in MARCADORES_PESSOA):
            return CIRURGIA_HOSPITAL_LEAD_MEDICO, "R3B lead do médico (indicado por médico)"
        for nome in nomes_profissionais:
            if nome and nome in k:
                return CIRURGIA_HOSPITAL_LEAD_MEDICO, "R3B lead do médico (indicado por profissional da casa)"
        if any(c in k for c in CANAIS_CLINICA):
            return CIRURGIA_HOSPITAL_LEAD_CLINICA, "R3C lead da clínica (canal próprio)"

    return CIRURGIA_HOSPITAL_LEAD_MEDICO, "R3B lead do médico (indicação não classificada — na dúvida, do médico)"


def eh_plano(tabela) -> bool:
    t = chave(tabela)
    return any(m in t for m in MARCAS_PLANO)


def tem_taxa_comercial(categoria, periodo_id: str) -> bool:
    desde = TAXA_COMERCIAL_CATEGORIAS.get(chave(categoria))
    return bool(desde) and periodo_id >= desde


def papel_de(empresa: str, categoria, profissional) -> str:
    execs = EXECUTORES.get((empresa, chave(categoria)))
    if not execs:
        return "executor"
    p = chave(profissional)
    return "executor" if any(e in p for e in execs) else "indicador"


def percentual(empresa: str, categoria, profissional, papel: str):
    """(percentual, nome_da_regra) — ou (None, motivo) quando não existe regra."""
    cat, prof = chave(categoria), chave(profissional)

    if papel == "indicador":
        pct = INDICADOR_PCT.get((empresa, cat))
        if pct is None:
            return None, f"sem regra de indicador para '{categoria}' em {empresa}"
        return pct, f"Indicador {cat}"

    for (e, c, nome), pct in EXECUTOR_PCT.items():
        if e == empresa and c == cat and nome in prof:
            return pct, f"Executor {cat}"

    for (e, c, nome), pct in EXCECOES.items():
        if e == empresa and c == cat and nome in prof:
            return pct, f"Exceção {nome} / {cat}"

    pct = GERAL.get((empresa, cat))
    if pct is None:
        return None, f"categoria '{categoria}' sem regra em {empresa}"
    return pct, f"Geral {empresa}"
