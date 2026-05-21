import re
from typing import Optional
import structlog

logger = structlog.get_logger()

PNCODES_RE = re.compile(r'BYD[-]?\w{4,12}')
GENERIC_RE = re.compile(r'[A-Z]{2,4}\d{5,10}')

STANDARDIZED_CHEMISTRY = {
    'NCM': 'NCM',
    'NMC': 'NCM',
    'LFP': 'LiFePO4',
    'LTO': 'LiTiO',
    'NCA': 'NCA',
}


def normalize_byd_pn(raw: str) -> str:
    raw = raw.strip().upper().replace(' ', '').replace('-', '')
    if raw.startswith('BYD'):
        return raw
    if len(raw) >= 5:
        return raw
    return raw


def detect_byd_supersession(normalized: str, html_text: str) -> Optional[str]:
    supersession_patterns = [
        r'(?:superseded|replaced|successor)[:\s]+([A-Z0-9]{6,})',
        r'(?:alt|previous|former)[:\s]+([A-Z0-9]{6,})',
        r'\b([A-Z0-9]{6,})\s+(?:replaces|replaced)',
    ]
    for pattern in supersession_patterns:
        match = re.search(pattern, html_text, re.IGNORECASE)
        if match:
            return normalize_byd_pn(match.group(1))
    return None


class BYDAdapter:
    BRAND = 'byd'
    SOURCE_DOMAIN = 'byd.com'
    SOURCE_KIND = 'dealer_catalog'

    BYD_MODELS = {
        'Seal': {'type': 'sedan', 'years': (2022, 2026)},
        'Han': {'type': 'sedan', 'years': (2020, 2026)},
        'Tang': {'type': 'suv', 'years': (2019, 2026)},
        'Dolphin': {'type': 'hatchback', 'years': (2021, 2026)},
        'Yuan': {'type': 'suv', 'years': (2019, 2026)},
        'Seagull': {'type': 'hatchback', 'years': (2023, 2026)},
        'Yangwang': {'type': 'suv', 'years': (2023, 2026)},
    }

    def __init__(self):
        self.logger = logger

    def extract_part_numbers(self, html_text: str) -> list[dict]:
        results = []
        byd_matches = PNCODES_RE.findall(html_text)
        for m in set(byd_matches):
            norm = normalize_byd_pn(m)
            if len(norm) >= 5:
                results.append({
                    'raw': m,
                    'normalized': norm,
                    'brand': self.BRAND,
                    'pn_type': 'service',
                })
        generic_matches = GENERIC_RE.findall(html_text)
        for m in set(generic_matches):
            norm = normalize_byd_pn(m)
            if len(norm) >= 6 and not any(m in str(r['raw']) for r in results):
                results.append({
                    'raw': m,
                    'normalized': norm,
                    'brand': self.BRAND,
                    'pn_type': 'service',
                })
        return results

    def build_search_url(self, part_number: str) -> str:
        pn = part_number.replace('/', '%2F').replace(' ', '+')
        return f"https://www.byd.com/search?q={pn}"

    def build_part_url(self, part_number: str) -> str:
        pn = part_number.replace('/', '%2F')
        return f"https://www.byd.com/parts/{pn}"

    def extract_vehicle_info(self, html_text: str) -> list[dict]:
        results = []
        year_match = re.findall(r'\b(19\d{2}|20\d{2})\b', html_text)
        years = sorted(set(int(y) for y in year_match if 2016 <= int(y) <= 2030)) if year_match else []

        for model, info in self.BYD_MODELS.items():
            pattern = rf'\b{model}\b'
            if re.search(pattern, html_text, re.IGNORECASE):
                results.append({
                    'make': 'BYD',
                    'model': model,
                    'variant_code': info['type'],
                    'year_from': years[0] if years else info['years'][0],
                    'year_to': years[-1] if years else info['years'][1],
                    'engine_code': None,
                })

        return results

    def enrich_with_byd_context(self, payload: dict, html_text: str) -> dict:
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
