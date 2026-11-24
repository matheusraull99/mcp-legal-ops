"""Regras de negócio. Funções puras sobre uma conexão SQLite, sem nada de MCP.

O servidor MCP (server.py) só traduz entre o protocolo e estas funções; assim
dá para testar a regra sem subir servidor nenhum.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime, timedelta

from . import cnj, prazos

TIPOS_ANDAMENTO = (
    "despacho",
    "decisao",
    "sentenca",
    "peticao",
    "audiencia",
    "intimacao",
    "citacao",
    "acordo",
    "outro",
)
LIMITE_RESULTADOS = 10


class ErroDeNegocio(ValueError):
    """Erro previsto (entrada inválida, registro inexistente). A mensagem vai para o modelo."""


# ---------------------------------------------------------------- auditoria


def auditar(
    conn: sqlite3.Connection, *, quem: str, origem: str, acao: str, alvo: str, resultado: str, detalhes: dict
) -> int:
    cur = conn.execute(
        "INSERT INTO auditoria (quando, quem, origem, acao, alvo, resultado, detalhes) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            datetime.now().isoformat(timespec="seconds"),
            quem,
            origem,
            acao,
            alvo,
            resultado,
            json.dumps(detalhes, ensure_ascii=False, sort_keys=True),
        ),
    )
    conn.commit()
    return cur.lastrowid


def ultimas_auditorias(conn: sqlite3.Connection, limite: int = 20) -> list[dict]:
    rows = conn.execute("SELECT * FROM auditoria ORDER BY id DESC LIMIT ?", (limite,)).fetchall()
    return [dict(r) | {"detalhes": json.loads(r["detalhes"])} for r in rows]


# ---------------------------------------------------------------- consultas


def _processo_por_numero(conn: sqlite3.Connection, numero: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM processos WHERE numero_cnj = ?", (numero,)).fetchone()


def _resumo_processo(conn: sqlite3.Connection, p: sqlite3.Row, hoje: date, detalhar: bool) -> dict:
    cliente = conn.execute("SELECT nome, tipo FROM clientes WHERE id = ?", (p["cliente_id"],)).fetchone()
    advogado = conn.execute("SELECT nome, oab FROM advogados WHERE id = ?", (p["advogado_id"],)).fetchone()
    resumo = {
        "numero_cnj": p["numero_cnj"],
        "cliente": cliente["nome"],
        "cliente_tipo": cliente["tipo"],
        "polo_do_cliente": p["polo"],
        "parte_contraria": p["parte_contraria"],
        "area": p["area"],
        "classe": p["classe"],
        "orgao": p["orgao"],
        "status": p["status"],
        "advogado_responsavel": f"{advogado['nome']} ({advogado['oab']})",
        "valor_causa": p["valor_causa"],
        "data_distribuicao": p["data_distribuicao"],
    }
    if detalhar:
        andamentos = conn.execute(
            "SELECT data, tipo, descricao FROM andamentos WHERE processo_id = ? ORDER BY data DESC, id DESC LIMIT 5",
            (p["id"],),
        ).fetchall()
        abertos = conn.execute(
            "SELECT id, descricao, data_vencimento FROM prazos WHERE processo_id = ? AND status = 'aberto' "
            "ORDER BY data_vencimento",
            (p["id"],),
        ).fetchall()
        resumo["ultimos_andamentos"] = [dict(a) for a in andamentos]
        resumo["prazos_abertos"] = [
            dict(x) | {"dias_uteis_restantes": prazos.dias_uteis_entre(hoje, date.fromisoformat(x["data_vencimento"]))}
            for x in abertos
        ]
    return resumo


def buscar_processo(conn: sqlite3.Connection, termo: str, hoje: date) -> dict:
    termo = (termo or "").strip()
    if len(termo) < 3:
        raise ErroDeNegocio("Informe pelo menos 3 caracteres: número CNJ (com ou sem máscara) ou nome do cliente.")

    digitos = cnj.somente_digitos(termo)
    if len(digitos) == 20:
        numero = cnj.decompor(digitos).formatado()
        p = _processo_por_numero(conn, numero)
        if p is None:
            diag = cnj.validar(numero)
            aviso = "" if diag["valido"] else f" Atenção: o número é inválido ({diag['motivo']})"
            return {
                "encontrados": 0,
                "processos": [],
                "mensagem": f"Nenhum processo {numero} na base.{aviso}",
            }
        return {"encontrados": 1, "processos": [_resumo_processo(conn, p, hoje, detalhar=True)]}

    padrao = f"%{termo}%"
    rows = conn.execute(
        "SELECT p.* FROM processos p JOIN clientes c ON c.id = p.cliente_id "
        "WHERE c.nome LIKE ? OR p.parte_contraria LIKE ? OR p.numero_cnj LIKE ? "
        "ORDER BY p.status = 'ativo' DESC, p.data_distribuicao DESC LIMIT ?",
        (padrao, padrao, padrao, LIMITE_RESULTADOS + 1),
    ).fetchall()
    detalhar = len(rows) <= 3
    resultado = {
        "encontrados": min(len(rows), LIMITE_RESULTADOS),
        "processos": [_resumo_processo(conn, p, hoje, detalhar) for p in rows[:LIMITE_RESULTADOS]],
    }
    if len(rows) > LIMITE_RESULTADOS:
        resultado["mensagem"] = f"Mais de {LIMITE_RESULTADOS} resultados; refine a busca."
    return resultado


def prazos_vencendo(
    conn: sqlite3.Connection,
    dias: int,
    hoje: date,
    advogado: str | None = None,
    incluir_atrasados: bool = True,
) -> dict:
    if not 0 <= dias <= 90:
        raise ErroDeNegocio("'dias' deve estar entre 0 e 90.")
    limite = hoje + timedelta(days=dias)
    sql = (
        "SELECT z.id, z.descricao, z.data_intimacao, z.dias_uteis, z.data_vencimento, p.numero_cnj, p.area, "
        "c.nome AS cliente, a.nome AS responsavel "
        "FROM prazos z JOIN processos p ON p.id = z.processo_id JOIN clientes c ON c.id = p.cliente_id "
        "JOIN advogados a ON a.id = z.responsavel_id "
        "WHERE z.status = 'aberto' AND z.data_vencimento <= ? AND z.data_vencimento >= ? "
    )
    params: list = [limite.isoformat(), (date.min if incluir_atrasados else hoje).isoformat()]
    if advogado:
        sql += "AND a.nome LIKE ? "
        params.append(f"%{advogado.strip()}%")
    sql += "ORDER BY z.data_vencimento, z.id"
    itens = []
    for r in conn.execute(sql, params).fetchall():
        venc = date.fromisoformat(r["data_vencimento"])
        restantes = prazos.dias_uteis_entre(hoje, venc)
        situacao = "ATRASADO" if venc < hoje else ("VENCE HOJE" if venc == hoje else "a vencer")
        itens.append(dict(r) | {"dias_uteis_restantes": restantes, "situacao": situacao})
    return {
        "data_referencia": hoje.isoformat(),
        "janela": f"{hoje.isoformat()} a {limite.isoformat()}",
        "total": len(itens),
        "atrasados": sum(1 for i in itens if i["situacao"] == "ATRASADO"),
        "prazos": itens,
    }


def kpis(conn: sqlite3.Connection, hoje: date, periodo_dias: int = 90) -> dict:
    if not 7 <= periodo_dias <= 730:
        raise ErroDeNegocio("'periodo_dias' deve estar entre 7 e 730.")
    inicio = (hoje - timedelta(days=periodo_dias)).isoformat()
    h = hoje.isoformat()

    st = {
        r["status"]: r["n"]
        for r in conn.execute(
            "SELECT status, COUNT(*) n FROM prazos WHERE data_vencimento BETWEEN ? AND ? GROUP BY status",
            (inicio, h),
        )
    }
    vencidos_em_aberto = conn.execute(
        "SELECT COUNT(*) FROM prazos WHERE status = 'aberto' AND data_vencimento < ?", (h,)
    ).fetchone()[0]
    cumpridos = st.get("cumprido", 0)
    perdidos = st.get("perdido", 0)
    decididos = cumpridos + perdidos

    volume = [
        dict(r)
        for r in conn.execute(
            "SELECT area, COUNT(*) processos_ativos, ROUND(SUM(valor_causa), 2) valor_em_disputa "
            "FROM processos WHERE status = 'ativo' GROUP BY area ORDER BY processos_ativos DESC"
        )
    ]
    carga = [
        dict(r)
        for r in conn.execute(
            "SELECT a.nome AS advogado, "
            " (SELECT COUNT(*) FROM processos p WHERE p.advogado_id = a.id AND p.status = 'ativo') processos_ativos, "
            " (SELECT COUNT(*) FROM prazos z WHERE z.responsavel_id = a.id AND z.status = 'aberto' "
            "    AND z.data_vencimento BETWEEN ? AND ?) prazos_proximos_15_dias, "
            " (SELECT COUNT(*) FROM prazos z WHERE z.responsavel_id = a.id AND z.status = 'perdido' "
            "    AND z.data_vencimento BETWEEN ? AND ?) prazos_perdidos_no_periodo "
            "FROM advogados a WHERE a.ativo = 1 ORDER BY processos_ativos DESC",
            (h, (hoje + timedelta(days=15)).isoformat(), inicio, h),
        )
    ]
    fin = conn.execute(
        "SELECT "
        " ROUND(COALESCE(SUM(CASE WHEN status = 'pendente' AND vencimento < ? THEN valor END), 0), 2) atrasado, "
        " ROUND(COALESCE(SUM(CASE WHEN status = 'pendente' AND vencimento >= ? THEN valor END), 0), 2) a_vencer, "
        " ROUND(COALESCE(SUM(CASE WHEN status = 'pago' AND vencimento BETWEEN ? AND ? THEN valor END), 0), 2) "
        "   recebido_no_periodo "
        "FROM honorarios",
        (h, h, inicio, h),
    ).fetchone()

    return {
        "data_referencia": h,
        "periodo": f"{inicio} a {h}",
        "prazos": {
            "cumpridos": cumpridos,
            "perdidos": perdidos,
            "taxa_cumprimento": round(cumpridos / decididos, 4) if decididos else None,
            "vencidos_ainda_em_aberto": vencidos_em_aberto,
        },
        "volume_por_area": volume,
        "carga_por_advogado": carga,
        "honorarios": dict(fin),
    }


# ---------------------------------------------------------------- escrita


def registrar_andamento(
    conn: sqlite3.Connection,
    *,
    numero_cnj: str,
    tipo: str,
    descricao: str,
    registrado_por: str,
    hoje: date,
    data: str | None = None,
    cumpre_prazo_id: int | None = None,
    confirmar: bool = False,
    origem: str = "mcp",
) -> dict:
    """Valida tudo antes; sem confirmar=True devolve só a prévia (e audita a tentativa)."""
    alvo = numero_cnj

    def recusar(motivo: str) -> None:
        auditar(
            conn,
            quem=registrado_por or "?",
            origem=origem,
            acao="registrar_andamento",
            alvo=alvo,
            resultado="recusado",
            detalhes={"motivo": motivo},
        )
        raise ErroDeNegocio(motivo)

    try:
        numero = cnj.normalizar(numero_cnj)
    except ValueError as erro:
        recusar(f"Número CNJ inválido: {erro}")
    alvo = numero
    processo = _processo_por_numero(conn, numero)
    if processo is None:
        recusar(f"Processo {numero} não existe na base.")
    if processo["status"] == "arquivado":
        recusar(f"Processo {numero} está arquivado; desarquive antes de registrar andamentos.")

    tipo = (tipo or "").strip().lower()
    if tipo not in TIPOS_ANDAMENTO:
        recusar(f"Tipo '{tipo}' inválido. Use um de: {', '.join(TIPOS_ANDAMENTO)}.")
    descricao = " ".join((descricao or "").split())
    if not 10 <= len(descricao) <= 2000:
        recusar("A descrição precisa ter entre 10 e 2000 caracteres.")

    adv = conn.execute(
        "SELECT id, nome FROM advogados WHERE ativo = 1 AND (nome = ? OR oab = ?)",
        (registrado_por.strip(), registrado_por.strip()),
    ).fetchone()
    if adv is None:
        recusar(f"'{registrado_por}' não é advogado ativo do escritório (use o nome completo ou a OAB).")

    try:
        dia = date.fromisoformat(data) if data else hoje
    except ValueError:
        recusar(f"Data '{data}' inválida; use AAAA-MM-DD.")
    if dia > hoje:
        recusar("Não é possível registrar andamento com data futura.")
    if dia < date.fromisoformat(processo["data_distribuicao"]):
        recusar("A data do andamento é anterior à distribuição do processo.")

    prazo = None
    if cumpre_prazo_id is not None:
        prazo = conn.execute(
            "SELECT * FROM prazos WHERE id = ? AND processo_id = ?", (cumpre_prazo_id, processo["id"])
        ).fetchone()
        if prazo is None:
            recusar(f"Prazo {cumpre_prazo_id} não pertence ao processo {numero}.")
        if prazo["status"] != "aberto":
            recusar(f"Prazo {cumpre_prazo_id} já está '{prazo['status']}'.")

    previa = {
        "processo": numero,
        "data": dia.isoformat(),
        "tipo": tipo,
        "descricao": descricao,
        "registrado_por": adv["nome"],
        "baixa_de_prazo": (
            {
                "prazo_id": prazo["id"],
                "descricao": prazo["descricao"],
                "vencimento": prazo["data_vencimento"],
                "cumprido_no_prazo": dia.isoformat() <= prazo["data_vencimento"],
            }
            if prazo
            else None
        ),
    }

    if not confirmar:
        auditar(
            conn,
            quem=adv["nome"],
            origem=origem,
            acao="registrar_andamento",
            alvo=numero,
            resultado="previa",
            detalhes=previa,
        )
        return {
            "gravado": False,
            "confirmacao_necessaria": True,
            "mensagem": "Nada foi gravado. Mostre a prévia ao usuário e, se ele concordar, "
            "chame de novo com confirmar=true.",
            "previa": previa,
        }

    agora = datetime.now().isoformat(timespec="seconds")
    with conn:
        cur = conn.execute(
            "INSERT INTO andamentos (processo_id, data, tipo, descricao, registrado_por, criado_em) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (processo["id"], dia.isoformat(), tipo, descricao, adv["id"], agora),
        )
        andamento_id = cur.lastrowid
        if prazo:
            novo_status = "cumprido" if dia.isoformat() <= prazo["data_vencimento"] else "perdido"
            conn.execute(
                "UPDATE prazos SET status = ?, data_cumprimento = ? WHERE id = ?",
                (novo_status, dia.isoformat(), prazo["id"]),
            )
    audit_id = auditar(
        conn,
        quem=adv["nome"],
        origem=origem,
        acao="registrar_andamento",
        alvo=numero,
        resultado="gravado",
        detalhes=previa | {"andamento_id": andamento_id},
    )
    return {"gravado": True, "andamento_id": andamento_id, "auditoria_id": audit_id, "registro": previa}
