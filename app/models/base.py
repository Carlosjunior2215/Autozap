"""Base declarativa e utilitários comuns dos modelos SQLAlchemy."""

import enum

from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Classe base declarativa de todos os modelos."""


def coluna_enum[EnumT: enum.Enum](enum_cls: type[EnumT]) -> SAEnum:
    """Tipo Enum portável (VARCHAR + CHECK) que persiste os *valores* do enum.

    Usa ``native_enum=False`` para funcionar de forma idêntica em PostgreSQL e
    SQLite (usado nos testes), e ``values_callable`` para gravar o ``value`` de
    cada membro em vez do ``name``.
    """
    return SAEnum(
        enum_cls,
        native_enum=False,
        values_callable=lambda classe: [str(membro.value) for membro in classe],
        validate_strings=True,
    )
