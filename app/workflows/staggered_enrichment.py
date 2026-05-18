from datetime import datetime, timedelta
from typing import Optional
import hashlib
import asyncio
import structlog
from app.services.fetcher_registry import FetcherRegistry
from app.services.extractor import ExtractionEngine
from app.schemas.battery_scrape_payload import BatteryScrapePayload

logger = structlog.get_logger()


class StaggeredEnrichmentWorkflow:
    def __init__(self, stagger_config: dict, llm_base_url: str):
        self.stagger_config = stagger_config
        self.extraction_engine = ExtractionEngine(llm_base_url)

    def _get_policy(self, source_domain: str) -> dict:
        for key, policy in self.stagger_config.get('wave_policies', {}).items():
            if key in source_domain:
                return policy
        return self.stagger_config.get('default_policy', {})

    def _compute_delay(self, wave: int, policy: dict) -> float:
        delays = policy.get('wave_delays_seconds', [0])
        jitter = policy.get('jitter_seconds', 0)
        base_delay = delays[min(wave, len(delays) - 1)]
        import random
        return base_delay + random.uniform(0, jitter)

    async def run_wave(self, plan_id: str, wave: int, url: str, fetcher_name: str, policy: dict) -> dict:
        delay = self._compute_delay(wave, policy)
        if delay > 0:
            await asyncio.sleep(delay)

        fetcher = FetcherRegistry.get(fetcher_name)
        fetch_result = await fetcher.fetch(url)

        if fetch_result.error:
            return {
                'wave': wave,
                'fetcher': fetcher_name,
                'status': 'failed',
                'error': fetch_result.error,
            }

        payload = await self.extraction_engine.extract(
            html=fetch_result.html,
            visible_text=fetch_result.visible_text,
            source_url=url,
            fetcher=fetcher_name,
            wave=wave,
        )

        return {
            'wave': wave,
            'fetcher': fetcher_name,
            'status': 'success' if payload else 'failed',
            'raw_hash': fetch_result.raw_hash,
            'html_length': fetch_result.html_length,
            'visible_text_length': fetch_result.visible_text_length,
            'payload': payload,
        }

    async def run_staggered_waves(self, plan_id: str, urls: list[str], source_domain: str) -> list[dict]:
        policy = self._get_policy(source_domain)
        waves_planned = policy.get('waves', 2)
        fetcher_priority = policy.get('fetcher_priority', ['crawl4ai'])
        quorum = policy.get('quorum_required', 1)
        escalation_threshold = policy.get('escalation_threshold', 0.5)

        results = []
        for wave_num in range(waves_planned):
            wave_tasks = []
            for url in urls:
                fetcher_name = fetcher_priority[wave_num % len(fetcher_priority)]
                task = self.run_wave(plan_id, wave_num, url, fetcher_name, policy)
                wave_tasks.append(task)

            wave_results = await asyncio.gather(*wave_tasks)
            results.extend(wave_results)

            successful = [r for r in wave_results if r['status'] == 'success']
            if len(successful) >= quorum:
                self.logger.info("quorum_reached", wave=wave_num, successful=len(successful))
                break

            avg_score = sum(
                r.get('payload', {}).get('_meta', {}).get('extraction_score', 0)
                for r in successful
            ) / max(len(successful), 1)

            if wave_num < waves_planned - 1 and avg_score < escalation_threshold:
                self.logger.info("escalating_to_next_wave", wave=wave_num, score=avg_score)
            elif wave_num >= waves_planned - 1:
                break

        return results


class DeferredWaveWorkflow:
    def __init__(self, stagger_config: dict, llm_base_url: str):
        self.stagger_config = stagger_config
        self.extraction_engine = ExtractionEngine(llm_base_url)

    async def schedule_deferred_wave(self, plan_id: str, wave: int, url: str, fetcher_name: str, delay_seconds: float) -> str:
        await asyncio.sleep(delay_seconds)
        return f"deferred:{plan_id}:wave{wave}:{url}"
