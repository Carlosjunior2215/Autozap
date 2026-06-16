"""Geração de horários disponíveis e lista de serviços para agendamento.

Slots simples baseados em horário comercial + duração (configuráveis), excluindo
horários já agendados — sem tabela de disponibilidade dedicada.
"""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Configuracoes
from app.models import Agendamento
from app.models.enums import StatusAgendamento
from app.services.tempo import para_utc


def listar_servicos(config: Configuracoes) -> list[str]:
    """Lista os serviços oferecidos (CSV na configuração)."""
    return [servico.strip() for servico in config.servicos_oferecidos.split(",") if servico.strip()]


async def _horarios_ocupados(sessao: AsyncSession) -> set[datetime]:
    """Conjunto de horários já agendados (não cancelados), em UTC."""
    resultado = await sessao.execute(
        select(Agendamento.data_hora).where(Agendamento.status != StatusAgendamento.CANCELADO)
    )
    return {para_utc(data_hora) for data_hora in resultado.scalars().all()}


async def gerar_slots(
    sessao: AsyncSession, config: Configuracoes, agora: datetime
) -> list[datetime]:
    """Gera horários futuros disponíveis (em UTC), excluindo os já agendados."""
    ocupados = await _horarios_ocupados(sessao)
    fuso = ZoneInfo(config.agenda_timezone)
    agora_utc = para_utc(agora)
    agora_local = agora_utc.astimezone(fuso)
    slots: list[datetime] = []
    for dia in range(config.agenda_dias_a_frente + 1):
        data = (agora_local + timedelta(days=dia)).date()
        minuto = config.agenda_hora_abertura * 60
        fim = config.agenda_hora_fechamento * 60
        while minuto < fim:
            hora, minutos = divmod(minuto, 60)
            minuto += config.agenda_duracao_min
            inicio_local = datetime(data.year, data.month, data.day, hora, minutos, tzinfo=fuso)
            inicio_utc = inicio_local.astimezone(UTC)
            if inicio_utc <= agora_utc or inicio_utc in ocupados:
                continue
            slots.append(inicio_utc)
            if len(slots) >= config.max_slots_oferecidos:
                return slots
    return slots


def formatar_horario(momento: datetime, config: Configuracoes) -> str:
    """Formata um horário (UTC) para exibição amigável no fuso configurado."""
    local = para_utc(momento).astimezone(ZoneInfo(config.agenda_timezone))
    return local.strftime("%d/%m %H:%M")
