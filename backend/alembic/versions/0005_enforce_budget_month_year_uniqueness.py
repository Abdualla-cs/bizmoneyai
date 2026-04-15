"""enforce budget month-year uniqueness

Revision ID: 0005_budget_month_unique
Revises: 0004_rename_system_log
Create Date: 2026-04-13 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0005_budget_month_unique"
down_revision: str | None = "0004_rename_system_log"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _duplicate_month_year_rows(bind) -> list[tuple[int, int, int, int, int]]:
    if bind.dialect.name == "sqlite":
        rows = bind.execute(
            sa.text(
                """
                SELECT
                    user_id,
                    category_id,
                    CAST(STRFTIME('%Y', month) AS INTEGER) AS year_value,
                    CAST(STRFTIME('%m', month) AS INTEGER) AS month_value,
                    COUNT(*) AS duplicate_count
                FROM budgets
                GROUP BY
                    user_id,
                    category_id,
                    CAST(STRFTIME('%Y', month) AS INTEGER),
                    CAST(STRFTIME('%m', month) AS INTEGER)
                HAVING COUNT(*) > 1
                """
            )
        ).fetchall()
    else:
        rows = bind.execute(
            sa.text(
                """
                SELECT
                    user_id,
                    category_id,
                    CAST(EXTRACT(YEAR FROM month) AS INTEGER) AS year_value,
                    CAST(EXTRACT(MONTH FROM month) AS INTEGER) AS month_value,
                    COUNT(*) AS duplicate_count
                FROM budgets
                GROUP BY
                    user_id,
                    category_id,
                    CAST(EXTRACT(YEAR FROM month) AS INTEGER),
                    CAST(EXTRACT(MONTH FROM month) AS INTEGER)
                HAVING COUNT(*) > 1
                """
            )
        ).fetchall()

    return [(row[0], row[1], row[2], row[3], row[4]) for row in rows]


def _normalize_budget_months(bind) -> None:
    if bind.dialect.name == "sqlite":
        bind.execute(
            sa.text(
                """
                UPDATE budgets
                SET month = date(strftime('%Y-%m-01', month))
                WHERE month <> date(strftime('%Y-%m-01', month))
                """
            )
        )
        bind.execute(
            sa.text(
                """
                CREATE UNIQUE INDEX uq_budgets_user_category_month_year
                ON budgets (
                    user_id,
                    category_id,
                    CAST(STRFTIME('%m', month) AS INTEGER),
                    CAST(STRFTIME('%Y', month) AS INTEGER)
                )
                """
            )
        )
        return

    bind.execute(
        sa.text(
            """
            UPDATE budgets
            SET month = DATE_TRUNC('month', month)::date
            WHERE month <> DATE_TRUNC('month', month)::date
            """
        )
    )
    bind.execute(
        sa.text(
            """
            CREATE UNIQUE INDEX uq_budgets_user_category_month_year
            ON budgets (
                user_id,
                category_id,
                EXTRACT(MONTH FROM month),
                EXTRACT(YEAR FROM month)
            )
            """
        )
    )


def upgrade() -> None:
    bind = op.get_bind()
    duplicates = _duplicate_month_year_rows(bind)
    if duplicates:
        preview = ", ".join(
            f"user={user_id}/category={category_id}/{year_value:04d}-{month_value:02d} x{duplicate_count}"
            for user_id, category_id, year_value, month_value, duplicate_count in duplicates[:5]
        )
        raise RuntimeError(
            "Duplicate budgets already exist for the same user/category/month-year combinations. "
            f"Resolve them before applying this migration: {preview}"
        )

    _normalize_budget_months(bind)


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("DROP INDEX IF EXISTS uq_budgets_user_category_month_year"))
