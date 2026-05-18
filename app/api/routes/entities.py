from fastapi import APIRouter, HTTPException, Query
from typing import Optional
import structlog

logger = structlog.get_logger()
router = APIRouter(prefix="/api/v1/entities", tags=["entities"])


@router.get("/")
async def list_entities(
    entity_type: Optional[str] = None,
    brand: Optional[str] = None,
    page: int = 1,
    page_size: int = 50,
):
    logger.info("entities_listed", entity_type=entity_type, brand=brand, page=page)
    return {"items": [], "total": 0, "page": page, "page_size": page_size}


@router.get("/{entity_id}")
async def get_entity(entity_id: str):
    logger.info("entity_fetched", entity_id=entity_id)
    raise HTTPException(status_code=404, detail="Entity not found")


@router.get("/{entity_id}/properties")
async def get_entity_properties(entity_id: str):
    return []


@router.get("/{entity_id}/cross-reference")
async def get_entity_cross_reference(entity_id: str):
    return {"items": []}


@router.get("/by-part-number/{pn}")
async def get_entity_by_part_number(pn: str):
    logger.info("entity_by_pn", pn=pn)
    raise HTTPException(status_code=404, detail="Entity not found")
