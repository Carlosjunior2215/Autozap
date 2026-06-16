"""Modelo de template de resposta."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Template(Base):
    """Mensagem pré-definida associada a um assunto/gatilho."""

    __tablename__ = "templates"

    id: Mapped[int] = mapped_column(primary_key=True)
    assunto: Mapped[str] = mapped_column(String(64), index=True)
    gatilho: Mapped[str | None] = mapped_column(String(255), default=None)
    conteudo: Mapped[str] = mapped_column(Text)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    aprovado_meta: Mapped[bool] = mapped_column(Boolean, default=False)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
