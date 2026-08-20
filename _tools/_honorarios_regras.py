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
# TAXA DE AQUISIÇÃO DO PACIENTE — decidida pelo Dr. Igor e fechada com o Thiago
# em 18/08/2026. Quando o LEAD é da clínica, a clínica retém 20 pontos
# percentuais a mais: quem trouxe o paciente foi a casa, não o médico.
#
# Vale para Endovascular SP e Cirurgias. **A Oxy Recovery está FORA** — decisão
# explícita do Thiago.
TAXA_AQUISICAO = 0.20

# UMA regra para toda cirurgia, escolhida entre duas alternativas em 18/08/2026:
# 90% se o lead é do médico, 70% se é da clínica — não importa se foi no hospital,
# na clínica ou por plano de saúde. O 80% da cirurgia na clínica e o 85% do plano
# DEIXARAM DE EXISTIR.
#
# A alternativa descartada era mais fiel à economia (a clínica reter mais onde a
# estrutura é dela: hospital 60, clínica 50, plano 70) e rendia R$ 13 mil/mês a
# mais. Perdeu porque eram três regras: esta é a que o médico entende de cabeça,
# e o Thiago vai ter de explicar isso 11 vezes.
CIRURGIA_LEAD_MEDICO = 0.90
CIRURGIA_LEAD_CLINICA = 0.70

# A OXY NÃO ENTROU na regra nova — decisão do Thiago em 18/08/2026. Lá a cirurgia
# continua como era: 80% na clínica, 85% por plano, e 80/90 conforme o lead no
# hospital. São poucos casos (9 em 7 meses), mas sem estas constantes o
# fechamento de Agosto aplicaria 90/70 na Oxy sem ninguém pedir.
OXY_CIRURGIA_CLINICA = 0.80
OXY_CIRURGIA_PLANO = 0.85
OXY_CIRURGIA_LEAD_CLINICA = 0.80
OXY_CIRURGIA_LEAD_MEDICO = 0.90

# Nomes antigos, mantidos para não quebrar quem importa daqui.
CIRURGIA_CLINICA = CIRURGIA_LEAD_MEDICO
CIRURGIA_PLANO = CIRURGIA_LEAD_MEDICO
CIRURGIA_HOSPITAL_LEAD_CLINICA = CIRURGIA_LEAD_CLINICA
CIRURGIA_HOSPITAL_LEAD_MEDICO = CIRURGIA_LEAD_MEDICO

# O campo "Indicado Por" em branco não é neutro: para o Dr. Igor conta como lead
# da clínica, para os demais como lead do próprio médico. Decisão do Thiago em
# 18/08/2026, olhando os 93 lançamentos de Julho com o campo vazio.
BRANCO_CONTA_COMO_CLINICA = ("igor rafael sincos",)

# Textos do campo "Indicado Por" que o Thiago decidiu UM A UM em 18/08/2026,
# porque comparação automática não resolve: "Dra Chris" é abreviação e não contém
# "christiane"; "App da Omint" é canal do plano, não médico. A decisão vale para
# todos os meses e para os que voltarem (OS parcelada traz o mesmo texto).
#
# TEMPORÁRIO: isto vira tabela + tela, como a do Catálogo. Enquanto não existe,
# mora aqui para não haver decisão de dinheiro escondida em heurística.
#
# A checagem de "o próprio executor" vem ANTES desta lista: "Dra Simone" numa
# consulta da própria Dra. Simone é paciente dela, não indicação da casa.
# Formato: texto -> (lado, token_de_quem_e).
#   ("casa", "christiane") = profissional da casa. Vira lead da CLÍNICA quando
#   outro atende, e lead do MÉDICO quando quem atende é a própria pessoa — por
#   isso o token: "Dra Chris" não contém "christiane", e sem ele a abreviação
#   transformaria o paciente dela em lead da casa.
INDICACAO_DECIDIDA = {
    # profissionais da casa
    "dra chris":       ("casa", "christiane"),
    "dra simone":      ("casa", "simone"),
    "dr paulo laredo": ("casa", "laredo"),
    "paulo laredo":    ("casa", "laredo"),
    # canais do plano de saúde -> lead da clínica (o credenciamento é da casa)
    "app da omint":    ("clinica", None),
    "app sulamerica":  ("clinica", None),
    "app omint":       ("clinica", None),
    # canais da casa que caíam como "não classificada" (decididos em 18/08/2026)
    "oxy prime":       ("clinica", None),
    "oxyprime":        ("clinica", None),
    "pesquisa":        ("clinica", None),
    "chat gpt":        ("clinica", None),
    "chatgpt":         ("clinica", None),
    "fotona day":      ("clinica", None),
    # São Camilo é o hospital onde o Dr. Manoel atende: quem chega por ali vem
    # pelo nome dele, não pela clínica (Thiago, 20/08/2026). Uma linha só resolve
    # as três grafias — "Sao Camilo", "Hosp São Camilo", "Hospital São Camilo -
    # Dr Manoel" — porque a busca é por substring.
    # TEM de vir antes de "amil": a busca para no primeiro texto que casa, e
    # "amil" está dentro de "c-amil-o". Era por isso que São Camilo contava como
    # lead da clínica — casava com o plano Amil, não com uma decisão de ninguém.
    "sao camilo":      ("medico", None),
    "amil":            ("clinica", None),
    "aplicativo":      ("clinica", None),
    "pelo convenio":   ("clinica", None),
    "doctoralia":      ("clinica", None),
    # a marca é do MÉDICO, não da clínica — decisão do Thiago em 18/08/2026.
    # Texto que traga "clínica" escrito NÃO cai aqui: a checagem de "clinica" no
    # texto vem antes, para "Instagram Clinica" seguir sendo da casa.
    "internet":        ("medico", None),
    "instagram":       ("medico", None),
    "instragram":      ("medico", None),
    "intagram":        ("medico", None),
    "redes sociais":   ("medico", None),
    "rede social":     ("medico", None),
    # decididos como rede do próprio médico
    "vila nova star":       ("medico", None),   # hospital onde o Dr. Igor opera
    "guilherme":            ("medico", None),
    "sumiko":               ("medico", None),
    "aline lamaita":        ("medico", None),
    "raquel rufino":        ("medico", None),
    "renata ginecologista": ("medico", None),
    "ludmilla":             ("medico", None),
    "vascular de americana":("medico", None),
    "padovessi":            ("medico", None),
    "sheila moreno":        ("medico", None),
    "marcia dermato":       ("medico", None),
}

# Decisão do Dr. Igor, reafirmada em 03/08/2026: **na dúvida, conta como lead do
# médico**. A clínica prefere pagar a mais a penalizar um médico por falha de
# cadastro nossa. Então indicação vazia ou que não dá para classificar -> 90%.
#
# Canais da própria clínica (marketing e plano de saúde) são lead da clínica: são
# preenchimentos corretos, não falha de cadastro.
# INTERNET, INSTAGRAM e REDES SOCIAIS saíram daqui em 18/08/2026, por decisão do
# Thiago: esses canais são movidos pela marca dos MÉDICOS, não pela da clínica —
# o Instagram do Dr. Igor traz paciente pelo nome dele. Passaram para
# INDICACAO_DECIDIDA como lead do médico. É a maior devolução da regra:
# 291 lançamentos, R$ 223.984,78 de líquido, R$ 44.796,96 de volta aos médicos
# em 7 meses. Eu registrei a ressalva de que quem paga tráfego, site e agência é
# a clínica; ele confirmou assim mesmo.
#
# "site" e "google" FICARAM: são o site e a ficha da clínica, não de ninguém.
CANAIS_CLINICA = (
    "clinica", "google", "site", "facebook",
    "omint", "sulamerica", "sulamérica", "medsenior", "tiktok", "whatsapp",
    "anuncio", "anúncio", "marketing", "youtube",
)

# Textos que significam "não informado". Sem isto, "Não possui" era tratado como
# uma indicação de verdade e caía em "não classificada".
VAZIOS = ("", "nao possui", "nao informado", "nao tem", "sem indicacao", "-", "--", "n/a")

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

# Fora do corpo clínico — a linha sai do fechamento inteira, sem virar repasse
# nem receita da clínica.
IGNORAR_PROFISSIONAL = {
    "paulo laredo pinto", "paulo laredo",     # esporádico, apurado em aba própria
    "agendamento cirurgico e visita hospitalar", "enfermagem", "sala spa",
    "oxy recovery", "endovascular sp",        # linhas com a empresa no lugar do nome
}

# Rótulos operacionais que aparecem no lugar do executante. Não são gente: são
# a fila do agendamento cirúrgico e o posto de enfermagem. Quando a OS tem um
# SOLICITANTE de verdade, é ele quem fez o trabalho, e a linha passa a ser dele.
# Só quando não há solicitante é que a linha sai do fechamento (fica na lista
# acima). Decidido pelo Thiago em 07/08/2026 — é a mesma regra que a
# Produtividade já usava, agora valendo também para o Recebimento.
REDIRECIONA_PARA_SOLICITANTE = {
    "enfermagem",
    "agendamento cirurgico e visita hospitalar",
}

# Executa procedimento e gera receita, mas é da casa: recebe salário, não
# repasse. A linha CONTINUA no fechamento — o valor inteiro vira receita da
# clínica. Diferente de IGNORAR_PROFISSIONAL, que faz a receita sumir do painel.
# Decidido pelo Thiago em 07/08/2026: "Juliana Olimpio não recebe repasse por
# procedimentos executados."
SEM_REPASSE_PROPRIO = {
    "juliana olimpio",
    "juliana olimpio de paula",
}


def lado_do_lead(indicacao, nomes_profissionais=(), executor=None) -> tuple:
    """Devolve ('clinica'|'medico', descrição) — de quem é o lead.

    A ORDEM DOS TESTES MUDOU em 18/08/2026, e é o coração da regra nova:

      1. "Clínica" escrito                       -> clínica
      2. o PRÓPRIO executor                      -> médico   (paciente dele)
      3. OUTRO profissional da casa              -> CLÍNICA  (era médico até 17/08)
      4. Dr./Dra. que não é da casa              -> médico   (rede dele)
      5. canal da própria clínica                -> clínica
      6. em branco                               -> depende de quem atendeu

    O passo 3 é uma INVERSÃO, não um ajuste: até 17/08 "indicado por profissional
    da casa" pagava 90% (lead do médico). O Dr. Igor definiu o contrário — se a
    Dra. Simone manda um paciente para o Dr. Igor, quem gerou o lead foi a casa.
    E por isso o passo 2 tem de vir ANTES do 3: o nome do próprio executor no
    campo é paciente dele, não indicação de terceiro.
    """
    k = chave(indicacao)
    ex = chave(executor)
    toks_ex = {t for t in ex.split() if len(t) > 3}
    if k in VAZIOS:
        k = ""

    if k in ("clinica", "clinica endovascular", "endovascular"):
        return "clinica", "lead da clínica"

    if k:
        # 2) o PRÓPRIO executor: qualquer token do nome dele no campo. Vem antes
        #    de tudo — "Dra Simone" numa consulta DA Dra. Simone é paciente dela,
        #    não indicação de terceiro.
        if any(t in k for t in toks_ex):
            return "medico", "lead do médico (paciente próprio dele)"

        # 3) a palavra "clínica" ESCRITA no texto vence o resto. Precisa vir
        #    antes da lista decidida porque "Instagram Clinica" contém
        #    "instagram", que passou a ser lead do médico em 18/08/2026 — sem
        #    esta linha, quem escreveu "Clinica" no campo perderia o efeito.
        if "clinica" in k:
            return "clinica", "lead da clínica (escrito no campo)"

        # 4) textos que o Thiago decidiu um a um: nome abreviado ou ambíguo não
        #    casa por comparação automática ("Dra Chris" não contém
        #    "christiane"). Sai daqui quando a tela de decisão existir.
        for texto, (lado, quem) in INDICACAO_DECIDIDA.items():
            if texto not in k:
                continue
            if lado == "casa":
                if quem and quem in ex:
                    return "medico", "lead do médico (paciente próprio dele)"
                return "clinica", "lead da clínica (profissional da casa, decidido caso a caso)"
            return lado, ("lead da clínica" if lado == "clinica"
                          else "lead do médico") + " (decidido caso a caso)"

        # 4) outro profissional da casa.
        #
        # Aceita nomes COMPLETOS (conjunto de tokens por pessoa) ou a lista antiga
        # de tokens soltos. Com nomes completos exige DUAS partes do nome da mesma
        # pessoa — sobrenome solto colide: "Juliana Bica" batia com a Juliana
        # Olimpio, "Maria Luiza ... LOPES ..." com o sobrenome da Christiane, e
        # "Dr Luiz Gonzaga ... SOUZA ..." com o Jonathan Souza. Três pessoas de
        # fora viravam lead da clínica por acidente, tirando repasse do médico.
        for nome in nomes_profissionais:
            if isinstance(nome, (set, frozenset, tuple, list)):
                toks = {t for t in nome if t not in toks_ex}
                achados = [t for t in toks if t in k]
                if len(achados) >= min(2, len(toks)) and achados:
                    return "clinica", "lead da clínica (indicado por profissional da casa)"
            elif nome and nome in k and nome not in toks_ex:
                return "clinica", "lead da clínica (indicado por profissional da casa)"

        # 5) médico de fora
        if any(m in f" {k} " for m in MARCADORES_PESSOA):
            return "medico", "lead do médico (indicado por médico de fora)"
        # 6) canal da casa
        if any(c in k for c in CANAIS_CLINICA):
            return "clinica", "lead da clínica (canal próprio)"
        return "medico", "lead do médico (indicação não classificada)"

    # 6) em branco
    if ex and any(n in ex for n in BRANCO_CONTA_COMO_CLINICA):
        return "clinica", "lead da clínica (indicação em branco)"
    return "medico", "lead do médico (indicação em branco)"


def origem_lead(indicacao, nomes_profissionais=(), executor=None) -> tuple:
    """(percentual de CIRURGIA, descrição). Uma regra só: 90% médico, 70% clínica."""
    lado, desc = lado_do_lead(indicacao, nomes_profissionais, executor)
    pct = CIRURGIA_LEAD_CLINICA if lado == "clinica" else CIRURGIA_LEAD_MEDICO
    return pct, ("R3C " if lado == "clinica" else "R3B ") + desc


def com_taxa_aquisicao(pct, lado, empresa) -> tuple:
    """Aplica os 20 pontos da Taxa de Aquisição fora da cirurgia.

    Só quando o lead é da clínica, e **nunca na Oxy Recovery**. O piso é zero:
    categoria de percentual baixo pode chegar a 0, e o Thiago decidiu em
    18/08/2026 não abrir exceção para elas ("pra gente não ficar criando mais
    exceções") — medicação injetável vai de 30% para 10%.
    """
    if pct is None or empresa == OXY or lado != "clinica" or pct <= 0:
        return pct, ""
    return max(0.0, round(pct - TAXA_AQUISICAO, 4)), " + taxa de aquisição (−20 pts)"


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
