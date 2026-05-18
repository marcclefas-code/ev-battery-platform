from sqlalchemy import Column, String, Integer, DateTime, Numeric, ForeignKey, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.models.base import Base
import uuid


class VehicleVariantCode(Base):
    __tablename__ = 'vehicle_variant_code'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_id = Column(UUID(as_uuid=True), ForeignKey('battery_entity.id'), nullable=False)
    make = Column(String(50), nullable=False)
    model = Column(String(100), nullable=False)
    variant_code = Column(String(50))
    year_from = Column(Integer())
    year_to = Column(Integer())
    engine_code = Column(String(50))
    source_url = Column(String(1000))
    trust_weight = Column(Numeric(3, 2), server_default='0.50')
    created_at = Column(DateTime(), server_default=text('now()'), nullable=False)
    updated_at = Column(DateTime(), server_default=text('now()'), nullable=False)

    entity = relationship('BatteryEntity', back_populates='vehicle_variant_codes')
