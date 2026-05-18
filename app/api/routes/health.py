from fastapi import APIRouter
import structlog
from app.services.database import get_engine
from sqlalchemy import text

logger = structlog.get_logger()
router = APIRouter(prefix="/api/v1/health", tags=["health"])


@router.get("/")
async def health_check():
    return {"status": "ok", "service": "ev-battery-platform"}


@router.get("/ready")
async def readiness_check():
    try:
        engine = get_engine()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return {"ready": True, "database": "connected"}
    except Exception as e:
        return {"ready": False, "database": "disconnected", "error": str(e)}


@router.get("/live")
async def liveness_check():
    return {"alive": True}
