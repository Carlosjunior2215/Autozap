"""Orquestração do processamento de uma mensagem recebida (executada no worker).

Recebe todas as dependências externas via :class:`Dependencias`, o que permite
injetar dublês nos testes (sem rede, sem Redis, sem Celery).
"""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Configuracoes
from app.integrations.ia import ClassificadorIA, ErroIA, GeradorRespostaIA
from app.integrations.whatsapp import WhatsAppClient
from app.models import Contato, Conversa, EventoMetrica, Intencao, Mensagem
from app.models.enums import (
    CategoriaIntencao,
    EstadoConversa,
    OrigemMensagem,
    StatusMensagem,
    TipoMensagem,
)
from app.services.agendamento import avancar_agendamento, iniciar_agendamento
from app.services.classificador import classificar_intencao
from app.services.deteccao import mensagem_nao_respondida
from app.services.janela_24h import dentro_da_janela_24h
from app.services.opt_out import eh_pedido_opt_out
from app.services.rate_limit import RateLimiter
from app.services.respostas import (
    RespostaBotoes,
    RespostaLista,
    RespostaPlanejada,
    RespostaTemplate,
    montar_resposta,
)
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


def _escalar_humano(sessao: AsyncSession, conversa: Conversa, evento: str) -> None:
    """Pausa o bot na conversa e a coloca na fila de atendimento humano."""
    conversa.em_atendimento_humano = True
    conversa.estado = EstadoConversa.AGUARDANDO_HUMANO
    _registrar_metrica(sessao, evento, conversa.id)


async def _enviar_resposta(
    sessao: AsyncSession,
    conversa: Conversa,
    contato: Contato,
    mensagem: Mensagem,
    resposta: RespostaPlanejada,
    whatsapp: WhatsAppClient,
    agora: datetime,
) -> None:
    """Registra a resposta como pendente, persiste, envia e confirma.

    A ordem importa para a idempotência: a mensagem do bot é gravada como
    ``PENDENTE`` e o commit é feito *antes* do envio externo. Assim, se o envio
    (ou o commit final) falhar, um reprocessamento verá a mensagem do cliente já
    como ``respondida`` e não reenviará — evitando resposta duplicada.
    """
    # Conteúdo a registrar: interativos usam 'corpo'; texto/template usam 'conteudo'.
    if isinstance(resposta, RespostaBotoes | RespostaLista):
        texto_registrado, tipo = resposta.corpo, TipoMensagem.INTERATIVO
    else:
        texto_registrado, tipo = resposta.conteudo, TipoMensagem.TEXTO

    msg_bot = Mensagem(
        conversa_id=conversa.id,
        origem=OrigemMensagem.BOT,
        texto=texto_registrado,
        tipo=tipo,
        status=StatusMensagem.PENDENTE,
    )
    sessao.add(msg_bot)
    mensagem.respondida = True
    conversa.ultima_msg_em = agora
    conversa.ultima_msg_origem = OrigemMensagem.BOT
    # Persiste a intenção de resposta antes do envio externo (idempotência).
    await sessao.commit()

    if isinstance(resposta, RespostaBotoes):
        wa_id = await whatsapp.enviar_botoes(
            contato.telefone, resposta.corpo, list(resposta.botoes)
        )
    elif isinstance(resposta, RespostaLista):
        wa_id = await whatsapp.enviar_lista(
            contato.telefone, resposta.corpo, resposta.titulo_botao, list(resposta.opcoes)
        )
    elif isinstance(resposta, RespostaTemplate):
        wa_id = await whatsapp.enviar_template(
            contato.telefone,
            resposta.nome_meta,
            resposta.idioma,
            list(resposta.parametros) or None,
        )
    else:
        wa_id = await whatsapp.enviar_texto(contato.telefone, resposta.conteudo)

    msg_bot.status = StatusMensagem.ENVIADA
    msg_bot.wa_message_id = wa_id or None


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

    # Idempotência: se esta mensagem já foi respondida, não reprocessa (evita
    # reenvio em um retry, mesmo que a conversa tenha recebido mensagens depois).
    if mensagem.respondida:
        return ResultadoProcessamento(acao="ignorada", motivo="ja respondida")

    conversa = await sessao.get(Conversa, mensagem.conversa_id)
    if conversa is None:
        return ResultadoProcessamento(acao="ignorada", motivo="conversa inexistente")
    contato = await sessao.get(Contato, conversa.contato_id)
    if contato is None:
        return ResultadoProcessamento(acao="ignorada", motivo="contato inexistente")

    if contato.opt_out:
        return ResultadoProcessamento(acao="ignorada", motivo="contato opt-out")

    if eh_pedido_opt_out(mensagem.texto):
        contato.opt_out = True
        mensagem.respondida = True
        _registrar_metrica(sessao, "opt_out", conversa.id)
        await sessao.commit()
        return ResultadoProcessamento(acao="opt_out")

    agora = agora_utc()
    if not mensagem_nao_respondida(conversa, agora, deps.config.minutos_sem_resposta):
        return ResultadoProcessamento(acao="ignorada", motivo="nao elegivel")

    # Fluxo de agendamento em andamento: continua sem reclassificar.
    if conversa.estado == EstadoConversa.AGENDAMENTO and conversa.dados_fluxo:
        if not await deps.rate_limiter.pode_responder(
            contato.id, deps.config.max_respostas_por_hora
        ):
            _registrar_metrica(sessao, "rate_limit_excedido", conversa.id)
            await sessao.commit()
            return ResultadoProcessamento(acao="rate_limited", intencao="agendamento")
        resposta = await avancar_agendamento(
            sessao, conversa, contato, mensagem.payload_interativo, mensagem.texto, deps.config
        )
        await _enviar_resposta(sessao, conversa, contato, mensagem, resposta, deps.whatsapp, agora)
        _registrar_metrica(sessao, "agendamento_passo", conversa.id)
        await sessao.commit()
        return ResultadoProcessamento(acao="respondida", intencao="agendamento")

    try:
        resultado = await classificar_intencao(
            mensagem.texto or "", deps.classificador_ia, deps.config.modelo_classificacao
        )
    except ErroIA:
        # Provedor de IA indisponível: não arrisca resposta automática, escala.
        _escalar_humano(sessao, conversa, "erro_ia_classificacao")
        await sessao.commit()
        return ResultadoProcessamento(acao="handoff", motivo="erro_ia")

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
        _escalar_humano(sessao, conversa, "handoff")
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

    # Intenção de agendamento: inicia o fluxo multi-turno.
    if resultado.intencao == CategoriaIntencao.AGENDAMENTO:
        inicio = iniciar_agendamento(conversa, deps.config)
        await _enviar_resposta(sessao, conversa, contato, mensagem, inicio, deps.whatsapp, agora)
        _registrar_metrica(sessao, "agendamento_iniciado", conversa.id)
        await sessao.commit()
        return ResultadoProcessamento(acao="respondida", intencao=resultado.intencao.value)

    # Demais intenções: template, geração por IA ou botões (ajuda).
    dentro = dentro_da_janela_24h(conversa.ultima_msg_cliente_em, agora)
    try:
        resposta_normal = await montar_resposta(
            sessao, resultado.intencao, dentro, deps.gerador_ia, mensagem.texto or ""
        )
    except ErroIA:
        _escalar_humano(sessao, conversa, "erro_ia_geracao")
        await sessao.commit()
        return ResultadoProcessamento(
            acao="handoff", intencao=resultado.intencao.value, motivo="erro_ia"
        )
    if resposta_normal is None:
        _registrar_metrica(sessao, "sem_resposta_fora_janela", conversa.id)
        await sessao.commit()
        return ResultadoProcessamento(acao="sem_resposta", intencao=resultado.intencao.value)

    await _enviar_resposta(
        sessao, conversa, contato, mensagem, resposta_normal, deps.whatsapp, agora
    )
    if conversa.estado == EstadoConversa.NOVA:
        conversa.estado = EstadoConversa.EM_ANDAMENTO
    _registrar_metrica(sessao, "resposta_enviada", conversa.id)
    await sessao.commit()
    return ResultadoProcessamento(acao="respondida", intencao=resultado.intencao.value)
