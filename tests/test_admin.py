"""Testes dos endpoints administrativos (API key, CRUD, handoff, esquecimento)."""

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import Contato, Conversa, Mensagem
from tests._fabricas import criar_mensagem_cliente
from tests.conftest import ADMIN_API_KEY_TESTE

_CABECALHO: dict[str, str] = {"X-API-Key": ADMIN_API_KEY_TESTE}


async def test_admin_sem_api_key_401(cliente: httpx.AsyncClient) -> None:
    resposta = await cliente.get("/admin/conversas")
    assert resposta.status_code == 401


async def test_admin_api_key_invalida_401(cliente: httpx.AsyncClient) -> None:
    resposta = await cliente.get("/admin/conversas", headers={"X-API-Key": "errada"})
    assert resposta.status_code == 401


async def test_listar_conversas(
    cliente: httpx.AsyncClient, sessionmaker_teste: async_sessionmaker[AsyncSession]
) -> None:
    await criar_mensagem_cliente(sessionmaker_teste, texto="oi")
    resposta = await cliente.get("/admin/conversas", headers=_CABECALHO)
    assert resposta.status_code == 200
    assert len(resposta.json()) == 1


async def test_criar_listar_atualizar_template(cliente: httpx.AsyncClient) -> None:
    criar = await cliente.post(
        "/admin/templates",
        headers=_CABECALHO,
        json={"assunto": "servicos", "conteudo": "Nossos serviços"},
    )
    assert criar.status_code == 201
    template_id = criar.json()["id"]

    listar = await cliente.get("/admin/templates", headers=_CABECALHO)
    assert any(item["id"] == template_id for item in listar.json())

    atualizar = await cliente.patch(
        f"/admin/templates/{template_id}", headers=_CABECALHO, json={"ativo": False}
    )
    assert atualizar.status_code == 200
    assert atualizar.json()["ativo"] is False


async def test_criar_promocao(cliente: httpx.AsyncClient) -> None:
    resposta = await cliente.post(
        "/admin/promocoes",
        headers=_CABECALHO,
        json={"titulo": "Promo", "conteudo": "Desconto de 10%"},
    )
    assert resposta.status_code == 201
    assert resposta.json()["ativa"] is True


async def test_liberar_handoff(
    cliente: httpx.AsyncClient, sessionmaker_teste: async_sessionmaker[AsyncSession]
) -> None:
    await criar_mensagem_cliente(sessionmaker_teste, texto="oi", em_atendimento_humano=True)
    async with sessionmaker_teste() as sessao:
        conversa_id = (await sessao.execute(select(Conversa))).scalar_one().id

    resposta = await cliente.post(f"/admin/conversas/{conversa_id}/liberar", headers=_CABECALHO)
    assert resposta.status_code == 200
    assert resposta.json()["em_atendimento_humano"] is False


async def test_apagar_contato_esquecimento(
    cliente: httpx.AsyncClient, sessionmaker_teste: async_sessionmaker[AsyncSession]
) -> None:
    await criar_mensagem_cliente(sessionmaker_teste, texto="oi")
    async with sessionmaker_teste() as sessao:
        contato_id = (await sessao.execute(select(Contato))).scalar_one().id

    resposta = await cliente.delete(f"/admin/contatos/{contato_id}", headers=_CABECALHO)
    assert resposta.status_code == 204

    async with sessionmaker_teste() as sessao:
        contatos = list((await sessao.execute(select(Contato))).scalars().all())
        mensagens = list((await sessao.execute(select(Mensagem))).scalars().all())
    assert contatos == []
    assert mensagens == []


async def test_apagar_contato_inexistente_404(cliente: httpx.AsyncClient) -> None:
    resposta = await cliente.delete("/admin/contatos/9999", headers=_CABECALHO)
    assert resposta.status_code == 404
