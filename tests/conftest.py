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
from app.core.db import obter_sessao, obter_sessionmaker
from app.main import app
from app.models import Base
from app.services.processamento import Dependencias
from tests.fakes.ia import FakeClassificadorIA, FakeGeradorRespostaIA
from tests.fakes.rate_limit import FakeRateLimiter
from tests.fakes.whatsapp import FakeWhatsAppClient

APP_SECRET_TESTE = "segredo-de-teste"
VERIFY_TOKEN_TESTE = "token-de-teste"
ADMIN_API_KEY_TESTE = "chave-admin-teste"


class EnfileiradorFake:
    """Enfileirador falso: registra os ids enfileirados e os atrasos pedidos."""

    def __init__(self) -> None:
        self.chamadas: list[int] = []
        self.atrasos: list[int] = []

    def __call__(self, mensagem_id: int, atraso_seg: int = 0) -> None:
        self.chamadas.append(mensagem_id)
        self.atrasos.append(atraso_seg)


@pytest.fixture
def config_teste() -> Configuracoes:
    """Configurações com segredos conhecidos para os testes."""
    return Configuracoes(
        whatsapp_app_secret=APP_SECRET_TESTE,
        whatsapp_verify_token=VERIFY_TOKEN_TESTE,
        admin_api_key=ADMIN_API_KEY_TESTE,
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
    app.dependency_overrides[obter_sessionmaker] = lambda: sessionmaker_teste
    app.dependency_overrides[obter_enfileirador] = lambda: enfileirador_fake

    transporte = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transporte, base_url="http://test") as c:
        yield c

    app.dependency_overrides.clear()


@pytest.fixture
def whatsapp_fake() -> FakeWhatsAppClient:
    """Cliente WhatsApp falso (registra os envios)."""
    return FakeWhatsAppClient()


@pytest.fixture
def classificador_fake() -> FakeClassificadorIA:
    """Classificador de intenção falso."""
    return FakeClassificadorIA()


@pytest.fixture
def gerador_fake() -> FakeGeradorRespostaIA:
    """Gerador de resposta falso."""
    return FakeGeradorRespostaIA()


@pytest.fixture
def rate_limiter_fake() -> FakeRateLimiter:
    """Rate limiter falso (contagem em memória)."""
    return FakeRateLimiter()


@pytest.fixture
def dependencias(
    config_teste: Configuracoes,
    sessionmaker_teste: async_sessionmaker[AsyncSession],
    whatsapp_fake: FakeWhatsAppClient,
    classificador_fake: FakeClassificadorIA,
    gerador_fake: FakeGeradorRespostaIA,
    rate_limiter_fake: FakeRateLimiter,
) -> Dependencias:
    """Monta as dependências de processamento com todos os dublês."""
    return Dependencias(
        sessionmaker=sessionmaker_teste,
        whatsapp=whatsapp_fake,
        classificador_ia=classificador_fake,
        gerador_ia=gerador_fake,
        rate_limiter=rate_limiter_fake,
        config=config_teste,
    )
