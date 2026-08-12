# ModelScope Embedding Cache and Source Grounding

## 基本信息
- 类型：feature
- 日期：2026-08-12
- 相关模块：embedding 缓存准备、runtime health、知识库问答后处理、跨领域评测
- 相关文件：`scripts/prepare_embedding_model_cache.py`、`api/runtime.py`、`api/services/chat_service.py`、`docs/project.md`、`docs/20260810-model-fallback-desktop-e2e/20260810-model-fallback-desktop-e2e-test-report.md`

## 需求背景
跨领域 v1-v6 全量评测需要稳定重启新 API，但本机 HuggingFace mirror 下载 `bge-small-zh-v1.5` 多次超时。runtime 已经默认禁止启动期远程下载，如果本地缓存缺失，新 API 会快速失败并提示诊断；这保护了桌面启动体验，却也让评测必须先解决本地 embedding 缓存来源。

同时，全量 suite 暴露出一批不是检索缺口的失败：source 已经命中，但模型会改写或漏掉精确短语，例如 `evidence preview`、`doc_id`、`preview_locator`、`各类粮油仓储单位`。这些失败需要在服务端做保真的 source-backed 修复，而不是继续调大检索范围。

## 设计与实现方案
`scripts.prepare_embedding_model_cache` 新增 `--provider {huggingface,modelscope}`，默认仍是 HuggingFace，显式指定 `--provider modelscope` 时通过 ModelScope 下载到项目标准目录 `localmodels/BAAI/bge-small-zh-v1.5`。下载结果继续输出结构化 JSON，包含 provider、before/after diagnostics、是否 skipped 和 error，便于脚本和人工排障复用。

`api/runtime.py` 修复 warmup 计时：后台 warmup 调用 `ensure_models_ready()` 设置 ready 时不再清掉 `_started_monotonic`，让最终 `last_duration_ms` 与 `started_at/finished_at` 对齐。

`api/services/chat_service.py` 扩展 source-backed 精确短语修复，覆盖 evidence preview 句子、字段名和中文范围短语。为了避免误替换，非 exact 问题必须和问题本身有足够 token 对齐；精确短语选择单独使用保守 tokenizer，避免 `remain/remains` 这类词干变体被重复计数后把答案错误替换成无关 source 句子。

## 为什么选这个方案
ModelScope provider 是对现有缓存准备脚本的最小扩展，不改变 runtime 的安全策略，也不要求桌面启动时重新承担远程下载风险。它把“下载模型”和“API 加载模型”拆开，失败时可以清楚知道问题发生在缓存准备阶段。

source-backed 修复选择放在 `chat_service` 的答案后处理，而不是改评测断言或 prompt。原因是这些失败已经有 source 证据，问题在模型输出保真；服务端用 source 原句补回，比放宽 expected terms 更能保护真实业务里的文件名、字段名和中文法规范围。

## 其他方案与为什么没选
推断方案一：允许 runtime 在启动时继续远程下载 embedding。没有选，因为这会让桌面/API 冷启动重新卡到数分钟甚至 stale，用户无法进入模型配置和知识库页面。

推断方案二：只放宽 v1-v6 expected terms。没有选，因为这会掩盖模型把精确 token 改坏的问题，评测通过但产品回答仍不够可信。

## 风险与权衡
ModelScope 映射目前只覆盖项目支持的两个 BGE 模型，新增模型时需要同步维护映射。`localmodels/` 不提交到 Git，新机器仍需要重新下载或用 `--source-dir` 导入。

精确短语修复如果条件太宽，会把答案替换成相邻但不回答问题的 source 句子。本轮用单测复现了这个风险，并通过保守 token 口径修正，确保图片 OCR 的 `Knowledge Base is the authorization boundary...` 不会被替换成 `Folder remains organization only.`。

## 验证与结果
`/opt/miniconda3/envs/agent-kb/bin/python -m scripts.prepare_embedding_model_cache --download --provider modelscope`：成功下载 `bge-small-zh-v1.5` 到 `localmodels/BAAI/bge-small-zh-v1.5`；dry-run 显示 `local_path_exists=true`、`load_source=local`、`skipped=true`。

`KB_API_PORT=18084 /opt/miniconda3/envs/agent-kb/bin/python run_api.py` 后请求 `/api/health`：`embedding_warmup.state=ready`、`embedding_diagnostics.load_source=local`、`embedding last_duration_ms=4521.347`；OCR `ready`、`last_duration_ms=6766.399`。

`/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/api/test_chat_service.py tests/scripts/test_prepare_embedding_model_cache.py tests/api/test_runtime_model_loading.py tests/test_embedding_model_diagnostics.py -q`：`76 passed, 7 warnings`。

`/opt/miniconda3/envs/agent-kb/bin/python -m scripts.diag_cross_domain_kb_eval --api-base http://127.0.0.1:18084 --timeout 120 --preflight --cases docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-extra-cases-v6.json --output docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-kb-eval-report-v6-after-latest-source-term-repair.json`：`4/4 passed`、逐轮 `6/6 passed`。

本地缓存后的 v1-v6 全量 suite 基线为 `34/49 passed`、逐轮 `39/54 passed`，比之前 `26/49` 明显提升，但仍需要继续处理正向 expected terms、source/evidence grounding 和一个负向 3072 输入长度 API 错误。

## 面试表达版本
我在做本地 RAG 桌面端评测时，发现最大阻塞不是业务逻辑，而是 embedding 模型缓存缺失导致新 API 启动不可控。我把缓存准备脚本扩成 HuggingFace 和 ModelScope 两个 provider，并保持 runtime 默认禁止远程下载，这样启动路径稳定，模型下载问题也能被提前诊断。随后我处理了一批 source 已命中但模型输出不保真的失败，用服务端 source-backed 修复补回字段名、短语和中文法规范围。最后用单测和 v6 真实评测验证，embedding 本地预热降到几秒，v6 跑到全绿，全量 suite 也从 26/49 提升到 34/49。
