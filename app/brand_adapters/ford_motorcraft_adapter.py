import re
from typing import Optional
import structlog

logger = structlog.get_logger()

FORD_PN_RE = re.compile(r'[A-Z]{2}[-]?\d{5,8}[-]?[A-Z]?')
FORD_PN_ALT_RE = re.compile(r'F\d{2}[-]?\d{6}')
MOTORCRAFT_PN_RE = re.compile(r'MU[-]?\d{5}[-]?[A-Z]?')

STANDARDIZED_CHEMISTRY = {
    'NCM': 'NCM',
    'NMC': 'NCM',
    'LFP': 'LiFePO4',
    'LTO': 'LiTiO',
    'NCA': 'NCA',
}


def normalize_ford_pn(raw: str) -> str:
    raw = raw.strip().upper().replace(' ', '').replace('-', '')
    return raw


class FordMotorcraftAdapter:
    BRAND = 'ford'
    SOURCE_DOMAIN = 'motorcraft.com'
    SOURCE_KIND = 'dealer_portal'

    def __init__(self):
        self.logger = logger

    def extract_part_numbers(self, html_text: str) -> list[dict]:
        results = []
        seen = set()

        for pattern in [FORD_PN_RE, FORD_PN_ALT_RE, MOTORCRAFT_PN_RE]:
            for match in pattern.finditer(html_text):
                raw = match.group(0)
                if raw in seen:
                    continue
                seen.add(raw)
                norm = normalize_ford_pn(raw)
                if len(norm) >= 6:
                    results.append({
                        'raw': raw,
                        'normalized': norm,
                        'brand': self.BRAND,
                        'pn_type': 'service',
                    })

        return results

    def build_search_url(self, part_number: str) -> str:
        pn = part_number.replace('/', '%2F').replace(' ', '+')
        return f"https://www.motorcraft.com/parts/search/?q={pn}"

    def extract_vehicle_info(self, html_text: str) -> list[dict]:
        results = []
        year_match = re.findall(r'\b(19\d{2}|20\d{2})\b', html_text)

        mustang_mache_pattern = r'(Mustang\s*Mach-E)[\s-]*(201A|312A|912A)?'
        f150_lightning_pattern = r'(F-150\s*Lightning)[\s-]*(Pro|XLT|Lariat|Platinum)?'
        etransit_pattern = r'(E-Transit)'

        vehicle_patterns = [
            (mustang_mache_pattern, 'Mustang Mach-E'),
            (f150_lightning_pattern, 'F-150 Lightning'),
            (etransit_pattern, 'E-Transit'),
        ]

        for pattern, base_model in vehicle_patterns:
            for match in re.finditer(pattern, html_text, re.IGNORECASE):
                model = match.group(1).strip()
                variant = match.group(2) or ''
                years = []
                if year_match:
                    years = sorted(set(int(y) for y in year_match if 2000 <= int(y) <= 2030))
                results.append({
                    'make': 'Ford',
                    'model': base_model,
                    'variant_code': variant.strip(),
                    'year_from': years[0] if years else None,
                    'year_to': years[-1] if years else None,
                    'engine_code': None,
                })

        return results

    def enrich_with_ford_context(self, payload: dict, html_text: str) -> dict:
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
