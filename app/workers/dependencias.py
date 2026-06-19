"""Montagem das dependências reais usadas pelo worker (Anthropic, Redis, etc.)."""

from dataclasses import dataclass

import httpx
from anthropic import AsyncAnthropic
from redis.asyncio import Redis

from app.core.config import obter_configuracoes
from app.core.db import obter_sessionmaker
from app.integrations.ia import ClassificadorHaiku, GeradorSonnet
from app.integrations.whatsapp import CloudApiWhatsAppClient
from app.services.processamento import Dependencias
from app.services.rate_limit import RateLimiterRedis


@dataclass
class RecursosWorker:
    """Dependências do worker + os clientes externos, fecháveis no shutdown.

    Os clientes são criados uma vez por processo de worker e reusados entre as
    tarefas (mantendo o pool de conexões de ``httpx``/``redis``), em vez de
    recriados/fechados por mensagem. O fechamento ocorre no encerramento do
    processo, coordenado pelo loop persistente em :mod:`app.workers.runtime` (#9).
    """

    deps: Dependencias
    http: httpx.AsyncClient
    anthropic: AsyncAnthropic
    redis: Redis

    async def aclose(self) -> None:
        """Fecha os clientes externos (encerramento do processo de worker)."""
        await self.http.aclose()
        await self.anthropic.close()
        await self.redis.aclose()


def construir_recursos() -> RecursosWorker:
    """Cria os clientes externos e monta as dependências do worker (sem fechar)."""
    config = obter_configuracoes()
    anthropic = AsyncAnthropic(
        api_key=config.anthropic_api_key,
        timeout=config.anthropic_timeout_seg,
        max_retries=config.anthropic_max_retries,
    )
    redis: Redis = Redis.from_url(config.redis_url)
    http = httpx.AsyncClient(timeout=config.whatsapp_timeout_seg)
    deps = Dependencias(
        sessionmaker=obter_sessionmaker(),
        whatsapp=CloudApiWhatsAppClient(config, cliente_http=http),
        classificador_ia=ClassificadorHaiku(anthropic, config.modelo_classificacao),
        gerador_ia=GeradorSonnet(anthropic, config.modelo_resposta),
        rate_limiter=RateLimiterRedis(redis),
        config=config,
    )
    return RecursosWorker(deps=deps, http=http, anthropic=anthropic, redis=redis)
