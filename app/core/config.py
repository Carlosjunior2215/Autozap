"""Configurações da aplicação, carregadas de variáveis de ambiente (.env)."""

from functools import lru_cache
from typing import Self

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Valores de exemplo do .env.example: nunca devem ir para produção.
_PLACEHOLDERS = frozenset(
    {
        "troque-este-token-de-verificacao",
        "troque-este-app-secret",
        "troque-esta-chave-admin",
    }
)
_AMBIENTES_PRODUCAO = frozenset({"producao", "produção", "production", "prod"})


class Configuracoes(BaseSettings):
    """Configurações centrais do autozap, lidas do ambiente ou do arquivo .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Aplicação
    ambiente: str = "desenvolvimento"
    debug: bool = False

    # Logging
    log_nivel: str = "INFO"
    log_json: bool = True

    # Banco de dados (async via asyncpg)
    database_url: str = "postgresql+asyncpg://autozap:autozap@localhost:5432/autozap"

    # Redis / Celery
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # WhatsApp Cloud API (Meta)
    whatsapp_verify_token: str = "troque-este-token-de-verificacao"
    whatsapp_app_secret: str = "troque-este-app-secret"
    whatsapp_access_token: str = ""
    whatsapp_phone_number_id: str = ""
    whatsapp_api_base_url: str = "https://graph.facebook.com/v21.0"

    # Anthropic
    anthropic_api_key: str = ""
    modelo_classificacao: str = "claude-haiku-4-5"
    modelo_resposta: str = "claude-sonnet-4-6"
    anthropic_timeout_seg: float = 30.0
    anthropic_max_retries: int = 2

    # WhatsApp (HTTP)
    whatsapp_timeout_seg: float = 10.0

    # Regras de negócio
    minutos_sem_resposta: int = 0
    limiar_confianca: float = 0.7
    max_respostas_por_hora: int = 10

    # Agendamento (slots configuráveis)
    servicos_oferecidos: str = "Corte de cabelo,Barba,Manicure"
    agenda_hora_abertura: int = 9
    agenda_hora_fechamento: int = 18
    agenda_duracao_min: int = 60
    agenda_dias_a_frente: int = 3
    agenda_timezone: str = "America/Sao_Paulo"
    max_slots_oferecidos: int = 9

    # Administração
    admin_api_key: str = "troque-esta-chave-admin"

    @model_validator(mode="after")
    def _exigir_segredos_em_producao(self) -> Self:
        """Em produção, recusa segredos vazios ou ainda com o valor de exemplo."""
        if self.ambiente.strip().lower() not in _AMBIENTES_PRODUCAO:
            return self
        obrigatorios = {
            "WHATSAPP_VERIFY_TOKEN": self.whatsapp_verify_token,
            "WHATSAPP_APP_SECRET": self.whatsapp_app_secret,
            "WHATSAPP_ACCESS_TOKEN": self.whatsapp_access_token,
            "WHATSAPP_PHONE_NUMBER_ID": self.whatsapp_phone_number_id,
            "ANTHROPIC_API_KEY": self.anthropic_api_key,
            "ADMIN_API_KEY": self.admin_api_key,
        }
        invalidos = [
            nome for nome, valor in obrigatorios.items() if not valor or valor in _PLACEHOLDERS
        ]
        if invalidos:
            raise ValueError(
                "Em produção, defina valores reais para: " + ", ".join(sorted(invalidos))
            )
        return self


@lru_cache
def obter_configuracoes() -> Configuracoes:
    """Retorna uma instância única (cacheada) das configurações."""
    return Configuracoes()
