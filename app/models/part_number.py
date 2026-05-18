from sqlalchemy import Column, String, Integer, DateTime, Enum as SAEnum, Numeric, ForeignKey, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.models.base import Base
import uuid


class BatteryPartNumber(Base):
    __tablename__ = 'battery_part_number'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_id = Column(UUID(as_uuid=True), ForeignKey('battery_entity.id'), nullable=False)
    raw = Column(String(200), nullable=False)
    normalized = Column(String(100), nullable=False)
    brand = Column(String(50), nullable=False)
    pn_type = Column(SAEnum('service', 'superseded', 'etn', 'alias', 'oem_cross', 'aftermarket', name='pn_type', create_type=False), server_default='service')
    source_url = Column(String(1000))
    evidence_quote = Column(String(1000))
    trust_weight = Column(Numeric(3, 2), server_default='0.50')
    created_at = Column(DateTime(), server_default=text('now()'), nullable=False)
    updated_at = Column(DateTime(), server_default=text('now()'), nullable=False)

    entity = relationship('BatteryEntity', back_populates='part_numbers')
