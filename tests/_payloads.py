"""Construtores de payloads do webhook usados pelos testes."""

from typing import Any


def payload_texto(
    *,
    wa_id: str = "5511999999999",
    msg_id: str = "wamid.AAA",
    texto: str = "Quero agendar um horário",
    nome: str = "Cliente Teste",
) -> dict[str, Any]:
    """Payload de uma mensagem de texto."""
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
                            "contacts": [{"profile": {"name": nome}, "wa_id": wa_id}],
                            "messages": [
                                {
                                    "from": wa_id,
                                    "id": msg_id,
                                    "timestamp": "1700000000",
                                    "type": "text",
                                    "text": {"body": texto},
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }


def payload_botao(
    *,
    wa_id: str = "5511988887777",
    msg_id: str = "wamid.BBB",
    botao_id: str = "opt_sim",
    titulo: str = "Sim",
) -> dict[str, Any]:
    """Payload de uma resposta de botão interativo."""
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
                            "contacts": [{"profile": {"name": "Cliente"}, "wa_id": wa_id}],
                            "messages": [
                                {
                                    "from": wa_id,
                                    "id": msg_id,
                                    "timestamp": "1700000001",
                                    "type": "interactive",
                                    "interactive": {
                                        "type": "button_reply",
                                        "button_reply": {"id": botao_id, "title": titulo},
                                    },
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }
