import pytest
from app.services.fetcher_registry import FetcherRegistry, AVAILABLE_FETCHERS, BaseFetcher


class TestFetcherRegistry:
    def test_available_fetchers_has_expected(self):
        assert "crawl4ai" in AVAILABLE_FETCHERS
        assert "scrapling" in AVAILABLE_FETCHERS
        assert "camoufox" in AVAILABLE_FETCHERS

    def test_get_returns_correct_type(self):
        try:
            fetcher = FetcherRegistry.get("crawl4ai")
            assert isinstance(fetcher, BaseFetcher)
        except ImportError:
            pytest.skip("crawl4ai not installed")

    def test_get_unknown_raises(self):
        with pytest.raises(ValueError) as exc_info:
            FetcherRegistry.get("nonexistent")
        assert "Unknown fetcher" in str(exc_info.value)

    def test_get_caches_instance(self):
        try:
            f1 = FetcherRegistry.get("crawl4ai")
            f2 = FetcherRegistry.get("crawl4ai")
            assert f1 is f2
        except ImportError:
            pytest.skip("crawl4ai not installed")
