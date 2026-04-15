"""FastAPI entry point — single server for customer + owner."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

import config
import database
from routes.customer import router as customer_router
from routes.owner import router as owner_router
from routes.specialist import router as specialist_router
from routes.whatsapp import router as whatsapp_router
from routes.facebook import router as facebook_router
from routes.voice import router as voice_router

app = FastAPI(title="SmartShop", version="2.0")

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
app.include_router(whatsapp_router)
app.include_router(facebook_router)
app.include_router(voice_router)

# Static file mounts
for name, path in [
    ("/uploads/user_images", config.USER_IMAGES_DIR),
    ("/uploads/tryon_outputs", config.TRYON_DIR),
    ("/database/images", config.DB_IMAGES_DIR),
]:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    app.mount(name, StaticFiles(directory=str(p)), name=name.strip("/").replace("/", "_"))


@app.on_event("startup")
def startup():
    database.init_db()
    print("[main] SmartShop API ready on http://localhost:8000")


@app.get("/")
async def root():
    return {"app": "SmartShop", "version": "2.0", "status": "running"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
