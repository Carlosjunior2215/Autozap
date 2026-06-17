"""Instância e configuração do Celery."""

from celery import Celery

from app.core.config import obter_configuracoes

_config = obter_configuracoes()

celery_app = Celery(
    "autozap",
    broker=_config.celery_broker_url,
    backend=_config.celery_result_backend,
)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    # Confirma a tarefa só após concluir; se o worker morrer no meio, ela volta
    # à fila (a idempotência por conversa evita reenvio na maioria dos casos).
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    timezone="UTC",
)
celery_app.autodiscover_tasks(["app.workers"])
