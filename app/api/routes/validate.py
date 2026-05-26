from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
import structlog
from app.services.ev_battery_validator import EVBatteryValidator

logger = structlog.get_logger()
router = APIRouter(prefix="/api/v1/validate", tags=["validate"])

validator = EVBatteryValidator()


class PartValidationRequest(BaseModel):
    normalized: str
    brand: Optional[str] = None
    pn_type: Optional[str] = None
    name: Optional[str] = None
    source_url: Optional[str] = None
    evidence_quote: Optional[str] = None
    use_ai: bool = True


class PartValidationResponse(BaseModel):
    is_valid: bool
    confidence: float
    reason: str
    warnings: list[str]
    validated_by: str


@router.post("/part", response_model=PartValidationResponse)
async def validate_part(req: PartValidationRequest):
    """
    Validate if a part number is an EV battery component.
    Uses rules-based validation first, then AI (DeepSeek) if needed.
    """
    part_data = {
        "normalized": req.normalized,
        "brand": req.brand,
        "pn_type": req.pn_type,
        "name": req.name,
        "source_url": req.source_url,
        "evidence_quote": req.evidence_quote,
    }

    if req.use_ai:
        result = await validator.validate_part(part_data)
        result["validated_by"] = "rules+ai" if "AI" not in result.get("warnings", []) else "ai_only"
    else:
        result = validator.validate_rules_based(part_data)
        result["validated_by"] = "rules_only"

    return PartValidationResponse(**result)


@router.post("/batch", response_model=list[PartValidationResponse])
async def validate_batch(requests: list[PartValidationRequest], use_ai: bool = True):
    """
    Validate multiple parts in batch.
    """
    results = []
    for req in requests:
        part_data = {
            "normalized": req.normalized,
            "brand": req.brand,
            "pn_type": req.pn_type,
            "name": req.name,
            "source_url": req.source_url,
            "evidence_quote": req.evidence_quote,
        }

        if use_ai:
            result = await validator.validate_part(part_data)
            result["validated_by"] = "rules+ai"
        else:
            result = validator.validate_rules_based(part_data)
            result["validated_by"] = "rules_only"

        results.append(PartValidationResponse(**result))

    return results
