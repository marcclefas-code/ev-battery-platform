from fastapi import APIRouter, HTTPException
import structlog

logger = structlog.get_logger()
router = APIRouter(prefix="/api/v1/reviews", tags=["reviews"])


@router.get("/")
async def list_review_tasks(status: str = "open"):
    return []


@router.get("/{task_id}")
async def get_review_task(task_id: str):
    raise HTTPException(status_code=404, detail="Review task not found")


@router.patch("/{task_id}")
async def update_review_task(task_id: str, body: dict):
    logger.info("review_task_updated", task_id=task_id)
    return {"task_id": task_id, "status": "updated"}
