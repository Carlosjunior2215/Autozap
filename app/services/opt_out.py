"""Detecção de pedido de opt-out (encerramento de automações)."""

_PALAVRAS_OPT_OUT = frozenset({"pare", "parar", "sair", "stop", "cancelar"})


def eh_pedido_opt_out(texto: str | None) -> bool:
    """Indica se a mensagem é um pedido de opt-out (ex.: 'pare', 'sair')."""
    if not texto:
        return False
    return texto.strip().lower() in _PALAVRAS_OPT_OUT
