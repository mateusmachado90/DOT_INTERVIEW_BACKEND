# DOT_INTERVIEW_BACKEND

Repositorio de backend da solucao de plataforma de tutores para entrevista na DOT Digital.

## Ambiente local

Este projeto usa Docker Compose para disponibilizar uma API FastAPI e um banco PostgreSQL local.

### Requisitos

- Docker
- Docker Compose

### Configuracao opcional

O `docker-compose.yml` ja possui valores padrao para desenvolvimento local. Para customizar as credenciais ou porta, crie um arquivo `.env` a partir do exemplo:

```bash
cp .env.example .env
```

### Subir a aplicacao

```bash
docker compose up -d
```

Se o ambiente usar Docker Compose v1, use `docker-compose` no lugar de `docker compose`.

API disponivel em `http://localhost:8000` por padrao.
Healthcheck da API: `http://localhost:8000/health`.
O PostgreSQL ficara disponivel em `localhost:5432` por padrao.

Na inicializacao da API, as tabelas basicas do MVP sao criadas automaticamente no PostgreSQL a partir dos modelos SQLAlchemy.

### Autenticacao

As rotas administrativas do MVP usam um token simples no header `X-API-Token`.
O valor padrao local e `dev-api-token`, configuravel por `API_TOKEN`.

Exemplo:

```bash
curl -H "X-API-Token: dev-api-token" http://localhost:8000/tutors
```

### API de tutores

Operacoes disponiveis:

- `POST /tutors`
- `GET /tutors`
- `GET /tutors/{tutor_id}`
- `PUT /tutors/{tutor_id}`
- `PATCH /tutors/{tutor_id}`
- `DELETE /tutors/{tutor_id}`

Exemplo de criacao:

```bash
curl -X POST http://localhost:8000/tutors \
  -H "Content-Type: application/json" \
  -H "X-API-Token: dev-api-token" \
  -d '{"name":"Tutor DOT","description":"Tutor interno","status":"ACTIVE","system_prompt":"Voce e um tutor objetivo."}'
```

### Verificar status

```bash
docker compose ps
```

### Parar o ambiente

```bash
docker compose down
```

Para remover tambem os dados persistidos do banco:

```bash
docker compose down -v
```

Notas do candidato:
* Embora o SQLite fosse suficiente para este MVP devido à sua simplicidade, optou-se pelo PostgreSQL porque a aplicação foi concebida como um serviço web para múltiplos usuários. Essa escolha representa melhor uma arquitetura orientada à produção, oferece garantias mais robustas de concorrência e evita um esforço de migração futuro caso a plataforma evolua.
