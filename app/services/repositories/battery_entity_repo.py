from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from typing import Optional
import uuid
from app.models.entity import BatteryEntity
from app.models.part_number import BatteryPartNumber
from app.models.property_statement import PropertyStatement
from app.models.vehicle_variant_code import VehicleVariantCode
from app.models.scrape import ScrapePlan, ScrapeAttempt, ScrapeConsensusResult
import structlog

logger = structlog.get_logger()


class BatteryEntityRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, entity_type: str, canonical_name: str = None, normalized_primary_part_number: str = None) -> BatteryEntity:
        entity = BatteryEntity(
            id=uuid.uuid4(),
            entity_type=entity_type,
            canonical_name=canonical_name,
            normalized_primary_part_number=normalized_primary_part_number,
            status='candidate',
        )
        self.session.add(entity)
        await self.session.flush()
        return entity

    async def get_by_id(self, entity_id: uuid.UUID) -> Optional[BatteryEntity]:
        result = await self.session.execute(
            select(BatteryEntity)
            .options(
                selectinload(BatteryEntity.part_numbers),
                selectinload(BatteryEntity.property_statements),
                selectinload(BatteryEntity.vehicle_variant_codes),
            )
            .where(BatteryEntity.id == entity_id)
        )
        return result.scalar_one_or_none()

    async def get_by_normalized_pn(self, normalized_pn: str) -> Optional[BatteryEntity]:
        result = await self.session.execute(
            select(BatteryEntity)
            .options(selectinload(BatteryEntity.part_numbers))
            .where(BatteryEntity.normalized_primary_part_number == normalized_pn)
        )
        return result.scalar_one_or_none()

    async def find_or_create_by_pn(self, normalized_pn: str, entity_type: str = 'pack') -> tuple[BatteryEntity, bool]:
        existing = await self.get_by_normalized_pn(normalized_pn)
        if existing:
            return existing, False
        entity = await self.create(entity_type=entity_type, normalized_primary_part_number=normalized_pn)
        return entity, True

    async def list_
(self, entity_type: Optional[str] = None, brand: Optional[str] = None, page: int = 1, page_size: int = 50) -> tuple[list[BatteryEntity], int]:
        query = select(BatteryEntity).options(selectinload(BatteryEntity.part_numbers))
        count_query = select(func.count(BatteryEntity.id))

        if entity_type:
            query = query.where(BatteryEntity.entity_type == entity_type)
            count_query = count_query.where(BatteryEntity.entity_type == entity_type)

        if brand:
            query = query.join(BatteryPartNumber).where(BatteryPartNumber.brand == brand)
            count_query = count_query.select_from(BatteryEntity).join(BatteryPartNumber).where(BatteryPartNumber.brand == brand)

        total_result = await self.session.execute(count_query)
        total = total_result.scalar()

        query = query.offset((page - 1) * page_size).limit(page_size).order_by(BatteryEntity.updated_at.desc())
        result = await self.session.execute(query)
        entities = list(result.scalars().all())
        return entities, total

    async def upsert_part_number(self, entity_id: uuid.UUID, raw: str, normalized: str, brand: str, pn_type: str = 'service', source_url: str = None, evidence_quote: str = None) -> BatteryPartNumber:
        result = await self.session.execute(
            select(BatteryPartNumber).where(
                and_(
                    BatteryPartNumber.entity_id == entity_id,
                    BatteryPartNumber.normalized == normalized,
                    BatteryPartNumber.brand == brand,
                )
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            existing.raw = raw
            existing.evidence_quote = evidence_quote
            return existing

        pn = BatteryPartNumber(
            id=uuid.uuid4(),
            entity_id=entity_id,
            raw=raw,
            normalized=normalized,
            brand=brand,
            pn_type=pn_type,
            source_url=source_url,
            evidence_quote=evidence_quote,
        )
        self.session.add(pn)
        await self.session.flush()
        return pn

    async def upsert_property(self, entity_id: uuid.UUID, code: str, value, unit: str = None, source_url: str = None, evidence_quote: str = None, confidence: float = 0.5) -> PropertyStatement:
        result = await self.session.execute(
            select(PropertyStatement).where(
                and_(
                    PropertyStatement.entity_id == entity_id,
                    PropertyStatement.code == code,
                )
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            if confidence > existing.confidence:
                existing.value = value
                existing.unit = unit
                existing.confidence = confidence
                existing.evidence_quote = evidence_quote
                existing.source_url = source_url
            return existing

        prop = PropertyStatement(
            id=uuid.uuid4(),
            entity_id=entity_id,
            code=code,
            value=value,
            unit=unit,
            source_url=source_url,
            evidence_quote=evidence_quote,
            confidence=confidence,
            status='candidate',
        )
        self.session.add(prop)
        await self.session.flush()
        return prop

    async def upsert_vehicle(self, entity_id: uuid.UUID, make: str, model: str, variant_code: str = None, year_from: int = None, year_to: int = None, engine_code: str = None, source_url: str = None) -> VehicleVariantCode:
        result = await self.session.execute(
            select(VehicleVariantCode).where(
                and_(
                    VehicleVariantCode.entity_id == entity_id,
                    VehicleVariantCode.make == make,
                    VehicleVariantCode.model == model,
                )
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            return existing

        vehicle = VehicleVariantCode(
            id=uuid.uuid4(),
            entity_id=entity_id,
            make=make,
            model=model,
            variant_code=variant_code,
            year_from=year_from,
            year_to=year_to,
            engine_code=engine_code,
            source_url=source_url,
        )
        self.session.add(vehicle)
        await self.session.flush()
        return vehicle
