"""FastAPI entry point — single server for customer + owner."""

import asyncio
from contextlib import AsyncExitStack, asynccontextmanager
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from api import config, llm
from api import db as database
from api.thread_pool import init_thread_pool, shutdown_thread_pool
from api.registry import get_registry
from api.routes.gate import router as gate_router
from api.routes.auth import router as auth_router
from api.routes.customer import router as customer_router
from api.routes.owner import router as owner_router
from api.routes.specialist import router as specialist_router
from api.routes.facebook import router as facebook_router
from api.routes.instagram import router as instagram_router
from api.routes.tracking import router as tracking_router
from api.schemas import RootResponse
from api.mcp_server import mcp_app
from api.middleware.auth_gate import AuthGateMiddleware
from api.middleware.rate_limit import RateLimitMiddleware
from api.observability import RequestIdMiddleware, setup_logging


setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    config.enforce()  # fail fast on bad/missing secrets

    async with AsyncExitStack() as stack:
        mcp_lifespan = getattr(
            getattr(mcp_app, "router", None), "lifespan_context", None
        )
        if mcp_lifespan is not None:
            await stack.enter_async_context(mcp_lifespan(mcp_app))

        database.startup()
        get_registry()
        executor = init_thread_pool()
        asyncio.get_running_loop().set_default_executor(executor)

        # Warm Gemini singleton — first chat avoids ~2s cold-init.
        try:
            llm._get_model()
            logger.info("Preloaded Gemini chat client")
        except Exception as e:
            logger.warning("Skipped Gemini preload: %s", e)

        logger.info("SmartShop API ready on http://localhost:8000")
        try:
            yield
        finally:
            shutdown_thread_pool()
            database.close_pool()


app = FastAPI(title="SmartShop", version="2.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Pure ASGI middleware stack. FastAPI runs these in reverse-add order, so the
# request-id middleware is added last to ensure it wraps everything (including
# auth + rate limit) and every log line picks up the id.
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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)
