"""Integração com a Anthropic (Claude): classificação e geração de resposta.

As chamadas reais ficam atrás dos Protocols :class:`ClassificadorIA` e
:class:`GeradorRespostaIA`, permitindo injetar dublês nos testes (sem rede).
"""

from typing import Protocol

from anthropic import AsyncAnthropic
from pydantic import BaseModel, Field

PROMPT_CLASSIFICACAO = """Você classifica a intenção de mensagens de clientes \
de um negócio no WhatsApp. Categorias possíveis:
- agendamento: marcar, remarcar ou cancelar horários.
- servicos: dúvidas sobre preços, valores ou o que é oferecido.
- promocoes: descontos, ofertas e cupons.
- ajuda: dúvidas gerais, como funciona, falar com um atendente.
- outros: qualquer coisa fora das categorias acima.

Responda com a categoria mais provável e sua confiança (0.0 a 1.0)."""

PROMPT_RESPOSTA = """Você é um atendente cordial de um negócio, respondendo no \
WhatsApp em português do Brasil. Seja breve, claro e útil. Não invente preços, \
horários ou políticas que não foram informados."""


class ResultadoIntencao(BaseModel):
    """Saída estruturada da classificação de intenção."""

    intencao: str
    confianca: float = Field(ge=0.0, le=1.0)


class ClassificadorIA(Protocol):
    """Classifica a intenção de uma mensagem."""

    async def classificar(self, texto: str, contexto: str | None = None) -> ResultadoIntencao:
        """Retorna a intenção e a confiança para o texto fornecido."""
        ...


class GeradorRespostaIA(Protocol):
    """Gera uma resposta em linguagem natural."""

    async def gerar(self, intencao: str, texto_cliente: str, contexto: str | None = None) -> str:
        """Retorna o texto de resposta para a mensagem do cliente."""
        ...


class ClassificadorHaiku:
    """Classificador de intenção usando Claude Haiku com saída JSON estrita."""

    def __init__(self, cliente: AsyncAnthropic, modelo: str) -> None:
        self._cliente = cliente
        self._modelo = modelo

    async def classificar(self, texto: str, contexto: str | None = None) -> ResultadoIntencao:
        conteudo = texto if contexto is None else f"{contexto}\n\nMensagem: {texto}"
        resposta = await self._cliente.messages.parse(
            model=self._modelo,
            max_tokens=256,
            system=PROMPT_CLASSIFICACAO,
            messages=[{"role": "user", "content": conteudo}],
            output_format=ResultadoIntencao,
        )
        if resposta.parsed_output is None:
            return ResultadoIntencao(intencao="outros", confianca=0.0)
        return resposta.parsed_output


class GeradorSonnet:
    """Gerador de respostas em linguagem natural usando Claude Sonnet."""

    def __init__(self, cliente: AsyncAnthropic, modelo: str) -> None:
        self._cliente = cliente
        self._modelo = modelo

    async def gerar(self, intencao: str, texto_cliente: str, contexto: str | None = None) -> str:
        partes = [f"Intenção identificada: {intencao}.", f"Mensagem do cliente: {texto_cliente}"]
        if contexto:
            partes.append(f"Contexto: {contexto}")
        resposta = await self._cliente.messages.create(
            model=self._modelo,
            max_tokens=1024,
            system=PROMPT_RESPOSTA,
            messages=[{"role": "user", "content": "\n".join(partes)}],
        )
        for bloco in resposta.content:
            if bloco.type == "text":
                return bloco.text
        return ""
