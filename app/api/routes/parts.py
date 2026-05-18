from fastapi import APIRouter, HTTPException, Depends
from typing import Optional
import uuid
import structlog
from sqlalchemy import select
from app.services.database import get_db_session
from app.models.part_number import BatteryPartNumber
from app.models.vehicle_variant_code import VehicleVariantCode
from app.api.middleware.auth import ReadOnly

logger = structlog.get_logger()
router = APIRouter(prefix="/api/v1/parts", tags=["parts"])


@router.get("/")
async def list_parts(brand: Optional[str] = None, page: int = 1, page_size: int = 50, _: dict = Depends(ReadOnly())):
    async with get_db_session() as session:
        query = select(BatteryPartNumber)
        if brand:
            query = query.where(BatteryPartNumber.brand == brand)
        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await session.execute(query)
        parts = result.scalars().all()
        return {"items": [{"id": str(p.id), "raw": p.raw, "normalized": p.normalized, "brand": p.brand, "pn_type": p.pn_type} for p in parts]}


@router.get("/{part_id}")
async def get_part(part_id: str, _: dict = Depends(ReadOnly())):
    async with get_db_session() as session:
        result = await session.execute(select(BatteryPartNumber).where(BatteryPartNumber.id == uuid.UUID(part_id)))
        part = result.scalar_one_or_none()
        if not part:
            raise HTTPException(status_code=404, detail="Part not found")
        return {"id": str(part.id), "raw": part.raw, "normalized": part.normalized, "brand": part.brand, "pn_type": part.pn_type, "entity_id": str(part.entity_id), "evidence_quote": part.evidence_quote, "trust_weight": float(part.trust_weight) if part.trust_weight else None}


@router.get("/{part_id}/fitment")
async def get_part_fitment(part_id: str, _: dict = Depends(ReadOnly())):
    async with get_db_session() as session:
        result = await session.execute(select(BatteryPartNumber).where(BatteryPartNumber.id == uuid.UUID(part_id)))
        part = result.scalar_one_or_none()
        if not part:
            raise HTTPException(status_code=404, detail="Part not found")
        vehicles_result = await session.execute(
            select(VehicleVariantCode).where(VehicleVariantCode.entity_id == part.entity_id)
        )
        vehicles = vehicles_result.scalars().all()
        return {"fitment_records": [{"make": v.make, "model": v.model, "variant_code": v.variant_code, "year_from": v.year_from, "year_to": v.year_to} for v in vehicles]}


@router.get("/{part_id}/supersession")
async def get_part_supersession(part_id: str, _: dict = Depends(ReadOnly())):
    async with get_db_session() as session:
        result = await session.execute(select(BatteryPartNumber).where(BatteryPartNumber.id == uuid.UUID(part_id)))
        part = result.scalar_one_or_none()
        if not part:
            raise HTTPException(status_code=404, detail="Part not found")
        return {"current_pn": part.normalized, "superseded_by": None, "supersedes": []}
