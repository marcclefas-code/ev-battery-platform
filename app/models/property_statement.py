from sqlalchemy import Column, String, Integer, DateTime, Enum as SAEnum, Numeric, ForeignKey, text
from sqlalchemy.dialects.postgresql import UUID, JSON
from sqlalchemy.orm import relationship
from app.models.base import Base
import uuid


class PropertyStatement(Base):
    __tablename__ = 'property_statement'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_id = Column(UUID(as_uuid=True), ForeignKey('battery_entity.id'), nullable=False)
    code = Column(String(50), ForeignKey('property_definition.code'), nullable=False)
    value = Column(JSON(), nullable=False)
    unit = Column(String(20))
    source_url = Column(String(1000))
    evidence_quote = Column(String(2000))
    trust_weight = Column(Numeric(3, 2), server_default='0.50')
    confidence = Column(Numeric(3, 2), server_default='0.50')
    model_used = Column(String(100))
    mayan_document_id = Column(String(100))
    status = Column(SAEnum('candidate', 'confirmed', 'rejected', name='property_status', create_type=False), server_default='candidate')
    alternative_values = Column(JSON())
    created_at = Column(DateTime(), server_default=text('now()'), nullable=False)
    updated_at = Column(DateTime(), server_default=text('now()'), nullable=False)

    entity = relationship('BatteryEntity', back_populates='property_statements')
