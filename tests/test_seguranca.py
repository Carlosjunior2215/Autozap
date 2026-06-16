"""Testes da verificação de assinatura e do token do webhook."""

from app.core.seguranca import (
    gerar_assinatura,
    verificar_assinatura,
    verificar_token_webhook,
)


def test_assinatura_valida() -> None:
    corpo = b'{"ok": true}'
    segredo = "segredo"
    assinatura = gerar_assinatura(corpo, segredo)
    assert verificar_assinatura(corpo, assinatura, segredo)


def test_assinatura_invalida() -> None:
    assert not verificar_assinatura(b"corpo", "sha256=deadbeef", "segredo")


def test_assinatura_ausente() -> None:
    assert not verificar_assinatura(b"corpo", None, "segredo")


def test_assinatura_sem_prefixo() -> None:
    corpo = b"corpo"
    digest_sem_prefixo = gerar_assinatura(corpo, "segredo").removeprefix("sha256=")
    assert not verificar_assinatura(corpo, digest_sem_prefixo, "segredo")


def test_assinatura_segredo_errado() -> None:
    corpo = b"corpo"
    assinatura = gerar_assinatura(corpo, "segredo-certo")
    assert not verificar_assinatura(corpo, assinatura, "segredo-errado")


def test_token_webhook_valido() -> None:
    assert verificar_token_webhook("subscribe", "tok", "tok")


def test_token_webhook_invalido() -> None:
    assert not verificar_token_webhook("subscribe", "errado", "tok")
    assert not verificar_token_webhook(None, "tok", "tok")
    assert not verificar_token_webhook("unsubscribe", "tok", "tok")
