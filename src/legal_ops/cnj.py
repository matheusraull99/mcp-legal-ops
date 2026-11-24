"""Numeração única de processos do CNJ (Resolução CNJ 65/2008).

Formato: NNNNNNN-DD.AAAA.J.TR.OOOO

- NNNNNNN: número sequencial do processo no ano, na unidade de origem
- DD: dígito verificador, calculado pelo módulo 97 (ISO 7064)
- AAAA: ano de ajuizamento
- J: segmento do Judiciário (ex.: 4 = Federal, 5 = Trabalho, 8 = Estadual)
- TR: tribunal dentro do segmento
- OOOO: unidade de origem (vara/foro)

Regra do dígito: DD = 98 - (N AAAA J TR OOOO 00 mod 97). A conferência é
(N AAAA J TR OOOO DD) mod 97 == 1.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

SEGMENTOS = {
    "1": "Supremo Tribunal Federal",
    "2": "Conselho Nacional de Justiça",
    "3": "Superior Tribunal de Justiça",
    "4": "Justiça Federal",
    "5": "Justiça do Trabalho",
    "6": "Justiça Eleitoral",
    "7": "Justiça Militar da União",
    "8": "Justiça Estadual",
    "9": "Justiça Militar Estadual",
}

_MASCARA = re.compile(r"^(\d{7})-(\d{2})\.(\d{4})\.(\d)\.(\d{2})\.(\d{4})$")


@dataclass(frozen=True)
class NumeroCNJ:
    sequencial: str
    dv: str
    ano: str
    segmento: str
    tribunal: str
    origem: str

    def formatado(self) -> str:
        return f"{self.sequencial}-{self.dv}.{self.ano}.{self.segmento}.{self.tribunal}.{self.origem}"


def somente_digitos(numero: str) -> str:
    return re.sub(r"\D", "", numero or "")


def calcular_dv(sequencial: str, ano: str, segmento: str, tribunal: str, origem: str) -> str:
    """Calcula os dois dígitos verificadores pelo módulo 97."""
    base = f"{int(sequencial):07d}{int(ano):04d}{int(segmento):01d}{int(tribunal):02d}{int(origem):04d}"
    resto = int(base + "00") % 97
    return f"{98 - resto:02d}"


def montar(sequencial: int, ano: int, segmento: int, tribunal: int, origem: int) -> str:
    """Monta um número CNJ válido (com DV correto) a partir das partes."""
    partes = (f"{sequencial:07d}", f"{ano:04d}", f"{segmento:d}", f"{tribunal:02d}", f"{origem:04d}")
    dv = calcular_dv(*partes)
    return NumeroCNJ(partes[0], dv, partes[1], partes[2], partes[3], partes[4]).formatado()


def decompor(numero: str) -> NumeroCNJ:
    """Aceita o número com ou sem máscara. Levanta ValueError se não tiver 20 dígitos."""
    numero = (numero or "").strip()
    m = _MASCARA.match(numero)
    if m:
        return NumeroCNJ(*m.groups())
    digitos = somente_digitos(numero)
    if len(digitos) != 20:
        raise ValueError(f"Número CNJ precisa ter 20 dígitos (NNNNNNN-DD.AAAA.J.TR.OOOO); recebi {len(digitos)}.")
    return NumeroCNJ(digitos[0:7], digitos[7:9], digitos[9:13], digitos[13], digitos[14:16], digitos[16:20])


def validar(numero: str) -> dict:
    """Valida o número e devolve um diagnóstico legível (nunca levanta exceção)."""
    try:
        n = decompor(numero)
    except ValueError as erro:
        return {"valido": False, "motivo": str(erro), "entrada": numero}

    esperado = calcular_dv(n.sequencial, n.ano, n.segmento, n.tribunal, n.origem)
    conferencia = int(f"{n.sequencial}{n.ano}{n.segmento}{n.tribunal}{n.origem}{n.dv}") % 97
    valido = conferencia == 1 and esperado == n.dv
    resultado = {
        "valido": valido,
        "entrada": numero,
        "formatado": n.formatado(),
        "partes": {
            "sequencial": n.sequencial,
            "dv_informado": n.dv,
            "ano": n.ano,
            "segmento": n.segmento,
            "segmento_nome": SEGMENTOS.get(n.segmento, "segmento desconhecido"),
            "tribunal": n.tribunal,
            "origem": n.origem,
        },
    }
    if not valido:
        resultado["dv_esperado"] = esperado
        resultado["motivo"] = f"Dígito verificador não confere: informado {n.dv}, esperado {esperado}."
    if n.segmento not in SEGMENTOS:
        resultado["valido"] = False
        resultado["motivo"] = f"Segmento do Judiciário '{n.segmento}' não existe (use 1 a 9)."
    return resultado


def normalizar(numero: str) -> str:
    """Devolve o número formatado se for válido; levanta ValueError se não for."""
    diag = validar(numero)
    if not diag["valido"]:
        raise ValueError(diag["motivo"])
    return diag["formatado"]
