import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.config import ALLOWED_ORIGINS, ENVIRONMENT, LOG_LEVEL
from src.api.routes_scenes import router as scenes_router
from src.api.routes_media import router as media_router
from src.api.routes_pipeline import router as pipeline_router
from src.api.routes_intake import router as intake_router

logging.basicConfig(level=getattr(logging, LOG_LEVEL, logging.INFO))
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Lego Worlds API",
    version="0.1.0",
    docs_url="/docs" if ENVIRONMENT == "development" else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(scenes_router)
app.include_router(media_router)
app.include_router(pipeline_router)
app.include_router(intake_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
