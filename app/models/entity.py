from sqlalchemy import Column, String, Integer, DateTime, Enum as SAEnum, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.models.base import Base
import uuid


class BatteryEntity(Base):
    __tablename__ = 'battery_entity'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_type = Column(SAEnum('pack', 'hv_module', 'hv_cell', 'aux_12v', 'aux_48v_mhev', name='entity_type', create_type=False), nullable=False)
    canonical_name = Column(String(500))
    normalized_primary_part_number = Column(String(100), unique=True)
    occurrence_count = Column(Integer(), server_default='1')
    status = Column(SAEnum('candidate', 'confirmed', 'deprecated', name='entity_status', create_type=False), server_default='candidate')
    created_at = Column(DateTime(), server_default=text('now()'), nullable=False)
    updated_at = Column(DateTime(), server_default=text('now()'), nullable=False)

    part_numbers = relationship('BatteryPartNumber', back_populates='entity')
    property_statements = relationship('PropertyStatement', back_populates='entity')
    relationships_as_parent = relationship('BatteryRelationship', foreign_keys='BatteryRelationship.parent_entity_id', back_populates='parent_entity')
    relationships_as_child = relationship('BatteryRelationship', foreign_keys='BatteryRelationship.child_entity_id', back_populates='child_entity')
    vehicle_variant_codes = relationship('VehicleVariantCode', back_populates='entity')
