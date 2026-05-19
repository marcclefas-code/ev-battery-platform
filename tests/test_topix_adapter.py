import pytest
from app.brand_adapters.topix_adapter import TOPIxAdapter


class TestTOPIxAdapter:
    def setup_method(self):
        self.adapter = TOPIxAdapter(api_key="test-key")

    def teardown_method(self):
        import asyncio
        asyncio.get_event_loop().run_until_complete(self.adapter.close())

    def test_brand_is_jlr(self):
        assert self.adapter.BRAND == "topix"

    def test_source_kind(self):
        assert self.adapter.SOURCE_KIND == "forum_parts_catalog"

    def test_build_search_url(self):
        url = self.adapter.build_search_url("ABC123")
        assert "topix" in url
        assert "ABC123" in url

    def test_extract_pns_from_html(self):
        html = """
        <html><body>
            Part number: AB1234567890
            Another: CD9876543210
            Not a PN: 123
        </body></html>
        """
        pns = self.adapter.extract_pns_from_html(html)
        assert len(pns) == 2
        assert any(p['normalized'] == 'AB1234567890' for p in pns)
        assert any(p['normalized'] == 'CD9876543210' for p in pns)

    def test_extract_vehicle_info_finds_jlr_models(self):
        html = """
        <html><body>
            Range Rover Sport
            Discovery 5
            Defender 110
        </body></html>
        """
        vehicles = self.adapter.extract_vehicle_info(html)
        makes = [v['make'] for v in vehicles]
        assert 'JLR' in makes
        models = [v['model'] for v in vehicles]
        assert 'Range Rover' in models or 'Discovery' in models
