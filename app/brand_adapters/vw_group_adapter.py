import re
from typing import Optional
import structlog

logger = structlog.get_logger()

PN_RE = re.compile(r'[0-9A-Z]{2}[014579][-]?\d{5,6}[-]?[A-Z]?')
GENERIC_RE = re.compile(r'0\d{3,7}[A-Z]?')

STANDARDIZED_CHEMISTRY = {
    'NCM': 'NCM',
    'NMC': 'NCM',
    'LFP': 'LiFePO4',
    'LTO': 'LiTiO',
    'NCA': 'NCA',
}

BRAND_MODELS = {
    'VW': ['ID.3', 'ID.4', 'ID.5', 'ID.7', 'ID.Buzz', 'e-Up!'],
    'Audi': ['Q4 e-tron', 'Q5 e-tron', 'Q8 e-tron', 'e-tron GT', 'A6 e-tron', 'Q6 e-tron'],
    'Porsche': ['Taycan', 'Taycan Cross Turismo', 'Macan EV'],
    'Cupra': ['Born', 'Tavascan'],
    'Škoda': ['Enyaq', 'Enyaq Coupe'],
}


def normalize_vw_group_pn(raw: str) -> str:
    raw = raw.strip().upper().replace(' ', '').replace('-', '')
    return raw


def detect_vw_group_supersession(normalized: str, html_text: str) -> Optional[str]:
    supersession_patterns = [
        r'(?:superseded|replaced| Nachfolger|Ersatz)[:\s]+([A-Z0-9]{6,})',
        r'(?:alt|previous|former)[:\s]+([A-Z0-9]{6,})',
        r'\b([A-Z0-9]{6,})\s+(?:ist|was)\s+(?:der|das)\s+(?:Nachfolger|alt)',
    ]
    for pattern in supersession_patterns:
        match = re.search(pattern, html_text, re.IGNORECASE)
        if match:
            return normalize_vw_group_pn(match.group(1))
    return None


class VWGroupAdapter:
    BRAND = 'vw_group'
    SOURCE_DOMAIN = 'vw.com'
    SOURCE_DOMAIN_ALT = 'vwgroup.com'
    SOURCE_KIND = 'dealer_portal'

    def __init__(self):
        self.logger = logger

    def extract_part_numbers(self, html_text: str) -> list[dict]:
        results = []
        pn_matches = PN_RE.findall(html_text)
        for m in set(pn_matches):
            norm = normalize_vw_group_pn(m)
            if len(norm) >= 6:
                etka_category = self._detect_etka_category(norm)
                results.append({
                    'raw': m,
                    'normalized': norm,
                    'brand': self.BRAND,
                    'pn_type': etka_category,
                })
        return results

    def _detect_etka_category(self, pn: str) -> str:
        if pn.startswith('3D0') or '3D0' in pn:
            return 'engine'
        elif pn.startswith('5G0') or '5G0' in pn:
            return 'body'
        elif pn.startswith('1J0') or '1J0' in pn:
            return 'interior'
        elif pn.startswith('8K0') or '8K0' in pn:
            return 'electrical'
        return 'service'

    def build_search_url(self, part_number: str) -> str:
        pn = part_number.replace('/', '%2F').replace(' ', '+')
        return f"https://www.vwgroup.com/parts/search/?q={pn}"

    def build_part_url(self, part_number: str) -> str:
        pn = part_number.replace('/', '%2F')
        return f"https://www.vwgroup.com/parts/{pn}"

    def extract_vehicle_info(self, html_text: str) -> list[dict]:
        results = []
        year_match = re.findall(r'\b(19\d{2}|20\d{2})\b', html_text)
        years = sorted(set(int(y) for y in year_match if 2000 <= int(y) <= 2030)) if year_match else []

        model_patterns = [
            r'(ID\.3|ID\.4|ID\.5|ID\.7|ID\.Buzz|e-Up!)',
            r'(Q4 e-tron|Q5 e-tron|Q8 e-tron|e-tron GT|A6 e-tron|Q6 e-tron)',
            r'(Taycan|Taycan Cross Turismo|Macan EV)',
            r'(Born|Tavascan)',
            r'(Enyaq|Enyaq Coupe)',
        ]

        for pattern in model_patterns:
            for match in re.finditer(pattern, html_text, re.IGNORECASE):
                model_name = match.group(1)
                make = self._determine_make(model_name)
                results.append({
                    'make': make,
                    'model': model_name,
                    'variant_code': None,
                    'year_from': years[0] if years else None,
                    'year_to': years[-1] if years else None,
                    'engine_code': None,
                })
        return results

    def _determine_make(self, model: str) -> str:
        if model.startswith('ID.') or model == 'e-Up!':
            return 'VW'
        elif 'e-tron' in model or model.startswith('A6') or model.startswith('Q'):
            return 'Audi'
        elif 'Taycan' in model or 'Macan EV' in model:
            return 'Porsche'
        elif model == 'Born' or model == 'Tavascan':
            return 'Cupra'
        elif model.startswith('Enyaq'):
            return 'Škoda'
        return 'VW'

    def enrich_with_vw_group_context(self, payload: dict, html_text: str) -> dict:
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
