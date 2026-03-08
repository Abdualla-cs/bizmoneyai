from datetime import date
from pathlib import Path

import yaml
from sqlalchemy.orm import Session

from app.models.ai_insight import AIInsight
from app.models.transaction import Transaction


RULES_PATH = Path(__file__).resolve().parents[2] / "rules" / "rules.yaml"


def run_rules_for_user(db: Session, user_id: int, period_start: date, period_end: date) -> list[AIInsight]:
    with open(RULES_PATH, "r", encoding="utf-8") as fh:
        config = yaml.safe_load(fh) or {}

    txs = (
        db.query(Transaction)
        .filter(
            Transaction.user_id == user_id,
            Transaction.date >= period_start,
            Transaction.date <= period_end,
        )
        .all()
    )

    total_income = sum(t.amount for t in txs if t.type == "income")
    total_expense = sum(t.amount for t in txs if t.type == "expense")
    expense_ratio = (total_expense / total_income) if total_income > 0 else 0.0

    created: list[AIInsight] = []

    for rule in config.get("rules", []):
        rule_type = rule.get("type")
        triggered = False

        if rule_type == "expense_ratio_gt":
            threshold = float(rule.get("threshold", 0.8))
            triggered = expense_ratio > threshold

        if rule_type == "high_single_expense":
            threshold = float(rule.get("threshold", 500.0))
            triggered = any(t.type == "expense" and t.amount > threshold for t in txs)

        if triggered:
            insight = AIInsight(
                user_id=user_id,
                title=rule.get("title", "Insight"),
                message=rule.get("message", "Rule triggered"),
                severity=rule.get("severity", "info"),
                period_start=period_start,
                period_end=period_end,
            )
            db.add(insight)
            created.append(insight)

    db.commit()
    for item in created:
        db.refresh(item)
    return created
