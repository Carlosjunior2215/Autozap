"""Modelo de intenção classificada para uma mensagem."""

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Intencao(Base):
    """Resultado da classificação de intenção de uma mensagem."""

    __tablename__ = "intencoes"

    id: Mapped[int] = mapped_column(primary_key=True)
    mensagem_id: Mapped[int] = mapped_column(
        ForeignKey("mensagens.id", ondelete="CASCADE"), index=True
    )
    label: Mapped[str] = mapped_column(String(64))
    confianca: Mapped[float] = mapped_column(Float)
    modelo: Mapped[str] = mapped_column(String(64))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
