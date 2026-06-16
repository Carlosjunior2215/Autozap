"""Testes do serviço de ingestão (normalização e persistência)."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import Contato, Conversa, Mensagem
from app.models.enums import EstadoConversa, TipoMensagem
from app.schemas.webhook import (
    Interativo,
    MensagemEntrada,
    RespostaBotao,
    RespostaLista,
    TextoEntrada,
    WebhookPayload,
)
from app.services.ingestao import ingerir_payload, normalizar
from tests._payloads import payload_texto


def test_normalizar_texto() -> None:
    msg = MensagemEntrada(id="1", remetente="55", type="text", text=TextoEntrada(body="oi"))
    assert normalizar(msg) == (TipoMensagem.TEXTO, "oi", None)


def test_normalizar_button_reply() -> None:
    msg = MensagemEntrada(
        id="1",
        remetente="55",
        type="interactive",
        interactive=Interativo(
            type="button_reply", button_reply=RespostaBotao(id="b1", title="Sim")
        ),
    )
    assert normalizar(msg) == (TipoMensagem.INTERATIVO, "Sim", "b1")


def test_normalizar_list_reply() -> None:
    msg = MensagemEntrada(
        id="1",
        remetente="55",
        type="interactive",
        interactive=Interativo(
            type="list_reply", list_reply=RespostaLista(id="l1", title="Opção 1")
        ),
    )
    assert normalizar(msg) == (TipoMensagem.INTERATIVO, "Opção 1", "l1")


def test_normalizar_imagem() -> None:
    msg = MensagemEntrada(id="1", remetente="55", type="image")
    assert normalizar(msg) == (TipoMensagem.IMAGEM, None, None)


def test_normalizar_tipo_desconhecido() -> None:
    msg = MensagemEntrada(id="1", remetente="55", type="sticker")
    assert normalizar(msg) == (TipoMensagem.OUTRO, None, None)


async def test_ingerir_cria_contato_conversa_mensagem(
    sessionmaker_teste: async_sessionmaker[AsyncSession],
) -> None:
    payload = WebhookPayload.model_validate(payload_texto(wa_id="5511777", msg_id="wamid.I1"))
    async with sessionmaker_teste() as sessao:
        ids = await ingerir_payload(sessao, payload)
    assert len(ids) == 1

    async with sessionmaker_teste() as sessao:
        contato = (await sessao.execute(select(Contato))).scalar_one()
        conversa = (await sessao.execute(select(Conversa))).scalar_one()
        mensagem = (await sessao.execute(select(Mensagem))).scalar_one()

    assert contato.telefone == "5511777"
    assert contato.nome == "Cliente Teste"
    assert conversa.contato_id == contato.id
    assert conversa.estado == EstadoConversa.EM_ANDAMENTO
    assert conversa.ultima_msg_cliente_em is not None
    assert mensagem.conversa_id == conversa.id


async def test_ingerir_deduplica(
    sessionmaker_teste: async_sessionmaker[AsyncSession],
) -> None:
    payload = WebhookPayload.model_validate(payload_texto(msg_id="wamid.DD"))
    async with sessionmaker_teste() as sessao:
        primeiros = await ingerir_payload(sessao, payload)
    async with sessionmaker_teste() as sessao:
        segundos = await ingerir_payload(sessao, payload)

    assert len(primeiros) == 1
    assert segundos == []

    async with sessionmaker_teste() as sessao:
        mensagens = list((await sessao.execute(select(Mensagem))).scalars().all())
    assert len(mensagens) == 1


async def test_ingerir_reusa_conversa_existente(
    sessionmaker_teste: async_sessionmaker[AsyncSession],
) -> None:
    async with sessionmaker_teste() as sessao:
        await ingerir_payload(
            sessao,
            WebhookPayload.model_validate(payload_texto(wa_id="5511555", msg_id="wamid.A")),
        )
    async with sessionmaker_teste() as sessao:
        await ingerir_payload(
            sessao,
            WebhookPayload.model_validate(payload_texto(wa_id="5511555", msg_id="wamid.B")),
        )

    async with sessionmaker_teste() as sessao:
        conversas = list((await sessao.execute(select(Conversa))).scalars().all())
        mensagens = list((await sessao.execute(select(Mensagem))).scalars().all())

    assert len(conversas) == 1
    assert len(mensagens) == 2
