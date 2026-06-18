"""Construtores de payloads do webhook usados pelos testes."""

from typing import Any

_WA_ID_PADRAO = "5511999999999"


def _envelope(
    wa_id: str, msg_id: str, mensagem: dict[str, Any], nome: str | None
) -> dict[str, Any]:
    perfil = {"name": nome} if nome else {}
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "ENTRY1",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "15550000000",
                                "phone_number_id": "PNID",
                            },
                            "contacts": [{"profile": perfil, "wa_id": wa_id}],
                            "messages": [{"from": wa_id, "id": msg_id, **mensagem}],
                        },
                    }
                ],
            }
        ],
    }


def payload_texto(
    *,
    wa_id: str = _WA_ID_PADRAO,
    msg_id: str = "wamid.AAA",
    texto: str = "Quero agendar um horário",
    nome: str | None = "Cliente Teste",
) -> dict[str, Any]:
    """Payload de uma mensagem de texto."""
    mensagem = {"timestamp": "1700000000", "type": "text", "text": {"body": texto}}
    return _envelope(wa_id, msg_id, mensagem, nome)


def payload_botao(
    *,
    wa_id: str = "5511988887777",
    msg_id: str = "wamid.BBB",
    botao_id: str = "opt_sim",
    titulo: str = "Sim",
    nome: str | None = "Cliente",
) -> dict[str, Any]:
    """Payload de uma resposta de botão interativo (button_reply)."""
    mensagem = {
        "timestamp": "1700000001",
        "type": "interactive",
        "interactive": {"type": "button_reply", "button_reply": {"id": botao_id, "title": titulo}},
    }
    return _envelope(wa_id, msg_id, mensagem, nome)


def payload_lista(
    *,
    reply_id: str,
    wa_id: str = _WA_ID_PADRAO,
    msg_id: str = "wamid.LST",
    titulo: str = "",
    nome: str | None = None,
) -> dict[str, Any]:
    """Payload de uma resposta de item de lista interativa (list_reply)."""
    mensagem = {
        "timestamp": "1700000002",
        "type": "interactive",
        "interactive": {"type": "list_reply", "list_reply": {"id": reply_id, "title": titulo}},
    }
    return _envelope(wa_id, msg_id, mensagem, nome)


def payload_status(
    *,
    recipient_id: str = _WA_ID_PADRAO,
    status_id: str = "wamid.OUT",
    status: str = "delivered",
) -> dict[str, Any]:
    """Payload de um evento de status de entrega (mensagem outbound)."""
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "ENTRY1",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "15550000000",
                                "phone_number_id": "PNID",
                            },
                            "statuses": [
                                {
                                    "id": status_id,
                                    "status": status,
                                    "timestamp": "1700000003",
                                    "recipient_id": recipient_id,
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }
