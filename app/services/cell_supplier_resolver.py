from typing import Optional
import structlog

logger = structlog.get_logger()

CELL_SUPPLIER_MAP = {
    "Porsche Taycan": {"supplier": "LG Chem", "years": "2019-2023", "module_ref": "LGES", "chemistry": "NMC"},
    "Porsche Taycan 2024": {"supplier": "CATL", "years": "2024+", "module_ref": None, "chemistry": "NMC"},
    "Porsche Cayenne E-Hybrid 2018": {"supplier": "Samsung SDI", "years": "2018-2022", "module_ref": "SDI", "chemistry": "NMC"},
    "Porsche 911 T-Hybrid": {"supplier": "Varta", "years": "2024+", "module_ref": "Varta", "chemistry": "LFP"},
    "Porsche Macan EV": {"supplier": "CATL", "years": "2024+", "module_ref": None, "chemistry": "NMC"},
    "Porsche Panamera E-Hybrid": {"supplier": "Samsung SDI", "years": "2022+", "module_ref": "SDI", "chemistry": "NMC"},
    "Jaguar I-Pace": {"supplier": "LG Energy Solution", "years": "2018-2024", "module_ref": "LGES Jaguar I-Pace", "chemistry": "NMC"},
    "Land Rover Range Rover P400e": {"supplier": "Samsung SDI", "years": "2018-2022", "module_ref": None, "chemistry": "NMC"},
    "Land Rover Defender P400e": {"supplier": "Samsung SDI", "years": "2020-2024", "module_ref": None, "chemistry": "NMC"},
    "Citroen e-C3": {"supplier": "SVOLT", "years": "2024+", "module_ref": None, "chemistry": "LFP"},
    "Peugeot e-208 2024": {"supplier": "SVOLT", "years": "2024+", "module_ref": None, "chemistry": "LFP"},
    "Peugeot e-2008 2024": {"supplier": "SVOLT", "years": "2024+", "module_ref": None, "chemistry": "LFP"},
    "Opel Corsa-e": {"supplier": "SVOLT", "years": "2024+", "module_ref": None, "chemistry": "LFP"},
    "Fiat 500e": {"supplier": "Samsung SDI", "years": "2020+", "module_ref": "SDI", "chemistry": "NMC"},
    "Citroen e-Jumpy 68kWh": {"supplier": "CATL", "years": "2020+", "module_ref": None, "chemistry": "NMC"},
    "Mercedes EQS": {"supplier": "CATL", "years": "2021+", "module_ref": None, "chemistry": "NMC"},
    "Mercedes EQE": {"supplier": "CATL", "years": "2022+", "module_ref": None, "chemistry": "NMC"},
    "Mercedes EQA": {"supplier": "CATL", "years": "2021+", "module_ref": None, "chemistry": "NMC"},
    "Mercedes EQB": {"supplier": "CATL", "years": "2022+", "module_ref": None, "chemistry": "NMC"},
    "BMW i3": {"supplier": "Samsung SDI", "years": "2013-2022", "module_ref": "SDI", "chemistry": "NMC"},
    "BMW iX3": {"supplier": "Samsung SDI", "years": "2020-2024", "module_ref": "SDI", "chemistry": "NMC"},
    "BMW iX": {"supplier": "Samsung SDI", "years": "2021-2024", "module_ref": "SDI", "chemistry": "NMC"},
    "Genesis GV60": {"supplier": "Samsung SDI", "years": "2022+", "module_ref": "SDI", "chemistry": "NMC"},
    "Audi e-tron": {"supplier": "LG Energy Solution", "years": "2019-2024", "module_ref": "LGES", "chemistry": "NMC"},
    "Audi Q4 e-tron": {"supplier": "LG Energy Solution", "years": "2021-2024", "module_ref": "LGES", "chemistry": "NMC"},
    "Volkswagen ID.3": {"supplier": "LG Energy Solution", "years": "2020-2024", "module_ref": "LGES", "chemistry": "NMC"},
    "Volkswagen ID.4": {"supplier": "LG Energy Solution", "years": "2020-2024", "module_ref": "LGES", "chemistry": "NMC"},
    "Volkswagen ID.Buzz": {"supplier": "LG Energy Solution", "years": "2022-2024", "module_ref": "LGES", "chemistry": "NMC"},
}


def normalize_model(model: str) -> str:
    return model.strip().lower().replace(' ', '').replace('-', '').replace('_', '')


def get_cell_supplier(vehicle_model: str) -> Optional[dict]:
    if not vehicle_model:
        return None
    normalized_input = normalize_model(vehicle_model)
    for model_key, info in CELL_SUPPLIER_MAP.items():
        if normalize_model(model_key) == normalized_input:
            return info
        if normalize_model(model_key) in normalized_input or normalized_input in normalize_model(model_key):
            return info
    return None


def get_supplier_as_property(vehicle_model: str, source: str = "batterydesign.net") -> Optional[dict]:
    info = get_cell_supplier(vehicle_model)
    if not info:
        return None
    return {
        'supplier': info['supplier'],
        'supplier_years': info.get('years', None),
        'supplier_module_ref': info.get('module_ref', None),
        'supplier_confidence': 0.80,
        'source': source,
    }
