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

from app.api.routes.indicator_settings import router as indicator_settings_router
app.include_router(indicator_settings_router, prefix="/api/indicator-settings", tags=["Indicator Settings"])

from app.api.routes.stats import router as stats_router
app.include_router(stats_router, prefix="/api/stats", tags=["Stats"])

from app.api.routes.alarms import router as alarms_router
app.include_router(alarms_router, prefix="/api/alarms", tags=["Alarms"])

from app.api.routes.cron_jobs import router as cron_jobs_router
app.include_router(cron_jobs_router, prefix="/api/cron-jobs", tags=["Cron Jobs"])

from app.api.routes.brokers import router as brokers_router
app.include_router(brokers_router, prefix="/api/brokers", tags=["Brokers"])

from app.api.routes.broker_accounts import router as broker_accounts_router
app.include_router(broker_accounts_router, prefix="/api/brokers", tags=["Broker Accounts"])

from app.api.routes.broker_orders import router as broker_orders_router
app.include_router(broker_orders_router, prefix="/api/brokers", tags=["Broker Orders"])

from app.api.routes.backtest_sessions import router as backtest_sessions_router
app.include_router(backtest_sessions_router, prefix="/api/backtest", tags=["Backtest Sessions"])

from app.api.routes.backtest_candles import router as backtest_candles_router
app.include_router(backtest_candles_router, prefix="/api/backtest", tags=["Backtest Candles"])

from app.api.routes.backtest_trade_state import router as backtest_trade_state_router
app.include_router(backtest_trade_state_router, prefix="/api/backtest", tags=["Backtest Trade State"])

from app.api.routes.backtest_history import router as backtest_history_router
app.include_router(backtest_history_router, prefix="/api/backtest", tags=["Backtest History"])

from app.api.routes.opencode_settings import router as opencode_settings_router
app.include_router(opencode_settings_router, prefix="/api/opencode-settings", tags=["OpenCode Settings"])

from app.api.routes.opencode_models import router as opencode_models_router
app.include_router(opencode_models_router, prefix="/api/opencode-models", tags=["OpenCode Models"])

from app.api.routes.opencode_test import router as opencode_test_router
app.include_router(opencode_test_router, prefix="/api/opencode-test", tags=["OpenCode Test"])

from app.api.routes.opencode_chat import router as opencode_chat_router
app.include_router(opencode_chat_router, prefix="/api/opencode-chat", tags=["OpenCode Chat"])

from app.api.routes.ai_sessions import router as ai_sessions_router
app.include_router(ai_sessions_router, prefix="/api/ai-sessions", tags=["AI Sessions"])

from app.api.routes.ai_rules import router as ai_rules_router
app.include_router(ai_rules_router, prefix="/api/ai-rules", tags=["AI Rules"])

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
