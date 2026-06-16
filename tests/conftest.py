"""Fixtures compartilhadas pelos testes."""

from collections.abc import AsyncIterator

import httpx
import pytest

from app.main import app


@pytest.fixture
async def cliente() -> AsyncIterator[httpx.AsyncClient]:
    """Cliente HTTP assíncrono ligado à aplicação FastAPI em memória."""
    transporte = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transporte, base_url="http://test") as c:
        yield c
