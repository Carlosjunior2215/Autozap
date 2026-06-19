"""Testes do runtime persistente do worker: loop e dependências reusados (#9).

Os testes são síncronos (não ``async``) porque ``executar`` chama
``run_until_complete`` — o que exige que nenhum loop esteja rodando na thread.
"""

import asyncio
from collections.abc import Iterator

import pytest

from app.services.processamento import Dependencias
from app.workers import runtime


class _EngineFake:
    """Engine falso: registra se foi descartado (dispose)."""

    def __init__(self) -> None:
        self.disposed = False

    async def dispose(self) -> None:
        self.disposed = True


@pytest.fixture(autouse=True)
def engine_fake(monkeypatch: pytest.MonkeyPatch) -> Iterator[_EngineFake]:
    """Evita tocar o engine real em ``encerrar`` e garante o reset do runtime."""
    fake = _EngineFake()
    monkeypatch.setattr(runtime, "obter_engine", lambda: fake)
    yield fake
    runtime.encerrar()  # limpa _loop/_recursos entre os testes


async def _loop_corrente() -> asyncio.AbstractEventLoop:
    return asyncio.get_running_loop()


def test_executar_roda_corrotina_e_retorna_valor() -> None:
    async def _soma() -> int:
        return 1 + 2

    assert runtime.executar(_soma()) == 3


def test_executar_reusa_o_mesmo_loop() -> None:
    primeiro = runtime.executar(_loop_corrente())
    segundo = runtime.executar(_loop_corrente())
    assert primeiro is segundo


def test_obter_dependencias_memoiza_e_encerrar_fecha(
    monkeypatch: pytest.MonkeyPatch, dependencias: Dependencias, engine_fake: _EngineFake
) -> None:
    class _RecursosFake:
        def __init__(self) -> None:
            self.deps = dependencias
            self.fechado = False

        async def aclose(self) -> None:
            self.fechado = True

    fake = _RecursosFake()
    chamadas = {"n": 0}

    def _fabrica() -> _RecursosFake:
        chamadas["n"] += 1
        return fake

    monkeypatch.setattr(runtime, "construir_recursos", _fabrica)

    primeira = runtime.obter_dependencias()
    segunda = runtime.obter_dependencias()
    assert primeira is segunda is dependencias
    assert chamadas["n"] == 1  # criou os recursos uma única vez

    runtime.encerrar()
    assert fake.fechado is True
    assert engine_fake.disposed is True


def test_encerrar_sem_inicializacao_e_idempotente() -> None:
    # Nada foi criado: não deve levantar nem descartar o engine.
    runtime.encerrar()
    runtime.encerrar()
