from openai import AsyncOpenAI
from typing import Optional
import json
import structlog
from app.schemas.battery_scrape_payload import BatteryScrapePayload

logger = structlog.get_logger()

EXTRACTION_PROMPT = """You are an expert automotive battery data extraction system. Given raw HTML from a battery parts website, extract structured battery data.

Extract ONLY fields you can find strong evidence for in the page. Use exact quotes from the page as evidence_quote.

Return a JSON object with these top-level keys:
- meta: {fetcher_used, wave, source_url, page_title}
- part_numbers: array of {raw, normalized, brand, pn_type, evidence_quote}
- properties: object mapping property_code -> {value, unit, evidence_quote, confidence}
- relationships: array of {type, target_pn_or_id, evidence_quote, confidence}
- vehicles: array of {make, model, variant_code, year_from, year_to, engine_code, evidence_quote}

IMPORTANT: For confidence, 0.5 = speculative, 0.7 = likely, 0.9+ = high certainty from clear data.
Return ONLY valid JSON, no markdown or explanation."""


class ExtractionEngine:
    def __init__(self, llm_base_url: str, llm_api_key: str = "not-required", model: str = "qwen3-coder-79b"):
        self.client = AsyncOpenAI(base_url=llm_base_url, api_key=llm_api_key)
        self.model = model

    async def extract(self, html: str, visible_text: str, source_url: str, fetcher: str, wave: int) -> Optional[BatteryScrapePayload]:
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": EXTRACTION_PROMPT},
                    {"role": "user", "content": f"Source URL: {source_url}\n\nVisible text (first 8000 chars):\n{visible_text[:8000]}\n\nFull HTML (first 5000 chars):\n{html[:5000]}"},
                ],
                temperature=0.1,
                max_tokens=4000,
            )

            content = response.choices[0].message.content
            if content.startswith("```"):
                content = "\n".join(content.split("\n")[1:])
                content = content.rsplit("```", 1)[0].strip()

            data = json.loads(content)

            return BatteryScrapePayload(
                _meta={
                    "fetcher": fetcher,
                    "wave": wave,
                    "source_url": source_url,
                    "page_title": data.get("meta", {}).get("page_title", ""),
                },
                part_numbers=data.get("part_numbers", []),
                properties=data.get("properties", {}),
                relationships=data.get("relationships", []),
                vehicles=data.get("vehicles", []),
            )
        except json.JSONDecodeError as e:
            logger.error("extraction_json_parse_failed", error=str(e), content=content[:500] if 'content' in dir() else "")
            return None
        except Exception as e:
            logger.error("extraction_failed", error=str(e))
            return None
