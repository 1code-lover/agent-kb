# 模型请求能力不兼容自动 Fallback

## 基本信息
- 类型：feature
- 日期：2026-08-14
- 相关模块：模型错误分类、自动 fallback、模型健康提示
- 相关文件：`api/services/model_service.py`、`tests/api/test_model_service.py`、`webapp/src/domain/modelHealth.js`、`webapp/src/domain/modelHealth.test.js`

## 需求背景
跨领域负向评测出现 `Range of input length should be [1, 3072]` 时，原有错误分类会落到 `unknown`，因此不会进入可恢复模型错误集合。即使系统已经配置了更长上下文或本地 Ollama 候选，也无法自动切换，前端只能展示含糊的未知错误。

## 设计与实现方案
后端新增 `request_incompatible` 错误类型，识别输入长度范围、maximum context length、`context_length_exceeded`、prompt/input too long 等常见错误文本，并把该类型加入 `RECOVERABLE_MODEL_ERROR_KINDS`。这样 query 调用遇到当前模型上下文能力不匹配时，会复用现有候选探活、自动切换、LLM invalidate 和单次重试链路。

前端模型健康摘要同步增加“请求超出模型能力”的中文解释；如果 fallback 已应用到 Ollama，还会继续复用现有动作提示，明确告知用户已经切换到本地候选模型，而不是只显示原始供应商异常。

## 为什么选这个方案
输入过长不代表知识库请求本身无效，而是当前模型能力与请求不兼容。把它纳入统一 fallback 错误分类，可以复用已经验证过的候选探活和切换机制，不需要在 Chat 层新增一条特殊重试分支，也能保持健康状态、前端提示和日志口径一致。

## 风险与权衡
自动切换只能解决候选模型拥有更大上下文窗口的情况；如果所有候选都不兼容，最终仍会返回不可用状态。为避免无限重试，Chat 层继续保持单次 fallback 重试约束，候选探活结果则通过 `fallback_attempts` 和 `fallback_attempt_summary` 暴露给用户排障。

## 验证与结果
- Python 非 slow 全量测试：`783 passed, 1 deselected, 35 warnings`。
- Web domain/API/store 测试：`89 passed`，Vite build 通过。
- 新增后端断言覆盖 `Range of input length should be [1, 3072]` 分类为 `request_incompatible` 且属于可恢复错误。
- 新增前端断言覆盖“请求超出模型能力”和“已自动切换到本地 Ollama 候选模型”的展示。
- 最终 v1-v6 真实评测：`49/49 cases passed`、`54/54 turns passed`，历史输入长度负向失败已关闭。

## 面试表达版本
我遇到过一个模型返回输入长度超限，但系统把它当成未知错误的问题。这个请求本身并不是坏请求，只是当前模型上下文能力不足，所以我新增了 `request_incompatible` 分类，把常见 context length 错误纳入可恢复集合，直接复用已有的候选探活和自动 fallback。前端也不再显示未知错误，而是明确提示请求超出模型能力，以及已经切换到哪个 Ollama 候选。最后相关单测、89 条前端测试和 49 条跨领域真实用例都通过。
