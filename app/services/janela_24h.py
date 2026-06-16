"""Decisão da janela de 24h da Cloud API (mensagem livre vs. template)."""

from datetime import datetime, timedelta

from app.services.tempo import para_utc

_JANELA = timedelta(hours=24)


def dentro_da_janela_24h(ultima_msg_cliente_em: datetime | None, agora: datetime) -> bool:
    """Indica se ainda estamos na janela de 24h desde a última mensagem do cliente.

    Dentro da janela é permitido enviar mensagem livre; fora dela, apenas
    templates aprovados pela Meta.
    """
    if ultima_msg_cliente_em is None:
        return False
    return (para_utc(agora) - para_utc(ultima_msg_cliente_em)) <= _JANELA
