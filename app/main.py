"""Ponto de entrada da API FastAPI do autozap."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, Response
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.admin import roteador as roteador_admin
from app.api.middleware import CorrelacaoMiddleware
from app.api.webhook import roteador as roteador_webhook
from app.core.config import obter_configuracoes
from app.core.db import obter_engine, obter_sessao
from app.core.logging import configurar_logging
from app.core.runtime import configurar_event_loop


@asynccontextmanager
async def ciclo_de_vida(_aplicacao: FastAPI) -> AsyncIterator[None]:
    """Gerencia recursos do processo da API: encerra o pool no shutdown."""
    yield
    await obter_engine().dispose()


def criar_app() -> FastAPI:
    """Cria e configura a instância FastAPI da aplicação."""
    configurar_event_loop()
    config = obter_configuracoes()
    configurar_logging(nivel=config.log_nivel, json_logs=config.log_json)
    aplicacao = FastAPI(
        title="autozap",
        description="Agente de atendimento automático no WhatsApp.",
        version="0.1.0",
        debug=config.debug,
        lifespan=ciclo_de_vida,
    )
    aplicacao.add_middleware(CorrelacaoMiddleware)

    @aplicacao.get("/health")
    async def health() -> dict[str, str]:
        """Liveness: indica apenas que o processo está no ar."""
        return {"status": "ok"}

    @aplicacao.get("/health/ready")
    async def health_ready(
        sessao: Annotated[AsyncSession, Depends(obter_sessao)],
    ) -> Response:
        """Readiness: verifica a conectividade com o banco de dados."""
        try:
            await sessao.execute(text("SELECT 1"))
        except SQLAlchemyError:
            return JSONResponse({"status": "indisponivel", "db": "erro"}, status_code=503)
        return JSONResponse({"status": "ok", "db": "ok"})

    aplicacao.include_router(roteador_webhook)
    aplicacao.include_router(roteador_admin)
    return aplicacao


app = criar_app()
