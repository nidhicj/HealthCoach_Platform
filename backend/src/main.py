"""FastAPI application entry point. Per ADR-0001/ADR-0006."""
import uuid
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from src.auth.router import router as auth_router
from src.config import get_settings
from src.telemetry.log import get_logger
from src.telemetry.sentry import init_sentry


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    init_sentry()
    yield


app = FastAPI(
    title="Parivarthan API",
    version=get_settings().app_version,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next: Any) -> Response:
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    request.state.request_id = request_id
    response: Response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


app.include_router(auth_router)


@app.get("/healthz", include_in_schema=False)
async def healthz(request: Request) -> dict[str, str]:
    logger = get_logger(request_id=getattr(request.state, "request_id", ""))
    logger.info("health_check")
    return {"status": "ok", "version": get_settings().app_version}
