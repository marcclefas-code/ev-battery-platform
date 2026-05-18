from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional
import httpx
import structlog

logger = structlog.get_logger()


@dataclass
class FetchResult:
    url: str
    status_code: int
    html: str
    visible_text: str
    fetcher_name: str
    raw_hash: str
    html_length: int
    visible_text_length: int
    error: Optional[str] = None


class BaseFetcher(ABC):
    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self.logger = logger

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    async def fetch(self, url: str, **kwargs) -> FetchResult:
        pass

    async def close(self):
        pass
