"""存储服务，提供运行环境和依赖连通性信息。"""

from __future__ import annotations

import socket
from typing import Any

import config


def _is_tcp_reachable(host: str, port: int, timeout: float = 0.3) -> bool:
    """检测目标地址是否可连通。

    Args:
        host: 目标主机名。
        port: 目标端口。
        timeout: 超时时间（秒）。

    Returns:
        bool: 连通时返回 True。
    """
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def get_storage_info() -> dict[str, Any]:
    """返回存储层信息，用于桌面端诊断页展示。

    Returns:
        Dict[str, Any]: 环境模式、默认后端与依赖连通状态。
    """
    redis_ok = _is_tcp_reachable(config.REDIS_HOST, config.REDIS_PORT)
    return {
        "environment": config.THINKRAG_ENV,
        "default_vector_store": config.DEFAULT_VS_TYPE,
        "default_chat_store": config.DEFAULT_CHAT_STORE,
        "redis": {
            "host": config.REDIS_HOST,
            "port": config.REDIS_PORT,
            "reachable": redis_ok,
        },
    }
