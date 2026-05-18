from sqlalchemy import Column, String, DateTime, Enum as SAEnum, ForeignKey, text
from sqlalchemy.dialects.postgresql import UUID
from app.models.base import Base
import uuid


class EnrichmentReviewTask(Base):
    __tablename__ = 'enrichment_review_task'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_id = Column(UUID(as_uuid=True), ForeignKey('battery_entity.id'), nullable=False)
    flag_code = Column(String(100), nullable=False)
    severity = Column(SAEnum('low', 'medium', 'high', 'critical', name='task_severity', create_type=False), server_default='medium')
    description = Column(String(1000), nullable=False)
    status = Column(SAEnum('open', 'in_review', 'resolved', 'dismissed', name='task_status', create_type=False), server_default='open')
    assigned_to = Column(String(100))
    resolved_at = Column(DateTime())
    created_at = Column(DateTime(), server_default=text('now()'), nullable=False)
    updated_at = Column(DateTime(), server_default=text('now()'), nullable=False)
