"""Agregação dos eventos de métrica para o painel administrativo (#11)."""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import EventoMetrica


@dataclass(frozen=True)
class AgregadoTipo:
    """Contagem e soma dos valores de um tipo de evento de métrica."""

    tipo: str
    quantidade: int
    soma: float


async def agregar_metricas(
    sessao: AsyncSession, desde: datetime | None = None
) -> list[AgregadoTipo]:
    """Agrupa os eventos por ``tipo`` (contagem e soma), opcionalmente desde uma data.

    Ordena por quantidade decrescente (desempate pelo nome do tipo) para destacar
    os eventos mais frequentes. Lê o que o processamento já grava em
    ``eventos_metrica`` (handoffs, rate limits, respostas etc.).
    """
    quantidade = func.count().label("quantidade")
    soma = func.coalesce(func.sum(EventoMetrica.valor), 0.0).label("soma")
    consulta = select(EventoMetrica.tipo, quantidade, soma)
    if desde is not None:
        consulta = consulta.where(EventoMetrica.criado_em >= desde)
    consulta = consulta.group_by(EventoMetrica.tipo).order_by(quantidade.desc(), EventoMetrica.tipo)
    resultado = await sessao.execute(consulta)
    return [
        AgregadoTipo(tipo=linha.tipo, quantidade=int(linha.quantidade), soma=float(linha.soma))
        for linha in resultado
    ]
