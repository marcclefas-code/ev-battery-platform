import re
from typing import Optional
import structlog

logger = structlog.get_logger()

PNCODES_RE = re.compile(r'T\d{6,8}[A-Z]?')

STANDARDIZED_CHEMISTRY = {
    'NCM': 'NCM',
    'NMC': 'NCM',
    'LFP': 'LiFePO4',
    'LTO': 'LiTiO',
    'NCA': 'NCA',
}

TESLA_MODELS = ['Model S', 'Model 3', 'Model X', 'Model Y', 'Cybertruck', 'Semi']


def normalize_tesla_pn(raw: str) -> str:
    raw = raw.strip().upper().replace(' ', '')
    if '-' in raw:
        return raw
    return raw


def detect_tesla_supersession(normalized: str, html_text: str) -> Optional[str]:
    supersession_patterns = [
        r'(?:superseded|replaced|supersedes)[:\s]+([A-Z0-9\-]{6,})',
        r'(?:previous|former|old)[:\s]+([A-Z0-9\-]{6,})',
        r'\b([A-Z0-9\-]{6,})\s+(?:replaces|supersedes)',
    ]
    for pattern in supersession_patterns:
        match = re.search(pattern, html_text, re.IGNORECASE)
        if match:
            return normalize_tesla_pn(match.group(1))
    return None


class TeslaAdapter:
    BRAND = 'tesla'
    SOURCE_DOMAIN = 'service.tesla.com'
    SOURCE_KIND = 'dealer_portal'

    def __init__(self):
        self.logger = logger

    async def extract_part_numbers(self, html_text: str) -> list[dict]:
        results = []
        pnc_matches = PNCODES_RE.findall(html_text)
        for m in set(pnc_matches):
            norm = normalize_tesla_pn(m)
            if len(norm) >= 6:
                results.append({
                    'raw': m,
                    'normalized': norm,
                    'brand': self.BRAND,
                    'pn_type': 'service',
                })
        return results

    def build_search_url(self, part_number: str) -> str:
        pn = part_number.replace('/', '%2F').replace(' ', '+')
        return f"https://service.tesla.com/search/?q={pn}"

    def build_part_url(self, part_number: str) -> str:
        pn = part_number.replace('/', '%2F')
        return f"https://service.tesla.com/parts/{pn}"

    async def extract_vehicle_info(self, html_text: str) -> list[dict]:
        results = []
        year_match = re.findall(r'\b(201[2-9]|202[0-9])\b', html_text)
        model_pattern = '|'.join(re.escape(m) for m in TESLA_MODELS)
        pattern = rf'({model_pattern})[\s-]+(\w+)?'
        for match in re.finditer(pattern, html_text, re.IGNORECASE):
            model = match.group(1)
            variant = match.group(2) or ''
            years = []
            if year_match:
                years = sorted(set(int(y) for y in year_match if 2012 <= int(y) <= 2030))
            results.append({
                'make': 'Tesla',
                'model': model,
                'variant_code': variant.strip(),
                'year_from': years[0] if years else None,
                'year_to': years[-1] if years else None,
                'engine_code': None,
            })
        return results

    async def enrich_with_tesla_context(self, payload: dict, html_text: str) -> dict:
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
