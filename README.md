# autozap

Agente de atendimento automático no **WhatsApp** (Cloud API da Meta). Monitora
mensagens recebidas, detecta mensagens **não respondidas** que se enquadram em
assuntos pré-definidos (agendamento, serviços, promoções, ajuda) e **responde
automaticamente**, com **escalonamento para humano** quando a confiança é baixa.

## Stack

- **Python 3.12+**, **FastAPI** + **Uvicorn** (API assíncrona)
- **Celery** + **Redis** (fila de tarefas; broker e backend)
- **PostgreSQL** + **SQLAlchemy 2.x async** (asyncpg) + **Alembic** (migrations)
- **Anthropic Claude**: `claude-haiku-4-5` (classificação de intenção) e
  `claude-sonnet-4-6` (respostas em linguagem natural)
- **Pydantic v2** + **pydantic-settings** (configuração via `.env`)
- **pytest** + **pytest-asyncio** (testes; rede sempre mockada)
- **ruff** + **mypy** (qualidade)
- **Docker** + **docker-compose** (api, worker, postgres, redis)

## Arquitetura (resumo)

```
WhatsApp Cloud API --POST /webhook--> FastAPI
   valida X-Hub-Signature-256 -> deduplica -> persiste -> enfileira tarefa Celery
Worker Celery: detecta "não respondida" -> classifica intenção (regras + LLM)
   -> gera resposta (template ou IA) -> envia -> registra
```

Toda chamada externa (WhatsApp, Anthropic) fica atrás de uma interface, para
permitir mock em testes. Nenhum teste faz chamada de rede real.

## Como rodar

### Local (desenvolvimento)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
Copy-Item .env.example .env   # ajuste os segredos
uvicorn app.main:app --reload
```

Acesse <http://localhost:8000/health> e <http://localhost:8000/docs>.

### Docker

```powershell
Copy-Item .env.example .env
docker compose up --build
```

Sobe `api`, `worker`, `postgres` e `redis`.

## Qualidade e testes

```powershell
ruff check .
ruff format --check .
mypy app tests
pytest
```

## Status de implementação

- **Fase 0 — Bootstrap** ✅ — estrutura, configuração, qualidade, containers.
- **Fase 1 — Webhook + persistência** ✅ — `/webhook` (assinatura HMAC, dedup), modelos e migration Alembic.
- **Fase 2 — Classificação + respostas** ✅ — classificador híbrido (regras + Haiku), regras de negócio (anti-loop, opt-out, rate limit, janela 24h, handoff), respostas via template/Sonnet/interativo.
- **Fase 3 — Agendamento + admin** ✅ — FSM de agendamento (lista interativa) e endpoints admin protegidos por API key.

**Qualidade:** `ruff` + `mypy` estrito sem erros; **66 testes** (pytest), sem chamadas de rede reais.
CI no GitHub Actions (lint, tipos, testes e build da imagem). Melhorias de robustez e o
backlog em [MELHORIAS.md](MELHORIAS.md).

**Saúde:** `GET /health` (liveness) e `GET /health/ready` (verifica o banco). Ao subir via
Docker, o serviço `migrate` aplica as migrations antes de `api`/`worker`.

### Endpoints administrativos (header `X-API-Key`)

- `GET /admin/conversas` — lista conversas.
- `POST /admin/conversas/{id}/liberar` — libera o handoff (reativa o bot).
- `GET|POST /admin/templates`, `PATCH /admin/templates/{id}` — gerir templates.
- `GET|POST /admin/promocoes`, `PATCH /admin/promocoes/{id}` — gerir promoções.
- `DELETE /admin/contatos/{id}` — direito ao esquecimento (apaga o contato e seus dados).

Veja [PLAN.md](PLAN.md) para o detalhamento das fases e decisões de design.
Comandos para o assistente de IA em [CLAUDE.md](CLAUDE.md).
