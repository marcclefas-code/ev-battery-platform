from fastapi import APIRouter, Query
from typing import Optional
import structlog

logger = structlog.get_logger()
router = APIRouter(prefix="/api/v1/search", tags=["search"])


@router.get("/cross-reference")
async def cross_reference_search(
    q: str = Query(..., description="Search query (part number, vehicle, or battery type)"),
    entity_type: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
):
    logger.info("cross_reference_search", q=q, entity_type=entity_type)
    return {"items": [], "total": 0, "query": q}


@router.get("/part-number/{pn}")
async def part_number_exact_match(pn: str):
    logger.info("pn_exact_match", pn=pn)
    return {"exact_matches": [], "fuzzy_matches": []}


@router.get("/vehicle/{make}/{model}")
async def vehicle_battery_search(
    make: str,
    model: str,
    year_from: Optional[int] = None,
    year_to: Optional[int] = None,
):
    logger.info("vehicle_battery_search", make=make, model=model)
    return {"items": []}


@router.get("/superset/{pn}")
async def supersession_chain(pn: str):
    logger.info("supersession_chain", pn=pn)
    return {"chain": [], "current_pn": pn}
