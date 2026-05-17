from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable
from typing import Dict

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from chat.router import router as chat_router
from config import settings
from kb.router import router as kb_router
from kb.upload_router import router as kb_upload_router
from matcher.router import router as matcher_router
from parser.router import router as parser_router
from profile.router import router as profile_router


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


app = FastAPI(
    title="CUHK Shenzhen Career AI Backend",
    description="Backend API gateway for the career AI assistant.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    start_time = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start_time) * 1000
    logger.info(
        "%s %s completed in %.2f ms",
        request.method,
        request.url.path,
        duration_ms,
    )
    return response


@app.get("/health")
async def health_check() -> Dict[str, str]:
    return {"status": "ok"}


app.include_router(chat_router, prefix="/api")
app.include_router(profile_router, prefix="/api")
app.include_router(kb_router, prefix="/api")
app.include_router(kb_upload_router)
app.include_router(matcher_router, prefix="/api")
app.include_router(parser_router, prefix="/api")
