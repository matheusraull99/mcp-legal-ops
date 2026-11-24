"""Integração de ponta a ponta: sobe o servidor como subprocesso e fala MCP por stdio."""

import json
import sys
from pathlib import Path

from conftest import rodar
from mcp import Client, StdioServerParameters

RAIZ = Path(__file__).resolve().parents[1]


def test_servidor_stdio_lista_e_chama_tools(tmp_path):
    parametros = StdioServerParameters(
        command=sys.executable,
        args=["-m", "legal_ops.server"],
        env={
            "LEGAL_OPS_DB": str(tmp_path / "stdio.db"),  # não existe: o servidor cria e popula sozinho
            "LEGAL_OPS_HOJE": "2026-11-24",
            "PYTHONPATH": str(RAIZ / "src"),
        },
        cwd=str(RAIZ),
    )

    async def sessao():
        async with Client(parametros) as c:
            nomes = sorted(t.name for t in (await c.list_tools()).tools)
            fila = await c.call_tool("prazos_vencendo", {"dias": 7})
            calc = await c.call_tool("calcular_prazo", {"data_intimacao": "2026-11-14", "dias_uteis": 5})
            recurso = await c.read_resource("manual://glossario")
            return nomes, fila, calc, recurso

    nomes, fila, calc, recurso = rodar(sessao())
    assert nomes == sorted(
        [
            "buscar_processo",
            "calcular_prazo",
            "kpis_escritorio",
            "prazos_vencendo",
            "registrar_andamento",
            "validar_numero_cnj",
        ]
    )
    assert not fila.is_error and json.loads(fila.content[0].text)["total"] > 0
    assert calc.structured_content["vencimento"] == "2026-11-24"
    assert "Número CNJ" in recurso.contents[0].text
    assert (tmp_path / "stdio.db").exists()
