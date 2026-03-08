# Setup

## Prerequisites
- Python 3.12+
- Node 20+
- Docker (for local PostgreSQL)

## 1) Start Postgres
```bash
docker compose up -d db
```

## 2) Backend
```bash
cd backend
python -m venv .venv
# Windows
.venv\\Scripts\\activate
# macOS/Linux
# source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

## 3) Frontend
```bash
cd frontend
npm install
copy .env.local.example .env.local
npm run dev
```

Open `http://localhost:3000`.
