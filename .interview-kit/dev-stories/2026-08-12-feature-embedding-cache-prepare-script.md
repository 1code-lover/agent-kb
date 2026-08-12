# Embedding Cache Prepare Script

## 基本信息
- 类型：feature
- 日期：2026-08-12
- 相关模块：runtime health、embedding 模型缓存、跨领域评测前置条件
- 相关文件：`scripts/prepare_embedding_model_cache.py`、`tests/scripts/test_prepare_embedding_model_cache.py`、`docs/project.md`

## 需求背景
source-backed 精确短语修复需要重启 API 后复跑 v1-v6 全量 suite 验证，但新端口 18084 启动后 120 秒进入 `embedding_warmup.state=stale`。Health 诊断显示 `localmodels/BAAI/bge-small-zh-v1.5` 缺失，当前只能走 HuggingFace mirror 远程加载，导致全量复跑前置条件不稳定。

## 设计与实现方案
新增 `scripts/prepare_embedding_model_cache.py`，提供一个显式的 embedding 缓存准备入口。默认模式只输出诊断，不下载；传 `--download` 时才调用 `huggingface_hub.snapshot_download`，把配置里的 embedding 模型下载到 `localmodels/BAAI/bge-small-zh-v1.5`。

脚本复用 `get_embedding_model_diagnostics()`，所以 health 和命令行看到的是同一套路径判断。测试覆盖 dry-run、未知模型、已有缓存跳过，以及显式 download 时传给 `snapshot_download` 的参数。

## 为什么选这个方案
直接等待 API 冷启动不可靠，之前已有 626 秒冷启动和 120 秒 stale 的证据。把预下载做成脚本，可以让用户或发布流程先解决本地缓存问题，再启动桌面/API；同时默认 dry-run 避免无意中触发长时间网络下载。

## 其他方案与为什么没选
在 API 启动时自动下载没有采用，因为桌面启动会变得更不可控，模型源网络慢时用户只会看到启动卡住。把 HuggingFaceEmbedding 初始化改成硬超时子进程也没有在本轮做，因为它涉及 Settings 生命周期和半初始化清理，适合作为后续更大的 runtime 改造。

## 风险与权衡
脚本只是提供缓存准备能力，不保证当前机器网络一定能下载成功。它也不会自动重启 18080，因此 source-backed answer repair 的全量 suite 改善仍需在本地缓存准备好并重启 API 后验证。

## 验证与结果
`/opt/miniconda3/envs/agent-kb/bin/python -m scripts.prepare_embedding_model_cache`：输出 `local_path_exists=false`、`load_source=remote`、`download_requested=false`、`downloaded=false`、`skipped=true`。

`/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/scripts/test_prepare_embedding_model_cache.py tests/api/test_chat_service.py tests/scripts/test_diag_cross_domain_kb_eval.py -q`：`59 passed, 7 warnings`。

## 面试表达版本
我在复跑 RAG 全量评测前发现了一个很典型的本地模型问题：代码已经修了，但新 API 启动后 embedding 预热卡到 stale，因为本地模型缓存不存在，只能走远程 mirror。我没有继续盲等，而是补了一个缓存准备脚本，默认只做诊断，显式 `--download` 才下载到项目的 `localmodels` 目录。这样桌面启动和评测前置条件都更可控，也给后续做硬超时隔离留下了清晰边界。
