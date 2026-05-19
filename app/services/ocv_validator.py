from typing import Optional
import structlog

logger = structlog.get_logger()

OCV_VOLTAGE_RANGES = {
    "LFP":  {"min": 2.885, "max": 3.650, "nominal": 3.20},
    "NMC":  {"min": 3.341, "max": 4.200, "nominal": 3.70},
    "NCA":  {"min": 3.341, "max": 4.200, "nominal": 3.70},
    "LTO":  {"min": 2.109, "max": 2.700, "nominal": 2.30},
    "NaB":  {"min": 2.222, "max": 4.000, "nominal": 3.10},
}


def validate_cell_voltage(chemistry: str, nominal_voltage: float) -> tuple[bool, Optional[str]]:
    ref = OCV_VOLTAGE_RANGES.get(chemistry.upper())
    if not ref:
        return True, None
    if nominal_voltage < ref["min"] * 0.95 or nominal_voltage > ref["max"] * 1.05:
        return False, f"voltage {nominal_voltage}V outside plausible range [{ref['min']:.2f}-{ref['max']:.2f}V] for {chemistry}"
    return True, None


def validate_pack_energy(
    nominal_voltage: float,
    capacity_ah: float,
    claimed_energy_kwh: float,
    tolerance: float = 0.10,
) -> tuple[bool, Optional[str]]:
    calculated = (nominal_voltage * capacity_ah) / 1000
    if calculated <= 0:
        return False, "calculated energy is zero or negative"
    delta = abs(claimed_energy_kwh - calculated) / calculated
    if delta > tolerance:
        return False, f"claimed energy {claimed_energy_kwh}kWh differs >{tolerance*100:.0f}% from voltage×capacity={calculated:.2f}kWh"
    return True, None


def validate_cross_property_consistency(properties: dict) -> list[dict]:
    warnings = []
    chem = properties.get('chemistry') or properties.get('cell_chemistry') or ''
    voltage = properties.get('voltage_nominal') or properties.get('nominal_voltage') or properties.get('voltage_nominal_v')
    capacity = properties.get('capacity_ah_nom') or properties.get('nominal_capacity') or properties.get('capacity_ah')
    energy = properties.get('energy_wh') or properties.get('nominal_energy')

    if chem and voltage is not None:
        ok, msg = validate_cell_voltage(chem, float(voltage))
        if not ok:
            warnings.append({"type": "PHYSICS_INCONSISTENT", "field": "voltage_nominal", "message": msg})

    if voltage is not None and capacity is not None and energy is not None:
        ok, msg = validate_pack_energy(float(voltage), float(capacity), float(energy) / 1000)
        if not ok:
            warnings.append({"type": "PHYSICS_INCONSISTENT", "field": "energy_wh", "message": msg})

    return warnings
