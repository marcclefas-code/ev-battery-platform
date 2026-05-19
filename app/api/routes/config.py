from fastapi import APIRouter, Depends
import structlog
from sqlalchemy import select
from app.services.database import get_db_session
from app.models.property_definition import PropertyDefinition
from app.api.middleware.auth import read_only
import yaml
import os

logger = structlog.get_logger()
router = APIRouter(prefix="/api/v1/config", tags=["config"])


@router.get("/property-definitions")
async def list_property_definitions(_: dict = Depends(read_only)):
    async with get_db_session() as session:
        result = await session.execute(select(PropertyDefinition))
        props = result.scalars().all()
        return {
            "property_definitions": [
                {"code": p.code, "label": p.label, "unit": p.unit, "data_type": p.data_type, "applies_to": p.applies_to, "category": p.category}
                for p in props
            ]
        }


@router.get("/wave-policies")
async def list_wave_policies(_: dict = Depends(read_only)):
    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "config", "stagger_config.yaml")
    try:
        with open(config_path) as f:
            config = yaml.safe_load(f)
        return config
    except Exception:
        return {"wave_policies": {}, "default_policy": {}}


@router.get("/brands")
async def list_brands(_: dict = Depends(read_only)):
    return {
        "brands": [
            {"name": "Porsche", "code": "porsche", "source_domain": "teile.com", "status": "active"},
            {"name": "Mercedes-Benz", "code": "mercedes", "source_domain": "teile.com", "status": "planned"},
            {"name": "JLR", "code": "jlr", "source_domain": "topix.jaguarlandrover.com", "status": "planned"},
            {"name": "Stellantis", "code": "stellantis", "source_domain": "websuite", "status": "planned"},
            {"name": "batterydesign.net", "code": "batterydesign", "source_domain": "batterydesign.net", "status": "seed_data"},
        ]
    }
