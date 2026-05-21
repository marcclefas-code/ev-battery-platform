import re
from typing import Optional
import structlog

logger = structlog.get_logger()

TOYOTA_PN_RE = re.compile(r'\d{5}[-]?\d{5}|[A-Z]{2}\d{3}[-]?\d{5,6}')
GENERIC_RE = re.compile(r'0\d{3,7}[A-Z]?')

STANDARDIZED_CHEMISTRY = {
    'NCM': 'NCM',
    'NMC': 'NCM',
    'LFP': 'LiFePO4',
    'LTO': 'LiTiO',
    'NCA': 'NCA',
}

TOYOTA_MODELS = {
    'bZ4X': {'year_from': 2022, 'battery_kwh': 72.8, 'type': 'BEV'},
    'bZ3': {'year_from': 2023, 'battery_kwh': 72.0, 'type': 'BEV'},
    'RAV4 Prime': {'year_from': 2021, 'battery_kwh': 18.1, 'type': 'PHEV'},
    'Prius Prime': {'year_from': 2023, 'battery_kwh': 13.6, 'type': 'PHEV'},
    'Sequoia Hybrid': {'year_from': 2023, 'battery_kwh': None, 'type': 'Hybrid'},
    'Sienna Hybrid': {'year_from': 2021, 'battery_kwh': None, 'type': 'Hybrid'},
    'Highlander Hybrid': {'year_from': 2021, 'battery_kwh': None, 'type': 'Hybrid'},
    'Corolla Cross Hybrid': {'year_from': 2022, 'battery_kwh': None, 'type': 'Hybrid'},
}


def normalize_toyota_pn(raw: str) -> str:
    raw = raw.strip().upper().replace(' ', '').replace('-', '')
    if len(raw) >= 8:
        return raw
    return raw


def detect_toyota_supersession(normalized: str, html_text: str) -> Optional[str]:
    supersession_patterns = [
        r'(?:superseded|replaced|supersedes)[:\s]+([A-Z0-9]{8,})',
        r'(?:alt|previous|former)[:\s]+([A-Z0-9]{8,})',
        r'\b([A-Z0-9]{8,})\s+(?:replaces|supersedes)',
    ]
    for pattern in supersession_patterns:
        match = re.search(pattern, html_text, re.IGNORECASE)
        if match:
            return normalize_toyota_pn(match.group(1))
    return None


class ToyotaAdapter:
    BRAND = 'toyota'
    SOURCE_DOMAIN = 'toyota.com'
    SOURCE_DOMAIN_ALT = 'parts.toyota.com'
    SOURCE_KIND = 'dealer_portal'

    def __init__(self):
        self.logger = logger

    def extract_part_numbers(self, html_text: str) -> list[dict]:
        results = []
        pn_matches = TOYOTA_PN_RE.findall(html_text)
        for m in set(pn_matches):
            norm = normalize_toyota_pn(m)
            if len(norm) >= 8:
                prefix = norm[:2]
                if prefix in ('81', '82', '84', '88'):
                    pn_type = 'hybrid_battery'
                else:
                    pn_type = 'service'
                results.append({
                    'raw': m,
                    'normalized': norm,
                    'brand': self.BRAND,
                    'pn_type': pn_type,
                })
        return results

    def build_search_url(self, part_number: str) -> str:
        pn = part_number.replace('/', '%2F').replace(' ', '+')
        return f"https://parts.toyota.com/search/?q={pn}"

    def extract_vehicle_info(self, html_text: str) -> list[dict]:
        results = []
        year_match = re.findall(r'\b(19\d{2}|20\d{2})\b', html_text)
        years = sorted(set(int(y) for y in year_match if 2000 <= int(y) <= 2030)) if year_match else []

        model_patterns = [
            r'bZ4X',
            r'bZ3',
            r'RAV4\s+Prime',
            r'Prius\s+Prime',
            r'Sequoia\s+Hybrid',
            r'Sienna\s+Hybrid',
            r'Highlander\s+Hybrid',
            r'Corolla\s+Cross\s+Hybrid',
        ]

        for pattern in model_patterns:
            match = re.search(pattern, html_text, re.IGNORECASE)
            if match:
                model_name = match.group(0).replace(' ', '_')
                model_info = TOYOTA_MODELS.get(match.group(0), {})

                results.append({
                    'make': 'Toyota',
                    'model': model_name,
                    'variant_code': None,
                    'year_from': years[0] if years else model_info.get('year_from'),
                    'year_to': years[-1] if years else None,
                    'engine_code': None,
                })

        if not results:
            for model_name, model_info in TOYOTA_MODELS.items():
                if model_name.lower() in html_text.lower():
                    results.append({
                        'make': 'Toyota',
                        'model': model_name,
                        'variant_code': None,
                        'year_from': years[0] if years else model_info.get('year_from'),
                        'year_to': years[-1] if years else None,
                        'engine_code': None,
                    })

        return results

    def enrich_with_toyota_context(self, payload: dict, html_text: str) -> dict:
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
