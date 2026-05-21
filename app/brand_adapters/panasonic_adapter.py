import re
from typing import Optional
import structlog

logger = structlog.get_logger()

PAN_PART_NUM_RE = re.compile(r'PAN[-]?\w{6,12}')
NCR_PART_NUM_RE = re.compile(r'NCR[-]?\d{4}')
KRH_PART_NUM_RE = re.compile(r'KRH[-]?\d{4}')
CELL_FORMAT_RE = re.compile(r'\b(18650|2170|4680|4680Plus)\b', re.IGNORECASE)

GENERIC_RE = re.compile(r'0\d{3,7}[A-Z]?')

STANDARDIZED_CHEMISTRY = {
    'NCA': 'NCA',
    'NCM': 'NCM',
    'NMC': 'NCM',
    'LFP': 'LiFePO4',
    'LTO': 'LiTiO',
    'LI-ION': 'Li-ion',
    'LITHIUM': 'Li-ion',
}


def normalize_panasonic_pn(raw: str) -> str:
    raw = raw.strip().upper().replace(' ', '').replace('-', '')
    if raw.startswith('PAN'):
        return raw
    if raw.startswith('NCR'):
        return raw
    if raw.startswith('KRH'):
        return raw
    if len(raw) >= 5:
        return raw
    return raw


def detect_panasonic_supersession(normalized: str, html_text: str) -> Optional[str]:
    supersession_patterns = [
        r'(?:superseded|replaced| Nachfolger|successor)[:\s]+([A-Z0-9]{6,})',
        r'(?:alt|previous|former)[:\s]+([A-Z0-9]{6,})',
        r'\b([A-Z0-9]{6,})\s+(?:ist|was)\s+(?:der|das)\s+(?:Nachfolger|alt)',
    ]
    for pattern in supersession_patterns:
        match = re.search(pattern, html_text, re.IGNORECASE)
        if match:
            return normalize_panasonic_pn(match.group(1))
    return None


class PanasonicAdapter:
    BRAND = 'panasonic'
    SOURCE_DOMAIN = 'panasonic.com'
    SOURCE_KIND = 'battery_supplier'

    def __init__(self):
        self.logger = logger

    def extract_part_numbers(self, html_text: str) -> list[dict]:
        results = []
        pan_matches = PAN_PART_NUM_RE.findall(html_text)
        for m in set(pan_matches):
            norm = normalize_panasonic_pn(m)
            if len(norm) >= 5:
                results.append({
                    'raw': m,
                    'normalized': norm,
                    'brand': self.BRAND,
                    'pn_type': 'cell',
                })
        ncr_matches = NCR_PART_NUM_RE.findall(html_text)
        for m in set(ncr_matches):
            norm = normalize_panasonic_pn(m)
            if len(norm) >= 5:
                results.append({
                    'raw': m,
                    'normalized': norm,
                    'brand': self.BRAND,
                    'pn_type': 'cell',
                })
        krh_matches = KRH_PART_NUM_RE.findall(html_text)
        for m in set(krh_matches):
            norm = normalize_panasonic_pn(m)
            if len(norm) >= 5:
                results.append({
                    'raw': m,
                    'normalized': norm,
                    'brand': self.BRAND,
                    'pn_type': 'cell',
                })
        return results

    def build_search_url(self, part_number: str) -> str:
        pn = part_number.replace('/', '%2F').replace(' ', '+')
        return f"https://www.panasonic.com/search?q={pn}"

    def build_part_url(self, part_number: str) -> str:
        pn = part_number.replace('/', '%2F')
        return f"https://www.panasonic.com/batteries/{pn}"

    def extract_vehicle_info(self, html_text: str) -> list[dict]:
        results = []
        year_match = re.findall(r'\b(19\d{2}|20\d{2})\b', html_text)
        years = sorted(set(int(y) for y in year_match if 2000 <= int(y) <= 2030)) if year_match else []

        vehicle_patterns = [
            (r'Tesla[\s-]+(Model\s*[S3XY]|Model\s*Y|Model\s*3|Model\s*S|Model\s*X|Cybertruck)', 'Tesla'),
            (r'Toyota[\s-]+(bZ4X|Rav4|Prius)', 'Toyota'),
            (r'Honda[\s-]+(Prologue|CR-V)', 'Honda'),
            (r'Ford[\s-]+(F-150[\s-]*Lightning|Mustang[\s-]*Mach-E)', 'Ford'),
        ]

        for pattern, make in vehicle_patterns:
            for match in re.finditer(pattern, html_text, re.IGNORECASE):
                model = match.group(1).strip()
                results.append({
                    'make': make,
                    'model': model,
                    'variant_code': None,
                    'year_from': years[0] if years else None,
                    'year_to': years[-1] if years else None,
                    'engine_code': None,
                })

        if not results and years:
            cell_match = CELL_FORMAT_RE.search(html_text)
            if cell_match:
                results.append({
                    'make': 'Panasonic',
                    'model': f'Cell-{cell_match.group(1)}',
                    'variant_code': None,
                    'year_from': years[0] if years else None,
                    'year_to': years[-1] if years else None,
                    'engine_code': None,
                })

        return results

    def extract_cell_format(self, html_text: str) -> list[str]:
        matches = CELL_FORMAT_RE.findall(html_text)
        return list(set(m.upper() for m in matches))

    def enrich_with_panasonic_context(self, payload: dict, html_text: str) -> dict:
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

        cell_formats = self.extract_cell_format(html_text)
        if cell_formats and 'cell_format' not in payload['properties']:
            payload['properties']['cell_format'] = {
                'value': cell_formats,
                'evidence_quote': f'Found cell format references: {", ".join(cell_formats)}',
                'confidence': 0.8,
            }

        if 'suppliers' not in payload['properties']:
            oem_matches = ['Tesla', 'Toyota', 'Honda', 'Ford']
            found_suppliers = [oem for oem in oem_matches if oem.lower() in html_text.lower()]
            if found_suppliers:
                payload['properties']['oem_suppliers'] = {
                    'value': found_suppliers,
                    'evidence_quote': f'Found OEM references: {", ".join(found_suppliers)}',
                    'confidence': 0.75,
                }

        return payload
