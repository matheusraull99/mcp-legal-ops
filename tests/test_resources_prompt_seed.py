from datetime import date

from conftest import HOJE, rodar
from mcp import Client

from legal_ops import cnj, db, seed
from legal_ops.server import mcp


def test_resources_da_base_de_conhecimento(base):
    async def ler():
        async with Client(mcp) as c:
            lista = (await c.list_resources()).resources
            texto = await c.read_resource("manual://controle-de-prazos")
            return lista, texto

    lista, texto = rodar(ler())
    uris = {str(r.uri) for r in lista}
    assert {"manual://regimento-interno", "manual://controle-de-prazos", "manual://glossario"} <= uris
    assert "Margem de segurança" in texto.contents[0].text


def test_resource_template_de_feriados(base):
    async def ler():
        async with Client(mcp) as c:
            return await c.read_resource("escritorio://feriados/2026")

    texto = rodar(ler()).contents[0].text
    assert "2026-04-03" in texto and "Sexta-feira Santa" in texto


def test_prompt_relatorio_semanal(base):
    async def pegar():
        async with Client(mcp) as c:
            nomes = [p.name for p in (await c.list_prompts()).prompts]
            p = await c.get_prompt("relatorio_semanal", {"advogado": "Camila Toledo"})
            return nomes, p.messages[0].content.text

    nomes, texto = rodar(pegar())
    assert "relatorio_semanal" in nomes
    assert 'prazos_vencendo(dias=7, advogado="Camila Toledo")' in texto
    assert "kpis_escritorio" in texto


def test_seed_e_deterministico_e_todos_os_cnj_sao_validos(tmp_path):
    numeros = []
    for nome in ("a.db", "b.db"):
        conn = db.conectar(tmp_path / nome)
        seed.gerar(conn, HOJE)
        numeros.append([r[0] for r in conn.execute("SELECT numero_cnj FROM processos ORDER BY id")])
        conn.close()
    assert numeros[0] == numeros[1]
    assert all(cnj.validar(n)["valido"] for n in numeros[0])


def test_seed_vencimentos_batem_com_o_motor(base):
    from legal_ops import prazos

    for r in base.execute("SELECT data_intimacao, dias_uteis, data_vencimento FROM prazos LIMIT 50"):
        calc = prazos.calcular_prazo(date.fromisoformat(r["data_intimacao"]), r["dias_uteis"])
        assert calc["vencimento"] == r["data_vencimento"]
