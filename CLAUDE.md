# CLAUDE.md

Guia operacional do projeto **autozap** para agentes de IA. Mantenha este arquivo
atualizado conforme novos comandos/fluxos forem adicionados.

## Visão geral

Backend de atendimento automático no WhatsApp (Cloud API). FastAPI recebe o
webhook, persiste e enfileira; o worker Celery classifica a intenção (regras +
Claude Haiku) e responde (template ou Claude Sonnet), com escalonamento para
humano em baixa confiança. Detalhes e fases em [PLAN.md](PLAN.md).

## Ambiente

- Python **3.12+** (Docker fixa 3.12; ambiente local pode ser mais novo).
- Gerência de dependências: `pyproject.toml` (PEP 621), `pip` + `venv`.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
Copy-Item .env.example .env
```

## Comandos

| Ação | Comando |
|------|---------|
| Lint | `ruff check .` |
| Formatação (verificar) | `ruff format --check .` |
| Formatação (aplicar) | `ruff format .` |
| Tipos | `mypy app tests` |
| Testes | `pytest` |
| Testes (1 arquivo) | `pytest tests/test_smoke.py` |
| Cobertura (gate 88%) | `pytest --cov --cov-report=term-missing` |
| API local | `uvicorn app.main:app --reload` |
| Worker (Fase 1+) | `celery -A app.core.celery_app.celery_app worker --loglevel=info` |
| Migrations aplicar (Fase 1+) | `alembic upgrade head` |
| Nova migration (Fase 1+) | `alembic revision --autogenerate -m "mensagem"` |
| Stack completa | `docker compose up --build` |
| Validar compose | `docker compose config` |

## Convenções

- Código, docstrings e comentários em **português**; identificadores podem ser PT.
- **Type hints em tudo**; `mypy` estrito deve passar limpo.
- **Nenhuma chamada de rede real em testes** — injete dependências e use os fakes
  (`FakeWhatsAppClient`, fakes de IA).
- Toda integração externa atrás de uma interface (Protocol).
- Modelos Claude: `claude-haiku-4-5` (classificação, JSON estrito via
  `messages.parse`) e `claude-sonnet-4-6` (respostas). Sem `effort`/thinking em Haiku.
- Critério para avançar de fase: `ruff`, `mypy` e `pytest` verdes.
- Commits pequenos por fase; **não fazer push** sem pedido explícito.
- **Logs**: estruturados (JSON) com id de correlação automático (`X-Request-ID`
  na API, header da tarefa no worker). Nunca logar telefone/conteúdo cru — use
  `mascarar_telefone` ([app/core/logging.py](app/core/logging.py)).

## Estrutura

```
app/
  main.py            # app factory + /health
  core/              # config, db, segurança, celery, logging
  api/               # webhook, admin, deps, middleware
  models/            # SQLAlchemy
  schemas/           # Pydantic
  services/          # regras de negócio
  integrations/      # whatsapp.py, ia.py (+ fakes em testes)
  workers/           # tasks Celery, sinais (logging/correlação)
alembic/             # migrations
tests/               # pytest (conftest, fakes, test_*)
```
