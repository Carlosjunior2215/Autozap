"""Tarefas assíncronas executadas pelo worker Celery."""

import logging

from app.core.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="processar_mensagem")
def processar_mensagem(mensagem_id: int) -> None:
    """Processa uma mensagem recebida.

    Stub da Fase 1 — a detecção de "não respondida", a classificação de intenção
    e a geração de resposta serão adicionadas na Fase 2. Por ora apenas registra.
    """
    logger.info("Mensagem %s recebida para processamento.", mensagem_id)
