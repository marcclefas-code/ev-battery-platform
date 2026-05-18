import pytest
from app.brand_adapters.porsche_adapter import PorscheAdapter, normalize_porsche_pn


class TestNormalizePorschePN:
    def test_normalize_porsche_pn_full_number(self):
        assert normalize_porsche_pn('9701234567890') == '9701234567890'

    def test_normalize_porsche_pn_strips_spaces(self):
        assert normalize_porsche_pn('970 123 456 78 90') == '9701234567890'

    def test_normalize_porsche_pn_strips_dashes(self):
        assert normalize_porsche_pn('970-123-456-78-90') == '9701234567890'


class TestPorscheAdapter:
    def setup_method(self):
        self.adapter = PorscheAdapter()

    def test_brand_is_porsche(self):
        assert self.adapter.BRAND == 'porsche'

    def test_build_search_url(self):
        url = self.adapter.build_search_url('9701234567890')
        assert 'teile.com' in url
        assert '9701234567890' in url

    def test_build_part_url(self):
        url = self.adapter.build_part_url('9701234567890')
        assert 'parts/9701234567890' in url
