import re
from typing import Optional
import structlog

logger = structlog.get_logger()

LG_PART_NUMBER_RE = re.compile(r'LG[E]?[-]?\w{8,12}')
LG_MOBILE_RE = re.compile(r'LGM\d{7,10}')
LG_CELL_RE = re.compile(r'LGC\d{7}')

STANDARDIZED_CHEMISTRY = {
    'NCM': 'NCM',
    'NMC': 'NCM',
    'LFP': 'LiFePO4',
    'LTO': 'LiTiO',
    'NCA': 'NCA',
}

VEHICLE_MODELS = [
    'Bolt', 'LYRIQ', 'ID.4', 'e-tron', 'Taycan', 'Mustang Mach-E', 'EX30', 'EX90',
    'Cadillac LYRIQ', 'Chevrolet Bolt', 'Volkswagen ID.4', 'Audi e-tron',
    'Porsche Taycan', 'Ford Mustang Mach-E', 'Volvo EX30', 'Volvo EX90',
]

BATTERY_PLATFORMS = ['PRiME', 'E4', 'E6']


def normalize_lg_pn(raw: str) -> str:
    raw = raw.strip().upper().replace(' ', '').replace('-', '')
    return raw


def detect_lg_supersession(normalized: str, html_text: str) -> Optional[str]:
    supersession_patterns = [
        r'(?:superseded|replaced|替代)[:\s]+([A-Z0-9]{6,})',
        r'(?:alt|previous|former)[:\s]+([A-Z0-9]{6,})',
        r'\b([A-Z0-9]{6,})\s+(?:ist|was)\s+(?:der|das|替代)',
    ]
    for pattern in supersession_patterns:
        match = re.search(pattern, html_text, re.IGNORECASE)
        if match:
            return normalize_lg_pn(match.group(1))
    return None


class LGEnergyAdapter:
    BRAND = 'lg_energy'
    SOURCE_DOMAIN = 'lgenergy.com'
    SOURCE_KIND = 'battery_supplier'

    def __init__(self):
        self.logger = logger

    def extract_part_numbers(self, html_text: str) -> list[dict]:
        results = []
        lg_matches = LG_PART_NUMBER_RE.findall(html_text)
        for m in set(lg_matches):
            norm = normalize_lg_pn(m)
            if len(norm) >= 8:
                results.append({
                    'raw': m,
                    'normalized': norm,
                    'brand': self.BRAND,
                    'pn_type': 'battery_module',
                })
        lg_mobile_matches = LG_MOBILE_RE.findall(html_text)
        for m in set(lg_mobile_matches):
            norm = normalize_lg_pn(m)
            if len(norm) >= 8:
                results.append({
                    'raw': m,
                    'normalized': norm,
                    'brand': self.BRAND,
                    'pn_type': 'battery_cell',
                })
        lg_cell_matches = LG_CELL_RE.findall(html_text)
        for m in set(lg_cell_matches):
            norm = normalize_lg_pn(m)
            if len(norm) >= 7:
                results.append({
                    'raw': m,
                    'normalized': norm,
                    'brand': self.BRAND,
                    'pn_type': 'battery_cell',
                })
        return results

    def build_search_url(self, part_number: str) -> str:
        pn = part_number.replace('/', '%2F').replace(' ', '+')
        return f"https://www.lgenergy.com/search/?q={pn}"

    def build_part_url(self, part_number: str) -> str:
        pn = part_number.replace('/', '%2F')
        return f"https://www.lgenergy.com/parts/{pn}"

    def extract_vehicle_info(self, html_text: str) -> list[dict]:
        results = []
        year_match = re.findall(r'\b(19\d{2}|20\d{2})\b', html_text)
        years = sorted(set(int(y) for y in year_match if 2000 <= int(y) <= 2030)) if year_match else []

        for model in VEHICLE_MODELS:
            if model in html_text:
                make = 'Chevrolet' if 'Bolt' in model else \
                       'Cadillac' if 'LYRIQ' in model else \
                       'Volkswagen' if 'ID.4' in model else \
                       'Audi' if 'e-tron' in model else \
                       'Porsche' if 'Taycan' in model else \
                       'Ford' if 'Mustang' in model else \
                       'Volvo' if 'EX' in model else 'LG Energy'
                results.append({
                    'make': make,
                    'model': model,
                    'variant_code': None,
                    'year_from': years[0] if years else None,
                    'year_to': years[-1] if years else None,
                    'engine_code': None,
                })

        for platform in BATTERY_PLATFORMS:
            if platform in html_text:
                results.append({
                    'make': 'LG Energy',
                    'model': platform,
                    'variant_code': 'platform',
                    'year_from': years[0] if years else None,
                    'year_to': years[-1] if years else None,
                    'engine_code': None,
                })

        seen = set()
        unique_results = []
        for r in results:
            key = (r['make'], r['model'])
            if key not in seen:
                seen.add(key)
                unique_results.append(r)
        return unique_results

    def enrich_with_lg_context(self, payload: dict, html_text: str) -> dict:
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
        if 'platform' not in payload['properties']:
            for platform in BATTERY_PLATFORMS:
                if platform in html_text:
                    payload['properties']['platform'] = {
                        'value': platform,
                        'evidence_quote': f'Found {platform} platform reference',
                        'confidence': 0.8,
                    }
                    break
        return payload
