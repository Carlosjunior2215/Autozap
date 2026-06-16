"""Configuração do banco de dados assíncrono (SQLAlchemy 2.x)."""

from collections.abc import AsyncIterator
from functools import lru_cache

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import obter_configuracoes


@lru_cache
def obter_engine() -> AsyncEngine:
    """Retorna o engine assíncrono (singleton) baseado na configuração."""
    config = obter_configuracoes()
    return create_async_engine(config.database_url, pool_pre_ping=True)


@lru_cache
def obter_sessionmaker() -> async_sessionmaker[AsyncSession]:
    """Retorna a fábrica de sessões assíncronas (singleton)."""
    return async_sessionmaker(obter_engine(), expire_on_commit=False)


async def obter_sessao() -> AsyncIterator[AsyncSession]:
    """Dependência FastAPI: fornece uma sessão por requisição."""
    fabrica = obter_sessionmaker()
    async with fabrica() as sessao:
        yield sessao
