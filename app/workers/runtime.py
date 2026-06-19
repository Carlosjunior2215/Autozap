"""Loop e dependências persistentes por processo de worker (#9).

Em vez de ``asyncio.run`` por mensagem (loop e clientes novos a cada tarefa), o
worker mantém um único event loop e um único conjunto de dependências por
processo, reusando o pool de conexões (``httpx``/``redis``) e o engine do banco
entre as tarefas. O modelo prefork do Celery processa uma tarefa por vez em cada
processo, então o loop é usado sequencialmente; cada processo tem seus próprios
``_loop``/``_recursos``.
"""

import asyncio
from collections.abc import Coroutine
from typing import Any

from app.core.db import obter_engine
from app.services.processamento import Dependencias
from app.workers.dependencias import RecursosWorker, construir_recursos

_loop: asyncio.AbstractEventLoop | None = None
_recursos: RecursosWorker | None = None


def _obter_loop() -> asyncio.AbstractEventLoop:
    """Retorna o loop persistente do processo, criando-o sob demanda."""
    global _loop
    loop = _loop
    if loop is None or loop.is_closed():
        loop = asyncio.new_event_loop()
        _loop = loop
    return loop


def obter_dependencias() -> Dependencias:
    """Dependências do worker, criadas uma vez por processo e reusadas."""
    global _recursos
    recursos = _recursos
    if recursos is None:
        recursos = construir_recursos()
        _recursos = recursos
    return recursos.deps


def executar[T](coro: Coroutine[Any, Any, T]) -> T:
    """Executa a corrotina no loop persistente do processo de worker."""
    return _obter_loop().run_until_complete(coro)


def encerrar() -> None:
    """Fecha clientes, engine e loop do processo (shutdown do worker). Idempotente."""
    global _loop, _recursos
    recursos, loop = _recursos, _loop
    _recursos, _loop = None, None
    if recursos is None and (loop is None or loop.is_closed()):
        return
    fechar = loop if (loop is not None and not loop.is_closed()) else asyncio.new_event_loop()
    try:
        if recursos is not None:
            fechar.run_until_complete(recursos.aclose())
        fechar.run_until_complete(obter_engine().dispose())
    finally:
        fechar.close()
