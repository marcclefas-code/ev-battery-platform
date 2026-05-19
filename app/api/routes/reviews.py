from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
import structlog
from sqlalchemy import select
from app.services.database import get_db_session
from app.models.enrichment_review_task import EnrichmentReviewTask
from app.api.middleware.auth import read_only, operator_or_admin
from datetime import datetime
import uuid

logger = structlog.get_logger()
router = APIRouter(prefix="/api/v1/reviews", tags=["reviews"])


class UpdateReviewTask(BaseModel):
    status: str
    assigned_to: str = None


@router.get("/")
async def list_review_tasks(status: str = "open", _: dict = Depends(read_only)):
    async with get_db_session() as session:
        result = await session.execute(
            select(EnrichmentReviewTask)
            .where(EnrichmentReviewTask.status == status)
            .order_by(EnrichmentReviewTask.severity.desc())
            .limit(100)
        )
        tasks = result.scalars().all()
        return {
            "tasks": [
                {"id": str(t.id), "entity_id": str(t.entity_id), "flag_code": t.flag_code, "severity": t.severity, "description": t.description, "status": t.status}
                for t in tasks
            ]
        }


@router.get("/{task_id}")
async def get_review_task(task_id: str, _: dict = Depends(read_only)):
    async with get_db_session() as session:
        result = await session.execute(select(EnrichmentReviewTask).where(EnrichmentReviewTask.id == uuid.UUID(task_id)))
        task = result.scalar_one_or_none()
        if not task:
            raise HTTPException(status_code=404, detail="Review task not found")
        return {"id": str(task.id), "entity_id": str(task.entity_id), "flag_code": task.flag_code, "severity": task.severity, "description": task.description, "status": task.status, "assigned_to": task.assigned_to}


@router.patch("/{task_id}")
async def update_review_task(task_id: str, body: UpdateReviewTask, _: dict = Depends(operator_or_admin)):
    async with get_db_session() as session:
        result = await session.execute(select(EnrichmentReviewTask).where(EnrichmentReviewTask.id == uuid.UUID(task_id)))
        task = result.scalar_one_or_none()
        if not task:
            raise HTTPException(status_code=404, detail="Review task not found")
        task.status = body.status
        if body.assigned_to:
            task.assigned_to = body.assigned_to
        if body.status in ("resolved", "dismissed"):
            task.resolved_at = datetime.utcnow()
        logger.info("review_task_updated", task_id=task_id, status=body.status)
        return {"task_id": task_id, "status": body.status}
