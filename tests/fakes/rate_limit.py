"""Rate limiter falso para testes (contagem em memória)."""


class FakeRateLimiter:
    """Conta tentativas por contato; pode ser forçado a negar via ``permitir``."""

    def __init__(self, *, permitir: bool = True) -> None:
        self.permitir = permitir
        self.contagem: dict[int, int] = {}

    async def pode_responder(self, contato_id: int, limite_por_hora: int) -> bool:
        self.contagem[contato_id] = self.contagem.get(contato_id, 0) + 1
        if not self.permitir:
            return False
        return self.contagem[contato_id] <= limite_por_hora
