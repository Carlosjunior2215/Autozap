"""Segurança do webhook: assinatura HMAC e verificação de token."""

import hashlib
import hmac

_PREFIXO_ASSINATURA = "sha256="


def gerar_assinatura(corpo: bytes, app_secret: str) -> str:
    """Gera o valor esperado do header ``X-Hub-Signature-256``."""
    digest = hmac.new(app_secret.encode("utf-8"), corpo, hashlib.sha256).hexdigest()
    return f"{_PREFIXO_ASSINATURA}{digest}"


def verificar_assinatura(corpo: bytes, header_assinatura: str | None, app_secret: str) -> bool:
    """Valida o ``X-Hub-Signature-256`` (HMAC SHA-256 do corpo bruto da requisição)."""
    if not header_assinatura or not header_assinatura.startswith(_PREFIXO_ASSINATURA):
        return False
    esperado = gerar_assinatura(corpo, app_secret)
    return hmac.compare_digest(esperado, header_assinatura)


def verificar_token_webhook(modo: str | None, token: str | None, verify_token: str) -> bool:
    """Valida os parâmetros de verificação (GET) enviados pela Meta."""
    return modo == "subscribe" and token == verify_token
