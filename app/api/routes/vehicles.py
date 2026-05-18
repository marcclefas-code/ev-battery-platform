from fastapi import APIRouter
from sqlalchemy import select, func
import structlog
from app.services.database import get_db_session
from app.models.vehicle_variant_code import VehicleVariantCode
from app.api.middleware.auth import ReadOnly

logger = structlog.get_logger()
router = APIRouter(prefix="/api/v1/vehicles", tags=["vehicles"])


@router.get("/makes")
async def list_makes(_: dict = Depends(ReadOnly())):
    async with get_db_session() as session:
        result = await session.execute(
            select(func.distinct(VehicleVariantCode.make)).order_by(VehicleVariantCode.make)
        )
        makes = [row[0] for row in result.fetchall()]
        return {"makes": makes}


@router.get("/makes/{make}/models")
async def list_models(make: str, _: dict = Depends(ReadOnly())):
    async with get_db_session() as session:
        result = await session.execute(
            select(func.distinct(VehicleVariantCode.model))
            .where(VehicleVariantCode.make == make)
            .order_by(VehicleVariantCode.model)
        )
        models = [row[0] for row in result.fetchall()]
        return {"make": make, "models": models}


@router.get("/makes/{make}/models/{model}/batteries")
async def list_vehicle_batteries(make: str, model: str, _: dict = Depends(ReadOnly())):
    async with get_db_session() as session:
        result = await session.execute(
            select(VehicleVariantCode.entity_id)
            .where(VehicleVariantCode.make == make, VehicleVariantCode.model == model)
        )
        entity_ids = [str(row[0]) for row in result.fetchall()]
        return {"make": make, "model": model, "battery_entity_ids": entity_ids}
