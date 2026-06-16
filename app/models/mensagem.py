"""Modelo de mensagem (recebida do cliente ou enviada pelo bot/humano)."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, coluna_enum
from app.models.enums import OrigemMensagem, StatusMensagem, TipoMensagem


class Mensagem(Base):
    """Uma mensagem individual de uma conversa."""

    __tablename__ = "mensagens"

    id: Mapped[int] = mapped_column(primary_key=True)
    conversa_id: Mapped[int] = mapped_column(
        ForeignKey("conversas.id", ondelete="CASCADE"), index=True
    )
    # Identificador da Cloud API (wamid...). Usado para deduplicação do webhook.
    wa_message_id: Mapped[str | None] = mapped_column(String(128), unique=True, default=None)
    origem: Mapped[OrigemMensagem] = mapped_column(coluna_enum(OrigemMensagem))
    texto: Mapped[str | None] = mapped_column(Text, default=None)
    tipo: Mapped[TipoMensagem] = mapped_column(
        coluna_enum(TipoMensagem), default=TipoMensagem.TEXTO
    )
    status: Mapped[StatusMensagem] = mapped_column(
        coluna_enum(StatusMensagem), default=StatusMensagem.RECEBIDA
    )
    # Acréscimo: id do botão/lista selecionado em respostas interativas.
    payload_interativo: Mapped[str | None] = mapped_column(String(256), default=None)
    recebida_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    respondida: Mapped[bool] = mapped_column(Boolean, default=False)
