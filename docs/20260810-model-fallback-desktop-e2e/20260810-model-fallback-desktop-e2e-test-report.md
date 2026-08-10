# 20260810 Model Fallback Desktop E2E Test Report

## 结论

本轮模型配置韧性、评测断点续跑、模型健康 API/UI、桌面端真实工作流诊断均已完成验证。macOS 启动桌面端时出现的“危险 App / Electron.app 被移除”问题已定位为旧 Electron 31.7.7 公证撤销，升级到 Electron 43.3.0 后桌面端可独立启动，并能使用 conda `agent-kb` 环境拉起 API。

## 验证项

| 验证项 | 结果 | 证据 |
|---|---:|---|
| 模型错误分类与 fallback 单测 | 通过 | `tests/api/test_model_service.py` |
| chat query 模型失败后 fallback 重试 | 通过 | `tests/api/test_chat_service.py` |
| `GET /api/model/health` | 通过 | `tests/api/test_settings_routes.py` |
| QA eval `--resume` / `--stop-on-api-error` | 通过 | `tests/scripts/test_run_grain_qa_eval.py` |
| 前端模型健康状态映射 | 通过 | `webapp/src/domain/modelHealth.test.js` |
| 桌面 Python 运行时选择 | 通过 | `desktop/src/python-process.test.js` |
| 前端 build | 通过 | `cd webapp && npm run build` |
| 桌面端独立启动 API | 通过 | `storage/logs/desktop_runtime.log` |
| 桌面工作流 E2E | 通过 | `artifacts/desktop-model-workflow-report-after-electron-fix.json` |

## 已执行命令

```bash
/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/ -q -m "not slow"
```

结果：`709 passed, 1 deselected, 35 warnings`

```bash
/opt/miniconda3/envs/agent-kb/bin/python -m pytest \
  tests/api/test_model_service.py \
  tests/api/test_settings_routes.py \
  tests/api/test_chat_service.py \
  tests/scripts/test_run_grain_qa_eval.py -q
```

结果：`65 passed, 8 warnings`

```bash
node --test webapp/src/domain/*.test.js webapp/src/api/*.test.js webapp/src/store/*.test.js
```

结果：`80 passed`

```bash
node --test desktop/src/python-process.test.js
```

结果：`2 passed`

```bash
cd webapp && npm run build
```

结果：Vite build 通过。

```bash
git diff --check
```

结果：通过。

```bash
/opt/miniconda3/envs/agent-kb/bin/python -m scripts.diag_desktop_model_workflow \
  --base-url http://127.0.0.1:18080 \
  --output-path docs/20260810-model-fallback-desktop-e2e/artifacts/desktop-model-workflow-report-after-electron-fix.json
```

结果：`run_passed=true`。验证内容包括模型 options/health、模型选择与探活、文件导入、定向知识库问答、引用来源、evidence preview、`default` 知识库隔离。

## 桌面端启动修复记录

旧桌面依赖 `electron@31.7.7` 在 macOS 上被系统判断为已撤销公证：

```text
notarization indicates this code has been revoked
```

表现为 `Electron.app` 启动后被系统移除，`desktop/node_modules/electron/dist/` 只剩 `LICENSE`、`LICENSES.chromium.html` 与 `version`。升级到 `electron@43.3.0` 后，桌面端成功进入主进程和渲染进程。

干净启动验证：

- `desktop_app_ready`
- `python_api_starting` 使用 `/opt/miniconda3/envs/agent-kb/bin/python`
- `python_api_ready`
- `renderer_resolved` 加载 `webapp/dist/index.html`
- `/api/model/options`、`/api/kb`、`/api/chat/history` 请求成功

## 剩余风险

- `desktop` 依赖树仍有 npm audit 风险：`8 vulnerabilities`，其中 `7 high`、`1 critical`。本轮优先解决 macOS 公证撤销导致的启动失败，后续应单独安排桌面依赖安全升级。
- Electron dev 模式仍提示 CSP 警告；该提示在打包后不会以同样形式出现，但后续正式发布前应补前端 CSP 策略。
