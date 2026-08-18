# 20260817-kb-migration-agent-ocr-cache 测试报告

## 1. 文档信息

- 需求目录：`docs/20260817-kb-migration-agent-ocr-cache/`
- 测试报告日期：2026-08-18
- 当前分支：`codex/desktop-agent-stage3`
- 当前工作区：`C:\Users\ethan1.zhao\Desktop\xiangmu\agent-kb`
- 报告目标：为“历史迁移 + OCR 基准 + 只读 Open API + Embedding 下载控制”补齐测试执行记录、覆盖率证据、失败修复闭环与最终结论。

## 2. 实际测试环境

### 2.1 本次补档采用的真实环境

| 项 | 实际值 |
|---|---|
| 操作系统 | Windows 10 22H2 (`Windows-10-10.0.19045-SP0`) |
| Python | `3.12.10` |
| Node.js | `v26.7.0` |
| npm | `11.19.0` |
| llama-index-core | `0.14.23` |
| Shell | PowerShell |

### 2.2 与测试方案基线的差异说明

测试方案文件 `20260817-kb-migration-agent-ocr-cache-test-plan.md` 以 macOS + `/opt/miniconda3/envs/agent-kb/bin/python` + `llama_index-core 0.11.19` 为编写基线；本次实际补档和复验均在当前 Windows 工作区完成，因此：

1. 路径分隔符、绝对路径前缀、文件权限语义、OCR runtime 耗时均以 Windows 实测为准；
2. 方案中的命令覆盖范围仍然有效，但报告中的环境、耗时和部分兼容性修复以当前实测结果为准；
3. 不能把本报告解读为对 macOS 发行环境耗时或路径表现的直接证明。

## 3. 专项测试执行结果

### 3.1 历史迁移

| 命令 | 结果 |
|---|---|
| `python -m pytest tests/api/test_kb_migration_service.py tests/api/test_kb_migration_route.py tests/api/test_kb_migration_integration.py -q` | `14 passed, 2 warnings, 28.65s` |

结论：历史共享索引扫描、dry-run、备份、重建、重试、回滚、路由层与集成链路均有专项测试覆盖。

### 3.2 Open API / access tokens

| 命令 | 结果 |
|---|---|
| `python -m pytest tests/api/test_access_token_service.py tests/api/test_access_token_route.py tests/api/test_open_api.py tests/api/test_open_api_service.py tests/api/test_open_api_integration.py tests/scripts/test_manage_access_tokens.py -q` | `18 passed, 2 warnings, 30.22s` |

结论：token 创建/存储/撤销、只读接口授权、审计脱敏、路由集成、CLI 生命周期均已通过。

### 3.3 Embedding 下载与缓存

| 命令 | 结果 |
|---|---|
| `python -m pytest tests/api/test_embedding_download_adapter.py tests/api/test_embedding_cache_service.py tests/api/test_embedding_cache_route.py tests/scripts/test_prepare_embedding_model_cache.py -q` | `33 passed, 2 warnings, 13.21s` |

结论：空间预检、下载适配器、状态推进、取消、清理、路由与脚本链路均已通过。

### 3.4 OCR 单元 / 非 slow 复验

| 命令 | 结果 |
|---|---|
| `python -m pytest tests/readers/test_ocr_continuous_tables.py tests/scripts/test_ocr_scan_benchmark.py -q -m "not slow"` | `12 passed, 1 deselected, 5.30s` |

结论：连续表格、跨页表头延续、基准资产构建和 recorded 模式校验通过。

### 3.5 OCR runtime 慢测与评测产物

| 命令 | 结果 |
|---|---|
| `python -m pytest tests/scripts/test_ocr_scan_benchmark.py -q -m slow` | `1 passed, 7 deselected, 2 warnings, 110.76s` |
| `python scripts/eval_ocr_scan_benchmark.py --manifest tests/fixtures/ocr_real_scan/manifest.json --mode recorded --output docs/20260817-kb-migration-agent-ocr-cache/artifacts/ocr-benchmark --min-score 0.8` | `overall_score = 1.0` |
| `python scripts/eval_ocr_scan_benchmark.py --manifest tests/fixtures/ocr_real_scan/manifest.json --mode runtime --output docs/20260817-kb-migration-agent-ocr-cache/artifacts/ocr-benchmark-runtime --min-score 0.8` | `overall_score = 1.0` |

对应产物：

- `docs/20260817-kb-migration-agent-ocr-cache/artifacts/ocr-benchmark/report.md`
- `docs/20260817-kb-migration-agent-ocr-cache/artifacts/ocr-benchmark/report.json`
- `docs/20260817-kb-migration-agent-ocr-cache/artifacts/ocr-benchmark-runtime/report.md`
- `docs/20260817-kb-migration-agent-ocr-cache/artifacts/ocr-benchmark-runtime/report.json`

两份 JSON 报告均显示以下五项指标全部为 `1.0`：

- `character_recall`
- `line_order_accuracy`
- `cell_recall`
- `header_continuation_accuracy`
- `continuous_table_merge_accuracy`

### 3.6 Python 全量非 slow 回归

| 命令 | 结果 |
|---|---|
| `python -m pytest tests/ -q -m "not slow"` | `864 passed, 2 deselected, 2 warnings, 68.25s` |

### 3.7 Web / Desktop 回归

| 命令 | 结果 |
|---|---|
| `node --test <webapp/src/**/*.test.js>` | `98 passed` |
| `npm run build --prefix webapp` | `passed` |
| `cmd /c "cd desktop && node --test src/*.test.js scripts/*.test.js"` | `86 passed` |
| `git diff --check` | `exit 0` |

说明：Desktop 用例在 Windows 主机上原先存在路径分隔符与执行位语义差异，已补齐兼容性断言并在当前工作区复验通过。

## 4. 覆盖率结果

覆盖率命令（按测试方案扩展到本次新增/修改的核心 Python 模块）：

```bash
python -m pytest \
  tests/api/test_kb_migration_service.py \
  tests/api/test_kb_migration_route.py \
  tests/api/test_kb_migration_integration.py \
  tests/api/test_access_token_service.py \
  tests/api/test_access_token_route.py \
  tests/api/test_open_api.py \
  tests/api/test_open_api_service.py \
  tests/api/test_open_api_integration.py \
  tests/api/test_embedding_download_adapter.py \
  tests/api/test_embedding_cache_service.py \
  tests/api/test_embedding_cache_route.py \
  tests/readers/test_ocr_continuous_tables.py \
  tests/scripts/test_manage_access_tokens.py \
  tests/scripts/test_prepare_embedding_model_cache.py \
  tests/scripts/test_ocr_scan_benchmark.py \
  --cov=api.services.kb_migration_service \
  --cov=api.routers.kb_migration \
  --cov=api.services.access_token_service \
  --cov=api.routers.access_tokens \
  --cov=api.services.open_api_service \
  --cov=api.services.open_api_audit \
  --cov=api.routers.open_api \
  --cov=api.services.embedding_cache_service \
  --cov=api.services.embedding_download_adapter \
  --cov=api.routers.embedding_cache \
  --cov=server.readers.ocr_layout \
  --cov=server.readers.image_ocr \
  --cov=server.readers.pdf_ocr \
  --cov=scripts.build_ocr_scan_benchmark \
  --cov=scripts.eval_ocr_scan_benchmark \
  --cov=scripts.manage_access_tokens \
  --cov=scripts.prepare_embedding_model_cache \
  --cov-report=term-missing \
  -q -m "not slow"
```

结果：`113 passed, 2 deselected, 2 warnings, 120.34s`，**TOTAL 88%**。

| 模块 | 覆盖率 |
|---|---:|
| `api.services.kb_migration_service` | 85% |
| `api.routers.kb_migration` | 89% |
| `api.services.access_token_service` | 92% |
| `api.routers.access_tokens` | 83% |
| `api.services.open_api_service` | 88% |
| `api.services.open_api_audit` | 100% |
| `api.routers.open_api` | 94% |
| `api.services.embedding_cache_service` | 92% |
| `api.services.embedding_download_adapter` | 85% |
| `api.routers.embedding_cache` | 88% |
| `server.readers.ocr_layout` | 94% |
| `server.readers.image_ocr` | 86% |
| `server.readers.pdf_ocr` | 86% |
| `scripts.build_ocr_scan_benchmark` | 93% |
| `scripts.eval_ocr_scan_benchmark` | 89% |
| `scripts.manage_access_tokens` | 96% |
| `scripts.prepare_embedding_model_cache` | 80% |

结论：本次新增/修改的核心 Python 模块全部达到测试方案要求的 `>= 80%` 门槛。

## 5. RTM 证据映射

| RTM 范围 | 直接证据 |
|---|---|
| `FR-MIG-01 ~ FR-MIG-09` | `tests/api/test_kb_migration_service.py`、`tests/api/test_kb_migration_route.py`、`tests/api/test_kb_migration_integration.py`、`webapp/src/api/migration.test.js`、`webapp/src/domain/kbMigration.test.js` |
| `FR-OCR-01 / FR-OCR-02` | `tests/fixtures/ocr_real_scan/manifest.json`、`tests/scripts/test_ocr_scan_benchmark.py`、`docs/.../artifacts/ocr-benchmark/report.json` |
| `FR-OCR-03 ~ FR-OCR-06` | `tests/readers/test_ocr_continuous_tables.py`、`tests/scripts/test_ocr_scan_benchmark.py`、`docs/.../artifacts/ocr-benchmark-runtime/report.json`、`docs/.../artifacts/ocr-benchmark/report.json` |
| `FR-OPEN-01 ~ FR-OPEN-08` | `tests/api/test_access_token_service.py`、`tests/api/test_access_token_route.py`、`tests/api/test_open_api.py`、`tests/api/test_open_api_service.py`、`tests/api/test_open_api_integration.py`、`tests/scripts/test_manage_access_tokens.py` |
| `FR-EMB-01 ~ FR-EMB-07` | `tests/api/test_embedding_download_adapter.py`、`tests/api/test_embedding_cache_service.py`、`tests/api/test_embedding_cache_route.py`、`tests/scripts/test_prepare_embedding_model_cache.py`、`webapp/src/domain/embeddingDownload.test.js`、`webapp/src/api/health.test.js` |
| 全量回归门禁 | `python -m pytest tests/ -q -m "not slow"`、Web 测试与构建、Desktop `node --test`、`git diff --check` |

## 6. 失败、修复与回归闭环

### 6.1 Windows 兼容性修复（Python / 脚本）

| 问题 | 修复 | 回归结果 |
|---|---|---|
| Access token 测试硬编码 POSIX `0600` 权限 | `tests/api/test_access_token_service.py` 新增 `assert_private_file()`；POSIX 继续校验 `0600`，Windows 仅校验敏感文件落盘 | Open API / token 专项 `18 passed` |
| Embedding 下载脚本与诊断测试硬编码 `/` 分隔符 | `tests/scripts/test_prepare_embedding_model_cache.py`、`tests/test_embedding_model_diagnostics.py`、`tests/scripts/test_diagnose_grain_qa_coverage.py` 改为路径标准化比较 | Embedding 专项 `33 passed` |
| 本地模型路径拼接混入 `/` 与 `\` | `server/utils/model_paths.py` 将 `model_path` 拆段后再 join，修复真实 mixed-separator 路径问题 | Embedding 专项与相关诊断用例通过 |
| OCR 基准测试在 GBK locale 下 `read_text()` 解码失败 | `tests/scripts/test_ocr_scan_benchmark.py` 显式加 `encoding="utf-8"` | OCR 非 slow 与 slow 都通过 |

### 6.2 Windows 兼容性修复（Desktop 测试）

| 问题 | 修复 | 回归结果 |
|---|---|---|
| Desktop 测试把 macOS/Unix 路径写死为 `/`，在 Windows 主机上断言失败 | `desktop/scripts/build-target.test.js`、`desktop/scripts/notarize-mac.test.js`、`desktop/scripts/verify-mac-release.test.js`、`desktop/scripts/verify-package.test.js`、`desktop/src/python-process.test.js`、`desktop/src/runtime-paths.test.js` 引入路径标准化断言 | `86 passed` |
| `ensureExecutable` 用例默认要求 POSIX execute bit | `desktop/scripts/release-preflight.test.js` 在 `win32` 下改为仅验证文件存在与调用成功，不再声称 Windows 必须具备 POSIX 执行位语义 | `86 passed` |

## 7. 已知 warning 与非阻断项

### 7.1 Python 运行期 warning

- `jieba/_compat.py`: `pkg_resources is deprecated`
- `pkg_resources.declare_namespace('google')` deprecation

### 7.2 OCR slow/runtime 补充 warning

- protobuf datetime deprecation warning
- Paddle/PaddleOCR 关于缺少 `ccache` 的提示

判断：以上 warning 均未导致用例失败，当前按“已知非阻断项”记录。

## 8. 仍未闭环的事项

### 8.1 OCR 真实实拍资产仍未补齐

当前 `tests/fixtures/ocr_real_scan/manifest.json` 中 3 个 `captured` 资产为：

- `captured-paragraph`
- `captured-single-table`
- `captured-continuous-table`

其字段均显示：

- `capture_method = "project_rendered_screenshot"`
- `physical_capture_verified = false`

这表示当前 checked-in 资产仍然是项目自制/渲染截图，不是“打印扫描件 / 手机实拍件”的已核验实物样本。

**因此：**

1. OCR 算法实现、layout 合并、跨页连续表头、recorded/runtime benchmark 都已经通过；
2. 但 `FR-OCR-01` 所要求的“真实实拍资产”证据仍处于外部资产待补状态；
3. 本报告只能证明“代码与基准闭环已完成”，不能把 OCR 的物理实拍验收说成已完全关闭。

### 8.2 迁移模块的状态判断

迁移服务、路由、集成链路与 Web 状态流均已有专项测试和回归证据，当前主要缺口已经从“代码/测试缺失”转为“测试报告未落档”。本报告补齐后，迁移模块可以判定为**实现完成，验收证据已归档**。

## 9. 最终结论

### 9.1 各模块结论

| 模块 | 结论 |
|---|---|
| 历史迁移 | **已完成**：代码、专项测试、覆盖率、回归与文档归档均已补齐 |
| Open API / access tokens | **已完成**：功能、权限、审计、CLI、回归均已通过 |
| Embedding 下载 | **已完成**：预检、下载、取消、清理、前后端状态流与覆盖率均已通过 |
| OCR 技术实现 | **已完成**：recorded/runtime benchmark、单元测试、slow/runtime 实测通过 |
| OCR 真实实拍资产 | **未完成**：外部实拍样本尚未补齐，`physical_capture_verified` 仍为 `false` |

### 9.2 是否允许进入 commit / push 阶段

结论：**允许进入当前代码与文档的 commit / push 阶段，但必须带着未完成项声明。**

约束如下：

1. 可以提交本次代码、测试兼容性修复与测试报告补档；
2. 可以把“迁移 / Open API / Embedding / OCR 技术实现”表述为已完成；
3. **不能**把“OCR 真实实拍资产验收”表述为已完成；
4. 后续若补入真实扫描件 / 手机实拍件，应重新执行 OCR benchmark 构建与评测，并更新本测试报告的结论。
