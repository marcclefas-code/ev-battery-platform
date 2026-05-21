import re
from typing import Optional
import structlog

logger = structlog.get_logger()

GM_PARTNUM_RE = re.compile(r'\b\d{7,8}\b')
ACDELCO_RE = re.compile(r'ACR[_-]?\w{6,10}')

STANDARDIZED_CHEMISTRY = {
    'NCM': 'NCM',
    'NMC': 'NCM',
    'LFP': 'LiFePO4',
    'LTO': 'LiTiO',
    'NCA': 'NCA',
}

GM_EV_MODELS = [
    'Bolt EV',
    'Bolt EUV',
    'LYRIQ',
    'Hummer EV',
    'Silverado EV',
    'Sierra EV',
    'Equinox EV',
    'Blazer EV',
    'Bolt',
]


def normalize_gm_pn(raw: str) -> str:
    raw = raw.strip().upper().replace(' ', '').replace('-', '').replace('_', '')
    return raw


def detect_gm_supersession(normalized: str, html_text: str) -> Optional[str]:
    supersession_patterns = [
        r'(?:superseded|replaced|superseded\s+by)[:\s]+([A-Z0-9]{6,})',
        r'(?:replaces|previous|former)[:\s]+([A-Z0-9]{6,})',
        r'\b([A-Z0-9]{7,8})\s+(?:replaces|superseded)',
    ]
    for pattern in supersession_patterns:
        match = re.search(pattern, html_text, re.IGNORECASE)
        if match:
            return normalize_gm_pn(match.group(1))
    return None


class GMACDelcoAdapter:
    BRAND = 'gm'
    SOURCE_DOMAIN = 'acdelco.com'
    SOURCE_DOMAIN_ALT = 'gmc.com'
    SOURCE_KIND = 'dealer_portal'

    def __init__(self):
        self.logger = logger

    def extract_part_numbers(self, html_text: str) -> list[dict]:
        results = []
        gm_matches = GM_PARTNUM_RE.findall(html_text)
        for m in set(gm_matches):
            norm = normalize_gm_pn(m)
            if len(norm) >= 7:
                results.append({
                    'raw': m,
                    'normalized': norm,
                    'brand': self.BRAND,
                    'pn_type': 'service',
                })
        acdelco_matches = ACDELCO_RE.findall(html_text)
        for m in set(acdelco_matches):
            norm = normalize_gm_pn(m)
            if len(norm) >= 6:
                results.append({
                    'raw': m,
                    'normalized': norm,
                    'brand': self.BRAND,
                    'pn_type': 'acdelco',
                })
        return results

    def build_search_url(self, part_number: str) -> str:
        pn = part_number.replace('/', '%2F').replace(' ', '+')
        return f"https://www.acdelco.com/search?q={pn}"

    def build_part_url(self, part_number: str) -> str:
        pn = part_number.replace('/', '%2F')
        return f"https://www.acdelco.com/parts/{pn}"

    def extract_vehicle_info(self, html_text: str) -> list[dict]:
        results = []
        year_match = re.findall(r'\b(19\d{2}|20\d{2})\b', html_text)
        years = sorted(set(int(y) for y in year_match if 2000 <= int(y) <= 2030)) if year_match else []

        model_patterns = [
            r'(Bolt\s*EV|Bolt\s*EUV|Hummer\s*EV|Silverado\s*EV|Sierra\s*EV|Equinox\s*EV|Blazer\s*EV|LYRIQ)',
            r'Cadillac\s+(LYRIQ)',
            r'Chevrolet\s+(Bolt|Bolt\s*EV|Bolt\s*EUV|Silverado\s*EV|Equinox\s*EV|Blazer\s*EV)',
            r'GMC\s+(Hummer\s*EV|Sierra\s*EV)',
        ]
        seen_models = set()
        for pattern in model_patterns:
            for match in re.finditer(pattern, html_text, re.IGNORECASE):
                model = match.group(1).strip()
                if model in seen_models:
                    continue
                seen_models.add(model)
                make = 'Cadillac' if model == 'LYRIQ' else 'GMC' if model in ['Hummer EV', 'Sierra EV'] else 'Chevrolet'
                results.append({
                    'make': make,
                    'model': model,
                    'variant_code': None,
                    'year_from': years[0] if years else None,
                    'year_to': years[-1] if years else None,
                    'engine_code': None,
                })
        return results

    def enrich_with_gm_context(self, payload: dict, html_text: str) -> dict:
        if 'properties' not in payload:
            payload['properties'] = {}
        if 'platform' not in payload['properties']:
            if 'Ultium' in html_text:
                if '800V' in html_text:
                    payload['properties']['platform'] = {
                        'value': 'Ultium 800V',
                        'evidence_quote': 'Found Ultium 800V architecture reference',
                        'confidence': 0.8,
                    }
                elif '400V' in html_text:
                    payload['properties']['platform'] = {
                        'value': 'Ultium 400V',
                        'evidence_quote': 'Found Ultium 400V architecture reference',
                        'confidence': 0.8,
                    }
                else:
                    payload['properties']['platform'] = {
                        'value': 'Ultium',
                        'evidence_quote': 'Found Ultium platform reference',
                        'confidence': 0.7,
                    }
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
