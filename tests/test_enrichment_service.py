import pytest
from app.services.enrichment_service import EnrichmentService

pytestmark = pytest.mark.asyncio


class TestEnrichmentService:
    def setup_method(self):
        self.service = EnrichmentService()

    def test_service_has_merger(self):
        assert hasattr(self.service, 'merger')
        assert self.service.merger is not None

    def test_service_has_correct_merger_type(self):
        from app.services.consensus_merger import ConsensusMerger
        assert isinstance(self.service.merger, ConsensusMerger)
