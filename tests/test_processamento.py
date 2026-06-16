"""Testes da orquestração de processamento (regras de negócio ponta a ponta)."""

from datetime import timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.integrations.ia import ResultadoIntencao
from app.models import Contato, Conversa, Intencao, Mensagem, Template
from app.models.enums import OrigemMensagem, StatusMensagem
from app.services.processamento import Dependencias, processar
from app.services.tempo import agora_utc
from tests._fabricas import criar_mensagem_cliente
from tests.fakes.ia import FakeClassificadorIA, FakeGeradorRespostaIA
from tests.fakes.rate_limit import FakeRateLimiter
from tests.fakes.whatsapp import FakeWhatsAppClient


@pytest.mark.parametrize(
    ("texto", "esperada"),
    [
        ("Quero agendar um horário", "agendamento"),
        ("Qual o preço do serviço?", "servicos"),
        ("Tem alguma promoção ou desconto?", "promocoes"),
    ],
)
async def test_classificacao_por_regras_responde(
    dependencias: Dependencias,
    sessionmaker_teste: async_sessionmaker[AsyncSession],
    whatsapp_fake: FakeWhatsAppClient,
    texto: str,
    esperada: str,
) -> None:
    mensagem_id = await criar_mensagem_cliente(sessionmaker_teste, texto=texto)
    resultado = await processar(mensagem_id, dependencias)

    assert resultado.acao == "respondida"
    assert resultado.intencao == esperada
    assert len(whatsapp_fake.envios) == 1

    async with sessionmaker_teste() as sessao:
        intencao = (await sessao.execute(select(Intencao))).scalar_one()
    assert intencao.label == esperada
    assert intencao.modelo == "regras"


async def test_intencao_ajuda_responde_com_botoes(
    dependencias: Dependencias,
    sessionmaker_teste: async_sessionmaker[AsyncSession],
    whatsapp_fake: FakeWhatsAppClient,
) -> None:
    mensagem_id = await criar_mensagem_cliente(sessionmaker_teste, texto="preciso de ajuda")
    resultado = await processar(mensagem_id, dependencias)

    assert resultado.acao == "respondida"
    assert resultado.intencao == "ajuda"
    assert whatsapp_fake.envios[0].metodo == "botoes"


async def test_fallback_llm_quando_regras_indecisas(
    dependencias: Dependencias,
    sessionmaker_teste: async_sessionmaker[AsyncSession],
    classificador_fake: FakeClassificadorIA,
) -> None:
    classificador_fake.resultado = ResultadoIntencao(intencao="servicos", confianca=0.95)
    mensagem_id = await criar_mensagem_cliente(sessionmaker_teste, texto="bom dia, tudo bem?")
    resultado = await processar(mensagem_id, dependencias)

    assert resultado.acao == "respondida"
    assert resultado.intencao == "servicos"
    assert classificador_fake.chamadas == ["bom dia, tudo bem?"]

    async with sessionmaker_teste() as sessao:
        intencao = (await sessao.execute(select(Intencao))).scalar_one()
    assert intencao.modelo == "claude-haiku-4-5"


async def test_baixa_confianca_escalona_para_humano(
    dependencias: Dependencias,
    sessionmaker_teste: async_sessionmaker[AsyncSession],
    classificador_fake: FakeClassificadorIA,
    whatsapp_fake: FakeWhatsAppClient,
) -> None:
    classificador_fake.resultado = ResultadoIntencao(intencao="outros", confianca=0.4)
    mensagem_id = await criar_mensagem_cliente(
        sessionmaker_teste, texto="mensagem ambígua qualquer"
    )
    resultado = await processar(mensagem_id, dependencias)

    assert resultado.acao == "handoff"
    assert whatsapp_fake.envios == []

    async with sessionmaker_teste() as sessao:
        conversa = (await sessao.execute(select(Conversa))).scalar_one()
    assert conversa.em_atendimento_humano is True


async def test_anti_loop_ignora_mensagem_do_bot(
    dependencias: Dependencias,
    sessionmaker_teste: async_sessionmaker[AsyncSession],
    whatsapp_fake: FakeWhatsAppClient,
) -> None:
    mensagem_id = await criar_mensagem_cliente(
        sessionmaker_teste, texto="oi", origem=OrigemMensagem.BOT
    )
    resultado = await processar(mensagem_id, dependencias)

    assert resultado.acao == "ignorada"
    assert resultado.motivo == "origem nao cliente"
    assert whatsapp_fake.envios == []


async def test_opt_out_marca_contato_e_nao_responde(
    dependencias: Dependencias,
    sessionmaker_teste: async_sessionmaker[AsyncSession],
    whatsapp_fake: FakeWhatsAppClient,
) -> None:
    mensagem_id = await criar_mensagem_cliente(sessionmaker_teste, texto="pare")
    resultado = await processar(mensagem_id, dependencias)

    assert resultado.acao == "opt_out"
    assert whatsapp_fake.envios == []

    async with sessionmaker_teste() as sessao:
        contato = (await sessao.execute(select(Contato))).scalar_one()
    assert contato.opt_out is True


async def test_contato_opt_out_previo_ignora(
    dependencias: Dependencias,
    sessionmaker_teste: async_sessionmaker[AsyncSession],
) -> None:
    mensagem_id = await criar_mensagem_cliente(
        sessionmaker_teste, texto="quero agendar", opt_out=True
    )
    resultado = await processar(mensagem_id, dependencias)
    assert resultado.acao == "ignorada"
    assert resultado.motivo == "contato opt-out"


async def test_rate_limit_excedido_nao_responde(
    dependencias: Dependencias,
    sessionmaker_teste: async_sessionmaker[AsyncSession],
    rate_limiter_fake: FakeRateLimiter,
    whatsapp_fake: FakeWhatsAppClient,
) -> None:
    rate_limiter_fake.permitir = False
    mensagem_id = await criar_mensagem_cliente(sessionmaker_teste, texto="quero agendar")
    resultado = await processar(mensagem_id, dependencias)

    assert resultado.acao == "rate_limited"
    assert whatsapp_fake.envios == []


async def test_em_atendimento_humano_nao_responde(
    dependencias: Dependencias,
    sessionmaker_teste: async_sessionmaker[AsyncSession],
    whatsapp_fake: FakeWhatsAppClient,
) -> None:
    mensagem_id = await criar_mensagem_cliente(
        sessionmaker_teste, texto="quero agendar", em_atendimento_humano=True
    )
    resultado = await processar(mensagem_id, dependencias)

    assert resultado.acao == "ignorada"
    assert resultado.motivo == "nao elegivel"
    assert whatsapp_fake.envios == []


async def test_fora_janela_usa_template_aprovado(
    dependencias: Dependencias,
    sessionmaker_teste: async_sessionmaker[AsyncSession],
    whatsapp_fake: FakeWhatsAppClient,
) -> None:
    async with sessionmaker_teste() as sessao:
        sessao.add(
            Template(
                assunto="servicos",
                conteudo="Tabela de serviços aprovada",
                ativo=True,
                aprovado_meta=True,
            )
        )
        await sessao.commit()

    antiga = agora_utc() - timedelta(hours=30)
    mensagem_id = await criar_mensagem_cliente(
        sessionmaker_teste, texto="qual o preço?", ultima_msg_cliente_em=antiga
    )
    resultado = await processar(mensagem_id, dependencias)

    assert resultado.acao == "respondida"
    assert whatsapp_fake.envios[0].conteudo == "Tabela de serviços aprovada"


async def test_fora_janela_sem_template_nao_responde(
    dependencias: Dependencias,
    sessionmaker_teste: async_sessionmaker[AsyncSession],
    whatsapp_fake: FakeWhatsAppClient,
) -> None:
    antiga = agora_utc() - timedelta(hours=30)
    mensagem_id = await criar_mensagem_cliente(
        sessionmaker_teste, texto="qual o preço?", ultima_msg_cliente_em=antiga
    )
    resultado = await processar(mensagem_id, dependencias)

    assert resultado.acao == "sem_resposta"
    assert whatsapp_fake.envios == []


async def test_dentro_janela_usa_template_em_vez_de_ia(
    dependencias: Dependencias,
    sessionmaker_teste: async_sessionmaker[AsyncSession],
    gerador_fake: FakeGeradorRespostaIA,
    whatsapp_fake: FakeWhatsAppClient,
) -> None:
    async with sessionmaker_teste() as sessao:
        sessao.add(Template(assunto="servicos", conteudo="Nossos serviços", ativo=True))
        await sessao.commit()

    mensagem_id = await criar_mensagem_cliente(sessionmaker_teste, texto="qual o preço?")
    resultado = await processar(mensagem_id, dependencias)

    assert resultado.acao == "respondida"
    assert whatsapp_fake.envios[0].conteudo == "Nossos serviços"
    # Havia template ativo: a IA não deve ter sido chamada.
    assert gerador_fake.chamadas == []


async def test_resposta_registra_mensagem_bot_e_marca_respondida(
    dependencias: Dependencias,
    sessionmaker_teste: async_sessionmaker[AsyncSession],
) -> None:
    mensagem_id = await criar_mensagem_cliente(sessionmaker_teste, texto="quero agendar")
    await processar(mensagem_id, dependencias)

    async with sessionmaker_teste() as sessao:
        mensagens = list(
            (await sessao.execute(select(Mensagem).order_by(Mensagem.id))).scalars().all()
        )
        conversa = (await sessao.execute(select(Conversa))).scalar_one()

    assert len(mensagens) == 2
    cliente_msg = next(m for m in mensagens if m.origem == OrigemMensagem.CLIENTE)
    bot_msg = next(m for m in mensagens if m.origem == OrigemMensagem.BOT)
    assert cliente_msg.respondida is True
    assert bot_msg.status == StatusMensagem.ENVIADA
    assert conversa.ultima_msg_origem == OrigemMensagem.BOT
