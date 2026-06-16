"""Fábricas de dados para os testes (inserção direta via ORM)."""

from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import Contato, Conversa, Mensagem
from app.models.enums import EstadoConversa, OrigemMensagem, StatusMensagem, TipoMensagem
from app.services.tempo import agora_utc


async def criar_mensagem_cliente(
    sessionmaker: async_sessionmaker[AsyncSession],
    *,
    texto: str,
    telefone: str = "5511999999999",
    nome: str | None = "Cliente",
    opt_out: bool = False,
    em_atendimento_humano: bool = False,
    origem: OrigemMensagem = OrigemMensagem.CLIENTE,
    tipo: TipoMensagem = TipoMensagem.TEXTO,
    ultima_msg_cliente_em: datetime | None = None,
) -> int:
    """Cria contato + conversa elegível + mensagem e devolve o id da mensagem."""
    async with sessionmaker() as sessao:
        agora = agora_utc()
        contato = Contato(telefone=telefone, nome=nome, opt_out=opt_out)
        sessao.add(contato)
        await sessao.flush()
        conversa = Conversa(
            contato_id=contato.id,
            estado=EstadoConversa.EM_ANDAMENTO,
            em_atendimento_humano=em_atendimento_humano,
            ultima_msg_em=agora,
            ultima_msg_origem=origem,
            ultima_msg_cliente_em=ultima_msg_cliente_em or agora,
        )
        sessao.add(conversa)
        await sessao.flush()
        mensagem = Mensagem(
            conversa_id=conversa.id,
            wa_message_id=f"wamid.fab.{contato.id}",
            origem=origem,
            texto=texto,
            tipo=tipo,
            status=StatusMensagem.RECEBIDA,
        )
        sessao.add(mensagem)
        await sessao.flush()
        mensagem_id = mensagem.id
        await sessao.commit()
        return mensagem_id
