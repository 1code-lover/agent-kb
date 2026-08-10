# 20260810 Model Fallback Desktop E2E Test Report

## 结论

本轮模型配置韧性、评测断点续跑、模型健康 API/UI、桌面端真实工作流诊断、macOS 打包内容校验和跨知识库泛化诊断均已完成验证。macOS 启动桌面端时出现的“危险 App / Electron.app 被移除”问题已定位为旧 Electron 31.7.7 公证撤销，升级到 Electron 43.3.0 后桌面端可独立启动，并能使用 conda `agent-kb` 环境拉起 API。

正式签名/公证尚未完成：本机缺少 Apple Developer 凭证、Developer ID 证书和 `APPLE_ID` / `APPLE_APP_SPECIFIC_PASSWORD` / `APPLE_TEAM_ID` 环境变量，因此当前结论只覆盖发布配置、预检、打包、packaged app 启动和内容校验。

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
| macOS dmg/zip 打包与 packaged resources | 通过 | `desktop/dist/` + `desktop/scripts/verify-package.js` |
| 跨知识库泛化诊断 | 通过 | `artifacts/cross-domain-kb-eval-report.json` |

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
- Electron CSP 已补到主进程响应头，并允许本地 API、Vite dev websocket 和文件资源；packaged app 已完成启动和首页 API 请求复核，后续仍需在签名/公证后的安装包中复核上传、preview 和更多静态资源加载。
- macOS release preflight、hardened runtime 与 entitlements 已补充，但本机未配置 `APPLE_ID`、`APPLE_APP_SPECIFIC_PASSWORD`、`APPLE_TEAM_ID` 且未发现有效 Developer ID 证书，严格签名/公证预检和真实 notarization 尚未执行。

## 2026-08-10 增量复核

本次增量继续收口模型 fallback 和桌面发布准备：

- Ollama 作为本地供应商时允许无 API Key 进入 fallback 候选。
- 当 Ollama provider 未显式配置模型列表时，fallback 会尝试读取 `/api/tags` 发现本地已安装模型。
- 前端模型页和 Agent 页补充 fallback action hint 与来源到目标的切换提示。
- Electron 主进程补充 CSP 响应头。
- `desktop` 新增 release preflight 脚本、macOS hardened runtime 和 entitlements 配置。
- `desktop` 新增 notarize hook 和 packaged resources 校验脚本，确认 `webapp/dist`、Python API、server、utils、`run_api.py`、`config.py` 和 `requirements.txt` 会进入 macOS app resources。
- 新增跨知识库泛化诊断脚本，覆盖粮仓、桌面诊断和 UTF-8 边界诊断 3 个 KB 的正向命中与负向隔离。

已执行命令：

```bash
/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/api/test_model_service.py -q
```

结果：`17 passed, 2 warnings`

```bash
node --test webapp/src/domain/modelHealth.test.js
```

结果：`5 passed`

```bash
node --test webapp/src/domain/*.test.js webapp/src/api/*.test.js webapp/src/store/*.test.js
```

结果：`80 passed`

```bash
node --test desktop/src/*.test.js
```

结果：`2 passed`

```bash
node --test desktop/scripts/*.test.js desktop/src/*.test.js
```

结果：`8 passed`

```bash
cd webapp && npm run build
```

结果：Vite build 通过。

```bash
node desktop/scripts/release-preflight.js
```

结果：非严格模式通过，Electron bundle 存在；提示缺少 Apple 签名/公证环境变量和 Developer ID Application 证书，但 `notarytool` 可用。

```bash
cd desktop && npm run build:mac && npm run verify:package
```

结果：通过。产物包括 `desktop/dist/NorthAgent-0.1.0-arm64.dmg` 和 `desktop/dist/NorthAgent-0.1.0-arm64-mac.zip`；packaged resources 校验确认包含 `webapp/dist/index.html`、`run_api.py`、`config.py`、`requirements.txt`、`api/app.py`、`server/index.py` 和 `utils/logging_utils.py`，且 `app.asar` 未包含 `.test.js`。

```bash
ELECTRON_ENABLE_LOGGING=1 THINKRAG_EMBED_PREWARM=0 THINKRAG_OCR_PREWARM=0 \
NORTHAGENT_PYTHON=/opt/miniconda3/envs/agent-kb/bin/python \
desktop/dist/mac-arm64/NorthAgent.app/Contents/MacOS/NorthAgent
```

结果：packaged app 主进程启动成功，API 监听 `18080`，渲染进程加载 packaged `webapp/dist/index.html`，前端请求 `/api/model/options`、`/api/kb`、`/api/chat/history` 成功。

```bash
/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/scripts/test_diag_cross_domain_kb_eval.py -q
```

结果：`5 passed, 1 warning`

```bash
/opt/miniconda3/envs/agent-kb/bin/python -m scripts.diag_cross_domain_kb_eval \
  --api-base http://127.0.0.1:18080 \
  --output docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-kb-eval-report.json
```

结果：`6/6 passed`。正向用例覆盖 `grain-knowledge-base`、`diag-desktop-e2e-1786353063`、`diag-kb-utf8-1785505921`；负向用例确认粮仓答案不会泄漏桌面 passcode，桌面诊断 KB 不会泄漏粮仓安全储粮方针，粮仓 KB 对 UTF-8 边界问题可以回答自身相似边界内容，但不得泄漏 `文件夹只承担组织作用`、`不承担权限隔离` 等精确短语或 UTF-8 诊断来源。

```bash
git diff --check
```

结果：通过。
