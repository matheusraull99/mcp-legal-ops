"""Agente de demonstração: conecta ao servidor MCP por stdio e roda um loop de tool calling.

Modos:
  offline  roteiro determinístico, sem chave e sem rede (mostra o protocolo funcionando)
  claude   Claude via SDK oficial `anthropic` (ANTHROPIC_API_KEY)
  gemini   Gemini via `google-genai` (GEMINI_API_KEY)

Exemplos:
  python demo_agente.py --modo offline
  python demo_agente.py --modo claude --pergunta "O que vence esta semana?"
  python demo_agente.py --modo gemini --salvar docs/transcricao-gemini.md

O agente nunca acessa o banco diretamente: tudo passa pelas tools MCP. A tool de escrita
(registrar_andamento com confirmar=true) passa ainda por um portão humano aqui no cliente,
além da exigência de confirmação no próprio servidor.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from mcp import Client, StdioServerParameters

RAIZ = Path(__file__).resolve().parent
HOJE_DEMO = "2026-11-24"
MODELO_CLAUDE = "claude-sonnet-5-5"
MODELO_GEMINI = "gemini-3.5-flash"
MODELOS_GEMINI_RESERVA = ["gemini-3.5-flash", "gemini-3.1-flash-lite", "gemini-2.5-flash", "gemini-flash-latest"]
MAX_PASSOS = 15

SISTEMA = (
    "Você é o assistente de operações jurídicas do escritório (fictício) Andrade & Lacerda Advogados. "
    "Responda em português do Brasil, de forma objetiva. Use as ferramentas para obter qualquer dado: "
    "nunca invente número de processo, data ou valor. Ao calcular prazos, lembre que feriados locais e "
    "suspensões do tribunal não entram na conta. Para registrar andamento, chame primeiro com "
    "confirmar=false, mostre a prévia ao usuário e só chame com confirmar=true depois de um 'sim' "
    "explícito dele."
)
PERGUNTA_PADRAO = (
    "Sou a Helena Andrade. Quais prazos meus vencem nos próximos 7 dias? Para o mais urgente, "
    "traga o resumo do processo e confira o vencimento pela contagem de dias úteis."
)


# ---------------------------------------------------------------- transcrição


@dataclass
class Transcricao:
    linhas: list[str] = field(default_factory=list)

    def _emitir(self, texto: str) -> None:
        print(texto, flush=True)
        self.linhas.append(texto)

    def usuario(self, texto: str) -> None:
        self._emitir(f"\n**Usuário:** {texto}\n")

    def agente(self, texto: str) -> None:
        self._emitir(f"\n**Agente:** {texto.strip()}\n")

    def chamada(self, nome: str, args: dict) -> None:
        self._emitir(f"→ `{nome}({json.dumps(args, ensure_ascii=False)})`")

    def resultado(self, texto: str, erro: bool) -> None:
        resumo = texto if len(texto) <= 400 else texto[:400] + " …"
        self._emitir(f"  ← {'ERRO: ' if erro else ''}{' '.join(resumo.split())}")

    def nota(self, texto: str) -> None:
        self._emitir(f"_{texto}_")

    def salvar(self, caminho: Path) -> None:
        caminho.parent.mkdir(parents=True, exist_ok=True)
        caminho.write_text("\n".join(self.linhas) + "\n", encoding="utf-8")


# ---------------------------------------------------------------- ponte MCP


class PonteMCP:
    """Executa tools no servidor MCP e aplica o portão humano para escrita."""

    def __init__(self, cliente: Client, log: Transcricao, auto_aprovar: bool, aprovacao_fixa: str | None = None):
        self.cliente = cliente
        self.log = log
        self.auto_aprovar = auto_aprovar
        self.aprovacao_fixa = aprovacao_fixa

    async def listar(self) -> list:
        return (await self.cliente.list_tools()).tools

    def _aprovado(self, nome: str, args: dict) -> bool:
        if nome != "registrar_andamento" or not args.get("confirmar"):
            return True
        if self.aprovacao_fixa is not None:
            resposta = self.aprovacao_fixa
        elif self.auto_aprovar:
            resposta = "s"
        elif sys.stdin.isatty():
            resposta = input("  [portão humano] Gravar este andamento na base? (s/N) ").strip().lower()
        else:
            resposta = "n"
        ok = resposta in ("s", "sim", "y")
        self.log.nota(f"Portão humano no cliente: escrita {'APROVADA' if ok else 'NEGADA'}.")
        return ok

    async def chamar(self, nome: str, args: dict) -> tuple[str, bool]:
        self.log.chamada(nome, args)
        if not self._aprovado(nome, args):
            texto = "O usuário NÃO aprovou a gravação. Nada foi gravado; não tente de novo sem novo pedido."
            self.log.resultado(texto, True)
            return texto, True
        r = await self.cliente.call_tool(nome, args)
        texto = (
            json.dumps(r.structured_content, ensure_ascii=False)
            if r.structured_content is not None
            else "\n".join(getattr(c, "text", "") for c in r.content)
        )
        self.log.resultado(texto, bool(r.is_error))
        return texto, bool(r.is_error)


def parametros_servidor(db: Path, hoje: str) -> StdioServerParameters:
    return StdioServerParameters(
        command=sys.executable,
        args=["-m", "legal_ops.server"],
        env={
            "LEGAL_OPS_DB": str(db),
            "LEGAL_OPS_HOJE": hoje,
            "LEGAL_OPS_CLIENTE": "demo_agente",
            "PYTHONPATH": str(RAIZ / "src"),
        },
        cwd=str(RAIZ),
    )


def proxima_pergunta(log: Transcricao) -> str | None:
    if not sys.stdin.isatty():
        return None
    try:
        texto = input("\nvocê> ").strip()
    except EOFError:
        return None
    if texto:
        log.usuario(texto)
    return texto or None


# ---------------------------------------------------------------- modo offline


async def rodar_offline(ponte: PonteMCP, log: Transcricao, pergunta: str) -> None:
    """Roteiro fixo que exercita todas as tools, inclusive o guardrail de escrita."""
    log.usuario(pergunta)
    log.nota("Modo offline: as decisões do 'agente' são um roteiro determinístico; as respostas são reais.")

    texto, _ = await ponte.chamar("prazos_vencendo", {"dias": 7, "advogado": "Helena Andrade"})
    fila = json.loads(texto)
    candidatos = [p for p in fila["prazos"] if p["situacao"] != "ATRASADO"] or fila["prazos"]
    if not candidatos:
        log.agente("Nenhum prazo seu vence nos próximos 7 dias.")
        return
    alvo = candidatos[0]

    texto, _ = await ponte.chamar("buscar_processo", {"termo": alvo["numero_cnj"]})
    processo = json.loads(texto)["processos"][0]

    texto, _ = await ponte.chamar(
        "calcular_prazo", {"data_intimacao": alvo["data_intimacao"], "dias_uteis": alvo["dias_uteis"]}
    )
    calculo = json.loads(texto)
    confere = "confere" if calculo["vencimento"] == alvo["data_vencimento"] else "NÃO confere"

    atrasados = fila["atrasados"]
    log.agente(
        f"Você tem {fila['total']} prazo(s) na janela ({atrasados} atrasado(s)). O mais urgente é "
        f"**{alvo['descricao']}** no processo {alvo['numero_cnj']} ({processo['classe']}, {processo['orgao']}), "
        f"cliente {processo['cliente']}: vence em {alvo['data_vencimento']} "
        f"({alvo['dias_uteis_restantes']} dia(s) útil(eis) restante(s)). Recontei: intimação em "
        f"{alvo['data_intimacao']} + {alvo['dias_uteis']} dias úteis = {calculo['vencimento']} — {confere} "
        "com o cadastro. Lembrete: feriados locais e suspensões do tribunal não entram nessa conta."
    )

    digitado = alvo["numero_cnj"][:8] + ("0" if alvo["numero_cnj"][8] != "0" else "1") + alvo["numero_cnj"][9:]
    log.usuario(f"Protocolei a peça hoje. Registra o andamento no {digitado} e dá baixa no prazo.")
    texto, _ = await ponte.chamar("validar_numero_cnj", {"numero": digitado})
    diag = json.loads(texto)
    log.agente(
        f"O número {digitado} é inválido: {diag.get('motivo')} Pelo contexto, você quis dizer "
        f"{alvo['numero_cnj']}. Vou preparar a prévia nesse número."
    )

    pedido = {
        "numero_cnj": alvo["numero_cnj"],
        "tipo": "peticao",
        "descricao": f"Protocolada petição de {alvo['descricao'].lower()} dentro do prazo.",
        "registrado_por": "Helena Andrade",
        "cumpre_prazo_id": alvo["id"],
    }
    texto, erro = await ponte.chamar("registrar_andamento", pedido | {"confirmar": False})
    if erro:
        log.agente(f"O servidor recusou a prévia: {texto}")
        return
    previa = json.loads(texto)["previa"]
    log.agente(
        f'Prévia (nada gravado ainda): {previa["tipo"]} em {previa["data"]} — "{previa["descricao"]}", '
        f"baixa do prazo {alvo['id']} como cumprido no prazo. Confirma?"
    )
    log.usuario("Sim, pode gravar.")
    texto, erro = await ponte.chamar("registrar_andamento", pedido | {"confirmar": True})
    if not erro:
        gravado = json.loads(texto)
        log.agente(
            f"Gravado: andamento #{gravado['andamento_id']}, registro de auditoria "
            f"#{gravado['auditoria_id']}. O prazo saiu da sua fila."
        )

    log.usuario("Fecha com os KPIs dos últimos 30 dias.")
    texto, _ = await ponte.chamar("kpis_escritorio", {"periodo_dias": 30})
    k = json.loads(texto)
    taxa = k["prazos"]["taxa_cumprimento"]
    maior = max(k["carga_por_advogado"], key=lambda c: c["processos_ativos"])
    log.agente(
        f"Últimos 30 dias: {k['prazos']['cumpridos']} prazos cumpridos e {k['prazos']['perdidos']} perdidos "
        f"(taxa {taxa:.0%}). Maior carga: {maior['advogado']} com {maior['processos_ativos']} processos ativos. "
        f"Honorários atrasados: {reais(k['honorarios']['atrasado'])}."
    )


def reais(valor: float) -> str:
    """Formata 12345.6 como 'R$ 12.345,60' sem depender do locale do sistema."""
    return "R$ " + f"{valor:,.2f}".translate(str.maketrans(",.", ".,"))


# ---------------------------------------------------------------- modo Claude


async def rodar_claude(ponte: PonteMCP, log: Transcricao, pergunta: str, modelo: str) -> None:
    import anthropic

    cliente = anthropic.AsyncAnthropic()
    tools = [
        {"name": t.name, "description": t.description or "", "input_schema": t.input_schema}
        for t in await ponte.listar()
    ]
    mensagens: list[dict] = [{"role": "user", "content": pergunta}]
    log.usuario(pergunta)

    while True:
        for _ in range(MAX_PASSOS):
            try:
                resposta = await cliente.beta.messages.create(
                    model=modelo,
                    max_tokens=16000,
                    system=SISTEMA,
                    tools=tools,
                    messages=mensagens,
                    output_config={"effort": "medium"},
                    # Se o modelo recusar por política, a API tenta de novo num modelo de reserva.
                    betas=["server-side-fallback-2026-07-01"],
                    fallbacks="default",
                )
            except anthropic.AuthenticationError:
                log.nota("Sem credencial válida da Anthropic: defina ANTHROPIC_API_KEY (veja .env.example).")
                return
            except anthropic.RateLimitError:
                log.nota("Limite de requisições atingido (429). Tente de novo em instantes.")
                return
            except anthropic.APIStatusError as erro:
                log.nota(f"Erro da API Anthropic ({erro.status_code}): {erro.message}")
                return
            except anthropic.APIConnectionError:
                log.nota("Sem conexão com a API Anthropic.")
                return

            mensagens.append({"role": "assistant", "content": resposta.content})
            for bloco in resposta.content:
                if bloco.type == "text" and bloco.text.strip():
                    log.agente(bloco.text)

            if resposta.stop_reason == "refusal":
                log.nota("O modelo recusou o pedido (stop_reason=refusal).")
                return
            if resposta.stop_reason == "pause_turn":
                continue
            if resposta.stop_reason == "max_tokens":
                log.nota("Resposta cortada por max_tokens.")
                break
            chamadas = [b for b in resposta.content if b.type == "tool_use"]
            if resposta.stop_reason != "tool_use" or not chamadas:
                break
            resultados = []
            for c in chamadas:
                texto, erro = await ponte.chamar(c.name, dict(c.input))
                resultados.append({"type": "tool_result", "tool_use_id": c.id, "content": texto, "is_error": erro})
            mensagens.append({"role": "user", "content": resultados})  # todos os resultados numa só mensagem
        else:
            log.nota(f"Parei após {MAX_PASSOS} passos sem resposta final.")

        seguinte = proxima_pergunta(log)
        if not seguinte:
            return
        mensagens.append({"role": "user", "content": seguinte})


# ---------------------------------------------------------------- modo Gemini


async def rodar_gemini(ponte: PonteMCP, log: Transcricao, pergunta: str, modelo: str) -> None:
    from google import genai
    from google.genai import errors as genai_errors
    from google.genai import types

    chave = os.environ.get("GEMINI_API_KEY")
    if not chave:
        log.nota("Defina GEMINI_API_KEY (veja .env.example).")
        return
    cliente = genai.Client(api_key=chave)
    declaracoes = [
        types.FunctionDeclaration(name=t.name, description=t.description or "", parameters_json_schema=t.input_schema)
        for t in await ponte.listar()
    ]
    config = types.GenerateContentConfig(
        system_instruction=SISTEMA,
        tools=[types.Tool(function_declarations=declaracoes)],
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )
    conteudos: list = [types.Content(role="user", parts=[types.Part.from_text(text=pergunta)])]
    log.usuario(pergunta)

    # Modelos "preview" somem e os gratuitos ficam sobrecarregados: tenta a lista em ordem.
    reservas = [modelo] + [m for m in MODELOS_GEMINI_RESERVA if m != modelo]

    async def gerar():
        while reservas:
            try:
                return await cliente.aio.models.generate_content(model=reservas[0], contents=conteudos, config=config)
            except genai_errors.APIError as erro:
                if erro.code not in (404, 429, 500, 503) or len(reservas) == 1:
                    raise
                log.nota(f"Gemini {reservas[0]} indisponível ({erro.code}); tentando {reservas[1]}.")
                reservas.pop(0)

    while True:
        for _ in range(MAX_PASSOS):
            try:
                resposta = await gerar()
            except genai_errors.APIError as erro:
                log.nota(f"Erro da API Gemini ({erro.code}): {erro.message}")
                return
            candidato = resposta.candidates[0] if resposta.candidates else None
            if candidato is None or candidato.content is None:
                log.nota(f"Resposta vazia do Gemini (finish_reason={getattr(candidato, 'finish_reason', None)}).")
                return
            conteudos.append(candidato.content)
            for parte in candidato.content.parts or []:
                if parte.text and not parte.thought:
                    log.agente(parte.text)
            chamadas = resposta.function_calls or []
            if not chamadas:
                break
            partes = []
            for c in chamadas:
                texto, erro = await ponte.chamar(c.name, dict(c.args or {}))
                carga = {"erro": texto} if erro else {"resultado": texto}
                partes.append(types.Part.from_function_response(name=c.name, response=carga))
            conteudos.append(types.Content(role="user", parts=partes))
        else:
            log.nota(f"Parei após {MAX_PASSOS} passos sem resposta final.")

        seguinte = proxima_pergunta(log)
        if not seguinte:
            return
        conteudos.append(types.Content(role="user", parts=[types.Part.from_text(text=seguinte)]))


# ---------------------------------------------------------------- main


def _carregar_dotenv() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(RAIZ / ".env")


async def principal(args: argparse.Namespace) -> Transcricao:
    log = Transcricao()
    db = Path(args.db)
    # base de demo descartável, regenerada a cada execução para o resultado ser reproduzível
    sys.path.insert(0, str(RAIZ / "src"))
    from legal_ops import db as ldb
    from legal_ops import seed

    db.parent.mkdir(parents=True, exist_ok=True)
    conn = ldb.conectar(db)
    try:
        seed.gerar(conn, date.fromisoformat(args.hoje))
    finally:
        conn.close()

    log.nota(f"Servidor MCP por stdio · base fictícia · data de referência {args.hoje} · modo {args.modo}")
    async with Client(parametros_servidor(db, args.hoje)) as cliente:
        ponte = PonteMCP(cliente, log, args.auto_aprovar)
        nomes = [t.name for t in await ponte.listar()]
        log.nota(f"Tools descobertas: {', '.join(nomes)}")
        pergunta = args.pergunta or PERGUNTA_PADRAO
        if args.modo == "offline":
            ponte.aprovacao_fixa = "s"
            await rodar_offline(ponte, log, pergunta)
        elif args.modo == "claude":
            await rodar_claude(ponte, log, pergunta, args.modelo or os.environ.get("CLAUDE_MODELO", MODELO_CLAUDE))
        else:
            await rodar_gemini(ponte, log, pergunta, args.modelo or os.environ.get("GEMINI_MODELO", MODELO_GEMINI))
    return log


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    _carregar_dotenv()
    parser = argparse.ArgumentParser(description="Agente de demonstração do mcp-legal-ops.")
    parser.add_argument("--modo", choices=["offline", "claude", "gemini"], default="offline")
    parser.add_argument("--pergunta", help="primeira mensagem do usuário")
    parser.add_argument("--modelo", help=f"padrão: {MODELO_CLAUDE} (claude) / {MODELO_GEMINI} (gemini)")
    parser.add_argument("--hoje", default=HOJE_DEMO, help="data de referência da base de demo (AAAA-MM-DD)")
    parser.add_argument("--db", default=str(RAIZ / "data" / "demo.db"), help="SQLite da demo (é recriado)")
    parser.add_argument("--auto-aprovar", action="store_true", help="aprova escritas sem perguntar (cuidado)")
    parser.add_argument("--salvar", help="grava a transcrição em Markdown neste caminho")
    args = parser.parse_args()
    log = asyncio.run(principal(args))
    if args.salvar:
        log.salvar(Path(args.salvar))
        print(f"\nTranscrição salva em {args.salvar}")


if __name__ == "__main__":
    main()
