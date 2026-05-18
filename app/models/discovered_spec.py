from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, text
from sqlalchemy.dialects.postgresql import UUID
from app.models.base import Base
import uuid


class DiscoveredSpec(Base):
    __tablename__ = 'discovered_spec'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    normalized_pn = Column(String(100), nullable=False)
    raw_context = Column(String())
    occurrence_count = Column(Integer(), server_default='1')
    first_seen = Column(DateTime(), server_default=text('now()'), nullable=False)
    last_seen = Column(DateTime(), server_default=text('now()'), nullable=False)
    promoted_to_entity_id = Column(UUID(as_uuid=True))
