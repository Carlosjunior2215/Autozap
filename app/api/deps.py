"""Dependências de injeção das rotas FastAPI."""

from typing import Protocol


class Enfileirador(Protocol):
    """Função que enfileira o processamento assíncrono de uma mensagem."""

    def __call__(self, mensagem_id: int) -> None: ...


def obter_enfileirador() -> Enfileirador:
    """Retorna o enfileirador padrão (envia a tarefa Celery para o broker)."""
    from app.workers.tasks import processar_mensagem

    def enfileirar(mensagem_id: int) -> None:
        processar_mensagem.delay(mensagem_id)

    return enfileirar
