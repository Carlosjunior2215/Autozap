"""Detecção de conversa elegível para resposta automática ('não respondida')."""

from datetime import datetime

from app.models import Conversa
from app.models.enums import OrigemMensagem
from app.services.tempo import para_utc


def mensagem_nao_respondida(conversa: Conversa, agora: datetime, minutos_sem_resposta: int) -> bool:
    """Indica se a conversa está elegível para resposta automática.

    Elegível quando, simultaneamente: a última mensagem é do cliente, passaram-se
    pelo menos ``minutos_sem_resposta`` minutos e a conversa não está em
    atendimento humano.
    """
    if conversa.em_atendimento_humano:
        return False
    if conversa.ultima_msg_origem != OrigemMensagem.CLIENTE:
        return False
    if conversa.ultima_msg_em is None:
        return False
    decorridos_min = (para_utc(agora) - para_utc(conversa.ultima_msg_em)).total_seconds() / 60
    return decorridos_min >= minutos_sem_resposta
