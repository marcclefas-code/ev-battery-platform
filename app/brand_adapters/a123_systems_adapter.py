import re
from typing import Optional
import structlog

logger = structlog.get_logger()

A123_PN_RE = re.compile(r'A123[_-]?\w{6,10}')
A1PH_PN_RE = re.compile(r'A1PH[_-]?\w{6,10}')
NAP_PN_RE = re.compile(r'NAP[_-]?\d{6}')

STANDARDIZED_CHEMISTRY = {
    'Nanophosphate': 'Nanophosphate Li-ion',
    'Li-ion': 'Li-ion',
    'NCM': 'NCM',
    'NMC': 'NCM',
    'LFP': 'LiFePO4',
    'LTO': 'LiTiO',
}


def normalize_a123_pn(raw: str) -> str:
    raw = raw.strip().upper().replace(' ', '')
    raw = re.sub(r'[_-]', '', raw)
    return raw


def detect_a123_supersession(normalized: str, html_text: str) -> Optional[str]:
    supersession_patterns = [
        r'(?:superseded|replaced|supersedes)[:\s]+([A-Z0-9]{6,})',
        r'(?:replaces|former|previous)[:\s]+([A-Z0-9]{6,})',
        r'\b([A-Z0-9]{6,})\s+(?:replaces|supersedes)',
    ]
    for pattern in supersession_patterns:
        match = re.search(pattern, html_text, re.IGNORECASE)
        if match:
            return normalize_a123_pn(match.group(1))
    return None


class A123SystemsAdapter:
    BRAND = 'a123_systems'
    SOURCE_DOMAIN = 'a123systems.com'
    SOURCE_KIND = 'battery_supplier'

    VEHICLE_MODELS = {
        'Chevrolet Volt': {'make': 'Chevrolet', 'model': 'Volt'},
        'Chevrolet Bolt': {'make': 'Chevrolet', 'model': 'Bolt'},
        'BMW i3': {'make': 'BMW', 'model': 'i3'},
        'Fisker Karma': {'make': 'Fisker', 'model': 'Karma'},
        'Daimler': {'make': 'Daimler', 'model': None},
    }

    def __init__(self):
        self.logger = logger

    def extract_part_numbers(self, html_text: str) -> list[dict]:
        results = []
        seen = set()

        a123_matches = A123_PN_RE.findall(html_text)
        for m in set(a123_matches):
            norm = normalize_a123_pn(m)
            if len(norm) >= 7 and norm not in seen:
                seen.add(norm)
                results.append({
                    'raw': m,
                    'normalized': norm,
                    'brand': self.BRAND,
                    'pn_type': 'battery_module',
                })

        a1ph_matches = A1PH_PN_RE.findall(html_text)
        for m in set(a1ph_matches):
            norm = normalize_a123_pn(m)
            if len(norm) >= 7 and norm not in seen:
                seen.add(norm)
                results.append({
                    'raw': m,
                    'normalized': norm,
                    'brand': self.BRAND,
                    'pn_type': 'battery_cell',
                })

        nap_matches = NAP_PN_RE.findall(html_text)
        for m in set(nap_matches):
            norm = normalize_a123_pn(m)
            if len(norm) >= 6 and norm not in seen:
                seen.add(norm)
                results.append({
                    'raw': m,
                    'normalized': norm,
                    'brand': self.BRAND,
                    'pn_type': 'nanophosphate_cell',
                })

        return results

    def build_search_url(self, part_number: str) -> str:
        pn = part_number.replace('/', '%2F').replace(' ', '+')
        return f"https://www.a123systems.com/search/?q={pn}"

    def build_part_url(self, part_number: str) -> str:
        pn = part_number.replace('/', '%2F')
        return f"https://www.a123systems.com/parts/{pn}"

    def extract_vehicle_info(self, html_text: str) -> list[dict]:
        results = []
        year_match = re.findall(r'\b(19\d{2}|20\d{2})\b', html_text)
        years = sorted(set(int(y) for y in year_match if 2000 <= int(y) <= 2030)) if year_match else []

        model_patterns = [
            r'Chevrolet\s+Volt',
            r'Chevrolet\s+Bolt',
            r'BMW\s+i3',
            r'Fisker\s+Karma',
            r'Daimler',
            r'General\s+Motors',
            r'GM\s+(?:Volt|Bolt)',
        ]

        found_models = set()
        for pattern in model_patterns:
            for match in re.finditer(pattern, html_text, re.IGNORECASE):
                model_text = match.group(0)
                if model_text in found_models:
                    continue
                found_models.add(model_text)

                if 'volt' in model_text.lower():
                    make, model = 'Chevrolet', 'Volt'
                elif 'bolt' in model_text.lower():
                    make, model = 'Chevrolet', 'Bolt'
                elif 'i3' in model_text.lower():
                    make, model = 'BMW', 'i3'
                elif 'karma' in model_text.lower():
                    make, model = 'Fisker', 'Karma'
                elif 'daimler' in model_text.lower() or 'general motors' in model_text.lower() or 'gm' in model_text.lower():
                    make, model = 'GM', None
                else:
                    make, model = 'A123 Systems', None

                results.append({
                    'make': make,
                    'model': model,
                    'variant_code': None,
                    'year_from': years[0] if years else None,
                    'year_to': years[-1] if years else None,
                    'engine_code': None,
                })

        return results

    def enrich_with_a123_context(self, payload: dict, html_text: str) -> dict:
        if 'properties' not in payload:
            payload['properties'] = {}

        if 'chemistry' not in payload['properties']:
            for chem_key, chem_val in STANDARDIZED_CHEMISTRY.items():
                if chem_key.lower() in html_text.lower():
                    payload['properties']['chemistry'] = {
                        'value': chem_val,
                        'evidence_quote': f'Found {chem_key} reference in page',
                        'confidence': 0.7,
                    }
                    break

        if 'technology' not in payload['properties']:
            if 'nanophosphate' in html_text.lower():
                payload['properties']['technology'] = {
                    'value': 'Nanophosphate Li-ion',
                    'evidence_quote': 'A123 Systems Nanophosphate technology',
                    'confidence': 0.9,
                }

        if 'cell_form_factor' not in payload['properties']:
            form_factors = ['prismatic', 'cylindrical']
            for ff in form_factors:
                if ff in html_text.lower():
                    payload['properties']['cell_form_factor'] = {
                        'value': ff,
                        'evidence_quote': f'Found {ff} cell reference',
                        'confidence': 0.6,
                    }
                    break

        return payload
