"""Dependências de injeção das rotas FastAPI."""

from typing import Any, Protocol

from app.core.logging import CABECALHO_CORRELACAO_TAREFA, gerar_id, obter_correlacao


def _headers_correlacao() -> dict[str, str]:
    """Cabeçalhos da tarefa Celery com o id de correlação atual (propagação #15)."""
    return {CABECALHO_CORRELACAO_TAREFA: obter_correlacao() or gerar_id()}


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
        headers = _headers_correlacao()
        if atraso_seg > 0:
            processar_mensagem.apply_async((mensagem_id,), countdown=atraso_seg, headers=headers)
        else:
            processar_mensagem.apply_async((mensagem_id,), headers=headers)

    return enfileirar


class EnfileiradorIngestao(Protocol):
    """Função que enfileira a ingestão durável do payload bruto do webhook."""

    def __call__(self, payload_bruto: dict[str, Any]) -> None: ...


def obter_enfileirador_ingestao() -> EnfileiradorIngestao:
    """Retorna o enfileirador de ingestão (envia o payload bruto à tarefa Celery)."""
    from app.workers.tasks import ingerir_webhook

    def enfileirar(payload_bruto: dict[str, Any]) -> None:
        ingerir_webhook.apply_async((payload_bruto,), headers=_headers_correlacao())

    return enfileirar
