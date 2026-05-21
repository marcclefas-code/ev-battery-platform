import re
from typing import Optional
import structlog

logger = structlog.get_logger()

SK_ON_PN_RE = re.compile(r'SK[_-]?ON[_-]?\w{6,10}')
SKO_PN_RE = re.compile(r'SKO\d{7,10}')
SKE_PN_RE = re.compile(r'SKE\d{7}')
GENERIC_RE = re.compile(r'0\d{3,7}[A-Z]?')

STANDARDIZED_CHEMISTRY = {
    'NCM': 'NCM',
    'NMC': 'NCM',
    'LFP': 'LiFePO4',
    'LTO': 'LiTiO',
    'NCA': 'NCA',
}


def normalize_sk_on_pn(raw: str) -> str:
    raw = raw.strip().upper().replace(' ', '').replace('-', '').replace('_', '')
    return raw


def detect_sk_on_supersession(normalized: str, html_text: str) -> Optional[str]:
    supersession_patterns = [
        r'(?:superseded|replaced| Nachfolger)[:\s]+([A-Z0-9]{6,})',
        r'(?:alt|previous|former)[:\s]+([A-Z0-9]{6,})',
        r'\b([A-Z0-9]{6,})\s+(?:ist|was)\s+(?:der|das)\s+(?:Nachfolger|alt)',
    ]
    for pattern in supersession_patterns:
        match = re.search(pattern, html_text, re.IGNORECASE)
        if match:
            return normalize_sk_on_pn(match.group(1))
    return None


class SKOnAdapter:
    BRAND = 'sk_on'
    SOURCE_DOMAIN = 'skon.com'
    SOURCE_KIND = 'battery_supplier'

    def __init__(self):
        self.logger = logger

    def extract_part_numbers(self, html_text: str) -> list[dict]:
        results = []
        seen = set()

        sk_on_matches = SK_ON_PN_RE.findall(html_text)
        for m in set(sk_on_matches):
            norm = normalize_sk_on_pn(m)
            if len(norm) >= 6 and norm not in seen:
                seen.add(norm)
                results.append({
                    'raw': m,
                    'normalized': norm,
                    'brand': self.BRAND,
                    'pn_type': 'service',
                })

        sko_matches = SKO_PN_RE.findall(html_text)
        for m in set(sko_matches):
            norm = normalize_sk_on_pn(m)
            if len(norm) >= 7 and norm not in seen:
                seen.add(norm)
                results.append({
                    'raw': m,
                    'normalized': norm,
                    'brand': self.BRAND,
                    'pn_type': 'service',
                })

        ske_matches = SKE_PN_RE.findall(html_text)
        for m in set(ske_matches):
            norm = normalize_sk_on_pn(m)
            if len(norm) >= 7 and norm not in seen:
                seen.add(norm)
                results.append({
                    'raw': m,
                    'normalized': norm,
                    'brand': self.BRAND,
                    'pn_type': 'service',
                })

        return results

    def build_search_url(self, part_number: str) -> str:
        pn = part_number.replace('/', '%2F').replace(' ', '+')
        return f"https://www.skon.com/search/?q={pn}"

    def build_part_url(self, part_number: str) -> str:
        pn = part_number.replace('/', '%2F')
        return f"https://www.skon.com/parts/{pn}"

    def extract_vehicle_info(self, html_text: str) -> list[dict]:
        results = []
        year_match = re.findall(r'\b(19\d{2}|20\d{2})\b', html_text)
        years = sorted(set(int(y) for y in year_match if 2000 <= int(y) <= 2030)) if year_match else []

        model_patterns = [
            r'F-150\s*Lightning',
            r'ID\.?4',
            r'Ioniq\s*(5|6)',
            r'EV[369]',
            r'EQS',
            r'BMW\s*i[XY]?',
        ]

        vehicle_map = {
            'F-150 Lightning': {'make': 'Ford', 'model': 'F-150 Lightning'},
            'ID.4': {'make': 'Volkswagen', 'model': 'ID.4'},
            'Ioniq 5': {'make': 'Hyundai', 'model': 'Ioniq 5'},
            'Ioniq 6': {'make': 'Hyundai', 'model': 'Ioniq 6'},
            'EV6': {'make': 'Kia', 'model': 'EV6'},
            'EV9': {'make': 'Kia', 'model': 'EV9'},
            'EQS': {'make': 'Mercedes', 'model': 'EQS'},
            'BMW iX': {'make': 'BMW', 'model': 'iX'},
        }

        found_models = set()
        for pattern in model_patterns:
            for match in re.finditer(pattern, html_text, re.IGNORECASE):
                model_key = match.group(0)
                if model_key in found_models:
                    continue
                found_models.add(model_key)

                vehicle = vehicle_map.get(model_key, {'make': 'Unknown', 'model': model_key})
                results.append({
                    'make': vehicle['make'],
                    'model': vehicle['model'],
                    'variant_code': None,
                    'year_from': years[0] if years else None,
                    'year_to': years[-1] if years else None,
                    'engine_code': None,
                })

        return results

    def enrich_with_sk_on_context(self, payload: dict, html_text: str) -> dict:
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

        product_patterns = [
            r'E-OPM',
            r'E-CMP',
            r'Electric\s*One\s*Platform\s*Module',
            r'E-CMP\s*Platform',
        ]
        if 'product_line' not in payload['properties']:
            for pattern in product_patterns:
                match = re.search(pattern, html_text, re.IGNORECASE)
                if match:
                    payload['properties']['product_line'] = {
                        'value': match.group(0).upper(),
                        'evidence_quote': f'Found product reference: {match.group(0)}',
                        'confidence': 0.8,
                    }
                    break

        return payload
