# 问题排查日志

> 持续记录开发过程中遇到的问题、根因、修复方案及验证结果。

---

## 2026-07-09: 后端启动后文件上传 / API 返回 503/400

### 现象

| 端点 | 状态码 | 响应消息 |
|------|--------|----------|
| `GET /api/kb/list` | 503 | `Service Unavailable` |
| `POST /api/kb/file/import` | 400 | `Backend dependency initialization failed. Please verify pydantic/llama-index versions.` |
| `GET /api/kb` | 200 | 正常 |

### 排查过程

1. 直接从后端 Python 进程验证发现真正的异常栈被 `HTTPException(503)` 和 `HTTPException(400)` 吞掉，没有打印到日志。
2. 逐层手工 `python -c` 验证调用链：

```
api/app.py:startup → bootstrap_runtime()        ← OK
api/runtime.py:ensure_models_ready()             ← FAIL
  → import server.models.embedding               ← FAIL
    → from llama_index.embeddings.huggingface import HuggingFaceEmbedding
      → from sentence_transformers import SentenceTransformer
        → from transformers.configuration_utils import PretrainedConfig
          → import torch
            → OSError: [WinError 1114] c10.dll 初始化失败
```

### 问题 1: `langchain.text_splitter` 不存在

**根因**: `langchain` 从 v1.0 起将 `text_splitter` 拆到了独立包 `langchain_text_splitters`，旧代码 `from langchain.text_splitter import CharacterTextSplitter` 导致 `ModuleNotFoundError`。

**修复**: 改为 `from langchain_text_splitters import CharacterTextSplitter`。

**效果**: ❌ 仍未解决——`langchain_text_splitters` 的 `__init__.py` 会自动导入 `sentence_transformers` → `transformers` → `torch`，再次触发 DLL 崩溃。

**二次修复**: 在 `server/splitters/compat.py` 中自建迷你 `TextSplitter` 基类，完全不依赖 `langchain_text_splitters`，实现 `_merge_splits` 等必要方法。

**效果**: ✅ 通过。

### 问题 2: `torch` DLL 加载失败 (WinError 1114)

**根因**: `C:\Users\...\Python312\Lib\site-packages\torch\lib\c10.dll` 初始化失败。尝试重装 torch（GPU + CPU 版均无效），VC++ Redistributable x64 已安装，推测为机器特定的 DLL 依赖冲突或系统环境问题。

**涉及导入链**:

```
llama-index-embeddings-huggingface → sentence-transformers → transformers → torch → c10.dll
```

**修复**: 将所有触发 torch 的导入改为**函数内延迟导入**：

| 文件 | 改动 |
|------|------|
| `server/models/embedding.py` | `HuggingFaceEmbedding` import 移入 `create_embedding_model()` 函数内 |
| `server/models/llm_api.py` | `ChatOpenAI` / `LangChainLLM` import 移入各自函数内 |
| `server/stores/ingestion_cache.py` | `RedisKVStore` import 仅在生产模式下执行，DEV_MODE 下跳过 |

**效果**: ✅ `ensure_models_ready()` 成功，embedding 创建失败时优雅降级到 `MockEmbedding`。

### 问题 3: `Settings.embed_model` 属性触发自动解析

**根因**: 首次访问 `Settings.embed_model` 时，llama-index 的 property 会尝试自动解析默认 embedding 包（需要 `llama-index-embeddings-openai`），即使只读不写也会报 `ImportError`。

**修复**: 将 `getattr(Settings, "embed_model", None)` 改为直接读私有属性 `Settings._embed_model`。

**效果**: ✅ 绕过自动解析。

### 问题 4: `RedisKVStore` 模块级硬导入

**根因**: `server/stores/ingestion_cache.py` 在模块级别 `from llama_index.storage.kvstore.redis import RedisKVStore`，即使 DEV_MODE=True 不使用缓存，导入也会失败（缺 `llama-index-storage` 包）。

**修复**: 将导入和构造移到 `if not DEV_MODE:` 条件块内。

**效果**: ✅ DEV_MODE 下不再触发此导入。

### 最终验证结果

```text
GET  /api/kb/list        => 200 code=0
POST /api/kb/file/import => 200 code=0
```

---

## 2026-07-09: `run_api.py` 日志配置导致 KeyError: 'levelprefix'

### 现象

启动 `run_api.py` 时报错：

```
ValueError: Formatting field not found in record: 'levelprefix'
```

### 根因

`%(levelprefix)s` 是 uvicorn 的 `DefaultFormatter` / `AccessFormatter` 自定义字段，标准 `logging.Formatter` 不认识。`run_api.py` 中配置的 `RotatingFileHandler` 使用标准 Formatter 导致此错误。

### 修复

在 formatter 配置中添加 `"()"` 字段指向 uvicorn 的 formatter class：

```python
"default": {
    "()": "uvicorn.logging.DefaultFormatter",
    "format": "%(asctime)s  %(levelprefix)s  %(message)s",
    ...
}
```

### 效果 ✅
