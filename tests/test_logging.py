"""Testes do logging estruturado, correlação e mascaramento de PII (#15)."""

import json
import logging

import pytest

from app.core.logging import (
    FiltroCorrelacao,
    FormatadorJSON,
    definir_correlacao,
    gerar_id,
    mascarar_telefone,
    obter_correlacao,
    restaurar_correlacao,
)
from app.workers.sinais import _correlacao_da_tarefa


def _formatar(record: logging.LogRecord) -> dict[str, object]:
    """Aplica o filtro de correlação e o formatador JSON; devolve o objeto parseado."""
    FiltroCorrelacao().filter(record)
    parsed: dict[str, object] = json.loads(FormatadorJSON().format(record))
    return parsed


def _registro(msg: str = "ola", **extra: object) -> logging.LogRecord:
    record = logging.LogRecord("app.teste", logging.INFO, __file__, 1, msg, None, None)
    for chave, valor in extra.items():
        setattr(record, chave, valor)
    return record


# --- Formatador JSON ------------------------------------------------------


def test_formatador_inclui_campos_base() -> None:
    dados = _formatar(_registro("mensagem de teste"))
    assert dados["nivel"] == "INFO"
    assert dados["logger"] == "app.teste"
    assert dados["msg"] == "mensagem de teste"
    assert "ts" in dados
    assert dados["correlacao"] == "-"


def test_formatador_usa_correlacao_do_contexto() -> None:
    token = definir_correlacao("req-123")
    try:
        dados = _formatar(_registro())
    finally:
        restaurar_correlacao(token)
    assert dados["correlacao"] == "req-123"


def test_formatador_inclui_campos_extra() -> None:
    dados = _formatar(_registro(acao="respondida", mensagem_id=7))
    assert dados["acao"] == "respondida"
    assert dados["mensagem_id"] == 7


def test_formatador_inclui_excecao() -> None:
    import sys

    try:
        raise ValueError("falhou")
    except ValueError:
        record = logging.LogRecord(
            "app.teste", logging.ERROR, __file__, 1, "erro", None, sys.exc_info()
        )
    dados = _formatar(record)
    assert "excecao" in dados
    assert "ValueError" in str(dados["excecao"])


# --- Correlação no contexto ----------------------------------------------


def test_correlacao_set_get_restore() -> None:
    assert obter_correlacao() is None
    token = definir_correlacao("abc")
    assert obter_correlacao() == "abc"
    restaurar_correlacao(token)
    assert obter_correlacao() is None


def test_gerar_id_unico() -> None:
    assert gerar_id() != gerar_id()


# --- Mascaramento de telefone (LGPD) -------------------------------------


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        (None, "(vazio)"),
        ("", "(vazio)"),
        ("5511999998888", "5511*******88"),
        ("+55 (11) 99999-8888", "5511*******88"),
        ("12345", "1****"),
    ],
)
def test_mascarar_telefone(entrada: str | None, esperado: str) -> None:
    assert mascarar_telefone(entrada) == esperado


def test_mascarar_nao_expoe_numero_cru() -> None:
    cru = "5511912345678"
    mascarado = mascarar_telefone(cru)
    assert cru not in mascarado
    assert mascarado.count("*") > 0


# --- Correlação da tarefa (worker) ---------------------------------------


def test_correlacao_da_tarefa_usa_header() -> None:
    class _Req:
        correlation_id = "do-header"

    assert _correlacao_da_tarefa(_Req(), "task-1") == "do-header"


def test_correlacao_da_tarefa_cai_no_task_id() -> None:
    assert _correlacao_da_tarefa(None, "task-1") == "task-1"


def test_correlacao_da_tarefa_gera_quando_ausente() -> None:
    assert _correlacao_da_tarefa(None, None)
