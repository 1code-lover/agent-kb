"""
模块功能：
- 将任意对象递归转换为可 JSON 序列化的安全结构。

执行逻辑：
1. 优先处理基础类型与常见容器类型。
2. 对 datetime、Path、bytes、bs4.Tag 等不可直接序列化对象做兼容转换。
3. 兜底转为字符串，保证 json.dumps 不因类型异常失败。
"""

from __future__ import annotations

from datetime import datetime, date
from pathlib import Path
from typing import Any


def sanitize_for_json(obj: Any) -> Any:
    """
    功能：
    - 将输入对象转换为 JSON 安全结构。

    输入：
    - obj(Any): 待转换的任意对象（可为嵌套结构）。

    执行逻辑：
    1. 递归处理 dict/list/tuple/set。
    2. 转换 datetime/date、Path、bytes、含 get_text 的对象。
    3. 无法识别的对象统一转为字符串。

    输出：
    - Any: 仅包含 JSON 可序列化类型的对象。
    """
    # 基础类型：直接返回
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj

    # dict：递归处理 key/value（key 也强制转 str）
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            out[str(k)] = sanitize_for_json(v)
        return out

    # list/tuple/set：递归处理（set 转 list）
    if isinstance(obj, (list, tuple, set)):
        return [sanitize_for_json(x) for x in obj]

    # datetime/date：转 ISO 字符串
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()

    # Path：转字符串路径
    if isinstance(obj, Path):
        return str(obj)

    # bytes：尽量 decode
    if isinstance(obj, (bytes, bytearray)):
        try:
            return obj.decode("utf-8", errors="ignore")
        except Exception:
            return str(obj)

    # bs4.Tag / BeautifulSoup：通常有 get_text 方法
    # 注解：用 hasattr 不硬依赖 bs4 包，避免 import 失败
    if hasattr(obj, "get_text"):
        try:
            return obj.get_text(" ", strip=True)
        except Exception:
            return str(obj)

    # 兜底：字符串化
    return str(obj)

