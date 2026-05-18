from sqlalchemy import Column, String, Integer, DateTime, Numeric, ForeignKey, text
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from app.models.base import Base
import uuid


class ScrapeLog(Base):
    __tablename__ = 'scrape_log'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_url = Column(String(1000), nullable=False)
    source_kind = Column(String(50), nullable=False)
    extraction_score = Column(Numeric(3, 2))
    trust_weight = Column(Numeric(3, 2))
    status = Column(String(50), nullable=False)
    review_flags = Column(ARRAY(String()))
    model_used = Column(String(100))
    processing_ms = Column(Integer())
    entity_id = Column(UUID(as_uuid=True), ForeignKey('battery_entity.id'))
    mayan_document_id = Column(String(100))
    created_at = Column(DateTime(), server_default=text('now()'), nullable=False)
    updated_at = Column(DateTime(), server_default=text('now()'), nullable=False)
