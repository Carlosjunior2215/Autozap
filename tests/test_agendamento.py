"""Testes do fluxo de agendamento: geração de slots e conversa E2E."""

import json
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Configuracoes
from app.core.seguranca import gerar_assinatura
from app.models import Agendamento, Contato, Conversa
from app.models.enums import EstadoConversa, StatusAgendamento
from app.services.agenda import gerar_slots, listar_servicos
from app.services.processamento import Dependencias, processar
from app.services.tempo import agora_utc
from tests._payloads import payload_botao, payload_lista, payload_texto
from tests.conftest import APP_SECRET_TESTE, EnfileiradorFake
from tests.fakes.whatsapp import FakeWhatsAppClient


async def _enviar(
    cliente: httpx.AsyncClient, enfileirador: EnfileiradorFake, payload: dict[str, Any]
) -> int:
    """Envia uma mensagem ao webhook (assinada) e devolve o id enfileirado."""
    corpo = json.dumps(payload).encode("utf-8")
    cabecalhos = {"X-Hub-Signature-256": gerar_assinatura(corpo, APP_SECRET_TESTE)}
    resposta = await cliente.post("/webhook", content=corpo, headers=cabecalhos)
    assert resposta.status_code == 200
    return enfileirador.chamadas[-1]


def test_listar_servicos(config_teste: Configuracoes) -> None:
    servicos = listar_servicos(config_teste)
    assert servicos == ["Corte de cabelo", "Barba", "Manicure"]


async def test_gerar_slots_futuros(
    sessionmaker_teste: async_sessionmaker[AsyncSession], config_teste: Configuracoes
) -> None:
    agora = agora_utc()
    async with sessionmaker_teste() as sessao:
        slots = await gerar_slots(sessao, config_teste, agora)
    assert slots
    assert len(slots) <= config_teste.max_slots_oferecidos
    assert all(slot > agora for slot in slots)


async def test_gerar_slots_exclui_ocupado(
    sessionmaker_teste: async_sessionmaker[AsyncSession], config_teste: Configuracoes
) -> None:
    agora = agora_utc()
    async with sessionmaker_teste() as sessao:
        slots = await gerar_slots(sessao, config_teste, agora)
        primeiro = slots[0]
        contato = Contato(telefone="5511000000000", nome="X")
        sessao.add(contato)
        await sessao.flush()
        sessao.add(
            Agendamento(
                contato_id=contato.id,
                servico="Corte de cabelo",
                data_hora=primeiro,
                status=StatusAgendamento.CONFIRMADO,
            )
        )
        await sessao.commit()

    async with sessionmaker_teste() as sessao:
        novos = await gerar_slots(sessao, config_teste, agora)
    assert primeiro not in novos


async def test_e2e_agendamento_completo(
    cliente: httpx.AsyncClient,
    dependencias: Dependencias,
    sessionmaker_teste: async_sessionmaker[AsyncSession],
    whatsapp_fake: FakeWhatsAppClient,
    enfileirador_fake: EnfileiradorFake,
) -> None:
    wa = "5511955554444"

    # Turno 1: o cliente pede para agendar -> bot oferece a lista de serviços.
    mid = await _enviar(
        cliente,
        enfileirador_fake,
        payload_texto(wa_id=wa, msg_id="ag1", texto="quero agendar", nome=None),
    )
    assert (await processar(mid, dependencias)).acao == "respondida"
    assert whatsapp_fake.envios[-1].metodo == "lista"
    servico_id = whatsapp_fake.envios[-1].extra["opcoes"][0].id

    # Turno 2: o cliente escolhe o serviço -> bot oferece horários.
    mid = await _enviar(
        cliente, enfileirador_fake, payload_lista(wa_id=wa, msg_id="ag2", reply_id=servico_id)
    )
    await processar(mid, dependencias)
    assert whatsapp_fake.envios[-1].metodo == "lista"
    horario_id = whatsapp_fake.envios[-1].extra["opcoes"][0].id

    # Turno 3: o cliente escolhe o horário -> bot pede o nome.
    mid = await _enviar(
        cliente, enfileirador_fake, payload_lista(wa_id=wa, msg_id="ag3", reply_id=horario_id)
    )
    await processar(mid, dependencias)
    assert whatsapp_fake.envios[-1].metodo == "texto"
    assert "nome" in whatsapp_fake.envios[-1].conteudo.lower()

    # Turno 4: o cliente informa o nome -> bot pede confirmação (botões).
    mid = await _enviar(
        cliente,
        enfileirador_fake,
        payload_texto(wa_id=wa, msg_id="ag4", texto="Maria Silva", nome=None),
    )
    await processar(mid, dependencias)
    assert whatsapp_fake.envios[-1].metodo == "botoes"

    # Turno 5: o cliente confirma -> bot cria o agendamento.
    mid = await _enviar(
        cliente,
        enfileirador_fake,
        payload_botao(
            wa_id=wa, msg_id="ag5", botao_id="confirmar:sim", titulo="Confirmar", nome=None
        ),
    )
    assert (await processar(mid, dependencias)).acao == "respondida"

    async with sessionmaker_teste() as sessao:
        agendamento = (await sessao.execute(select(Agendamento))).scalar_one()
        conversa = (await sessao.execute(select(Conversa))).scalar_one()
        contato = (await sessao.execute(select(Contato))).scalar_one()

    assert agendamento.status == StatusAgendamento.CONFIRMADO
    assert agendamento.servico in listar_servicos(dependencias.config)
    assert conversa.estado == EstadoConversa.EM_ANDAMENTO
    assert conversa.dados_fluxo is None
    assert contato.nome == "Maria Silva"
