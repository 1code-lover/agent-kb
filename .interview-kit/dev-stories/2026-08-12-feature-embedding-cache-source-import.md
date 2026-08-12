# Embedding Cache Source Import

## 基本信息
- 类型：feature
- 日期：2026-08-12
- 相关模块：embedding 缓存准备、runtime 启动前置条件、跨领域评测
- 相关文件：`scripts/prepare_embedding_model_cache.py`、`tests/scripts/test_prepare_embedding_model_cache.py`、`docs/project.md`

## 需求背景
v1-v6 全量评测需要重启新 API，但新 runtime 已经默认禁止启动期远程下载 embedding。本机 `localmodels/` 为空，`~/.cache/huggingface` 只发现 `BAAI/bge-reranker-base`，没有 `BAAI/bge-small-zh-v1.5` 可复用 snapshot；继续只依赖 `--download` 会被 HuggingFace mirror 超时卡住。

## 设计与实现方案
`scripts.prepare_embedding_model_cache` 新增 `--source-dir` 参数，支持把已有本地模型目录复制到 `localmodels/BAAI/bge-small-zh-v1.5`。这样模型可以来自其他机器、离线包或用户手动下载目录，不再只有在线 `snapshot_download` 一条路。

同时把 `--download` 的异常改为结构化 JSON `error`，例如 `Download failed: LocalEntryNotFoundError ... ConnectTimeout`，避免命令输出长 traceback。测试覆盖 dry-run、本地已存在跳过、显式下载、source-dir 导入、source-dir 缺失和下载异常。

## 为什么选这个方案
在当前网络环境下，继续调 HuggingFace 只会重复超时。支持本地导入能把“网络下载”和“项目缓存落位”解耦，用户只要拿到一个合法模型目录，就能稳定推进 API 重启和全量评测。

## 风险与权衡
`--source-dir` 只负责复制目录，不校验模型文件完整性；真正可用性仍由后续新 API health 和 RAG 测试验证。没有模型源时，`local_path_exists=false` 仍然是当前阻塞。

## 验证与结果
`/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/scripts/test_prepare_embedding_model_cache.py tests/test_embedding_model_diagnostics.py tests/api/test_health_route.py tests/api/test_runtime_model_loading.py tests/test_diag_roundtrip_support.py -q`：`58 passed, 3 warnings`。

`/opt/miniconda3/envs/agent-kb/bin/python -m scripts.prepare_embedding_model_cache --download`：结构化返回 JSON error，`downloaded=false`、`local_path_exists=false`，错误为 HuggingFace mirror `ConnectTimeout`。

`KB_API_PORT=18084 /opt/miniconda3/envs/agent-kb/bin/python run_api.py` 后请求 `/api/health`：秒级返回 `embedding_warmup.state=failed`、`allow_remote_download=false`、`local_path_exists=false`，说明 runtime 没有重新卡住。

## 面试表达版本
我在推进 RAG 全量评测时遇到 embedding 模型缓存缺失，但在线下载一直超时。我没有继续把所有流程绑在 HuggingFace 上，而是把缓存准备脚本扩成两条路：在线下载和本地目录导入。这样用户从离线包或其他机器拿到模型目录后，可以直接导入到项目标准位置；下载失败也会输出结构化 JSON，评测报告能清楚知道是缓存源问题，而不是业务逻辑失败。
