"""Acesso ao SQLite. Só consultas parametrizadas: nenhum SQL livre sai daqui."""

from __future__ import annotations

import os
import sqlite3
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
CAMINHO_PADRAO = RAIZ / "data" / "escritorio.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS advogados (
    id INTEGER PRIMARY KEY,
    nome TEXT NOT NULL,
    oab TEXT NOT NULL UNIQUE,
    area_principal TEXT NOT NULL,
    ativo INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS clientes (
    id INTEGER PRIMARY KEY,
    nome TEXT NOT NULL,
    tipo TEXT NOT NULL CHECK (tipo IN ('PF', 'PJ')),
    email TEXT NOT NULL,
    cidade TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS processos (
    id INTEGER PRIMARY KEY,
    numero_cnj TEXT NOT NULL UNIQUE,
    cliente_id INTEGER NOT NULL REFERENCES clientes(id),
    polo TEXT NOT NULL CHECK (polo IN ('ativo', 'passivo')),
    parte_contraria TEXT NOT NULL,
    area TEXT NOT NULL,
    classe TEXT NOT NULL,
    orgao TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('ativo', 'suspenso', 'arquivado')),
    advogado_id INTEGER NOT NULL REFERENCES advogados(id),
    valor_causa REAL NOT NULL,
    data_distribuicao TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS andamentos (
    id INTEGER PRIMARY KEY,
    processo_id INTEGER NOT NULL REFERENCES processos(id),
    data TEXT NOT NULL,
    tipo TEXT NOT NULL,
    descricao TEXT NOT NULL,
    registrado_por INTEGER REFERENCES advogados(id),
    criado_em TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS prazos (
    id INTEGER PRIMARY KEY,
    processo_id INTEGER NOT NULL REFERENCES processos(id),
    descricao TEXT NOT NULL,
    data_intimacao TEXT NOT NULL,
    dias_uteis INTEGER NOT NULL,
    data_vencimento TEXT NOT NULL,
    responsavel_id INTEGER NOT NULL REFERENCES advogados(id),
    status TEXT NOT NULL CHECK (status IN ('aberto', 'cumprido', 'perdido')),
    data_cumprimento TEXT
);

CREATE TABLE IF NOT EXISTS honorarios (
    id INTEGER PRIMARY KEY,
    processo_id INTEGER NOT NULL REFERENCES processos(id),
    tipo TEXT NOT NULL CHECK (tipo IN ('contratual', 'exito', 'mensal')),
    valor REAL NOT NULL,
    vencimento TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('pago', 'pendente'))
);

CREATE TABLE IF NOT EXISTS auditoria (
    id INTEGER PRIMARY KEY,
    quando TEXT NOT NULL,
    quem TEXT NOT NULL,
    origem TEXT NOT NULL,
    acao TEXT NOT NULL,
    alvo TEXT NOT NULL,
    resultado TEXT NOT NULL,
    detalhes TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_prazos_venc ON prazos (status, data_vencimento);
CREATE INDEX IF NOT EXISTS ix_andamentos_proc ON andamentos (processo_id, data);
"""


def caminho_banco() -> Path:
    return Path(os.environ.get("LEGAL_OPS_DB") or CAMINHO_PADRAO)


def hoje() -> date:
    """Data de referência. LEGAL_OPS_HOJE=AAAA-MM-DD fixa a data (demo e testes)."""
    valor = os.environ.get("LEGAL_OPS_HOJE")
    return date.fromisoformat(valor) if valor else date.today()


def conectar(caminho: Path | str | None = None) -> sqlite3.Connection:
    conn = sqlite3.connect(str(caminho or caminho_banco()))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def criar_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
