"""Serviços administrativos (ex.: direito ao esquecimento)."""

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Agendamento, Contato, Conversa, EventoMetrica, Intencao, Mensagem


async def esquecer_contato(sessao: AsyncSession, contato_id: int) -> bool:
    """Apaga o contato e todos os dados relacionados.

    Remove explicitamente os registros filhos (independente de cascade do banco)
    para funcionar tanto no PostgreSQL quanto no SQLite dos testes. Retorna
    ``False`` se o contato não existir.
    """
    contato = await sessao.get(Contato, contato_id)
    if contato is None:
        return False

    conversas_ids = list(
        (await sessao.execute(select(Conversa.id).where(Conversa.contato_id == contato_id)))
        .scalars()
        .all()
    )
    if conversas_ids:
        mensagens_ids = list(
            (
                await sessao.execute(
                    select(Mensagem.id).where(Mensagem.conversa_id.in_(conversas_ids))
                )
            )
            .scalars()
            .all()
        )
        if mensagens_ids:
            await sessao.execute(delete(Intencao).where(Intencao.mensagem_id.in_(mensagens_ids)))
        await sessao.execute(delete(Mensagem).where(Mensagem.conversa_id.in_(conversas_ids)))
        await sessao.execute(
            delete(EventoMetrica).where(EventoMetrica.conversa_id.in_(conversas_ids))
        )
        await sessao.execute(delete(Conversa).where(Conversa.contato_id == contato_id))

    await sessao.execute(delete(Agendamento).where(Agendamento.contato_id == contato_id))
    await sessao.delete(contato)
    await sessao.commit()
    return True
