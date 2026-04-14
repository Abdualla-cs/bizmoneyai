"""add admins and system logs

Revision ID: 0003_add_admins_and_system_logs
Revises: 0002_add_budgets
Create Date: 2026-04-06 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003_add_admins_and_system_logs"
down_revision: str | None = "0002_add_budgets"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "admins",
        sa.Column("admin_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("admin_id"),
        sa.UniqueConstraint("email"),
    )
    op.create_index(op.f("ix_admins_admin_id"), "admins", ["admin_id"], unique=False)
    op.create_index(op.f("ix_admins_email"), "admins", ["email"], unique=True)

    op.add_column("users", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))

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


def downgrade() -> None:
    op.drop_index(op.f("ix_system_logs_user_id"), table_name="system_logs")
    op.drop_index(op.f("ix_system_logs_admin_id"), table_name="system_logs")
    op.drop_index(op.f("ix_system_logs_log_id"), table_name="system_logs")
    op.drop_table("system_logs")

    op.drop_column("users", "is_active")

    op.drop_index(op.f("ix_admins_email"), table_name="admins")
    op.drop_index(op.f("ix_admins_admin_id"), table_name="admins")
    op.drop_table("admins")
