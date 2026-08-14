# 20260810 Model Fallback Desktop E2E RTM

| Requirement | Design | Test |
|---|---|---|
| 识别额度耗尽、403、401、模型不可用 | FR-01 | `tests/api/test_model_service.py` 分类测试 |
| 自动切换到可用模型 | FR-02 | `tests/api/test_chat_service.py` fallback 重试测试 |
| API 输出模型健康状态 | FR-03 | `tests/api/test_model_service.py`、`tests/api/test_settings_routes.py` |
| UI 显示模型健康状态 | FR-04 | webapp Node 测试、前端构建 |
| QA eval 断点续跑 | FR-05 | `tests/scripts/test_run_grain_qa_eval.py` |
| 桌面真实工作流 E2E | FR-06 | 诊断脚本输出 E2E 报告 |
| 项目文档收口 | 文档更新 | `docs/project.md`、测试报告、评审建议 |
| macOS 三种公证凭证策略 | FR-07 | `desktop/scripts/notarization-credentials.test.js`、`desktop/scripts/notarize-mac.test.js`、`desktop/scripts/release-preflight.test.js` |
| 单次公证且不重复提交 | FR-07 | `desktop/scripts/verify-release-config.test.js` 检查 `afterSign` 与 `mac.notarize=false` |
| 正式签名、公证和安装后验证 | FR-07 | `release:preflight`、`release:mac`、`verify:package`、`verify:mac-release`、桌面工作流报告 |
| Agent 直连 Ollama | FR-08 | `tests/api/test_agent_tools.py` Ollama 原生 `/api/chat` 请求测试 |
| Agent 直连模型自动 fallback | FR-08 | `tests/api/test_agent_tools.py` 首次失败、切换、单次重试和失败状态测试；`tests/api/test_agent_runtime.py` 结果透传测试；`artifacts/agent-ollama-fallback-e2e-report-20260815.json` 真实本地模型报告 |
| fallback 来源/目标完整回显 | FR-03、FR-08 | `tests/api/test_model_service.py` 来源快照回归；真实 Ollama E2E 报告的 `fallback_from/fallback_to` |
