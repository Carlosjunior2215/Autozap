"""Modelo de conversa (thread de mensagens com um contato)."""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, coluna_enum
from app.models.enums import EstadoConversa, OrigemMensagem


class Conversa(Base):
    """Thread de atendimento entre o negócio e um contato."""

    __tablename__ = "conversas"

    id: Mapped[int] = mapped_column(primary_key=True)
    contato_id: Mapped[int] = mapped_column(
        ForeignKey("contatos.id", ondelete="CASCADE"), index=True
    )
    estado: Mapped[EstadoConversa] = mapped_column(
        coluna_enum(EstadoConversa), default=EstadoConversa.NOVA
    )
    em_atendimento_humano: Mapped[bool] = mapped_column(Boolean, default=False)
    ultima_msg_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    ultima_msg_origem: Mapped[OrigemMensagem | None] = mapped_column(
        coluna_enum(OrigemMensagem), default=None
    )
    intencao_atual: Mapped[str | None] = mapped_column(String(64), default=None)
    # Acréscimo: momento da última mensagem do cliente (janela de 24h da Cloud API).
    ultima_msg_cliente_em: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    # Acréscimo: estado livre da máquina de estados de agendamento (Fase 3).
    dados_fluxo: Mapped[dict[str, Any] | None] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), default=None
    )
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
