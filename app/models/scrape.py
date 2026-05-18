from sqlalchemy import Column, String, Integer, Boolean, DateTime, Numeric, ForeignKey, text
from sqlalchemy.dialects.postgresql import UUID, JSON, ARRAY
from sqlalchemy.orm import relationship
from app.models.base import Base
import uuid


class ScrapePlan(Base):
    __tablename__ = 'scrape_plan'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_id = Column(UUID(as_uuid=True), ForeignKey('battery_entity.id'), nullable=False)
    source_url = Column(String(1000), nullable=False)
    source_kind = Column(String(50), nullable=False)
    brand = Column(String(50))
    wave_policy_key = Column(String(100))
    waves_planned = Column(Integer(), server_default='1')
    waves_completed = Column(Integer(), server_default='0')
    quorum_policy = Column(JSON())
    status = Column(String(50), server_default='open')
    completed_at = Column(DateTime())
    created_at = Column(DateTime(), server_default=text('now()'), nullable=False)
    updated_at = Column(DateTime(), server_default=text('now()'), nullable=False)

    attempts = relationship('ScrapeAttempt', back_populates='scrape_plan')
    consensus_results = relationship('ScrapeConsensusResult', back_populates='scrape_plan')


class ScrapeAttempt(Base):
    __tablename__ = 'scrape_attempt'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scrape_plan_id = Column(UUID(as_uuid=True), ForeignKey('scrape_plan.id'), nullable=False)
    wave_number = Column(Integer(), nullable=False)
    fetcher = Column(String(50), nullable=False)
    source_url = Column(String(1000), nullable=False)
    source_kind = Column(String(50), nullable=False)
    scheduled_for = Column(DateTime())
    started_at = Column(DateTime())
    completed_at = Column(DateTime())
    status = Column(String(50), server_default='scheduled')
    blocked = Column(Boolean(), server_default='false')
    block_reason = Column(String(500))
    raw_hash = Column(String(64))
    html_length = Column(Integer())
    visible_text_length = Column(Integer())
    extraction_score = Column(Numeric(3, 2))
    evidence_quote_coverage = Column(Numeric(3, 2))
    payload_json = Column(JSON())
    created_at = Column(DateTime(), server_default=text('now()'), nullable=False)
    updated_at = Column(DateTime(), server_default=text('now()'), nullable=False)

    scrape_plan = relationship('ScrapePlan', back_populates='attempts')


class ScrapeConsensusResult(Base):
    __tablename__ = 'scrape_consensus_result'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scrape_plan_id = Column(UUID(as_uuid=True), ForeignKey('scrape_plan.id'), nullable=False)
    winning_attempt_id = Column(UUID(as_uuid=True), ForeignKey('scrape_attempt.id'))
    attempts_succeeded = Column(Integer(), server_default='0')
    consensus_score = Column(Numeric(3, 2))
    conflicting_fields = Column(ARRAY(String()))
    merged_payload_json = Column(JSON())
    completed_at = Column(DateTime())
    created_at = Column(DateTime(), server_default=text('now()'), nullable=False)
    updated_at = Column(DateTime(), server_default=text('now()'), nullable=False)

    scrape_plan = relationship('ScrapePlan', back_populates='consensus_results')
