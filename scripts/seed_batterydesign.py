"""Seed batterydesign.net data from purchased dataset.

This script loads the batterydesign.net dataset (once purchased) into the
enrichment_ev_batteries database as pre-confirmed battery entities.

Usage:
    python scripts/seed_batterydesign.py --file /path/to/batterydesign_dump.csv
"""
import asyncio
import sys
import csv
import uuid
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
import structlog

logger = structlog.get_logger()

REQUIRED_COLUMNS = [
    'part_number', 'entity_type', 'nominal_voltage', 'nominal_capacity',
    'nominal_energy', 'chemistry', 'manufacturer', 'weight',
    'dimensions_length', 'dimensions_width', 'dimensions_height',
]


async def seed_batterydesign(csv_path: str, db_url: str):
    engine = create_async_engine(db_url, echo=False)
    async with engine.begin() as conn:
        count = 0
        with open(csv_path, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                normalized_pn = row.get('part_number', '').strip().upper()
                if not normalized_pn:
                    continue

                entity_id = str(uuid.uuid4())
                await conn.execute(
                    text("""
                        INSERT INTO battery_entity (id, entity_type, canonical_name,
                            normalized_primary_part_number, status, occurrence_count)
                        VALUES (:id, :entity_type, :canonical_name, :normalized_pn, 'confirmed', 1)
                        ON CONFLICT (normalized_primary_part_number) DO NOTHING
                    """),
                    {
                        'id': entity_id,
                        'entity_type': row.get('entity_type', 'pack'),
                        'canonical_name': row.get('canonical_name', row.get('part_number', '')),
                        'normalized_pn': normalized_pn,
                    }
                )

                if row.get('nominal_voltage'):
                    await conn.execute(
                        text("""
                            INSERT INTO property_statement (id, entity_id, code, value, unit, confidence, status)
                            SELECT :id, e.id, 'nominal_voltage', :value, 'V', 0.95, 'confirmed'
                            FROM battery_entity e WHERE e.normalized_primary_part_number = :pn
                        """),
                        {'id': str(uuid.uuid4()), 'value': float(row['nominal_voltage']), 'pn': normalized_pn}
                    )

                if row.get('nominal_capacity'):
                    await conn.execute(
                        text("""
                            INSERT INTO property_statement (id, entity_id, code, value, unit, confidence, status)
                            SELECT :id, e.id, 'nominal_capacity', :value, 'Ah', 0.95, 'confirmed'
                            FROM battery_entity e WHERE e.normalized_primary_part_number = :pn
                        """),
                        {'id': str(uuid.uuid4()), 'value': float(row['nominal_capacity']), 'pn': normalized_pn}
                    )

                if row.get('chemistry'):
                    await conn.execute(
                        text("""
                            INSERT INTO property_statement (id, entity_id, code, value, confidence, status)
                            SELECT :id, e.id, 'chemistry', :value, 0.95, 'confirmed'
                            FROM battery_entity e WHERE e.normalized_primary_part_number = :pn
                        """),
                        {'id': str(uuid.uuid4()), 'value': row['chemistry'], 'pn': normalized_pn}
                    )

                await conn.execute(
                    text("""
                        INSERT INTO battery_part_number (id, entity_id, raw, normalized, brand, pn_type, trust_weight, source_url)
                        SELECT :id, e.id, :raw, :normalized, 'batterydesign', 'service', 0.95, 'https://batterydesign.net'
                        FROM battery_entity e WHERE e.normalized_primary_part_number = :pn
                    """),
                    {'id': str(uuid.uuid4()), 'raw': normalized_pn, 'normalized': normalized_pn, 'pn': normalized_pn}
                )

                count += 1

        logger.info('batterydesign_seed_complete', records=count)
    await engine.dispose()
    return count


if __name__ == '__main__':
    import os
    import argparse
    parser = argparse.ArgumentParser(description='Seed batterydesign.net data')
    parser.add_argument('--file', required=True, help='Path to CSV file')
    parser.add_argument('--db-url', default=os.getenv('DATABASE_URL'), help='Database URL')
    args = parser.parse_args()

    if not args.db_url:
        print('ERROR: --db-url or DATABASE_URL required')
        sys.exit(1)

    count = asyncio.run(seed_batterydesign(args.file, args.db_url))
    print(f'Loaded {count} batterydesign.net records')
