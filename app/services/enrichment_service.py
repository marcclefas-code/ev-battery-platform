from typing import Optional
import uuid
import structlog
from app.services.database import get_db_session
from app.services.repositories.battery_entity_repo import BatteryEntityRepository
from app.services.repositories.scrape_plan_repo import ScrapePlanRepository
from app.services.consensus_merger import ConsensusMerger
from app.services.ev_battery_validator import EVBatteryValidator
from app.schemas.battery_scrape_payload import BatteryScrapePayload

logger = structlog.get_logger()
validator = EVBatteryValidator()


class EnrichmentService:
    def __init__(self):
        self.merger = ConsensusMerger()

    async def create_scrape_plan(self, entity_id: uuid.UUID, source_url: str, source_kind: str, brand: str = None, waves_planned: int = 3) -> uuid.UUID:
        async with get_db_session() as session:
            repo = ScrapePlanRepository(session)
            plan = await repo.create(
                entity_id=entity_id,
                source_url=source_url,
                source_kind=source_kind,
                brand=brand,
                waves_planned=waves_planned,
            )
            return plan.id

    async def record_attempt(self, plan_id: uuid.UUID, wave_number: int, fetcher: str, source_url: str, source_kind: str) -> uuid.UUID:
        async with get_db_session() as session:
            repo = ScrapePlanRepository(session)
            attempt = await repo.create_attempt(
                scrape_plan_id=plan_id,
                wave_number=wave_number,
                fetcher=fetcher,
                source_url=source_url,
                source_kind=source_kind,
            )
            return attempt.id

    async def finalize_attempt(self, attempt_id: uuid.UUID, raw_hash: str, html_length: int, visible_text_length: int, extraction_score: float, payload: BatteryScrapePayload, status: str = "success"):
        async with get_db_session() as session:
            repo = ScrapePlanRepository(session)
            await repo.update_attempt_result(
                attempt_id=attempt_id,
                raw_hash=raw_hash,
                html_length=html_length,
                visible_text_length=visible_text_length,
                extraction_score=extraction_score,
                payload_json=payload.model_dump() if payload else None,
                status=status,
            )

    async def merge_and_record_consensus(self, plan_id: uuid.UUID, payloads: list[BatteryScrapePayload], winning_attempt_id: Optional[uuid.UUID] = None):
        merge_result = await self.merger.merge_payloads(payloads)

        async with get_db_session() as session:
            plan_repo = ScrapePlanRepository(session)
            await plan_repo.update_status(plan_id, "completed", waves_completed=max(p.wave_number for p in payloads if p) + 1)

            if merge_result["merged"]:
                await plan_repo.create_consensus_result(
                    scrape_plan_id=plan_id,
                    winning_attempt_id=winning_attempt_id or uuid.uuid4(),
                    attempts_succeeded=merge_result["attempts_succeeded"],
                    consensus_score=merge_result["score"],
                    conflicting_fields=[c["field"] for c in merge_result["conflicts"]],
                    merged_payload_json=merge_result["merged"],
                )

        self.logger.info(
            "consensus_recorded",
            plan_id=str(plan_id),
            score=merge_result["score"],
            conflicts=len(merge_result["conflicts"]),
        )
        return merge_result

    async def persist_merged_payload(self, entity_id: uuid.UUID, merged_payload: dict):
        async with get_db_session() as session:
            entity_repo = BatteryEntityRepository(session)

            valid_pn_count = 0
            invalid_pn_count = 0

            for pn_data in merged_payload.get("part_numbers", []):
                part_validation = await validator.validate_part({
                    "normalized": pn_data.get("normalized", ""),
                    "brand": pn_data.get("brand", ""),
                    "pn_type": pn_data.get("pn_type", ""),
                    "name": pn_data.get("name", ""),
                    "source_url": merged_payload.get("_meta", {}).get("source_url", ""),
                    "evidence_quote": pn_data.get("evidence_quote", ""),
                })

                if part_validation["is_valid"]:
                    await entity_repo.upsert_part_number(
                        entity_id=entity_id,
                        raw=pn_data["raw"],
                        normalized=pn_data["normalized"],
                        brand=pn_data["brand"],
                        pn_type=pn_data.get("pn_type", "service"),
                        source_url=merged_payload.get("_meta", {}).get("source_url"),
                        evidence_quote=pn_data.get("evidence_quote"),
                    )
                    valid_pn_count += 1
                else:
                    invalid_pn_count += 1
                    self.logger.warning(
                        "part_number_rejected_by_validation",
                        normalized=pn_data.get("normalized"),
                        brand=pn_data.get("brand"),
                        reason=part_validation.get("reason"),
                        warnings=part_validation.get("warnings", []),
                    )

            for code, prop_data in merged_payload.get("properties", {}).items():
                await entity_repo.upsert_property(
                    entity_id=entity_id,
                    code=code,
                    value=prop_data["value"],
                    unit=prop_data.get("unit"),
                    source_url=merged_payload.get("_meta", {}).get("source_url"),
                    evidence_quote=prop_data.get("evidence_quote"),
                    confidence=prop_data.get("confidence", 0.5),
                )

            for vehicle_data in merged_payload.get("vehicles", []):
                await entity_repo.upsert_vehicle(
                    entity_id=entity_id,
                    make=vehicle_data["make"],
                    model=vehicle_data["model"],
                    variant_code=vehicle_data.get("variant_code"),
                    year_from=vehicle_data.get("year_from"),
                    year_to=vehicle_data.get("year_to"),
                    engine_code=vehicle_data.get("engine_code"),
                    source_url=merged_payload.get("_meta", {}).get("source_url"),
                )

            self.logger.info(
                "merged_payload_persisted",
                entity_id=str(entity_id),
                valid_pn_count=valid_pn_count,
                invalid_pn_count=invalid_pn_count,
            )
