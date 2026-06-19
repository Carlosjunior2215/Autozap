"""Testes do ajuste de event loop por plataforma (#19)."""

import asyncio
import sys

from app.core.runtime import configurar_event_loop


def test_configurar_event_loop_nao_levanta() -> None:
    # Seguro e idempotente em qualquer plataforma (no-op fora do Windows).
    configurar_event_loop()
    configurar_event_loop()


def test_configurar_event_loop_seleciona_selector_no_windows() -> None:
    configurar_event_loop()
    if sys.platform == "win32":
        # Um loop novo (criado pela policy vigente) deve ser do tipo Selector.
        loop = asyncio.new_event_loop()
        try:
            assert isinstance(loop, asyncio.SelectorEventLoop)
        finally:
            loop.close()
