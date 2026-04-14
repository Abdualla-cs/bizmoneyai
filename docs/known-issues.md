# BizMoneyAI Known Issues

## 1. Category prediction profiles require explicit retraining

- Persisted category profiles are refreshed only when `POST /ml/train-category-model` or the training script runs.
- The current user frontend calls prediction but does not automatically trigger retraining after category or transaction changes.
- Impact: predictions can become stale or fall back to weaker category-name-only matching.
- Expected follow-up: retrain automatically after relevant write operations or schedule retraining jobs.

## 2. ML fallback mode favors uptime over quality

- If `sentence-transformers` cannot load, `embed_texts` falls back to deterministic random vectors.
- File affected: `backend/app/services/embeddings.py`.
- Impact: the API remains available, but category suggestions are not semantically reliable in fallback mode.
- Expected follow-up: surface fallback mode in monitoring and avoid presenting those predictions as fully trusted.

## 3. The first embedding-backed ML request still has a warm-start hit

- The sentence-transformer model is loaded lazily on first use and then cached in-process.
- File affected: `backend/app/services/embeddings.py`.
- Impact: the first ML training or prediction request in a fresh process can take noticeably longer than steady-state requests.
- Expected follow-up: add an optional warmup path only if that latency becomes user-facing enough to justify the extra startup work.

## 4. Legacy mixed-case auth data may still need cleanup during rollout

- New writes and logins now normalize email casing, but this patch does not include a data migration for any pre-existing mixed-case or duplicate account rows from older builds.
- Files affected: `backend/app/api/auth.py`, `backend/app/models/user.py`.
- Impact: if historical duplicate rows already exist in a deployed database, they should still be reviewed and cleaned up operationally.
- Expected follow-up: add a one-time backfill or audit script before production rollout if legacy auth data is already present.
