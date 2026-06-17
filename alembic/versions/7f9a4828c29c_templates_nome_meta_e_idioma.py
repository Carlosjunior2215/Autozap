"""templates nome_meta e idioma

Revision ID: 7f9a4828c29c
Revises: eed42955c620
Create Date: 2026-06-17 13:22:27.057083

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "7f9a4828c29c"
down_revision: str | None = "eed42955c620"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Aplica a migration."""
    op.add_column("templates", sa.Column("nome_meta", sa.String(length=128), nullable=True))
    op.add_column(
        "templates",
        sa.Column("idioma", sa.String(length=10), nullable=False, server_default="pt_BR"),
    )


def downgrade() -> None:
    """Reverte a migration."""
    op.drop_column("templates", "idioma")
    op.drop_column("templates", "nome_meta")
