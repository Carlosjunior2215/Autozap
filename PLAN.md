# PLAN.md — Agente de Atendimento Automático no WhatsApp (autozap)

> Documento de planejamento. **Nenhum código será escrito antes do seu "ok".**
> Trabalho incremental: implemento fase por fase, rodo `ruff` + `mypy` + `pytest`
> ao final de cada fase e só avanço quando a fase atual estiver verde.

---

## 1. Visão geral da arquitetura

```
WhatsApp Cloud API ──POST /webhook──► FastAPI (assíncrono)
                                          │  1. lê corpo BRUTO (bytes)
                                          │  2. valida X-Hub-Signature-256 (HMAC SHA-256) → 403 se inválida
                                          │  3. deduplica por wa_message_id
                                          │  4. persiste contato + conversa + mensagem
                                          │  5. enfileira tarefa Celery e responde 200 rápido
                                          ▼
                                   Redis (broker/backend Celery + contadores efêmeros)
                                          ▼
Worker Celery ── processar_mensagem(mensagem_id) ──────────────────────────────────
   1. detecta "não respondida" (regras 1–3)
   2. checa opt-out / anti-loop / rate limit / janela 24h
   3. classifica intenção: regras (keywords) → fallback LLM (Haiku, JSON estrito)
   4. se confiança < 0.7 → marca em_atendimento_humano (NÃO responde)
   5. senão → seleciona template OU gera resposta livre (Sonnet)
   6. envia via WhatsAppClient → registra mensagem bot + intenção + métricas
```

**Toda chamada externa fica atrás de uma interface** para permitir mock em testes:
- `WhatsAppClient` (Protocol) com `enviar_texto`, `enviar_template` e
  `enviar_interativo` (botões/listas) → impl real `CloudApiWhatsAppClient` (httpx)
  + `FakeWhatsAppClient` que grava os envios.
- `ClassificadorIA` / `GeradorRespostaIA` (Protocols) → impl real com SDK `anthropic` + fakes.

Nenhum teste faz chamada de rede real — dependências injetadas via factory/overrides.

---

## 2. Stack e decisões de modelo de IA

| Item | Escolha |
|------|---------|
| Linguagem | Python 3.12+ |
| Web | FastAPI + Uvicorn (async) |
| Fila | Celery + Redis (broker e backend) |
| Banco | PostgreSQL + SQLAlchemy 2.x async (driver `asyncpg`) + Alembic |
| Classificação de intenção | `claude-haiku-4-5` (rápido/barato) |
| Geração de resposta | `claude-sonnet-4-6` |
| Saída JSON da classificação | `client.messages.parse()` + modelo Pydantic (validação automática) |
| Validação/config | Pydantic v2 + pydantic-settings (`.env`) |
| Testes | pytest + pytest-asyncio + httpx AsyncClient |
| Qualidade | ruff (lint+format) e mypy estrito |
| Containers | Dockerfile + docker-compose (api, worker, postgres, redis) |

**Notas sobre a Claude API** (confirmadas na referência oficial):
- Model IDs usados **exatamente** como acima — sem sufixo de data no alias.
- Classificação retorna JSON estrito `{"intencao": "...", "confianca": 0.0–1.0}` via
  structured output (`messages.parse`), categorias: `agendamento`, `serviços`,
  `promoções`, `ajuda`, `outros`. Threshold de confiança: `0.7`.
- Haiku 4.5 **não** aceita `effort` nem thinking budget → chamada simples,
  `max_tokens` pequeno (~256). `temperature` é aceito em Haiku/Sonnet 4.6.
- Resposta livre com Sonnet: `max_tokens` ~1024.
- Cliente: dentro do worker Celery uso o cliente **síncrono** `anthropic.Anthropic()`
  (Celery task é síncrona); o FastAPI não chama a Anthropic diretamente.

---

## 3. Estrutura de pastas

```
autozap/
├── app/
│   ├── main.py                 # app factory FastAPI + /health
│   ├── api/
│   │   ├── webhook.py          # GET (verificação) e POST (recebe)
│   │   ├── admin.py            # endpoints admin (API key)
│   │   └── deps.py             # injeção: sessão DB, API key, clients
│   ├── core/
│   │   ├── config.py           # Settings (pydantic-settings)
│   │   ├── db.py               # engine/session async
│   │   ├── seguranca.py        # HMAC SHA-256, verify_token, API key admin
│   │   └── celery_app.py       # instância Celery
│   ├── models/                 # SQLAlchemy (1 arquivo por tabela)
│   ├── schemas/                # Pydantic (payload Cloud API, intenção, admin)
│   ├── services/
│   │   ├── ingestao.py         # persistência + dedup
│   │   ├── deteccao.py         # regra "não respondida"
│   │   ├── classificador.py    # regras + LLM (híbrido)
│   │   ├── respostas.py        # seleção template / geração
│   │   ├── agendamento.py      # máquina de estados
│   │   ├── rate_limit.py
│   │   └── janela_24h.py
│   ├── integrations/
│   │   ├── whatsapp.py         # Protocol WhatsAppClient + impl Cloud API
│   │   └── ia.py               # Protocols IA + impl SDK anthropic
│   └── workers/
│       └── tasks.py            # tarefas Celery
├── alembic/ (env.py async + versions/)
├── tests/ (conftest.py, fakes/, test_*.py)
├── alembic.ini
├── pyproject.toml              # deps + config ruff/mypy/pytest
├── .env.example
├── Dockerfile
├── docker-compose.yml
├── README.md
├── CLAUDE.md                   # comandos build/test/run (mantido atualizado)
└── PLAN.md
```

---

## 4. Modelo de dados (SQLAlchemy + Alembic)

- **contatos** (id, telefone[unique], nome, opt_out, criado_em)
- **conversas** (id, contato_id[fk], estado, em_atendimento_humano,
  ultima_msg_em, ultima_msg_origem, intencao_atual,
  ultima_msg_cliente_em *(p/ janela 24h)*, dados_fluxo[JSONB] *(p/ FSM agendamento)*)
- **mensagens** (id, conversa_id[fk], wa_message_id[unique, p/ dedup], origem
  [cliente|bot|humano], texto, tipo, status, recebida_em, respondida)
- **intencoes** (id, mensagem_id[fk], label, confianca, modelo)
- **templates** (id, assunto, gatilho, conteudo, ativo, aprovado_meta)
- **agendamentos** (id, contato_id[fk], servico, data_hora, status)
- **promocoes** (id, titulo, conteudo, vigencia_inicio, vigencia_fim, ativa)
- **eventos_metrica** (id, tipo, conversa_id[fk], valor, criado_em)

Campos extras (`ultima_msg_cliente_em`, `dados_fluxo`) são acréscimos necessários
para janela de 24h e FSM — destacados como suposição em §8.

---

## 5. Regras de negócio (centralizadas e testáveis)

- **"Não respondida"** (todas simultâneas): (1) última msg é do cliente, (2)
  passaram ≥ N min (N configurável, default 0), (3) conversa não está em
  atendimento humano.
- **Classificação híbrida**: regras/keywords primeiro; LLM (Haiku) só quando as
  regras não decidem; `confianca < 0.7` → `em_atendimento_humano = true` e não responde.
- **Anti-loop**: ignora mensagens cuja origem seja o próprio número/bot ou outro
  número de negócio.
- **Rate limit**: máx. configurável de respostas automáticas por contato/hora.
- **Opt-out**: "pare"/"sair" → `opt_out = true`, encerra automações do contato.
- **Janela 24h**: dentro da janela → mensagem livre; fora → só template com
  `aprovado_meta = true`.
- **Handoff**: ao escalar, pausa o bot na conversa até liberação manual (admin).
- **Idempotência**: dedup do webhook por `wa_message_id`.

---

## 6. Segurança

- `X-Hub-Signature-256` (HMAC SHA-256 do corpo **bruto** com App Secret),
  `hmac.compare_digest`; 403 se inválida/ausente.
- GET `/webhook` de verificação (`hub.mode`, `hub.verify_token`, `hub.challenge`).
- Sem segredos no código — tudo via `.env` (+ `.env.example`).
- Endpoint admin de "direito ao esquecimento": apaga dados de um contato.
- Endpoints admin protegidos por API key (`X-API-Key`).

---

## 7. Fases → tarefas concretas

### Fase 0 — Bootstrap
- [ ] Estrutura de pastas + `__init__.py`.
- [ ] `pyproject.toml`: deps (fastapi, uvicorn, celery[redis], redis,
      sqlalchemy[asyncio], asyncpg, alembic, anthropic, pydantic, pydantic-settings,
      httpx) e dev (pytest, pytest-asyncio, httpx, ruff, mypy); config de ruff,
      mypy estrito e pytest (`asyncio_mode=auto`).
- [ ] `core/config.py` (Settings) + `.env.example`.
- [ ] `main.py` mínimo com `/health`.
- [ ] Dockerfile + docker-compose (api, worker, postgres, redis).
- [ ] README.md + CLAUDE.md.
- [ ] `git init` (necessário p/ commits por fase).
- **Aceite:** `ruff check`, `ruff format --check`, `mypy`, `pytest` rodam (smoke
  test) e `docker compose config` é válido.

### Fase 1 — Webhook + persistência
- [ ] Modelos SQLAlchemy (todas as tabelas) + `base.py`.
- [ ] Alembic async (`env.py`) + migration inicial.
- [ ] `core/seguranca.py`: `verificar_assinatura(corpo, header, secret)`.
- [ ] Schemas Pydantic do payload Cloud API (entry/changes/value/messages/statuses),
      incluindo `text` **e** `interactive` (button_reply / list_reply) → normalizados
      para `tipo` + texto/payload na persistência.
- [ ] GET `/webhook` (verificação) e POST `/webhook` (assinatura → dedup →
      persistência → enfileira).
- [ ] Task Celery stub `processar_mensagem(mensagem_id)`.
- [ ] Interface `WhatsAppClient` + impl Cloud API (httpx).
- **Aceite:** testes do webhook (assinatura válida/inválida/ausente, GET ok/erro,
  dedup, persistência, payload malformado) verdes com Cloud API mockada.

### Fase 2 — Classificação + respostas
- [ ] Serviço de detecção "não respondida".
- [ ] Classificador por regras (keywords PT) + interface IA + impl Haiku
      (`messages.parse` → `ResultadoIntencao`).
- [ ] Lógica híbrida + threshold 0.7 → escalonamento.
- [ ] Seleção de template + geração livre (Sonnet) via `GeradorRespostaIA`; a
      resposta pode ser texto ou interativa (botões/listas) conforme o assunto.
- [ ] Regras: anti-loop, opt-out, rate limit, janela 24h, handoff.
- [ ] Registro de `intencoes`, atualização de estado, envio, `eventos_metrica`.
- [ ] Task Celery completa orquestrando o fluxo.
- **Aceite:** testes por intenção, baixa confiança → escalonamento, anti-loop,
  opt-out, rate limit (com IA mockada).

### Fase 3 — Agendamento + admin mínimo
- [ ] FSM de agendamento (confirma serviço → oferta de horário → coleta nome →
      confirma → cria `agendamentos`), estado em `conversas.dados_fluxo`. A oferta
      de horário usa **lista interativa**; respostas chegam como `list_reply`.
- [ ] Slots configuráveis (horário comercial + duração via `.env`), evitando
      conflito com `agendamentos` já existentes.
- [ ] Endpoints admin (API key): listar conversas, ativar/editar templates e
      promoções, liberar handoff, apagar dados de contato.
- **Aceite:** teste E2E simulando conversa completa de agendamento.

---

## 8. Suposições (assumirei como default salvo objeção)

1. **Single-tenant**: um único número de negócio (App Secret, Verify Token,
   Access Token e Phone Number ID via `.env`).
2. **API key admin** única e estática (`X-API-Key`), sem usuários/roles.
3. **Categorias fixas**: agendamento, serviços, promoções, ajuda, outros.
4. **Idioma das respostas/templates**: PT-BR. `N` (atraso) default `0` min.
5. **Timezone** dos agendamentos: `America/Sao_Paulo` (configurável).
6. **Acréscimos de schema** `conversas.ultima_msg_cliente_em` e
   `conversas.dados_fluxo` (JSONB) para janela 24h e FSM.
7. **Gerência de deps**: `pyproject.toml` (PEP 621); funciona com `pip` ou `uv`.
8. Farei **`git init`** na Fase 0 e commits pequenos por fase (sem push).
9. Testes usam **SQLite async** (aiosqlite) OU Postgres efêmero — decido por
   SQLite para velocidade, salvo se você preferir Postgres real nos testes.

## 9. Decisões tomadas

1. **Celery + DB**: cada task executa corrotinas async via `asyncio.run()`; um único
   conjunto de modelos/repositórios async (driver `asyncpg`), coerente com o FastAPI.
2. **Horários (Fase 3)**: slots configuráveis simples (horário comercial + duração
   no `.env`), evitando conflito com agendamentos existentes.
3. **Rate limit / estado efêmero**: Redis (contadores com TTL por janela/contato).
4. **Tipos de mensagem**: **texto + interativos** — envio de botões/listas e parsing
   de `button_reply` / `list_reply` em todas as fases (escopo ampliado).
