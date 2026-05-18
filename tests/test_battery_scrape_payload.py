import pytest
from pydantic import ValidationError
from app.schemas.battery_scrape_payload import BatteryScrapePayload, MetaInfo


class TestBatteryScrapePayload:
    def test_valid_payload(self):
        payload = BatteryScrapePayload(
            _meta=MetaInfo(fetcher='crawl4ai', wave=0, source_url='https://example.com'),
            part_numbers=[{'raw': 'ABC123', 'normalized': 'ABC123', 'brand': 'porsche'}],
            properties={'nominal_voltage': {'value': 400, 'unit': 'V', 'confidence': 0.9}},
        )
        assert payload._meta.fetcher == 'crawl4ai'
        assert payload._meta.wave == 0
        assert len(payload.part_numbers) == 1
        assert payload.properties['nominal_voltage']['value'] == 400

    def test_default_wave_is_zero(self):
        payload = BatteryScrapePayload(
            _meta=MetaInfo(fetcher='scrapling', wave=0, source_url='https://example.com'),
        )
        assert payload._meta.wave == 0

    def test_empty_payload_is_valid(self):
        payload = BatteryScrapePayload(
            _meta=MetaInfo(fetcher='camoufox', wave=0, source_url='https://example.com'),
        )
        assert payload.part_numbers == []
        assert payload.properties == {}
