import re
from typing import Optional
import structlog

logger = structlog.get_logger()

RENAULT_PN_RE = re.compile(r'82\d{7}')
RENAULT_PN_ALT_RE = re.compile(r'\d{2}\s?\d{2}\s?\d\s?\d{3}\s?\d{3}')

STANDARDIZED_CHEMISTRY = {
    'NCM': 'NCM',
    'NMC': 'NCM',
    'LFP': 'LiFePO4',
    'LTO': 'LiTiO',
    'NCA': 'NCA',
}

BATTERY_SPECS = {
    'megane_e_tech': {'capacity_kwh': 60, 'voltage': 400, 'chemistry': 'NCM'},
    'scenic_e_tech': {'capacity_kwh': 60, 'voltage': 400, 'chemistry': 'NCM'},
    'zoe_ze50': {'capacity_kwh': 52, 'voltage': 400, 'chemistry': 'NCM'},
    'zoe_ze40': {'capacity_kwh': 41, 'voltage': 400, 'chemistry': 'NCM'},
    'zoe_ze24': {'capacity_kwh': 22, 'voltage': 400, 'chemistry': 'NCM'},
    'spring': {'capacity_kwh': 27, 'voltage': 400, 'chemistry': 'LFP'},
    'alpine_a290': {'capacity_kwh': 52, 'voltage': 400, 'chemistry': 'NCM'},
}


def normalize_renault_pn(raw: str) -> str:
    raw = raw.strip().upper().replace(' ', '').replace('-', '').replace('.', '')
    return raw


class RenaultAdapter:
    BRAND = 'renault'
    SOURCE_DOMAIN = 'renault.com'
    SOURCE_DOMAIN_ALT = 'myrenault.com'
    SOURCE_KIND = 'dealer_portal'

    def __init__(self):
        self.logger = logger

    def extract_part_numbers(self, html_text: str) -> list[dict]:
        results = []
        seen = set()
        for pattern in [RENAULT_PN_RE, RENAULT_PN_ALT_RE]:
            for m in pattern.findall(html_text):
                norm = normalize_renault_pn(m)
                if norm in seen:
                    continue
                seen.add(norm)
                if len(norm) >= 8:
                    results.append({
                        'raw': m,
                        'normalized': norm,
                        'brand': self.BRAND,
                        'pn_type': 'service',
                    })
        return results

    def build_search_url(self, part_number: str) -> str:
        pn = part_number.replace(' ', '+')
        return f"https://www.renault.com/parts-catalog/search?q={pn}"

    def extract_vehicle_info(self, html_text: str) -> list[dict]:
        results = []
        year_match = re.findall(r'\b(19\d{2}|20\d{2})\b', html_text)
        model_patterns = [
            r'(Megane[\s-]+E-Tech[\s-]+Electric)',
            r'(Scenic[\s-]+E-Tech[\s-]+Electric)',
            r'(Zoe[\s-]+(?:ZE50|ZE40|ZE24)?)',
            r'(Twingo[\s-]+E-Tech)',
            r'(Dacia[\s-]+Spring)',
            r'(Alpine[\s-]+A290)',
        ]
        for pattern in model_patterns:
            for match in re.finditer(pattern, html_text, re.IGNORECASE):
                model_raw = match.group(1)
                years = sorted(set(int(y) for y in year_match if 2000 <= int(y) <= 2030)) if year_match else []
                model_lower = model_raw.lower().replace(' ', '_').replace('-', '_')
                if 'megane_e_tech' in model_lower or 'megane' in model_lower and 'e_tech' in model_lower:
                    model = 'Megane E-Tech Electric'
                    battery = BATTERY_SPECS['megane_e_tech']
                elif 'scenic_e_tech' in model_lower or 'scenic' in model_lower and 'e_tech' in model_lower:
                    model = 'Scenic E-Tech Electric'
                    battery = BATTERY_SPECS['scenic_e_tech']
                elif 'zoe' in model_lower:
                    if 'ze50' in model_lower:
                        model = 'Zoe ZE50'
                        battery = BATTERY_SPECS['zoe_ze50']
                    elif 'ze40' in model_lower:
                        model = 'Zoe ZE40'
                        battery = BATTERY_SPECS['zoe_ze40']
                    elif 'ze24' in model_lower:
                        model = 'Zoe ZE24'
                        battery = BATTERY_SPECS['zoe_ze24']
                    else:
                        model = 'Zoe'
                        battery = BATTERY_SPECS['zoe_ze50']
                elif 'twingo' in model_lower:
                    model = 'Twingo E-Tech'
                    battery = BATTERY_SPECS['megane_e_tech']
                elif 'spring' in model_lower or 'dacia' in model_lower:
                    model = 'Dacia Spring'
                    battery = BATTERY_SPECS['spring']
                elif 'alpine' in model_lower or 'a290' in model_lower:
                    model = 'Alpine A290'
                    battery = BATTERY_SPECS['alpine_a290']
                else:
                    model = model_raw
                    battery = None
                entry = {
                    'make': 'Renault',
                    'model': model,
                    'variant_code': None,
                    'year_from': years[0] if years else None,
                    'year_to': years[-1] if years else None,
                    'engine_code': None,
                }
                if battery:
                    entry['battery_capacity_kwh'] = battery['capacity_kwh']
                    entry['battery_voltage'] = battery['voltage']
                    entry['battery_chemistry'] = battery['chemistry']
                results.append(entry)
        return results

    def enrich_with_renault_context(self, payload: dict, html_text: str) -> dict:
        if 'properties' not in payload:
            payload['properties'] = {}
        if 'chemistry' not in payload['properties']:
            for chem_key, chem_val in STANDARDIZED_CHEMISTRY.items():
                if chem_key in html_text.upper():
                    payload['properties']['chemistry'] = {
                        'value': chem_val,
                        'evidence_quote': f'Found {chem_key} reference in page',
                        'confidence': 0.7,
                    }
                    break
        return payload
