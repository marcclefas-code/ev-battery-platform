from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel
from typing import Optional
import uuid
import structlog
from app.services.database import get_db_session
from app.services.repositories.scrape_plan_repo import ScrapePlanRepository
from app.services.enrichment_service import EnrichmentService
from app.services.fetcher_registry import FetcherRegistry
from app.services.extractor import ExtractionEngine
from app.services.consensus_merger import ConsensusMerger
from app.schemas.battery_scrape_payload import BatteryScrapePayload
from app.api.middleware.auth import read_only, operator_or_admin
from app.brand_adapters.porsche_adapter import PorscheAdapter
import os
import asyncio

logger = structlog.get_logger()
router = APIRouter(prefix="/api/v1/scrape", tags=["scrape"])


class ScrapeRequest(BaseModel):
    entity_id: Optional[str] = None
    part_number: str
    brand: str = "porsche"
    source_url: Optional[str] = None
    waves: int = 3


class ScrapeResponse(BaseModel):
    plan_id: str
    status: str
    waves_completed: int = 0


@router.post("/", response_model=ScrapeResponse)
async def create_scrape_plan(req: ScrapeRequest, _: dict = Depends(operator_or_admin)):
    async with get_db_session() as session:
        plan_repo = ScrapePlanRepository(session)
        entity_id = uuid.UUID(req.entity_id) if req.entity_id else uuid.uuid4()
        source_url = req.source_url or f"https://www.teile.com/Porsche/search/?q={req.part_number}"
        plan = await plan_repo.create(
            entity_id=entity_id,
            source_url=source_url,
            source_kind="dealer_catalog",
            brand=req.brand,
            waves_planned=req.waves,
        )
        logger.info("scrape_plan_created", plan_id=str(plan.id), part_number=req.part_number)
        return ScrapeResponse(plan_id=str(plan.id), status="open", waves_completed=0)


@router.get("/{plan_id}")
async def get_scrape_plan(plan_id: str, _: dict = Depends(read_only)):
    async with get_db_session() as session:
        plan_repo = ScrapePlanRepository(session)
        plan = await plan_repo.get_by_id(uuid.UUID(plan_id))
        if not plan:
            raise HTTPException(status_code=404, detail="Scrape plan not found")
        return {
            "plan_id": str(plan.id),
            "entity_id": str(plan.entity_id),
            "source_url": plan.source_url,
            "brand": plan.brand,
            "status": plan.status,
            "waves_planned": plan.waves_planned,
            "waves_completed": plan.waves_completed,
            "created_at": plan.created_at.isoformat() if plan.created_at else None,
        }


@router.get("/{plan_id}/attempts")
async def get_scrape_attempts(plan_id: str, _: dict = Depends(read_only)):
    async with get_db_session() as session:
        plan_repo = ScrapePlanRepository(session)
        attempts = await plan_repo.get_attempts_for_plan(uuid.UUID(plan_id))
        return {
            "plan_id": plan_id,
            "attempts": [
                {
                    "id": str(a.id),
                    "wave_number": a.wave_number,
                    "fetcher": a.fetcher,
                    "status": a.status,
                    "raw_hash": a.raw_hash,
                    "html_length": a.html_length,
                    "extraction_score": float(a.extraction_score) if a.extraction_score else None,
                    "started_at": a.started_at.isoformat() if a.started_at else None,
                    "completed_at": a.completed_at.isoformat() if a.completed_at else None,
                }
                for a in attempts
            ],
        }
