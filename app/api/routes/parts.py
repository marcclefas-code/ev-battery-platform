from fastapi import APIRouter, HTTPException
import structlog

logger = structlog.get_logger()
router = APIRouter(prefix="/api/v1/parts", tags=["parts"])


@router.get("/")
async def list_parts():
    return []


@router.get("/{part_id}")
async def get_part(part_id: str):
    raise HTTPException(status_code=404, detail="Part not found")


@router.get("/{part_id}/fitment")
async def get_part_fitment(part_id: str):
    return {"fitment_records": []}


@router.get("/{part_id}/supersession")
async def get_part_supersession(part_id: str):
    return {"current_pn": part_id, "superseded_by": None, "supersedes": []}
