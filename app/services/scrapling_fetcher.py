import hashlib
import asyncio
from typing import Optional
from app.services.base_fetcher import BaseFetcher, FetchResult
import structlog

logger = structlog.get_logger()

try:
    from scrapling import Adaptor
    HAS_SCRAPLING = True
except ImportError:
    HAS_SCRAPLING = False


class ScraplingFetcher(BaseFetcher):
    def __init__(self, timeout: int = 30):
        super().__init__(timeout)
        if not HAS_SCRAPLING:
            raise ImportError("scrapling not installed: pip install scrapling[all]")

    @property
    def name(self) -> str:
        return "scrapling"

    async def fetch(self, url: str, **kwargs) -> FetchResult:
        try:
            adaptor = Adaptor(url)
            await adaptor.fetch()

            html = adaptor.html
            visible_text = adaptor.xtree.xpath("string(//body)") if adaptor.xtree is not None else ""
            raw_hash = hashlib.sha256(html.encode()).hexdigest()

            return FetchResult(
                url=url,
                status_code=200,
                html=html,
                visible_text=visible_text,
                fetcher_name=self.name,
                raw_hash=raw_hash,
                html_length=len(html),
                visible_text_length=len(visible_text),
            )
        except Exception as e:
            self.logger.error("scrapling_fetch_failed", url=url, error=str(e))
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
