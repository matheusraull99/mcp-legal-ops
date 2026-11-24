from datetime import date, timedelta

import pytest

from legal_ops import prazos


def venc(intimacao: str, dias: int) -> str:
    return prazos.calcular_prazo(date.fromisoformat(intimacao), dias)["vencimento"]


@pytest.mark.parametrize(
    "ano, esperado",
    [
        (2000, "2000-04-23"),
        (2024, "2024-03-31"),
        (2025, "2025-04-20"),
        (2026, "2026-04-05"),
        (2027, "2027-03-28"),
    ],
)
def test_pascoa(ano, esperado):
    assert prazos.pascoa(ano).isoformat() == esperado


def test_feriados_moveis_2026():
    f = prazos.feriados_nacionais(2026)
    assert f[date(2026, 2, 16)] == "Carnaval (segunda-feira)"
    assert f[date(2026, 2, 17)] == "Carnaval (terça-feira)"
    assert f[date(2026, 4, 3)] == "Sexta-feira Santa"
    assert f[date(2026, 6, 4)] == "Corpus Christi"


def test_prazo_em_semana_sem_feriado_exclui_o_dia_do_comeco():
    # terça 03/11/2026 -> conta qua 04, qui 05, sex 06, seg 09, ter 10
    assert venc("2026-11-03", 5) == "2026-11-10"


def test_fim_de_semana_nao_conta():
    # intimação na sexta, prazo de 1 dia vence na segunda
    assert venc("2026-11-06", 1) == "2026-11-09"


def test_intimacao_em_sabado_prorroga_o_dia_do_comeco():
    r = prazos.calcular_prazo(date(2026, 11, 14), 5)
    assert r["dia_do_comeco"] == "2026-11-16"
    # 17, 18, 19, (20 feriado, 21, 22), 23, 24
    assert r["vencimento"] == "2026-11-24"


def test_consciencia_negra_e_pulada():
    r = prazos.calcular_prazo(date(2026, 11, 19), 1)
    assert r["vencimento"] == "2026-11-23"
    assert "Consciência Negra" in r["periodos_nao_uteis"][0]["motivos"][0]


def test_recesso_forense_suspende_a_contagem():
    r = prazos.calcular_prazo(date(2026, 12, 18), 5)
    # recesso até 20/01; 21 (qui), 22 (sex), 25, 26, 27
    assert r["inicio_contagem"] == "2027-01-21"
    assert r["vencimento"] == "2027-01-27"


def test_intimacao_dentro_do_recesso():
    # começo prorrogado para 21/01/2027 (1º dia útil), prazo de 1 dia vence 22/01
    assert venc("2027-01-10", 1) == "2027-01-22"


def test_carnaval_e_pulado_e_quarta_de_cinzas_conta():
    assert venc("2026-02-13", 1) == "2026-02-18"


def test_sexta_santa_e_pulada():
    assert venc("2026-04-02", 1) == "2026-04-06"


def test_tiradentes_e_pulado():
    # seg 20/04/2026 -> ter 21 é Tiradentes -> qua 22
    assert venc("2026-04-20", 1) == "2026-04-22"


@pytest.mark.parametrize("dias", [0, -3, 366])
def test_prazo_com_tamanho_implausivel_e_recusado(dias):
    with pytest.raises(ValueError):
        prazos.calcular_prazo(date(2026, 3, 2), dias)


def test_vencimento_e_sempre_dia_util():
    inicio = date(2026, 1, 1)
    for i in range(0, 730, 3):
        for dias in (1, 5, 15):
            v = date.fromisoformat(prazos.calcular_prazo(inicio + timedelta(days=i), dias)["vencimento"])
            assert prazos.eh_dia_util(v)


def test_prazo_corrido_prorroga_quando_cai_em_feriado():
    # 10/11 + 10 dias = 20/11 (feriado, sexta) -> segunda 23/11
    assert prazos.calcular_prazo_corridos(date(2026, 11, 10), 10) == date(2026, 11, 23)


def test_dias_uteis_entre_tem_sinal():
    assert prazos.dias_uteis_entre(date(2026, 11, 24), date(2026, 11, 27)) == 3
    assert prazos.dias_uteis_entre(date(2026, 11, 27), date(2026, 11, 24)) == -3
    assert prazos.dias_uteis_entre(date(2026, 11, 24), date(2026, 11, 24)) == 0
