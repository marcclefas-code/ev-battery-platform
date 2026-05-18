from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
import uuid
from app.models.scrape import ScrapePlan, ScrapeAttempt, ScrapeConsensusResult
import structlog

logger = structlog.get_logger()


class ScrapePlanRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, entity_id: uuid.UUID, source_url: str, source_kind: str, brand: str = None, wave_policy_key: str = None, waves_planned: int = 1) -> ScrapePlan:
        plan = ScrapePlan(
            id=uuid.uuid4(),
            entity_id=entity_id,
            source_url=source_url,
            source_kind=source_kind,
            brand=brand,
            wave_policy_key=wave_policy_key,
            waves_planned=waves_planned,
            status='open',
        )
        self.session.add(plan)
        await self.session.flush()
        return plan

    async def get_by_id(self, plan_id: uuid.UUID) -> Optional[ScrapePlan]:
        result = await self.session.execute(
            select(ScrapePlan).where(ScrapePlan.id == plan_id)
        )
        return result.scalar_one_or_none()

    async def update_status(self, plan_id: uuid.UUID, status: str, waves_completed: int = None):
        plan = await self.get_by_id(plan_id)
        if plan:
            plan.status = status
            if waves_completed is not None:
                plan.waves_completed = waves_completed
            if status == 'completed':
                from datetime import datetime
                plan.completed_at = datetime.utcnow()
            await self.session.flush()

    async def create_attempt(self, scrape_plan_id: uuid.UUID, wave_number: int, fetcher: str, source_url: str, source_kind: str, scheduled_for=None) -> ScrapeAttempt:
        attempt = ScrapeAttempt(
            id=uuid.uuid4(),
            scrape_plan_id=scrape_plan_id,
            wave_number=wave_number,
            fetcher=fetcher,
            source_url=source_url,
            source_kind=source_kind,
            scheduled_for=scheduled_for,
            status='scheduled',
        )
        self.session.add(attempt)
        await self.session.flush()
        return attempt

    async def update_attempt_result(self, attempt_id: uuid.UUID, raw_hash: str = None, html_length: int = None, visible_text_length: int = None, extraction_score: float = None, payload_json: dict = None, status: str = 'success'):
        result = await self.session.execute(
            select(ScrapeAttempt).where(ScrapeAttempt.id == attempt_id)
        )
        attempt = result.scalar_one_or_none()
        if attempt:
            from datetime import datetime
            attempt.status = status
            attempt.started_at = datetime.utcnow()
            attempt.completed_at = datetime.utcnow()
            if raw_hash:
                attempt.raw_hash = raw_hash
            if html_length is not None:
                attempt.html_length = html_length
            if visible_text_length is not None:
                attempt.visible_text_length = visible_text_length
            if extraction_score is not None:
                attempt.extraction_score = extraction_score
            if payload_json:
                attempt.payload_json = payload_json
            await self.session.flush()
        return attempt

    async def create_consensus_result(self, scrape_plan_id: uuid.UUID, winning_attempt_id: uuid.UUID, attempts_succeeded: int, consensus_score: float, conflicting_fields: list, merged_payload_json: dict) -> ScrapeConsensusResult:
        result = ScrapeConsensusResult(
            id=uuid.uuid4(),
            scrape_plan_id=scrape_plan_id,
            winning_attempt_id=winning_attempt_id,
            attempts_succeeded=attempts_succeeded,
            consensus_score=consensus_score,
            conflicting_fields=conflicting_fields,
            merged_payload_json=merged_payload_json,
        )
        self.session.add(result)
        await self.session.flush()
        return result

    async def get_attempts_for_plan(self, plan_id: uuid.UUID) -> list[ScrapeAttempt]:
        result = await self.session.execute(
            select(ScrapeAttempt)
            .where(ScrapeAttempt.scrape_plan_id == plan_id)
            .order_by(ScrapeAttempt.wave_number)
        )
        return list(result.scalars().all())
