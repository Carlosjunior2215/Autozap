"""Modelo de evento de métrica (observabilidade simples)."""

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class EventoMetrica(Base):
    """Evento de métrica associado opcionalmente a uma conversa."""

    __tablename__ = "eventos_metrica"

    id: Mapped[int] = mapped_column(primary_key=True)
    tipo: Mapped[str] = mapped_column(String(64), index=True)
    conversa_id: Mapped[int | None] = mapped_column(
        ForeignKey("conversas.id", ondelete="SET NULL"), default=None, index=True
    )
    valor: Mapped[float] = mapped_column(Float, default=1.0)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
