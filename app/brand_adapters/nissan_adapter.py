import re
from typing import Optional
import structlog

logger = structlog.get_logger()

NISSAN_PN_RE = re.compile(r'[1-4][A-Z]\d[A-Z]\d{4,6}[A-Z0-9]')
NISSAN_PN_ALT_RE = re.compile(r'\d{4}[-]?\d{6}')
NISSAN_PACK_RE = re.compile(r'\b(LZ1|3W1|2W2)\b', re.IGNORECASE)

STANDARDIZED_CHEMISTRY = {
    'NCM': 'NCM',
    'NMC': 'NCM',
    'LFP': 'LiFePO4',
    'NCA': 'NCA',
    'LIMN': 'NCM',
}


def normalize_nissan_pn(raw: str) -> str:
    raw = raw.strip().upper().replace(' ', '').replace('-', '')
    if len(raw) >= 6:
        return raw
    return raw


def detect_nissan_battery_pack(normalized: str, html_text: str) -> Optional[dict]:
    pack_info = {
        'LZ1': {'name': 'Leaf Battery Pack', 'kwh': '40/62', 'chemistry': 'NCM'},
        '2W2': {'name': 'Leaf Battery Assembly', 'kwh': '40/62', 'chemistry': 'NCM'},
        '3W1': {'name': 'Leaf Electrical/HV Component', 'kwh': None, 'chemistry': 'NCM'},
    }
    for pack_code, info in pack_info.items():
        if pack_code in html_text.upper():
            return info
    return None


class NissanAdapter:
    BRAND = 'nissan'
    SOURCE_DOMAIN = 'nissanusa.com'
    SOURCE_DOMAIN_ALT = 'parts.nissanusa.com'
    SOURCE_KIND = 'dealer_portal'

    def __init__(self):
        self.logger = logger

    def extract_part_numbers(self, html_text: str) -> list[dict]:
        results = []
        seen = set()
        for pattern in [NISSAN_PN_RE, NISSAN_PN_ALT_RE]:
            for m in pattern.findall(html_text):
                norm = normalize_nissan_pn(m)
                if len(norm) >= 5 and norm not in seen:
                    seen.add(norm)
                    pn_type = 'service'
                    if any(m.startswith(p) for p in ['1N4', '2W2', '3W1']):
                        pn_type = 'hv_component'
                    results.append({
                        'raw': m,
                        'normalized': norm,
                        'brand': self.BRAND,
                        'pn_type': pn_type,
                    })
        return results

    def build_search_url(self, part_number: str) -> str:
        pn = part_number.replace('/', '%2F').replace(' ', '+')
        return f"https://parts.nissanusa.com/search?query={pn}"

    def build_part_url(self, part_number: str) -> str:
        pn = part_number.replace('/', '%2F')
        return f"https://parts.nissanusa.com/parts/nissan/parts/{pn}"

    def extract_vehicle_info(self, html_text: str) -> list[dict]:
        results = []
        year_match = re.findall(r'\b(19\d{2}|20\d{2})\b', html_text)
        years = sorted(set(int(y) for y in year_match if 2000 <= int(y) <= 2030)) if year_match else []

        model_patterns = [
            (r'Leaf\s*(?:ZE1(?:A)?)?', 'Leaf', ['ZE1', 'ZE1A']),
            (r'Ariya\s*YE15', 'Ariya', ['YE15']),
            (r'Sakura', 'Sakura', [None]),
        ]

        for pattern, model, variant_codes in model_patterns:
            for match in re.finditer(pattern, html_text, re.IGNORECASE):
                variant = None
                for vc in variant_codes:
                    if vc and vc in html_text.upper():
                        variant = vc
                        break
                results.append({
                    'make': 'Nissan',
                    'model': model,
                    'variant_code': variant,
                    'year_from': years[0] if years else None,
                    'year_to': years[-1] if years else None,
                    'engine_code': None,
                })

        leaf_battery_patterns = [
            r'Leaf\s*(?:40kWh|40\s*kWh)',
            r'Leaf\s*(?:62kWh|62\s*kWh)',
            r'Leaf\s*(?:24kWh|24\s*kWh)',
            r'Leaf\s*(?:30kWh|30\s*kWh)',
            r'ZE1(?:A)?',
            r'LZ1',
        ]
        for pattern in leaf_battery_patterns:
            if re.search(pattern, html_text, re.IGNORECASE):
                battery_info = {'make': 'Nissan', 'model': 'Leaf', 'variant_code': None}
                if '40' in pattern:
                    battery_info['kwh'] = '40'
                    battery_info['variant_code'] = 'ZE1'
                elif '62' in pattern:
                    battery_info['kwh'] = '62'
                    battery_info['variant_code'] = 'ZE1A'
                elif '24' in pattern:
                    battery_info['kwh'] = '24'
                    battery_info['variant_code'] = 'ZE0'
                elif '30' in pattern:
                    battery_info['kwh'] = '30'
                    battery_info['variant_code'] = 'ZE0'
                elif 'ZE1A' in pattern.upper():
                    battery_info['kwh'] = '62'
                    battery_info['variant_code'] = 'ZE1A'
                elif 'LZ1' in pattern.upper():
                    battery_info['kwh'] = '40/62'
                    battery_info['variant_code'] = 'ZE1/ZE1A'
                if battery_info not in results:
                    results.append(battery_info)

        ariya_patterns = [
            r'Ariya\s*(?:63kWh|63\s*kWh)',
            r'Ariya\s*(?:87kWh|87\s*kWh)',
            r'Ariya\s*(?:e-4ORCE|e4ORCE)',
            r'YE15',
        ]
        for pattern in ariya_patterns:
            if re.search(pattern, html_text, re.IGNORECASE):
                ariya_info = {'make': 'Nissan', 'model': 'Ariya', 'variant_code': 'YE15'}
                if '63' in pattern:
                    ariya_info['kwh'] = '63'
                elif '87' in pattern:
                    ariya_info['kwh'] = '87'
                elif 'e-4ORCE' in pattern.lower() or 'e4orce' in pattern.lower():
                    ariya_info['awd'] = True
                if ariya_info not in results:
                    results.append(ariya_info)

        return results

    def enrich_with_nissan_context(self, payload: dict, html_text: str) -> dict:
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

        pack_info = detect_nissan_battery_pack('', html_text)
        if pack_info:
            payload['properties']['battery_pack'] = {
                'value': pack_info['name'],
                'kwh': pack_info['kwh'],
                'evidence_quote': f'Found pack code reference in page',
                'confidence': 0.8,
            }

        return payload
