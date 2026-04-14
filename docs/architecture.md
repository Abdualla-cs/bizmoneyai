# BizMoneyAI Architecture

## System Overview

BizMoneyAI is split into three main application surfaces:

- `frontend/user`: the customer-facing Next.js app for authentication, transactions, categories, budgets, dashboard, and AI insights.
- `frontend/admin`: the admin-facing Next.js app for operational monitoring, moderation, and system analytics.
- `backend/app`: the FastAPI API layer that owns auth, business logic, data access, AI insights, ML category prediction, and admin workflows.

Primary state lives in PostgreSQL through SQLAlchemy and Alembic migrations. ML artifacts are stored on disk under `backend/artifacts/ml/user_<id>/`. Rule-based insight behavior is configured in `backend/rules/rules.yaml`.

## Core Backend Modules

- `app/api`: HTTP routes for auth, admin, categories, transactions, budgets, dashboard, AI, ML, and health.
- `app/models`: SQLAlchemy models for users, admins, categories, transactions, budgets, AI insights, and system logs.
- `app/services`: financial metrics, rules evaluation, embedding generation, ML profile training, budget calculations, system logging, and admin analytics.
- `app/data_access`: reusable training-data extraction used by ML profile building.
- `app/core`: config, logging, auth/security helpers, time utilities, and exception handling.

## Key Runtime Flows

### User authentication

User login and registration are handled by `/auth/*`. Successful login sets an HttpOnly `access_token` cookie, and protected user routes resolve the current user from that cookie.

### Admin authentication

Admin login is isolated under `/admin/auth/*`. Successful login sets a separate HttpOnly `admin_access_token` cookie. Admin routes reject normal user sessions with `403 Admin access required`.

### Financial data flow

Users manage categories, transactions, and budgets through the backend APIs. Dashboard and analytics views are generated from persisted transactional data rather than frontend-side aggregation.

### AI insight flow

`/ai/generate` runs the YAML-driven rules engine against a requested date range, computes financial metrics, compares the result with the previous period, and persists new `AIInsight` rows when a rule triggers. `/ai/insights` and admin insight endpoints read from those stored records.

### ML category suggestion flow

`/ml/train-category-model` builds per-user category profiles from category labels plus recent transaction descriptions. Profiles are stored as `profiles.npy` and `metadata.json`. `/ml/predict-category` loads those profiles when available, otherwise falls back to category-name embeddings generated on demand, then returns the closest match by cosine similarity.

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
