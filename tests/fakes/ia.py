"""Dublês de IA para testes (sem rede)."""

from app.integrations.ia import ResultadoIntencao


class FakeClassificadorIA:
    """Classificador falso: retorna um resultado configurável e registra chamadas."""

    def __init__(self, resultado: ResultadoIntencao | None = None) -> None:
        self.resultado = resultado or ResultadoIntencao(intencao="outros", confianca=0.9)
        self.chamadas: list[str] = []

    async def classificar(self, texto: str, contexto: str | None = None) -> ResultadoIntencao:
        self.chamadas.append(texto)
        return self.resultado


class FakeGeradorRespostaIA:
    """Gerador falso: retorna um texto fixo e registra as chamadas."""

    def __init__(self, texto: str = "Posso ajudar com isso!") -> None:
        self.texto = texto
        self.chamadas: list[tuple[str, str]] = []

    async def gerar(self, intencao: str, texto_cliente: str, contexto: str | None = None) -> str:
        self.chamadas.append((intencao, texto_cliente))
        return self.texto
