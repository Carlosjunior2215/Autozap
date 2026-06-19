"""Ingestão de mensagens do webhook: normalização, deduplicação e persistência."""

import re
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import Contato, Conversa, Mensagem
from app.models.enums import EstadoConversa, OrigemMensagem, StatusMensagem, TipoMensagem
from app.schemas.webhook import MensagemEntrada, StatusEntrada, WebhookPayload


def _so_digitos(valor: str | None) -> str:
    """Reduz um número a apenas dígitos, para comparar telefones de forma robusta."""
    return re.sub(r"\D", "", valor or "")


_MAPA_TIPOS: dict[str, TipoMensagem] = {
    "image": TipoMensagem.IMAGEM,
    "audio": TipoMensagem.AUDIO,
    "video": TipoMensagem.VIDEO,
    "document": TipoMensagem.DOCUMENTO,
    "location": TipoMensagem.LOCALIZACAO,
}


def normalizar(msg: MensagemEntrada) -> tuple[TipoMensagem, str | None, str | None]:
    """Converte uma mensagem da Cloud API em ``(tipo, texto, payload_interativo)``."""
    if msg.type == "text" and msg.text is not None:
        return TipoMensagem.TEXTO, msg.text.body, None
    if msg.type == "interactive" and msg.interactive is not None:
        if msg.interactive.button_reply is not None:
            botao = msg.interactive.button_reply
            return TipoMensagem.INTERATIVO, botao.title, botao.id
        if msg.interactive.list_reply is not None:
            item = msg.interactive.list_reply
            return TipoMensagem.INTERATIVO, item.title, item.id
        return TipoMensagem.INTERATIVO, None, None
    return _MAPA_TIPOS.get(msg.type, TipoMensagem.OUTRO), None, None


async def _mensagem_ja_existe(sessao: AsyncSession, wa_message_id: str) -> bool:
    """Indica se uma mensagem com esse id da Cloud API já foi persistida."""
    resultado = await sessao.execute(
        select(Mensagem.id).where(Mensagem.wa_message_id == wa_message_id)
    )
    return resultado.scalar_one_or_none() is not None


async def _obter_ou_criar_contato(sessao: AsyncSession, telefone: str, nome: str | None) -> Contato:
    """Busca o contato pelo telefone ou cria um novo."""
    resultado = await sessao.execute(select(Contato).where(Contato.telefone == telefone))
    contato = resultado.scalar_one_or_none()
    if contato is None:
        contato = Contato(telefone=telefone, nome=nome)
        sessao.add(contato)
        await sessao.flush()
    elif nome and not contato.nome:
        contato.nome = nome
    return contato


async def _conversa_ativa_do_contato(sessao: AsyncSession, contato_id: int) -> Conversa | None:
    """Retorna a conversa ativa (não encerrada) mais recente do contato, se houver."""
    resultado = await sessao.execute(
        select(Conversa)
        .where(
            Conversa.contato_id == contato_id,
            Conversa.estado != EstadoConversa.ENCERRADA,
        )
        .order_by(Conversa.id.desc())
        .limit(1)
    )
    return resultado.scalar_one_or_none()


async def _obter_ou_criar_conversa(sessao: AsyncSession, contato_id: int) -> Conversa:
    """Retorna a conversa ativa do contato ou cria uma nova."""
    conversa = await _conversa_ativa_do_contato(sessao, contato_id)
    if conversa is None:
        conversa = Conversa(contato_id=contato_id)
        sessao.add(conversa)
        await sessao.flush()
    return conversa


async def _marcar_resposta_humana(
    sessao: AsyncSession, status: StatusEntrada, agora: datetime
) -> None:
    """Detecta resposta do atendente (status outbound) e pausa a automação (#20).

    Eventos ``statuses`` (entrega) chegam para *toda* mensagem outbound. Os do
    próprio bot têm ``id`` (wamid) já persistido em ``mensagens``; os enviados
    manualmente pelo atendente (pelo app) não — esses indicam resposta humana.
    Marcar ``ultima_msg_origem=HUMANO`` faz a reavaliação de "não respondida" (#2)
    deixar de considerar a conversa elegível, evitando auto-resposta sobreposta.
    """
    if not status.recipient_id:
        return
    # Status de uma mensagem nossa (bot): não é resposta humana.
    if status.id and await _mensagem_ja_existe(sessao, status.id):
        return
    resultado = await sessao.execute(select(Contato).where(Contato.telefone == status.recipient_id))
    contato = resultado.scalar_one_or_none()
    if contato is None:
        return
    conversa = await _conversa_ativa_do_contato(sessao, contato.id)
    if conversa is None:
        return
    conversa.ultima_msg_em = agora
    conversa.ultima_msg_origem = OrigemMensagem.HUMANO


async def ingerir_payload(sessao: AsyncSession, payload: WebhookPayload) -> list[int]:
    """Persiste as mensagens novas do payload e retorna os ids das criadas.

    Deduplica por ``wa_message_id``: mensagens já conhecidas são ignoradas.
    """
    ids_novos: list[int] = []
    for entrada in payload.entry:
        for mudanca in entrada.changes:
            valor = mudanca.value
            # Número do próprio negócio (vem na metadata do payload, já autenticado).
            numero_negocio = _so_digitos(
                valor.metadata.display_phone_number if valor.metadata else None
            )
            nomes: dict[str, str | None] = {
                contato.wa_id: (contato.profile.name if contato.profile else None)
                for contato in valor.contacts
            }
            for msg in valor.messages:
                if not msg.id or not msg.remetente:
                    continue
                # Anti-loop: ignora eco de mensagens do próprio número de negócio.
                if numero_negocio and _so_digitos(msg.remetente) == numero_negocio:
                    continue
                if await _mensagem_ja_existe(sessao, msg.id):
                    continue
                tipo, texto, payload_interativo = normalizar(msg)
                contato = await _obter_ou_criar_contato(
                    sessao, msg.remetente, nomes.get(msg.remetente)
                )
                conversa = await _obter_ou_criar_conversa(sessao, contato.id)
                nova = Mensagem(
                    conversa_id=conversa.id,
                    wa_message_id=msg.id,
                    origem=OrigemMensagem.CLIENTE,
                    texto=texto,
                    tipo=tipo,
                    status=StatusMensagem.RECEBIDA,
                    payload_interativo=payload_interativo,
                )
                sessao.add(nova)
                await sessao.flush()
                agora = datetime.now(UTC)
                conversa.ultima_msg_em = agora
                conversa.ultima_msg_cliente_em = agora
                conversa.ultima_msg_origem = OrigemMensagem.CLIENTE
                if conversa.estado == EstadoConversa.NOVA:
                    conversa.estado = EstadoConversa.EM_ANDAMENTO
                ids_novos.append(nova.id)
            # Statuses outbound: detectam resposta do atendente para pausar o bot (#20).
            for status in valor.statuses:
                await _marcar_resposta_humana(sessao, status, datetime.now(UTC))
    await sessao.commit()
    return ids_novos


async def ingerir_e_enfileirar(
    payload_bruto: dict[str, Any],
    sessionmaker: async_sessionmaker[AsyncSession],
    enfileirar: Callable[[int, int], None],
    atraso_seg: int,
) -> list[int]:
    """Valida o payload bruto, persiste as mensagens novas e as enfileira.

    Orquestração executada de forma durável pela tarefa Celery de ingestão (#21):
    o payload bruto recebido no webhook é validado aqui, persistido e cada
    mensagem nova é enfileirada para processamento (com ``atraso_seg`` de
    reavaliação de "não respondida"). Retorna os ids enfileirados.
    """
    payload = WebhookPayload.model_validate(payload_bruto)
    async with sessionmaker() as sessao:
        ids = await ingerir_payload(sessao, payload)
    for mensagem_id in ids:
        enfileirar(mensagem_id, atraso_seg)
    return ids
