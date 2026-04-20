# API

Base URL: `http://localhost:8000`

## Health
- `GET /health`

## Auth
- `POST /auth/register`
- `POST /auth/login` (sets HttpOnly `access_token` cookie)

## Categories
- `GET /categories`
- `POST /categories`
- `PUT /categories/{id}`
- `DELETE /categories/{id}`

## Transactions
- `GET /transactions`
- `POST /transactions`
- `PUT /transactions/{id}`
- `DELETE /transactions/{id}`
- `GET /transactions/export-csv` (extra MVP utility)
- `POST /transactions/import-csv` (extra MVP utility)

## Dashboard
- `GET /dashboard/summary`

## AI
- `POST /ai/generate`
  - optional JSON body: `period_start`, `period_end`
  - default behavior with no body: generates for the last 30 days ending on today
  - returns only newly created insight rows after deduplication
  - writes persisted `ai_insights` rows and a `generate_insights` system log entry
  - returns `422` if `period_start > period_end`
- `GET /ai/insights`
  - query params: `date_from`, `date_to`, `severity`
  - filters persisted insights by `created_at` range and severity
  - returns `422` if `date_from > date_to`
- `GET /ai/insights/timeseries`
  - query params: `date_from`, `date_to`, `severity`, `granularity=day|month`
  - returns persisted insight counts bucketed by created date
  - returns `422` for invalid date ranges or unsupported `granularity`

## ML
- `POST /ml/predict-category`

All non-auth endpoints enforce ownership by authenticated user.
