"""Tarefas assíncronas executadas pelo worker Celery."""

import asyncio
import logging
from typing import Any

from app.core.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="ingerir_webhook")
def ingerir_webhook(payload_bruto: dict[str, Any]) -> None:
    """Ingere de forma durável o payload bruto recebido no webhook (#21).

    O webhook só valida assinatura/parse e enfileira o payload aqui; assim a
    persistência sobrevive a uma queda do processo (o broker Redis reentrega),
    diferente da ``BackgroundTask`` efêmera anterior. Após persistir, enfileira o
    processamento de cada mensagem nova.
    """
    from app.api.deps import obter_enfileirador
    from app.core.config import obter_configuracoes
    from app.core.db import obter_sessionmaker
    from app.services.ingestao import ingerir_e_enfileirar

    config = obter_configuracoes()
    atraso_seg = max(0, config.minutos_sem_resposta * 60)
    enfileirar = obter_enfileirador()

    async def _executar() -> list[int]:
        return await ingerir_e_enfileirar(
            payload_bruto, obter_sessionmaker(), enfileirar, atraso_seg
        )

    ids = asyncio.run(_executar())
    logger.info("Webhook ingerido: %d mensagem(ns) enfileirada(s)", len(ids))


@celery_app.task(name="processar_mensagem")
def processar_mensagem(mensagem_id: int) -> None:
    """Processa uma mensagem recebida do cliente (detecção, classificação, resposta).

    A lógica é assíncrona; aqui ela é executada via ``asyncio.run`` por tarefa,
    conforme decidido para integrar o worker síncrono do Celery ao acesso async.
    """
    from app.services.processamento import ResultadoProcessamento, processar
    from app.workers.dependencias import criar_dependencias

    async def _executar() -> ResultadoProcessamento:
        async with criar_dependencias() as deps:
            return await processar(mensagem_id, deps)

    resultado = asyncio.run(_executar())
    logger.info("Mensagem %s processada: acao=%s", mensagem_id, resultado.acao)
