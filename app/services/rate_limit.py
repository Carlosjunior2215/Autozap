"""Limite de taxa de respostas automáticas por contato (contadores no Redis)."""

from typing import Protocol

from redis.asyncio import Redis

from app.services.tempo import agora_utc


class RateLimiter(Protocol):
    """Controla quantas respostas automáticas um contato pode receber por hora."""

    async def pode_responder(self, contato_id: int, limite_por_hora: int) -> bool:
        """Registra uma tentativa de resposta e indica se está dentro do limite."""
        ...


class RateLimiterRedis:
    """Implementação com Redis: um contador por contato e janela horária (TTL)."""

    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def pode_responder(self, contato_id: int, limite_por_hora: int) -> bool:
        janela = agora_utc().strftime("%Y%m%d%H")
        chave = f"autozap:rl:{contato_id}:{janela}"
        atual = int(await self._redis.incr(chave))
        if atual == 1:
            await self._redis.expire(chave, 3600)
        return atual <= limite_por_hora
