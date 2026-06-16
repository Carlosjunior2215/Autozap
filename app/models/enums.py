"""Enumerações de domínio usadas pelos modelos."""

import enum


class OrigemMensagem(enum.StrEnum):
    """Quem enviou a mensagem na conversa."""

    CLIENTE = "cliente"
    BOT = "bot"
    HUMANO = "humano"


class TipoMensagem(enum.StrEnum):
    """Tipo normalizado da mensagem (independente do formato da Cloud API)."""

    TEXTO = "texto"
    INTERATIVO = "interativo"
    IMAGEM = "imagem"
    AUDIO = "audio"
    VIDEO = "video"
    DOCUMENTO = "documento"
    LOCALIZACAO = "localizacao"
    OUTRO = "outro"


class StatusMensagem(enum.StrEnum):
    """Status de entrega de uma mensagem."""

    RECEBIDA = "recebida"
    ENVIADA = "enviada"
    ENTREGUE = "entregue"
    LIDA = "lida"
    FALHA = "falha"


class EstadoConversa(enum.StrEnum):
    """Estado de alto nível da conversa."""

    NOVA = "nova"
    EM_ANDAMENTO = "em_andamento"
    AGUARDANDO_HUMANO = "aguardando_humano"
    AGENDAMENTO = "agendamento"
    ENCERRADA = "encerrada"


class StatusAgendamento(enum.StrEnum):
    """Status de um agendamento."""

    PENDENTE = "pendente"
    CONFIRMADO = "confirmado"
    CANCELADO = "cancelado"
    CONCLUIDO = "concluido"
