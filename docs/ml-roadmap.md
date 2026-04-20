# BizMoneyAI ML Roadmap

## Current AI and ML Features

### Rule-based financial insights

- Endpoints: `POST /ai/generate`, `GET /ai/insights`, and `GET /ai/insights/timeseries`
- Source of truth: `backend/rules/rules.yaml`
- Runtime implementation: `backend/app/services/insights/`
- Current phase-1 rule ids are:
  - `zero_income_with_expense`
  - `expense_ratio`
  - `profit_drop_percent`
  - `spending_spike_percent`
  - `negative_balance`
  - `negative_balance_below`
  - `budget_overspend_ratio`
  - `category_income_ratio`
  - `income_drop_percent`
  - `missing_budget_high_spend`
  - `consecutive_budget_overspend`
- Output is persisted as `AIInsight` records with `rule_id` and `metadata_json` so the system can audit historical insight generation later.
- Duplicate insight inserts are prevented per user, rule, period, and `scope_key`.

### Category suggestion

- Endpoint: `POST /ml/predict-category`
- Model approach: sentence-transformer embeddings with cosine similarity matching.
- The current API compares the request text against the authenticated user's live category list. There is no persisted training endpoint in the current runtime API.

## Datasets in Use

- User-owned categories.
- User transactions for current-period versus previous-period comparisons.
- User budgets for category-month budget monitoring and overspending streaks.
- Persisted `ai_insights` rows for historical review.
- YAML rule configuration maintained in `backend/rules/rules.yaml`.

There is no separate centralized training dataset yet. The current ML behavior is built from each user's own financial records.

## Model Choices and Reasoning

### `all-MiniLM-L6-v2` for embeddings

Chosen because it is lightweight, runs locally, works well with short merchant-style text, and avoids introducing an external hosted inference dependency for basic category prediction.

### Direct category embedding comparison instead of supervised classification

Chosen because the system currently has sparse, user-specific data and category lists that can change often. Live category matching is simple to operate, transparent to debug, and does not require a separate training lifecycle.

### YAML rules for financial insights

Chosen because operational finance alerts need to stay transparent and easy to tune. The rules engine is easier to reason about than a black-box model at the current stage of the product.

## Planned Next Steps

- Add an evaluation harness for category prediction quality before introducing more complex models.
- Add confidence gating and abstain behavior for low-signal descriptions.
- Capture user correction feedback so category suggestions can improve from accepted versus rejected predictions.
- Explore anomaly detection and budget-risk scoring once there is enough historical data to evaluate those features safely.
- Consider an optional process warmup step only if first-request ML latency becomes user-facing enough to justify the extra startup cost.

## Current Constraints

- If the sentence-transformers model is unavailable, the service falls back to deterministic random vectors to keep the API online. This preserves availability but not semantic quality.
- The current approach is optimized for small, user-level datasets, not large shared-model training.
- The embedding model is loaded lazily on first use. `backend/app/services/embeddings.py` already caches the model in-process after that first load, but a fresh process still pays the initial warm-start cost.
