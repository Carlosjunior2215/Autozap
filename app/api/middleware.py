"""Middlewares HTTP da API."""

from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging import definir_correlacao, gerar_id, restaurar_correlacao

CABECALHO_REQUEST_ID = "X-Request-ID"


class CorrelacaoMiddleware(BaseHTTPMiddleware):
    """Garante um id de correlação por requisição.

    Reaproveita o ``X-Request-ID`` recebido (se houver) ou gera um novo, deixa-o
    disponível no contexto para os logs e o devolve no cabeçalho da resposta.
    """

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        correlacao = request.headers.get(CABECALHO_REQUEST_ID) or gerar_id()
        token = definir_correlacao(correlacao)
        try:
            resposta = await call_next(request)
        finally:
            restaurar_correlacao(token)
        resposta.headers[CABECALHO_REQUEST_ID] = correlacao
        return resposta
