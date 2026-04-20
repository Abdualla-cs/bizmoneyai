"""add ai insight rule tracking

Revision ID: 0007_add_ai_insight_rule_tracking
Revises: 0006_add_system_log_metadata_json
Create Date: 2026-04-20 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0007_add_ai_insight_rule_tracking"
down_revision: str | None = "0006_add_system_log_metadata_json"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("ai_insights", sa.Column("rule_id", sa.String(length=120), nullable=True))
    op.add_column("ai_insights", sa.Column("metadata_json", sa.JSON(), nullable=True))
    op.create_index(op.f("ix_ai_insights_rule_id"), "ai_insights", ["rule_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_ai_insights_rule_id"), table_name="ai_insights")
    op.drop_column("ai_insights", "metadata_json")
    op.drop_column("ai_insights", "rule_id")
