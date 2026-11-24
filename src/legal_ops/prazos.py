"""Motor de prazos processuais no estilo do CPC/2015.

Regras implementadas:

- Art. 219: prazos processuais em dias contam só os dias úteis.
- Art. 224: exclui o dia do começo e inclui o do vencimento.
- Art. 224, §1º: se o dia do começo cair em dia sem expediente, ele é
  prorrogado para o primeiro dia útil seguinte (a contagem começa depois dele).
- Art. 220: suspensão dos prazos de 20/12 a 20/01 (recesso forense), inclusive.
- Feriados nacionais fixos e móveis (Carnaval, Sexta-feira Santa e Corpus
  Christi calculados a partir da Páscoa).

O que fica de fora (e está documentado no README): feriados estaduais e
municipais, suspensões decretadas por tribunal (indisponibilidade de sistema,
portarias), regras de intimação eletrônica (art. 5º da Lei 11.419/2006, que
define quando a intimação se considera feita) e prazos em dobro (art. 229,
Fazenda Pública, Defensoria).
"""

from __future__ import annotations

from datetime import date, timedelta
from functools import lru_cache


def pascoa(ano: int) -> date:
    """Domingo de Páscoa pelo algoritmo anônimo gregoriano (Meeus/Jones/Butcher)."""
    a = ano % 19
    b, c = divmod(ano, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l_ = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l_) // 451
    mes, dia = divmod(h + l_ - 7 * m + 114, 31)
    return date(ano, mes, dia + 1)


@lru_cache(maxsize=64)
def feriados_nacionais(ano: int) -> dict[date, str]:
    """Dias sem expediente forense de âmbito nacional no ano.

    Carnaval e Corpus Christi não são feriados nacionais por lei, mas os
    tribunais costumam não ter expediente; entram aqui por decisão de projeto.
    """
    p = pascoa(ano)
    return {
        date(ano, 1, 1): "Confraternização Universal",
        p - timedelta(days=48): "Carnaval (segunda-feira)",
        p - timedelta(days=47): "Carnaval (terça-feira)",
        p - timedelta(days=2): "Sexta-feira Santa",
        date(ano, 4, 21): "Tiradentes",
        date(ano, 5, 1): "Dia do Trabalho",
        p + timedelta(days=60): "Corpus Christi",
        date(ano, 9, 7): "Independência do Brasil",
        date(ano, 10, 12): "Nossa Senhora Aparecida",
        date(ano, 11, 2): "Finados",
        date(ano, 11, 15): "Proclamação da República",
        date(ano, 11, 20): "Dia Nacional de Zumbi e da Consciência Negra",
        date(ano, 12, 25): "Natal",
    }


def em_recesso(dia: date) -> bool:
    """True entre 20/12 e 20/01, inclusive (art. 220 do CPC)."""
    return (dia.month == 12 and dia.day >= 20) or (dia.month == 1 and dia.day <= 20)


def motivo_nao_util(dia: date) -> str | None:
    """Explica por que o dia não é útil, ou None se for dia útil."""
    if dia.weekday() == 5:
        return "sábado"
    if dia.weekday() == 6:
        return "domingo"
    feriado = feriados_nacionais(dia.year).get(dia)
    if feriado:
        return f"feriado: {feriado}"
    if em_recesso(dia):
        return "recesso forense (20/12 a 20/01)"
    return None


def eh_dia_util(dia: date) -> bool:
    return motivo_nao_util(dia) is None


def proximo_dia_util(dia: date) -> date:
    """O próprio dia, se útil; senão o primeiro dia útil seguinte."""
    while not eh_dia_util(dia):
        dia += timedelta(days=1)
    return dia


def calcular_prazo(data_intimacao: date, dias_uteis: int) -> dict:
    """Calcula o vencimento de um prazo em dias úteis.

    Retorna um dicionário com o vencimento e a memória de cálculo (os dias
    pulados e o motivo), para o advogado conferir.
    """
    if dias_uteis < 1:
        raise ValueError("O prazo precisa ter pelo menos 1 dia útil.")
    if dias_uteis > 365:
        raise ValueError("Prazo acima de 365 dias úteis não é plausível; confira o valor.")

    dia_do_comeco = proximo_dia_util(data_intimacao)
    pulados: list[dict] = []
    contados = 0
    dia = dia_do_comeco
    while contados < dias_uteis:
        dia += timedelta(days=1)
        motivo = motivo_nao_util(dia)
        if motivo:
            pulados.append({"data": dia.isoformat(), "motivo": motivo})
        else:
            contados += 1

    return {
        "data_intimacao": data_intimacao.isoformat(),
        "dia_do_comeco": dia_do_comeco.isoformat(),
        "inicio_contagem": proximo_dia_util(dia_do_comeco + timedelta(days=1)).isoformat(),
        "dias_uteis": dias_uteis,
        "vencimento": dia.isoformat(),
        "dias_corridos_ate_vencimento": (dia - data_intimacao).days,
        "total_dias_nao_uteis_pulados": len(pulados),
        "periodos_nao_uteis": _agrupar(pulados),
        "observacao": (
            "Contagem em dias úteis (CPC, arts. 219, 220 e 224) com feriados nacionais e recesso "
            "forense. Não considera feriados locais nem suspensões decretadas pelo tribunal."
        ),
    }


def _agrupar(pulados: list[dict]) -> list[dict]:
    """Junta dias não úteis consecutivos num só período (memória de cálculo legível)."""
    periodos: list[dict] = []
    for item in pulados:
        d = date.fromisoformat(item["data"])
        motivo = item["motivo"]
        if periodos and date.fromisoformat(periodos[-1]["ate"]) + timedelta(days=1) == d:
            periodos[-1]["ate"] = item["data"]
            if motivo not in periodos[-1]["motivos"]:
                periodos[-1]["motivos"].append(motivo)
        else:
            periodos.append({"de": item["data"], "ate": item["data"], "motivos": [motivo]})
    return periodos


def calcular_prazo_corridos(data_inicio: date, dias: int) -> date:
    """Prazo em dias corridos (ex.: prazos materiais): exclui o dia do começo e,
    se o vencimento cair em dia não útil, prorroga para o primeiro dia útil seguinte.
    """
    if dias < 1:
        raise ValueError("O prazo precisa ter pelo menos 1 dia.")
    return proximo_dia_util(data_inicio + timedelta(days=dias))


def dias_uteis_entre(inicio: date, fim: date) -> int:
    """Quantos dias úteis existem em (inicio, fim]. Negativo se fim < inicio."""
    if fim == inicio:
        return 0
    sinal = 1 if fim > inicio else -1
    a, b = (inicio, fim) if sinal == 1 else (fim, inicio)
    total = 0
    dia = a
    while dia < b:
        dia += timedelta(days=1)
        if eh_dia_util(dia):
            total += 1
    return total * sinal
