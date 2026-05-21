import re
import structlog

logger = structlog.get_logger()

PN_RE = re.compile(r'A\s?\d{3}\s?\d{3}\s?\d{4}[A-Z]?')
GENERIC_RE = re.compile(r'[A-Z]\s?\d{3}\s?\d{3}\s?\d{4}')
OEM_CODE_RE = re.compile(r'(?:A\s?0{2,3}|D[ABF]\s?0{2,3})\d{6,}')


def normalize_mercedes_pn(raw: str) -> str:
    raw = raw.strip().upper().replace(' ', '').replace('-', '')
    return raw


class MercedesAdapter:
    BRAND = 'mercedes'
    SOURCE_DOMAIN = 'webautocats.com'
    SOURCE_KIND = 'dealer_catalog'

    def __init__(self):
        self.logger = logger

    def extract_part_numbers(self, html_text: str) -> list[dict]:
        results = []
        matches = PN_RE.findall(html_text)
        for m in set(matches):
            norm = normalize_mercedes_pn(m)
            if len(norm) >= 8:
                results.append({
                    'raw': m,
                    'normalized': norm,
                    'brand': self.BRAND,
                    'pn_type': 'service',
                })
        generic = OEM_CODE_RE.findall(html_text)
        for m in generic:
            norm = normalize_mercedes_pn(m)
            if len(norm) >= 8 and norm not in [r['normalized'] for r in results]:
                results.append({
                    'raw': m,
                    'normalized': norm,
                    'brand': self.BRAND,
                    'pn_type': 'service',
                })
        return results

    def build_search_url(self, part_number: str) -> str:
        pn = part_number.replace('/', '%2F').replace(' ', '+')
        return f"https://www.webautocats.com/search?query={pn}"

    def build_part_url(self, part_number: str) -> str:
        pn = part_number.replace('/', '%2F').replace(' ', '+')
        return f"https://www.webautocats.com/part/{pn}"

    def extract_vehicle_info(self, html_text: str) -> list[dict]:
        results = []
        year_match = re.findall(r'\b(201[5-9]|202[0-9])\b', html_text)
        model_patterns = [
            r'EQ[A-Z]{1,3}',
            r'([A-Z]\s?Class)',
            r'GLS\s?\d{3}',
            r'EQS\s?\d{3}',
            r'EQE\s?\d{3}',
        ]
        for pattern in model_patterns:
            for match in re.finditer(pattern, html_text, re.IGNORECASE):
                model_text = match.group(0)
                years = sorted(set(int(y) for y in year_match)) if year_match else [2020]
                results.append({
                    'make': 'Mercedes-Benz',
                    'model': model_text.strip(),
                    'variant_code': None,
                    'year_from': years[0],
                    'year_to': years[-1] if len(years) > 1 else None,
                    'engine_code': None,
                })
        return results

    def enrich_with_mercedes_context(self, payload: dict, html_text: str) -> dict:
        if 'properties' not in payload:
            payload['properties'] = {}
        chemistry_patterns = {
            'NMC': 'NMC', 'NCM': 'NMC', 'LFP': 'LFP', 'LTO': 'LTO'
        }
        for key, val in chemistry_patterns.items():
            if key in html_text.upper():
                payload['properties']['chemistry'] = {
                    'value': val,
                    'evidence_quote': f'Found {key} in Mercedes EPC',
                    'confidence': 0.8,
                }
                break
        return payload
