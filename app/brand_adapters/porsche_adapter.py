import re
from typing import Optional
import structlog

logger = structlog.get_logger()

PNCODES_RE = re.compile(r'[A-Z]{2,4}\d{2,4}[A-Z0-9]{2,8}')
GENERIC_RE = re.compile(r'0\d{3,7}[A-Z]?')

STANDARDIZED_CHEMISTRY = {
    'NCM': 'NCM',
    'NMC': 'NCM',
    'LFP': 'LiFePO4',
    'LTO': 'LiTiO',
    'NCA': 'NCA',
}


def normalize_porsche_pn(raw: str) -> str:
    raw = raw.strip().upper().replace(' ', '').replace('-', '')
    raw = re.sub(r'\b(0K|OK)\b', 'OK', raw)
    if raw.startswith('970'):
        return raw
    if len(raw) >= 6:
        return raw
    return raw


def detect_porsche_supersession(normalized: str, html_text: str) -> Optional[str]:
    supersession_patterns = [
        r'(?:superseded|replaced| Nachfolger)[:\s]+([A-Z0-9]{6,})',
        r'(?:alt|previous|former)[:\s]+([A-Z0-9]{6,})',
        r'\b([A-Z0-9]{6,})\s+(?:ist|was)\s+(?:der|das)\s+(?:Nachfolger|alt)',
    ]
    for pattern in supersession_patterns:
        match = re.search(pattern, html_text, re.IGNORECASE)
        if match:
            return normalize_porsche_pn(match.group(1))
    return None


class PorscheAdapter:
    BRAND = 'porsche'
    SOURCE_DOMAIN = 'teile.com'
    SOURCE_KIND = 'dealer_catalog'

    def __init__(self):
        self.logger = logger

    def extract_part_numbers(self, html_text: str) -> list[dict]:
        results = []
        pnc_matches = PNCODES_RE.findall(html_text)
        for m in set(pnc_matches):
            norm = normalize_porsche_pn(m)
            if len(norm) >= 5:
                results.append({
                    'raw': m,
                    'normalized': norm,
                    'brand': self.BRAND,
                    'pn_type': 'service',
                })
        return results

    def build_search_url(self, part_number: str) -> str:
        pn = part_number.replace('/', '%2F').replace(' ', '+')
        return f"https://www.teile.com/Porsche/search/?q={pn}"

    def build_part_url(self, part_number: str) -> str:
        pn = part_number.replace('/', '%2F')
        return f"https://www.teile.com/Porsche/parts/{pn}"

    def extract_vehicle_info(self, html_text: str) -> list[dict]:
        results = []
        year_match = re.findall(r'\b(19\d{2}|20\d{2})\b', html_text)
        model_patterns = [
            r'(Taycan|Cayenne|Panamera|911|718|Macan|Cayman|Boxster)[\s-]+(\w+)?',
        ]
        for pattern in model_patterns:
            for match in re.finditer(pattern, html_text, re.IGNORECASE):
                model = match.group(1)
                variant = match.group(2) or ''
                years = []
                if year_match:
                    years = sorted(set(int(y) for y in year_match if 2000 <= int(y) <= 2030))
                results.append({
                    'make': 'Porsche',
                    'model': model,
                    'variant_code': variant.strip(),
                    'year_from': years[0] if years else None,
                    'year_to': years[-1] if years else None,
                    'engine_code': None,
                })
        return results

    def enrich_with_porsche_context(self, payload: dict, html_text: str) -> dict:
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
