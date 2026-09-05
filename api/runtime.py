"""API 运行时状态管理。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import RLock, Thread
from typing import Any
import time

import config


def _utc_now_iso() -> str:
    """返回 UTC ISO 时间字符串，便于诊断预热状态。"""
    return datetime.now(timezone.utc).isoformat()


def _elapsed_ms(started_at: float) -> float:
    """把 perf_counter 起点转换为毫秒耗时。"""
    return round((time.perf_counter() - started_at) * 1000, 3)


EMBEDDING_WARMUP_STALE_AFTER_MS = 120_000.0


def _new_embedding_warmup_status() -> dict[str, Any]:
    """创建 embedding 预热状态默认结构。"""
    return {
        "state": "idle",
        "attempt_count": 0,
        "last_error": None,
        "last_duration_ms": None,
        "started_at": None,
        "finished_at": None,
        "current_model": None,
        "loaded_model": None,
        "is_ready": False,
        "elapsed_ms": None,
        "is_stale": False,
        "stale_after_ms": EMBEDDING_WARMUP_STALE_AFTER_MS,
        "thread_alive": False,
        "_started_monotonic": None,
    }


@dataclass
class RuntimeState:
    """维护 API 层共享的模型与索引管理器状态。"""

    index_manager: Any = None
    index_managers: dict[str, Any] = field(default_factory=dict)
    embedding_model_name: str | None = None
    llm_fingerprint: tuple[str, str, str] | None = None
    lock: RLock = field(default_factory=RLock)
    model_lock: RLock = field(default_factory=RLock)
    embedding_warmup_status: dict[str, Any] = field(default_factory=_new_embedding_warmup_status)
    _embedding_warmup_thread: Thread | None = field(default=None, init=False, repr=False)

    @staticmethod
    def _normalize_kb_id(kb_id: str | None = None) -> str:
        """把空 kb_id 统一映射为 default。"""
        if kb_id in (None, ""):
            return "default"
        return kb_id

    def _get_configured_embedding_model_name(self) -> str:
        """读取当前配置中的 embedding 模型名，失败时回退默认值。"""
        try:
            from server.stores.config_store import CONFIG_STORE
        except Exception:
            return config.DEFAULT_EMBEDDING_MODEL

        llm_settings = CONFIG_STORE.get("current_llm_settings") or {}
        return llm_settings.get("embedding_model", config.DEFAULT_EMBEDDING_MODEL)

    def _embedding_runtime_is_ready(self) -> bool:
        """判断当前 embedding 运行时是否已对齐到配置模型。"""
        try:
            from llama_index.core import Settings
        except Exception:
            return False
        current_model = self._get_configured_embedding_model_name()
        return getattr(Settings, "_embed_model", None) is not None and self.embedding_model_name == current_model

    def _update_embedding_warmup_status_locked(self, **changes: Any) -> None:
        """在持锁状态下更新 embedding 预热状态。"""
        self.embedding_warmup_status.update(changes)

    def get_embedding_warmup_status(self) -> dict[str, Any]:
        """返回 embedding 预热状态快照。"""
        with self.lock:
            current_model = self._get_configured_embedding_model_name()
            status = dict(self.embedding_warmup_status)
            thread = self._embedding_warmup_thread
            thread_alive = thread is not None and thread.is_alive()
            started_monotonic = status.get("_started_monotonic")
            elapsed_ms = status.get("last_duration_ms")
            if status.get("state") == "warming" and isinstance(started_monotonic, (int, float)):
                elapsed_ms = _elapsed_ms(float(started_monotonic))
            status["current_model"] = current_model
            status["loaded_model"] = self.embedding_model_name
            status["is_ready"] = self._embedding_runtime_is_ready()
            status["elapsed_ms"] = elapsed_ms
            status["stale_after_ms"] = EMBEDDING_WARMUP_STALE_AFTER_MS
            status["thread_alive"] = thread_alive
            status["is_stale"] = (
                status.get("state") == "warming"
                and not status["is_ready"]
                and elapsed_ms is not None
                and (elapsed_ms >= EMBEDDING_WARMUP_STALE_AFTER_MS or not thread_alive)
            )
            if status["is_ready"] and status.get("state") in {"idle", "warming"}:
                status["state"] = "ready"
                status["is_stale"] = False
            elif status["is_stale"]:
                status["state"] = "stale"
                status["last_error"] = status.get("last_error") or "Embedding warmup exceeded stale threshold."
            status.pop("_started_monotonic", None)
            return status

    def _run_embedding_warmup(self) -> None:
        """后台执行 embedding 预热，并写回状态。"""
        started_at = time.perf_counter()
        started_at_iso = _utc_now_iso()
        current_model = self._get_configured_embedding_model_name()
        try:
            ready = self.ensure_models_ready(require_llm=False)
            if not ready:
                raise RuntimeError("Embedding model is unavailable.")
        except Exception as exc:
            with self.lock:
                self._update_embedding_warmup_status_locked(
                    state="failed",
                    last_error=str(exc),
                    last_duration_ms=_elapsed_ms(started_at),
                    started_at=started_at_iso,
                    finished_at=_utc_now_iso(),
                    current_model=current_model,
                    loaded_model=self.embedding_model_name,
                    is_ready=False,
                    elapsed_ms=_elapsed_ms(started_at),
                    is_stale=False,
                    thread_alive=False,
                    _started_monotonic=None,
                )
                self._embedding_warmup_thread = None
            return

        with self.lock:
            self._update_embedding_warmup_status_locked(
                state="ready",
                last_error=None,
                last_duration_ms=_elapsed_ms(started_at),
                started_at=started_at_iso,
                finished_at=_utc_now_iso(),
                current_model=current_model,
                loaded_model=self.embedding_model_name,
                is_ready=self._embedding_runtime_is_ready(),
                elapsed_ms=_elapsed_ms(started_at),
                is_stale=False,
                thread_alive=False,
                _started_monotonic=None,
            )
            self._embedding_warmup_thread = None

    def reset_embedding_runtime(self) -> None:
        """清除失败或过期的 embedding 实例，供缓存恢复后重新加载。"""
        try:
            from llama_index.core import Settings
        except Exception:
            Settings = None

        with self.model_lock:
            if Settings is not None:
                Settings._embed_model = None
            self.embedding_model_name = None
        with self.lock:
            attempt_count = int(self.embedding_warmup_status.get("attempt_count") or 0)
            self.embedding_warmup_status = _new_embedding_warmup_status()
            self.embedding_warmup_status["attempt_count"] = attempt_count

    def start_embedding_warmup_in_background(self, force: bool = False) -> bool:
        """按需启动 embedding 后台预热线程。"""
        with self.lock:
            if self._embedding_runtime_is_ready() and not force:
                self._update_embedding_warmup_status_locked(
                    state="ready",
                    last_error=None,
                    current_model=self._get_configured_embedding_model_name(),
                    loaded_model=self.embedding_model_name,
                    is_ready=True,
                    elapsed_ms=self.embedding_warmup_status.get("last_duration_ms"),
                    is_stale=False,
                    thread_alive=False,
                    _started_monotonic=None,
                    finished_at=_utc_now_iso(),
                )
                return False

            if self._embedding_warmup_thread is not None and self._embedding_warmup_thread.is_alive() and not force:
                return False

            self._update_embedding_warmup_status_locked(
                state="warming",
                attempt_count=int(self.embedding_warmup_status.get("attempt_count") or 0) + 1,
                last_error=None,
                last_duration_ms=None,
                started_at=_utc_now_iso(),
                finished_at=None,
                current_model=self._get_configured_embedding_model_name(),
                loaded_model=self.embedding_model_name,
                is_ready=False,
                elapsed_ms=None,
                is_stale=False,
                stale_after_ms=EMBEDDING_WARMUP_STALE_AFTER_MS,
                thread_alive=True,
                _started_monotonic=time.perf_counter(),
            )
            thread = Thread(target=self._run_embedding_warmup, name="thinkrag-embedding-warmup", daemon=True)
            self._embedding_warmup_thread = thread
        thread.start()
        return True

    def get_index_manager(self, kb_id: str | None = None) -> Any:
        """按知识库维度获取 IndexManager，并复用对应的 kb_id 缓存。"""
        kb_key = self._normalize_kb_id(kb_id)
        with self.lock:
            if kb_key == "default" and self.index_manager is not None:
                self.index_managers.setdefault("default", self.index_manager)

            cached = self.index_managers.get(kb_key)
            if cached is not None:
                if kb_key == "default":
                    self.index_manager = cached
                return cached

        try:
            from server.index import IndexManager
        except Exception as exc:  # pragma: no cover - 导入失败由运行时依赖决定
            raise RuntimeError(
                "Backend dependency initialization failed. Please verify pydantic/llama-index versions."
            ) from exc

        try:
            manager = IndexManager(config.DEFAULT_INDEX_NAME, kb_id=kb_key)
        except TypeError:
            manager = IndexManager(config.DEFAULT_INDEX_NAME)

        with self.lock:
            if kb_key == "default" and self.index_manager is not None:
                self.index_managers.setdefault("default", self.index_manager)

            cached = self.index_managers.get(kb_key)
            if cached is not None:
                if kb_key == "default":
                    self.index_manager = cached
                return cached

            self.index_managers[kb_key] = manager
            if kb_key == "default":
                self.index_manager = manager
            return manager

    def drop_index_manager(self, kb_id: str | None = None) -> None:
        """丢弃指定知识库的 IndexManager 缓存。"""
        kb_key = self._normalize_kb_id(kb_id)
        with self.lock:
            self.index_managers.pop(kb_key, None)
            if kb_key == "default":
                self.index_manager = None

    def ensure_models_ready(self, require_llm: bool = False) -> bool:
        """确保 RAG 运行所需模型已经就绪。

        Args:
            require_llm: 若为 True，则同时检查 LLM；否则只保证 embedding 就绪。

        Returns:
            bool: 是否已满足当前请求所需的模型准备条件。
        """
        try:
            from llama_index.core import Settings
            from server.models.embedding import create_embedding_model
            from server.models.llm_api import create_openai_llm
            from server.stores.config_store import CONFIG_STORE
            import server.text_splitter  # noqa: F401  # 确保 Settings.text_splitter 已完成注册
        except Exception as exc:  # pragma: no cover - 导入失败由运行时依赖决定
            raise RuntimeError(
                "Backend dependency initialization failed. Please verify pydantic/llama-index versions."
            ) from exc

        with self.model_lock:
            llm_settings = CONFIG_STORE.get("current_llm_settings") or {}
            embedding_model = llm_settings.get("embedding_model", config.DEFAULT_EMBEDDING_MODEL)
            loaded_embedding_model = self.embedding_model_name
            if Settings._embed_model is None or loaded_embedding_model != embedding_model:
                embed_model = create_embedding_model(embedding_model)
                if embed_model is None:
                    with self.lock:
                        self._update_embedding_warmup_status_locked(
                            state="failed",
                            last_error="Embedding model is unavailable.",
                            finished_at=_utc_now_iso(),
                            current_model=embedding_model,
                            loaded_model=self.embedding_model_name,
                            is_ready=False,
                            is_stale=False,
                            thread_alive=False,
                            _started_monotonic=None,
                        )
                    return False
                with self.lock:
                    self.embedding_model_name = embedding_model
                    loaded_embedding_model = self.embedding_model_name
            else:
                loaded_embedding_model = self.embedding_model_name

            with self.lock:
                self._update_embedding_warmup_status_locked(
                    state="ready",
                    last_error=None,
                    finished_at=_utc_now_iso(),
                    current_model=embedding_model,
                    loaded_model=loaded_embedding_model,
                    is_ready=True,
                    is_stale=False,
                    thread_alive=False,
                )

            provider_info = CONFIG_STORE.get("current_llm_info") or {}
            provider = provider_info.get("service_provider")
            model_name = provider_info.get("model")
            api_base = (provider_info.get("api_base") or "").strip().strip("`")
            api_key = provider_info.get("api_key")
            fingerprint = (provider or "", model_name or "", api_base or "")

            if provider in (None, "", "None") or model_name in (None, "", "None"):
                return not require_llm

            if provider == "OpenAI":
                api_base = api_base or config.OPENAI_API_BASE
                api_key = api_key or config.OPENAI_API_KEY
            elif provider == "OpenAI-like":
                api_base = api_base or config.OPENAI_API_BASE
            elif provider == "Aliyun Bailian":
                api_base = api_base or config.DASHSCOPE_BASE_URL
            elif provider == "Volcengine Ark":
                api_base = api_base or config.ARK_BASE_URL
            elif provider == "DeepSeek":
                api_base = api_base or config.DEEPSEEK_API_BASE
                api_key = api_key or config.DEEPSEEK_API_KEY

            if provider == "Ollama":
                fingerprint = (provider or "", model_name or "", api_base or config.OLLAMA_API_URL)

            if getattr(Settings, "_llm", None) is not None and self.llm_fingerprint == fingerprint:
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
                    with self.lock:
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
            with self.lock:
                self.llm_fingerprint = fingerprint
            return True

    def invalidate_llm(self) -> None:
        """清理已缓存 LLM，使下一次请求按最新配置重新加载。"""
        try:
            from llama_index.core import Settings

            setattr(Settings, "_llm", None)
        except Exception:
            pass
        with self.lock:
            self.llm_fingerprint = None

    def ensure_index_loaded(self, kb_id: str | None = None) -> bool:
        """确保指定知识库的索引已加载。

        Returns:
            bool: 若存在可加载索引则返回 True，否则返回 False。
        """
        # 先预热 embedding，避免 load_index / as_retriever 隐式触发默认 OpenAI。
        self.ensure_models_ready(require_llm=False)
        manager = self.get_index_manager(kb_id)
        with self.lock:
            if manager.check_index_exists():
                manager.load_index()
                return True
            return False

    def build_query_engine(
        self,
        kb_ids: list[str] | None = None,
        *,
        top_k: int | None = None,
        response_mode: str | None = None,
        use_reranker: bool | None = None,
        top_n: int | None = None,
        reranker_model: str | None = None,
    ) -> Any:
        """构建查询引擎。

        当前 Stage 3 仅支持单知识库查询引擎；如果传入多个 kb_id，
        直接拒绝，避免在目录隔离尚未完全打通前退回共享索引行为。
        请求级参数存在时优先覆盖当前配置，确保 QueryRequest 的检索设置真正生效。
        """
        from server.engine import create_query_engine
        from server.stores.config_store import CONFIG_STORE

        if not self.ensure_models_ready(require_llm=True):
            raise RuntimeError("LLM is not configured or unavailable. Please configure a model provider first.")

        effective_kb_ids = [kb_id for kb_id in (kb_ids or []) if isinstance(kb_id, str) and kb_id]
        unique_kb_ids = list(dict.fromkeys(effective_kb_ids))
        if len(unique_kb_ids) > 1:
            raise RuntimeError("Multi-KB query is not supported in the isolated storage runtime yet.")

        manager = self.get_index_manager(unique_kb_ids[0] if unique_kb_ids else "default")
        if manager.index is None and manager.check_index_exists():
            manager.load_index()

        llm_settings = CONFIG_STORE.get("current_llm_settings") or {}
        effective_use_reranker = llm_settings.get("use_reranker", config.USE_RERANKER) if use_reranker is None else use_reranker
        effective_response_mode = llm_settings.get("response_mode", config.DEFAULT_RESPONSE_MODE) if response_mode is None else response_mode
        effective_top_k = llm_settings.get("top_k", config.TOP_K) if top_k is None else top_k
        effective_top_n = llm_settings.get("top_n", config.RERANKER_MODEL_TOP_N) if top_n is None else top_n
        effective_reranker_model = llm_settings.get("reranker_model", config.DEFAULT_RERANKER_MODEL) if reranker_model is None else reranker_model
        return create_query_engine(
            index=manager.index,
            use_reranker=effective_use_reranker,
            response_mode=effective_response_mode,
            top_k=effective_top_k,
            top_n=effective_top_n,
            reranker=effective_reranker_model,
            kb_ids=unique_kb_ids or kb_ids,
        )


runtime_state = RuntimeState()


def bootstrap_runtime() -> None:
    """初始化默认配置与默认知识库。"""
    try:
        from server.stores.config_store import CONFIG_STORE
    except Exception:  # pragma: no cover - 运行时依赖缺失
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

    from server.kb_registry import KBRegistry

    registry = KBRegistry()
    if not registry.exists("default"):
        registry.create_kb("default", "Default Knowledge Base")
