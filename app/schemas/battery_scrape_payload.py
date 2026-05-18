from pydantic import BaseModel, Field
from typing import Optional, Any


class MetaInfo(BaseModel):
    fetcher: str
    wave: int
    source_url: str
    page_title: Optional[str] = ""
    extraction_score: Optional[float] = None


class PartNumberItem(BaseModel):
    raw: str
    normalized: str
    brand: str
    pn_type: str = "service"
    evidence_quote: Optional[str] = None
    source_url: Optional[str] = None


class PropertyItem(BaseModel):
    value: Any
    unit: Optional[str] = None
    evidence_quote: Optional[str] = None
    confidence: float = 0.5


class RelationshipItem(BaseModel):
    type: str
    target_pn_or_id: str
    evidence_quote: Optional[str] = None
    confidence: float = 0.5


class VehicleItem(BaseModel):
    make: str
    model: str
    variant_code: Optional[str] = None
    year_from: Optional[int] = None
    year_to: Optional[int] = None
    engine_code: Optional[str] = None
    evidence_quote: Optional[str] = None


class BatteryScrapePayload(BaseModel):
    _meta: MetaInfo
    part_numbers: list[PartNumberItem] = Field(default_factory=list)
    properties: dict[str, PropertyItem] = Field(default_factory=dict)
    relationships: list[RelationshipItem] = Field(default_factory=list)
    vehicles: list[VehicleItem] = Field(default_factory=list)
