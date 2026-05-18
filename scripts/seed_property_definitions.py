import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
import yaml
import structlog

logger = structlog.get_logger()

PROPERTY_DEFINITIONS = [
    {"code": "batt_type", "label": "Battery Type", "unit": None, "data_type": "string", "applies_to": ["pack"], "category": "classification"},
    {"code": "nominal_voltage", "label": "Nominal Voltage", "unit": "V", "data_type": "number", "applies_to": ["pack", "hv_module", "hv_cell"], "category": "electrical"},
    {"code": "nominal_capacity", "label": "Nominal Capacity", "unit": "Ah", "data_type": "number", "applies_to": ["pack", "hv_module", "hv_cell"], "category": "electrical"},
    {"code": "nominal_energy", "label": "Nominal Energy", "unit": "kWh", "data_type": "number", "applies_to": ["pack", "hv_module"], "category": "electrical"},
    {"code": "weight", "label": "Weight", "unit": "kg", "data_type": "number", "applies_to": ["pack", "hv_module", "hv_cell"], "category": "physical"},
    {"code": "dimensions_length", "label": "Length", "unit": "mm", "data_type": "number", "applies_to": ["pack", "hv_module", "hv_cell"], "category": "physical"},
    {"code": "dimensions_width", "label": "Width", "unit": "mm", "data_type": "number", "applies_to": ["pack", "hv_module", "hv_cell"], "category": "physical"},
    {"code": "dimensions_height", "label": "Height", "unit": "mm", "data_type": "number", "applies_to": ["pack", "hv_module", "hv_cell"], "category": "physical"},
    {"code": "chemistry", "label": "Battery Chemistry", "unit": None, "data_type": "string", "applies_to": ["pack", "hv_module", "hv_cell"], "category": "electrical"},
    {"code": "manufacturer", "label": "Manufacturer", "unit": None, "data_type": "string", "applies_to": ["pack", "hv_module", "hv_cell"], "category": "classification"},
    {"code": "part_number_service", "label": "Service Part Number", "unit": None, "data_type": "string", "applies_to": ["pack", "hv_module", "hv_cell"], "category": "identifiers"},
    {"code": "part_number_superseded", "label": "Superseded Part Number", "unit": None, "data_type": "string", "applies_to": ["pack"], "category": "identifiers"},
    {"code": "oem_part_number", "label": "OEM Part Number", "unit": None, "data_type": "string", "applies_to": ["pack"], "category": "identifiers"},
    {"code": "warranty_months", "label": "Warranty", "unit": "months", "data_type": "integer", "applies_to": ["pack"], "category": "commercial"},
    {"code": "coolant_type", "label": "Coolant Type", "unit": None, "data_type": "string", "applies_to": ["pack"], "category": "thermal"},
    {"code": "cooling_system", "label": "Cooling System", "unit": None, "data_type": "string", "applies_to": ["pack"], "category": "thermal"},
    {"code": "ip_rating", "label": "IP Rating", "unit": None, "data_type": "string", "applies_to": ["pack"], "category": "environmental"},
    {"code": "thermal_management", "label": "Thermal Management", "unit": None, "data_type": "string", "applies_to": ["pack", "hv_module", "hv_cell"], "category": "thermal"},
    {"code": "bms_canbus", "label": "BMS CAN Bus", "unit": None, "data_type": "boolean", "applies_to": ["pack"], "category": "electrical"},
    {"code": "module_count", "label": "Module Count", "unit": None, "data_type": "integer", "applies_to": ["pack"], "category": "structural"},
    {"code": "cell_count", "label": "Cell Count", "unit": None, "data_type": "integer", "applies_to": ["pack", "hv_module"], "category": "structural"},
    {"code": "cell_format", "label": "Cell Format", "unit": None, "data_type": "string", "applies_to": ["hv_cell"], "category": "structural"},
    {"code": "cycle_life", "label": "Cycle Life", "unit": "cycles", "data_type": "integer", "applies_to": ["pack", "hv_module", "hv_cell"], "category": "performance"},
    {"code": "soc_window_min", "label": "Min State of Charge", "unit": "percent", "data_type": "number", "applies_to": ["pack"], "category": "electrical"},
    {"code": "soc_window_max", "label": "Max State of Charge", "unit": "percent", "data_type": "number", "applies_to": ["pack"], "category": "electrical"},
    {"code": "max_charge_rate", "label": "Max Charge Rate", "unit": "kW", "data_type": "number", "applies_to": ["pack", "hv_module", "hv_cell"], "category": "performance"},
    {"code": "max_discharge_rate", "label": "Max Discharge Rate", "unit": "kW", "data_type": "number", "applies_to": ["pack", "hv_module"], "category": "performance"},
    {"code": "operating_temp_min", "label": "Min Operating Temperature", "unit": "°C", "data_type": "number", "applies_to": ["pack", "hv_module", "hv_cell"], "category": "environmental"},
    {"code": "operating_temp_max", "label": "Max Operating Temperature", "unit": "°C", "data_type": "number", "applies_to": ["pack", "hv_module", "hv_cell"], "category": "environmental"},
    {"code": "communication_protocol", "label": "Communication Protocol", "unit": None, "data_type": "string", "applies_to": ["pack", "hv_module"], "category": "electrical"},
    {"code": "diagnostic_port", "label": "Diagnostic Port", "unit": None, "data_type": "string", "applies_to": ["pack"], "category": "electrical"},
    {"code": "grounding_type", "label": "Grounding Type", "unit": None, "data_type": "string", "applies_to": ["pack"], "category": "electrical"},
    {"code": "application", "label": "Application", "unit": None, "data_type": "string", "applies_to": ["pack", "hv_module"], "category": "classification"},
    {"code": "compatible_model", "label": "Compatible Model", "unit": None, "data_type": "string", "applies_to": ["pack", "hv_module"], "category": "compatibility"},
]


async def seed(db_url: str):
    engine = create_async_engine(db_url, echo=False)
    async with engine.begin() as conn:
        for prop in PROPERTY_DEFINITIONS:
            await conn.execute(
                text("""
                    INSERT INTO property_definition (code, label, unit, data_type, applies_to, category)
                    VALUES (:code, :label, :unit, :data_type, :applies_to, :category)
                    ON CONFLICT (code) DO UPDATE SET
                        label = EXCLUDED.label,
                        unit = EXCLUDED.unit,
                        data_type = EXCLUDED.data_type,
                        applies_to = EXCLUDED.applies_to,
                        category = EXCLUDED.category
                """),
                {
                    "code": prop["code"],
                    "label": prop["label"],
                    "unit": prop["unit"],
                    "data_type": prop["data_type"],
                    "applies_to": prop["applies_to"],
                    "category": prop["category"],
                }
            )
        logger.info("property_definitions_seeded", count=len(PROPERTY_DEFINITIONS))
    await engine.dispose()


if __name__ == "__main__":
    import os
    db_url = os.getenv("DATABASE_URL", "postgresql+asyncpg://ev_battery_user:ev_battery_pass@localhost:5432/ev_battery")
    asyncio.run(seed(db_url))
