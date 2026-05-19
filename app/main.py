from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import structlog

from app.api.routes import scrape, entities, search, parts, vehicles, health, reviews, xref, waves, config, auth
from app.api.middleware.logging import RequestLoggingMiddleware

structlog.configure(processors=[])
logger = structlog.get_logger()

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
    logger.info("ev_battery_platform_starting")


@app.on_event("shutdown")
async def shutdown_event():
    from app.services.database import dispose_engine
    from app.services.fetcher_registry import FetcherRegistry
    await FetcherRegistry.close_all()
    await dispose_engine()
    logger.info("ev_battery_platform_shutdown")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8090)
