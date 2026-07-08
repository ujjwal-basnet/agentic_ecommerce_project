"""FastAPI entry point — single server for customer + owner."""

import asyncio
import logging
from contextlib import AsyncExitStack, asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from api import config
from api import db as database
from api.agents import get_agent_registry
from api.mcp_server import mcp_app
from api.middleware.auth_gate import AuthGateMiddleware
from api.middleware.rate_limit import RateLimitMiddleware
from api.observability import RequestIdMiddleware, setup_logging, setup_logfire
from api.rag.ingest import ingest_all_products
from api.routes.auth import router as auth_router
from api.routes.customer import router as customer_router
from api.routes.facebook import router as facebook_router
from api.routes.gate import router as gate_router
from api.routes.instagram import router as instagram_router
from api.routes.owner import router as owner_router
from api.routes.specialist import router as specialist_router
from api.routes.tracking import router as tracking_router
from api.schemas import RootResponse
from api.thread_pool import init_thread_pool, shutdown_thread_pool


setup_logging()
logger = logging.getLogger(__name__)


async def _background_ingest():
    """Ingest products into Pinecone in the background so startup stays fast.

    We force re-ingestion every startup because product prices/descriptions
    may have changed since the last run. 16 products × one integrated embed
    call is ~1 second — acceptable overhead.
    """
    try:
        result = await ingest_all_products(force=True)
        logger.info("Pinecone ingest result: %s", result)
    except Exception:
        logger.exception("Background Pinecone ingest failed")


@asynccontextmanager
async def lifespan(app: FastAPI):
    config.enforce()

    async with AsyncExitStack() as stack:
        mcp_lifespan = getattr(
            getattr(mcp_app, "router", None), "lifespan_context", None
        )
        if mcp_lifespan is not None:
            await stack.enter_async_context(mcp_lifespan(mcp_app))

        database.startup()
        get_agent_registry()
        executor = init_thread_pool()
        asyncio.get_running_loop().set_default_executor(executor)

        # Fire-and-forget Pinecone ingest — don't block startup
        asyncio.create_task(_background_ingest())

        logger.info("SmartShop API ready on http://localhost:8000")
        try:
            yield
        finally:
            shutdown_thread_pool()
            database.close_pool()


app = FastAPI(title="SmartShop", version="2.0", lifespan=lifespan)

# Logfire must be configured before middleware/routes are added so it can
# instrument FastAPI properly.
setup_logfire(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(AuthGateMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(RequestIdMiddleware)

app.include_router(gate_router)
app.include_router(auth_router)
app.include_router(customer_router)
app.include_router(owner_router)
app.include_router(specialist_router)
app.include_router(facebook_router)
app.include_router(instagram_router)
app.include_router(tracking_router)
app.mount("/mcp", mcp_app)


# Static file mounts
for name, path in [
    ("/data/uploads", config.USER_UPLOADS_DIR),
    ("/data/tryon", config.TRYON_DIR),
    ("/data/products", config.PRODUCT_IMAGES_DIR),
    ("/data/campaigns", config.CAMPAIGN_DIR),
    ("/data/memes", config.MEME_ASSETS_DIR),
]:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    app.mount(
        name, StaticFiles(directory=str(p)), name=name.strip("/").replace("/", "_")
    )


@app.get("/", response_model=RootResponse)
async def root():
    return {"app": "SmartShop", "version": "2.0", "status": "running"}


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/admin/reingest")
async def admin_reingest():
    """Manual re-ingestion endpoint — forces Pinecone rebuild from Postgres."""
    result = await ingest_all_products(force=True)
    return result


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)
