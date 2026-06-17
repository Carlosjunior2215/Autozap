"""Rotas do webhook da WhatsApp Cloud API."""

import json
from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Depends, Header, Query, Request, Response
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.deps import Enfileirador, obter_enfileirador
from app.core.config import Configuracoes, obter_configuracoes
from app.core.db import obter_sessionmaker
from app.core.seguranca import verificar_assinatura, verificar_token_webhook
from app.schemas.webhook import WebhookPayload
from app.services.ingestao import ingerir_payload

roteador = APIRouter(tags=["webhook"])


async def _ingerir_e_enfileirar(
    dados: dict[str, Any],
    sessionmaker: async_sessionmaker[AsyncSession],
    enfileirar: Enfileirador,
    atraso_seg: int,
) -> None:
    """Ingestão + enfileiramento, executados após responder 200 ao webhook."""
    payload = WebhookPayload.model_validate(dados)
    async with sessionmaker() as sessao:
        ids = await ingerir_payload(sessao, payload)
    for mensagem_id in ids:
        enfileirar(mensagem_id, atraso_seg)


@roteador.get("/webhook")
async def verificar_webhook(
    config: Annotated[Configuracoes, Depends(obter_configuracoes)],
    hub_mode: Annotated[str | None, Query(alias="hub.mode")] = None,
    hub_verify_token: Annotated[str | None, Query(alias="hub.verify_token")] = None,
    hub_challenge: Annotated[str | None, Query(alias="hub.challenge")] = None,
) -> Response:
    """Handshake de verificação do webhook (GET) enviado pela Meta."""
    if verificar_token_webhook(hub_mode, hub_verify_token, config.whatsapp_verify_token):
        return PlainTextResponse(hub_challenge or "")
    return PlainTextResponse("Token de verificação inválido", status_code=403)


@roteador.post("/webhook")
async def receber_webhook(
    request: Request,
    tarefas: BackgroundTasks,
    config: Annotated[Configuracoes, Depends(obter_configuracoes)],
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(obter_sessionmaker)],
    enfileirar: Annotated[Enfileirador, Depends(obter_enfileirador)],
    x_hub_signature_256: Annotated[str | None, Header()] = None,
) -> Response:
    """Valida a assinatura e responde 200 rápido; ingestão segue em background.

    A Meta reentrega eventos se a resposta demorar/falhar; por isso só fazemos no
    request o indispensável (assinatura + parse) e delegamos a persistência e o
    enfileiramento para uma tarefa de fundo.
    """
    corpo = await request.body()
    if not verificar_assinatura(corpo, x_hub_signature_256, config.whatsapp_app_secret):
        return Response(status_code=403)
    try:
        dados = json.loads(corpo)
    except json.JSONDecodeError:
        return Response(status_code=400)
    if not isinstance(dados, dict):
        return Response(status_code=400)

    atraso_seg = max(0, config.minutos_sem_resposta * 60)
    tarefas.add_task(_ingerir_e_enfileirar, dados, sessionmaker, enfileirar, atraso_seg)
    return Response(status_code=200)
