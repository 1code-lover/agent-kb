# 20260810 Model Fallback Desktop E2E Release Checklist

## 目标

本清单用于 Apple Developer 凭证和 Developer ID Application 证书到位后，完成 NorthAgent macOS 桌面端 release candidate 的签名、公证、打包和安装后回归。

## 当前阻塞

- 本机尚未配置任一完整公证策略：Keychain profile、App Store Connect API Key 或 Apple ID app-specific password。
- `security find-identity -v -p codesigning` 当前未发现有效 `Developer ID Application` 证书。
- `xcrun --find notarytool` 可用，路径为 `/Library/Developer/CommandLineTools/usr/bin/notarytool`。

## 2026-08-16 本地 packaged 门禁状态

以下内部发布门禁已通过，但不等同于 Apple 正式签名/公证：

- `npm run build:mac`、`npm run verify:package` 通过。
- `localmodels/BAAI/bge-small-zh-v1.5/` 已随包发布，包含 config、model.safetensors、tokenizer、vocab、modules 和 `1_Pooling/config.json`。
- 独立 `--user-data-dir` packaged E2E 中，embedding `ready` 且 `load_source=local`；Resources 启动前后 114 项文件哈希完全一致，未产生 `__pycache__`。
- Python cwd、日志、session、KB、receipt 和 config 写入 userData/runtime；退出后 Python 进程已回收。
- packaged Agent Ollama 直连和坏云端到动态 Ollama 候选 fallback 均通过，报告为 `artifacts/packaged-runtime-release-e2e-report-20260816.json`。
- 当前验证使用 `/opt/miniconda3/envs/agent-kb/bin/python` 3.12.13；安装包尚未内置 Python 解释器和依赖，不能宣称清洁机自包含。
- `verify:python-runtime` 已进入 build/release preflight，强制 CPython 3.12、核心模块、`llama-index-core=0.11.19` 和 `pip check`；通过 `llama_index` import probe 覆盖 namespace / integration 可用性，但不再把顶层 `llama_index` metapackage 当成默认 runtime gate；显式 override 失败时不会回退其他 Python。

## 凭证要求

签名/公证前必须满足：

- Apple Developer 账号可用。
- Keychain 中存在有效 `Developer ID Application` 签名身份。
- 以下公证策略至少完整配置一种，推荐优先使用 Keychain profile：
  1. `APPLE_KEYCHAIN_PROFILE`，自定义 keychain 时附加 `APPLE_KEYCHAIN`。
  2. `APPLE_API_KEY`（`.p8` 绝对路径）+ `APPLE_API_KEY_ID` + `APPLE_API_ISSUER`。
  3. `APPLE_ID` + `APPLE_APP_SPECIFIC_PASSWORD` + `APPLE_TEAM_ID`。
- 不要把 app-specific password、`.p8` 内容或 Keychain 密码写入仓库、日志或 shell history。
- `NORTHAGENT_PYTHON` 指向 `/opt/miniconda3/envs/agent-kb/bin/python`，或桌面端能自动发现该解释器。

推荐先把凭证安全存入 Keychain：

```bash
xcrun notarytool store-credentials "northagent-notary" \
  --apple-id "<AppleID>" \
  --team-id "<DeveloperTeamID>" \
  --password "<AppSpecificPassword>"

export APPLE_KEYCHAIN_PROFILE=northagent-notary
```

也可以使用 App Store Connect Team API Key：

```bash
xcrun notarytool store-credentials "northagent-notary" \
  --key "/absolute/path/AuthKey_<KeyID>.p8" \
  --key-id "<KeyID>" \
  --issuer "<IssuerID>"

export APPLE_KEYCHAIN_PROFILE=northagent-notary
```

## 执行命令

```bash
security find-identity -v -p codesigning
```

通过标准：输出中至少包含一条 `Developer ID Application:`。

```bash
cd desktop && npm run release:preflight
```

通过标准：先通过外部 Python runtime 门禁，再通过严格 Apple 预检；release env、Developer ID Application、`notarytool` 和 Electron bundle 均 ready。

```bash
cd desktop && npm run verify:python-runtime
```

通过标准：输出 `ok=true`、CPython 3.12、核心模块完整、`llama-index-core=0.11.19` 且 `pipCheck` 通过；通过 `llama_index` import probe 证明 namespace / integration 可用，但不要求额外安装顶层 `llama_index` metapackage；只记录必要版本和安全摘要，不输出完整环境清单。

```bash
cd desktop && npm run build:preflight
```

通过标准：`verify-release-config` 通过，确认 Python verifier 不可旁路，以及 `afterSign`、`mac.notarize=false`、hardened runtime、entitlements、`dmg/zip` target、notarization requirement 和 packaged runtime resources 未被破坏；自定义 hook 是唯一公证提交点。Python runtime 错误必须阻断；非严格 Apple 环境预检只允许继续提示本机缺少完整公证策略或 Developer ID。

```bash
cd desktop && npm run release:mac
```

通过标准：`release:mac` 先串起 `build:web`、`build:preflight` 和严格 `release:preflight`，再生成签名并公证后的 macOS `dmg` 和 `zip` 产物，`afterSign` 阶段执行 `scripts/notarize-mac.js` 且未跳过。

```bash
cd desktop && npm run verify:package
```

通过标准：packaged resources 包含 `webapp/dist`、Python API、`server/`、`utils/`、`run_api.py`、`config.py` 和 `requirements-runtime.txt`，且 `app.asar` 不包含 `.test.js`。
同时必须包含 `localmodels/BAAI/bge-small-zh-v1.5/config.json`、`model.safetensors`、`tokenizer.json`、`vocab.txt`、`modules.json` 和 `1_Pooling/config.json`。

## 安装后回归

安装并首次启动签名/公证后的 app，确认：

- macOS 不再提示未认证开发者或公证撤销。
- 主进程日志包含 `desktop_app_ready`、`python_api_starting`、`python_api_ready`。
- 渲染进程加载 packaged `webapp/dist/index.html`。
- 前端能请求 `/api/model/options`、`/api/kb`、`/api/chat/history`。
- runtime log 和 Python cwd 必须位于 userData/runtime，不得在 `Contents/Resources` 生成运行文件或 `__pycache__`。

继续执行桌面工作流诊断：

> `http://127.0.0.1:18080` 下面只是安装后仍使用默认本地端口时的固定示例；如果桌面运行时通过 `KB_API_BASE_URL` / `KB_API_PORT` 改过 API 端口，请改成实际 resolved API base，不要把 `18080` 误读成安装后的唯一口径。

```bash
/opt/miniconda3/envs/agent-kb/bin/python -m scripts.diag_desktop_model_workflow \
  --base-url http://127.0.0.1:18080 \
  --output-path docs/20260810-model-fallback-desktop-e2e/artifacts/desktop-model-workflow-report-release-candidate.json
```

通过标准：`run_passed=true`，覆盖模型配置、探活、文件导入、定向 KB 问答、引用来源、evidence preview 和 `default` 跨 KB 隔离。

## 回归补充

```bash
node --test desktop/src/*.test.js desktop/scripts/*.test.js
```

通过标准：桌面 Python runtime、release preflight、notarize hook、release config verifier 和 CSP 单测全部通过。

```bash
cd webapp && npm run build
```

通过标准：Vite build 通过，桌面端可加载最新前端产物。

## 发布判定

只有同时满足以下证据，才能把 macOS release candidate 标记为通过：

- 严格 `release:preflight` 通过。
- 外部 Python runtime verifier 通过，且解释器与安装后实际启动口径一致。
- `build:preflight` 的 release config verifier 通过。
- `release:mac` 完成签名和公证，未跳过 notarization，且日志中只出现一次公证 submission。
- `verify:package` 通过。
- 签名/公证后的 app 能安装并启动。
- `diag_desktop_model_workflow` 在安装后 app 拉起的 API 上通过。
- packaged runtime 报告必须证明 Resources 前后文件清单/哈希一致、embedding ready、Python 退出后已回收，并记录 resolved Python、版本和 `pip check`。
- 桌面 Node 单测和 Web build 通过。
