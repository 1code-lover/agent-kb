# 补齐 Windows 验证闭环并落档 KB 迁移 / OCR 测试报告

## 基本信息
- 类型：bug
- 日期：2026-08-18
- 相关模块：知识库迁移、只读 Open API / Access Token、Embedding 缓存恢复、OCR 基准评测、Desktop 构建测试
- 相关文件：`docs/20260817-kb-migration-agent-ocr-cache/20260817-kb-migration-agent-ocr-cache-test-report.md`、`server/utils/model_paths.py`、`tests/api/test_access_token_service.py`、`tests/scripts/test_prepare_embedding_model_cache.py`、`tests/scripts/test_ocr_scan_benchmark.py`、`tests/test_embedding_model_diagnostics.py`、`desktop/scripts/build-target.test.js`、`desktop/scripts/notarize-mac.test.js`、`desktop/scripts/release-preflight.test.js`、`desktop/scripts/verify-mac-release.test.js`、`desktop/scripts/verify-package.test.js`、`desktop/src/python-process.test.js`、`desktop/src/runtime-paths.test.js`

## 问题现象
上一轮已经完成知识库物理隔离、Embedding 缓存恢复、只读 Open API 和 OCR 基准能力，但收尾阶段还有两类问题没有闭环：一类是测试报告没有正式落档，导致需求目录缺少测试执行结论；另一类是当前工作区切到 Windows 后，多处测试仍然把路径分隔符、文件权限和默认文本编码写死成 POSIX 假设，造成 Desktop / Python 回归在 Windows 主机上不稳定，无法直接作为 commit 前的最终验收依据。

## 根因分析
根因不是单一实现缺陷，而是“功能完成后缺少跨平台收尾”带来的组合问题：
1. 测试和诊断脚本默认用 `/`、`0600`、`read_text()` 默认编码等 Unix 语义断言，到了 Windows/GBK locale 环境后会把平台差异误判成产品故障。
2. `server/utils/model_paths.py` 直接把带有混合分隔符的 `model_path` 整串 join 到目标目录，在 Windows 下可能得到不一致的本地模型路径，属于真实代码层问题，不只是测试写法问题。
3. 需求目录已经有 PRD / FRD / RTM / Plan / Test Plan，但缺少测试报告，导致“实现完成”和“验收证据完整”之间仍有文档缺口。

## 解决方案
1. 新增 `docs/20260817-kb-migration-agent-ocr-cache/20260817-kb-migration-agent-ocr-cache-test-report.md`，把迁移、Open API、Embedding、OCR、Desktop/Web 回归、覆盖率、失败修复闭环和最终限制一次性落档，并明确声明 OCR 真实实拍资产仍未完成。
2. 修正 `server/utils/model_paths.py`：先把 `model_path` 统一拆成规范化 path parts，再交给 `os.path.join()` 组合，消除 `\` 和 `/` 混用导致的路径拼接问题。
3. 调整 Python 测试断言：Access Token 用例改为区分 POSIX 权限和 Windows 落盘校验；Embedding / 诊断脚本统一做路径标准化；OCR benchmark fixture 读取 JSON 时显式指定 `encoding="utf-8"`，避免 GBK locale 解码失败。
4. 调整 Desktop 测试断言：对命令路径统一做 normalize，再匹配脚本和构建产物路径；`release-preflight` 在 `win32` 下不再宣称必须具备 POSIX execute bit，只验证文件存在和调用链正确。
5. 重新生成 OCR benchmark recorded/runtime JSON 产物，并在当前 Windows 工作区完成 Python、Web、Desktop 回归和 `git diff --check` 收尾验证。

## 为什么选这个方案
这批问题的目标是把已有功能安全地推进到可提交状态，所以优先选择“修正真实跨平台缺陷 + 放宽错误的平台假设 + 补齐测试证据”，而不是继续扩大需求范围。这样做的收益是：产品代码只在确有 bug 的 `model_paths.py` 上动刀，其余主要通过测试和文档收尾消除环境噪声；同时可以保留 Windows 实测证据，又不伪造 macOS 发布环境已经验收完成的结论。

## 其他方案与为什么没选
1. 把所有 Windows 差异都改到产品代码里：没选。多数失败来自测试断言把平台行为写死，如果为了让测试过而改业务实现，反而会引入额外回归风险。
2. 直接跳过 Desktop 或 OCR 的 Windows 用例：没选。当前目标是形成 commit 前的真实验收闭环，跳过用例只会把问题继续留到后面。
3. 把 OCR 真实实拍资产也在本轮一起补齐：没选。那部分依赖外部实体样本，不属于当前代码仓内可立即闭环的改动，测试报告里必须如实保留未完成声明。

## 验证与结果
- `python -m pytest tests/api/test_kb_migration_service.py tests/api/test_kb_migration_route.py tests/api/test_kb_migration_integration.py -q` → `14 passed, 2 warnings, 28.65s`
- `python -m pytest tests/api/test_access_token_service.py tests/api/test_access_token_route.py tests/api/test_open_api.py tests/api/test_open_api_service.py tests/api/test_open_api_integration.py tests/scripts/test_manage_access_tokens.py -q` → `18 passed, 2 warnings, 30.22s`
- `python -m pytest tests/api/test_embedding_download_adapter.py tests/api/test_embedding_cache_service.py tests/api/test_embedding_cache_route.py tests/scripts/test_prepare_embedding_model_cache.py -q` → `33 passed, 2 warnings, 13.21s`
- `python -m pytest tests/readers/test_ocr_continuous_tables.py tests/scripts/test_ocr_scan_benchmark.py -q -m "not slow"` → `12 passed, 1 deselected, 5.30s`
- `python -m pytest tests/scripts/test_ocr_scan_benchmark.py -q -m slow` → `1 passed, 7 deselected, 2 warnings, 110.76s`
- `python -m pytest tests/ -q -m "not slow"` → `864 passed, 2 deselected, 2 warnings, 68.25s`
- 覆盖率切片结果：`113 passed, 2 deselected, 2 warnings, TOTAL 88%`，目标模块均达到或超过 80%
- `cmd /c "cd desktop && node --test src/*.test.js scripts/*.test.js"` → `86 passed`
- `node --test <webapp/src/**/*.test.js>` → `98 passed`
- `npm run build --prefix webapp` → `passed`
- `git diff --check` → `exit 0`
- 结论：迁移 / Open API / Embedding / OCR 技术实现与测试报告已闭环；但 `tests/fixtures/ocr_real_scan/manifest.json` 中 `physical_capture_verified=false` 的真实实拍资产缺口仍未关闭，不能把 OCR 物理验收说成完成。

## 面试表达版本
我接手的是一个“功能基本做完，但最后验收卡在 Windows 环境”的收尾窗口。先补上了缺失的测试报告，把迁移、Open API、Embedding 和 OCR 的实测结果、覆盖率以及失败修复闭环完整落档；然后把真正的跨平台问题拆开处理：真实代码 bug 只修 `model_paths.py` 的混合分隔符拼接，其余测试改成按平台语义断言，不再把 Windows 行为误判成故障。这样做之后，Python 全量非 slow、Web、Desktop 和 OCR recorded/runtime 基准都能在当前工作区稳定通过。最后我在报告里明确保留了一个边界：OCR 真实实拍资产还没补齐，所以我只宣称技术实现闭环，不会把物理验收夸大成已完成。
