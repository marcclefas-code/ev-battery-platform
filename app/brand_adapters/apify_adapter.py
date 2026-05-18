import httpx
from typing import Optional
import structlog

logger = structlog.get_logger()


class ApifyAdapter:
    BRAND = "apify"
    SOURCE_KIND = "apify_actor"

    def __init__(self, api_token: Optional[str] = None, actor_id: Optional[str] = None):
        self.api_token = api_token or ""
        self.actor_id = actor_id or ""
        self.client = httpx.AsyncClient(timeout=60.0)
        self.logger = logger
        self.base_url = "https://api.apify.com/v2"

    async def close(self):
        await self.client.aclose()

    async def run_actor(self, actor_id: str = None, input_data: dict = None) -> Optional[str]:
        actor_id = actor_id or self.actor_id
        try:
            response = await self.client.post(
                f"{self.base_url}/acts/{actor_id}/runs",
                headers={"Authorization": f"Bearer {self.api_token}"},
                json={"input": input_data or {}},
            )
            response.raise_for_status()
            data = response.json()
            return data.get("data", {}).get("id")
        except Exception as e:
            self.logger.error("apify_actor_run_failed", actor_id=actor_id, error=str(e))
            return None

    async def get_run_result(self, run_id: str, timeout: int = 60) -> Optional[dict]:
        import asyncio
        for _ in range(timeout // 5):
            try:
                response = await self.client.get(
                    f"{self.base_url}/acts/~{run_id}/runs/{run_id}",
                    headers={"Authorization": f"Bearer {self.api_token}"},
                )
                response.raise_for_status()
                data = response.json()
                status = data.get("data", {}).get("status")
                if status == "succeeded":
                    return data.get("data", {}).get("defaultDatasetId")
                elif status in ("failed", "aborted", "timed-out"):
                    return None
                await asyncio.sleep(5)
            except Exception as e:
                self.logger.error("apify_status_check_failed", run_id=run_id, error=str(e))
                return None
        return None

    async def get_dataset_items(self, dataset_id: str) -> list[dict]:
        try:
            response = await self.client.get(
                f"{self.base_url}/datasets/{dataset_id}/items",
                headers={"Authorization": f"Bearer {self.api_token}"},
                params={"clean": "true"},
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.logger.error("apify_dataset_fetch_failed", dataset_id=dataset_id, error=str(e))
            return []
