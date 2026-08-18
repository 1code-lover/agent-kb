"""API 应用入口。

模块职责：
- 创建 ThinkRAG 本地 FastAPI 应用；
- 在启动阶段完成基础 runtime bootstrap；
- 按需触发 embedding / OCR 的后台预热；
- 注册统一异常处理与 API 路由。
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.routers import access_tokens, agent, chat, embedding_cache, health, kb, kb_migration, open_api, settings
from api.runtime import bootstrap_runtime, runtime_state
from server.readers.image_ocr import start_ocr_warmup_in_background
from utils.api_response import error_response

DEFAULT_FRONTEND_DEV_ORIGINS = [
    "http://127.0.0.1:5173",
    "http://localhost:5173",
]
LOCAL_DEV_ORIGIN_REGEX = r"^https?://(localhost|127\.0\.0\.1|\[::1\])(?::\d+)?$"


def _parse_extra_dev_origins() -> list[str]:
    """解析附加的本地前端调试来源。"""
    raw_value = os.getenv("THINKRAG_EXTRA_DEV_ORIGINS", "")
    return [item.strip() for item in raw_value.split(",") if item.strip()]


def _should_enable_embedding_prewarm() -> bool:
    """判断是否在启动后后台预热 embedding 模型。"""
    raw_value = os.getenv("THINKRAG_EMBED_PREWARM", "0").strip().lower()
    return raw_value in {"1", "true", "yes", "on"}


def _should_enable_ocr_prewarm() -> bool:
    """判断是否在启动后后台预热 OCR 引擎。"""
    raw_value = os.getenv("THINKRAG_OCR_PREWARM", "0").strip().lower()
    return raw_value in {"1", "true", "yes", "on"}


def _run_startup_tasks() -> None:
    """执行启动任务：bootstrap runtime，并按需异步预热模型。"""
    bootstrap_runtime()
    if _should_enable_embedding_prewarm():
        runtime_state.start_embedding_warmup_in_background()
    if _should_enable_ocr_prewarm():
        start_ocr_warmup_in_background()


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    """使用 FastAPI lifespan 接口执行启动预热，避免 on_event 弃用提示。"""
    _run_startup_tasks()
    yield


app = FastAPI(title="ThinkRAG Local API", version="0.1.0", lifespan=_lifespan)

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
app.include_router(embedding_cache.router)
app.include_router(chat.router)
app.include_router(kb.router)
app.include_router(kb_migration.router)
app.include_router(open_api.router)
app.include_router(access_tokens.router)
app.include_router(settings.router)
app.include_router(agent.router)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """统一处理请求参数校验错误。"""
    return JSONResponse(status_code=422, content=error_response(code=422, message="validation_error", data=exc.errors()))


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """统一处理 FastAPI HTTPException。"""
    detail = exc.detail if isinstance(exc.detail, str) else "http_error"
    return JSONResponse(status_code=exc.status_code, content=error_response(code=exc.status_code, message=detail))


@app.exception_handler(Exception)
async def common_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """统一处理未捕获异常。"""
    return JSONResponse(status_code=500, content=error_response(code=500, message=str(exc)))
