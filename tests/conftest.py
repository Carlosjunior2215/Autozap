"""Fixtures compartilhadas pelos testes.

Usa SQLite assíncrono em memória (com ``StaticPool`` para compartilhar a mesma
conexão entre sessões) e sobrescreve as dependências da aplicação (banco,
configurações e enfileirador) para não tocar serviços reais.
"""

from collections.abc import AsyncIterator

import httpx
import pytest
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from app.api.deps import obter_enfileirador
from app.core.config import Configuracoes, obter_configuracoes
from app.core.db import obter_sessao
from app.main import app
from app.models import Base

APP_SECRET_TESTE = "segredo-de-teste"
VERIFY_TOKEN_TESTE = "token-de-teste"


class EnfileiradorFake:
    """Enfileirador falso: apenas registra os ids enfileirados."""

    def __init__(self) -> None:
        self.chamadas: list[int] = []

    def __call__(self, mensagem_id: int) -> None:
        self.chamadas.append(mensagem_id)


@pytest.fixture
def config_teste() -> Configuracoes:
    """Configurações com segredos conhecidos para os testes."""
    return Configuracoes(
        whatsapp_app_secret=APP_SECRET_TESTE,
        whatsapp_verify_token=VERIFY_TOKEN_TESTE,
    )


@pytest.fixture
async def engine() -> AsyncIterator[AsyncEngine]:
    """Engine SQLite em memória com as tabelas criadas a partir do metadata."""
    eng = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with eng.begin() as conexao:
        await conexao.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest.fixture
def sessionmaker_teste(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Fábrica de sessões ligada ao engine de teste."""
    return async_sessionmaker(engine, expire_on_commit=False)


@pytest.fixture
def enfileirador_fake() -> EnfileiradorFake:
    """Instância do enfileirador falso usada no teste."""
    return EnfileiradorFake()


@pytest.fixture
async def cliente(
    config_teste: Configuracoes,
    sessionmaker_teste: async_sessionmaker[AsyncSession],
    enfileirador_fake: EnfileiradorFake,
) -> AsyncIterator[httpx.AsyncClient]:
    """Cliente HTTP com as dependências da aplicação sobrescritas."""

    async def _sessao_override() -> AsyncIterator[AsyncSession]:
        async with sessionmaker_teste() as sessao:
            yield sessao

    app.dependency_overrides[obter_configuracoes] = lambda: config_teste
    app.dependency_overrides[obter_sessao] = _sessao_override
    app.dependency_overrides[obter_enfileirador] = lambda: enfileirador_fake

    transporte = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transporte, base_url="http://test") as c:
        yield c

    app.dependency_overrides.clear()
