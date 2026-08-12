"""配置存储落盘格式回归测试。"""

from __future__ import annotations

import json

from server.stores.config_store import LocalKVStore


def test_local_kv_store_persists_pretty_json(tmp_path) -> None:
    """写入配置后应以可读 JSON 格式落盘，并保留中文原文。"""

    path = tmp_path / "config_store.json"
    store = LocalKVStore({})
    store.persist_path = str(path)

    store.put("current_llm_info", {"model": "qwen-plus", "label": "中文模型"})

    content = path.read_text(encoding="utf-8")
    assert "\n  " in content
    assert "\\u4e2d" not in content
    assert json.loads(content) == {
        "data": {
            "current_llm_info": {
                "model": "qwen-plus",
                "label": "中文模型",
            }
        }
    }


def test_local_kv_store_delete_keeps_pretty_json(tmp_path) -> None:
    """删除配置后持久化文件仍应保持缩进格式。"""

    path = tmp_path / "config_store.json"
    store = LocalKVStore({})
    store.persist_path = str(path)
    store.put("current_llm_info", {"model": "qwen-plus"})

    assert store.delete("current_llm_info") is True

    content = path.read_text(encoding="utf-8")
    assert "\n  " in content
    assert json.loads(content) == {"data": {}}
