"""Ambiente de migrations do Alembic (assíncrono, asyncpg)."""

import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context
from app.core.config import obter_configuracoes
from app.models import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# A URL vem das configurações da aplicação (não fica fixa no .ini).
config.set_main_option("sqlalchemy.url", obter_configuracoes().database_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Executa as migrations em modo offline (gera SQL, sem conexão)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Configura o contexto e executa as migrations sobre uma conexão."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Cria o engine assíncrono e roda as migrations sobre ele."""
    secao = config.get_section(config.config_ini_section, {})
    connectable = async_engine_from_config(secao, prefix="sqlalchemy.", poolclass=pool.NullPool)
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    """Executa as migrations em modo online (com conexão)."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
