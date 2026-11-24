"""Servidor MCP do escritório (fictício) Andrade & Lacerda Advogados.

Expõe, por stdio, ferramentas (tools), base de conhecimento (resources) e um
roteiro de relatório (prompt). As docstrings abaixo NÃO são comentário para
humanos apenas: são o texto que o modelo lê para decidir quando e como chamar
cada ferramenta. Por isso dizem quando usar, o formato das entradas e o que volta.

Rodar: python -m legal_ops.server   (ou o script `mcp-legal-ops`)
"""

from __future__ import annotations

import os
from collections.abc import Callable
from contextlib import closing
from datetime import date
from importlib import resources as importlib_resources
from typing import Annotated, Any

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp_types import ToolAnnotations
from pydantic import Field

from . import cnj, db, prazos, seed, servicos

INSTRUCOES = (
    "Servidor de operação jurídica de um escritório de advocacia FICTÍCIO (dados sintéticos). "
    "Use buscar_processo para localizar processos, prazos_vencendo para a fila de prazos, "
    "calcular_prazo para contar dias úteis, kpis_escritorio para indicadores e validar_numero_cnj "
    "antes de confiar num número digitado. registrar_andamento grava dados: chame primeiro sem "
    "confirmar (devolve uma prévia), mostre a prévia ao usuário e só repita com confirmar=true "
    "depois do 'sim' explícito dele. A base de conhecimento está nos resources manual://."
)

mcp = MCPServer("legal-ops", instructions=INSTRUCOES, version="0.1.0", log_level="WARNING")

LEITURA = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
ESCRITA = ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False)


def _executar[T](funcao: Callable[..., T], *args, **kwargs) -> T:
    """Abre a base, roda a regra de negócio e converte erro previsto em ToolError legível."""
    caminho = seed.garantir_base()
    with closing(db.conectar(caminho)) as conn:
        try:
            return funcao(conn, *args, **kwargs)
        except servicos.ErroDeNegocio as erro:
            raise ToolError(str(erro)) from erro


def _data(valor: str, campo: str) -> date:
    try:
        return date.fromisoformat(valor.strip())
    except (ValueError, AttributeError) as erro:
        raise ToolError(f"'{campo}' deve estar no formato AAAA-MM-DD; recebi '{valor}'.") from erro


# ---------------------------------------------------------------- tools de leitura


@mcp.tool(annotations=LEITURA)
def buscar_processo(
    termo: Annotated[
        str,
        Field(
            description="Número CNJ (com ou sem máscara) ou parte do nome do cliente "
            "ou da parte contrária. Mínimo 3 caracteres."
        ),
    ],
) -> dict[str, Any]:
    """Localiza processos do escritório.

    Use quando o usuário citar um número de processo, um cliente ou uma parte contrária.
    Com número CNJ completo devolve o processo com os 5 últimos andamentos e os prazos abertos
    (com o id de cada prazo, usado em registrar_andamento). Com nome, devolve até 10 processos;
    se vierem 3 ou menos, já vêm detalhados.
    """
    return _executar(servicos.buscar_processo, termo, db.hoje())


@mcp.tool(annotations=LEITURA)
def prazos_vencendo(
    dias: Annotated[
        int,
        Field(
            ge=0,
            le=90,
            description="Janela em dias corridos a partir de hoje. Ex.: 0 = só hoje, 7 = próxima semana.",
        ),
    ] = 7,
    advogado: Annotated[
        str | None,
        Field(description="Filtra pelo nome (ou parte do nome) do advogado responsável. Omita para o escritório todo."),
    ] = None,
    incluir_atrasados: Annotated[
        bool, Field(description="Inclui prazos já vencidos e ainda não baixados (situação ATRASADO).")
    ] = True,
) -> dict[str, Any]:
    """Lista os prazos abertos que vencem até hoje + `dias`, do mais urgente para o menos urgente.

    Use para "o que vence esta semana?", pauta de reunião ou carga de um advogado. Cada item traz
    processo, cliente, responsável, vencimento, dias úteis restantes e situação
    (ATRASADO, VENCE HOJE, a vencer).
    """
    return _executar(servicos.prazos_vencendo, dias, db.hoje(), advogado, incluir_atrasados)


@mcp.tool(annotations=LEITURA)
def calcular_prazo(
    data_intimacao: Annotated[str, Field(description="Data da intimação no formato AAAA-MM-DD.")],
    dias_uteis: Annotated[
        int,
        Field(ge=1, le=365, description="Tamanho do prazo em dias úteis (ex.: 15 para contestação ou apelação)."),
    ],
) -> dict[str, Any]:
    """Calcula o vencimento de um prazo processual contado em dias úteis (CPC/2015).

    Exclui o dia do começo e inclui o do vencimento; pula sábados, domingos, feriados nacionais
    (inclusive Carnaval, Sexta-feira Santa e Corpus Christi) e o recesso de 20/12 a 20/01.
    Devolve a memória de cálculo com cada dia pulado e o motivo. NÃO considera feriados
    estaduais/municipais nem suspensões decretadas pelo tribunal: avise o usuário disso.
    """
    try:
        return prazos.calcular_prazo(_data(data_intimacao, "data_intimacao"), dias_uteis)
    except ValueError as erro:
        raise ToolError(str(erro)) from erro


@mcp.tool(annotations=LEITURA)
def validar_numero_cnj(
    numero: Annotated[str, Field(description="Número do processo, com ou sem máscara.")],
) -> dict[str, Any]:
    """Confere se um número de processo segue o padrão CNJ (NNNNNNN-DD.AAAA.J.TR.OOOO) e se o
    dígito verificador (módulo 97) bate. Devolve as partes decodificadas (ano, segmento, tribunal,
    origem) e, se inválido, o dígito esperado. Use antes de registrar algo a partir de um número
    digitado ou copiado de e-mail.
    """
    return cnj.validar(numero)


@mcp.tool(annotations=LEITURA)
def kpis_escritorio(
    periodo_dias: Annotated[
        int,
        Field(
            ge=7,
            le=730,
            description="Janela retroativa, em dias, para prazos cumpridos/perdidos e honorários recebidos.",
        ),
    ] = 90,
) -> dict[str, Any]:
    """Indicadores do escritório: prazos cumpridos x perdidos (e taxa de cumprimento) no período,
    prazos vencidos ainda em aberto, volume de processos ativos e valor em disputa por área,
    carga por advogado (processos ativos, prazos nos próximos 15 dias, prazos perdidos) e
    honorários (atrasados, a vencer, recebidos no período).
    """
    return _executar(servicos.kpis, db.hoje(), periodo_dias)


# ---------------------------------------------------------------- tool de escrita


@mcp.tool(annotations=ESCRITA)
def registrar_andamento(
    numero_cnj: Annotated[str, Field(description="Número CNJ do processo.")],
    tipo: Annotated[str, Field(description="Um de: " + ", ".join(servicos.TIPOS_ANDAMENTO) + ".")],
    descricao: Annotated[str, Field(description="Texto do andamento, 10 a 2000 caracteres.")],
    registrado_por: Annotated[
        str,
        Field(description="Nome completo ou OAB do advogado que está registrando (precisa ser do escritório)."),
    ],
    data: Annotated[
        str | None, Field(description="Data do ato, AAAA-MM-DD. Padrão: hoje. Não aceita data futura.")
    ] = None,
    cumpre_prazo_id: Annotated[
        int | None, Field(description="Id do prazo aberto que este andamento cumpre (dá baixa no prazo).")
    ] = None,
    confirmar: Annotated[
        bool,
        Field(
            description="false = só valida e devolve a prévia, nada é gravado. "
            "true = grava. Só use true depois que o usuário "
            "aprovar a prévia explicitamente."
        ),
    ] = False,
) -> dict[str, Any]:
    """Registra um andamento num processo e, opcionalmente, dá baixa num prazo. ESCREVE NA BASE.

    Protocolo obrigatório: (1) chame com confirmar=false para validar e obter a prévia;
    (2) mostre a prévia ao usuário e peça confirmação; (3) só então chame de novo com os mesmos
    dados e confirmar=true. Toda chamada (prévia, recusa ou gravação) entra na trilha de auditoria
    com quem, quando e o quê. Andamentos não podem ser editados nem apagados por aqui.
    """
    origem = f"mcp:{os.environ.get('LEGAL_OPS_CLIENTE', 'stdio')}"
    return _executar(
        servicos.registrar_andamento,
        numero_cnj=numero_cnj,
        tipo=tipo,
        descricao=descricao,
        registrado_por=registrado_por,
        hoje=db.hoje(),
        data=data,
        cumpre_prazo_id=cumpre_prazo_id,
        confirmar=confirmar,
        origem=origem,
    )


# ---------------------------------------------------------------- resources


def _ler_conhecimento(arquivo: str) -> str:
    return importlib_resources.files("legal_ops").joinpath("conhecimento", arquivo).read_text(encoding="utf-8")


@mcp.resource(
    "manual://regimento-interno",
    name="regimento-interno",
    mime_type="text/markdown",
    description="Regimento interno: áreas, distribuição, regras de andamento e honorários.",
)
def regimento_interno() -> str:
    return _ler_conhecimento("regimento-interno.md")


@mcp.resource(
    "manual://controle-de-prazos",
    name="manual-de-prazos",
    mime_type="text/markdown",
    description="Manual de controle de prazos: responsável, cadastro, margem de segurança, baixa.",
)
def manual_prazos() -> str:
    return _ler_conhecimento("manual-prazos.md")


@mcp.resource(
    "manual://glossario",
    name="glossario",
    mime_type="text/markdown",
    description="Glossário jurídico para quem não é da área (CNJ, intimação, dias úteis...).",
)
def glossario() -> str:
    return _ler_conhecimento("glossario.md")


@mcp.resource(
    "escritorio://feriados/{ano}",
    name="feriados-do-ano",
    mime_type="application/json",
    description="Feriados nacionais considerados pelo motor de prazos no ano informado.",
)
def feriados(ano: str) -> dict[str, Any]:
    a = int(ano)
    if not 1900 <= a <= 2200:
        raise ValueError("Ano fora do intervalo suportado (1900-2200).")
    return {
        "ano": a,
        "feriados": {d.isoformat(): nome for d, nome in sorted(prazos.feriados_nacionais(a).items())},
        "recesso_forense": f"{a}-12-20 a {a + 1}-01-20",
    }


# ---------------------------------------------------------------- prompt


@mcp.prompt(name="relatorio_semanal", title="Relatório semanal de prazos e KPIs")
def relatorio_semanal(advogado: str | None = None) -> str:
    """Roteiro para o agente montar o relatório da reunião de segunda-feira."""
    foco = f"com foco em {advogado}" if advogado else "do escritório inteiro"
    filtro = f', advogado="{advogado}"' if advogado else ""
    return (
        f"Monte o relatório semanal {foco} para a reunião de segunda-feira.\n\n"
        "Passos:\n"
        f"1. Chame prazos_vencendo(dias=7{filtro}) e kpis_escritorio(periodo_dias=30).\n"
        "2. Leia o resource manual://controle-de-prazos para aplicar a margem de segurança.\n"
        "3. Escreva em português, nesta ordem:\n"
        "   - Atrasados (se houver) — primeiro e em destaque, com processo, cliente e responsável.\n"
        "   - Prazos da semana, agrupados por dia de vencimento.\n"
        "   - Prazos que já estão dentro da margem de 2 dias úteis.\n"
        "   - KPIs: taxa de cumprimento, perdidos no período, carga por advogado (aponte quem passa "
        "de 20 processos ativos) e honorários atrasados.\n"
        "   - Até 3 ações recomendadas, cada uma com dono.\n"
        "4. Não invente dado: se uma ferramenta falhar, diga qual e siga com o resto.\n"
        "5. Não registre nada na base durante o relatório."
    )


def main() -> None:
    seed.garantir_base()
    mcp.run("stdio")


if __name__ == "__main__":
    main()
