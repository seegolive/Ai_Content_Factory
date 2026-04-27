"""FastAPI application entry point."""
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger

from app.core.config import settings
from app.core.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting AI Content Factory API...")
    await init_db()
    logger.info("Database initialized.")
    yield
    logger.info("Shutting down API.")


app = FastAPI(
    title="AI Content Factory",
    description="Automated video-to-clips pipeline with AI analysis",
    version="0.1.0",
    docs_url="/docs" if settings.APP_ENV != "production" else None,
    redoc_url="/redoc" if settings.APP_ENV != "production" else None,
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL, "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    duration = time.perf_counter() - start
    logger.info(f"{request.method} {request.url.path} → {response.status_code} ({duration:.3f}s)")
    return response


# Exception handlers
@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    # Pydantic v2 may include non-serializable ctx (e.g. ValueError objects) — convert to str
    errors = []
    for err in exc.errors():
        e = dict(err)
        if "ctx" in e and "error" in e["ctx"]:
            e["ctx"] = {k: str(v) for k, v in e["ctx"].items()}
        errors.append(e)
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": errors},
    )


@app.exception_handler(Exception)
async def generic_error_handler(request: Request, exc: Exception):
    logger.exception(f"Unhandled error on {request.url.path}: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"},
    )


# Protected file serving — requires JWT auth
# IMPORTANT: Do NOT use StaticFiles(directory=...) for user content — that serves files without auth.
# Use the /api/v1/clips/{id}/stream endpoint (authenticated) to serve clip files.
import os

os.makedirs(settings.LOCAL_STORAGE_PATH, exist_ok=True)


# Routers
from app.api.routes import analytics, auth, clips, settings, videos, youtube

app.include_router(auth.router, prefix="/api/v1", tags=["auth"])
app.include_router(videos.router, prefix="/api/v1", tags=["videos"])
app.include_router(clips.router, prefix="/api/v1", tags=["clips"])
app.include_router(youtube.router, prefix="/api/v1", tags=["youtube"])
app.include_router(analytics.router, prefix="/api/v1", tags=["analytics"])
app.include_router(settings.router, prefix="/api/v1", tags=["settings"])


@app.get("/health", tags=["system"])
async def health_check():
    """Health check endpoint."""
    from app.core.database import engine

    try:
        async with engine.connect() as conn:
            await conn.execute(__import__("sqlalchemy").text("SELECT 1"))
        db_status = "ok"
    except Exception as e:
        db_status = f"error: {e}"

    return {
        "status": "ok",
        "version": "0.1.0",
        "environment": settings.APP_ENV,
        "components": {
            "database": db_status,
            "storage": os.path.exists(settings.LOCAL_STORAGE_PATH),
        },
    }
