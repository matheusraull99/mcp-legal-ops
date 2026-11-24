import asyncio
import json
from datetime import date

import pytest

from legal_ops import db, seed

HOJE = date(2026, 11, 24)


@pytest.fixture
def base(tmp_path, monkeypatch):
    """Base fictícia nova por teste, com data de referência fixa."""
    caminho = tmp_path / "escritorio.db"
    monkeypatch.setenv("LEGAL_OPS_DB", str(caminho))
    monkeypatch.setenv("LEGAL_OPS_HOJE", HOJE.isoformat())
    conn = db.conectar(caminho)
    seed.gerar(conn, HOJE)
    yield conn
    conn.close()


def rodar(coro):
    return asyncio.run(coro)


async def chamar(nome: str, args: dict):
    """Chama uma tool pelo cliente MCP oficial, conectado em processo ao servidor."""
    from mcp import Client

    from legal_ops.server import mcp

    async with Client(mcp) as cliente:
        return await cliente.call_tool(nome, args)


def chamar_tool(nome: str, args: dict):
    r = rodar(chamar(nome, args))
    dados = r.structured_content
    if dados is None and not r.is_error:
        dados = json.loads(r.content[0].text)
    return r, dados
