import asyncio
import uuid
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import openpyxl
from sqlalchemy import select
from app.services.database import get_db_session
from app.models.entity import BatteryEntity
from app.models.scrape import ScrapePlan
import structlog

logger = structlog.get_logger()

DATA_DIR = os.environ.get("BDN_DATA_DIR", "/app/scripts/data")
PACK_FILE = os.path.join(DATA_DIR, "pack-benchmark-specification-BatteryDesignNET-v1.5-download.xlsx")

OEM_TO_BRAND = {
    "Mercedes-Benz": "mercedes",
    "Mercedes": "mercedes",
    "Mercedes-Maybach": "mercedes",
    "Jaguar": "jlr",
    "Land Rover": "jlr",
    "Porsche": "porsche",
    "Peugeot": "stellantis",
    "Citroën": "stellantis",
    "Citroen": "stellantis",
    "DS Automobiles": "stellantis",
    "Fiat": "stellantis",
    "Alfa Romeo": "stellantis",
    "Vauxhall": "stellantis",
    "Opel": "stellantis",
    "Jeep": "stellantis",
    "Chrysler": "stellantis",
    "Maserati": "stellantis",
}

BRAND_TO_POLICY = {
    "mercedes": "webautocats",
    "jlr": "topix_jaguarlandrover_com",
    "porsche": "teile_com",
    "stellantis": "webautocats",
}


def normalize_pn(raw: str) -> str:
    return raw.strip().upper().replace(" ", "").replace("-", "") if raw else ""


async def seed_scrape_plan_from_packs() -> int:
    logger.info("Loading pack database from %s", PACK_FILE)
    if not os.path.exists(PACK_FILE):
        logger.warning("File not found: %s", PACK_FILE)
        return 0

    wb = openpyxl.load_workbook(PACK_FILE, read_only=True, data_only=True)
    ws = wb["Packs"]
    rows = list(ws.iter_rows(min_row=2, values_only=True))
    wb.close()

    gap_rows = []
    for row in rows:
        if not row or not row[3]:
            continue
        try:
            mfr = str(row[3]).strip() if row[3] else None
            model = str(row[4]).strip() if row[4] else None
            mfr_code = str(row[5]).strip() if row[5] else None
            if not mfr or not model or mfr in ("", "-", "Manufacturer"):
                continue
            brand = OEM_TO_BRAND.get(mfr) or OEM_TO_BRAND.get(mfr.replace("-", " "))
            if not brand:
                continue
            has_mfr_code = mfr_code and str(mfr_code).strip() not in ("", "-", "nan")
            if not has_mfr_code:
                gap_rows.append({
                    "manufacturer": mfr,
                    "model": model,
                    "mfr_code": mfr_code,
                    "brand": brand,
                    "search_query": f"{mfr} {model} battery pack part number",
                })
        except Exception:
            continue

    logger.info("Found %d gap rows needing scrape", len(gap_rows))

    count = 0
    async with get_db_session() as session:
        for gap in gap_rows:
            try:
                result = await session.execute(
                    select(BatteryEntity).where(
                        BatteryEntity.canonical_name.ilike(f"%{gap['model']}%")
                    ).limit(1)
                )
                entity = result.scalar_one_or_none()
                if not entity:
                    entity_id = uuid.uuid4()
                    entity = BatteryEntity(
                        id=entity_id,
                        entity_type="pack",
                        canonical_name=f"{gap['manufacturer']} {gap['model']}",
                        normalized_primary_part_number=f"BDN:GAP:{normalize_pn(gap['model'])[:20]}",
                        occurrence_count=1,
                        status="candidate",
                    )
                    session.add(entity)
                    await session.flush()
                else:
                    entity_id = entity.id

                brand = gap["brand"]
                policy_key = BRAND_TO_POLICY.get(brand, "default")

                plan = ScrapePlan(
                    id=uuid.uuid4(),
                    entity_id=entity_id,
                    source_url=f"https://www.google.com/search?q={gap['search_query']}",
                    source_kind="manufacturer_catalog",
                    brand=brand,
                    wave_policy_key=policy_key,
                    waves_planned=1,
                    waves_completed=0,
                    quorum_policy={"quorum_required": 1},
                    status="open",
                )
                session.add(plan)
                count += 1

                if count % 50 == 0:
                    await session.commit()
                    logger.info("  Committed %d scrape plans...", count)

            except Exception as e:
                logger.warning("Error processing gap row: %s", e)
                continue

        await session.commit()

    logger.info("Seeded %d scrape plans", count)
    return count


async def main():
    logger.info("=== Seed Scrape Plan from BatteryDesign.NET Gaps ===")
    count = await seed_scrape_plan_from_packs()
    logger.info("=== Seed Complete: %d scrape plans created ===", count)


if __name__ == "__main__":
    asyncio.run(main())
