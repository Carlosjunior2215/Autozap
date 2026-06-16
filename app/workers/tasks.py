"""Tarefas assíncronas executadas pelo worker Celery."""

import asyncio
import logging

from app.core.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="processar_mensagem")
def processar_mensagem(mensagem_id: int) -> None:
    """Processa uma mensagem recebida do cliente (detecção, classificação, resposta).

    A lógica é assíncrona; aqui ela é executada via ``asyncio.run`` por tarefa,
    conforme decidido para integrar o worker síncrono do Celery ao acesso async.
    """
    from app.services.processamento import processar
    from app.workers.dependencias import montar_dependencias

    resultado = asyncio.run(processar(mensagem_id, montar_dependencias()))
    logger.info("Mensagem %s processada: acao=%s", mensagem_id, resultado.acao)
