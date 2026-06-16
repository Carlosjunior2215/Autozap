"""Modelo de contato (cliente identificado pelo telefone/wa_id)."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Contato(Base):
    """Cliente que interage com o número de negócio."""

    __tablename__ = "contatos"

    id: Mapped[int] = mapped_column(primary_key=True)
    telefone: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    nome: Mapped[str | None] = mapped_column(String(255), default=None)
    opt_out: Mapped[bool] = mapped_column(Boolean, default=False)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
