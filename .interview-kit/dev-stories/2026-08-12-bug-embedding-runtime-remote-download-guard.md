# Embedding Runtime Remote Download Guard

## 基本信息
- 类型：bug
- 日期：2026-08-12
- 相关模块：embedding 初始化、runtime health、桌面启动、跨领域评测前置条件
- 相关文件：`config.py`、`server/models/embedding.py`、`scripts/prepare_embedding_model_cache.py`、`tests/test_embedding_model_diagnostics.py`

## 问题背景
source-backed 精确短语修复需要重启 API 后复跑 v1-v6 全量评测，但本机 `localmodels/BAAI/bge-small-zh-v1.5` 缺失。此前新 API 会在启动期尝试通过 HuggingFace mirror 初始化 embedding，网络慢或超时时会长时间停留在 `embedding_warmup.state=warming/stale`，桌面和评测都难以判断是业务失败还是模型冷启动被拖住。

## 根因
运行时 embedding 初始化默认允许本地缓存缺失时回退远程下载。这个行为在开发环境里看似方便，但在桌面端和自动化评测里会把外部网络问题变成不可控的启动等待。另一个细节是，失败路径如果写 `Settings.embed_model = None`，LlamaIndex 会把它转成 `MockEmbedding`，存在把失败伪装成可用模型的风险。

## 解决方案
新增 `EMBEDDING_ALLOW_REMOTE_DOWNLOAD` 开关，默认关闭。`server/models/embedding.py` 在本地缓存缺失且未显式允许远程下载时直接失败，并提示执行 `scripts.prepare_embedding_model_cache --download` 或设置环境变量。失败路径改为清空 `Settings._embed_model`，避免落到 `MockEmbedding`。

预下载脚本仍然保留显式下载能力：只有用户传 `--download` 时，诊断才会以允许远程的口径运行。这样 runtime 和下载工具的职责分开，API/桌面启动不会再被隐式网络下载拖住。

## 为什么选这个方案
把 HuggingFaceEmbedding 初始化放进子进程并硬超时也能解决卡住，但主进程仍然需要真正的 embedding 对象，不能复用子进程对象；如果子进程成功，主进程仍要再初始化一次。当前更直接的修复是让 runtime 默认不做远程初始化，只接受已经准备好的本地缓存，从源头消除启动期卡死。

## 风险与权衡
没有本地缓存时，新 API 会快速显示 embedding failed，不能直接跑 RAG 问答和 v1-v6 suite。这是有意的显式失败：用户需要先准备本地模型缓存，或明确设置 `EMBEDDING_ALLOW_REMOTE_DOWNLOAD=1` 接受远程下载风险。

## 验证与结果
`/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/test_embedding_model_diagnostics.py tests/api/test_health_route.py tests/api/test_runtime_model_loading.py tests/scripts/test_prepare_embedding_model_cache.py tests/api/test_chat_service.py tests/scripts/test_diag_cross_domain_kb_eval.py -q`：`99 passed, 8 warnings`。

`KB_API_PORT=18084 /opt/miniconda3/envs/agent-kb/bin/python run_api.py` 后请求 `/api/health`：`embedding_warmup.state=failed`、`is_ready=false`、`embedding_diagnostics.allow_remote_download=false`、`local_path_exists=false`，临时 API 秒级返回诊断，不再等待 120 秒 stale。

## 面试表达版本
我遇到一个桌面 RAG 很实际的稳定性问题：embedding 本地缓存缺失时，API 会偷偷走 HuggingFace mirror 下载，网络一慢就把启动拖到 stale。我的修复不是继续拉长等待，而是把启动期远程下载默认关掉，缺缓存就快速失败并给出预下载命令；同时修了 LlamaIndex 把 `None` 变成 `MockEmbedding` 的误报风险。这样用户看到的是明确诊断，而不是一个看似还在预热、实际被网络卡住的系统。
