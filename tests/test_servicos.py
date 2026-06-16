"""Testes unitários dos serviços puros (regras, detecção, janela, opt-out)."""

from datetime import timedelta

from app.models import Conversa
from app.models.enums import CategoriaIntencao, OrigemMensagem
from app.services.classificador import classificar_por_regras
from app.services.deteccao import mensagem_nao_respondida
from app.services.janela_24h import dentro_da_janela_24h
from app.services.opt_out import eh_pedido_opt_out
from app.services.tempo import agora_utc


def test_classificar_por_regras_categorias() -> None:
    assert classificar_por_regras("Quero agendar um horário") == CategoriaIntencao.AGENDAMENTO
    assert classificar_por_regras("Qual o preço?") == CategoriaIntencao.SERVICOS
    assert classificar_por_regras("Tem desconto?") == CategoriaIntencao.PROMOCOES
    assert classificar_por_regras("Preciso de ajuda") == CategoriaIntencao.AJUDA


def test_classificar_por_regras_indeciso() -> None:
    assert classificar_por_regras("bom dia, tudo bem?") is None
    assert classificar_por_regras("") is None


def test_eh_pedido_opt_out() -> None:
    assert eh_pedido_opt_out("pare")
    assert eh_pedido_opt_out("  SAIR  ")
    assert not eh_pedido_opt_out("não pare por favor")
    assert not eh_pedido_opt_out(None)


def test_dentro_da_janela_24h() -> None:
    agora = agora_utc()
    assert dentro_da_janela_24h(agora - timedelta(hours=1), agora)
    assert not dentro_da_janela_24h(agora - timedelta(hours=25), agora)
    assert not dentro_da_janela_24h(None, agora)


def test_mensagem_nao_respondida_elegivel() -> None:
    agora = agora_utc()
    conversa = Conversa(
        contato_id=1,
        em_atendimento_humano=False,
        ultima_msg_origem=OrigemMensagem.CLIENTE,
        ultima_msg_em=agora,
    )
    assert mensagem_nao_respondida(conversa, agora, minutos_sem_resposta=0)


def test_mensagem_nao_respondida_bloqueios() -> None:
    agora = agora_utc()
    # Em atendimento humano não é elegível.
    em_humano = Conversa(
        contato_id=1,
        em_atendimento_humano=True,
        ultima_msg_origem=OrigemMensagem.CLIENTE,
        ultima_msg_em=agora,
    )
    assert not mensagem_nao_respondida(em_humano, agora, 0)

    # Última mensagem não é do cliente.
    do_bot = Conversa(
        contato_id=1,
        em_atendimento_humano=False,
        ultima_msg_origem=OrigemMensagem.BOT,
        ultima_msg_em=agora,
    )
    assert not mensagem_nao_respondida(do_bot, agora, 0)

    # Atraso mínimo não cumprido.
    recente = Conversa(
        contato_id=1,
        em_atendimento_humano=False,
        ultima_msg_origem=OrigemMensagem.CLIENTE,
        ultima_msg_em=agora,
    )
    assert not mensagem_nao_respondida(recente, agora, minutos_sem_resposta=5)
