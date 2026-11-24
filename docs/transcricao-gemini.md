_Servidor MCP por stdio · base fictícia · data de referência 2026-11-24 · modo gemini_
_Tools descobertas: buscar_processo, prazos_vencendo, calcular_prazo, validar_numero_cnj, kpis_escritorio, registrar_andamento_

**Usuário:** Sou a Helena Andrade. Quais prazos meus vencem nos próximos 7 dias? Para o mais urgente, traga o resumo do processo, confira o vencimento pela contagem de dias úteis e prepare a prévia do andamento de protocolo da peça (não grave nada ainda).

_Gemini gemini-flash-latest indisponível (404); tentando gemini-3.5-flash._
→ `prazos_vencendo({"dias": 7, "advogado": "Helena Andrade"})`
  ← {"data_referencia": "2026-11-24", "janela": "2026-11-24 a 2026-12-01", "total": 2, "atrasados": 0, "prazos": [{"id": 33, "descricao": "Especificação de provas", "data_intimacao": "2026-11-14", "dias_uteis": 5, "data_vencimento": "2026-11-24", "numero_cnj": "0305941-69.2025.8.13.0024", "area": "Consumidor", "cliente": "Bruno Jardim Kowalski", "responsavel": "Helena Andrade", "dias_uteis_restantes": …
→ `buscar_processo({"termo": "0305941-69.2025.8.13.0024"})`
  ← {"encontrados": 1, "processos": [{"numero_cnj": "0305941-69.2025.8.13.0024", "cliente": "Bruno Jardim Kowalski", "cliente_tipo": "PF", "polo_do_cliente": "ativo", "parte_contraria": "Tecelagem Fio de Ouro Ltda.", "area": "Consumidor", "classe": "Procedimento do Juizado Especial Cível", "orgao": "20ª Vara Cível", "status": "ativo", "advogado_responsavel": "Helena Andrade (OAB/SP 900.101)", "valor_c …
→ `calcular_prazo({"dias_uteis": 5, "data_intimacao": "2026-11-14"})`
  ← {"data_intimacao": "2026-11-14", "dia_do_comeco": "2026-11-16", "inicio_contagem": "2026-11-17", "dias_uteis": 5, "vencimento": "2026-11-24", "dias_corridos_ate_vencimento": 10, "total_dias_nao_uteis_pulados": 3, "periodos_nao_uteis": [{"de": "2026-11-20", "ate": "2026-11-22", "motivos": ["feriado: Dia Nacional de Zumbi e da Consciência Negra", "sábado", "domingo"]}], "observacao": "Contagem em di …
→ `registrar_andamento({"descricao": "Protocolo de petição de especificação de provas.", "confirmar": false, "numero_cnj": "0305941-69.2025.8.13.0024", "tipo": "peticao", "registrado_por": "Helena Andrade", "cumpre_prazo_id": 33})`
  ← {"gravado": false, "confirmacao_necessaria": true, "mensagem": "Nada foi gravado. Mostre a prévia ao usuário e, se ele concordar, chame de novo com confirmar=true.", "previa": {"processo": "0305941-69.2025.8.13.0024", "data": "2026-11-24", "tipo": "peticao", "descricao": "Protocolo de petição de especificação de provas.", "registrado_por": "Helena Andrade", "baixa_de_prazo": {"prazo_id": 33, "desc …

**Agente:** Olá, Dra. Helena Andrade! Seguem as informações solicitadas:

---

### 1. Prazos nos Próximos 7 Dias (24/11/2026 a 01/12/2026)

1. **[MAIS URGENTE] Especificação de provas** (ID 33)
   * **Processo:** `0305941-69.2025.8.13.0024`
   * **Cliente:** Bruno Jardim Kowalski
   * **Vencimento:** **24/11/2026 (VENCE HOJE)**

2. **Contrarrazões de apelação** (ID 108)
   * **Processo:** `4480957-81.2023.8.19.0311`
   * **Cliente:** Mercado Bom Preço Eireli
   * **Vencimento:** **27/11/2026** (restam 3 dias úteis)

---

### 2. Resumo do Processo mais Urgente (`0305941-69.2025.8.13.0024`)

* **Cliente (Polo Ativo):** Bruno Jardim Kowalski (PF)
* **Parte Contrária:** Tecelagem Fio de Ouro Ltda.
* **Área / Classe:** Consumidor | Procedimento do Juizado Especial Cível
* **Juízo:** 20ª Vara Cível
* **Advogada Responsável:** Helena Andrade (OAB/SP 900.101)
* **Valor da Causa:** R$ 814.681,89
* **Data de Distribuição:** 21/04/2025
* **Último Andamento Notável:** Sentença de parcial procedência publicada em 13/08/2026.

---

### 3. Conferência da Contagem de Dias Úteis (CPC/2015)

* **Data da Intimação:** 14/11/2026 (Sábado)
* **Primeiro Dia Útil / Dia do Começo:** 16/11/2026 (Segunda-feira)
* **Início da Contagem (Dia 1):** 17/11/2026 (Terça-feira)
* **Dias não úteis pulados:**
  * 20/11/2026 (Sexta-feira – Feriado Nacional: Dia da Consciência Negra)
  * 21/11/2026 (Sábado)
  * 22/11/2026 (Domingo)
* **Vencimento Confirmado:** **24/11/2026 (Hoje)**

> *Aviso: A contagem considera feriados nacionais e o recesso forense. Não inclui eventuais feriados locais/estaduais ou portarias de suspensão de prazos do tribunal.*

---

### 4. Prévia do Andamento (Não Gravado)

Foi gerada a prévia para o protocolo e baixa do prazo:

* **Processo:** `0305941-69.2025.8.13.0024`
* **Data:** 24/11/2026
* **Tipo:** Petição
* **Descrição:** Protocolo de petição de especificação de provas.
* **Registrado por:** Helena Andrade
* **Baixa do Prazo:** ID 33 (Especificação de provas)

---

**Confirmação necessária:** Deseja que eu confirme e grave este andamento no sistema?

