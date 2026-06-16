"""Integração com a WhatsApp Cloud API (Meta).

Toda comunicação de saída passa pela interface :class:`WhatsAppClient`, o que
permite injetar um cliente falso (``FakeWhatsAppClient``) nos testes.
"""

from dataclasses import dataclass
from typing import Any, Protocol

import httpx

from app.core.config import Configuracoes


@dataclass(frozen=True, slots=True)
class OpcaoInterativa:
    """Opção de um botão ou item de lista interativa."""

    id: str
    titulo: str
    descricao: str | None = None


class WhatsAppClient(Protocol):
    """Interface de envio de mensagens via WhatsApp."""

    async def enviar_texto(self, destino: str, texto: str) -> str:
        """Envia uma mensagem de texto livre. Retorna o id da mensagem."""
        ...

    async def enviar_template(
        self, destino: str, nome_template: str, idioma: str, parametros: list[str] | None
    ) -> str:
        """Envia uma mensagem de template aprovado. Retorna o id da mensagem."""
        ...

    async def enviar_botoes(self, destino: str, corpo: str, botoes: list[OpcaoInterativa]) -> str:
        """Envia mensagem interativa com botões de resposta (máx. 3)."""
        ...

    async def enviar_lista(
        self,
        destino: str,
        corpo: str,
        titulo_botao: str,
        opcoes: list[OpcaoInterativa],
    ) -> str:
        """Envia mensagem interativa com lista de opções."""
        ...


class CloudApiWhatsAppClient:
    """Implementação real usando a WhatsApp Cloud API via HTTP (httpx)."""

    def __init__(
        self, config: Configuracoes, cliente_http: httpx.AsyncClient | None = None
    ) -> None:
        self._config = config
        self._http = cliente_http or httpx.AsyncClient(timeout=10.0)

    @property
    def _url(self) -> str:
        base = self._config.whatsapp_api_base_url.rstrip("/")
        return f"{base}/{self._config.whatsapp_phone_number_id}/messages"

    async def _enviar(self, payload: dict[str, Any]) -> str:
        corpo = {"messaging_product": "whatsapp", **payload}
        cabecalhos = {"Authorization": f"Bearer {self._config.whatsapp_access_token}"}
        resposta = await self._http.post(self._url, json=corpo, headers=cabecalhos)
        resposta.raise_for_status()
        dados: Any = resposta.json()
        mensagens = dados.get("messages") if isinstance(dados, dict) else None
        if mensagens:
            return str(mensagens[0].get("id", ""))
        return ""

    async def enviar_texto(self, destino: str, texto: str) -> str:
        return await self._enviar({"to": destino, "type": "text", "text": {"body": texto}})

    async def enviar_template(
        self, destino: str, nome_template: str, idioma: str, parametros: list[str] | None
    ) -> str:
        template: dict[str, Any] = {"name": nome_template, "language": {"code": idioma}}
        if parametros:
            template["components"] = [
                {
                    "type": "body",
                    "parameters": [{"type": "text", "text": p} for p in parametros],
                }
            ]
        return await self._enviar({"to": destino, "type": "template", "template": template})

    async def enviar_botoes(self, destino: str, corpo: str, botoes: list[OpcaoInterativa]) -> str:
        acao = {
            "buttons": [{"type": "reply", "reply": {"id": b.id, "title": b.titulo}} for b in botoes]
        }
        return await self._enviar(
            {
                "to": destino,
                "type": "interactive",
                "interactive": {
                    "type": "button",
                    "body": {"text": corpo},
                    "action": acao,
                },
            }
        )

    async def enviar_lista(
        self,
        destino: str,
        corpo: str,
        titulo_botao: str,
        opcoes: list[OpcaoInterativa],
    ) -> str:
        linhas = [{"id": o.id, "title": o.titulo, "description": o.descricao or ""} for o in opcoes]
        return await self._enviar(
            {
                "to": destino,
                "type": "interactive",
                "interactive": {
                    "type": "list",
                    "body": {"text": corpo},
                    "action": {
                        "button": titulo_botao,
                        "sections": [{"title": corpo[:24], "rows": linhas}],
                    },
                },
            }
        )

    async def fechar(self) -> None:
        """Encerra o cliente HTTP subjacente."""
        await self._http.aclose()
