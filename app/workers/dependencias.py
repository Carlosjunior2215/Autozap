"""Montagem das dependências reais usadas pelo worker (Anthropic, Redis, etc.)."""

from anthropic import AsyncAnthropic
from redis.asyncio import Redis

from app.core.config import obter_configuracoes
from app.core.db import obter_sessionmaker
from app.integrations.ia import ClassificadorHaiku, GeradorSonnet
from app.integrations.whatsapp import CloudApiWhatsAppClient
from app.services.processamento import Dependencias
from app.services.rate_limit import RateLimiterRedis


def montar_dependencias() -> Dependencias:
    """Instancia as dependências reais a partir das configurações."""
    config = obter_configuracoes()
    cliente_anthropic = AsyncAnthropic(api_key=config.anthropic_api_key)
    redis: Redis = Redis.from_url(config.redis_url)
    return Dependencias(
        sessionmaker=obter_sessionmaker(),
        whatsapp=CloudApiWhatsAppClient(config),
        classificador_ia=ClassificadorHaiku(cliente_anthropic, config.modelo_classificacao),
        gerador_ia=GeradorSonnet(cliente_anthropic, config.modelo_resposta),
        rate_limiter=RateLimiterRedis(redis),
        config=config,
    )
