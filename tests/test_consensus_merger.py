import pytest
from app.services.consensus_merger import ConsensusMerger
from app.schemas.battery_scrape_payload import BatteryScrapePayload, MetaInfo, PartNumberItem, PropertyItem


class TestConsensusMerger:
    def setup_method(self):
        self.merger = ConsensusMerger()

    def _make_payload(self, wave=0, pns=None, props=None, vehicles=None):
        return BatteryScrapePayload(
            _meta=MetaInfo(fetcher='crawl4ai', wave=wave, source_url='https://example.com'),
            part_numbers=[PartNumberItem(**pn) for pn in (pns or [])],
            properties={k: PropertyItem(**v) for k, v in (props or {}).items()},
        )

    @pytest.mark.asyncio
    async def test_merge_empty_payloads(self):
        result = await self.merger.merge_payloads([])
        assert result['merged'] is None
        assert result['score'] == 0.0

    @pytest.mark.asyncio
    async def test_merge_single_payload(self):
        payload = self._make_payload(
            pns=[{'raw': 'ABC123', 'normalized': 'ABC123', 'brand': 'porsche'}],
            props={'nominal_voltage': {'value': 400, 'unit': 'V', 'confidence': 0.9}},
        )
        result = await self.merger.merge_payloads([payload])
        assert result['merged'] is not None
        assert result['score'] > 0.0
        assert len(result['merged']['part_numbers']) == 1
        assert result['merged']['properties']['nominal_voltage']['value'] == 400

    @pytest.mark.asyncio
    async def test_merge_deduplicates_part_numbers(self):
        p1 = self._make_payload(pns=[{'raw': 'ABC123', 'normalized': 'ABC123', 'brand': 'porsche'}])
        p2 = self._make_payload(pns=[{'raw': 'ABC123', 'normalized': 'ABC123', 'brand': 'porsche'}])
        result = await self.merger.merge_payloads([p1, p2])
        assert len(result['merged']['part_numbers']) == 1

    @pytest.mark.asyncio
    async def test_merge_takes_higher_confidence_property(self):
        p1 = self._make_payload(
            props={'nominal_voltage': {'value': 400, 'unit': 'V', 'confidence': 0.5}}
        )
        p2 = self._make_payload(
            props={'nominal_voltage': {'value': 400, 'unit': 'V', 'confidence': 0.9}}
        )
        result = await self.merger.merge_payloads([p1, p2])
        assert result['merged']['properties']['nominal_voltage']['confidence'] == 0.9

    @pytest.mark.asyncio
    async def test_detects_conflict_on_different_values(self):
        p1 = self._make_payload(
            props={'nominal_voltage': {'value': 400, 'unit': 'V', 'confidence': 0.8}}
        )
        p2 = self._make_payload(
            props={'nominal_voltage': {'value': 420, 'unit': 'V', 'confidence': 0.8}}
        )
        result = await self.merger.merge_payloads([p1, p2])
        assert len(result['conflicts']) == 1
        assert result['conflicts'][0]['field'] == 'nominal_voltage'
        assert '400' in result['conflicts'][0]['conflicting_values']
        assert '420' in result['conflicts'][0]['conflicting_values']

    @pytest.mark.asyncio
    async def test_no_conflict_on_same_values(self):
        p1 = self._make_payload(
            props={'nominal_voltage': {'value': 400, 'unit': 'V', 'confidence': 0.8}}
        )
        p2 = self._make_payload(
            props={'nominal_voltage': {'value': 400, 'unit': 'V', 'confidence': 0.9}}
        )
        result = await self.merger.merge_payloads([p1, p2])
        assert len(result['conflicts']) == 0

    @pytest.mark.asyncio
    async def test_consensus_score_reflects_agreement(self):
        p1 = self._make_payload(
            pns=[{'raw': 'ABC123', 'normalized': 'ABC123', 'brand': 'porsche'}],
            props={'nominal_voltage': {'value': 400, 'unit': 'V', 'confidence': 0.9}},
        )
        p2 = self._make_payload(
            pns=[{'raw': 'ABC123', 'normalized': 'ABC123', 'brand': 'porsche'}],
            props={'nominal_voltage': {'value': 400, 'unit': 'V', 'confidence': 0.9}},
        )
        result = await self.merger.merge_payloads([p1, p2])
        assert result['score'] > 0.6

    @pytest.mark.asyncio
    async def test_winning_payload_has_most_data(self):
        p1 = self._make_payload(
            props={'nominal_voltage': {'value': 400, 'unit': 'V', 'confidence': 0.5}}
        )
        p2 = self._make_payload(
            pns=[{'raw': 'ABC123', 'normalized': 'ABC123', 'brand': 'porsche'}],
            props={'nominal_voltage': {'value': 400, 'unit': 'V', 'confidence': 0.5}, 'nominal_capacity': {'value': 60, 'unit': 'Ah', 'confidence': 0.5}},
        )
        result = await self.merger.merge_payloads([p1, p2])
        assert 'nominal_capacity' in result['merged']['properties']
