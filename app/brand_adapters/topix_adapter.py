import httpx
from typing import Optional
import structlog
import re

logger = structlog.get_logger()

TOPIX_BASE = "https://topix.jaguarlandrover.com"


class TOPIxAdapter:
    BRAND = "jlr"
    SOURCE_DOMAIN = "topix.jaguarlandrover.com"
    SOURCE_KIND = "dealer_portal"

    def __init__(self, username: Optional[str] = None, password: Optional[str] = None):
        self.username = username
        self.password = password
        self.client = httpx.AsyncClient(timeout=60.0, follow_redirects=True)
        self.logger = logger
        self._session_token: Optional[str] = None

    async def close(self):
        await self.client.aclose()

    async def login(self) -> bool:
        if not self.username or not self.password:
            self.logger.warning("topix_login_skipped_no_credentials")
            return False
        try:
            response = await self.client.post(
                f"{TOPIX_BASE}/jlrlogin",
                data={
                    "username": self.username,
                    "password": self.password,
                },
                headers={"User-Agent": "Mozilla/5.0 (compatible; EVBatteryBot/3.0)"},
            )
            response.raise_for_status()
            self._session_token = self.client.cookies.get("JSESSIONID")
            self.logger.info("topix_login_success", username=self.username)
            return True
        except Exception as e:
            self.logger.error("topix_login_failed", username=self.username, error=str(e))
            return False

    async def search_part_number(self, part_number: str) -> list[dict]:
        if not self._session_token:
            logged_in = await self.login()
            if not logged_in:
                return []

        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (compatible; EVBatteryBot/3.0)",
                "Cookie": f"JSESSIONID={self._session_token}",
            }
            response = await self.client.get(
                f"{TOPIX_BASE}/EPQRWeb/search.xhtml",
                params={"partNumber": part_number},
                headers=headers,
            )
            response.raise_for_status()
            return self.extract_pns_from_html(response.text)
        except Exception as e:
            self.logger.error("topix_search_failed", part_number=part_number, error=str(e))
            return []

    async def get_part_details(self, part_number: str) -> Optional[dict]:
        if not self._session_token:
            await self.login()

        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (compatible; EVBatteryBot/3.0)",
                "Cookie": f"JSESSIONID={self._session_token}",
            }
            response = await self.client.get(
                f"{TOPIX_BASE}/EPQRWeb/partDetails.xhtml",
                params={"partNumber": part_number},
                headers=headers,
            )
            response.raise_for_status()
            return {"html": response.text, "url": str(response.url)}
        except Exception as e:
            self.logger.error("topix_part_details_failed", part_number=part_number, error=str(e))
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
        jlr_models = [
            "Range Rover", "Range Rover Sport", "Range Rover Velar",
            "Range Rover Evoque", "Discovery", "Discovery Sport",
            "Defender", "Jaguar F-PACE", "Jaguar E-PACE", "Jaguar I-PACE",
            "Freelander",
        ]
        for model in jlr_models:
            if model.lower() in html.lower():
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
        return f"{TOPIX_BASE}/EPQRWeb/search.xhtml?partNumber={part_number}"
