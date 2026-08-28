"""遗留 Streamlit 入口兼容包装。

当前仓库主入口已经统一为 FastAPI + React（Vite）+ Electron。
本文件仅保留给历史 Streamlit 页面做兼容/排障使用，默认不再直接启动旧 UI，
避免在 runtime profile 下误把它当作当前主链路，并且避免顶层硬依赖 `streamlit`。
"""

from __future__ import annotations

import logging
import os
import sys
from importlib import import_module
from typing import Mapping

LEGACY_STREAMLIT_ENV_KEYS = (
    "KB_ALLOW_LEGACY_STREAMLIT",
    "NORTHAGENT_ALLOW_LEGACY_STREAMLIT",
    "THINKRAG_ALLOW_LEGACY_STREAMLIT",
    "FOXGLOVE_ALLOW_LEGACY_STREAMLIT",
)


def _is_truthy(value: str | None) -> bool:
    """判断环境变量是否表示显式启用。"""
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def legacy_streamlit_enabled(environ: Mapping[str, str] | None = None) -> bool:
    """只有显式声明 opt-in 时才允许进入旧 Streamlit 入口。"""
    source = environ or os.environ
    return any(_is_truthy(source.get(key)) for key in LEGACY_STREAMLIT_ENV_KEYS)


def build_legacy_entry_message() -> str:
    """生成旧入口提示，统一告知当前主链路与 opt-in 方式。"""
    return (
        "Legacy Streamlit entry is disabled by default.\n"
        "Current primary entry: FastAPI + React (Vite) + Electron.\n"
        "- Windows local dev: powershell -File .\\start_all.ps1\n"
        "- Desktop dev: powershell -File .\\scripts\\dev-all.ps1\n"
        "- API only: python run_api.py\n"
        "If you really need the historical Streamlit UI, first install the full local profile "
        "(python -m pip install -r requirements.txt), then set KB_ALLOW_LEGACY_STREAMLIT=1 and run "
        "python -m streamlit run app.py."
    )


def _load_legacy_runtime():
    """延迟加载旧入口依赖，避免 runtime profile 顶层硬依赖 streamlit。"""
    try:
        st = import_module("streamlit")
        frontend_state = import_module("frontend.state")
    except ImportError as exc:
        raise RuntimeError(
            "Legacy Streamlit entry requires the full local profile. "
            "Please install requirements.txt and set KB_ALLOW_LEGACY_STREAMLIT=1 before running app.py."
        ) from exc
    return st, frontend_state.init_state


def run_legacy_streamlit_app() -> None:
    """按旧页面结构运行遗留 Streamlit 应用。"""
    logging.basicConfig(stream=sys.stdout, level=logging.INFO)
    logging.getLogger().addHandler(logging.StreamHandler(stream=sys.stdout))

    st, init_state = _load_legacy_runtime()

    st.set_page_config(
        page_title="ThinkRAG - LLM RAG system runs on laptop",
        page_icon="🧊",
        layout="wide",
        initial_sidebar_state="auto",
        menu_items=None,
    )

    st.logo("frontend/images/ThinkRAG_Logo.png")
    init_state()

    pages = {
        "Application": [
            st.Page("frontend/Document_QA.py", title="Query"),
        ],
        "Knowledge Base": [
            st.Page("frontend/KB_File.py", title="File"),
            st.Page("frontend/KB_Web.py", title="Web"),
            st.Page("frontend/KB_Manage.py", title="Manage"),
        ],
        "Model & Tool": [
            st.Page("frontend/Model_LLM.py", title="LLM"),
            st.Page("frontend/Model_Embed.py", title="Embed"),
            st.Page("frontend/Model_Rerank.py", title="Rerank"),
            st.Page("frontend/Storage.py", title="Storage"),
        ],
        "Settings": [
            st.Page("frontend/Setting_Advanced.py", title="Advanced"),
        ],
    }

    navigation = st.navigation(pages, position="sidebar")
    navigation.run()


def main(*, environ: Mapping[str, str] | None = None, stderr=None) -> int:
    """默认输出主入口提示；只有显式 opt-in 才运行 legacy Streamlit。"""
    output = stderr or sys.stderr

    if not legacy_streamlit_enabled(environ):
        print(build_legacy_entry_message(), file=output)
        return 1

    try:
        run_legacy_streamlit_app()
    except RuntimeError as exc:
        print(str(exc), file=output)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
