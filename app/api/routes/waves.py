from fastapi import APIRouter
import structlog
from app.api.middleware.auth import ReadOnly, OperatorOrAdmin
import uuid
from app.services.database import get_db_session
from app.services.repositories.scrape_plan_repo import ScrapePlanRepository
from app.services.enrichment_service import EnrichmentService
import asyncio

logger = structlog.get_logger()
router = APIRouter(prefix="/api/v1/waves", tags=["waves"])


@router.get("/{plan_id}")
async def get_wave_status(plan_id: str, _: dict = Depends(ReadOnly())):
    async with get_db_session() as session:
        repo = ScrapePlanRepository(session)
        attempts = await repo.get_attempts_for_plan(uuid.UUID(plan_id))
        return {
            "plan_id": plan_id,
            "waves": [
                {
                    "wave_number": a.wave_number,
                    "fetcher": a.fetcher,
                    "status": a.status,
                    "started_at": a.started_at.isoformat() if a.started_at else None,
                    "completed_at": a.completed_at.isoformat() if a.completed_at else None,
                    "extraction_score": float(a.extraction_score) if a.extraction_score else None,
                }
                for a in attempts
            ],
        }


@router.post("/{plan_id}/wave/{wave_num}")
async def trigger_wave(plan_id: str, wave_num: int, _: dict = Depends(OperatorOrAdmin())):
    logger.info("wave_triggered", plan_id=plan_id, wave=wave_num)
    return {"plan_id": plan_id, "wave": wave_num, "status": "triggered"}


@router.get("/{plan_id}/wave/{wave_num}/attempts")
async def get_wave_attempts(plan_id: str, wave_num: int, _: dict = Depends(ReadOnly())):
    async with get_db_session() as session:
        repo = ScrapePlanRepository(session)
        all_attempts = await repo.get_attempts_for_plan(uuid.UUID(plan_id))
        filtered = [a for a in all_attempts if a.wave_number == wave_num]
        return {
            "plan_id": plan_id,
            "wave": wave_num,
            "attempts": [
                {"id": str(a.id), "fetcher": a.fetcher, "status": a.status, "raw_hash": a.raw_hash, "extraction_score": float(a.extraction_score) if a.extraction_score else None}
                for a in filtered
            ],
        }
