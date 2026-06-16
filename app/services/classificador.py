"""Classificação de intenção híbrida: regras (keywords) com fallback para LLM."""

from dataclasses import dataclass

from app.integrations.ia import ClassificadorIA
from app.models.enums import CategoriaIntencao

# Ordem importa: a primeira categoria cujas palavras casarem é escolhida.
_KEYWORDS: dict[CategoriaIntencao, tuple[str, ...]] = {
    CategoriaIntencao.AGENDAMENTO: (
        "agendar",
        "agenda",
        "horario",
        "horário",
        "marcar",
        "remarcar",
        "marcacao",
        "marcação",
    ),
    CategoriaIntencao.SERVICOS: (
        "preço",
        "preco",
        "valor",
        "quanto custa",
        "quanto e",
        "quanto é",
        "serviço",
        "servico",
        "serviços",
        "servicos",
    ),
    CategoriaIntencao.PROMOCOES: (
        "promoção",
        "promocao",
        "promoções",
        "promocoes",
        "desconto",
        "oferta",
        "cupom",
    ),
    CategoriaIntencao.AJUDA: (
        "ajuda",
        "ajudar",
        "dúvida",
        "duvida",
        "como funciona",
        "atendente",
        "suporte",
    ),
}


@dataclass(frozen=True)
class ResultadoClassificacao:
    """Resultado consolidado da classificação (regras ou LLM)."""

    intencao: CategoriaIntencao
    confianca: float
    modelo: str


def classificar_por_regras(texto: str) -> CategoriaIntencao | None:
    """Classifica por palavras-chave; retorna ``None`` quando indeciso."""
    normalizado = texto.strip().lower()
    if not normalizado:
        return None
    for categoria, palavras in _KEYWORDS.items():
        if any(palavra in normalizado for palavra in palavras):
            return categoria
    return None


async def classificar_intencao(
    texto: str, classificador_ia: ClassificadorIA, modelo_ia: str
) -> ResultadoClassificacao:
    """Classifica via regras; se indeciso, recorre ao LLM (confiança do modelo)."""
    por_regras = classificar_por_regras(texto)
    if por_regras is not None:
        return ResultadoClassificacao(intencao=por_regras, confianca=1.0, modelo="regras")
    bruto = await classificador_ia.classificar(texto)
    categoria = CategoriaIntencao.de_texto(bruto.intencao)
    return ResultadoClassificacao(intencao=categoria, confianca=bruto.confianca, modelo=modelo_ia)
