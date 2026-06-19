"""Testes do serviço de ingestão (normalização e persistência)."""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import Contato, Conversa, Mensagem
from app.models.enums import EstadoConversa, OrigemMensagem, TipoMensagem
from app.schemas.webhook import (
    Interativo,
    MensagemEntrada,
    RespostaBotao,
    RespostaLista,
    TextoEntrada,
    WebhookPayload,
)
from app.services.deteccao import mensagem_nao_respondida
from app.services.ingestao import ingerir_e_enfileirar, ingerir_payload, normalizar
from tests._payloads import payload_botao, payload_status, payload_texto
from tests.conftest import EnfileiradorFake


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


# --- ingerir_e_enfileirar (orquestração da tarefa de ingestão durável, #21) ---


async def test_ingerir_e_enfileirar_persiste_e_enfileira(
    sessionmaker_teste: async_sessionmaker[AsyncSession],
    enfileirador_fake: EnfileiradorFake,
) -> None:
    ids = await ingerir_e_enfileirar(
        payload_texto(msg_id="wamid.E1"), sessionmaker_teste, enfileirador_fake, atraso_seg=0
    )

    async with sessionmaker_teste() as sessao:
        mensagem = (await sessao.execute(select(Mensagem))).scalar_one()

    assert ids == [mensagem.id]
    assert mensagem.tipo == TipoMensagem.TEXTO
    assert enfileirador_fake.chamadas == [mensagem.id]
    assert enfileirador_fake.atrasos == [0]


async def test_ingerir_e_enfileirar_propaga_atraso(
    sessionmaker_teste: async_sessionmaker[AsyncSession],
    enfileirador_fake: EnfileiradorFake,
) -> None:
    await ingerir_e_enfileirar(
        payload_botao(msg_id="wamid.E2"), sessionmaker_teste, enfileirador_fake, atraso_seg=300
    )
    assert enfileirador_fake.atrasos == [300]


async def test_ingerir_e_enfileirar_sem_mensagens_nao_enfileira(
    sessionmaker_teste: async_sessionmaker[AsyncSession],
    enfileirador_fake: EnfileiradorFake,
) -> None:
    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "changes": [
                    {
                        "field": "messages",
                        "value": {"statuses": [{"id": "wamid.S", "status": "delivered"}]},
                    }
                ]
            }
        ],
    }
    ids = await ingerir_e_enfileirar(payload, sessionmaker_teste, enfileirador_fake, atraso_seg=0)
    assert ids == []
    assert enfileirador_fake.chamadas == []


async def test_ingerir_e_enfileirar_dedup_nao_reenfileira(
    sessionmaker_teste: async_sessionmaker[AsyncSession],
    enfileirador_fake: EnfileiradorFake,
) -> None:
    payload = payload_texto(msg_id="wamid.EDUP")
    primeiros = await ingerir_e_enfileirar(payload, sessionmaker_teste, enfileirador_fake, 0)
    segundos = await ingerir_e_enfileirar(payload, sessionmaker_teste, enfileirador_fake, 0)

    assert len(primeiros) == 1
    assert segundos == []
    assert enfileirador_fake.chamadas == primeiros


# --- statuses outbound: resposta do atendente pausa a automação (#20) ---------


async def _conversa_do_cliente(
    sessionmaker: async_sessionmaker[AsyncSession], wa_id: str, msg_id: str
) -> int:
    """Cria contato+conversa ingerindo uma mensagem do cliente; devolve a conversa id."""
    async with sessionmaker() as sessao:
        await ingerir_payload(
            sessao, WebhookPayload.model_validate(payload_texto(wa_id=wa_id, msg_id=msg_id))
        )
        return (await sessao.execute(select(Conversa.id))).scalar_one()


async def test_status_do_atendente_marca_humano(
    sessionmaker_teste: async_sessionmaker[AsyncSession],
) -> None:
    wa = "5511700000001"
    await _conversa_do_cliente(sessionmaker_teste, wa, "wamid.C1")

    # Status outbound cujo id não é de nenhuma mensagem nossa: envio do atendente.
    async with sessionmaker_teste() as sessao:
        await ingerir_payload(
            sessao,
            WebhookPayload.model_validate(
                payload_status(recipient_id=wa, status_id="wamid.MANUAL")
            ),
        )

    async with sessionmaker_teste() as sessao:
        conversa = (await sessao.execute(select(Conversa))).scalar_one()
    assert conversa.ultima_msg_origem == OrigemMensagem.HUMANO
    # Efeito do #20: a conversa deixa de ser elegível para auto-resposta (#2).
    assert not mensagem_nao_respondida(conversa, datetime.now(UTC), minutos_sem_resposta=0)


async def test_status_do_proprio_bot_nao_marca_humano(
    sessionmaker_teste: async_sessionmaker[AsyncSession],
) -> None:
    wa = "5511700000002"
    conversa_id = await _conversa_do_cliente(sessionmaker_teste, wa, "wamid.C2")
    # Mensagem do bot já enviada (wamid conhecido), como faz o processamento.
    async with sessionmaker_teste() as sessao:
        sessao.add(
            Mensagem(
                conversa_id=conversa_id,
                origem=OrigemMensagem.BOT,
                wa_message_id="wamid.BOT",
                tipo=TipoMensagem.TEXTO,
            )
        )
        await sessao.commit()

    # O status é da mensagem do bot: não deve ser tratado como resposta humana.
    async with sessionmaker_teste() as sessao:
        await ingerir_payload(
            sessao,
            WebhookPayload.model_validate(payload_status(recipient_id=wa, status_id="wamid.BOT")),
        )

    async with sessionmaker_teste() as sessao:
        conversa = (await sessao.execute(select(Conversa))).scalar_one()
    assert conversa.ultima_msg_origem == OrigemMensagem.CLIENTE


async def test_status_de_recipient_desconhecido_e_ignorado(
    sessionmaker_teste: async_sessionmaker[AsyncSession],
) -> None:
    # Sem contato/conversa para o recipient: no-op, sem erro.
    async with sessionmaker_teste() as sessao:
        await ingerir_payload(
            sessao,
            WebhookPayload.model_validate(payload_status(recipient_id="5511999888777")),
        )
    async with sessionmaker_teste() as sessao:
        conversas = list((await sessao.execute(select(Conversa))).scalars().all())
    assert conversas == []
