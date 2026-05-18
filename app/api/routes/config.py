from fastapi import APIRouter, HTTPException
import structlog

logger = structlog.get_logger()
router = APIRouter(prefix="/api/v1/config", tags=["config"])


@router.get("/property-definitions")
async def list_property_definitions():
    return []


@router.get("/wave-policies")
async def list_wave_policies():
    return {}


@router.get("/brands")
async def list_brands():
    return []
