# MELHORIAS.md

Backlog de melhorias, otimizações e dívidas técnicas levantadas após a entrega
das Fases 0–3 e da validação da stack no Docker. Cada item traz **severidade**
(🔴 alta / 🟠 média / 🟢 baixa), **esforço** estimado e o **local** no código.

Status: `[ ]` pendente · `[~]` parcial · `[x]` concluído.

> Convenção do projeto: avançar só com `ruff`, `mypy` e `pytest` verdes; commits
> pequenos por bloco; sem `push` sem pedido explícito.

**Concluídos:** #1, #2, #3, #4, #6, #7, #8, #12, #13, #14, #16 e #9 (parcial).
Restam: #5, #10, #11, #15, #17, #18, #19, #20.

---

## 1. Correções funcionais (bugs de regra de negócio) 🔴

- [x] **#1 — Template fora da janela de 24h era enviado como texto livre.** 🔴 · médio
  - Resolvido: `Template` ganhou `nome_meta`/`idioma` (migration `7f9a4828c29c`);
    nova `RespostaTemplate`; fora da janela envia via `enviar_template` e, sem
    `nome_meta`, não responde. [respostas.py](app/services/respostas.py),
    [processamento.py](app/services/processamento.py).

- [x] **#2 — "Não respondida após N minutos" não tinha reavaliação agendada.** 🔴 · médio
  - Resolvido: o webhook enfileira com `countdown` = N·60 (`apply_async`); ao rodar,
    `mensagem_nao_respondida` reverifica a elegibilidade. [deps.py](app/api/deps.py),
    [webhook.py](app/api/webhook.py).

- [x] **#3 — Anti-loop não cobria o próprio número de negócio.** 🟠 · baixo
  - Resolvido: a ingestão descarta mensagens cujo `from` é o `display_phone_number`
    do negócio; `statuses` já eram ignorados. [ingestao.py](app/services/ingestao.py).

- [ ] **#20 — Detectar resposta do atendente (statuses outbound) para parar a automação.** 🟠 · médio
  - Limitação conhecida do #2: se o atendente responde pelo app durante os N
    minutos, isso chega como evento `statuses` (outbound), hoje ignorado — então a
    conversa não é marcada como respondida por humano e a auto-resposta agendada
    ainda pode disparar.
  - Ação: processar `value.statuses` (ou mensagens outbound) e marcar
    `ultima_msg_origem=HUMANO` na conversa do `recipient_id`. Complementa o #2.

## 2. Robustez de produção 🟠

- [x] **#4 — Task Celery sem retry / `acks_late`.** 🟠 · baixo
  - Resolvido: `task_acks_late` + `task_reject_on_worker_lost`. [celery_app.py](app/core/celery_app.py).

- [ ] **#5 — Dual-write não idempotente (envia, depois faz commit).** 🟠 · médio
  - Risco: envio OK + commit falha → retry reenvia. Ação: registrar a mensagem do
    bot como `PENDENTE` antes de enviar; ou chave de idempotência.

- [x] **#6 — Sem timeout/tratamento de erro nas chamadas Anthropic.** 🟠 · baixo
  - Resolvido: `timeout`/`max_retries` no `AsyncAnthropic`; erros viram `ErroIA` e
    o processamento escala para humano. [ia.py](app/integrations/ia.py).

- [x] **#7 — Race no rate limiter (`incr` depois `expire`).** 🟢 · baixo
  - Resolvido: pipeline transacional (MULTI/EXEC). [rate_limit.py](app/services/rate_limit.py).

- [x] **#8 — Config aceita segredos placeholder em produção.** 🟠 · baixo
  - Resolvido: validador recusa defaults quando `ambiente=producao`. [config.py](app/core/config.py).

## 3. Performance / otimização 🟢

- [~] **#9 — Clientes recriados a cada mensagem; `httpx` nunca fechado.** 🟠 · médio
  - Parcial: `criar_dependencias()` fecha `httpx`/`redis`/`anthropic` ao fim de
    cada tarefa (sem mais vazamento). [dependencias.py](app/workers/dependencias.py).
  - Falta: loop persistente por processo de worker para reuso real de pool.

- [ ] **#10 — Webhook processa de forma síncrona antes de responder 200.** 🟠 · médio
  - Local: [webhook.py](app/api/webhook.py). Ação: ingestão mínima + 200 rápido.

- [ ] **#11 — `eventos_metrica` é gravado mas nunca lido.** 🟢 · baixo
  - Ação: endpoint admin de métricas agregadas (ou Prometheus).

## 4. Observabilidade / operação 🟠

- [x] **#12 — `docker compose up` subia a stack com o banco vazio.** 🟠 · baixo
  - Resolvido: serviço `migrate` com `service_completed_successfully`. [docker-compose.yml](docker-compose.yml).

- [x] **#13 — `/health` raso; sem readiness; api sem healthcheck.** 🟢 · baixo
  - Resolvido: `/health/ready` (SELECT 1) e healthcheck da api. [main.py](app/main.py).

- [x] **#14 — Sem `lifespan` para encerrar recursos no shutdown.** 🟢 · baixo
  - Resolvido: `lifespan` encerra o pool. [main.py](app/main.py).

- [ ] **#15 — Logging mínimo, sem correlação; risco de PII (LGPD).** 🟠 · médio
  - Ação: logging estruturado com request-id; nunca logar telefone/conteúdo cru.

## 5. Testes / CI / qualidade 🟢

- [x] **#16 — Sem CI.** 🟠 · baixo
  - Resolvido: GitHub Actions (lint, tipos, testes, build Docker). [ci.yml](.github/workflows/ci.yml).

- [ ] **#17 — Sem medição de cobertura.** 🟢 · baixo · `pytest-cov`.

- [ ] **#18 — Faltam testes:** payload `statuses`, falha da IA (feito p/ processamento;
  falta para os clientes reais), `RateLimiterRedis` real (com `fakeredis`). 🟢 · baixo-médio.

## 6. Dev local (Windows) 🟢

- [ ] **#19 — `asyncpg` falha no host (Python 3.14 + event loop do Windows).** 🟢 · baixo
  - O alvo (Docker, Python 3.12) funciona. Para dev local fora do Docker, definir
    `WindowsSelectorEventLoopPolicy` no startup.

---

## Histórico

- **Iteração de robustez (2026-06):** entregues #1, #4, #6, #7, #8, #9 (parcial),
  #12, #13, #14, #16 em 5 blocos commitados; `ruff`/`mypy`/`pytest` verdes e
  migration `7f9a4828c29c` validada no Postgres real.
- **Validação Docker (2026-06): bug corrigido** — `.dockerignore` excluía
  `README.md`, exigido pelo `pyproject` (`readme=`), quebrando `docker compose
  build`. Corrigido com exceção `!README.md` (commit `5df0d0d`).
