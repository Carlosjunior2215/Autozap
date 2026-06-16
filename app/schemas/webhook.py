"""Schemas Pydantic do payload do webhook da WhatsApp Cloud API.

Os schemas são tolerantes: todos os campos têm valores padrão, de forma que um
payload com estrutura parcial/variada seja parseado sem erro. A validação de
"mensagem útil" (possui id e remetente) é feita na camada de ingestão.
"""

from pydantic import BaseModel, ConfigDict, Field


class _Base(BaseModel):
    """Base tolerante: ignora campos extras e aceita preenchimento por nome/alias."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)


class TextoEntrada(_Base):
    """Corpo de uma mensagem de texto."""

    body: str = ""


class RespostaBotao(_Base):
    """Resposta a um botão interativo (``button_reply``)."""

    id: str = ""
    title: str = ""


class RespostaLista(_Base):
    """Resposta a um item de lista interativa (``list_reply``)."""

    id: str = ""
    title: str = ""
    description: str | None = None


class Interativo(_Base):
    """Bloco ``interactive`` (resposta de botão ou lista)."""

    type: str = ""
    button_reply: RespostaBotao | None = None
    list_reply: RespostaLista | None = None


class MensagemEntrada(_Base):
    """Mensagem recebida dentro de ``value.messages``."""

    id: str = ""
    remetente: str = Field(default="", alias="from")
    timestamp: str | None = None
    type: str = ""
    text: TextoEntrada | None = None
    interactive: Interativo | None = None


class Perfil(_Base):
    """Perfil do contato."""

    name: str | None = None


class ContatoEntrada(_Base):
    """Contato dentro de ``value.contacts``."""

    wa_id: str = ""
    profile: Perfil | None = None


class Metadados(_Base):
    """Metadados do número de negócio."""

    display_phone_number: str | None = None
    phone_number_id: str | None = None


class StatusEntrada(_Base):
    """Status de entrega dentro de ``value.statuses``."""

    id: str | None = None
    status: str | None = None
    timestamp: str | None = None
    recipient_id: str | None = None


class Valor(_Base):
    """Conteúdo de ``changes[].value``."""

    messaging_product: str | None = None
    metadata: Metadados | None = None
    contacts: list[ContatoEntrada] = Field(default_factory=list)
    messages: list[MensagemEntrada] = Field(default_factory=list)
    statuses: list[StatusEntrada] = Field(default_factory=list)


class Mudanca(_Base):
    """Item de ``entry[].changes``."""

    field: str | None = None
    value: Valor = Field(default_factory=Valor)


class Entrada(_Base):
    """Item de ``entry``."""

    id: str | None = None
    changes: list[Mudanca] = Field(default_factory=list)


class WebhookPayload(_Base):
    """Payload completo do webhook da Cloud API."""

    object: str | None = None
    entry: list[Entrada] = Field(default_factory=list)
