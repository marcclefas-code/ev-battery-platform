import hashlib
from typing import Optional
from app.services.base_fetcher import BaseFetcher, FetchResult
import structlog

logger = structlog.get_logger()

try:
    import camoufox
    HAS_CAMOUFOX = True
except ImportError:
    HAS_CAMOUFOX = False


class CamoufoxFetcher(BaseFetcher):
    def __init__(self, timeout: int = 30):
        super().__init__(timeout)
        if not HAS_CAMOUFOX:
            raise ImportError("camoufox not installed: pip install camoufox")
        self.client = None

    @property
    def name(self) -> str:
        return "camoufox"

    async def fetch(self, url: str, **kwargs) -> FetchResult:
        try:
            session = camoufox.Session()
            response = session.get(url)
            response.raise_for_status()
            html = response.text
            visible_text = response.text[:10000]
            raw_hash = hashlib.sha256(html.encode()).hexdigest()
            session.close()

            return FetchResult(
                url=url,
                status_code=response.status_code,
                html=html,
                visible_text=visible_text,
                fetcher_name=self.name,
                raw_hash=raw_hash,
                html_length=len(html),
                visible_text_length=len(visible_text),
            )
        except Exception as e:
            self.logger.error("camoufox_fetch_failed", url=url, error=str(e))
            return FetchResult(
                url=url,
                status_code=0,
                html="",
                visible_text="",
                fetcher_name=self.name,
                raw_hash="",
                html_length=0,
                visible_text_length=0,
                error=str(e),
            )

    async def close(self):
        if self.client:
            await self.client.close()
