from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
import structlog
import uuid
from app.services.database import get_db_session
from app.models.relationship import BatteryRelationship
from app.models.entity import BatteryEntity
from app.models.part_number import BatteryPartNumber
from sqlalchemy import select
from app.api.middleware.auth import ReadOnly, OperatorOrAdmin

logger = structlog.get_logger()
router = APIRouter(prefix="/api/v1/xref", tags=["xref"])


class CrossReferenceRequest(BaseModel):
    source_pn: str
    source_brand: str
    target_brand: str
    target_pn: str = None
    relationship_type: str = "CROSS_REF_AFTERMARKET"


@router.post("/")
async def create_cross_reference(req: CrossReferenceRequest, _: dict = Depends(OperatorOrAdmin())):
    xref_id = str(uuid.uuid4())
    logger.info("xref_created", xref_id=xref_id, source=req.source_pn, target_brand=req.target_brand)
    return {"xref_id": xref_id, "status": "pending", "source_pn": req.source_pn, "target_brand": req.target_brand}


@router.get("/")
async def list_cross_references(page: int = 1, page_size: int = 50, _: dict = Depends(ReadOnly())):
    async with get_db_session() as session:
        result = await session.execute(
            select(BatteryRelationship)
            .where(BatteryRelationship.relationship_type.in_(["CROSS_REF_AFTERMARKET", "CROSS_REF_OEM"]))
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        xrefs = result.scalars().all()
        return {"items": [{"id": str(x.id), "parent_entity_id": str(x.parent_entity_id), "child_entity_id": str(x.child_entity_id), "relationship_type": x.relationship_type, "confidence": float(x.confidence) if x.confidence else None} for x in xrefs]}


@router.get("/{xref_id}")
async def get_cross_reference(xref_id: str, _: dict = Depends(ReadOnly())):
    raise HTTPException(status_code=404, detail="Cross-reference not found")
