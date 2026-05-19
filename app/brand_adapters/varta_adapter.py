import re
import structlog

logger = structlog.get_logger()

PN_RE = re.compile(r'AGM\s*\d{2,4}|[\d]{2,4}\s*AH', re.IGNORECASE)
GENERIC_RE = re.compile(r'[A-Z]{2,3}[-_]?\d{2,5}[A-Z]?')


def normalize_varta_pn(raw: str) -> str:
    raw = raw.strip().upper().replace(' ', '').replace('-', '')
    return raw


class VartaAdapter:
    BRAND = 'varta'
    SOURCE_DOMAIN = 'varta-automotive.com'
    SOURCE_KIND = 'manufacturer_catalog'

    def __init__(self):
        self.logger = logger

    def extract_part_numbers(self, html_text: str) -> list[dict]:
        results = []
        matches = PN_RE.findall(html_text)
        for m in set(matches):
            norm = normalize_varta_pn(m)
            if len(norm) >= 4:
                results.append({
                    'raw': m,
                    'normalized': norm,
                    'brand': self.BRAND,
                    'pn_type': 'service',
                })
        generic = GENERIC_RE.findall(html_text)
        for m in generic:
            norm = normalize_varta_pn(m)
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
        return f"https://www.varta-automotive.com/en-en/products/car-batteries/?q={pn}"

    def build_part_url(self, part_number: str) -> str:
        pn = part_number.replace('/', '%2F').replace(' ', '+')
        return f"https://www.varta-automotive.com/en-en/products/car-batteries/{pn}"

    def extract_vehicle_info(self, html_text: str) -> list[dict]:
        results = []
        year_match = re.findall(r'\b(2022|2023|2024|2025)\b', html_text)
        model_patterns = [
            r'(Porsche\s+911\s+T-Hybrid|Porsche\s+Cayenne\s+E-Hybrid|BMW\s+\d+[a-zA-Z]+|Mercedes\s+[\w\s-]+)',
        ]
        for pattern in model_patterns:
            for match in re.finditer(pattern, html_text, re.IGNORECASE):
                model_text = match.group(0)
                years = sorted(set(int(y) for y in year_match)) if year_match else [2024]
                results.append({
                    'make': 'OEM',
                    'model': model_text,
                    'variant_code': None,
                    'year_from': years[0],
                    'year_to': years[-1],
                    'engine_code': None,
                })
        return results

    def extract_fitment_table(self, html_text: str) -> list[dict]:
        results = []
        rows = re.findall(r'<tr[^>]*>.*?</tr>', html_text, re.DOTALL)
        for row in rows:
            cells = re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', row, re.DOTALL)
            if len(cells) >= 3:
                vehicle_cell = re.sub(r'<[^>]+>', '', cells[0]).strip()
                pn_cell = re.sub(r'<[^>]+>', '', cells[1]).strip()
                if vehicle_cell and pn_cell:
                    results.append({
                        'vehicle': vehicle_cell,
                        'part_number': pn_cell,
                    })
        return results

    def enrich_with_varta_context(self, payload: dict, html_text: str) -> dict:
        if 'properties' not in payload:
            payload['properties'] = {}
        if 'agm' in html_text.lower():
            payload['properties']['battery_type'] = {
                'value': 'AGM',
                'evidence_quote': 'Found AGM reference in Varta page',
                'confidence': 0.85,
            }
        return payload
