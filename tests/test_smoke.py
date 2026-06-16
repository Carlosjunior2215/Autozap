"""Testes de fumaça da Fase 0."""

import httpx


async def test_health_responde_ok(cliente: httpx.AsyncClient) -> None:
    """O endpoint /health deve responder 200 com status ok."""
    resposta = await cliente.get("/health")
    assert resposta.status_code == 200
    assert resposta.json() == {"status": "ok"}
