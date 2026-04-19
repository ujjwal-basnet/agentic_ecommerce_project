"""FastAPI entry point — single server for customer + owner."""

import asyncio
from contextlib import AsyncExitStack, asynccontextmanager
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

import config
import database
import llm
import session_memory
import storage
from google_client import get_chat_model, get_genai_client
from thread_pool import init_thread_pool, shutdown_thread_pool
from registry import get_registry
from routes.auth import router as auth_router
from routes.customer import router as customer_router
from routes.owner import router as owner_router
from routes.specialist import router as specialist_router
from routes.facebook import router as facebook_router
from routes.instagram import router as instagram_router
from routes.tracking import router as tracking_router
from schemas import RootResponse
from mcp_server import mcp_app

from datetime import datetime, timezone, timedelta

_NPT = timezone(timedelta(hours=5, minutes=45))


class _NptFormatter(logging.Formatter):
    def formatTime(self, record, datefmt=None):
        dt = datetime.fromtimestamp(record.created, tz=_NPT)
        return dt.strftime("%b %-d, %-I:%M:%S%p").lower()  # e.g. "apr 18, 2:30:45am"


def _setup_logging():
    fmt = _NptFormatter("%(asctime)s  %(levelname)-8s  %(name)s  %(message)s")
    handler = logging.StreamHandler()
    handler.setFormatter(fmt)
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers.clear()
    root.addHandler(handler)


_setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with AsyncExitStack() as stack:
        mcp_lifespan = getattr(getattr(mcp_app, "router", None), "lifespan_context", None)
        if mcp_lifespan is not None:
            await stack.enter_async_context(mcp_lifespan(mcp_app))

        database.startup()
        session_memory.init_memory_store()
        storage.ensure_buckets()
        get_registry()
        executor = init_thread_pool()
        asyncio.get_running_loop().set_default_executor(executor)

        # Warm Gemini singletons — first chat/try-on avoids ~2s cold-init.
        for name, fn in (("chat", get_chat_model), ("genai", get_genai_client)):
            try:
                fn()
                logger.info("Preloaded Gemini %s client", name)
            except Exception as e:
                logger.warning("Skipped Gemini %s preload: %s", name, e)

        logger.info("SmartShop API ready on http://localhost:8000")
        try:
            yield
        finally:
            shutdown_thread_pool()


app = FastAPI(title="SmartShop", version="2.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    app.mount(name, StaticFiles(directory=str(p)), name=name.strip("/").replace("/", "_"))



@app.get("/", response_model=RootResponse)
async def root():
    return {"app": "SmartShop", "version": "2.0", "status": "running"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
