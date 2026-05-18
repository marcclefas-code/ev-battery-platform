from sqlalchemy import Column, String, Integer, DateTime, Enum as SAEnum, Numeric, ForeignKey, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.models.base import Base
import uuid


class BatteryRelationship(Base):
    __tablename__ = 'battery_relationship'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    parent_entity_id = Column(UUID(as_uuid=True), ForeignKey('battery_entity.id'), nullable=False)
    child_entity_id = Column(UUID(as_uuid=True), ForeignKey('battery_entity.id'))
    relationship_type = Column(SAEnum('CONTAINS_MODULE', 'CONTAINS_CELL', 'USES_CONTROLLER', 'FITMENT_VEHICLE', 'SUPERSEDES', 'CROSS_REF_AFTERMARKET', 'CROSS_REF_OEM', name='relationship_type', create_type=False), nullable=False)
    sequence_position = Column(Integer())
    confidence = Column(Numeric(3, 2), server_default='0.50')
    source_url = Column(String(1000))
    evidence_quote = Column(String(2000))
    trust_weight = Column(Numeric(3, 2), server_default='0.50')
    status = Column(SAEnum('candidate', 'confirmed', 'rejected', name='relationship_status', create_type=False), server_default='candidate')
    created_at = Column(DateTime(), server_default=text('now()'), nullable=False)
    updated_at = Column(DateTime(), server_default=text('now()'), nullable=False)

    parent_entity = relationship('BatteryEntity', foreign_keys=[parent_entity_id], back_populates='relationships_as_parent')
    child_entity = relationship('BatteryEntity', foreign_keys=[child_entity_id], back_populates='relationships_as_child')
