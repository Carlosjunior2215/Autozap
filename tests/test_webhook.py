"""Testes das rotas do webhook (verificação, assinatura, dedup, persistência)."""

import json
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.seguranca import gerar_assinatura
from app.models import Conversa, Mensagem
from app.models.enums import OrigemMensagem, TipoMensagem
from tests._payloads import payload_botao, payload_texto
from tests.conftest import (
    ADMIN_API_KEY_TESTE,
    APP_SECRET_TESTE,
    VERIFY_TOKEN_TESTE,
    EnfileiradorFake,
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


async def test_post_json_malformado_400(cliente: httpx.AsyncClient) -> None:
    corpo = b"{ invalido"
    cabecalhos = {"X-Hub-Signature-256": gerar_assinatura(corpo, APP_SECRET_TESTE)}
    resposta = await cliente.post("/webhook", content=corpo, headers=cabecalhos)
    assert resposta.status_code == 400


async def test_post_payload_nao_objeto_400(cliente: httpx.AsyncClient) -> None:
    corpo = b"[]"
    cabecalhos = {"X-Hub-Signature-256": gerar_assinatura(corpo, APP_SECRET_TESTE)}
    resposta = await cliente.post("/webhook", content=corpo, headers=cabecalhos)
    assert resposta.status_code == 400


# --- POST (persistência e enfileiramento) --------------------------------


async def test_post_texto_persiste_e_enfileira(
    cliente: httpx.AsyncClient,
    sessionmaker_teste: async_sessionmaker[AsyncSession],
    enfileirador_fake: EnfileiradorFake,
) -> None:
    resposta = await _post_webhook(cliente, payload_texto(msg_id="wamid.X1"))
    assert resposta.status_code == 200

    async with sessionmaker_teste() as sessao:
        mensagens = list((await sessao.execute(select(Mensagem))).scalars().all())
        conversas = list((await sessao.execute(select(Conversa))).scalars().all())

    assert len(mensagens) == 1
    assert mensagens[0].wa_message_id == "wamid.X1"
    assert mensagens[0].origem == OrigemMensagem.CLIENTE
    assert mensagens[0].tipo == TipoMensagem.TEXTO
    assert mensagens[0].texto == "Quero agendar um horário"
    assert len(conversas) == 1
    assert conversas[0].ultima_msg_cliente_em is not None
    assert enfileirador_fake.chamadas == [mensagens[0].id]


async def test_post_sem_atraso_por_padrao(
    cliente: httpx.AsyncClient, enfileirador_fake: EnfileiradorFake
) -> None:
    # Com MINUTOS_SEM_RESPOSTA=0 (padrão), enfileira sem atraso.
    await _post_webhook(cliente, payload_texto(msg_id="wamid.SEMATRASO"))
    assert enfileirador_fake.atrasos == [0]


async def test_post_agenda_com_atraso_quando_configurado(
    cliente: httpx.AsyncClient, enfileirador_fake: EnfileiradorFake
) -> None:
    # Com MINUTOS_SEM_RESPOSTA=5, a reavaliação é agendada para 300s à frente.
    from app.core.config import Configuracoes, obter_configuracoes
    from app.main import app

    app.dependency_overrides[obter_configuracoes] = lambda: Configuracoes(
        whatsapp_app_secret=APP_SECRET_TESTE,
        whatsapp_verify_token=VERIFY_TOKEN_TESTE,
        admin_api_key=ADMIN_API_KEY_TESTE,
        minutos_sem_resposta=5,
    )
    await _post_webhook(cliente, payload_texto(msg_id="wamid.COMATRASO"))
    assert enfileirador_fake.atrasos[-1] == 300


async def test_post_dedup_nao_reprocessa(
    cliente: httpx.AsyncClient,
    sessionmaker_teste: async_sessionmaker[AsyncSession],
    enfileirador_fake: EnfileiradorFake,
) -> None:
    payload = payload_texto(msg_id="wamid.DUP")
    assert (await _post_webhook(cliente, payload)).status_code == 200
    assert (await _post_webhook(cliente, payload)).status_code == 200

    async with sessionmaker_teste() as sessao:
        mensagens = list((await sessao.execute(select(Mensagem))).scalars().all())

    assert len(mensagens) == 1
    assert enfileirador_fake.chamadas == [mensagens[0].id]


async def test_post_interativo_button_reply(
    cliente: httpx.AsyncClient,
    sessionmaker_teste: async_sessionmaker[AsyncSession],
) -> None:
    resposta = await _post_webhook(cliente, payload_botao(msg_id="wamid.BTN"))
    assert resposta.status_code == 200

    async with sessionmaker_teste() as sessao:
        mensagem = (
            await sessao.execute(select(Mensagem).where(Mensagem.wa_message_id == "wamid.BTN"))
        ).scalar_one()

    assert mensagem.tipo == TipoMensagem.INTERATIVO
    assert mensagem.texto == "Sim"
    assert mensagem.payload_interativo == "opt_sim"


async def test_post_sem_mensagens_nao_enfileira(
    cliente: httpx.AsyncClient, enfileirador_fake: EnfileiradorFake
) -> None:
    # Payload de status (sem mensagens) não deve enfileirar nada.
    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "changes": [
                    {
                        "field": "messages",
                        "value": {"statuses": [{"id": "wamid.S", "status": "delivered"}]},
                    }
                ]
            }
        ],
    }
    resposta = await _post_webhook(cliente, payload)
    assert resposta.status_code == 200
    assert enfileirador_fake.chamadas == []


async def test_post_ignora_eco_do_proprio_numero(
    cliente: httpx.AsyncClient,
    sessionmaker_teste: async_sessionmaker[AsyncSession],
    enfileirador_fake: EnfileiradorFake,
) -> None:
    # from igual ao display_phone_number do negócio (15550000000): eco, anti-loop.
    payload = payload_texto(wa_id="15550000000", msg_id="wamid.ECHO")
    resposta = await _post_webhook(cliente, payload)
    assert resposta.status_code == 200

    async with sessionmaker_teste() as sessao:
        mensagens = list((await sessao.execute(select(Mensagem))).scalars().all())
    assert mensagens == []
    assert enfileirador_fake.chamadas == []
