"""Testes de fumaça da Fase 0."""

import httpx


async def test_health_responde_ok(cliente: httpx.AsyncClient) -> None:
    """O endpoint /health deve responder 200 com status ok."""
    resposta = await cliente.get("/health")
    assert resposta.status_code == 200
    assert resposta.json() == {"status": "ok"}


async def test_health_ready_verifica_banco(cliente: httpx.AsyncClient) -> None:
    """O /health/ready deve responder 200 quando o banco está acessível."""
    resposta = await cliente.get("/health/ready")
    assert resposta.status_code == 200
    assert resposta.json()["db"] == "ok"
