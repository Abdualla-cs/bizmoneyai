# BizMoneyAI Architecture

## System Overview

BizMoneyAI is split into three main application surfaces:

- `frontend/user`: the customer-facing Next.js app for authentication, transactions, categories, budgets, dashboard, and AI insights.
- `frontend/admin`: the admin-facing Next.js app for operational monitoring, moderation, and system analytics.
- `backend/app`: the FastAPI API layer that owns auth, business logic, data access, AI insights, ML category prediction, and admin workflows.

Primary state lives in PostgreSQL through SQLAlchemy and Alembic migrations. Rule-based insight behavior is configured in `backend/rules/rules.yaml`, and the current ML category suggestion flow runs directly from live category data plus in-process embeddings.

## Core Backend Modules

- `app/api`: HTTP routes for auth, admin, categories, transactions, budgets, dashboard, AI, ML, and health.
- `app/models`: SQLAlchemy models for users, admins, categories, transactions, budgets, AI insights, and system logs.
- `app/services`: financial metrics, the modular AI insight engine, embedding generation, budget calculations, system logging, and admin analytics.
- `app/services/insights`: rule context calculation, YAML rule loading/validation, candidate generation, and deduplication for persisted AI insights.
- `app/data_access`: reusable query/filter helpers for insight reporting, timeseries responses, and training-data extraction.
- `app/core`: config, logging, auth/security helpers, time utilities, and exception handling.

## Key Runtime Flows

### User authentication

User login and registration are handled by `/auth/*`. Successful login sets an HttpOnly `access_token` cookie, and protected user routes resolve the current user from that cookie.

### Admin authentication

Admin login is isolated under `/admin/auth/*`. Successful login sets a separate HttpOnly `admin_access_token` cookie. Admin routes reject normal user sessions with `403 Admin access required`.

### Financial data flow

Users manage categories, transactions, and budgets through the backend APIs. Dashboard and analytics views are generated from persisted transactional data rather than frontend-side aggregation.

### AI insight flow

`/ai/generate` runs the YAML-driven rules engine against a requested date range, computes current-period and previous-period metrics, evaluates the phase-1 ruleset from `backend/rules/rules.yaml`, deduplicates by `rule_id + scope_key` inside the requested period, and persists only new `AIInsight` rows. `GET /ai/insights`, `GET /ai/insights/timeseries`, and the admin insight endpoints read from those stored records.

Persisted AI insights now carry both `rule_id` and `metadata_json`. Category-period rules use stable `scope_key` values in metadata so reruns do not create duplicates for the same category or category-month. See `docs/ai-insights.md` for the current production ruleset and endpoint contract.

### ML category suggestion flow

`/ml/predict-category` embeds the user input plus the authenticated user's current categories, compares them by cosine similarity, and returns the closest category match. If the sentence-transformers model is unavailable, the service falls back to deterministic local vectors so the endpoint stays online.

## Admin Analytics

The admin dashboard is composed from service-level analytics builders in `app/services/admin_analytics.py`. Those responses are cached in-process for 30 seconds per scope (`global` or `user_id`) to reduce repeated query cost. Admin pages can operate globally or be narrowed to a single user.

## Data Model Snapshot

The current operational model includes:

- `users`
- `admins`
- `categories`
- `transactions`
- `budgets`
- `ai_insights`
- `system_log`

This is the current production shape that the user app, admin app, AI logic, and audit logging all depend on.
