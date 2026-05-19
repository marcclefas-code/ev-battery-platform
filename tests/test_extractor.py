import pytest
from app.services.extractor import ExtractionEngine

pytestmark = pytest.mark.asyncio


class TestExtractionEngine:
    def setup_method(self):
        self.engine = ExtractionEngine(
            llm_base_url="http://localhost:18000/v1",
            llm_api_key="not-required",
            model="qwen3-coder-79b",
        )

    @pytest.mark.asyncio
    async def test_extraction_engine_initializes(self):
        assert self.engine.model == "qwen3-coder-79b"
        assert "qwen3" in self.engine.client.base_url.path

    @pytest.mark.asyncio
    async def test_extraction_prompt_includes_key_instructions(self):
        from app.services.extractor import EXTRACTION_PROMPT
        assert "part_numbers" in EXTRACTION_PROMPT
        assert "properties" in EXTRACTION_PROMPT
        assert "nominal_voltage" in EXTRACTION_PROMPT or "battery" in EXTRACTION_PROMPT.lower()
        assert "evidence_quote" in EXTRACTION_PROMPT
