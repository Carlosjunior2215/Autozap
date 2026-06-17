"""Dependências de injeção das rotas FastAPI."""

from typing import Protocol


class Enfileirador(Protocol):
    """Função que enfileira o processamento assíncrono de uma mensagem.

    ``atraso_seg`` adia a execução (countdown): usado para reavaliar se a
    mensagem segue "não respondida" após N minutos.
    """

    def __call__(self, mensagem_id: int, atraso_seg: int = 0) -> None: ...


def obter_enfileirador() -> Enfileirador:
    """Retorna o enfileirador padrão (envia a tarefa Celery para o broker)."""
    from app.workers.tasks import processar_mensagem

    def enfileirar(mensagem_id: int, atraso_seg: int = 0) -> None:
        if atraso_seg > 0:
            processar_mensagem.apply_async((mensagem_id,), countdown=atraso_seg)
        else:
            processar_mensagem.delay(mensagem_id)

    return enfileirar
