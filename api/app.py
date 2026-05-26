"""
模块功能：
- 定义 ThinkRAG 本地 FastAPI 应用入口并统一注册路由与异常处理。

执行逻辑：
1. 创建 FastAPI 实例并加载各业务路由。
2. 在应用启动时执行运行时初始化。
3. 通过统一异常处理器输出标准化 API 响应结构。
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from api.routers import agent, chat, health, kb, settings
from api.runtime import bootstrap_runtime
from utils.api_response import error_response

app = FastAPI(title="ThinkRAG Local API", version="0.1.0")

app.include_router(health.router)
app.include_router(chat.router)
app.include_router(kb.router)
app.include_router(settings.router)
app.include_router(agent.router)


@app.on_event("startup")
def on_startup() -> None:
    """
    启动事件处理函数。

    执行逻辑：
    1. 调用 bootstrap_runtime 初始化运行时依赖与默认配置。

    输出：
    - None
    """
    bootstrap_runtime()


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """
    统一处理请求参数校验异常。

    输入：
    - request(Request): 当前请求对象。
    - exc(RequestValidationError): 参数校验异常对象。

    输出：
    - JSONResponse: 标准错误响应（422）。
    """
    return JSONResponse(status_code=422, content=error_response(code=422, message="validation_error", data=exc.errors()))


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """
    统一处理 HTTPException。

    输入：
    - request(Request): 当前请求对象。
    - exc(HTTPException): FastAPI 抛出的 HTTP 异常。

    输出：
    - JSONResponse: 标准错误响应（透传状态码）。
    """
    detail = exc.detail if isinstance(exc.detail, str) else "http_error"
    return JSONResponse(status_code=exc.status_code, content=error_response(code=exc.status_code, message=detail))


@app.exception_handler(Exception)
async def common_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    统一处理未捕获异常的兜底逻辑。

    输入：
    - request(Request): 当前请求对象。
    - exc(Exception): 未捕获异常对象。

    输出：
    - JSONResponse: 标准错误响应（500）。
    """
    return JSONResponse(status_code=500, content=error_response(code=500, message=str(exc)))
