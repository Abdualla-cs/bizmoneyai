"""add metadata json to system log

Revision ID: 0006_add_system_log_metadata_json
Revises: 0005_enforce_budget_month_year_uniqueness
Create Date: 2026-04-13 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0006_add_system_log_metadata_json"
down_revision: str | None = "0005_enforce_budget_month_year_uniqueness"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("system_log", sa.Column("metadata_json", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("system_log", "metadata_json")
