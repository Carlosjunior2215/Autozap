"""Utilitários de data/hora (normalização para UTC consciente de fuso)."""

from datetime import UTC, datetime


def agora_utc() -> datetime:
    """Momento atual em UTC (timezone-aware)."""
    return datetime.now(UTC)


def para_utc(momento: datetime) -> datetime:
    """Garante um datetime timezone-aware em UTC.

    O SQLite (usado nos testes) devolve datetimes *naive*; o PostgreSQL devolve
    *aware*. Normalizar evita erros ao subtrair instantes.
    """
    if momento.tzinfo is None:
        return momento.replace(tzinfo=UTC)
    return momento.astimezone(UTC)
