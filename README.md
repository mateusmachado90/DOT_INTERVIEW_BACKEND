# DOT_INTERVIEW_BACKEND

Repositorio de backend da solucao de plataforma de tutores para entrevista na DOT Digital.

## Ambiente local

Este projeto usa Docker Compose para disponibilizar um banco PostgreSQL local.

### Requisitos

- Docker
- Docker Compose

### Configuracao opcional

O `docker-compose.yml` ja possui valores padrao para desenvolvimento local. Para customizar as credenciais ou porta, crie um arquivo `.env` a partir do exemplo:

```bash
cp .env.example .env
```

### Subir o banco

```bash
docker compose up -d
```

Se o ambiente usar Docker Compose v1, use `docker-compose` no lugar de `docker compose`.

O PostgreSQL ficara disponivel em `localhost:5432` por padrao.

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
