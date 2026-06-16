"""Schemas Pydantic dos endpoints administrativos."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ConversaSaida(BaseModel):
    """Visão administrativa de uma conversa."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    contato_id: int
    estado: str
    em_atendimento_humano: bool
    intencao_atual: str | None
    ultima_msg_em: datetime | None


class TemplateEntrada(BaseModel):
    """Dados para criar um template."""

    assunto: str
    gatilho: str | None = None
    conteudo: str
    ativo: bool = True
    aprovado_meta: bool = False


class TemplateAtualizacao(BaseModel):
    """Campos opcionais para atualizar um template (PATCH parcial)."""

    assunto: str | None = None
    gatilho: str | None = None
    conteudo: str | None = None
    ativo: bool | None = None
    aprovado_meta: bool | None = None


class TemplateSaida(BaseModel):
    """Representação de um template."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    assunto: str
    gatilho: str | None
    conteudo: str
    ativo: bool
    aprovado_meta: bool


class PromocaoEntrada(BaseModel):
    """Dados para criar uma promoção."""

    titulo: str
    conteudo: str
    vigencia_inicio: datetime | None = None
    vigencia_fim: datetime | None = None
    ativa: bool = True


class PromocaoAtualizacao(BaseModel):
    """Campos opcionais para atualizar uma promoção (PATCH parcial)."""

    titulo: str | None = None
    conteudo: str | None = None
    vigencia_inicio: datetime | None = None
    vigencia_fim: datetime | None = None
    ativa: bool | None = None


class PromocaoSaida(BaseModel):
    """Representação de uma promoção."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    titulo: str
    conteudo: str
    vigencia_inicio: datetime | None
    vigencia_fim: datetime | None
    ativa: bool
