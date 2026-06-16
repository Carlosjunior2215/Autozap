"""Modelo de promoção."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Promocao(Base):
    """Promoção com período de vigência."""

    __tablename__ = "promocoes"

    id: Mapped[int] = mapped_column(primary_key=True)
    titulo: Mapped[str] = mapped_column(String(255))
    conteudo: Mapped[str] = mapped_column(Text)
    vigencia_inicio: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    vigencia_fim: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    ativa: Mapped[bool] = mapped_column(Boolean, default=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
