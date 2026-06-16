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

- **Fase 0 — Bootstrap**: estrutura, configuração, qualidade, containers. ✅
- **Fase 1 — Webhook + persistência**: em breve.
- **Fase 2 — Classificação + respostas**: em breve.
- **Fase 3 — Agendamento + admin**: em breve.

Veja [PLAN.md](PLAN.md) para o detalhamento das fases e decisões de design.
Comandos para o assistente de IA em [CLAUDE.md](CLAUDE.md).
