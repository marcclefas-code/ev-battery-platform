from fastapi import APIRouter, HTTPException
import structlog

logger = structlog.get_logger()
router = APIRouter(prefix="/api/v1/waves", tags=["waves"])


@router.get("/{plan_id}")
async def get_wave_status(plan_id: str):
    return {"plan_id": plan_id, "waves": []}


@router.post("/{plan_id}/wave/{wave_num}")
async def trigger_wave(plan_id: str, wave_num: int):
    logger.info("wave_triggered", plan_id=plan_id, wave=wave_num)
    return {"plan_id": plan_id, "wave": wave_num, "status": "triggered"}


@router.get("/{plan_id}/wave/{wave_num}/attempts")
async def get_wave_attempts(plan_id: str, wave_num: int):
    return []
