from fastapi import APIRouter, Query
from typing import Optional
import structlog
from sqlalchemy import select, text
from app.services.database import get_db_session
from app.api.middleware.auth import ReadOnly

logger = structlog.get_logger()
router = APIRouter(prefix="/api/v1/search", tags=["search"])


@router.get("/cross-reference")
async def cross_reference_search(
    q: str = Query(..., description="Search query"),
    entity_type: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    _: dict = Depends(ReadOnly()),
):
    async with get_db_session() as session:
        try:
            result = await session.execute(
                text("""
                    SELECT * FROM battery_cross_reference_search
                    WHERE canonical_name ILIKE :q
                       OR normalized_primary_part_number ILIKE :q
                       OR brand ILIKE :q
                    ORDER BY occurrence_count DESC, avg_confidence DESC
                    LIMIT :limit OFFSET :offset
                """),
                {"q": f"%{q}%", "limit": page_size, "offset": (page - 1) * page_size},
            )
            rows = result.fetchall()
            return {
                "items": [dict(row._mapping) for row in rows],
                "total": len(rows),
                "query": q,
            }
        except Exception as e:
            logger.error("cross_reference_search_failed", error=str(e))
            return {"items": [], "total": 0, "query": q}


@router.get("/part-number/{pn}")
async def part_number_exact_match(pn: str, _: dict = Depends(ReadOnly())):
    async with get_db_session() as session:
        result = await session.execute(
            text("""
                SELECT e.*, pn.normalized, pn.brand, pn.pn_type
                FROM battery_entity e
                JOIN battery_part_number pn ON pn.entity_id = e.id
                WHERE pn.normalized = :pn
                ORDER BY pn.trust_weight DESC
            """),
            {"pn": pn.strip().upper()},
        )
        rows = result.fetchall()
        return {"exact_matches": [dict(row._mapping) for row in rows], "fuzzy_matches": []}


@router.get("/vehicle/{make}/{model}")
async def vehicle_battery_search(
    make: str,
    model: str,
    year_from: Optional[int] = None,
    year_to: Optional[int] = None,
    _: dict = Depends(ReadOnly()),
):
    async with get_db_session() as session:
        result = await session.execute(
            text("""
                SELECT DISTINCT e.*, v.year_from, v.year_to
                FROM battery_entity e
                JOIN vehicle_variant_code v ON v.entity_id = e.id
                WHERE v.make = :make AND v.model = :model
                  AND (v.year_from <= :year_to OR :year_to IS NULL)
                  AND (v.year_to >= :year_from OR :year_from IS NULL)
                LIMIT 50
            """),
            {"make": make, "model": model, "year_from": year_from or 0, "year_to": year_to or 9999},
        )
        rows = result.fetchall()
        return {"items": [dict(row._mapping) for row in rows]}


@router.get("/superset/{pn}")
async def supersession_chain(pn: str, _: dict = Depends(ReadOnly())):
    async with get_db_session() as session:
        result = await session.execute(
            text("""
                WITH RECURSIVE chain AS (
                    SELECT e.id, e.normalized_primary_part_number, e.canonical_name, 1 as depth
                    FROM battery_entity e
                    JOIN battery_part_number pn ON pn.entity_id = e.id
                    WHERE pn.normalized = :pn AND pn.pn_type = 'service'
                    UNION ALL
                    SELECT e.id, e.normalized_primary_part_number, e.canonical_name, c.depth + 1
                    FROM battery_entity e
                    JOIN battery_part_number pn ON pn.entity_id = e.id
                    JOIN battery_relationship r ON r.child_entity_id = e.id AND r.relationship_type = 'SUPERSEDES'
                    JOIN chain c ON c.id = r.parent_entity_id
                    WHERE c.depth < 10
                )
                SELECT * FROM chain ORDER BY depth
            """),
            {"pn": pn.strip().upper()},
        )
        rows = result.fetchall()
        return {"chain": [dict(row._mapping) for row in rows], "current_pn": pn}
