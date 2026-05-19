import re
import structlog

logger = structlog.get_logger()

PN_RE = re.compile(r'\d{2,4}[A-Z]\d{2,4}[A-Z0-9]{0,4}')
GENERIC_RE = re.compile(r'[A-Z]{2,3}[-_]?\d{2,5}')

STANDARDIZED_CHEMISTRY = {
    'NMC': 'NMC',
    'NCM': 'NMC',
    'NCA': 'NCA',
    'LFP': 'LFP',
}


def normalize_samsung_pn(raw: str) -> str:
    raw = raw.strip().upper().replace(' ', '').replace('-', '')
    return raw


class SamsungSDIAdapter:
    BRAND = 'samsung_sdi'
    SOURCE_DOMAIN = 'samsungsdi.com'
    SOURCE_KIND = 'manufacturer_catalog'

    def __init__(self):
        self.logger = logger

    def extract_part_numbers(self, html_text: str) -> list[dict]:
        results = []
        matches = PN_RE.findall(html_text)
        for m in set(matches):
            norm = normalize_samsung_pn(m)
            if len(norm) >= 5:
                results.append({
                    'raw': m,
                    'normalized': norm,
                    'brand': self.BRAND,
                    'pn_type': 'service',
                })
        generic = GENERIC_RE.findall(html_text)
        for m in generic:
            norm = normalize_samsung_pn(m)
            if len(norm) >= 5 and norm not in [r['normalized'] for r in results]:
                results.append({
                    'raw': m,
                    'normalized': norm,
                    'brand': self.BRAND,
                    'pn_type': 'service',
                })
        return results

    def build_search_url(self, part_number: str) -> str:
        pn = part_number.replace('/', '%2F').replace(' ', '+')
        return f"https://www.samsungsdi.com/automotive-battery/products/?q={pn}"

    def build_part_url(self, part_number: str) -> str:
        pn = part_number.replace('/', '%2F').replace(' ', '+')
        return f"https://www.samsungsdi.com/automotive-battery/products/{pn}"

    def extract_vehicle_info(self, html_text: str) -> list[dict]:
        results = []
        year_match = re.findall(r'\b(2018|2019|2020|2021|2022|2023|2024|2025)\b', html_text)
        model_patterns = [
            r'(BMW\s+i3|Fiat\s+500e|Porsche\s+Cayenne\s+E-Hybrid|Genesis\s+G80|Genesis\s+GV60|Audi\s+e-tron)',
        ]
        for pattern in model_patterns:
            for match in re.finditer(pattern, html_text, re.IGNORECASE):
                model_text = match.group(0)
                years = sorted(set(int(y) for y in year_match)) if year_match else [2020]
                results.append({
                    'make': 'OEM',
                    'model': model_text,
                    'variant_code': None,
                    'year_from': years[0],
                    'year_to': years[-1],
                    'engine_code': None,
                })
        return results

    def enrich_with_samsung_context(self, payload: dict, html_text: str) -> dict:
        if 'properties' not in payload:
            payload['properties'] = {}
        for chem_key, chem_val in STANDARDIZED_CHEMISTRY.items():
            if chem_key in html_text.upper():
                payload['properties']['chemistry'] = {
                    'value': chem_val,
                    'evidence_quote': f'Found {chem_key} reference in Samsung SDI page',
                    'confidence': 0.75,
                }
                break
        return payload
