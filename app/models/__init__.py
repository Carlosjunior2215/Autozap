"""Modelos SQLAlchemy e Base declarativa.

Importa todos os modelos para que ``Base.metadata`` esteja completo (necessário
para o Alembic e para criação das tabelas nos testes).
"""

from app.models.agendamento import Agendamento
from app.models.base import Base
from app.models.contato import Contato
from app.models.conversa import Conversa
from app.models.enums import (
    EstadoConversa,
    OrigemMensagem,
    StatusAgendamento,
    StatusMensagem,
    TipoMensagem,
)
from app.models.evento_metrica import EventoMetrica
from app.models.intencao import Intencao
from app.models.mensagem import Mensagem
from app.models.promocao import Promocao
from app.models.template import Template

__all__ = [
    "Agendamento",
    "Base",
    "Contato",
    "Conversa",
    "EstadoConversa",
    "EventoMetrica",
    "Intencao",
    "Mensagem",
    "OrigemMensagem",
    "Promocao",
    "StatusAgendamento",
    "StatusMensagem",
    "Template",
    "TipoMensagem",
]
