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

## 2026-08-15 Agent Ollama 与 fallback 补充

15. 先新增 `tests/api/test_agent_tools.py`，覆盖 Ollama 原生请求、云端失败后切换到 Ollama、非可恢复错误和重试失败状态。
16. 将 Agent 直连调用拆为当前配置读取、OpenAI 兼容调用和 Ollama 原生调用；`run_llm_chat` 统一负责单次 fallback。
17. 在 `agent_runtime.run_agent` 结果、step 和 receipt 中透传最终模型健康与切换摘要，前端沿用已有 model options 主动刷新。
18. 执行 Agent 定向测试、Python 非 slow 全量测试、Web 测试/build 和 Electron 测试，更新报告、评审和开发故事后提交推送。
19. 安装并启动 Ollama、拉取小型模型，执行 Agent 直接推理和坏云端模型到动态 Ollama 候选的真实 E2E；将结果固化为 JSON artifact，并依据真实结果修复状态回显缺口。

## 2026-08-15 packaged runtime 数据隔离补充

20. 更新 PRD、FRD、RTM、spec、计划和测试方案，明确 Resources 只读、userData/runtime 可写及默认 embedding 随包发布的验收口径；完成文档评审后再编码。
21. 先增加 `desktop/src/runtime-paths.test.js` 和 `desktop/src/python-process.test.js` 失败测试，覆盖 packaged 路径解析、Python script/cwd/env 和日志目录。
22. 先增加 `tests/test_runtime_paths.py` 失败测试，使用隔离子进程验证数据/模型环境变量，并覆盖 KV、session、fallback、embedding、reranker 的绝对路径。
23. 先扩展 `desktop/scripts/verify-package.test.js`，证明默认 embedding 文件缺失会阻断 package verifier。
24. 实现 `resourceRoot`/`runtimeRoot` 拆分，修正 Python 路径解析和持久化路径；在 `desktop/package.json` 增加 `localmodels` extraResource 并强化 verifier。
25. 运行 Electron/Python 定向测试和全部既有测试；重新构建 Web 与 macOS 包并执行 `verify:package`。
26. 使用独立 userData 启动 packaged app，生成 Resources 启动前后 SHA-256 清单，验证 API/embedding ready、知识库问答、Ollama 直连/fallback 和退出后 Python 进程回收。
27. 更新测试报告、release checklist、`docs/project.md`、评审建议和开发故事；审核通过后按 Task 提交并 push。

### 预期结果

- Node 定向测试新增路径和 package 模型资源门禁并全部通过。
- Python 定向测试证明环境变量产生绝对 storage/data/model 路径，且持久化不进入源码/resources。
- `npm run build:mac` 和 `npm run verify:package` 通过，产物包含默认 embedding。
- packaged E2E 报告中 `resources_unchanged=true`、`runtime_writes_outside_resources=true`、`embedding_ready=true`、`python_stopped_after_quit=true`。
