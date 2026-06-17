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
        # incr + expire numa transação (MULTI/EXEC): evita a chave ficar sem TTL
        # se o processo cair entre as duas operações.
        async with self._redis.pipeline(transaction=True) as pipe:
            pipe.incr(chave)
            pipe.expire(chave, 3600)
            atual, _ = await pipe.execute()
        return int(atual) <= limite_por_hora
