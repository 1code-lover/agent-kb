# 桌面复用已运行 API

## 基本信息
- 类型：feature
- 日期：2026-08-12
- 相关模块：Electron 桌面启动、Python API 进程管理、模型配置持久化
- 相关文件：`desktop/src/python-process.js`、`desktop/src/main.js`、`desktop/src/python-process.test.js`、`server/stores/config_store.py`、`tests/api/test_config_store.py`、`docs/project.md`、`docs/20260810-model-fallback-desktop-e2e/20260810-model-fallback-desktop-e2e-test-report.md`

## 需求背景
模型额度或凭据不可用时，需要同时打开 API、Web 和桌面端，让用户在界面里重新配置可用模型。此前如果调试流程已经先启动了 `run_api.py`，Electron 主进程仍会无条件再启动一个 Python API 子进程，导致端口 `127.0.0.1:18080` 被占用并输出 `address already in use`。主窗口虽然可以继续使用现有 API，但日志表现像桌面启动失败，不利于排障和用户恢复配置。

## 设计与实现方案
在 `desktop/src/python-process.js` 增加 `ensurePythonApi`。桌面启动时先访问 `http://127.0.0.1:18080/api/health`；如果已有服务健康，就记录 `python_api_reusing_existing` 并直接进入渲染加载；如果健康检查失败，再按原路径选择 Python 运行时并启动 `run_api.py`。`desktop/src/main.js` 改为调用 `ensurePythonApi`，避免主流程重复拼装“启动再等待”的逻辑。

为了让模型配置恢复更容易人工核对，`server/stores/config_store.py` 在 `put/delete` 持久化后会把 `config_store.json` 重新写成缩进 JSON，并保留中文原文。新增 `tests/api/test_config_store.py` 覆盖写入和删除后的落盘格式。

## 为什么选这个方案
健康检查复用已有服务是最小改动路径：它不改变 API 端口、协议和桌面渲染加载方式，也不引入额外进程协调状态。把判断集中在 `ensurePythonApi` 中，可以继续复用原有 `startPythonApi`、`waitForApiReady` 和运行日志能力；测试里通过注入 `fetchImpl`、`spawnImpl`、`sleep`，不需要真的占用端口或启动 Python。

## 其他方案与为什么没选
推断：可以在启动前扫描系统进程或强杀占用端口的进程，但这会误伤用户手动启动的 API，也不适合桌面端。也可以让 API 端口动态漂移，但前端、桌面 CSP、配置文档和用户排障路径都依赖固定 `18080`，改动面更大。

## 风险与权衡
健康检查只判断 `/api/health` 可用，不校验该服务一定来自当前 checkout；这符合当前固定本地端口的调试习惯，但如果机器上同时跑多个项目副本，仍需要用户按端口区分。配置文件美化会改变 JSON 空白格式，但不改变数据结构；新增测试确认写入、删除和中文保留行为正常。

## 验证与结果
- `node --test desktop/src/python-process.test.js`：`4 passed`。
- `node --test desktop/src/python-process.test.js desktop/src/csp.test.js desktop/scripts/verify-release-config.test.js desktop/scripts/release-preflight.test.js desktop/scripts/build-target.test.js desktop/scripts/verify-package.test.js desktop/scripts/verify-mac-release.test.js desktop/scripts/notarize-mac.test.js`：`44 passed`。
- `/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/api/test_config_store.py -q`：`2 passed, 2 warnings`。
- 手工复核：在 API 已运行时重启桌面，`storage/logs/desktop_runtime.log` 出现 `python_api_reusing_existing`，未再产生新的 `address already in use` 子进程错误。

## 面试表达版本
我处理了桌面端在恢复模型配置时的一个启动噪声问题。以前 API 已经在 `18080` 跑着时，Electron 还会再拉一个 `run_api.py`，于是日志里出现端口占用，看起来像启动失败。我把主进程入口改成先探活现有 API，健康就直接复用，不健康才启动新进程，并用可注入的 fetch/spawn 写了单测。同时把模型配置存储改成缩进 JSON，方便人工检查和恢复配置。
