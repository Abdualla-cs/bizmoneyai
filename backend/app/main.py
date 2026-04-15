from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import admin, admin_auth, ai, auth, budgets, categories, dashboard, health, ml, transactions
from app.core.config import settings

app = FastAPI(title=settings.app_name)

origins = [origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(admin_auth.router)
app.include_router(admin_auth.protected_router)
app.include_router(admin.router)
app.include_router(categories.router)
app.include_router(transactions.router)
app.include_router(budgets.router)
app.include_router(dashboard.router)
app.include_router(ai.router)
app.include_router(ml.router)
