# DOT_INTERVIEW_BACKEND

Repositório de backend da solução de plataforma de tutores para entrevista na DOT Digital.

## Nota sobre autoria

Este código foi produzido com o apoio de agentes de codificação, não por codificação integralmente manual.

## Ambiente local

Este projeto usa Docker Compose para disponibilizar uma API FastAPI e um banco PostgreSQL local.

### Requisitos

- Docker
- Docker Compose

### Configuração opcional

O `docker-compose.yml` já possui valores padrão para desenvolvimento local. Para customizar as credenciais ou porta, crie um arquivo `.env` a partir do exemplo:

```bash
cp .env.example .env
```

### Subir a aplicação

```bash
docker compose up -d
```

Se o ambiente usar Docker Compose v1, use `docker-compose` no lugar de `docker compose`.

API disponível em `http://localhost:8000` por padrão.
Healthcheck da API: `http://localhost:8000/health`.
O PostgreSQL ficará disponível em `localhost:5432` por padrão.

Na inicialização da API, as tabelas básicas do MVP são criadas automaticamente no PostgreSQL a partir dos modelos SQLAlchemy.

Também são cadastrados tutores demonstrativos de forma idempotente:

- `Tutor Copa do Mundo FIFA`, com fonte em `https://pt.wikipedia.org/wiki/Copa_do_Mundo_FIFA`
- `Tutor Python`, com fontes em `https://docs.python.org/3/library/pathlib.html`, `https://docs.python.org/3/library/functions.html` e `https://docs.python.org/3/tutorial/classes.html`
- `Tutor Revolução Francesa`, com fonte em `https://pt.wikipedia.org/wiki/Revolu%C3%A7%C3%A3o_Francesa`

### Autenticação

As rotas administrativas do MVP usam um token simples no header `X-API-Token`.
O valor padrão local é `dev-api-token`, configurável por `API_TOKEN`.
As origens liberadas para o frontend em desenvolvimento são configuráveis por `CORS_ORIGINS`
e, por padrão, incluem `http://localhost:5173` e `http://127.0.0.1:5173`.
O modelo usado pelo agente de conversação é configurável por `LANGCHAIN_MODEL`.
O timeout das chamadas do agente é configurável por `CONVERSATION_AGENT_TIMEOUT_SECONDS`
e usa `180` segundos por padrão para acomodar fluxos que acionam ferramentas e fontes externas.
A identificação enviada pelas ferramentas do agente pode ser ajustada por `CONVERSATION_AGENT_NAME` e `CONVERSATION_AGENT_VERSION`.

Por padrão, o ambiente local usa o modelo gratuito `openai:tencent/hy3:free`,
que pode ser acessado via OpenRouter usando a compatibilidade com a API da OpenAI.
Para usar OpenRouter, configure:

```env
OPENAI_API_KEY=sua-chave-openrouter
OPENAI_BASE_URL=https://openrouter.ai/api/v1
LANGCHAIN_MODEL=openai:tencent/hy3:free
CONVERSATION_AGENT_TIMEOUT_SECONDS=180
```

Para usar o provedor OpenAI diretamente via LangChain, configure `OPENAI_API_KEY`,
defina `OPENAI_BASE_URL=https://api.openai.com/v1` quando estiver usando Docker Compose
e selecione um modelo compatível em `LANGCHAIN_MODEL`.

A API administrativa é protegida por uma única chave de API (API Key) configurada por meio de variáveis de ambiente. Como este MVP é destinado a um único usuário administrador e não exige gerenciamento de usuários nem autorização com controle granular de permissões, o uso de uma API Key oferece uma solução mais simples, com complexidade de implementação significativamente menor. Uma versão pronta para produção provavelmente adotaria autenticação baseada em JWT, integrada a um provedor de identidade.

Exemplo:

```bash
curl -H "X-API-Token: dev-api-token" http://localhost:8000/tutors
```

### API de tutores

Operações disponíveis:

- `POST /tutors`
- `GET /tutors`
- `GET /tutors/{tutor_id}`
- `PUT /tutors/{tutor_id}`
- `PATCH /tutors/{tutor_id}`
- `DELETE /tutors/{tutor_id}`
- `POST /tutors/{tutor_id}/chat`

Exemplo de criação:

```bash
curl -X POST http://localhost:8000/tutors \
  -H "Content-Type: application/json" \
  -H "X-API-Token: dev-api-token" \
  -d '{"name":"Tutor DOT","description":"Tutor interno","status":"ACTIVE","system_prompt":"Você é um tutor objetivo."}'
```

Exemplo de conversa:

```bash
curl -X POST http://localhost:8000/tutors/{tutor_id}/chat \
  -H "Content-Type: application/json" \
  -H "X-API-Token: dev-api-token" \
  -d '{"message":"Explique o tema em poucas palavras."}'
```

Para continuar a mesma conversa, envie o `session_token` retornado na primeira resposta:

```bash
curl -X POST http://localhost:8000/tutors/{tutor_id}/chat \
  -H "Content-Type: application/json" \
  -H "X-API-Token: dev-api-token" \
  -d '{"session_token":"token-retornado","message":"Pode dar um exemplo?"}'
```

### Decisões de arquitetura

O LangChain foi escolhido por ser um framework maduro e amplamente adotado para fluxos agênticos com LLMs, com suporte nativo a ferramentas, templates de prompt e pipelines conversacionais. Para este MVP, ele oferece estrutura suficiente para implementar recuperação de conhecimento baseada em ferramentas, sem criar uma camada própria de orquestração.

O pipeline de conversa usa um agente LangChain com ferramentas de conhecimento vinculadas às fontes cadastradas do tutor. O agente decide quando listar fontes, buscar trechos textuais em uma fonte específica ou compilar contexto das fontes habilitadas, sem uma etapa automática de recuperação antes da chamada ao modelo.

Este MVP não implementa RAG: não há banco vetorial, índice vetorial externo, embeddings nem pipeline próprio de recuperação como estratégia principal de resposta. As consultas às fontes são ferramentas textuais pontuais, acionadas pelo agente quando ele decidir que precisa de conhecimento adicional.

### Verificar status

```bash
docker compose ps
```

### Parar o ambiente

```bash
docker compose down
```

Para remover também os dados persistidos do banco:

```bash
docker compose down -v
```

Notas do candidato:

- Embora o SQLite fosse suficiente para este MVP devido à sua simplicidade, optou-se pelo PostgreSQL porque a aplicação foi concebida como um serviço web para múltiplos usuários. Essa escolha representa melhor uma arquitetura orientada à produção, oferece garantias mais robustas de concorrência e evita um esforço de migração futuro caso a plataforma evolua.
