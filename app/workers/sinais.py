"""Sinais do Celery: logging estruturado e correlação por tarefa (#15).

Conecta a configuração de logging do worker (substituindo a padrão do Celery) e
mantém o id de correlação no contexto durante a execução de cada tarefa,
propagado pelo header ``correlation_id`` enfileirado na API.
"""

from typing import Any

from celery.signals import (
    setup_logging,
    task_postrun,
    task_prerun,
    worker_process_shutdown,
)

from app.core.config import obter_configuracoes
from app.core.logging import configurar_logging, definir_correlacao, gerar_id


def _correlacao_da_tarefa(request: Any, task_id: str | None) -> str:
    """Usa o id de correlação propagado no header da tarefa; senão, o id da tarefa."""
    correlacao = getattr(request, "correlation_id", None) if request is not None else None
    return correlacao or task_id or gerar_id()


@setup_logging.connect
def _configurar_logging_worker(**_: Any) -> None:
    config = obter_configuracoes()
    configurar_logging(nivel=config.log_nivel, json_logs=config.log_json)


@task_prerun.connect
def _inicio_tarefa(task_id: str | None = None, task: Any = None, **_: Any) -> None:
    definir_correlacao(_correlacao_da_tarefa(getattr(task, "request", None), task_id))


@task_postrun.connect
def _fim_tarefa(**_: Any) -> None:
    definir_correlacao(None)


@worker_process_shutdown.connect
def _encerrar_processo(**_: Any) -> None:
    # Fecha o loop persistente e os clientes reusados pelo processo (#9).
    from app.workers.runtime import encerrar

    encerrar()
