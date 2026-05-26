"""API 运行时上下文，负责复用核心对象。"""

from __future__ import annotations

from dataclasses import dataclass, field
from threading import RLock
from typing import Any

import config


@dataclass
class RuntimeState:
    """集中管理 API 共享状态。"""

    index_manager: Any = None
    embedding_model_name: str | None = None
    llm_fingerprint: tuple[str, str, str] | None = None
    lock: RLock = field(default_factory=RLock)

    def get_index_manager(self) -> Any:
        """惰性初始化 IndexManager，避免导入时硬依赖。"""
        if self.index_manager is None:
            try:
                from server.index import IndexManager
            except Exception as exc:
                raise RuntimeError("Backend dependency initialization failed. Please verify pydantic/llama-index versions.") from exc

            self.index_manager = IndexManager(config.DEFAULT_INDEX_NAME)
        return self.index_manager

    def ensure_models_ready(self, require_llm: bool = False) -> bool:
        """按当前配置懒加载 RAG 运行时模型。

        Args:
            require_llm: 为 True 时，无法创建 LLM 会返回 False。

        Returns:
            bool: 模型运行时是否满足本次调用要求。
        """
        try:
            from llama_index.core import Settings
            from server.models.embedding import create_embedding_model
            from server.models.llm_api import create_openai_llm
            from server.stores.config_store import CONFIG_STORE
            import server.text_splitter  # noqa: F401  # 注册 Settings.text_splitter
        except Exception as exc:
            raise RuntimeError("Backend dependency initialization failed. Please verify pydantic/llama-index versions.") from exc

        with self.lock:
            llm_settings = CONFIG_STORE.get("current_llm_settings") or {}
            embedding_model = llm_settings.get("embedding_model", config.DEFAULT_EMBEDDING_MODEL)
            if getattr(Settings, "embed_model", None) is None or self.embedding_model_name != embedding_model:
                created = create_embedding_model(embedding_model)
                if created is None:
                    raise RuntimeError(f"Embedding model unavailable: {embedding_model}")
                self.embedding_model_name = embedding_model

            current_llm_info = CONFIG_STORE.get("current_llm_info")
            if not current_llm_info:
                return not require_llm

            model_name = current_llm_info.get("model", "")
            provider = current_llm_info.get("service_provider", "")
            api_base = (current_llm_info.get("api_base") or "").strip().replace("`", "")
            api_key = current_llm_info.get("api_key") or ""
            fingerprint = (provider, model_name, api_base)
            if getattr(Settings, "llm", None) is not None and self.llm_fingerprint == fingerprint:
                return True

            if provider == "Ollama":
                try:
                    from llama_index.llms.ollama import Ollama

                    Settings.llm = Ollama(
                        model=model_name,
                        base_url=api_base or config.OLLAMA_API_URL,
                        request_timeout=600,
                        temperature=llm_settings.get("temperature", config.TEMPERATURE),
                        system_prompt=llm_settings.get("system_prompt", config.SYSTEM_PROMPT),
                    )
                    self.llm_fingerprint = fingerprint
                    return True
                except Exception:
                    return not require_llm

            if not api_base or not api_key:
                return not require_llm

            llm = create_openai_llm(
                model_name=model_name,
                api_base=api_base,
                api_key=api_key,
                temperature=llm_settings.get("temperature", config.TEMPERATURE),
                system_prompt=llm_settings.get("system_prompt", config.SYSTEM_PROMPT),
            )
            if llm is None:
                return not require_llm
            self.llm_fingerprint = fingerprint
            return True

    def ensure_index_loaded(self) -> bool:
        """确保索引已加载。

        Returns:
            是否存在并成功加载索引。
        """
        manager = self.get_index_manager()
        with self.lock:
            if manager.check_index_exists():
                manager.load_index()
                return True
            return False

    def build_query_engine(self) -> Any:
        """根据配置构建查询引擎。

        Returns:
            可执行 query 的查询引擎。
        """
        from server.engine import create_query_engine
        from server.stores.config_store import CONFIG_STORE

        if not self.ensure_models_ready(require_llm=True):
            raise RuntimeError("LLM is not configured or unavailable. Please configure a model provider first.")

        manager = self.get_index_manager()
        llm_settings = CONFIG_STORE.get("current_llm_settings") or {}
        return create_query_engine(
            index=manager.index,
            use_reranker=llm_settings.get("use_reranker", config.USE_RERANKER),
            response_mode=llm_settings.get("response_mode", config.DEFAULT_RESPONSE_MODE),
            top_k=llm_settings.get("top_k", config.TOP_K),
            top_n=llm_settings.get("top_n", config.RERANKER_MODEL_TOP_N),
            reranker=llm_settings.get("reranker_model", config.DEFAULT_RERANKER_MODEL),
        )


runtime_state = RuntimeState()


def bootstrap_runtime() -> None:
    """初始化运行时依赖。"""
    try:
        from server.stores.config_store import CONFIG_STORE
    except Exception:
        return

    if CONFIG_STORE.get("current_llm_settings") is None:
        CONFIG_STORE.put(
            key="current_llm_settings",
            val={
                "temperature": config.TEMPERATURE,
                "system_prompt": config.SYSTEM_PROMPT,
                "top_k": config.TOP_K,
                "response_mode": config.DEFAULT_RESPONSE_MODE,
                "use_reranker": config.USE_RERANKER,
                "top_n": config.RERANKER_MODEL_TOP_N,
                "embedding_model": config.DEFAULT_EMBEDDING_MODEL,
                "reranker_model": config.DEFAULT_RERANKER_MODEL,
            },
        )
