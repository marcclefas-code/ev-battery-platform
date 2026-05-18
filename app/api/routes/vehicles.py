from fastapi import APIRouter
import structlog

logger = structlog.get_logger()
router = APIRouter(prefix="/api/v1/vehicles", tags=["vehicles"])


@router.get("/makes")
async def list_makes():
    return []


@router.get("/makes/{make}/models")
async def list_models(make: str):
    return []


@router.get("/makes/{make}/models/{model}/batteries")
async def list_vehicle_batteries(make: str, model: str):
    return []
