import re
from typing import Optional
import structlog

logger = structlog.get_logger()

CATL_RE = re.compile(r'CATL[-]?\w{6,10}')
NMC_RE = re.compile(r'NMC[-]?\d{6}')
LFP_RE = re.compile(r'LFP[-]?\d{6}')
CELL_TYPE_RE = re.compile(r'\b(NMC|LFP|LSS|LTO|NCA|NCM)\b', re.IGNORECASE)

STANDARDIZED_CHEMISTRY = {
    'NCM': 'NCM',
    'NMC': 'NCM',
    'LFP': 'LiFePO4',
    'LTO': 'LiTiO',
    'NCA': 'NCA',
    'LSS': 'Li-Solid-State',
}


def normalize_catl_pn(raw: str) -> str:
    raw = raw.strip().upper().replace(' ', '').replace('-', '')
    if raw.startswith('CATL'):
        return raw
    if raw.startswith('NMC') or raw.startswith('LFP'):
        return raw
    return raw


def detect_catl_supersession(normalized: str, html_text: str) -> Optional[str]:
    supersession_patterns = [
        r'(?:superseded|replaced|replacement)[:\s]+([A-Z0-9\-]{6,})',
        r'(?:replaces|supersedes)[:\s]+([A-Z0-9\-]{6,})',
        r'\b([A-Z0-9\-]{6,})\s+(?:replaces|supersedes)',
    ]
    for pattern in supersession_patterns:
        match = re.search(pattern, html_text, re.IGNORECASE)
        if match:
            return normalize_catl_pn(match.group(1))
    return None


class CATLAdapter:
    BRAND = 'catl'
    SOURCE_DOMAIN = 'catl.com'
    SOURCE_KIND = 'battery_supplier'

    def __init__(self):
        self.logger = logger

    def extract_part_numbers(self, html_text: str) -> list[dict]:
        results = []
        seen = set()

        catl_matches = CATL_RE.findall(html_text)
        for m in set(catl_matches):
            norm = normalize_catl_pn(m)
            if len(norm) >= 6 and norm not in seen:
                seen.add(norm)
                results.append({
                    'raw': m,
                    'normalized': norm,
                    'brand': self.BRAND,
                    'pn_type': 'battery_pack',
                })

        nmc_matches = NMC_RE.findall(html_text)
        for m in set(nmc_matches):
            norm = normalize_catl_pn(m)
            if len(norm) >= 6 and norm not in seen:
                seen.add(norm)
                results.append({
                    'raw': m,
                    'normalized': norm,
                    'brand': self.BRAND,
                    'pn_type': 'cell_module',
                })

        lfp_matches = LFP_RE.findall(html_text)
        for m in set(lfp_matches):
            norm = normalize_catl_pn(m)
            if len(norm) >= 6 and norm not in seen:
                seen.add(norm)
                results.append({
                    'raw': m,
                    'normalized': norm,
                    'brand': self.BRAND,
                    'pn_type': 'cell_module',
                })

        return results

    def build_search_url(self, part_number: str) -> str:
        pn = part_number.replace('/', '%2F').replace(' ', '+')
        return f"https://www.catl.com/search/?q={pn}"

    def build_part_url(self, part_number: str) -> str:
        pn = part_number.replace('/', '%2F')
        return f"https://www.catl.com/parts/{pn}"

    def extract_vehicle_info(self, html_text: str) -> list[dict]:
        results = []
        year_match = re.findall(r'\b(19\d{2}|20\d{2})\b', html_text)
        years = sorted(set(int(y) for y in year_match if 2000 <= int(y) <= 2030)) if year_match else []

        oem_patterns = [
            r'(Tesla|Tesla[\s-]+Model[\s-]*(?:S|3|X|Y))',
            r'(BMW|BMW[\s-]+(?:i3|i4|i5|i7|iX|X1|X3|X5))',
            r'(Mercedes(?:[\s-]?Benz)?|Mercedes[\s-]+(?:EQ[ABCES]|EQA|EQB|EQC|EQS))',
            r'(Volkswagen|VW|Volkswagen[\s-]+ID(?:\.?(?:3|4|5|6)))',
            r'(Volvo|Volvo[\s-]+(?:XC(?:40|60|90)|C40|EX30|EX90))',
            r'(Hyundai|Hyundai[\s-]+(?:Ioniq|Kona|Ionic))',
            r'(Honda|Honda[\s-]+(?:e(?:NY1|Advance)?|e:?))',
            r'(Toyota|Toyota[\s-]+(?:bZ4X|Camry|Prius|Rav4))',
        ]

        for pattern in oem_patterns:
            for match in re.finditer(pattern, html_text, re.IGNORECASE):
                oem = match.group(1).strip()
                oem_clean = re.sub(r'\s+', ' ', oem).title()
                results.append({
                    'make': oem_clean,
                    'model': None,
                    'variant_code': None,
                    'year_from': years[0] if years else None,
                    'year_to': years[-1] if years else None,
                    'engine_code': None,
                })

        return results

    def extract_cell_type(self, html_text: str) -> dict | None:
        cell_match = CELL_TYPE_RE.search(html_text)
        if cell_match:
            chem = cell_match.group(1).upper()
            standardized = STANDARDIZED_CHEMISTRY.get(chem, chem)
            return {
                'value': standardized,
                'evidence_quote': f'Found {chem} cell type reference',
                'confidence': 0.8,
            }
        return None

    def enrich_with_catl_context(self, payload: dict, html_text: str) -> dict:
        if 'properties' not in payload:
            payload['properties'] = {}

        cell_type = self.extract_cell_type(html_text)
        if cell_type:
            payload['properties']['chemistry'] = cell_type

        oem_matches = re.findall(
            r'(Tesla|BMW|Mercedes|Volkswagen|Volvo|Hyundai|Honda|Toyundai)',
            html_text,
            re.IGNORECASE
        )
        if oem_matches:
            payload['properties']['oem_customers'] = {
                'value': list(set(oem_matches)),
                'evidence_quote': 'CATL supplies batteries to multiple OEMs',
                'confidence': 0.9,
            }

        return payload
