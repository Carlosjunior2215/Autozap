"""Rotas administrativas, protegidas por API key (header ``X-API-Key``)."""

import hmac
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Configuracoes, obter_configuracoes
from app.core.db import obter_sessao
from app.models import Conversa, Promocao, Template
from app.models.enums import EstadoConversa
from app.schemas.admin import (
    ConversaSaida,
    MetricasSaida,
    MetricaTipo,
    PromocaoAtualizacao,
    PromocaoEntrada,
    PromocaoSaida,
    TemplateAtualizacao,
    TemplateEntrada,
    TemplateSaida,
)
from app.services.admin import esquecer_contato
from app.services.metricas import agregar_metricas
from app.services.tempo import agora_utc


async def verificar_api_key(
    config: Annotated[Configuracoes, Depends(obter_configuracoes)],
    x_api_key: Annotated[str | None, Header()] = None,
) -> None:
    """Valida a API key administrativa (comparação em tempo constante)."""
    if not x_api_key or not hmac.compare_digest(x_api_key, config.admin_api_key):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="API key inválida")


roteador = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(verificar_api_key)])

Sessao = Annotated[AsyncSession, Depends(obter_sessao)]


@roteador.get("/conversas")
async def listar_conversas(sessao: Sessao, limite: int = 50) -> list[ConversaSaida]:
    """Lista as conversas mais recentes."""
    resultado = await sessao.execute(select(Conversa).order_by(Conversa.id.desc()).limit(limite))
    return [ConversaSaida.model_validate(conversa) for conversa in resultado.scalars().all()]


@roteador.get("/metricas")
async def listar_metricas(
    sessao: Sessao,
    desde_horas: Annotated[int | None, Query(ge=1)] = None,
) -> MetricasSaida:
    """Métricas agregadas por tipo (handoffs, rate limits, respostas etc.).

    ``desde_horas`` (opcional) restringe à janela recente; sem ele, considera tudo.
    """
    agora = agora_utc()
    desde = agora - timedelta(hours=desde_horas) if desde_horas else None
    agregados = await agregar_metricas(sessao, desde)
    return MetricasSaida(
        desde=desde,
        ate=agora,
        total=sum(item.quantidade for item in agregados),
        por_tipo=[
            MetricaTipo(tipo=item.tipo, quantidade=item.quantidade, soma=item.soma)
            for item in agregados
        ],
    )


@roteador.post("/conversas/{conversa_id}/liberar")
async def liberar_handoff(conversa_id: int, sessao: Sessao) -> ConversaSaida:
    """Libera o handoff: reativa o bot na conversa."""
    conversa = await sessao.get(Conversa, conversa_id)
    if conversa is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversa não encontrada")
    conversa.em_atendimento_humano = False
    conversa.estado = EstadoConversa.EM_ANDAMENTO
    await sessao.commit()
    await sessao.refresh(conversa)
    return ConversaSaida.model_validate(conversa)


@roteador.get("/templates")
async def listar_templates(sessao: Sessao) -> list[TemplateSaida]:
    """Lista os templates cadastrados."""
    resultado = await sessao.execute(select(Template).order_by(Template.id))
    return [TemplateSaida.model_validate(template) for template in resultado.scalars().all()]


@roteador.post("/templates", status_code=status.HTTP_201_CREATED)
async def criar_template(dados: TemplateEntrada, sessao: Sessao) -> TemplateSaida:
    """Cria um novo template."""
    template = Template(**dados.model_dump())
    sessao.add(template)
    await sessao.commit()
    await sessao.refresh(template)
    return TemplateSaida.model_validate(template)


@roteador.patch("/templates/{template_id}")
async def atualizar_template(
    template_id: int, dados: TemplateAtualizacao, sessao: Sessao
) -> TemplateSaida:
    """Atualiza (parcialmente) um template — ex.: ativar/desativar."""
    template = await sessao.get(Template, template_id)
    if template is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template não encontrado")
    for campo, valor in dados.model_dump(exclude_unset=True).items():
        setattr(template, campo, valor)
    await sessao.commit()
    await sessao.refresh(template)
    return TemplateSaida.model_validate(template)


@roteador.get("/promocoes")
async def listar_promocoes(sessao: Sessao) -> list[PromocaoSaida]:
    """Lista as promoções cadastradas."""
    resultado = await sessao.execute(select(Promocao).order_by(Promocao.id))
    return [PromocaoSaida.model_validate(promocao) for promocao in resultado.scalars().all()]


@roteador.post("/promocoes", status_code=status.HTTP_201_CREATED)
async def criar_promocao(dados: PromocaoEntrada, sessao: Sessao) -> PromocaoSaida:
    """Cria uma nova promoção."""
    promocao = Promocao(**dados.model_dump())
    sessao.add(promocao)
    await sessao.commit()
    await sessao.refresh(promocao)
    return PromocaoSaida.model_validate(promocao)


@roteador.patch("/promocoes/{promocao_id}")
async def atualizar_promocao(
    promocao_id: int, dados: PromocaoAtualizacao, sessao: Sessao
) -> PromocaoSaida:
    """Atualiza (parcialmente) uma promoção — ex.: ativar/desativar."""
    promocao = await sessao.get(Promocao, promocao_id)
    if promocao is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Promoção não encontrada")
    for campo, valor in dados.model_dump(exclude_unset=True).items():
        setattr(promocao, campo, valor)
    await sessao.commit()
    await sessao.refresh(promocao)
    return PromocaoSaida.model_validate(promocao)


@roteador.delete("/contatos/{contato_id}", status_code=status.HTTP_204_NO_CONTENT)
async def apagar_contato(contato_id: int, sessao: Sessao) -> Response:
    """Direito ao esquecimento: apaga o contato e todos os seus dados."""
    apagado = await esquecer_contato(sessao, contato_id)
    if not apagado:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contato não encontrado")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
