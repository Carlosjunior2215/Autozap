# MELHORIAS.md

Backlog de melhorias, otimizações e dívidas técnicas levantadas após a entrega
das Fases 0–3 e da validação da stack no Docker. Cada item traz **severidade**
(🔴 alta / 🟠 média / 🟢 baixa), **esforço** estimado e o **local** no código.

Status: `[ ]` pendente · `[~]` parcial · `[x]` concluído.

> Convenção do projeto: avançar só com `ruff`, `mypy` e `pytest` verdes; commits
> pequenos por bloco; sem `push` sem pedido explícito.

**Concluídos:** #1–#22. Resta: #23 (correlação entre tarefas). #22 e #23 são
follow-ups levantados na validação da stack real (seção 7).

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

- [x] **#20 — Detectar resposta do atendente (statuses outbound) para parar a automação.** 🟠 · médio
  - Resolvido: a ingestão processa `value.statuses`; quando o `status.id` não
    corresponde a uma mensagem nossa (o bot grava o `wa_message_id` de cada envio),
    trata-se de um envio manual do atendente e a conversa do `recipient_id` é
    marcada com `ultima_msg_origem=HUMANO`, barrando a reavaliação do #2.
    [ingestao.py](app/services/ingestao.py).
  - Nota: pausa só a auto-resposta agendada; não coloca a conversa em atendimento
    humano permanente (se o cliente voltar a escrever, a automação reavalia).

## 2. Robustez de produção 🟠

- [x] **#4 — Task Celery sem retry / `acks_late`.** 🟠 · baixo
  - Resolvido: `task_acks_late` + `task_reject_on_worker_lost`. [celery_app.py](app/core/celery_app.py).

- [x] **#5 — Dual-write não idempotente (envia, depois faz commit).** 🟠 · médio
  - Resolvido: a mensagem do bot é gravada como `PENDENTE` e commitada antes do
    envio (depois vira `ENVIADA`); guarda de idempotência ignora mensagem do
    cliente já respondida. [processamento.py](app/services/processamento.py).

- [x] **#6 — Sem timeout/tratamento de erro nas chamadas Anthropic.** 🟠 · baixo
  - Resolvido: `timeout`/`max_retries` no `AsyncAnthropic`; erros viram `ErroIA` e
    o processamento escala para humano. [ia.py](app/integrations/ia.py).

- [x] **#7 — Race no rate limiter (`incr` depois `expire`).** 🟢 · baixo
  - Resolvido: pipeline transacional (MULTI/EXEC). [rate_limit.py](app/services/rate_limit.py).

- [x] **#8 — Config aceita segredos placeholder em produção.** 🟠 · baixo
  - Resolvido: validador recusa defaults quando `ambiente=producao`. [config.py](app/core/config.py).

## 3. Performance / otimização 🟢

- [x] **#9 — Clientes recriados a cada mensagem; `httpx` nunca fechado.** 🟠 · médio
  - Resolvido: o worker mantém um event loop e um conjunto de dependências
    persistentes por processo (`runtime.executar`/`obter_dependencias`), reusando o
    pool de `httpx`/`redis` e o engine entre as tarefas; o fechamento ocorre no
    `worker_process_shutdown`. Substitui o `asyncio.run` (loop novo) por mensagem,
    que também ligava o engine async a loops distintos.
    [runtime.py](app/workers/runtime.py), [dependencias.py](app/workers/dependencias.py),
    [tasks.py](app/workers/tasks.py), [sinais.py](app/workers/sinais.py).

- [x] **#10 — Webhook processava de forma síncrona antes de responder 200.** 🟠 · médio
  - Resolvido: o POST valida assinatura + parse e responde 200; ingestão e
    enfileiramento vão para uma `BackgroundTask`. [webhook.py](app/api/webhook.py).

- [x] **#21 — Ingestão em background é efêmera (evolução do #10).** 🟠 · médio
  - Resolvido: o webhook valida assinatura/parse e enfileira o payload bruto na
    tarefa Celery `ingerir_webhook` (broker Redis durável), respondendo 200 rápido;
    a tarefa persiste e enfileira o processamento. A orquestração
    `ingerir_e_enfileirar` é reutilizada/testada de forma isolada.
    [webhook.py](app/api/webhook.py), [tasks.py](app/workers/tasks.py),
    [deps.py](app/api/deps.py), [ingestao.py](app/services/ingestao.py).

- [x] **#11 — `eventos_metrica` é gravado mas nunca lido.** 🟢 · baixo
  - Resolvido: `GET /admin/metricas` agrega por tipo (quantidade + soma), com
    filtro opcional `desde_horas`. Serviço `agregar_metricas` (GROUP BY).
    [metricas.py](app/services/metricas.py), [admin.py](app/api/admin.py).

## 4. Observabilidade / operação 🟠

- [x] **#12 — `docker compose up` subia a stack com o banco vazio.** 🟠 · baixo
  - Resolvido: serviço `migrate` com `service_completed_successfully`. [docker-compose.yml](docker-compose.yml).

- [x] **#13 — `/health` raso; sem readiness; api sem healthcheck.** 🟢 · baixo
  - Resolvido: `/health/ready` (SELECT 1) e healthcheck da api. [main.py](app/main.py).

- [x] **#14 — Sem `lifespan` para encerrar recursos no shutdown.** 🟢 · baixo
  - Resolvido: `lifespan` encerra o pool. [main.py](app/main.py).

- [x] **#15 — Logging mínimo, sem correlação; risco de PII (LGPD).** 🟠 · médio
  - Resolvido: logging estruturado (JSON) com id de correlação ponta a ponta —
    middleware gera/propaga `X-Request-ID` (contextvar) na API e os sinais do
    Celery o levam ao worker (header `correlation_id`, fallback no id da tarefa).
    Helper `mascarar_telefone` e convenção "sem telefone/conteúdo cru".
    [logging.py](app/core/logging.py), [middleware.py](app/api/middleware.py),
    [sinais.py](app/workers/sinais.py).

## 5. Testes / CI / qualidade 🟢

- [x] **#16 — Sem CI.** 🟠 · baixo
  - Resolvido: GitHub Actions (lint, tipos, testes, build Docker). [ci.yml](.github/workflows/ci.yml).

- [x] **#17 — Sem medição de cobertura.** 🟢 · baixo · `pytest-cov`.
  - Resolvido: `pytest-cov` configurado em `pyproject.toml` (branch on, gate
    `fail_under=88`, ~90% atual), omitindo só a composição de infra do worker; o
    CI roda `pytest --cov`. `pytest` puro segue sem gate (runs isolados).

- [x] **#18 — Faltam testes:** payload `statuses`, falha da IA (clientes reais) e
  `RateLimiterRedis` real. 🟢 · baixo-médio.
  - Resolvido: `statuses` coberto junto ao #20; `test_ia.py` exercita
    `ClassificadorHaiku`/`GeradorSonnet` (parsing, fallback, contexto e `APIError`
    → `ErroIA`) com um dublê do SDK; `test_rate_limit.py` testa o
    `RateLimiterRedis` real com `fakeredis` (limite, TTL, janelas). `fakeredis`
    entrou nas deps de dev.

## 6. Dev local (Windows) 🟢

- [x] **#19 — `asyncpg` falha no host (Python 3.14 + event loop do Windows).** 🟢 · baixo
  - Resolvido: `configurar_event_loop` ([runtime.py](app/core/runtime.py)) define a
    `WindowsSelectorEventLoopPolicy` só no Windows (no-op em Linux/Docker), chamada
    no startup da API e do worker. [main.py](app/main.py),
    [celery_app.py](app/core/celery_app.py).

## 7. Follow-ups da validação da stack real 🟠

- [x] **#22 — Erros de envio ao WhatsApp estouravam a tarefa.** 🟠 · baixo
  - Observado na stack: com `WHATSAPP_ACCESS_TOKEN` vazio, o envio levantava
    `httpx.HTTPError` não tratado e a tarefa falhava (sem escalar).
  - Resolvido: `CloudApiWhatsAppClient._enviar` converte `httpx.HTTPError` em
    `ErroEnvio`; `processar` captura e escala para humano (`erro_envio`), análogo
    ao tratamento da IA (#6). A resposta do bot permanece `PENDENTE` (idempotência
    do #5). [whatsapp.py](app/integrations/whatsapp.py),
    [processamento.py](app/services/processamento.py).

- [ ] **#23 — Correlação não se propaga entre tarefas.** 🟠 · baixo
  - O id de correlação enfileirado no header `correlation_id` cai no fallback do
    task id no worker (provável colisão com o campo reservado do Celery). Cada
    tarefa é rastreável, mas o encadeamento API→ingestão→processamento se perde.

---

## Histórico

- **Worker persistente (2026-06):** #9 (completo) — event loop e dependências por
  processo (reuso de pool httpx/redis + engine), encerrados no shutdown do worker;
  fim do `asyncio.run` por mensagem. Backlog 100% concluído. 111 testes verdes.
- **Dev local Windows (2026-06):** #19 — `configurar_event_loop` seleciona o
  `SelectorEventLoop` no Windows (asyncpg), no startup da API e do worker; no-op
  em Linux/Docker. Backlog zerado (só #9 segue parcial). 107 testes verdes.
- **Cobertura medida (2026-06):** #17 — `pytest-cov` com branch coverage e gate de
  88% (~90% atual) no CI; `pytest` puro permanece sem gate. 105 testes verdes.
- **Cobertura de integrações (2026-06):** #18 — testes dos clientes reais de IA
  (com dublê do SDK) e do `RateLimiterRedis` real (`fakeredis`); `statuses` já
  cobertos no #20. 105 testes verdes.
- **Métricas (2026-06):** #11 — `GET /admin/metricas` agrega `eventos_metrica`
  por tipo (com filtro `desde_horas`), expondo o que já era coletado. 93 testes.
- **Observabilidade (2026-06):** #15 — logging estruturado (JSON) com correlação
  ponta a ponta (`X-Request-ID` na API → header de tarefa no worker) e
  mascaramento de telefone (LGPD). 89 testes verdes.
- **Resposta do atendente (2026-06):** #20 — a ingestão passou a processar
  `statuses` outbound e marcar a conversa como `HUMANO` quando o envio não é do
  bot (distinção por `wa_message_id`), complementando o #2. 72 testes verdes.
- **Ingestão durável (2026-06):** #21 — webhook passou a só enfileirar o payload
  bruto numa tarefa Celery (`ingerir_webhook`), eliminando a `BackgroundTask`
  efêmera do #10; ingestão+enfileiramento extraídos em `ingerir_e_enfileirar`.
  `ruff`/`mypy`/`pytest` verdes (69 testes).
- **Iteração de robustez (2026-06):** entregues #1, #4, #6, #7, #8, #9 (parcial),
  #12, #13, #14, #16 em 5 blocos commitados; `ruff`/`mypy`/`pytest` verdes e
  migration `7f9a4828c29c` validada no Postgres real.
- **Validação Docker (2026-06): bug corrigido** — `.dockerignore` excluía
  `README.md`, exigido pelo `pyproject` (`readme=`), quebrando `docker compose
  build`. Corrigido com exceção `!README.md` (commit `5df0d0d`).
