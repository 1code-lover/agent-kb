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
