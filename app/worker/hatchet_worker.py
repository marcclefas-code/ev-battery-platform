import os
import asyncio
import structlog
from datetime import datetime
import uuid
import yaml

from hatchet_sdk import Hatchet
from hatchet_sdk.client import WorkflowContext

from app.services.fetcher_registry import FetcherRegistry
from app.services.extractor import ExtractionEngine
from app.services.consensus_merger import ConsensusMerger
from app.services.enrichment_service import EnrichmentService
from app.services.database import get_db_session
from app.services.repositories.battery_entity_repo import BatteryEntityRepository
from app.services.repositories.scrape_plan_repo import ScrapePlanRepository
from app.brand_adapters.porsche_adapter import PorscheAdapter
from app.schemas.battery_scrape_payload import BatteryScrapePayload

logger = structlog.get_logger()

HATCHET_CLIENT_TOKEN = os.getenv("HATCHET_CLIENT_TOKEN", "")
HATCHET_CLIENT_HOST_PORT = os.getenv("HATCHET_CLIENT_HOST_PORT", "127.0.0.1:7070")
HATCHET_CLIENT_TLS_STRATEGY = os.getenv("HATCHET_CLIENT_TLS_STRATEGY", "none")
LITELLM_BASE_URL = os.getenv("LITELLM_BASE_URL", "http://127.0.0.1:18000/v1")

STAGGER_CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "stagger_config.yaml")


def load_stagger_config() -> dict:
    try:
        with open(STAGGER_CONFIG_PATH) as f:
            return yaml.safe_load(f)
    except Exception:
        return {
            "wave_policies": {
                "teile_com": {"waves": 3, "wave_delays_seconds": [0, 300, 900], "jitter_seconds": 30, "escalation_threshold": 0.4, "quorum_required": 2, "fetcher_priority": ["crawl4ai", "scrapling", "camoufox"]},
            },
            "default_policy": {"waves": 2, "wave_delays_seconds": [0, 600], "jitter_seconds": 60, "escalation_threshold": 0.5, "quorum_required": 1, "fetcher_priority": ["crawl4ai"]},
        }


class EVBatteryWorker:
    def __init__(self):
        self.hatchet = Hatchet(
            token=HATCHET_CLIENT_TOKEN,
            host_port=HATCHET_CLIENT_HOST_PORT,
            tls_strategy=HATCHET_CLIENT_TLS_STRATEGY,
        )
        self.extraction_engine = ExtractionEngine(LITELLM_BASE_URL)
        self.merger = ConsensusMerger()
        self.enrichment_service = EnrichmentService()
        self.stagger_config = load_stagger_config()
        self.porsche_adapter = PorscheAdapter()
        self.logger = logger

    def register_workflows(self):
        @self.hatchet.workflow(name="staggered-enrichment", description="Staggered multi-wave battery enrichment")
        class StaggeredEnrichmentWF:
            def __init__(self, context: WorkflowContext):
                self.context = context

            @self.hatchet.step(name="fetch-wave-0", description="Initial crawl4ai fetch")
            async def fetch_wave_0(self, pn: str, source_url: str, entity_id: str) -> dict:
                self.logger.info("wf_fetch_wave_0", pn=pn, workflow_id=self.context.workflow_id())
                fetcher = FetcherRegistry.get("crawl4ai")
                result = await fetcher.fetch(source_url)
                if result.error:
                    return {"status": "failed", "error": result.error}
                payload = await self.extraction_engine.extract(
                    result.html, result.visible_text, source_url, "crawl4ai", 0
                )
                return {
                    "status": "success",
                    "wave": 0,
                    "fetcher": "crawl4ai",
                    "raw_hash": result.raw_hash,
                    "html_length": result.html_length,
                    "visible_text_length": result.visible_text_length,
                    "payload": payload.model_dump() if payload else None,
                }

            @self.hatchet.step(name="fetch-wave-1", description="Secondary scrapling fetch")
            async def fetch_wave_1(self, pn: str, source_url: str, entity_id: str) -> dict:
                self.logger.info("wf_fetch_wave_1", pn=pn, workflow_id=self.context.workflow_id())
                await asyncio.sleep(300)
                fetcher = FetcherRegistry.get("scrapling")
                result = await fetcher.fetch(source_url)
                if result.error:
                    return {"status": "failed", "error": result.error}
                payload = await self.extraction_engine.extract(
                    result.html, result.visible_text, source_url, "scrapling", 1
                )
                return {
                    "status": "success",
                    "wave": 1,
                    "fetcher": "scrapling",
                    "raw_hash": result.raw_hash,
                    "html_length": result.html_length,
                    "visible_text_length": result.visible_text_length,
                    "payload": payload.model_dump() if payload else None,
                }

            @self.hatchet.step(name="merge-results", description="Merge results and persist")
            async def merge_results(self, wave_0_result: dict, wave_1_result: dict, entity_id: str) -> dict:
                self.logger.info("wf_merge_results", entity_id=entity_id, workflow_id=self.context.workflow_id())
                payloads = []
                if wave_0_result.get("payload"):
                    payloads.append(BatteryScrapePayload(**wave_0_result["payload"]))
                if wave_1_result.get("payload"):
                    payloads.append(BatteryScrapePayload(**wave_1_result["payload"]))

                merge_result = await self.merger.merge_payloads(payloads)

                if merge_result["merged"]:
                    await self.enrichment_service.persist_merged_payload(
                        uuid.UUID(entity_id), merge_result["merged"]
                    )

                return {
                    "status": "merged",
                    "score": merge_result["score"],
                    "conflicts": len(merge_result["conflicts"]),
                }

        @self.hatchet.workflow(name="deferred-wave", description="Deferred wave with delay")
        class DeferredWaveWF:
            def __init__(self, context: WorkflowContext):
                self.context = context

            @self.hatchet.step(name="deferred-fetch", description="Delayed fetch after backoff")
            async def deferred_fetch(self, pn: str, source_url: str, delay_seconds: int) -> dict:
                self.logger.info("wf_deferred_fetch", pn=pn, delay=delay_seconds, workflow_id=self.context.workflow_id())
                await asyncio.sleep(delay_seconds)
                fetcher = FetcherRegistry.get("camoufox")
                result = await fetcher.fetch(source_url)
                if result.error:
                    return {"status": "failed", "error": result.error}
                payload = await self.extraction_engine.extract(
                    result.html, result.visible_text, source_url, "camoufox", 2
                )
                return {
                    "status": "success",
                    "wave": 2,
                    "fetcher": "camoufox",
                    "payload": payload.model_dump() if payload else None,
                }

        return [StaggeredEnrichmentWF, DeferredWaveWF]

    async def start(self):
        self.register_workflows()
        await self.hatchet.start()
        self.logger.info("ev_battery_hatchet_worker_started")

    async def stop(self):
        await self.hatchet.stop()
        await FetcherRegistry.close_all()
        self.logger.info("ev_battery_hatchet_worker_stopped")


def run_worker():
    import uvicorn
    worker = EVBatteryWorker()
    asyncio.run(worker.start())


if __name__ == "__main__":
    run_worker()
