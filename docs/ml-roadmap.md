# BizMoneyAI ML Roadmap

## Current AI and ML Features

### Rule-based financial insights

- Endpoint: `POST /ai/generate`
- Source of truth: `backend/rules/rules.yaml`
- Current rule types include expense ratio, negative balance, high single expense, low transaction count, income drop, expense spike, and category spike detection.
- Output is persisted as `AIInsight` records so the system can review historical insight generation later.

### Category suggestion

- Endpoints: `POST /ml/train-category-model` and `POST /ml/predict-category`
- Model approach: sentence-transformer embeddings with cosine similarity matching.
- Per-user profiles are stored under `backend/artifacts/ml/user_<id>/`.
- Training uses the category name, category type, and up to the latest 20 transaction descriptions per category.

## Datasets in Use

- User-owned categories.
- User transaction descriptions grouped by category.
- Transaction windows used by the rules engine for current-period versus previous-period comparison.
- YAML rule configuration maintained in `backend/rules/rules.yaml`.

There is no separate centralized training dataset yet. The current ML behavior is built from each user's own financial records.

## Model Choices and Reasoning

### `all-MiniLM-L6-v2` for embeddings

Chosen because it is lightweight, runs locally, works well with short merchant-style text, and avoids introducing an external hosted inference dependency for basic category prediction.

### Profile matching instead of supervised classification

Chosen because the system currently has sparse, user-specific data and category lists that can change often. Averaged category profiles are simpler to maintain than a global classifier and are easier to rebuild per user.

### YAML rules for financial insights

Chosen because operational finance alerts need to stay transparent and easy to tune. The rules engine is easier to reason about than a black-box model at the current stage of the product.

## Planned Next Steps

- Add automatic profile retraining after category or transaction changes so predictions do not depend on a manual training call.
- Store model version metadata with each trained artifact so future migrations are easier.
- Add an evaluation harness for category prediction quality before introducing more complex models.
- Add confidence gating and abstain behavior for low-signal descriptions.
- Capture user correction feedback so category suggestions can improve from accepted versus rejected predictions.
- Explore anomaly detection and budget-risk scoring once there is enough historical data to evaluate those features safely.
- Consider an optional process warmup step only if first-request ML latency becomes user-facing enough to justify the extra startup cost.

## Current Constraints

- If the sentence-transformers model is unavailable, the service falls back to deterministic random vectors to keep the API online. This preserves availability but not semantic quality.
- Persisted profiles are only as fresh as the last training run.
- The current approach is optimized for small, user-level datasets, not large shared-model training.
- The embedding model is loaded lazily on first use. `backend/app/services/embeddings.py` already caches the model in-process after that first load, but a fresh process still pays the initial warm-start cost.
