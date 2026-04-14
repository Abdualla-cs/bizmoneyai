# BizMoneyAI Admin Module

## Overview

The admin module is a separate operational surface for monitoring platform usage, reviewing user activity, and performing a small set of moderation actions. The frontend lives in `frontend/admin`, and the backend contract lives under `/admin/*`.

The current admin module is primarily read-heavy. Most pages focus on visibility and analysis, with only a few guarded write operations.

## Admin Features

- Admin-only authentication with a dedicated cookie.
- Global dashboard with optional per-user analytics scope.
- User monitoring with search, activity counts, enable/disable, and delete actions.
- Read-only transaction monitoring with filters for user, category, type, and date range.
- Category moderation with filtering, delete action, and default-category seeding.
- Budget monitoring with overspending analysis and trend summaries.
- AI insight monitoring with severity and trigger-frequency summaries.
- System log review with filters for event type, severity, actor, and date range.

## Available Pages

- `/login`: admin sign-in page.
- `/`: monitoring dashboard with overview metrics, charts, recent logs, and optional user scoping.
- `/users`: searchable user table with status toggle and delete action.
- `/transactions`: read-only operational ledger view.
- `/categories`: category review, moderation, and default-category creation.
- `/budgets`: budget monitoring, overspending trends, and budget table.
- `/insights`: AI insight review with severity and trigger summaries.
- `/logs`: system log explorer.

## Backend Routes

### Authentication

- `POST /admin/auth/login`
- `GET /admin/auth/me`
- `POST /admin/auth/logout`

### Dashboard and Analytics

- `GET /admin/dashboard`
- `GET /admin/analytics/overview`
- `GET /admin/analytics/transactions`
- `GET /admin/analytics/users`
- `GET /admin/analytics/insights`
- `GET /admin/analytics/budgets`

All dashboard and analytics endpoints accept optional `user_id`. Overview and transaction analytics also accept `days` with a bounded range of `7-180`.

### User Operations

- `GET /admin/users`
- `PATCH /admin/users/{user_id}/status`
- `DELETE /admin/users/{user_id}`

`GET /admin/users` supports search, active-state filtering, pagination, and sorting across account and activity fields.

### Transaction Operations

- `GET /admin/transactions`

Supports search, `user_id`, `category_id`, `type`, `date_from`, `date_to`, pagination, and sorting.

### Category Operations

- `GET /admin/categories`
- `DELETE /admin/categories/{category_id}`
- `POST /admin/categories/defaults`

`POST /admin/categories/defaults` can target all users or a single `user_id`, and it skips defaults that already exist by name for that user.

### Budget Operations

- `GET /admin/budgets`

Supports `user_id`, `month`, text search, pagination, and sorting. Responses also include overspending analysis, popular categories, and monthly trend summaries.

### Insight Operations

- `GET /admin/insights`

Supports `user_id`, search, severity filtering, date range filtering, pagination, and sorting.

### Log Operations

- `GET /admin/logs`

Supports search, `event_type`, `level`, `user_id`, `admin_id`, date range filters, pagination, and sorting.

## Permissions and Behavior

- Every `/admin/*` route requires a valid `admin_access_token` cookie.
- If a normal user session hits an admin route, the request is rejected with `403 Admin access required`.
- The dashboard can run in global mode or scoped mode for a single user. The selected scope changes every analytics request, not just the UI.
- Admin write actions are logged into `system_log` with actor and target metadata when available.
- Deleting a category from the admin module also removes related budgets and transactions for that category.
- User status changes use `PATCH /admin/users/{user_id}/status` rather than deleting the account outright.
- The transaction page is intentionally monitoring-only at the moment; edits are not exposed through the admin UI.
