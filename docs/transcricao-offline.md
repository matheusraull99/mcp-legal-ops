_Servidor MCP por stdio · base fictícia · data de referência 2026-11-24 · modo offline_
_Tools descobertas: buscar_processo, prazos_vencendo, calcular_prazo, validar_numero_cnj, kpis_escritorio, registrar_andamento_

**Usuário:** Sou a Helena Andrade. Quais prazos meus vencem nos próximos 7 dias? Para o mais urgente, traga o resumo do processo e confira o vencimento pela contagem de dias úteis.

_Modo offline: as decisões do 'agente' são um roteiro determinístico; as respostas são reais._
→ `prazos_vencendo({"dias": 7, "advogado": "Helena Andrade"})`
  ← {"data_referencia": "2026-11-24", "janela": "2026-11-24 a 2026-12-01", "total": 2, "atrasados": 0, "prazos": [{"id": 33, "descricao": "Especificação de provas", "data_intimacao": "2026-11-14", "dias_uteis": 5, "data_vencimento": "2026-11-24", "numero_cnj": "0305941-69.2025.8.13.0024", "area": "Consumidor", "cliente": "Bruno Jardim Kowalski", "responsavel": "Helena Andrade", "dias_uteis_restantes": …
→ `buscar_processo({"termo": "0305941-69.2025.8.13.0024"})`
  ← {"encontrados": 1, "processos": [{"numero_cnj": "0305941-69.2025.8.13.0024", "cliente": "Bruno Jardim Kowalski", "cliente_tipo": "PF", "polo_do_cliente": "ativo", "parte_contraria": "Tecelagem Fio de Ouro Ltda.", "area": "Consumidor", "classe": "Procedimento do Juizado Especial Cível", "orgao": "20ª Vara Cível", "status": "ativo", "advogado_responsavel": "Helena Andrade (OAB/SP 900.101)", "valor_c …
→ `calcular_prazo({"data_intimacao": "2026-11-14", "dias_uteis": 5})`
  ← {"data_intimacao": "2026-11-14", "dia_do_comeco": "2026-11-16", "inicio_contagem": "2026-11-17", "dias_uteis": 5, "vencimento": "2026-11-24", "dias_corridos_ate_vencimento": 10, "total_dias_nao_uteis_pulados": 3, "periodos_nao_uteis": [{"de": "2026-11-20", "ate": "2026-11-22", "motivos": ["feriado: Dia Nacional de Zumbi e da Consciência Negra", "sábado", "domingo"]}], "observacao": "Contagem em di …

**Agente:** Você tem 2 prazo(s) na janela (0 atrasado(s)). O mais urgente é **Especificação de provas** no processo 0305941-69.2025.8.13.0024 (Procedimento do Juizado Especial Cível, 20ª Vara Cível), cliente Bruno Jardim Kowalski: vence em 2026-11-24 (0 dia(s) útil(eis) restante(s)). Recontei: intimação em 2026-11-14 + 5 dias úteis = 2026-11-24 — confere com o cadastro. Lembrete: feriados locais e suspensões do tribunal não entram nessa conta.


**Usuário:** Protocolei a peça hoje. Registra o andamento no 0305941-09.2025.8.13.0024 e dá baixa no prazo.

→ `validar_numero_cnj({"numero": "0305941-09.2025.8.13.0024"})`
  ← {"valido": false, "entrada": "0305941-09.2025.8.13.0024", "formatado": "0305941-09.2025.8.13.0024", "partes": {"sequencial": "0305941", "dv_informado": "09", "ano": "2025", "segmento": "8", "segmento_nome": "Justiça Estadual", "tribunal": "13", "origem": "0024"}, "dv_esperado": "69", "motivo": "Dígito verificador não confere: informado 09, esperado 69."}

**Agente:** O número 0305941-09.2025.8.13.0024 é inválido: Dígito verificador não confere: informado 09, esperado 69. Pelo contexto, você quis dizer 0305941-69.2025.8.13.0024. Vou preparar a prévia nesse número.

→ `registrar_andamento({"numero_cnj": "0305941-69.2025.8.13.0024", "tipo": "peticao", "descricao": "Protocolada petição de especificação de provas dentro do prazo.", "registrado_por": "Helena Andrade", "cumpre_prazo_id": 33, "confirmar": false})`
  ← {"gravado": false, "confirmacao_necessaria": true, "mensagem": "Nada foi gravado. Mostre a prévia ao usuário e, se ele concordar, chame de novo com confirmar=true.", "previa": {"processo": "0305941-69.2025.8.13.0024", "data": "2026-11-24", "tipo": "peticao", "descricao": "Protocolada petição de especificação de provas dentro do prazo.", "registrado_por": "Helena Andrade", "baixa_de_prazo": {"prazo …

**Agente:** Prévia (nada gravado ainda): peticao em 2026-11-24 — "Protocolada petição de especificação de provas dentro do prazo.", baixa do prazo 33 como cumprido no prazo. Confirma?


**Usuário:** Sim, pode gravar.

→ `registrar_andamento({"numero_cnj": "0305941-69.2025.8.13.0024", "tipo": "peticao", "descricao": "Protocolada petição de especificação de provas dentro do prazo.", "registrado_por": "Helena Andrade", "cumpre_prazo_id": 33, "confirmar": true})`
_Portão humano no cliente: escrita APROVADA._
  ← {"gravado": true, "andamento_id": 398, "auditoria_id": 2, "registro": {"processo": "0305941-69.2025.8.13.0024", "data": "2026-11-24", "tipo": "peticao", "descricao": "Protocolada petição de especificação de provas dentro do prazo.", "registrado_por": "Helena Andrade", "baixa_de_prazo": {"prazo_id": 33, "descricao": "Especificação de provas", "vencimento": "2026-11-24", "cumprido_no_prazo": true}}}

**Agente:** Gravado: andamento #398, registro de auditoria #2. O prazo saiu da sua fila.


**Usuário:** Fecha com os KPIs dos últimos 30 dias.

→ `kpis_escritorio({"periodo_dias": 30})`
  ← {"data_referencia": "2026-11-24", "periodo": "2026-10-25 a 2026-11-24", "prazos": {"cumpridos": 33, "perdidos": 4, "taxa_cumprimento": 0.8919, "vencidos_ainda_em_aberto": 0}, "volume_por_area": [{"area": "Empresarial", "processos_ativos": 13, "valor_em_disputa": 5448921.23}, {"area": "Consumidor", "processos_ativos": 12, "valor_em_disputa": 5194061.75}, {"area": "Tributário", "processos_ativos": 1 …

**Agente:** Últimos 30 dias: 33 prazos cumpridos e 4 perdidos (taxa 89%). Maior carga: Helena Andrade com 13 processos ativos. Honorários atrasados: R$ 304.954,26.

