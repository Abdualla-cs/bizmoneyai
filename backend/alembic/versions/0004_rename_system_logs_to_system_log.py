"""rename system logs table

Revision ID: 0004_rename_system_log
Revises: 0003_add_admins_and_system_logs
Create Date: 2026-04-06 00:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0004_rename_system_log"
down_revision: str | None = "0003_add_admins_and_system_logs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "system_log",
        sa.Column("log_id", sa.Integer(), nullable=False),
        sa.Column("admin_id", sa.Integer(), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("level", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["admin_id"], ["admins.admin_id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("log_id"),
    )
    op.create_index(op.f("ix_system_log_log_id"), "system_log", ["log_id"], unique=False)
    op.create_index(op.f("ix_system_log_admin_id"), "system_log", ["admin_id"], unique=False)
    op.create_index(op.f("ix_system_log_user_id"), "system_log", ["user_id"], unique=False)

    op.execute(
        """
        INSERT INTO system_log (log_id, admin_id, user_id, event_type, message, level, created_at)
        SELECT log_id, admin_id, user_id, event_type, message, level, created_at
        FROM system_logs
        """
    )

    op.drop_index(op.f("ix_system_logs_user_id"), table_name="system_logs")
    op.drop_index(op.f("ix_system_logs_admin_id"), table_name="system_logs")
    op.drop_index(op.f("ix_system_logs_log_id"), table_name="system_logs")
    op.drop_table("system_logs")


def downgrade() -> None:
    op.create_table(
        "system_logs",
        sa.Column("log_id", sa.Integer(), nullable=False),
        sa.Column("admin_id", sa.Integer(), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("level", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["admin_id"], ["admins.admin_id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("log_id"),
    )
    op.create_index(op.f("ix_system_logs_log_id"), "system_logs", ["log_id"], unique=False)
    op.create_index(op.f("ix_system_logs_admin_id"), "system_logs", ["admin_id"], unique=False)
    op.create_index(op.f("ix_system_logs_user_id"), "system_logs", ["user_id"], unique=False)

    op.execute(
        """
        INSERT INTO system_logs (log_id, admin_id, user_id, event_type, message, level, created_at)
        SELECT log_id, admin_id, user_id, event_type, message, level, created_at
        FROM system_log
        """
    )

    op.drop_index(op.f("ix_system_log_user_id"), table_name="system_log")
    op.drop_index(op.f("ix_system_log_admin_id"), table_name="system_log")
    op.drop_index(op.f("ix_system_log_log_id"), table_name="system_log")
    op.drop_table("system_log")
