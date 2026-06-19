"""Logging estruturado (JSON) com correlação por requisição/tarefa (#15).

Centraliza a configuração de logs num formato JSON com um id de correlação
(``X-Request-ID`` na API, id da tarefa no worker), permitindo rastrear um fluxo
ponta a ponta. Convenção de privacidade (LGPD): **nunca** logar telefone ou
conteúdo de mensagem crus — use :func:`mascarar_telefone` e jamais coloque o
corpo da mensagem em logs.
"""

from __future__ import annotations

import json
import logging
from contextvars import ContextVar, Token
from datetime import UTC, datetime
from uuid import uuid4

_correlacao: ContextVar[str | None] = ContextVar("correlacao", default=None)

# Header (não reservado) para propagar a correlação entre tarefas Celery. O nome
# "correlation_id" colide com o campo reservado do protocolo do Celery (que o
# sobrescreve com o id da tarefa), então usamos um nome próprio.
CABECALHO_CORRELACAO_TAREFA = "autozap_correlacao"

# Atributos padrão de ``logging.LogRecord`` — usados para separar os campos
# "extra" passados pelo chamador dos campos internos do registro.
_ATRIBUTOS_PADRAO = frozenset(logging.makeLogRecord({}).__dict__) | {
    "message",
    "asctime",
    "taskName",
    "correlacao",
}


def gerar_id() -> str:
    """Gera um id de correlação curto e único."""
    return uuid4().hex


def obter_correlacao() -> str | None:
    """Retorna o id de correlação do contexto atual, se houver."""
    return _correlacao.get()


def definir_correlacao(valor: str | None) -> Token[str | None]:
    """Define o id de correlação do contexto atual; devolve o token p/ restaurar."""
    return _correlacao.set(valor)


def restaurar_correlacao(token: Token[str | None]) -> None:
    """Restaura o id de correlação anterior a partir do token."""
    _correlacao.reset(token)


def mascarar_telefone(telefone: str | None) -> str:
    """Mascara um telefone para log, preservando país/DDD e os 2 últimos dígitos.

    Ex.: ``"5511999998888"`` -> ``"5511*******88"``. Evita expor o número cru em
    logs (LGPD), mantendo o mínimo útil para depuração.
    """
    if not telefone:
        return "(vazio)"
    digitos = "".join(c for c in telefone if c.isdigit())
    if len(digitos) <= 6:
        return (digitos[:1] or "") + "*" * max(len(digitos) - 1, 0)
    return digitos[:4] + "*" * (len(digitos) - 6) + digitos[-2:]


def _serializavel(valor: object) -> object:
    """Converte um valor para algo serializável em JSON (fallback para ``str``)."""
    if valor is None or isinstance(valor, str | int | float | bool):
        return valor
    return str(valor)


class FiltroCorrelacao(logging.Filter):
    """Injeta o id de correlação atual em cada registro de log."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.correlacao = obter_correlacao() or "-"
        return True


class FormatadorJSON(logging.Formatter):
    """Formata registros como uma linha JSON (um objeto por linha)."""

    def format(self, record: logging.LogRecord) -> str:
        dados: dict[str, object] = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "nivel": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "correlacao": getattr(record, "correlacao", "-"),
        }
        # Campos extras passados via ``logger.info(..., extra={...})``.
        for chave, valor in record.__dict__.items():
            if chave not in _ATRIBUTOS_PADRAO:
                dados[chave] = _serializavel(valor)
        if record.exc_info:
            dados["excecao"] = self.formatException(record.exc_info)
        return json.dumps(dados, ensure_ascii=False, default=str)


_configurado = False


def configurar_logging(*, nivel: str = "INFO", json_logs: bool = True) -> None:
    """Configura o root logger com saída estruturada e filtro de correlação.

    Idempotente: chamadas repetidas não duplicam handlers.
    """
    global _configurado
    if _configurado:
        return
    handler = logging.StreamHandler()
    handler.addFilter(FiltroCorrelacao())
    if json_logs:
        handler.setFormatter(FormatadorJSON())
    else:
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s [%(correlacao)s] %(name)s: %(message)s")
        )
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(nivel.upper())
    _configurado = True
