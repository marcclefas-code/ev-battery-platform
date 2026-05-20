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

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import scrape, entities, search, parts, vehicles, health, reviews, xref, waves, config, auth
from app.api.middleware.logging import RequestLoggingMiddleware

app = FastAPI(
    title="EV Battery Intelligence Platform",
    version="3.0.0",
    description="Staggered scraping, enrichment, and cross-reference for EV battery data",
)

app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(scrape.router)
app.include_router(entities.router)
app.include_router(search.router)
app.include_router(parts.router)
app.include_router(vehicles.router)
app.include_router(health.router)
app.include_router(reviews.router)
app.include_router(xref.router)
app.include_router(waves.router)
app.include_router(config.router)


@app.get("/")
async def root():
    return {"service": "ev-battery-platform", "version": "3.0.0"}


@app.on_event("startup")
async def startup_event():
    print("EV Battery Platform starting...")


@app.on_event("shutdown")
async def shutdown_event():
    from app.services.database import dispose_engine
    from app.services.fetcher_registry import FetcherRegistry
    await FetcherRegistry.close_all()
    await dispose_engine()
    print("EV Battery Platform shutting down...")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8090)
