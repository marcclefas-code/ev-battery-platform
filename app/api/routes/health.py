from fastapi import APIRouter
import structlog

logger = structlog.get_logger()
router = APIRouter(prefix="/api/v1/health", tags=["health"])


@router.get("/")
async def health_check():
    return {"status": "ok", "service": "ev-battery-platform"}


@router.get("/ready")
async def readiness_check():
    return {"ready": True}


@router.get("/live")
async def liveness_check():
    return {"alive": True}
