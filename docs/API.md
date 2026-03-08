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
- `GET /ai/insights`

## ML
- `POST /ml/predict-category`

All non-auth endpoints enforce ownership by authenticated user.
