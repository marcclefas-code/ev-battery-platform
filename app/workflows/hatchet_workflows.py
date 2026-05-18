from hatchet import WorkflowSpec, WorkflowContext
from typing import Any
import structlog

logger = structlog.get_logger()


class StaggeredEnrichmentHatchetWorkflow:
    def __init__(self, stagger_config: dict, llm_base_url: str):
        self.stagger_config = stagger_config
        self.llm_base_url = llm_base_url

    def define(self) -> WorkflowSpec:
        return WorkflowSpec(
            name="staggered-enrichment",
            description="Staggered multi-wave battery enrichment with quorum-based escalation",
            steps=[
                {
                    "id": "fetch-wave-0",
                    "name": "Fetch Wave 0",
                    "description": "Initial fetch with crawl4ai",
                },
                {
                    "id": "fetch-wave-1",
                    "name": "Fetch Wave 1",
                    "description": "Secondary fetch with scrapling",
                },
                {
                    "id": "merge-results",
                    "name": "Merge Results",
                    "description": "Merge and deduplicate results from all waves",
                },
            ],
        )


def staggered_enrichment_worker():
    @WorkflowSpec(
        name="staggered-enrichment",
        description="Staggered multi-wave battery enrichment",
    )
    class _Workflow:
        def __init__(self, context: WorkflowContext):
            self.context = context

        async def fetch_wave_0(self) -> dict:
            logger.info("hatchet_workflow_fetch_wave_0", workflow_id=self.context.workflow_id())
            return {"status": "wave_0_fetched", "wave": 0}

        async def fetch_wave_1(self) -> dict:
            logger.info("hatchet_workflow_fetch_wave_1", workflow_id=self.context.workflow_id())
            return {"status": "wave_1_fetched", "wave": 1}

        async def merge_results(self, wave_0_result: dict, wave_1_result: dict) -> dict:
            logger.info("hatchet_workflow_merge", workflow_id=self.context.workflow_id())
            return {
                "status": "merged",
                "waves": 2,
                "wave_0": wave_0_result,
                "wave_1": wave_1_result,
            }

    return _Workflow
