"""Montagem das dependências reais usadas pelo worker (Anthropic, Redis, etc.)."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from anthropic import AsyncAnthropic
from redis.asyncio import Redis

from app.core.config import obter_configuracoes
from app.core.db import obter_sessionmaker
from app.integrations.ia import ClassificadorHaiku, GeradorSonnet
from app.integrations.whatsapp import CloudApiWhatsAppClient
from app.services.processamento import Dependencias
from app.services.rate_limit import RateLimiterRedis


@asynccontextmanager
async def criar_dependencias() -> AsyncIterator[Dependencias]:
    """Monta as dependências reais e fecha os clientes ao final.

    Como o worker executa cada tarefa em seu próprio ``asyncio.run`` (loop novo a
    cada mensagem), os clientes assíncronos são criados e encerrados por execução
    para evitar vazamento de conexões/sockets. O reuso real de pool (loop
    persistente) está registrado em MELHORIAS.md (#9).
    """
    config = obter_configuracoes()
    cliente_anthropic = AsyncAnthropic(
        api_key=config.anthropic_api_key,
        timeout=config.anthropic_timeout_seg,
        max_retries=config.anthropic_max_retries,
    )
    redis: Redis = Redis.from_url(config.redis_url)
    http = httpx.AsyncClient(timeout=config.whatsapp_timeout_seg)
    try:
        yield Dependencias(
            sessionmaker=obter_sessionmaker(),
            whatsapp=CloudApiWhatsAppClient(config, cliente_http=http),
            classificador_ia=ClassificadorHaiku(cliente_anthropic, config.modelo_classificacao),
            gerador_ia=GeradorSonnet(cliente_anthropic, config.modelo_resposta),
            rate_limiter=RateLimiterRedis(redis),
            config=config,
        )
    finally:
        await http.aclose()
        await cliente_anthropic.close()
        await redis.aclose()
