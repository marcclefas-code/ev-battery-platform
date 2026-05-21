import re
from typing import Optional
import structlog

logger = structlog.get_logger()

BMW_PN_RE = re.compile(r'\d{11}')
BMW_ETK_RE = re.compile(r'\d{2}\s?\d{2}\s?\d\s?\d{3}\s?\d{3}')
GENERIC_RE = re.compile(r'0\d{3,7}[A-Z]?')

STANDARDIZED_CHEMISTRY = {
    'NCM': 'NCM',
    'NMC': 'NCM',
    'LFP': 'LiFePO4',
    'LTO': 'LiTiO',
    'NCA': 'NCA',
}

BATTERY_CODES = {
    'iX xDrive40': '111Ah',
    'iX xDrive50': '111Ah+ext',
    'iX M60': '111Ah+ext',
    'i4 eDrive35': '70kWh',
    'i4 eDrive40': '83kWh',
    'i4 M50': '83kWh',
    'i5 eDrive40': '84kWh',
    'i5 M60 xDrive': '84kWh',
    'i7 xDrive60': '105kWh',
    'iX1 xDrive30': '64kWh',
    'iX2 xDrive30': '64kWh',
    'Cooper SE': '32kWh',
    'Countryman Electric': '66kWh',
    'Aceman': '54kWh',
    'Spectre': '102kWh',
}

EV_MODELS = {
    'BMW': ['i3', 'i3s', 'i4', 'i5', 'i7', 'iX', 'iX1', 'iX2', 'i5 Touring'],
    'MINI': ['Cooper SE', 'Countryman Electric', 'Aceman'],
    'Rolls-Royce': ['Spectre'],
}


def normalize_bmw_pn(raw: str) -> str:
    raw = raw.strip().upper().replace(' ', '').replace('-', '')
    if len(raw) == 11 and raw.isdigit():
        return raw
    if re.match(r'^\d{2}\s?\d{2}\s?\d\s?\d{3}\s?\d{3}$', raw):
        return raw.replace(' ', '')
    return raw


def detect_bmw_supersession(normalized: str, html_text: str) -> Optional[str]:
    supersession_patterns = [
        r'(?:superseded|replaced|Nachfolger|ERSETZT)[:\s]+([A-Z0-9]{6,})',
        r'(?:alt|previous|former|vormals)[:\s]+([A-Z0-9]{6,})',
        r'\b([A-Z0-9]{6,})\s+(?:ist|was)\s+(?:der|das)\s+(?:Nachfolger|alt)',
    ]
    for pattern in supersession_patterns:
        match = re.search(pattern, html_text, re.IGNORECASE)
        if match:
            return normalize_bmw_pn(match.group(1))
    return None


class BMWGroupAdapter:
    BRAND = 'bmw_group'
    SOURCE_DOMAIN = 'bmwgroup.com'
    SOURCE_DOMAIN_ALT = 'bmwgroupparts.com'
    SOURCE_KIND = 'dealer_portal'

    def __init__(self):
        self.logger = logger

    def extract_part_numbers(self, html_text: str) -> list[dict]:
        results = []
        seen = set()
        bmw_matches = BMW_PN_RE.findall(html_text)
        for m in set(bmw_matches):
            norm = normalize_bmw_pn(m)
            if len(norm) >= 11 and norm not in seen:
                seen.add(norm)
                results.append({
                    'raw': m,
                    'normalized': norm,
                    'brand': self.BRAND,
                    'pn_type': 'service',
                })
        etk_matches = BMW_ETK_RE.findall(html_text)
        for m in set(etk_matches):
            norm = normalize_bmw_pn(m)
            if norm not in seen:
                seen.add(norm)
                results.append({
                    'raw': m,
                    'normalized': norm,
                    'brand': self.BRAND,
                    'pn_type': 'etk',
                })
        return results

    def build_search_url(self, part_number: str) -> str:
        pn = part_number.replace('/', '%2F').replace(' ', '+')
        return f"https://www.bmwgroupparts.com/search?q={pn}"

    def build_part_url(self, part_number: str) -> str:
        pn = part_number.replace('/', '%2F').replace(' ', '')
        return f"https://www.bmwgroupparts.com/parts/{pn}"

    def extract_vehicle_info(self, html_text: str) -> list[dict]:
        results = []
        year_match = re.findall(r'\b(19\d{2}|20\d{2})\b', html_text)
        years = sorted(set(int(y) for y in year_match if 2000 <= int(y) <= 2030)) if year_match else []

        all_models = []
        for models in EV_MODELS.values():
            all_models.extend(models)

        model_pattern = r'\b(' + '|'.join(re.escape(m) for m in all_models) + r')\b'
        variant_pattern = r'(xDrive40|xDrive50|M60|eDrive35|eDrive40|M50|eDrive40|M60 xDrive|xDrive30|SE|Countryman Electric|Aceman|Spectre)'

        for match in re.finditer(model_pattern, html_text, re.IGNORECASE):
            model = match.group(1)
            variant_match = re.search(variant_pattern, html_text[match.end():match.end()+50], re.IGNORECASE)
            variant = variant_match.group(1) if variant_match else ''

            make = 'BMW'
            if model in EV_MODELS['MINI']:
                make = 'MINI'
            elif model in EV_MODELS['Rolls-Royce']:
                make = 'Rolls-Royce'

            battery_code = None
            if variant:
                for code, capacity in BATTERY_CODES.items():
                    if variant.lower() in code.lower() or code.lower() in variant.lower():
                        battery_code = capacity
                        break

            results.append({
                'make': make,
                'model': model,
                'variant_code': variant,
                'year_from': years[0] if years else None,
                'year_to': years[-1] if years else None,
                'engine_code': battery_code,
            })
        return results

    def enrich_with_bmw_context(self, payload: dict, html_text: str) -> dict:
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
