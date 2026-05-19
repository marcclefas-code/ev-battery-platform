from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Optional
import uuid
import structlog
from app.services.database import get_db_session
from app.services.repositories.battery_entity_repo import BatteryEntityRepository
from app.api.middleware.auth import read_only, operator_or_admin

logger = structlog.get_logger()
router = APIRouter(prefix="/api/v1/entities", tags=["entities"])


@router.get("/")
async def list_entities(
    entity_type: Optional[str] = None,
    brand: Optional[str] = None,
    page: int = 1,
    page_size: int = 50,
    _: dict = Depends(read_only),
):
    async with get_db_session() as session:
        repo = BatteryEntityRepository(session)
        entities, total = await repo.list_(entity_type=entity_type, brand=brand, page=page, page_size=page_size)
        return {
            "items": [
                {
                    "id": str(e.id),
                    "entity_type": e.entity_type,
                    "canonical_name": e.canonical_name,
                    "normalized_primary_part_number": e.normalized_primary_part_number,
                    "status": e.status,
                    "occurrence_count": e.occurrence_count,
                    "part_numbers": [{"normalized": pn.normalized, "brand": pn.brand, "pn_type": pn.pn_type} for pn in e.part_numbers],
                    "updated_at": e.updated_at.isoformat() if e.updated_at else None,
                }
                for e in entities
            ],
            "total": total,
            "page": page,
            "page_size": page_size,
        }


@router.get("/{entity_id}")
async def get_entity(entity_id: str, _: dict = Depends(read_only)):
    async with get_db_session() as session:
        repo = BatteryEntityRepository(session)
        entity = await repo.get_by_id(uuid.UUID(entity_id))
        if not entity:
            raise HTTPException(status_code=404, detail="Entity not found")
        return {
            "id": str(entity.id),
            "entity_type": entity.entity_type,
            "canonical_name": entity.canonical_name,
            "normalized_primary_part_number": entity.normalized_primary_part_number,
            "status": entity.status,
            "occurrence_count": entity.occurrence_count,
            "part_numbers": [
                {"id": str(pn.id), "raw": pn.raw, "normalized": pn.normalized, "brand": pn.brand, "pn_type": pn.pn_type, "evidence_quote": pn.evidence_quote, "trust_weight": float(pn.trust_weight) if pn.trust_weight else None}
                for pn in entity.part_numbers
            ],
            "properties": [
                {"code": ps.code, "value": ps.value, "unit": ps.unit, "confidence": float(ps.confidence) if ps.confidence else None, "status": ps.status}
                for ps in entity.property_statements
            ],
            "vehicles": [
                {"make": vv.make, "model": vv.model, "variant_code": vv.variant_code, "year_from": vv.year_from, "year_to": vv.year_to}
                for vv in entity.vehicle_variant_codes
            ],
        }


@router.get("/{entity_id}/properties")
async def get_entity_properties(entity_id: str, _: dict = Depends(read_only)):
    async with get_db_session() as session:
        repo = BatteryEntityRepository(session)
        entity = await repo.get_by_id(uuid.UUID(entity_id))
        if not entity:
            raise HTTPException(status_code=404, detail="Entity not found")
        return {
            "entity_id": entity_id,
            "properties": [
                {"code": ps.code, "value": ps.value, "unit": ps.unit, "evidence_quote": ps.evidence_quote, "confidence": float(ps.confidence) if ps.confidence else None, "status": ps.status}
                for ps in entity.property_statements
            ],
        }


@router.get("/{entity_id}/cross-reference")
async def get_entity_cross_reference(entity_id: str, _: dict = Depends(read_only)):
    async with get_db_session() as session:
        repo = BatteryEntityRepository(session)
        entity = await repo.get_by_id(uuid.UUID(entity_id))
        if not entity:
            raise HTTPException(status_code=404, detail="Entity not found")
        return {
            "entity_id": entity_id,
            "cross_references": [
                {"normalized": pn.normalized, "brand": pn.brand, "pn_type": pn.pn_type}
                for pn in entity.part_numbers if pn.pn_type in ("oem_cross", "aftermarket", "alias")
            ],
        }


@router.get("/by-part-number/{pn}")
async def get_entity_by_part_number(pn: str, _: dict = Depends(read_only)):
    async with get_db_session() as session:
        repo = BatteryEntityRepository(session)
        entity = await repo.get_by_normalized_pn(pn.strip().upper())
        if not entity:
            raise HTTPException(status_code=404, detail="Entity not found")
        return {
            "id": str(entity.id),
            "entity_type": entity.entity_type,
            "normalized_primary_part_number": entity.normalized_primary_part_number,
            "status": entity.status,
        }


@router.post("/", status_code=201)
async def create_entity(body: dict, _: dict = Depends(operator_or_admin)):
    async with get_db_session() as session:
        repo = BatteryEntityRepository(session)
        entity, created = await repo.find_or_create_by_pn(
            normalized_pn=body.get("normalized_primary_part_number", ""),
            entity_type=body.get("entity_type", "pack"),
        )
        if not created:
            raise HTTPException(status_code=409, detail="Entity already exists")
        return {"id": str(entity.id), "status": "created"}
