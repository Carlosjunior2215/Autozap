"""Orquestração do processamento de uma mensagem recebida (executada no worker).

Recebe todas as dependências externas via :class:`Dependencias`, o que permite
injetar dublês nos testes (sem rede, sem Redis, sem Celery).
"""

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Configuracoes
from app.integrations.ia import ClassificadorIA, GeradorRespostaIA
from app.integrations.whatsapp import WhatsAppClient
from app.models import Contato, Conversa, EventoMetrica, Intencao, Mensagem
from app.models.enums import EstadoConversa, OrigemMensagem, StatusMensagem, TipoMensagem
from app.services.classificador import classificar_intencao
from app.services.deteccao import mensagem_nao_respondida
from app.services.janela_24h import dentro_da_janela_24h
from app.services.opt_out import eh_pedido_opt_out
from app.services.rate_limit import RateLimiter
from app.services.respostas import RespostaBotoes, montar_resposta
from app.services.tempo import agora_utc


@dataclass
class Dependencias:
    """Dependências externas necessárias para processar uma mensagem."""

    sessionmaker: async_sessionmaker[AsyncSession]
    whatsapp: WhatsAppClient
    classificador_ia: ClassificadorIA
    gerador_ia: GeradorRespostaIA
    rate_limiter: RateLimiter
    config: Configuracoes


@dataclass(frozen=True)
class ResultadoProcessamento:
    """Resultado de uma execução de :func:`processar` (útil para logs/testes)."""

    acao: str
    motivo: str | None = None
    intencao: str | None = None
    confianca: float | None = None


def _registrar_metrica(sessao: AsyncSession, tipo: str, conversa_id: int) -> None:
    sessao.add(EventoMetrica(tipo=tipo, conversa_id=conversa_id))


async def processar(mensagem_id: int, deps: Dependencias) -> ResultadoProcessamento:
    """Processa uma mensagem recebida do cliente, aplicando todas as regras."""
    async with deps.sessionmaker() as sessao:
        return await _processar(mensagem_id, deps, sessao)


async def _processar(
    mensagem_id: int, deps: Dependencias, sessao: AsyncSession
) -> ResultadoProcessamento:
    mensagem = await sessao.get(Mensagem, mensagem_id)
    if mensagem is None:
        return ResultadoProcessamento(acao="ignorada", motivo="mensagem inexistente")

    # Anti-loop: o bot nunca responde a si mesmo nem a mensagens não-cliente.
    if mensagem.origem != OrigemMensagem.CLIENTE:
        return ResultadoProcessamento(acao="ignorada", motivo="origem nao cliente")

    conversa = await sessao.get(Conversa, mensagem.conversa_id)
    if conversa is None:
        return ResultadoProcessamento(acao="ignorada", motivo="conversa inexistente")
    contato = await sessao.get(Contato, conversa.contato_id)
    if contato is None:
        return ResultadoProcessamento(acao="ignorada", motivo="contato inexistente")

    # Opt-out já registrado: nenhuma automação.
    if contato.opt_out:
        return ResultadoProcessamento(acao="ignorada", motivo="contato opt-out")

    # Pedido de opt-out nesta mensagem.
    if eh_pedido_opt_out(mensagem.texto):
        contato.opt_out = True
        mensagem.respondida = True
        _registrar_metrica(sessao, "opt_out", conversa.id)
        await sessao.commit()
        return ResultadoProcessamento(acao="opt_out")

    agora = agora_utc()
    if not mensagem_nao_respondida(conversa, agora, deps.config.minutos_sem_resposta):
        return ResultadoProcessamento(acao="ignorada", motivo="nao elegivel")

    resultado = await classificar_intencao(
        mensagem.texto or "", deps.classificador_ia, deps.config.modelo_classificacao
    )
    sessao.add(
        Intencao(
            mensagem_id=mensagem.id,
            label=resultado.intencao.value,
            confianca=resultado.confianca,
            modelo=resultado.modelo,
        )
    )
    conversa.intencao_atual = resultado.intencao.value

    # Confiança baixa: escalona para humano e pausa o bot.
    if resultado.confianca < deps.config.limiar_confianca:
        conversa.em_atendimento_humano = True
        conversa.estado = EstadoConversa.AGUARDANDO_HUMANO
        _registrar_metrica(sessao, "handoff", conversa.id)
        await sessao.commit()
        return ResultadoProcessamento(
            acao="handoff",
            intencao=resultado.intencao.value,
            confianca=resultado.confianca,
        )

    # Limite de taxa por contato.
    if not await deps.rate_limiter.pode_responder(contato.id, deps.config.max_respostas_por_hora):
        _registrar_metrica(sessao, "rate_limit_excedido", conversa.id)
        await sessao.commit()
        return ResultadoProcessamento(acao="rate_limited", intencao=resultado.intencao.value)

    dentro = dentro_da_janela_24h(conversa.ultima_msg_cliente_em, agora)
    resposta = await montar_resposta(
        sessao, resultado.intencao, dentro, deps.gerador_ia, mensagem.texto or ""
    )
    if resposta is None:
        _registrar_metrica(sessao, "sem_resposta_fora_janela", conversa.id)
        await sessao.commit()
        return ResultadoProcessamento(acao="sem_resposta", intencao=resultado.intencao.value)

    if isinstance(resposta, RespostaBotoes):
        wa_id = await deps.whatsapp.enviar_botoes(
            contato.telefone, resposta.corpo, list(resposta.botoes)
        )
        texto_registrado = resposta.corpo
        tipo = TipoMensagem.INTERATIVO
    else:
        wa_id = await deps.whatsapp.enviar_texto(contato.telefone, resposta.conteudo)
        texto_registrado = resposta.conteudo
        tipo = TipoMensagem.TEXTO

    sessao.add(
        Mensagem(
            conversa_id=conversa.id,
            wa_message_id=wa_id or None,
            origem=OrigemMensagem.BOT,
            texto=texto_registrado,
            tipo=tipo,
            status=StatusMensagem.ENVIADA,
        )
    )
    mensagem.respondida = True
    conversa.ultima_msg_em = agora
    conversa.ultima_msg_origem = OrigemMensagem.BOT
    if conversa.estado == EstadoConversa.NOVA:
        conversa.estado = EstadoConversa.EM_ANDAMENTO
    _registrar_metrica(sessao, "resposta_enviada", conversa.id)
    await sessao.commit()
    return ResultadoProcessamento(acao="respondida", intencao=resultado.intencao.value)
