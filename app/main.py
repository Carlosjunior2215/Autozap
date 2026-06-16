"""Ponto de entrada da API FastAPI do autozap."""

from fastapi import FastAPI

from app.core.config import obter_configuracoes


def criar_app() -> FastAPI:
    """Cria e configura a instância FastAPI da aplicação."""
    config = obter_configuracoes()
    aplicacao = FastAPI(
        title="autozap",
        description="Agente de atendimento automático no WhatsApp.",
        version="0.1.0",
        debug=config.debug,
    )

    @aplicacao.get("/health")
    async def health() -> dict[str, str]:
        """Verificação de saúde da aplicação."""
        return {"status": "ok"}

    return aplicacao


app = criar_app()
