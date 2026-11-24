"""Gera a base fictícia do escritório "Andrade & Lacerda Advogados" (inventado).

Tudo é sintético: nomes combinados ao acaso, números CNJ gerados com DV correto
mas sem correspondência com processos reais, valores aleatórios. A geração é
determinística (semente fixa) e relativa à data de referência, para a base
sempre ter prazos vencendo "esta semana".

Uso: python -m legal_ops.seed [--hoje AAAA-MM-DD] [--db caminho]
"""

from __future__ import annotations

import argparse
import random
from datetime import date, datetime, timedelta
from pathlib import Path

from . import cnj, db, prazos

NOMES = [
    "Ana",
    "Bruno",
    "Carla",
    "Diego",
    "Elaine",
    "Fábio",
    "Gabriela",
    "Heitor",
    "Isabela",
    "João",
    "Karina",
    "Lucas",
    "Marina",
    "Nicolas",
    "Olívia",
    "Paulo",
    "Renata",
    "Sérgio",
    "Tatiane",
    "Vinícius",
]
SOBRENOMES = [
    "Albuquerque",
    "Barros",
    "Cavalcanti",
    "Duarte",
    "Esteves",
    "Figueiredo",
    "Guimarães",
    "Hartmann",
    "Iwamoto",
    "Jardim",
    "Kowalski",
    "Lacerda",
    "Monteiro",
    "Nogueira",
    "Orsini",
    "Pacheco",
    "Quintela",
    "Rezende",
    "Siqueira",
    "Toledo",
]
EMPRESAS = [
    "Padaria Estrela do Vale Ltda.",
    "Transportes Rota Azul Ltda.",
    "Clínica Bem Viver S.A.",
    "Construtora Horizonte Novo Ltda.",
    "Mercado Bom Preço Eireli",
    "Tecelagem Fio de Ouro Ltda.",
    "Escola Pequeno Saber Ltda.",
    "Oficina Motor Forte ME",
    "Agropecuária Campo Verde S.A.",
    "Hotel Brisa do Mar Ltda.",
]
CIDADES = ["São Paulo", "Campinas", "Santos", "Rio de Janeiro", "Niterói", "Belo Horizonte", "Contagem"]

ADVOGADOS = [
    ("Helena Andrade", "OAB/SP 900.101", "Cível"),
    ("Rafael Lacerda", "OAB/SP 900.202", "Trabalhista"),
    ("Camila Toledo", "OAB/SP 900.303", "Tributário"),
    ("Otávio Nogueira", "OAB/RJ 900.404", "Família"),
    ("Beatriz Rezende", "OAB/MG 900.505", "Consumidor"),
    ("Gustavo Pacheco", "OAB/SP 900.606", "Empresarial"),
]

# área -> (segmento J, tribunais TR possíveis, classes)
AREAS = {
    "Cível": (8, [26, 19, 13], ["Procedimento Comum Cível", "Execução de Título Extrajudicial", "Monitória"]),
    "Consumidor": (8, [26, 19, 13], ["Procedimento do Juizado Especial Cível", "Procedimento Comum Cível"]),
    "Família": (8, [26, 19], ["Divórcio Litigioso", "Alimentos", "Guarda"]),
    "Empresarial": (8, [26], ["Recuperação Judicial", "Dissolução Parcial de Sociedade"]),
    "Trabalhista": (
        5,
        [2, 1, 3],
        ["Ação Trabalhista - Rito Ordinário", "Ação Trabalhista - Rito Sumaríssimo"],
    ),
    "Tributário": (
        4,
        [3, 2],
        ["Mandado de Segurança Cível", "Execução Fiscal", "Embargos à Execução Fiscal"],
    ),
}
ORGAOS = {
    4: "{n}ª Vara Federal",
    5: "{n}ª Vara do Trabalho",
    8: "{n}ª Vara Cível",
}

PRAZOS_TIPICOS = [
    ("Contestação", 15),
    ("Réplica", 15),
    ("Apelação", 15),
    ("Contrarrazões de apelação", 15),
    ("Embargos de declaração", 5),
    ("Manifestação sobre laudo pericial", 15),
    ("Especificação de provas", 5),
    ("Agravo de instrumento", 15),
    ("Recurso ordinário", 8),
    ("Cumprimento de despacho", 5),
]

ANDAMENTOS = [
    ("distribuicao", "Processo distribuído por sorteio."),
    ("despacho", "Despacho: cite-se a parte ré."),
    ("citacao", "Juntada de mandado de citação cumprido."),
    ("peticao", "Juntada de petição intermediária."),
    ("audiencia", "Audiência de conciliação realizada; sem acordo."),
    ("decisao", "Decisão interlocutória: deferida a produção de prova pericial."),
    ("intimacao", "Intimação das partes para manifestação."),
    ("sentenca", "Sentença de parcial procedência publicada."),
]


def _nome(rng: random.Random) -> str:
    return f"{rng.choice(NOMES)} {rng.choice(SOBRENOMES)} {rng.choice(SOBRENOMES)}"


def gerar(conn, hoje: date, semente: int = 2026, n_clientes: int = 40, n_processos: int = 80) -> dict:
    """Popula a base. Apaga o conteúdo anterior (é uma base de demonstração)."""
    rng = random.Random(semente)
    db.criar_schema(conn)
    for tabela in ("auditoria", "honorarios", "prazos", "andamentos", "processos", "clientes", "advogados"):
        conn.execute(f"DELETE FROM {tabela}")  # nomes fixos do próprio código, não entrada externa

    conn.executemany(
        "INSERT INTO advogados (id, nome, oab, area_principal) VALUES (?, ?, ?, ?)",
        [(i + 1, *a) for i, a in enumerate(ADVOGADOS)],
    )
    adv_por_area = {area: i + 1 for i, (_, _, area) in enumerate(ADVOGADOS)}

    clientes = []
    empresas = rng.sample(EMPRESAS, len(EMPRESAS))
    for i in range(1, n_clientes + 1):
        if i % 4 == 0 and empresas:
            nome, tipo = empresas.pop(), "PJ"
        else:
            nome, tipo = _nome(rng), "PF"
        email = f"cliente{i:03d}@exemplo.com.br"
        clientes.append((i, nome, tipo, email, rng.choice(CIDADES)))
    conn.executemany("INSERT INTO clientes VALUES (?, ?, ?, ?, ?)", clientes)

    agora = datetime.combine(hoje, datetime.min.time()).isoformat()
    sequenciais: set[tuple] = set()
    n_prazos = n_andamentos = 0
    for pid in range(1, n_processos + 1):
        area = rng.choice(list(AREAS))
        segmento, tribunais, classes = AREAS[area]
        tribunal = rng.choice(tribunais)
        distribuicao = hoje - timedelta(days=rng.randint(60, 1400))
        while True:
            chave = (rng.randint(1, 9_999_999), distribuicao.year, segmento, tribunal, rng.randint(1, 450))
            if chave not in sequenciais:
                sequenciais.add(chave)
                break
        numero = cnj.montar(*chave)
        # 70% com o advogado da área, 30% redistribuídos (gera carga desigual, como na vida real)
        advogado = adv_por_area[area] if rng.random() < 0.7 else rng.randint(1, len(ADVOGADOS))
        status = rng.choices(["ativo", "suspenso", "arquivado"], weights=[80, 8, 12])[0]
        cliente = rng.choice(clientes)
        conn.execute(
            "INSERT INTO processos VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                pid,
                numero,
                cliente[0],
                rng.choice(["ativo", "passivo"]),
                _nome(rng) if rng.random() < 0.6 else rng.choice(EMPRESAS),
                area,
                rng.choice(classes),
                ORGAOS[segmento].format(n=rng.randint(1, 45)),
                status,
                advogado,
                round(rng.uniform(5_000, 850_000), 2),
                distribuicao.isoformat(),
            ),
        )

        # andamentos em ordem cronológica
        datas = sorted(
            distribuicao + timedelta(days=rng.randint(0, (hoje - distribuicao).days)) for _ in range(rng.randint(3, 7))
        )
        datas[0] = distribuicao
        for k, d in enumerate(datas):
            tipo, texto = ANDAMENTOS[0] if k == 0 else rng.choice(ANDAMENTOS[1:])
            conn.execute(
                "INSERT INTO andamentos (processo_id, data, tipo, descricao, registrado_por, criado_em) "
                "VALUES (?, ?, ?, ?, NULL, ?)",
                (pid, d.isoformat(), tipo, texto, agora),
            )
            n_andamentos += 1

        if status != "ativo":
            continue

        # prazos: históricos (para KPI) e abertos (para a fila de trabalho)
        for _ in range(rng.randint(1, 4)):
            descricao, dias = rng.choice(PRAZOS_TIPICOS)
            intimacao = hoje - timedelta(days=rng.randint(0, 150))
            intimacao = max(intimacao, distribuicao)
            venc = date.fromisoformat(prazos.calcular_prazo(intimacao, dias)["vencimento"])
            responsavel = advogado if rng.random() < 0.85 else rng.randint(1, len(ADVOGADOS))
            if venc < hoje:
                if rng.random() < 0.9:
                    st, cumprimento = "cumprido", venc - timedelta(days=rng.randint(0, 4))
                else:
                    st, cumprimento = "perdido", None
            elif rng.random() < 0.15:
                st, cumprimento = "cumprido", hoje - timedelta(days=rng.randint(0, 2))
            else:
                st, cumprimento = "aberto", None
            if cumprimento is not None and cumprimento < intimacao:
                cumprimento = intimacao
            conn.execute(
                "INSERT INTO prazos (processo_id, descricao, data_intimacao, dias_uteis, data_vencimento, "
                "responsavel_id, status, data_cumprimento) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    pid,
                    descricao,
                    intimacao.isoformat(),
                    dias,
                    venc.isoformat(),
                    responsavel,
                    st,
                    cumprimento.isoformat() if cumprimento else None,
                ),
            )
            n_prazos += 1

        # honorários
        for _ in range(rng.randint(1, 3)):
            venc = hoje + timedelta(days=rng.randint(-90, 60))
            st = "pago" if venc < hoje and rng.random() < 0.75 else "pendente"
            conn.execute(
                "INSERT INTO honorarios (processo_id, tipo, valor, vencimento, status) VALUES (?, ?, ?, ?, ?)",
                (
                    pid,
                    rng.choice(["contratual", "exito", "mensal"]),
                    round(rng.uniform(800, 25_000), 2),
                    venc.isoformat(),
                    st,
                ),
            )

    conn.commit()
    return {
        "advogados": len(ADVOGADOS),
        "clientes": n_clientes,
        "processos": n_processos,
        "andamentos": n_andamentos,
        "prazos": n_prazos,
        "data_referencia": hoje.isoformat(),
    }


def garantir_base(caminho: Path | None = None, hoje: date | None = None) -> Path:
    """Cria e popula a base se ela ainda não existir. Devolve o caminho."""
    caminho = Path(caminho or db.caminho_banco())
    if not caminho.exists():
        caminho.parent.mkdir(parents=True, exist_ok=True)
        conn = db.conectar(caminho)
        try:
            gerar(conn, hoje or db.hoje())
        finally:
            conn.close()
    return caminho


def main() -> None:
    parser = argparse.ArgumentParser(description="Gera a base fictícia do escritório.")
    parser.add_argument("--hoje", help="data de referência AAAA-MM-DD (padrão: hoje ou LEGAL_OPS_HOJE)")
    parser.add_argument("--db", help="caminho do SQLite (padrão: LEGAL_OPS_DB ou data/escritorio.db)")
    args = parser.parse_args()
    caminho = Path(args.db) if args.db else db.caminho_banco()
    caminho.parent.mkdir(parents=True, exist_ok=True)
    hoje = date.fromisoformat(args.hoje) if args.hoje else db.hoje()
    conn = db.conectar(caminho)
    try:
        resumo = gerar(conn, hoje)
    finally:
        conn.close()
    print(f"Base gerada em {caminho}: {resumo}")


if __name__ == "__main__":
    main()
