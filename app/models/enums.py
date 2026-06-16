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


class CategoriaIntencao(enum.StrEnum):
    """Categorias de intenção classificadas para uma mensagem."""

    AGENDAMENTO = "agendamento"
    SERVICOS = "servicos"
    PROMOCOES = "promocoes"
    AJUDA = "ajuda"
    OUTROS = "outros"

    @classmethod
    def de_texto(cls, valor: str | None) -> "CategoriaIntencao":
        """Converte uma string arbitrária (ex.: saída do LLM) em categoria válida."""
        if valor is None:
            return cls.OUTROS
        normalizado = valor.strip().lower()
        for membro in cls:
            if membro.value == normalizado:
                return membro
        return cls.OUTROS
