import os
import asyncio
import structlog
from datetime import datetime
import uuid
import yaml

from hatchet_sdk.loader import ClientConfig, ClientTLSConfig
from hatchet_sdk.worker import Worker
from hatchet_sdk.hatchet import workflow, step
from hatchet_sdk.context import Context

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
HATCHET_CLIENT_HOST_PORT = os.getenv("HATCHET_CLIENT_HOST_PORT", "hatchet-hatchet-engine-1:7070")
HATCHET_CLIENT_TLS_STRATEGY = os.getenv("HATCHET_CLIENT_TLS_STRATEGY", "none")
LITELLM_BASE_URL = os.getenv("LITELLM_BASE_URL", "http://intelligence-litellm:4000/v1")

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


def create_hatchet_worker() -> Worker:
    tls_config = None
    if HATCHET_CLIENT_TLS_STRATEGY != "none":
        tls_config = ClientTLSConfig(
            tls_strategy=HATCHET_CLIENT_TLS_STRATEGY,
            cert_file="",
            key_file="",
            ca_file="",
            server_name="",
        )

    config = ClientConfig(
        token=HATCHET_CLIENT_TOKEN,
        host_port=HATCHET_CLIENT_HOST_PORT,
        tls_config=tls_config,
    )

    worker = Worker(name="ev-battery-worker", config=config, debug=False)
    return worker


@workflow(name="staggered-enrichment", on_events=["staggered-enrichment-trigger"])
class StaggeredEnrichmentWF:
    def __init__(self):
        self.extraction_engine = ExtractionEngine(LITELLM_BASE_URL)
        self.merger = ConsensusMerger()
        self.enrichment_service = EnrichmentService()
        self.stagger_config = load_stagger_config()
        self.porsche_adapter = PorscheAdapter()

    @step(name="fetch-wave-0", timeout="10m")
    async def fetch_wave_0(self, context: Context) -> dict:
        step_run = context.step_run()
        pn = step_run.workflow_input().get("pn", "")
        source_url = step_run.workflow_input().get("source_url", "")
        entity_id = step_run.workflow_input().get("entity_id", "")

        logger.info("wf_fetch_wave_0", pn=pn, workflow_id=context.workflow_run_id())

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

    @step(name="fetch-wave-1", timeout="10m", parents=["fetch-wave-0"])
    async def fetch_wave_1(self, context: Context) -> dict:
        step_run = context.step_run()
        pn = step_run.workflow_input().get("pn", "")
        source_url = step_run.workflow_input().get("source_url", "")
        entity_id = step_run.workflow_input().get("entity_id", "")

        logger.info("wf_fetch_wave_1", pn=pn, workflow_id=context.workflow_run_id())
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

    @step(name="merge-results", timeout="5m", parents=["fetch-wave-1"])
    async def merge_results(self, context: Context) -> dict:
        step_run = context.step_run()
        wave_0_result = step_run.parent_step_run_outputs().get("fetch-wave-0", {})
        wave_1_result = step_run.parent_step_run_outputs().get("fetch-wave-1", {})
        entity_id = step_run.workflow_input().get("entity_id", "")

        logger.info("wf_merge_results", entity_id=entity_id, workflow_id=context.workflow_run_id())

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


@workflow(name="deferred-wave", on_events=["deferred-wave-trigger"])
class DeferredWaveWF:
    def __init__(self):
        self.extraction_engine = ExtractionEngine(LITELLM_BASE_URL)

    @step(name="deferred-fetch", timeout="15m")
    async def deferred_fetch(self, context: Context) -> dict:
        step_run = context.step_run()
        pn = step_run.workflow_input().get("pn", "")
        source_url = step_run.workflow_input().get("source_url", "")
        delay_seconds = step_run.workflow_input().get("delay_seconds", 0)

        logger.info("wf_deferred_fetch", pn=pn, delay=delay_seconds, workflow_id=context.workflow_run_id())
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


def register_workflows(worker: Worker):
    worker.register_workflow(StaggeredEnrichmentWF)
    worker.register_workflow(DeferredWaveWF)


def run_worker():
    logger.info("starting_ev_battery_hatchet_worker")
    worker = create_hatchet_worker()
    register_workflows(worker)
    worker.start()
    logger.info("ev_battery_hatchet_worker_stopped")


if __name__ == "__main__":
    run_worker()
