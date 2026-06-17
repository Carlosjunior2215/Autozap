"""Seleção/geração da resposta automática (template, IA ou interativa)."""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.ia import GeradorRespostaIA
from app.integrations.whatsapp import OpcaoInterativa
from app.models import Template
from app.models.enums import CategoriaIntencao


@dataclass(frozen=True)
class RespostaTexto:
    """Resposta de texto livre (de template ou gerada por IA)."""

    conteudo: str
    origem_conteudo: str


@dataclass(frozen=True)
class RespostaBotoes:
    """Resposta interativa com botões de resposta rápida."""

    corpo: str
    botoes: tuple[OpcaoInterativa, ...]
    origem_conteudo: str = "fixo"


@dataclass(frozen=True)
class RespostaLista:
    """Resposta interativa com lista de opções (seções/itens)."""

    corpo: str
    titulo_botao: str
    opcoes: tuple[OpcaoInterativa, ...]
    origem_conteudo: str = "fixo"


@dataclass(frozen=True)
class RespostaTemplate:
    """Template aprovado pela Meta (único formato permitido fora da janela 24h)."""

    nome_meta: str
    idioma: str
    conteudo: str  # texto equivalente, apenas para registro/auditoria
    parametros: tuple[str, ...] = ()
    origem_conteudo: str = "template"


RespostaPlanejada = RespostaTexto | RespostaBotoes | RespostaLista | RespostaTemplate

_BOTOES_AJUDA: tuple[OpcaoInterativa, ...] = (
    OpcaoInterativa(id="menu_agendamento", titulo="Agendar"),
    OpcaoInterativa(id="menu_servicos", titulo="Serviços"),
    OpcaoInterativa(id="menu_promocoes", titulo="Promoções"),
)


async def _buscar_template(sessao: AsyncSession, assunto: str) -> Template | None:
    """Busca um template ativo para o assunto informado."""
    resultado = await sessao.execute(
        select(Template).where(Template.assunto == assunto, Template.ativo.is_(True)).limit(1)
    )
    return resultado.scalar_one_or_none()


async def montar_resposta(
    sessao: AsyncSession,
    intencao: CategoriaIntencao,
    dentro_janela_24h: bool,
    gerador_ia: GeradorRespostaIA,
    texto_cliente: str,
) -> RespostaPlanejada | None:
    """Decide a resposta a enviar, respeitando a janela de 24h.

    - Fora da janela: apenas template aprovado pela Meta (caso contrário, ``None``).
    - Dentro da janela: 'ajuda' usa botões; senão template ativo; senão geração via IA.
    """
    template = await _buscar_template(sessao, intencao.value)

    if not dentro_janela_24h:
        # Fora da janela, a Cloud API só aceita template aprovado (type:template),
        # referenciado pelo nome registrado na Meta — texto livre é recusado.
        if template is not None and template.aprovado_meta and template.nome_meta:
            return RespostaTemplate(
                nome_meta=template.nome_meta,
                idioma=template.idioma,
                conteudo=template.conteudo,
            )
        return None

    if intencao == CategoriaIntencao.AJUDA:
        corpo = (
            template.conteudo if template is not None else "Como posso ajudar? Escolha uma opção:"
        )
        return RespostaBotoes(corpo=corpo, botoes=_BOTOES_AJUDA)

    if template is not None:
        return RespostaTexto(conteudo=template.conteudo, origem_conteudo="template")

    texto = await gerador_ia.gerar(intencao.value, texto_cliente)
    return RespostaTexto(conteudo=texto, origem_conteudo="ia")
