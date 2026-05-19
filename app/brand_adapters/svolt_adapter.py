import re
import structlog

logger = structlog.get_logger()

PN_RE = re.compile(r'[A-Z]{1,3}\d{2,4}[A-Z0-9]{0,6}')
GENERIC_RE = re.compile(r'[A-Z]{2,3}[-_]?\d{2,5}[A-Z0-9]{0,4}')

STANDARDIZED_CHEMISTRY = {
    'LFP': 'LFP',
    'LI-FE': 'LFP',
    'LIFEPO4': 'LFP',
    'NMC': 'NMC',
    'NCM': 'NMC',
    'NCA': 'NCA',
    'LTO': 'LTO',
    'LITI': 'LTO',
}


def normalize_svolt_pn(raw: str) -> str:
    raw = raw.strip().upper().replace(' ', '').replace('-', '').replace('_', '')
    return raw


class SvoltAdapter:
    BRAND = 'svolt'
    SOURCE_DOMAIN = 'svolt-eu.com'
    SOURCE_KIND = 'manufacturer_catalog'

    def __init__(self):
        self.logger = logger

    def extract_part_numbers(self, html_text: str) -> list[dict]:
        results = []
        matches = PN_RE.findall(html_text)
        for m in set(matches):
            norm = normalize_svolt_pn(m)
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
        return f"https://www.svolt-eu.com/en/products/?search={pn}"

    def build_part_url(self, part_number: str) -> str:
        pn = part_number.replace('/', '%2F').replace(' ', '+')
        return f"https://www.svolt-eu.com/en/products/{pn}"

    def extract_vehicle_info(self, html_text: str) -> list[dict]:
        results = []
        year_match = re.findall(r'\b(2020|2021|2022|2023|2024|2025)\b', html_text)
        model_patterns = [
            r'(Citro[eé]n\s+e-C3|Peugeot\s+e-208|Opel\s+Corsa-e|Fiat\s+500e|Vauxhall\s+Corsa-e)',
        ]
        for pattern in model_patterns:
            for match in re.finditer(pattern, html_text, re.IGNORECASE):
                model_text = match.group(0)
                years = sorted(set(int(y) for y in year_match)) if year_match else [2024]
                results.append({
                    'make': 'Stellantis',
                    'model': model_text,
                    'variant_code': None,
                    'year_from': years[0],
                    'year_to': years[-1],
                    'engine_code': None,
                })
        return results

    def enrich_with_svolt_context(self, payload: dict, html_text: str) -> dict:
        if 'properties' not in payload:
            payload['properties'] = {}
        for chem_key, chem_val in STANDARDIZED_CHEMISTRY.items():
            if chem_key in html_text.upper():
                payload['properties']['chemistry'] = {
                    'value': chem_val,
                    'evidence_quote': f'Found {chem_key} reference in SVOLT page',
                    'confidence': 0.7,
                }
                break
        return payload
