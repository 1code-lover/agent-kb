# Ollama 动态发现失败补充 fallback 诊断提示

## 基本信息
- 类型：feature
- 日期：2026-08-11
- 相关模块：模型 fallback、Ollama 候选发现、模型健康 UI、桌面端模型恢复体验
- 相关文件：`api/services/model_service.py`、`tests/api/test_model_service.py`、`webapp/src/domain/modelHealth.js`、`webapp/src/domain/modelHealth.test.js`、`docs/20260810-model-fallback-desktop-e2e/20260810-model-fallback-desktop-e2e-test-report.md`、`docs/project.md`

## 需求背景

模型 fallback 已经能记录候选探测摘要，并能在 Ollama 候选全部不可用时提示用户检查本地服务和目标模型。但还有一个容易被忽略的边角：如果 Ollama provider 配置为 `models: []`，系统会依赖 `/api/tags` 动态发现本地模型；当 Ollama 没启动、地址不可达或本地没有模型时，候选枚举会变成 0 个。

这种情况下 UI 只能展示“没有可用供应商”一类泛化提示，用户看不出自己应该启动 Ollama、修正地址，还是先 `ollama pull` 一个模型。对桌面端恢复配置来说，这个提示太弱。

## 设计与实现方案

在 `api/services/model_service.py` 中补充 Ollama 动态发现失败的诊断候选：

- 当 provider 为 Ollama、`models` 为空，且动态发现没有返回模型时，枚举一个 `discovery_only` 候选。
- fallback 探测阶段会再次探测 Ollama `/api/tags`，并把结果归一为 `ollama_unreachable`、`ollama_no_models`、`ollama_http_xxx` 或 `ollama_models_discovered`。
- `fallback_attempt_summary` 会把该诊断候选计入 `ollama_candidate_count`，避免前端只看到 `candidate_count=0`。

在 `webapp/src/domain/modelHealth.js` 中细化 unavailable 状态下的 Ollama 提示：

- `ollama_unreachable` / `ollama_http_xxx`：提示启动 Ollama、确认 `http://localhost:11434` 可访问，或修正 Ollama 地址。
- `ollama_no_models`：提示 Ollama 已连接但没有可切换模型，可先运行 `ollama pull qwen2.5:7b`。
- `model_not_found`：提示目标模型未安装，并给出 `ollama pull <model>`。

## 为什么选这个方案

这次没有把“发现失败”藏在日志里，而是保留为一个结构化候选，是因为前端已经有 `fallback_attempt_summary` 的展示路径。沿用这条路径可以让 Models 页和 Agent 页自然拿到同一套诊断口径，不需要额外 API 或页面状态。

`discovery_only` 候选不会被选中为当前模型，只承担诊断职责，因此不会误切换到一个空模型；但它能让用户知道“系统确实检查过 Ollama，只是服务/模型条件还没满足”。

## 其他方案与为什么没选

一种方案是保持候选数为 0，只在后端 health detail 中写错误文本。这样实现简单，但前端无法稳定区分云端无候选和 Ollama 动态发现失败。

另一种方案是为 Ollama 固定写死几个默认模型作为候选。这个方案容易误导用户，因为本地未必安装这些模型；诊断候选更诚实，只在用户明确拉取或配置模型后才进入真实可切换候选。

## 风险与权衡

`models: []` 且 Ollama 不可达时，现在 candidate count 会从 0 变成 1。这个 1 是诊断候选，不代表可切换模型；UI 会通过 `ollama_candidate_count=1` 和 `reachable_count=0` 展示不可用修复提示。

探测阶段会多一次 `/api/tags` 调用：第一次用于候选发现，第二次用于 fallback 结果记录。当前 timeout 较短，且只发生在 fallback 异常路径，换来的是更准确的用户提示和可追踪报告。

## 验证与结果

- `/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/api/test_model_service.py -q`：`19 passed, 2 warnings`
- `/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/api/test_model_service.py tests/api/test_settings_routes.py tests/api/test_chat_service.py -q`：`57 passed, 8 warnings`
- `node --test webapp/src/domain/modelHealth.test.js`：`10 passed`
- `node --test webapp/src/domain/*.test.js webapp/src/api/*.test.js webapp/src/store/*.test.js`：`85 passed`
- `cd webapp && npm run build`：通过
- `git diff --check`：通过

## 面试表达版本

我补了一个模型 fallback 的边角：Ollama 配置存在但依赖动态发现时，如果本地服务没启动或没有已安装模型，之前候选数会直接变成 0，前端只能给泛化提示。现在后端会保留一个 `discovery_only` 诊断候选，并把结果写进 `fallback_attempt_summary`；前端根据 `ollama_unreachable`、`ollama_no_models`、`model_not_found` 分别提示启动 Ollama、修正地址或执行 `ollama pull`。这样用户重新配置模型时能看到具体下一步，而不是猜哪里坏了。
