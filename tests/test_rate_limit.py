"""Testes do RateLimiterRedis real, usando fakeredis (sem rede)."""

from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
from fakeredis import FakeAsyncRedis

from app.services import rate_limit
from app.services.rate_limit import RateLimiterRedis


@pytest.fixture
async def redis() -> AsyncIterator[FakeAsyncRedis]:
    """Instância isolada de Redis falso, encerrada ao fim do teste."""
    cliente = FakeAsyncRedis()
    yield cliente
    await cliente.aclose()


async def test_permite_ate_o_limite_e_depois_bloqueia(redis: FakeAsyncRedis) -> None:
    limiter = RateLimiterRedis(redis)
    # Limite 3: as três primeiras passam; a quarta excede.
    decisoes = [await limiter.pode_responder(1, 3) for _ in range(4)]
    assert decisoes == [True, True, True, False]


async def test_contadores_independentes_por_contato(redis: FakeAsyncRedis) -> None:
    limiter = RateLimiterRedis(redis)
    assert await limiter.pode_responder(1, 1) is True
    assert await limiter.pode_responder(1, 1) is False  # contato 1 estourou
    assert await limiter.pode_responder(2, 1) is True  # contato 2 é independente


async def test_define_ttl_na_chave(redis: FakeAsyncRedis) -> None:
    limiter = RateLimiterRedis(redis)
    await limiter.pode_responder(99, 5)
    chaves = await redis.keys("autozap:rl:99:*")
    assert len(chaves) == 1
    ttl = await redis.ttl(chaves[0])
    assert 0 < ttl <= 3600


async def test_janelas_horarias_separadas(
    redis: FakeAsyncRedis, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Cada chamada usa uma "hora" controlada: a virada de janela zera o contador.
    horas = iter(
        [
            datetime(2026, 1, 1, 10, tzinfo=UTC),
            datetime(2026, 1, 1, 10, tzinfo=UTC),
            datetime(2026, 1, 1, 11, tzinfo=UTC),
        ]
    )
    monkeypatch.setattr(rate_limit, "agora_utc", lambda: next(horas))
    limiter = RateLimiterRedis(redis)
    assert await limiter.pode_responder(7, 1) is True  # hora 10: 1ª
    assert await limiter.pode_responder(7, 1) is False  # hora 10: estourou
    assert await limiter.pode_responder(7, 1) is True  # hora 11: nova janela
