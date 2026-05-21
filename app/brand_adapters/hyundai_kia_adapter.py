import re
from typing import Optional
import structlog

logger = structlog.get_logger()

HYUNDAI_PN_RE = re.compile(r'[A-Z]{2}\d{3}[-]?\d{5,6}')
KIA_PN_RE = re.compile(r'\d{5}[-]?\w{3}[-]?\d{4}')
GENERIC_RE = re.compile(r'[A-Z]{2}\d{3}[-]?\d{5,6}')

BRAND_PREFIXES = {
    'OH': 'Hyundai',
    'OK': 'Kia',
    'OZ': 'Genesis',
}

E_GMP_MODELS = {
    'Hyundai Ioniq 5': {'battery_kwh': 77.4, 'year_from': 2022, 'year_to': None, 'drivetrain': ['RWD', 'AWD']},
    'Hyundai Ioniq 6': {'battery_kwh': 77.4, 'year_from': 2023, 'year_to': None, 'drivetrain': ['RWD', 'AWD']},
    'Hyundai Ioniq 9': {'battery_kwh': 111.0, 'year_from': 2024, 'year_to': None, 'drivetrain': ['AWD']},
    'Kia EV6': {'battery_kwh': 77.4, 'year_from': 2022, 'year_to': None, 'drivetrain': ['RWD', 'AWD']},
    'Kia EV9': {'battery_kwh': 111.0, 'year_from': 2024, 'year_to': None, 'drivetrain': ['AWD']},
    'Genesis GV60': {'battery_kwh': 77.4, 'year_from': 2022, 'year_to': None, 'drivetrain': ['RWD', 'AWD']},
    'Genesis GV70e': {'battery_kwh': 77.4, 'year_from': 2022, 'year_to': None, 'drivetrain': ['AWD']},
    'Genesis GV80e': {'battery_kwh': 77.4, 'year_from': 2023, 'year_to': None, 'drivetrain': ['AWD']},
}


def normalize_hyundai_kia_pn(raw: str) -> str:
    raw = raw.strip().upper().replace(' ', '').replace('-', '')
    return raw


def detect_brand_from_prefix(pn: str) -> str:
    for prefix, brand in BRAND_PREFIXES.items():
        if pn.startswith(prefix):
            return brand
    return 'Hyundai'


class HyundaiKiaAdapter:
    BRAND = 'hyundai_kia'
    SOURCE_DOMAIN = 'hyundai.com'
    SOURCE_DOMAIN_ALT = ['parts.hyundai.com', 'parts.kia.com', 'kia.com']
    SOURCE_KIND = 'dealer_portal'

    def __init__(self):
        self.logger = logger

    def extract_part_numbers(self, html_text: str) -> list[dict]:
        results = []
        hyundai_matches = HYUNDAI_PN_RE.findall(html_text)
        kia_matches = KIA_PN_RE.findall(html_text)
        all_matches = set(hyundai_matches + kia_matches)
        for m in all_matches:
            norm = normalize_hyundai_kia_pn(m)
            if len(norm) >= 7:
                prefix_brand = detect_brand_from_prefix(norm)
                results.append({
                    'raw': m,
                    'normalized': norm,
                    'brand': self.BRAND,
                    'pn_type': 'service',
                    'source_brand': prefix_brand,
                })
        return results

    def build_search_url(self, part_number: str, domain: str = 'hyundai.com') -> str:
        pn = part_number.replace('/', '%2F').replace(' ', '+')
        if domain == 'kia.com':
            return f"https://parts.kia.com/search/?q={pn}"
        return f"https://parts.hyundai.com/search/?q={pn}"

    def build_part_url(self, part_number: str, domain: str = 'hyundai.com') -> str:
        pn = part_number.replace('/', '%2F')
        if domain == 'kia.com':
            return f"https://parts.kia.com/parts/{pn}"
        return f"https://parts.hyundai.com/parts/{pn}"

    def extract_vehicle_info(self, html_text: str) -> list[dict]:
        results = []
        year_match = re.findall(r'\b(19\d{2}|20\d{2})\b', html_text)
        years = sorted(set(int(y) for y in year_match if 2000 <= int(y) <= 2030)) if year_match else []

        model_patterns = [
            r'(Ioniq\s*5|Ioniq\s*6|Ioniq\s*9)',
            r'(EV6|EV9)',
            r'(GV60|GV70e|GV80e)',
        ]

        found_models = set()
        for pattern in model_patterns:
            for match in re.finditer(pattern, html_text, re.IGNORECASE):
                model_raw = match.group(1)
                model_normalized = model_raw.replace(' ', '')
                if 'Ioniq' in model_normalized:
                    model_normalized = model_normalized.replace('Ioniq', 'Ioniq ')
                    if 'Ioniq 9' not in model_normalized:
                        model_normalized = model_normalized.replace('Ioniq', 'Ioniq ')
                found_models.add(model_normalized)

        for model_name, model_data in E_GMP_MODELS.items():
            for found in found_models:
                if model_name.replace(' ', '').lower() in found.lower().replace(' ', ''):
                    year_from = years[0] if years else model_data['year_from']
                    year_to = years[-1] if years else model_data['year_to']
                    results.append({
                        'make': 'Hyundai' if 'Hyundai' in model_name else ('Kia' if 'Kia' in model_name else 'Genesis'),
                        'model': model_name,
                        'battery_kwh': model_data['battery_kwh'],
                        'drivetrain': model_data['drivetrain'],
                        'year_from': year_from,
                        'year_to': year_to,
                        'platform': 'E-GMP',
                        'voltage_arch': '800V',
                    })

        return results

    def detect_supersession(self, normalized: str, html_text: str) -> Optional[str]:
        supersession_patterns = [
            r'(?:superseded|replaced|superseded\s+by)[:\s]+([A-Z0-9]{8,})',
            r'(?:previous|former|old)[:\s]+([A-Z0-9]{8,})',
            r'\b([A-Z]{2}\d{3}[-]?\d{5,6})\s+(?:replaces|supersedes)',
        ]
        for pattern in supersession_patterns:
            match = re.search(pattern, html_text, re.IGNORECASE)
            if match:
                return normalize_hyundai_kia_pn(match.group(1))
        return None

    def enrich_with_egmp_context(self, payload: dict, html_text: str) -> dict:
        if 'properties' not in payload:
            payload['properties'] = {}

        battery_matches = re.findall(r'(\d+\.?\d*)\s*(?:kWh|kwh)', html_text, re.IGNORECASE)
        if battery_matches and 'battery_capacity_kwh' not in payload['properties']:
            payload['properties']['battery_capacity_kwh'] = {
                'value': float(battery_matches[0]),
                'evidence_quote': f'Found {battery_matches[0]}kWh reference',
                'confidence': 0.8,
            }

        if '800V' in html_text.upper() and 'voltage' not in payload['properties']:
            payload['properties']['voltage'] = {
                'value': '800V',
                'evidence_quote': 'Found 800V architecture reference',
                'confidence': 0.9,
            }

        for model_name, model_data in E_GMP_MODELS.items():
            if model_name.lower() in html_text.lower():
                if 'platform' not in payload['properties']:
                    payload['properties']['platform'] = {
                        'value': 'E-GMP',
                        'evidence_quote': f'Found {model_name} reference',
                        'confidence': 0.85,
                    }
                break

        return payload
