import os
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from sqlalchemy import text

load_dotenv()

PORT = int(os.getenv("PORT", "8000"))
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "").split(",") if o.strip()]

app = FastAPI(
    title="Nucestatic Terminal API",
    description="API for Nucestatic Terminal",
    version="1.0.0"
)

from app.api.routes.auth import router as auth_router
app.include_router(auth_router, prefix="/api/auth", tags=["Auth"])

from app.api.routes.users import router as users_router
app.include_router(users_router, prefix="/api/users", tags=["Users"])

from app.api.routes.bookmarks import router as bookmarks_router
app.include_router(bookmarks_router, prefix="/api/bookmarks", tags=["Bookmarks"])

from app.api.routes.bridges import router as bridges_router
app.include_router(bridges_router, prefix="/api/bridge-apis", tags=["Bridge APIs"])

from app.api.routes.indicators import router as indicators_router
app.include_router(indicators_router, prefix="/api/indicators", tags=["Indicators"])

from app.api.routes.stats import router as stats_router
app.include_router(stats_router, prefix="/api/stats", tags=["Stats"])

from app.api.routes.alarms import router as alarms_router
app.include_router(alarms_router, prefix="/api/alarms", tags=["Alarms"])

from app.api.routes.brokers import router as brokers_router
app.include_router(brokers_router, prefix="/api/brokers", tags=["Brokers"])

from app.api.routes.broker_accounts import router as broker_accounts_router
app.include_router(broker_accounts_router, prefix="/api/brokers", tags=["Broker Accounts"])

from app.api.routes.broker_orders import router as broker_orders_router
app.include_router(broker_orders_router, prefix="/api/brokers", tags=["Broker Orders"])

if CORS_ORIGINS:
    from fastapi.middleware.cors import CORSMiddleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

@app.get("/api/health")
async def health_check():
    from app.databases.config import SessionLocal
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        return {"status": "healthy", "database": "connected"}
    except Exception:
        return {"status": "unhealthy", "database": "disconnected"}
    finally:
        db.close()

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=PORT,
        reload=True
    )
