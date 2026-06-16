"""Modelo de agendamento."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, coluna_enum
from app.models.enums import StatusAgendamento


class Agendamento(Base):
    """Horário marcado por um contato para um serviço."""

    __tablename__ = "agendamentos"

    id: Mapped[int] = mapped_column(primary_key=True)
    contato_id: Mapped[int] = mapped_column(
        ForeignKey("contatos.id", ondelete="CASCADE"), index=True
    )
    servico: Mapped[str] = mapped_column(String(255))
    data_hora: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[StatusAgendamento] = mapped_column(
        coluna_enum(StatusAgendamento), default=StatusAgendamento.PENDENTE
    )
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
