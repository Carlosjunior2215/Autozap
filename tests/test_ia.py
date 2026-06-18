"""Testes dos clientes reais de IA (ClassificadorHaiku/GeradorSonnet) com dublê.

Substitui o ``AsyncAnthropic`` por um dublê que devolve respostas pré-montadas ou
levanta ``APIError`` — sem rede. Cobre o parsing das respostas e a conversão de
falhas do SDK em :class:`ErroIA`.
"""

from typing import Any, cast

import httpx
import pytest
from anthropic import APIConnectionError, AsyncAnthropic

from app.integrations.ia import ClassificadorHaiku, ErroIA, GeradorSonnet, ResultadoIntencao


def _erro_api() -> APIConnectionError:
    return APIConnectionError(request=httpx.Request("POST", "https://api.anthropic.com"))


class _Bloco:
    """Bloco de conteúdo da resposta (imita ``content[i]`` da Anthropic)."""

    def __init__(self, tipo: str, text: str = "") -> None:
        self.type = tipo
        self.text = text


class _RespParse:
    def __init__(self, parsed_output: ResultadoIntencao | None) -> None:
        self.parsed_output = parsed_output


class _RespCreate:
    def __init__(self, content: list[_Bloco]) -> None:
        self.content = content


class _Mensagens:
    """Dublê de ``cliente.messages``: registra os kwargs e devolve/erra conforme configurado."""

    def __init__(
        self,
        *,
        parse: _RespParse | None = None,
        parse_erro: Exception | None = None,
        create: _RespCreate | None = None,
        create_erro: Exception | None = None,
    ) -> None:
        self._parse = parse
        self._parse_erro = parse_erro
        self._create = create
        self._create_erro = create_erro
        self.kwargs_parse: dict[str, Any] = {}
        self.kwargs_create: dict[str, Any] = {}

    async def parse(self, **kwargs: Any) -> Any:
        self.kwargs_parse = kwargs
        if self._parse_erro is not None:
            raise self._parse_erro
        return self._parse

    async def create(self, **kwargs: Any) -> Any:
        self.kwargs_create = kwargs
        if self._create_erro is not None:
            raise self._create_erro
        return self._create


def _cliente(mensagens: _Mensagens) -> AsyncAnthropic:
    """Embrulha o dublê de mensagens como se fosse um ``AsyncAnthropic``."""

    class _Cliente:
        def __init__(self) -> None:
            self.messages = mensagens

    return cast(AsyncAnthropic, _Cliente())


# --- ClassificadorHaiku ---------------------------------------------------


async def test_classificar_retorna_saida_estruturada() -> None:
    esperado = ResultadoIntencao(intencao="agendamento", confianca=0.92)
    msgs = _Mensagens(parse=_RespParse(esperado))
    resultado = await ClassificadorHaiku(_cliente(msgs), "claude-haiku-4-5").classificar(
        "quero marcar"
    )
    assert resultado == esperado
    assert msgs.kwargs_parse["model"] == "claude-haiku-4-5"
    assert msgs.kwargs_parse["output_format"] is ResultadoIntencao


async def test_classificar_sem_parsed_usa_fallback() -> None:
    msgs = _Mensagens(parse=_RespParse(None))
    resultado = await ClassificadorHaiku(_cliente(msgs), "m").classificar("???")
    assert resultado.intencao == "outros"
    assert resultado.confianca == 0.0


async def test_classificar_inclui_contexto_no_conteudo() -> None:
    msgs = _Mensagens(parse=_RespParse(ResultadoIntencao(intencao="outros", confianca=0.1)))
    await ClassificadorHaiku(_cliente(msgs), "m").classificar("oi", contexto="cliente recorrente")
    conteudo = msgs.kwargs_parse["messages"][0]["content"]
    assert "cliente recorrente" in conteudo
    assert "oi" in conteudo


async def test_classificar_erro_api_vira_erroia() -> None:
    msgs = _Mensagens(parse_erro=_erro_api())
    with pytest.raises(ErroIA):
        await ClassificadorHaiku(_cliente(msgs), "m").classificar("oi")


# --- GeradorSonnet --------------------------------------------------------


async def test_gerar_retorna_texto_do_primeiro_bloco() -> None:
    msgs = _Mensagens(create=_RespCreate([_Bloco("text", "Olá! Como posso ajudar?")]))
    texto = await GeradorSonnet(_cliente(msgs), "claude-sonnet-4-6").gerar(
        "ajuda", "preciso de ajuda"
    )
    assert texto == "Olá! Como posso ajudar?"


async def test_gerar_sem_bloco_de_texto_retorna_vazio() -> None:
    msgs = _Mensagens(create=_RespCreate([_Bloco("tool_use")]))
    texto = await GeradorSonnet(_cliente(msgs), "m").gerar("outros", "x")
    assert texto == ""


async def test_gerar_inclui_contexto_no_conteudo() -> None:
    msgs = _Mensagens(create=_RespCreate([_Bloco("text", "ok")]))
    await GeradorSonnet(_cliente(msgs), "m").gerar("servicos", "qual o preço?", contexto="tabela")
    conteudo = msgs.kwargs_create["messages"][0]["content"]
    assert "tabela" in conteudo
    assert "servicos" in conteudo


async def test_gerar_erro_api_vira_erroia() -> None:
    msgs = _Mensagens(create_erro=_erro_api())
    with pytest.raises(ErroIA):
        await GeradorSonnet(_cliente(msgs), "m").gerar("ajuda", "oi")
