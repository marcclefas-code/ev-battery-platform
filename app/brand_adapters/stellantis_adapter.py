import re
import structlog

logger = structlog.get_logger()

PSA_PN_RE = re.compile(r'\d{10}')
FCA_PN_RE = re.compile(r'68\d{6}[A-Z]{2}')
ALphanum_PN_RE = re.compile(r'[A-Z0-9]{8,12}')


def normalize_stellantis_pn(raw: str) -> str:
    raw = raw.strip().upper().replace(' ', '').replace('-', '')
    return raw


def classify_stellantis_pn(norm: str) -> str:
    if re.match(r'^\d{10}$', norm):
        return 'PSA'
    if re.match(r'^68\d{6}[A-Z]{2}$', norm):
        return 'FCA'
    return 'UNKNOWN'


class StellantisAdapter:
    BRAND = 'stellantis'
    SOURCE_DOMAIN = 'evshop.eu'
    SOURCE_KIND = 'reseller'

    def __init__(self):
        self.logger = logger

    def extract_part_numbers(self, html_text: str) -> list[dict]:
        results = []
        psa_matches = PSA_PN_RE.findall(html_text)
        for m in set(psa_matches):
            norm = normalize_stellantis_pn(m)
            results.append({
                'raw': m,
                'normalized': norm,
                'brand': self.BRAND,
                'pn_type': 'service',
                'family': 'PSA',
            })
        fca_matches = FCA_PN_RE.findall(html_text)
        for m in set(fca_matches):
            norm = normalize_stellantis_pn(m)
            results.append({
                'raw': m,
                'normalized': norm,
                'brand': self.BRAND,
                'pn_type': 'service',
                'family': 'FCA',
            })
        alphanum = ALphanum_PN_RE.findall(html_text)
        for m in alphanum:
            norm = normalize_stellantis_pn(m)
            if len(norm) >= 8 and not any(n['normalized'] == norm for n in results):
                results.append({
                    'raw': m,
                    'normalized': norm,
                    'brand': self.BRAND,
                    'pn_type': 'service',
                    'family': classify_stellantis_pn(norm),
                })
        return results

    def build_search_url(self, part_number: str) -> str:
        pn = part_number.replace('/', '%2F').replace(' ', '+')
        return f"https://www.evshop.eu/search?q={pn}"

    def build_part_url(self, part_number: str) -> str:
        pn = part_number.replace('/', '%2F').replace(' ', '+')
        return f"https://www.evshop.eu/product/{pn}"

    def extract_vehicle_info(self, html_text: str) -> list[dict]:
        results = []
        year_match = re.findall(r'\b(201[8-9]|202[0-9])\b', html_text)
        model_patterns = [
            r'(e-208|e-2008|e-Rifter)',
            r'(Corsa-e|Ampera-e)',
            r'(500e|Jolli)',
            r'(Transit\s+Electric)',
            r'(Partner\s+Electric)',
        ]
        for pattern in model_patterns:
            for match in re.finditer(pattern, html_text, re.IGNORECASE):
                model_text = match.group(0)
                years = sorted(set(int(y) for y in year_match)) if year_match else [2020]
                results.append({
                    'make': 'Stellantis',
                    'model': model_text,
                    'variant_code': None,
                    'year_from': years[0],
                    'year_to': years[-1] if len(years) > 1 else None,
                    'engine_code': None,
                })
        return results

    def extract_config_from_qa(self, html_text: str) -> dict | None:
        config_patterns = [
            r'(\d+)s(\d+)p',
            r'(\d+)\s*[xX×]\s*(\d+)',
            r'(\d+)\s*cells?',
        ]
        for pattern in config_patterns:
            match = re.search(pattern, html_text)
            if match:
                groups = match.groups()
                if len(groups) >= 2:
                    try:
                        return {
                            'value': f"{groups[0]}s{groups[1]}p",
                            'evidence_quote': f"Found configuration {groups[0]}s{groups[1]}p in Q&A",
                            'confidence': 0.75,
                        }
                    except ValueError:
                        continue
        return None

    def enrich_with_stellantis_context(self, payload: dict, html_text: str) -> dict:
        if 'properties' not in payload:
            payload['properties'] = {}
        config = self.extract_config_from_qa(html_text)
        if config:
            payload['properties']['pack_configuration'] = config
        chemistry_patterns = {
            'NMC': 'NMC', 'NCM': 'NMC', 'LFP': 'LFP', 'NCA': 'NCA'
        }
        for key, val in chemistry_patterns.items():
            if key in html_text.upper():
                payload['properties']['chemistry'] = {
                    'value': val,
                    'evidence_quote': f'Found {key} in EVSHOP page',
                    'confidence': 0.7,
                }
                break
        return payload
