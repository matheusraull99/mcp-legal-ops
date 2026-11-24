import pytest

from legal_ops import cnj


def _confere_mod97(numero: str) -> bool:
    """Conferência independente: N AAAA J TR OOOO DD mod 97 == 1."""
    d = cnj.somente_digitos(numero)
    return int(d[0:7] + d[9:20] + d[7:9]) % 97 == 1


@pytest.mark.parametrize(
    "partes",
    [(1, 2020, 8, 26, 1), (123456, 2024, 5, 2, 31), (9999999, 2026, 4, 3, 6100), (42, 1999, 8, 13, 24)],
)
def test_montar_gera_numero_com_dv_correto(partes):
    numero = cnj.montar(*partes)
    assert _confere_mod97(numero)
    assert cnj.validar(numero)["valido"] is True


def test_dv_errado_e_detectado_e_aponta_o_esperado():
    certo = cnj.montar(305941, 2025, 8, 13, 24)
    dv = certo[8:10]
    errado = certo[:8] + ("00" if dv != "00" else "01") + certo[10:]
    diag = cnj.validar(errado)
    assert diag["valido"] is False
    assert diag["dv_esperado"] == dv


def test_aceita_numero_sem_mascara():
    certo = cnj.montar(777, 2023, 5, 1, 12)
    diag = cnj.validar(cnj.somente_digitos(certo))
    assert diag["valido"] is True
    assert diag["formatado"] == certo
    assert diag["partes"]["segmento_nome"] == "Justiça do Trabalho"


def test_quantidade_de_digitos_errada():
    diag = cnj.validar("123-45.2020")
    assert diag["valido"] is False
    assert "20 dígitos" in diag["motivo"]


def test_segmento_inexistente_e_invalido_mesmo_com_dv_certo():
    numero = cnj.montar(1, 2020, 0, 1, 1)
    assert cnj.validar(numero)["valido"] is False


def test_normalizar_levanta_para_numero_invalido():
    with pytest.raises(ValueError):
        cnj.normalizar("0000001-00.2020.8.26.0001")
