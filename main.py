"""FastAPI entry point — single server for customer + owner."""

import asyncio
from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

import config
import database
import llm
import session_memory
from thread_pool import init_thread_pool, shutdown_thread_pool
from registry import get_registry
from routes.customer import router as customer_router
from routes.owner import router as owner_router
from routes.specialist import router as specialist_router
from routes.facebook import router as facebook_router
from routes.instagram import router as instagram_router
from schemas import RootResponse

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    database.startup()
    session_memory.init_memory_store()
    get_registry()
    executor = init_thread_pool()
    asyncio.get_running_loop().set_default_executor(executor)
    logger.info("SmartShop API ready on http://localhost:8000")
    yield
    shutdown_thread_pool()


app = FastAPI(title="SmartShop", version="2.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(customer_router)
app.include_router(owner_router)
app.include_router(specialist_router)
app.include_router(facebook_router)
app.include_router(instagram_router)


# Static file mounts
for name, path in [
    ("/data/uploads", config.USER_UPLOADS_DIR),
    ("/data/tryon", config.TRYON_DIR),
    ("/data/products", config.PRODUCT_IMAGES_DIR),
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
