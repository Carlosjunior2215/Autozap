# MELHORIAS.md

Backlog de melhorias, otimizações e dívidas técnicas levantadas após a entrega
das Fases 0–3 e da validação da stack no Docker. Cada item traz **severidade**
(🔴 alta / 🟠 média / 🟢 baixa), **esforço** estimado e o **local** no código.

Status: `[ ]` pendente · `[~]` em andamento · `[x]` concluído.

> Convenção do projeto: avançar só com `ruff`, `mypy` e `pytest` verdes; commits
> pequenos por bloco; sem `push` sem pedido explícito.

---

## 1. Correções funcionais (bugs de regra de negócio) 🔴

- [ ] **#1 — Template fora da janela de 24h é enviado como texto livre.** 🔴 · médio
  - Local: [respostas.py](app/services/respostas.py) (fora da janela retorna `RespostaTexto`),
    [processamento.py](app/services/processamento.py) (`_enviar_resposta` → `enviar_texto`).
  - Problema: fora das 24h a Cloud API só aceita `type:template` aprovado; texto
    livre é recusado. [`enviar_template`](app/integrations/whatsapp.py) existe mas
    nunca é chamado, e o modelo [Template](app/models/template.py) não guarda
    `nome_meta`/`idioma` registrados na Meta.
  - Ação: adicionar `nome_meta` + `idioma` ao modelo/migration; criar
    `RespostaTemplate`; enviar via `enviar_template` no caminho fora-da-janela.

- [ ] **#2 — "Não respondida após N minutos" não tem reavaliação agendada.** 🔴 · médio
  - Local: [deteccao.py](app/services/deteccao.py), [tasks.py](app/workers/tasks.py).
  - Problema: a task roda no instante do webhook; com `MINUTOS_SEM_RESPOSTA>0`,
    `mensagem_nao_respondida` retorna `False` e a mensagem é descartada — não há
    re-agendamento. Só funciona com N=0.
  - Ação: enfileirar com `apply_async(countdown=...)` ou usar Celery beat para
    varrer conversas elegíveis após N minutos.

- [ ] **#3 — Anti-loop não cobre "outro número de negócio".** 🟠 · baixo
  - Local: [processamento.py](app/services/processamento.py) (`origem != CLIENTE`),
    [ingestao.py](app/services/ingestao.py) (marca tudo como `CLIENTE`).
  - Ação: ignorar mensagens cujo `from` seja o próprio `phone_number_id`/
    `display_phone_number`; ignorar eventos `statuses`.

## 2. Robustez de produção 🟠

- [ ] **#4 — Task Celery sem retry / `acks_late`.** 🟠 · baixo
  - Local: [tasks.py](app/workers/tasks.py). Falha transitória → mensagem sem
    resposta, sem reprocessamento. Ação: `acks_late=True`,
    `task_reject_on_worker_lost=True`, retry com backoff para erros de infra.

- [ ] **#5 — Dual-write não idempotente (envia, depois faz commit).** 🟠 · médio
  - Local: [processamento.py](app/services/processamento.py) (`_enviar_resposta`).
  - Risco: envio OK + commit falha → retry reenvia (resposta duplicada).
  - Ação: registrar a mensagem do bot como `PENDENTE` antes de enviar e marcar
    `ENVIADA` depois; ou chave de idempotência por mensagem.

- [ ] **#6 — Sem timeout/tratamento de erro nas chamadas Anthropic.** 🟠 · baixo
  - Local: [ia.py](app/integrations/ia.py). Ação: configurar `timeout`/`max_retries`
    no `AsyncAnthropic`; em falha de classificação, cair para handoff.

- [ ] **#7 — Race no rate limiter (`incr` depois `expire`).** 🟢 · baixo
  - Local: [rate_limit.py](app/services/rate_limit.py). Ação: pipeline atômico.

- [ ] **#8 — Config aceita segredos placeholder em produção.** 🟠 · baixo
  - Local: [config.py](app/core/config.py). Ação: validador que recusa defaults de
    `whatsapp_app_secret`/`admin_api_key`/chaves quando `ambiente=producao`.

## 3. Performance / otimização 🟢

- [ ] **#9 — Clientes recriados a cada mensagem; `httpx` nunca fechado.** 🟠 · médio
  - Local: [dependencias.py](app/workers/dependencias.py), [whatsapp.py](app/integrations/whatsapp.py).
  - Com `asyncio.run` por task, clientes async ficam atados ao loop da task.
  - Ação imediata: fechar `httpx`/`redis`/`anthropic` ao fim da task (evita
    vazamento de sockets). Ação futura: loop persistente por processo de worker
    para reuso real de pool.

- [ ] **#10 — Webhook processa de forma síncrona antes de responder 200.** 🟠 · médio
  - Local: [webhook.py](app/api/webhook.py). A Meta reentrega se demorar/falhar.
  - Ação: ingestão mínima + 200 rápido; resto assíncrono.

- [ ] **#11 — `eventos_metrica` é gravado mas nunca lido.** 🟢 · baixo
  - Ação: endpoint admin de métricas agregadas (ou exportar para Prometheus).

## 4. Observabilidade / operação 🟠

- [ ] **#12 — `docker compose up` sobe a stack mas o banco fica vazio.** 🟠 · baixo
  - Nada roda `alembic upgrade head`. Ação: serviço `migrate` (mesma imagem) com
    `depends_on: service_completed_successfully` em `api`/`worker`.

- [ ] **#13 — `/health` é raso; sem readiness; api sem healthcheck no compose.** 🟢 · baixo
  - Local: [main.py](app/main.py), [docker-compose.yml](docker-compose.yml).
  - Ação: `/health/ready` checando DB; healthcheck da `api`.

- [ ] **#14 — Sem `lifespan` para encerrar recursos no shutdown.** 🟢 · baixo
  - Local: [main.py](app/main.py).

- [ ] **#15 — Logging mínimo, sem correlação; risco de PII (LGPD).** 🟠 · médio
  - Ação: logging estruturado com request-id; nunca logar telefone/conteúdo cru.

## 5. Testes / CI / qualidade 🟢

- [ ] **#16 — Sem CI (ruff + mypy + pytest) e sem pre-commit.** 🟠 · baixo
  - Ação: GitHub Actions; opcional `pre-commit`.

- [ ] **#17 — Sem medição de cobertura.** 🟢 · baixo · `pytest-cov`.

- [ ] **#18 — Faltam testes:** payload `statuses`, template fora-da-janela (#1),
  falha da IA → handoff, `RateLimiterRedis` real. 🟢 · baixo-médio.

## 6. Dev local (Windows) 🟢

- [ ] **#19 — `asyncpg` falha no host (Python 3.14 + event loop do Windows).** 🟢 · baixo
  - O alvo (Docker, Python 3.12) funciona. Para dev local fora do Docker, definir
    `WindowsSelectorEventLoopPolicy` no startup.

---

## Histórico

- **Validação Docker (2026-06): bug corrigido** — `.dockerignore` excluía
  `README.md`, exigido pelo `pyproject` (`readme=`), quebrando `docker compose
  build`. Corrigido com exceção `!README.md` (commit `5df0d0d`). Migration
  validada no Postgres real (`alembic check` sem drift; reversível).
