"""Testes das configurações: validação de segredos em produção."""

import pytest
from pydantic import ValidationError

from app.core.config import Configuracoes


def test_desenvolvimento_aceita_defaults() -> None:
    """Fora de produção, os valores de exemplo são aceitos (conveniência local)."""
    cfg = Configuracoes()
    assert cfg.ambiente == "desenvolvimento"


def test_producao_recusa_segredos_placeholder() -> None:
    """Em produção, segredos vazios/de exemplo devem falhar na carga."""
    with pytest.raises(ValidationError):
        Configuracoes(ambiente="producao")


def test_producao_aceita_segredos_reais() -> None:
    """Em produção, segredos preenchidos passam normalmente."""
    cfg = Configuracoes(
        ambiente="producao",
        whatsapp_verify_token="vt",
        whatsapp_app_secret="sec",
        whatsapp_access_token="tok",
        whatsapp_phone_number_id="pnid",
        anthropic_api_key="ak",
        admin_api_key="adm",
    )
    assert cfg.ambiente == "producao"
