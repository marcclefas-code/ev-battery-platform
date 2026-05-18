import httpx
from typing import Optional
import structlog
import re

logger = structlog.get_logger()

TOPIX_BASE = "https://topix.ourworld.eu"


class TOPIxAdapter:
    BRAND = "topix"
    SOURCE_DOMAIN = "topix.ourworld.eu"
    SOURCE_KIND = "forum_parts_catalog"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.client = httpx.AsyncClient(timeout=30.0)
        self.logger = logger

    async def close(self):
        await self.client.aclose()

    async def search_part_number(self, part_number: str) -> list[dict]:
        try:
            response = await self.client.get(
                f"{TOPIX_BASE}/api/search",
                params={"q": part_number, "key": self.api_key},
            )
            response.raise_for_status()
            data = response.json()
            return data.get("results", [])
        except Exception as e:
            self.logger.error("topix_search_failed", part_number=part_number, error=str(e))
            return []

    async def get_thread_by_pn(self, part_number: str) -> Optional[str]:
        results = await self.search_part_number(part_number)
        for result in results:
            if result.get("type") == "thread":
                return result.get("url")
        return None

    async def fetch_thread_html(self, thread_url: str) -> Optional[str]:
        try:
            headers = {"User-Agent": "Mozilla/5.0 (compatible; EVBatteryBot/3.0)"}
            response = await self.client.get(thread_url, headers=headers)
            response.raise_for_status()
            return response.text
        except Exception as e:
            self.logger.error("topix_fetch_failed", url=thread_url, error=str(e))
            return None

    def extract_pns_from_html(self, html: str) -> list[dict]:
        pncodes_re = re.compile(r'\b[A-Z]{2,4}\d{2,4}[A-Z0-9]{2,8}\b')
        results = []
        for m in set(pncodes_re.findall(html)):
            results.append({
                "raw": m,
                "normalized": m.strip().upper(),
                "brand": "jlr",
                "pn_type": "service",
            })
        return results

    def extract_vehicle_info(self, html: str) -> list[dict]:
        results = []
        jlr_models = ["Range Rover", "Discovery", "Defender", "Evoque", "Velar", "Sport", "Freelander"]
        for model in jlr_models:
            if model in html:
                year_match = re.findall(r'\b(19\d{2}|20\d{2})\b', html)
                years = sorted(set(int(y) for y in year_match if 2000 <= int(y) <= 2030)) if year_match else []
                results.append({
                    "make": "JLR",
                    "model": model,
                    "variant_code": None,
                    "year_from": years[0] if years else None,
                    "year_to": years[-1] if years else None,
                })
        return results

    def build_search_url(self, part_number: str) -> str:
        return f"{TOPIX_BASE}/search?q={part_number}"
