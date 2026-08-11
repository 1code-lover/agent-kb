# 2026-08-10 Feature: 桌面发布准备、Ollama fallback 与跨域泛化门禁

## 背景

模型 fallback 和桌面 E2E 主链路已经打通后，项目还剩三个收口点：桌面端需要从开发态启动推进到可打包验证，fallback 需要覆盖本地 Ollama 候选，粮仓知识库之外还需要更大的验证面，避免只对单一业务资料过拟合。

## 目标

- 补齐 Electron macOS 打包、CSP、签名/公证预检和 notarize hook。
- 让 fallback 能把 Ollama 作为无 API Key 的本地候选，并在未配置模型列表时发现本机模型。
- 让 UI 更清楚地展示自动切换后的动作提示和来源到目标模型。
- 建立一个可复跑的跨知识库、跨领域真实问答门禁，并把它扩成可读的领域分布矩阵。

## 实现

桌面端在 `desktop/package.json` 中补充 `build:web`、`build:preflight`、`release:preflight`、`verify:package`、`build:mac` 和 `release:mac` 脚本；macOS 配置启用 hardened runtime、entitlements、asar 和 maximum compression，并把 `webapp/dist`、Python API、server、utils、`run_api.py`、`config.py`、`requirements.txt` 打入 packaged resources。

`desktop/src/main.js` 在 packaged app 中改用 `process.resourcesPath` 定位资源，并添加 CSP 响应头。CSP 默认限制脚本来源，同时允许本地 API、Vite dev websocket、file/blob/data 等桌面端实际需要的资源。

新增 `desktop/scripts/release-preflight.js`，用于检查 `Electron.app`、清理 macOS quarantine/provenance xattr、修复 `app-builder` execute bit，并在严格模式下要求 Apple 签名/公证环境变量、Developer ID Application 证书和 `notarytool` 可用性。新增 `desktop/scripts/notarize-mac.js` 作为 electron-builder `afterSign` hook；缺少凭证时默认跳过，`NORTHAGENT_REQUIRE_NOTARIZE=1` 时失败。新增 `desktop/scripts/verify-package.js` 校验 dmg/zip 和 packaged resources，并确保 `app.asar` 不包含测试文件。

模型 fallback 在 `api/services/model_service.py` 中新增 Ollama `/api/tags` 读取、模型名提取、Ollama 候选判断和模型存在性检查。Ollama provider 不再因为缺 API Key 被排除；如果配置里没有模型列表，会尝试读取本机已安装模型作为候选。

前端在 `webapp/src/domain/modelHealth.js` 增加 `actionHint` 和 `transitionLabel`，`AgentPage` 与 `ModelsPage` 复用这些字段，让用户能看懂系统已切到哪个模型、后续会如何沿用当前配置。

新增 `scripts/diag_cross_domain_kb_eval.py`，内置 17 条跨域用例：粮仓、桌面诊断、图像 OCR、扫描 PDF、混合批次、UTF-8 边界、boundary、exttext、跨域负向隔离以及多 KB 契约拒绝。脚本检查答案关键词、同义关键词组、禁止精确泄漏词、来源 `kb_id`、允许来源和禁止来源，不引入 LLM 裁判。它特别区分了“目标 KB 自身有相似边界概念”和“跨库泄漏精确证据短语”。

## 验证

- `/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/api/test_model_service.py -q`：`17 passed, 2 warnings`。
- `/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/scripts/test_diag_cross_domain_kb_eval.py -q`：`8 passed, 1 warning`。
- `node --test webapp/src/domain/*.test.js webapp/src/api/*.test.js webapp/src/store/*.test.js`：`80 passed`。
- `node --test desktop/scripts/*.test.js desktop/src/*.test.js`：`8 passed`。
- `node --test desktop/scripts/release-preflight.test.js desktop/scripts/notarize-mac.test.js desktop/src/*.test.js`：`13 passed`，覆盖环境变量、Developer ID 证书解析和 `notarytool` 探测。
- `cd webapp && npm run build`：通过。
- `cd desktop && npm run build:mac && npm run verify:package`：通过，生成 `NorthAgent-0.1.0-arm64.dmg` 和 `NorthAgent-0.1.0-arm64-mac.zip`。
- packaged app 主进程启动验证通过：使用 `/opt/miniconda3/envs/agent-kb/bin/python` 拉起 API，加载 packaged `webapp/dist/index.html`，前端请求模型、知识库和聊天历史接口成功。
- `/opt/miniconda3/envs/agent-kb/bin/python -m scripts.diag_cross_domain_kb_eval --api-base http://127.0.0.1:18080 --output docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-kb-eval-report-v3.json`：`17/17 passed`，覆盖 grain / desktop / image-ocr / pdf-scan / mixed-batch / boundary / exttext / contract 九类 focus。
- `git diff --check`：通过。

## 取舍

- 真实 Apple 签名/公证没有伪造结果；本轮只做到配置、预检、打包、packaged app 启动和校验，正式 notarization 仍需要 Apple Developer 凭证和 Developer ID 证书，尽管 `notarytool` 本机已可用。
- Ollama fallback 先验证 `/api/tags` 发现和候选探活，不在没有本地模型的机器上强行做生成 E2E。
- 跨域泛化脚本已扩到 17 条真实门禁，覆盖多种文件类型、boundary/exttext 编码样本和多 KB 契约；接下来应继续扩入更多非诊断型真实资料集，验证是否还能稳定泛化。

## 后续

- 配置 Apple Developer 凭证和 Developer ID 证书后，跑严格 release preflight、签名、公证、安装后启动和桌面完整工作流回归。
- 单独处理 `desktop` npm audit，重点评估 `electron-builder` 大版本升级。
- 扩展跨领域评测到更多真实资料集、更多问题类型和更完整的 preview/拒答指标。
