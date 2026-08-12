# Embedding Cache Diagnostics And V6 Closure

## 基本信息
- 类型：feature
- 日期：2026-08-12
- 相关模块：API health、embedding runtime、跨领域评测
- 相关文件：`server/models/embedding.py`、`api/routers/health.py`、`tests/test_embedding_model_diagnostics.py`、`docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-kb-eval-report-v6-after-embedding-diagnostics.json`

## 需求背景
上一轮发现 API/Web 都可访问，但 embedding 冷启动会长时间停在 warming，导致 v6 跨领域评测被 timeout 和 network_error 影响。只知道 warming 不够，排障时还需要知道当前 embedding 是从本地缓存加载，还是在走 HuggingFace mirror 远程下载。

## 设计与实现方案
在 `server/models/embedding.py` 增加 `get_embedding_model_diagnostics()`，输出当前 embedding 名称、支持的模型列表、HF 模型路径、本地 `localmodels/` 路径、缓存是否存在、加载来源、HF endpoint 和预下载建议。`create_embedding_model()` 复用同一份诊断逻辑，避免路径判断在多个地方漂移。

`/api/health` 增加 `embedding_diagnostics` 字段，让桌面、Web 和诊断脚本都可以直接拿到模型缓存状态。测试覆盖本地缓存存在、缓存缺失远程回退、未知模型和 health 响应字段。等 runtime ready 后重新跑 v6 extra，把之前因 warmup/model 链路不稳定留下的疑点收掉。

## 为什么选这个方案
这一步优先补诊断而不是强行杀掉初始化线程，因为 HuggingFaceEmbedding 初始化内部可能涉及下载、缓存和底层库加载，直接中断线程风险较高。先把缓存状态和加载来源暴露出来，可以指导用户预下载模型，也能让后续是否要做独立进程硬超时有清晰依据。

## 其他方案与为什么没选
把模型初始化完全改成子进程超时没有在本轮做，因为那会影响 Settings.embed_model 的生命周期和现有索引/检索调用方式，需要单独设计恢复路径。只在文档里写“预下载模型”也不够，因为桌面运行时和诊断脚本无法自动判断本地缓存是否存在。

## 风险与权衡
新增 health 字段是向后兼容的，但当前已经运行的 API 进程不会自动出现新字段，需要下次重启后生效。这个改动仍没有解决冷启动本身慢的问题，只是把本地缓存缺失和远程回退原因变成可观察状态。

## 验证与结果
`/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/test_embedding_model_diagnostics.py tests/api/test_health_route.py tests/api/test_runtime_model_loading.py -q`：`38 passed, 3 warnings`。

runtime ready 后执行：

```bash
/opt/miniconda3/envs/agent-kb/bin/python -m scripts.diag_cross_domain_kb_eval \
  --api-base http://127.0.0.1:18080 \
  --timeout 60 \
  --preflight \
  --cases docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-extra-cases-v6.json \
  --output docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-kb-eval-report-v6-after-embedding-diagnostics.json
```

结果：`4/4 passed`，逐轮 `6/6 passed`，`systemic_failure_summary.suspected=false`。

## 面试表达版本
我遇到过一个本地 RAG 应用的冷启动问题：API 是活的，但 embedding 预热可能卡很久，导致评测 timeout。第一步我先补了 stale 状态，第二步继续把 embedding 的本地缓存和远程下载来源暴露到 health 里，让排障能看到是不是缺 `localmodels` 缓存、是否会走 HuggingFace mirror。这个方案没有冒险中断初始化线程，而是先把运行时变得可解释。等 runtime ready 之后，我复跑了之前失败的 v6 跨领域样本，结果 4 个 case、6 个 turn 全部通过，证明之前的问题主要是运行时链路而不是业务泛化退化。
