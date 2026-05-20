import base64
import json
import hatchet_sdk.token as _hatchet_token

def _patched_extract_claims(token: str) -> dict:
    try:
        parts = token.strip().split(".")
        if len(parts) != 3:
            raise ValueError("Invalid token format")
        segment = parts[1].replace(" ", "").replace("-", "+").replace("_", "/")
        padding = segment + "=" * ((4 - len(segment) % 4) % 4)
        decoded = base64.b64decode(padding)
        return json.loads(decoded)
    except Exception as e:
        raise ValueError(f"Invalid token format: {e}")

_hatchet_token.extract_claims_from_jwt = _patched_extract_claims

import os
import asyncio
import sys
import structlog
import uuid
import yaml

import hatchet_sdk.worker
import hatchet_sdk.context
import hatchet_sdk.hatchet

_original_register_workflow = hatchet_sdk.worker.Worker.register_workflow

def _patched_register_workflow(self, workflow_cls):
    """Patch for hatchet-sdk 0.38.x bug: get_name/get_create_opts are closures
    defined in WorkflowMeta.__new__ that take 'self' and 'namespace', but when
    called on the CLASS (not an instance), Python doesn't bind 'self'.
    Fix: create an instance and call methods on the instance for proper descriptor binding."""
    namespace = self.client.config.namespace

    try:
        workflow_instance = workflow_cls()
    except TypeError:
        workflow_instance = None

    try:
        if workflow_instance:
            workflow_name = workflow_instance.get_name(namespace)
            workflow_opts = workflow_instance.get_create_opts(namespace)
        else:
            workflow_name = workflow_cls.get_name(namespace)
            workflow_opts = workflow_cls.get_create_opts(namespace)

        self.client.admin.put_workflow(workflow_name, workflow_opts)
    except Exception as e:
        from hatchet_sdk.logger import logger
        logger.error(f"failed to register workflow: {workflow_name if 'workflow_name' in dir() else 'unknown'}")
        logger.error(e)
        sys.exit(1)

    def create_action_function(action_func):
        def action_function(context):
            return action_func(workflow_instance or workflow_cls, context)

        if asyncio.iscoroutinefunction(action_func):
            action_function.is_coroutine = True
        else:
            action_function.is_coroutine = False

        return action_function

    actions_method = workflow_instance.get_actions if workflow_instance else workflow_cls.get_actions
    for action_name, action_func in actions_method(namespace):
        self.action_registry[action_name] = create_action_function(action_func)

hatchet_sdk.worker.Worker.register_workflow = _patched_register_workflow

from hatchet_sdk.loader import ClientConfig, ClientTLSConfig
from hatchet_sdk.worker import Worker
from hatchet_sdk.hatchet import workflow, step
from hatchet_sdk.context import Context

from app.services.fetcher_registry import FetcherRegistry
from app.services.extractor import ExtractionEngine
from app.services.consensus_merger import ConsensusMerger
from app.services.enrichment_service import EnrichmentService
from app.brand_adapters.porsche_adapter import PorscheAdapter
from app.schemas.battery_scrape_payload import BatteryScrapePayload

logger = structlog.get_logger()

HATCHET_CLIENT_TOKEN = os.getenv("HATCHET_CLIENT_TOKEN", "")
HATCHET_CLIENT_HOST_PORT = os.getenv("HATCHET_CLIENT_HOST_PORT", "hatchet-hatchet-engine-1:7070")
HATCHET_CLIENT_TLS_STRATEGY = os.getenv("HATCHET_CLIENT_TLS_STRATEGY", "tls")
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
    tls_config = ClientTLSConfig(
        tls_strategy=HATCHET_CLIENT_TLS_STRATEGY,
        cert_file="",
        key_file="",
        ca_file="",
        server_name=HATCHET_CLIENT_HOST_PORT.split(":")[0] if HATCHET_CLIENT_HOST_PORT else "localhost",
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
        wf_input = context.workflow_input()
        pn = wf_input.get("pn", "")
        source_url = wf_input.get("source_url", "")
        entity_id = wf_input.get("entity_id", "")

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
        wf_input = context.workflow_input()
        pn = wf_input.get("pn", "")
        source_url = wf_input.get("source_url", "")
        entity_id = wf_input.get("entity_id", "")

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
        wf_input = context.workflow_input()
        entity_id = wf_input.get("entity_id", "")

        wave_0_result = context.step_output("fetch-wave-0")
        wave_1_result = context.step_output("fetch-wave-1")

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
        wf_input = context.workflow_input()
        pn = wf_input.get("pn", "")
        source_url = wf_input.get("source_url", "")
        delay_seconds = wf_input.get("delay_seconds", 0)

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
