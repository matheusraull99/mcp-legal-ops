"""Cada tool chamada pelo cliente MCP oficial (em processo), contra uma base fictícia nova."""

from conftest import HOJE, chamar_tool, rodar
from mcp import Client

from legal_ops import cnj, servicos
from legal_ops.server import mcp


def _um_processo_ativo(conn):
    return conn.execute("SELECT * FROM processos WHERE status = 'ativo' ORDER BY id LIMIT 1").fetchone()


def _prazo_aberto(conn):
    return conn.execute(
        "SELECT z.*, p.numero_cnj FROM prazos z JOIN processos p ON p.id = z.processo_id "
        "WHERE z.status = 'aberto' ORDER BY z.data_vencimento LIMIT 1"
    ).fetchone()


def test_lista_as_seis_tools_com_descricao(base):
    async def listar():
        async with Client(mcp) as c:
            return (await c.list_tools()).tools

    tools = {t.name: t for t in rodar(listar())}
    assert set(tools) == {
        "buscar_processo",
        "prazos_vencendo",
        "calcular_prazo",
        "registrar_andamento",
        "kpis_escritorio",
        "validar_numero_cnj",
    }
    assert all(len(t.description or "") > 80 for t in tools.values())
    assert tools["registrar_andamento"].annotations.read_only_hint is False
    assert tools["buscar_processo"].annotations.read_only_hint is True


def test_buscar_processo_por_numero_traz_andamentos_e_prazos(base):
    p = _um_processo_ativo(base)
    r, dados = chamar_tool("buscar_processo", {"termo": cnj.somente_digitos(p["numero_cnj"])})
    assert not r.is_error
    assert dados["encontrados"] == 1
    proc = dados["processos"][0]
    assert proc["numero_cnj"] == p["numero_cnj"]
    assert "ultimos_andamentos" in proc and "prazos_abertos" in proc


def test_buscar_processo_por_nome_do_cliente(base):
    nome = base.execute("SELECT c.nome FROM clientes c JOIN processos p ON p.cliente_id = c.id LIMIT 1").fetchone()[
        "nome"
    ]
    r, dados = chamar_tool("buscar_processo", {"termo": nome.split()[-1]})
    assert not r.is_error
    assert dados["encontrados"] >= 1


def test_buscar_processo_com_termo_curto_da_erro_legivel(base):
    r, _ = chamar_tool("buscar_processo", {"termo": "ab"})
    assert r.is_error
    assert "3 caracteres" in r.content[0].text


def test_busca_nao_executa_sql_injetado(base):
    r, dados = chamar_tool("buscar_processo", {"termo": "x'; DROP TABLE processos; --"})
    assert not r.is_error
    assert dados["encontrados"] == 0
    assert base.execute("SELECT COUNT(*) FROM processos").fetchone()[0] == 80


def test_prazos_vencendo_respeita_janela_e_ordem(base):
    r, dados = chamar_tool("prazos_vencendo", {"dias": 7, "incluir_atrasados": False})
    assert not r.is_error
    vencs = [p["data_vencimento"] for p in dados["prazos"]]
    assert vencs == sorted(vencs)
    assert all(HOJE.isoformat() <= v <= "2026-12-01" for v in vencs)
    assert dados["total"] > 0


def test_prazos_vencendo_filtra_por_advogado(base):
    _, dados = chamar_tool("prazos_vencendo", {"dias": 30, "advogado": "Rafael"})
    assert dados["prazos"]
    assert {p["responsavel"] for p in dados["prazos"]} == {"Rafael Lacerda"}


def test_prazos_vencendo_rejeita_janela_fora_do_schema(base):
    r, _ = chamar_tool("prazos_vencendo", {"dias": 500})
    assert r.is_error


def test_calcular_prazo_tool(base):
    r, dados = chamar_tool("calcular_prazo", {"data_intimacao": "2026-12-18", "dias_uteis": 5})
    assert not r.is_error
    assert dados["vencimento"] == "2027-01-27"


def test_calcular_prazo_com_data_invalida(base):
    r, _ = chamar_tool("calcular_prazo", {"data_intimacao": "18/12/2026", "dias_uteis": 5})
    assert r.is_error
    assert "AAAA-MM-DD" in r.content[0].text


def test_validar_numero_cnj_tool(base):
    numero = _um_processo_ativo(base)["numero_cnj"]
    _, ok = chamar_tool("validar_numero_cnj", {"numero": numero})
    assert ok["valido"] is True
    _, ruim = chamar_tool("validar_numero_cnj", {"numero": numero[:8] + "99" + numero[10:]})
    assert ruim["valido"] is (numero[8:10] == "99")


def test_kpis_escritorio(base):
    r, k = chamar_tool("kpis_escritorio", {"periodo_dias": 90})
    assert not r.is_error
    assert 0 <= k["prazos"]["taxa_cumprimento"] <= 1
    assert len(k["carga_por_advogado"]) == 6
    ativos = base.execute("SELECT COUNT(*) FROM processos WHERE status = 'ativo'").fetchone()[0]
    assert sum(a["processos_ativos"] for a in k["volume_por_area"]) == ativos


# ---------------------------------------------------------------- guardrails de escrita


def _pedido(prazo, **extra):
    return {
        "numero_cnj": prazo["numero_cnj"],
        "tipo": "peticao",
        "descricao": "Protocolada a petição correspondente ao prazo.",
        "registrado_por": "Helena Andrade",
        "cumpre_prazo_id": prazo["id"],
    } | extra


def _contar(conn, tabela):
    return conn.execute(f"SELECT COUNT(*) FROM {tabela}").fetchone()[0]


def test_sem_confirmar_nao_grava_e_audita_previa(base):
    prazo = _prazo_aberto(base)
    antes = _contar(base, "andamentos")
    r, dados = chamar_tool("registrar_andamento", _pedido(prazo))
    assert not r.is_error
    assert dados["gravado"] is False and dados["confirmacao_necessaria"] is True
    assert _contar(base, "andamentos") == antes
    audit = servicos.ultimas_auditorias(base, 1)[0]
    assert audit["resultado"] == "previa" and audit["quem"] == "Helena Andrade"


def test_com_confirmar_grava_baixa_prazo_e_audita(base):
    prazo = _prazo_aberto(base)
    antes = _contar(base, "andamentos")
    r, dados = chamar_tool("registrar_andamento", _pedido(prazo, confirmar=True))
    assert not r.is_error and dados["gravado"] is True
    assert _contar(base, "andamentos") == antes + 1
    novo = base.execute("SELECT status FROM prazos WHERE id = ?", (prazo["id"],)).fetchone()
    assert novo["status"] == "cumprido"
    audit = servicos.ultimas_auditorias(base, 1)[0]
    assert audit["resultado"] == "gravado"
    assert audit["detalhes"]["andamento_id"] == dados["andamento_id"]


def test_advogado_de_fora_e_recusado_e_auditado(base):
    prazo = _prazo_aberto(base)
    r, _ = chamar_tool("registrar_andamento", _pedido(prazo, registrado_por="Fulano Externo", confirmar=True))
    assert r.is_error
    assert servicos.ultimas_auditorias(base, 1)[0]["resultado"] == "recusado"


def test_data_futura_e_recusada(base):
    prazo = _prazo_aberto(base)
    r, _ = chamar_tool("registrar_andamento", _pedido(prazo, data="2026-12-31", confirmar=True))
    assert r.is_error and "futura" in r.content[0].text


def test_processo_arquivado_nao_aceita_andamento(base):
    arq = base.execute("SELECT numero_cnj FROM processos WHERE status = 'arquivado' LIMIT 1").fetchone()
    r, _ = chamar_tool(
        "registrar_andamento",
        {
            "numero_cnj": arq["numero_cnj"],
            "tipo": "outro",
            "descricao": "Tentativa em processo arquivado.",
            "registrado_por": "Helena Andrade",
            "confirmar": True,
        },
    )
    assert r.is_error and "arquivado" in r.content[0].text


def test_prazo_de_outro_processo_e_recusado(base):
    prazo = _prazo_aberto(base)
    outro = base.execute(
        "SELECT numero_cnj FROM processos WHERE status = 'ativo' AND id != ? LIMIT 1", (prazo["processo_id"],)
    ).fetchone()
    r, _ = chamar_tool("registrar_andamento", _pedido(prazo, numero_cnj=outro["numero_cnj"], confirmar=True))
    assert r.is_error and "não pertence" in r.content[0].text


def test_tipo_invalido_e_cnj_invalido(base):
    prazo = _prazo_aberto(base)
    r1, _ = chamar_tool("registrar_andamento", _pedido(prazo, tipo="mandinga"))
    r2, _ = chamar_tool("registrar_andamento", _pedido(prazo, numero_cnj="1234567-00.2020.8.26.0001"))
    assert r1.is_error and r2.is_error
    assert [a["resultado"] for a in servicos.ultimas_auditorias(base, 2)] == ["recusado", "recusado"]
