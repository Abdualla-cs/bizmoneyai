# BizMoneyAI Known Issues

## 1. AI verification still leaves non-blocking framework deprecation warnings

- The isolated AI verification suite passes, but the backend still emits Pydantic v2 `Config` deprecation warnings and `datetime.utcnow()` deprecation warnings during test runs.
- Files affected include `backend/app/schemas/*.py` and model defaults still using `datetime.utcnow`.
- Impact: the AI insight engine works as expected, but these warnings should be cleaned up before a longer production hardening pass.
- Expected follow-up: migrate schema configs to `ConfigDict` and standardize UTC-aware timestamp defaults.

## 2. ML fallback mode favors uptime over quality

- If `sentence-transformers` cannot load, `embed_texts` falls back to deterministic random vectors.
- File affected: `backend/app/services/embeddings.py`.
- Impact: the API remains available, but category suggestions are not semantically reliable in fallback mode.
- Expected follow-up: surface fallback mode in monitoring and avoid presenting those predictions as fully trusted.

## 3. The first embedding-backed ML request still has a warm-start hit

- The sentence-transformer model is loaded lazily on first use and then cached in-process.
- File affected: `backend/app/services/embeddings.py`.
- Impact: the first ML prediction request in a fresh process can take noticeably longer than steady-state requests.
- Expected follow-up: add an optional warmup path only if that latency becomes user-facing enough to justify the extra startup work.

## 4. Legacy mixed-case auth data may still need cleanup during rollout

- New writes and logins now normalize email casing, but this patch does not include a data migration for any pre-existing mixed-case or duplicate account rows from older builds.
- Files affected: `backend/app/api/auth.py`, `backend/app/models/user.py`.
- Impact: if historical duplicate rows already exist in a deployed database, they should still be reviewed and cleaned up operationally.
- Expected follow-up: add a one-time backfill or audit script before production rollout if legacy auth data is already present.
