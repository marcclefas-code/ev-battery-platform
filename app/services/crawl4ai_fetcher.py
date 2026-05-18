import hashlib
from typing import Optional
import httpx
from crawl4ai import AsyncWebCrawler
from app.services.base_fetcher import BaseFetcher, FetchResult
import structlog

logger = structlog.get_logger()


class Crawl4AIFetcher(BaseFetcher):
    def __init__(self, crawler_url: str = "http://localhost:8000", timeout: int = 30):
        super().__init__(timeout)
        self.crawler_url = crawler_url
        self.client = None

    @property
    def name(self) -> str:
        return "crawl4ai"

    async def fetch(self, url: str, **kwargs) -> FetchResult:
        try:
            self.client = AsyncWebCrawler(api_url=self.crawler_url)
            async with self.client:
                result = await self.client.arun(url=url, **kwargs)

            html = result.html if hasattr(result, 'html') else str(result)
            visible_text = result.visible_text if hasattr(result, 'visible_text') else ""
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
            self.logger.error("crawl4ai_fetch_failed", url=url, error=str(e))
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
