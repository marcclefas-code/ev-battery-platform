from app.services.base_fetcher import BaseFetcher, FetchResult
from app.services.crawl4ai_fetcher import Crawl4AIFetcher
from app.services.scrapling_fetcher import ScraplingFetcher
from app.services.camoufox_fetcher import CamoufoxFetcher
from typing import Dict
import structlog

logger = structlog.get_logger()

AVAILABLE_FETCHERS: Dict[str, type[BaseFetcher]] = {
    "crawl4ai": Crawl4AIFetcher,
    "scrapling": ScraplingFetcher,
    "camoufox": CamoufoxFetcher,
}


class FetcherRegistry:
    _instances: Dict[str, BaseFetcher] = {}

    @classmethod
    def get(cls, name: str, **kwargs) -> BaseFetcher:
        if name not in AVAILABLE_FETCHERS:
            raise ValueError(f"Unknown fetcher: {name}. Available: {list(AVAILABLE_FETCHERS.keys())}")
        if name not in cls._instances:
            cls._instances[name] = AVAILABLE_FETCHERS[name](**kwargs)
        return cls._instances[name]

    @classmethod
    async def close_all(cls):n        for instance in cls._instances.values():
            await instance.close()
        cls._instances.clear()
