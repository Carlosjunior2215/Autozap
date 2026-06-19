"""Testes do cliente real do WhatsApp (CloudApiWhatsAppClient) com transporte falso.

Usa ``httpx.MockTransport`` para simular respostas/erros sem rede, cobrindo o
parsing do id e a conversão de falhas HTTP/transporte em :class:`ErroEnvio`.
"""

from collections.abc import Callable

import httpx
import pytest

from app.core.config import Configuracoes
from app.integrations.whatsapp import CloudApiWhatsAppClient, ErroEnvio


def _cliente(handler: Callable[[httpx.Request], httpx.Response]) -> CloudApiWhatsAppClient:
    config = Configuracoes(
        whatsapp_phone_number_id="PNID",
        whatsapp_access_token="token-teste",
    )
    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return CloudApiWhatsAppClient(config, cliente_http=http)


async def test_enviar_texto_retorna_id() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        assert req.headers["Authorization"] == "Bearer token-teste"
        return httpx.Response(200, json={"messages": [{"id": "wamid.OK"}]})

    cliente = _cliente(handler)
    try:
        assert await cliente.enviar_texto("5511999999999", "oi") == "wamid.OK"
    finally:
        await cliente.fechar()


async def test_resposta_sem_messages_retorna_vazio() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={})

    cliente = _cliente(handler)
    try:
        assert await cliente.enviar_texto("5511999999999", "oi") == ""
    finally:
        await cliente.fechar()


async def test_status_de_erro_vira_erroenvio() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "interno"})

    cliente = _cliente(handler)
    try:
        with pytest.raises(ErroEnvio):
            await cliente.enviar_texto("5511999999999", "oi")
    finally:
        await cliente.fechar()


async def test_erro_de_transporte_vira_erroenvio() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("sem rede")

    cliente = _cliente(handler)
    try:
        with pytest.raises(ErroEnvio):
            await cliente.enviar_lista("5511999999999", "corpo", "Escolha", [])
    finally:
        await cliente.fechar()
