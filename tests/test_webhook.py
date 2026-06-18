"""Testes das rotas do webhook (verificação, assinatura, enfileiramento)."""

import json
from typing import Any

import httpx

from app.core.seguranca import gerar_assinatura
from tests._payloads import payload_texto
from tests.conftest import (
    APP_SECRET_TESTE,
    VERIFY_TOKEN_TESTE,
    EnfileiradorIngestaoFake,
)


async def _post_webhook(
    cliente: httpx.AsyncClient,
    payload: dict[str, Any],
    *,
    secret: str = APP_SECRET_TESTE,
    assinar: bool = True,
) -> httpx.Response:
    """POST no webhook assinando o corpo bruto (como faz a Cloud API)."""
    corpo = json.dumps(payload).encode("utf-8")
    cabecalhos: dict[str, str] = {}
    if assinar:
        cabecalhos["X-Hub-Signature-256"] = gerar_assinatura(corpo, secret)
    return await cliente.post("/webhook", content=corpo, headers=cabecalhos)


# --- GET (verificação) ---------------------------------------------------


async def test_get_verificacao_ok(cliente: httpx.AsyncClient) -> None:
    resposta = await cliente.get(
        "/webhook",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": VERIFY_TOKEN_TESTE,
            "hub.challenge": "12345",
        },
    )
    assert resposta.status_code == 200
    assert resposta.text == "12345"


async def test_get_verificacao_token_invalido(cliente: httpx.AsyncClient) -> None:
    resposta = await cliente.get(
        "/webhook",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "token-errado",
            "hub.challenge": "12345",
        },
    )
    assert resposta.status_code == 403


# --- POST (assinatura) ---------------------------------------------------


async def test_post_sem_assinatura_403(cliente: httpx.AsyncClient) -> None:
    resposta = await _post_webhook(cliente, payload_texto(), assinar=False)
    assert resposta.status_code == 403


async def test_post_assinatura_invalida_403(cliente: httpx.AsyncClient) -> None:
    resposta = await _post_webhook(cliente, payload_texto(), secret="segredo-errado")
    assert resposta.status_code == 403


async def test_post_json_malformado_400(
    cliente: httpx.AsyncClient, enfileirador_ingestao_fake: EnfileiradorIngestaoFake
) -> None:
    corpo = b"{ invalido"
    cabecalhos = {"X-Hub-Signature-256": gerar_assinatura(corpo, APP_SECRET_TESTE)}
    resposta = await cliente.post("/webhook", content=corpo, headers=cabecalhos)
    assert resposta.status_code == 400
    assert enfileirador_ingestao_fake.payloads == []


async def test_post_payload_nao_objeto_400(
    cliente: httpx.AsyncClient, enfileirador_ingestao_fake: EnfileiradorIngestaoFake
) -> None:
    corpo = b"[]"
    cabecalhos = {"X-Hub-Signature-256": gerar_assinatura(corpo, APP_SECRET_TESTE)}
    resposta = await cliente.post("/webhook", content=corpo, headers=cabecalhos)
    assert resposta.status_code == 400
    assert enfileirador_ingestao_fake.payloads == []


# --- POST (enfileiramento durável da ingestão) ---------------------------


async def test_post_enfileira_ingestao(
    cliente: httpx.AsyncClient, enfileirador_ingestao_fake: EnfileiradorIngestaoFake
) -> None:
    # O webhook valida e responde 200 rápido; a ingestão vai para a tarefa Celery
    # com o payload bruto exato (sem persistir nada de forma síncrona) (#21).
    payload = payload_texto(msg_id="wamid.X1")
    resposta = await _post_webhook(cliente, payload)
    assert resposta.status_code == 200
    assert enfileirador_ingestao_fake.payloads == [payload]


async def test_post_assinatura_invalida_nao_enfileira(
    cliente: httpx.AsyncClient, enfileirador_ingestao_fake: EnfileiradorIngestaoFake
) -> None:
    resposta = await _post_webhook(cliente, payload_texto(), secret="segredo-errado")
    assert resposta.status_code == 403
    assert enfileirador_ingestao_fake.payloads == []
