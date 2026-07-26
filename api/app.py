"""
?????
- ?? ThinkRAG ?? FastAPI ?????????????????

?????
1. ?? FastAPI ???????????
2. ????????????????? OCR ???
3. ?????????????? API ?????
"""

from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.routers import agent, chat, health, kb, settings
from api.runtime import bootstrap_runtime
from server.readers.image_ocr import start_ocr_warmup_in_background
from utils.api_response import error_response

app = FastAPI(title="ThinkRAG Local API", version="0.1.0")

DEFAULT_FRONTEND_DEV_ORIGINS = [
    "http://127.0.0.1:5173",
    "http://localhost:5173",
]
LOCAL_DEV_ORIGIN_REGEX = r"^https?://(localhost|127\.0\.0\.1|\[::1\])(?::\d+)?$"


def _parse_extra_dev_origins() -> list[str]:
    """?????????????????????????"""
    raw_value = os.getenv("THINKRAG_EXTRA_DEV_ORIGINS", "")
    return [item.strip() for item in raw_value.split(",") if item.strip()]


def _should_enable_ocr_prewarm() -> bool:
    """???????????? OCR ???"""
    raw_value = os.getenv("THINKRAG_OCR_PREWARM", "0").strip().lower()
    return raw_value in {"1", "true", "yes", "on"}


def _run_startup_tasks() -> None:
    """?????????? runtime bootstrap + ?? OCR ???"""
    bootstrap_runtime()
    if _should_enable_ocr_prewarm():
        start_ocr_warmup_in_background()


FRONTEND_DEV_ORIGINS = [
    *DEFAULT_FRONTEND_DEV_ORIGINS,
    *_parse_extra_dev_origins(),
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=FRONTEND_DEV_ORIGINS,
    allow_origin_regex=LOCAL_DEV_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(chat.router)
app.include_router(kb.router)
app.include_router(settings.router)
app.include_router(agent.router)


@app.on_event("startup")
def on_startup() -> None:
    """???????????????????? OCR ???"""
    _run_startup_tasks()


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """?????????????"""
    return JSONResponse(status_code=422, content=error_response(code=422, message="validation_error", data=exc.errors()))


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """???? HTTPException?"""
    detail = exc.detail if isinstance(exc.detail, str) else "http_error"
    return JSONResponse(status_code=exc.status_code, content=error_response(code=exc.status_code, message=detail))


@app.exception_handler(Exception)
async def common_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """???????????????"""
    return JSONResponse(status_code=500, content=error_response(code=500, message=str(exc)))
