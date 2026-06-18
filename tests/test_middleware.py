"""Testes do middleware de correlação (X-Request-ID) (#15)."""

import httpx

from app.api.middleware import CABECALHO_REQUEST_ID


async def test_request_id_gerado_quando_ausente(cliente: httpx.AsyncClient) -> None:
    resposta = await cliente.get("/health")
    assert resposta.status_code == 200
    assert resposta.headers.get(CABECALHO_REQUEST_ID)


async def test_request_id_propagado_quando_enviado(cliente: httpx.AsyncClient) -> None:
    resposta = await cliente.get("/health", headers={CABECALHO_REQUEST_ID: "req-fixo-123"})
    assert resposta.headers.get(CABECALHO_REQUEST_ID) == "req-fixo-123"
