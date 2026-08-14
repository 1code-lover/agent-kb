# 20260810 Model Fallback Desktop E2E Plan

## 实施顺序

1. 建立文档与验收口径。
2. 在 `api.services.model_service` 中增加模型错误分类、健康状态读写和候选 fallback 探活。
3. 在 `api.runtime.RuntimeState` 中增加 LLM 失效清理能力。
4. 在 `api.services.chat_service.query` 中捕获可恢复模型错误，fallback 后重试一次。
5. 在 settings API/model options 中返回模型健康状态。
6. 在 webapp 模型页和 Agent 页展示模型健康状态。
7. 为 `scripts.run_grain_qa_eval` 增加 `--resume` 和 `--stop-on-api-error`。
8. 增加桌面 E2E 诊断脚本，输出验证报告。
9. 抽取 notarization credentials 纯函数模块，按 TDD 支持 Keychain profile、API Key、Apple ID 三种策略。
10. 让 notarize hook 和 release preflight 复用凭证模块；配置 `mac.notarize=false` 并补 release config 防重复公证校验。
11. 更新 release checklist、`docs/project.md`、`评审建议.txt` 和测试报告。

## 关键测试命令

```bash
/opt/miniconda3/envs/agent-kb/bin/python -m pytest \
  tests/api/test_model_service.py \
  tests/api/test_chat_service.py \
  tests/api/test_settings_routes.py \
  tests/scripts/test_run_grain_qa_eval.py -q

node --test webapp/src/domain/*.test.js webapp/src/api/*.test.js webapp/src/store/*.test.js

cd webapp && npm run build

cd desktop && node --test src/*.test.js scripts/*.test.js
cd desktop && npm run build:preflight
cd desktop && npm run verify:package

/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/ -q -m "not slow"
```

## 风险控制

- fallback 只对明确可恢复的模型调用错误生效，且单次 query 最多重试一次。
- 不在日志和 API 响应里泄露 API key。
- 若没有候选模型可用，保留原错误并记录健康状态为 `unavailable`。
- 评测脚本断点续跑只复用无 API 错误的用例，避免固化失败结果。
- 公证凭证只通过环境变量或 macOS Keychain 读取；日志和测试 fixture 不写入真实秘密。
- 自定义 afterSign 是唯一公证提交点，`mac.notarize=false` 必须由配置 verifier 强制检查，防止 electron-builder 内建流程重复提交。

## 2026-08-14 fallback 状态即时同步补充

12. 先在 `tests/api/test_chat_service.py` 增加正常 query 与 fallback query 的 `model_health` 响应契约测试。
13. 在 `api/services/chat_service.py` 返回服务端最新健康快照；在 `webapp/src/pages/AgentPage.jsx` 的问答成功处理器中主动刷新模型 options。
14. 运行定向 Python/Web 测试和 Web build；更新测试报告与评审建议后再提交。
