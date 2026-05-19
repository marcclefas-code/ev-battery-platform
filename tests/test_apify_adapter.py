import pytest
from app.brand_adapters.apify_adapter import ApifyAdapter


class TestApifyAdapter:
    def setup_method(self):
        self.adapter = ApifyAdapter(api_token="test-token", actor_id="test-actor")

    def teardown_method(self):
        import asyncio
        asyncio.get_event_loop().run_until_complete(self.adapter.close())

    def test_brand_is_apify(self):
        assert self.adapter.BRAND == "apify"

    def test_source_kind(self):
        assert self.adapter.SOURCE_KIND == "apify_actor"

    def test_client_has_timeout(self):
        assert self.adapter.client.timeout.read == 60.0
