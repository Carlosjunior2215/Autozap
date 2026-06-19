"""Rotas do webhook da WhatsApp Cloud API."""

import json
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, Request, Response
from fastapi.responses import PlainTextResponse

from app.api.deps import EnfileiradorIngestao, obter_enfileirador_ingestao
from app.core.config import Configuracoes, obter_configuracoes
from app.core.seguranca import verificar_assinatura, verificar_token_webhook

roteador = APIRouter(tags=["webhook"])


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
    config: Annotated[Configuracoes, Depends(obter_configuracoes)],
    enfileirar_ingestao: Annotated[EnfileiradorIngestao, Depends(obter_enfileirador_ingestao)],
    x_hub_signature_256: Annotated[str | None, Header()] = None,
) -> Response:
    """Valida a assinatura e responde 200 rápido; ingestão segue de forma durável.

    A Meta reentrega eventos se a resposta demorar/falhar; por isso só fazemos no
    request o indispensável (assinatura + parse) e delegamos a persistência e o
    enfileiramento a uma tarefa Celery (broker Redis), que sobrevive a quedas do
    processo — diferente da ``BackgroundTask`` efêmera anterior (#21).
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

    enfileirar_ingestao(dados)
    return Response(status_code=200)
