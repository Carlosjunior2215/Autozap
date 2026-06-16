"""Máquina de estados do fluxo de agendamento (multi-turno, via interativo).

O estado do fluxo é persistido em ``conversa.dados_fluxo`` (JSON). As transições
sempre reatribuem o dicionário (em vez de mutá-lo) para que o SQLAlchemy detecte
a alteração.
"""

from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Configuracoes
from app.integrations.whatsapp import OpcaoInterativa
from app.models import Agendamento, Contato, Conversa
from app.models.enums import EstadoConversa, StatusAgendamento
from app.services.agenda import formatar_horario, gerar_slots, listar_servicos
from app.services.respostas import (
    RespostaBotoes,
    RespostaLista,
    RespostaPlanejada,
    RespostaTexto,
)
from app.services.tempo import agora_utc

_PREFIXO_SERVICO = "servico:"
_PREFIXO_HORARIO = "horario:"
_CONFIRMAR_SIM = "confirmar:sim"
_CONFIRMAR_NAO = "confirmar:nao"


def _entrada(payload_interativo: str | None, texto: str | None) -> str:
    """Entrada efetiva do cliente: prioriza o payload interativo, senão o texto."""
    if payload_interativo:
        return payload_interativo.strip()
    return (texto or "").strip()


def _oferta_servicos(config: Configuracoes, corpo: str) -> RespostaLista:
    opcoes = tuple(
        OpcaoInterativa(id=f"{_PREFIXO_SERVICO}{servico}", titulo=servico[:24])
        for servico in listar_servicos(config)
    )
    return RespostaLista(corpo=corpo, titulo_botao="Serviços", opcoes=opcoes)


def _oferta_horarios(slots: list[datetime], config: Configuracoes, corpo: str) -> RespostaLista:
    opcoes = tuple(
        OpcaoInterativa(
            id=f"{_PREFIXO_HORARIO}{slot.isoformat()}", titulo=formatar_horario(slot, config)
        )
        for slot in slots
    )
    return RespostaLista(corpo=corpo, titulo_botao="Horários", opcoes=opcoes)


def _confirmacao(dados: dict[str, Any], config: Configuracoes) -> RespostaBotoes:
    data_hora = datetime.fromisoformat(str(dados["data_hora"]))
    corpo = f"Confirmar {dados.get('servico', '')} em {formatar_horario(data_hora, config)}?"
    botoes = (
        OpcaoInterativa(id=_CONFIRMAR_SIM, titulo="Confirmar"),
        OpcaoInterativa(id=_CONFIRMAR_NAO, titulo="Cancelar"),
    )
    return RespostaBotoes(corpo=corpo, botoes=botoes)


def _resolver_servico(entrada: str, config: Configuracoes) -> str | None:
    servicos = listar_servicos(config)
    if entrada.startswith(_PREFIXO_SERVICO):
        candidato = entrada[len(_PREFIXO_SERVICO) :]
        return candidato if candidato in servicos else None
    for servico in servicos:
        if servico.lower() == entrada.lower():
            return servico
    return None


def _resolver_horario(entrada: str, slots_iso: list[str]) -> str | None:
    if entrada.startswith(_PREFIXO_HORARIO):
        candidato = entrada[len(_PREFIXO_HORARIO) :]
        return candidato if candidato in slots_iso else None
    return None


def _eh_confirmacao_positiva(entrada: str) -> bool:
    normal = entrada.lower()
    if normal == _CONFIRMAR_NAO:
        return False
    return normal == _CONFIRMAR_SIM or normal in {"sim", "s", "confirmar", "ok", "isso"}


def _encerrar_fluxo(conversa: Conversa) -> None:
    conversa.dados_fluxo = None
    conversa.estado = EstadoConversa.EM_ANDAMENTO


def iniciar_agendamento(conversa: Conversa, config: Configuracoes) -> RespostaPlanejada:
    """Entra no fluxo de agendamento e oferece os serviços disponíveis."""
    conversa.estado = EstadoConversa.AGENDAMENTO
    conversa.dados_fluxo = {"fluxo": "agendamento", "etapa": "escolher_servico"}
    return _oferta_servicos(config, "Vamos agendar! Qual serviço você deseja?")


async def avancar_agendamento(
    sessao: AsyncSession,
    conversa: Conversa,
    contato: Contato,
    payload_interativo: str | None,
    texto: str | None,
    config: Configuracoes,
) -> RespostaPlanejada:
    """Avança o fluxo conforme a etapa atual e a entrada do cliente."""
    dados: dict[str, Any] = dict(conversa.dados_fluxo or {})
    etapa = dados.get("etapa")
    entrada = _entrada(payload_interativo, texto)

    if etapa == "escolher_servico":
        servico = _resolver_servico(entrada, config)
        if servico is None:
            return _oferta_servicos(config, "Não entendi. Escolha um serviço da lista:")
        slots = await gerar_slots(sessao, config, agora_utc())
        if not slots:
            _encerrar_fluxo(conversa)
            return RespostaTexto(
                conteudo="No momento não há horários disponíveis. Tente mais tarde.",
                origem_conteudo="fixo",
            )
        dados.update(
            servico=servico, etapa="escolher_horario", slots=[s.isoformat() for s in slots]
        )
        conversa.dados_fluxo = dados
        return _oferta_horarios(slots, config, f"Serviço: {servico}. Escolha um horário:")

    if etapa == "escolher_horario":
        slots_iso: list[str] = list(dados.get("slots", []))
        escolhido = _resolver_horario(entrada, slots_iso)
        if escolhido is None:
            slots = [datetime.fromisoformat(s) for s in slots_iso]
            return _oferta_horarios(slots, config, "Não entendi. Escolha um horário da lista:")
        dados["data_hora"] = escolhido
        if contato.nome:
            dados.update(nome=contato.nome, etapa="confirmar")
            conversa.dados_fluxo = dados
            return _confirmacao(dados, config)
        dados["etapa"] = "coletar_nome"
        conversa.dados_fluxo = dados
        return RespostaTexto(conteudo="Qual nome para a reserva?", origem_conteudo="fixo")

    if etapa == "coletar_nome":
        nome = (texto or "").strip()
        if not nome:
            return RespostaTexto(conteudo="Por favor, informe um nome.", origem_conteudo="fixo")
        if not contato.nome:
            contato.nome = nome
        dados.update(nome=nome, etapa="confirmar")
        conversa.dados_fluxo = dados
        return _confirmacao(dados, config)

    if etapa == "confirmar":
        if _eh_confirmacao_positiva(entrada):
            data_hora = datetime.fromisoformat(str(dados["data_hora"]))
            sessao.add(
                Agendamento(
                    contato_id=contato.id,
                    servico=str(dados.get("servico", "")),
                    data_hora=data_hora,
                    status=StatusAgendamento.CONFIRMADO,
                )
            )
            _encerrar_fluxo(conversa)
            return RespostaTexto(
                conteudo=(
                    f"Pronto, {dados.get('nome', '')}! Seu {dados.get('servico', '')} está "
                    f"confirmado para {formatar_horario(data_hora, config)}."
                ),
                origem_conteudo="fixo",
            )
        _encerrar_fluxo(conversa)
        return RespostaTexto(conteudo="Tudo bem, cancelei o agendamento.", origem_conteudo="fixo")

    # Etapa desconhecida: reinicia o fluxo.
    return iniciar_agendamento(conversa, config)
