# Embedding Warmup Stale Diagnostics

## 基本信息
- 类型：feature
- 日期：2026-08-12
- 相关模块：API runtime、health check、项目进度文档
- 相关文件：`api/runtime.py`、`tests/api/test_runtime_model_loading.py`、`docs/project.md`

## 需求背景
桌面端和 Web 都能访问时，API 健康检查仍可能长时间显示 `embedding_warmup.state=warming`。这会让评测、桌面配置和问答链路难以判断：到底是模型仍在正常预热，还是底层 embedding 初始化已经卡住。

## 设计与实现方案
在 `RuntimeState` 的 embedding 预热状态里新增 `elapsed_ms`、`is_stale`、`stale_after_ms` 和 `thread_alive`。健康检查读取状态时基于单调时钟计算 warming 持续时间；如果预热超过 120 秒仍未 ready，或线程已不存活但状态仍停在 warming，就对外标记为 `state=stale` 并给出明确错误信息。

测试侧在 `tests/api/test_runtime_model_loading.py` 增加两个用例：一个验证超过阈值会从 warming 变成 stale，另一个验证短时间预热仍保持 warming 并携带 elapsed 诊断。`docs/project.md` 同步记录当前真实状态：独立进程初始化 `bge-small-zh-v1.5` 45 秒内未返回，因此下一步仍需要补初始化超时、缓存和恢复提示。

## 为什么选这个方案
这个方案只扩展健康状态的可观测性，不改变 embedding 加载、索引或问答行为，风险小且能马上帮助排障。用单调时钟而不是解析 ISO 时间，可以避免系统时间调整影响 stale 判断；把内部 `_started_monotonic` 从对外响应里移除，也避免泄漏实现细节。

## 其他方案与为什么没选
直接杀掉预热线程没有采用，因为 Python 线程安全停止很难做好，容易留下半初始化模型或锁状态。直接把 45 秒初始化超时作为本轮功能也没有采用，因为这涉及 HuggingFaceEmbedding 初始化、模型下载缓存和跨平台进程隔离，应该作为下一步独立修复来做。

## 风险与权衡
当前改动不会解决模型初始化本身卡住的问题，只会把卡住状态暴露出来。阈值暂定为 120 秒，偏保守，避免首次下载或冷启动时过早误报；如果后续模型包更大或机器更慢，可以把阈值配置化。

## 验证与结果
`/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/api/test_runtime_model_loading.py -q`：`32 passed, 2 warnings`。

`/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/api/test_runtime_model_loading.py tests/api/test_health_route.py -q`：`35 passed, 3 warnings`。

`git diff --check`：通过。

独立进程初始化 `bge-small-zh-v1.5` 在 45 秒内未返回，验证了当前运行态确实存在长期 warming 的排障价值；这不是本轮已经修复的模型初始化问题。

## 面试表达版本
我在一个本地 RAG 桌面应用里处理过模型预热状态不可观测的问题。表面上 API 和 Web 都是好的，但 embedding 预热会长期停在 warming，评测失败时很难判断是业务退化还是模型初始化卡住。我没有直接改模型加载路径，而是先在 runtime 健康状态里补了 elapsed、线程存活和 stale 判断，让系统能明确暴露“已经不像正常预热了”。这个改动有单测覆盖，并且项目文档也同步记录了真实的 45 秒初始化超时现象，后续可以在这个证据上继续做初始化超时和缓存恢复。
