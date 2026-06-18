"""Ajustes de runtime dependentes da plataforma."""

import asyncio
import sys
import warnings


def configurar_event_loop() -> None:
    """No Windows, seleciona o ``SelectorEventLoop`` para o ``asyncpg`` funcionar.

    O alvo de produção é Linux (Docker, Python 3.12); este ajuste só importa para
    desenvolvimento local fora do contêiner, onde o ``ProactorEventLoop`` padrão do
    Windows é incompatível com o driver ``asyncpg``. No-op nas demais plataformas (#19).

    A API de policy está deprecada no 3.14+, mas segue sendo a forma suportada de
    trocar o loop até a remoção (3.16); o aviso é silenciado por ser intencional.
    """
    if sys.platform == "win32":  # pragma: no cover
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
