"""Cliente WhatsApp falso para testes (registra os envios, sem rede)."""

from dataclasses import dataclass, field
from typing import Any

from app.integrations.whatsapp import OpcaoInterativa


@dataclass
class EnvioRegistrado:
    """Registro de um envio efetuado pelo cliente falso."""

    metodo: str
    destino: str
    conteudo: str
    extra: dict[str, Any] = field(default_factory=dict)


class FakeWhatsAppClient:
    """Implementação de :class:`WhatsAppClient` que apenas registra os envios.

    Defina ``erro`` para simular uma falha de envio (todas as chamadas a levantam),
    útil para exercitar o escalonamento por falha de envio.
    """

    def __init__(self) -> None:
        self.envios: list[EnvioRegistrado] = []
        self.erro: Exception | None = None
        self._contador = 0

    def _proximo_id(self) -> str:
        self._contador += 1
        return f"wamid.FAKE{self._contador}"

    def _verificar_erro(self) -> None:
        if self.erro is not None:
            raise self.erro

    async def enviar_texto(self, destino: str, texto: str) -> str:
        self._verificar_erro()
        self.envios.append(EnvioRegistrado("texto", destino, texto))
        return self._proximo_id()

    async def enviar_template(
        self, destino: str, nome_template: str, idioma: str, parametros: list[str] | None
    ) -> str:
        self._verificar_erro()
        self.envios.append(
            EnvioRegistrado(
                "template",
                destino,
                nome_template,
                {"idioma": idioma, "parametros": parametros},
            )
        )
        return self._proximo_id()

    async def enviar_botoes(self, destino: str, corpo: str, botoes: list[OpcaoInterativa]) -> str:
        self._verificar_erro()
        self.envios.append(EnvioRegistrado("botoes", destino, corpo, {"botoes": botoes}))
        return self._proximo_id()

    async def enviar_lista(
        self,
        destino: str,
        corpo: str,
        titulo_botao: str,
        opcoes: list[OpcaoInterativa],
    ) -> str:
        self._verificar_erro()
        self.envios.append(
            EnvioRegistrado(
                "lista", destino, corpo, {"titulo_botao": titulo_botao, "opcoes": opcoes}
            )
        )
        return self._proximo_id()
