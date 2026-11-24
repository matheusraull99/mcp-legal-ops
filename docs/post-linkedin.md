# Post do LinkedIn

## Texto do post

Prazo perdido é o pior erro de um escritório de advocacia. Então fui ver se um agente de IA conseguia ajudar sem virar risco.

Trabalho com automação e RPA, e quase toda vaga que leio hoje pede a mesma coisa: conectar agentes de IA aos sistemas da empresa. O padrão que está ganhando esse jogo se chama MCP (Model Context Protocol). Faltava um no meu portfólio.

Construí um servidor MCP para um escritório fictício. Qualquer agente compatível, como o Claude Desktop, passa a buscar processos, listar prazos da semana, calcular vencimentos e ver indicadores.

O que mais deu trabalho não foi a IA, foi a regra de negócio:

→ prazo em dias úteis do jeito do CPC: exclui o dia do começo, pula feriados (inclusive Carnaval e Sexta-feira Santa, calculados pela Páscoa) e o recesso de 20/12 a 20/01
→ número de processo validado pelo dígito verificador do CNJ
→ escrita só com confirmação explícita, prévia antes e trilha de auditoria de quem gravou o quê

Na rodada com modelo real, o agente achou o prazo que vencia no dia, recontou os dias úteis, preparou o registro e parou para pedir confirmação antes de gravar.

Também deixei escrito o que o motor não cobre, como feriados locais e suspensões do tribunal. Saber o limite da ferramenta faz parte de entregar uma automação confiável.

55 testes, dados 100% fictícios. Link do código nos comentários.

#MCP #AgentesDeIA #LegalOps #Automação #Python

## 1º comentário

Código, instruções para plugar no Claude Desktop/Claude Code e a transcrição da conversa com o agente: https://github.com/matheusraull99/mcp-legal-ops
